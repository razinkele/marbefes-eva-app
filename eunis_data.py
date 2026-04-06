# eunis_data.py
"""EUNIS Level 3 habitat data processing for Physical Accounts.

Pure functions operating on GeoDataFrames. No Shiny dependencies.
Handles EUSeaMap 2007/2012 codes (A5.25 format) — does NOT use
pa_config.EUNIS_LOOKUP (which uses 2022 codes like MA12).
"""
import logging

import geopandas as gpd
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_eunis_overlay(path: str) -> gpd.GeoDataFrame:
    """Load pre-extracted EUNIS overlay GeoPackage."""
    gdf = gpd.read_file(path)
    required = {"Subzone_ID", "dominant_EUNIS", "dominant_EUNIS_name"}
    missing = required - set(gdf.columns)
    if missing:
        raise ValueError(f"EUNIS overlay missing columns: {missing}")
    return gdf


def compute_eunis_extent(eunis_gdf: gpd.GeoDataFrame, unit: str = "Ha") -> pd.DataFrame:
    """Compute area per EUNIS class from dominant habitat assignments."""
    from pa_config import AREA_CONVERSIONS
    gdf = eunis_gdf.copy()
    # Reproject to metric CRS for area calculation
    if gdf.crs is not None and gdf.crs.is_projected:
        metric = gdf  # already metric (e.g., EPSG:3346)
    else:
        from pa_calculations import _reproject_to_metric
        metric = _reproject_to_metric(gdf, original_crs=gdf.crs)
    conversion = AREA_CONVERSIONS.get(unit, 10_000)
    metric["_area"] = metric.geometry.area / conversion

    agg = metric.groupby("dominant_EUNIS").agg(
        EUNIS_name=("dominant_EUNIS_name", "first"),
        n_subzones=("Subzone_ID", "count"),
        total_area=("_area", "sum"),
    ).reset_index().rename(columns={"dominant_EUNIS": "EUNIS_code"})

    total = agg["total_area"].sum()
    agg["pct_of_total"] = (agg["total_area"] / total * 100).round(1) if total > 0 else 0.0
    agg["total_area"] = agg["total_area"].round(2)
    agg["area_m2"] = (agg["total_area"] * AREA_CONVERSIONS.get(unit, 10_000)).round(0)

    return agg.sort_values("total_area", ascending=False).reset_index(drop=True)


def compute_eunis_condition(
    eunis_gdf: gpd.GeoDataFrame, eva_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Compute mean EVA scores per EUNIS class via Subzone_ID join."""
    # Join on Subzone_ID
    eunis_ids = eunis_gdf[["Subzone_ID", "dominant_EUNIS", "dominant_EUNIS_name"]].copy()

    eva_cols = ["Subzone_ID"]
    if "TotalEV_MAX" in eva_gdf.columns:
        eva_cols.append("TotalEV_MAX")
    elif "TotalEV" in eva_gdf.columns:
        eva_cols.append("TotalEV")
    if "Confidence" in eva_gdf.columns:
        eva_cols.append("Confidence")

    # Fallback: compute max of EC scores as Habitat_EV
    ec_score_cols = [c for c in ["AQ7_HABITATS", "ZooScore", "PhytoScore", "MaxBenthos", "EVA_all_fish"]
                     if c in eva_gdf.columns]
    eva_cols.extend(ec_score_cols)

    eva_subset = eva_gdf[eva_cols].drop(columns="geometry", errors="ignore") if "geometry" in eva_gdf.columns else eva_gdf[eva_cols]

    merged = eunis_ids.merge(eva_subset, on="Subzone_ID", how="left")

    # Habitat_EV = TotalEV_MAX if available, else max of EC scores
    if "TotalEV_MAX" in merged.columns:
        merged["_ev"] = merged["TotalEV_MAX"]
    elif ec_score_cols:
        merged["_ev"] = merged[ec_score_cols].max(axis=1, skipna=True)
    else:
        merged["_ev"] = np.nan

    merged["_conf"] = merged.get("Confidence", pd.Series(np.nan, index=merged.index))

    cond = merged.groupby("dominant_EUNIS").agg(
        EUNIS_name=("dominant_EUNIS_name", "first"),
        Habitat_EV=("_ev", "mean"),
        Habitat_confidence=("_conf", "mean"),
        n_subzones=("Subzone_ID", "count"),
    ).reset_index().rename(columns={"dominant_EUNIS": "EUNIS_code"})

    cond["Habitat_EV"] = cond["Habitat_EV"].round(3)
    cond["Habitat_confidence"] = cond["Habitat_confidence"].round(3)
    return cond


def compute_eunis_supply(
    eunis_gdf: gpd.GeoDataFrame, eva_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Compute ecosystem service proxies per EUNIS class."""
    eunis_ids = eunis_gdf[["Subzone_ID", "dominant_EUNIS", "dominant_EUNIS_name"]].copy()

    supply_map = {
        "EVA_all_fish": "Fisheries_proxy",
        "ZooScore": "FoodWeb_proxy",
        "PhytoScore": "PrimaryProd_proxy",
    }
    available = {k: v for k, v in supply_map.items() if k in eva_gdf.columns}

    eva_cols = ["Subzone_ID"] + list(available.keys())
    eva_subset = eva_gdf[eva_cols].drop(columns="geometry", errors="ignore") if "geometry" in eva_gdf.columns else eva_gdf[eva_cols]

    merged = eunis_ids.merge(eva_subset, on="Subzone_ID", how="left")

    supply = merged.groupby("dominant_EUNIS")[list(available.keys())].mean().round(3)
    supply = supply.reset_index().rename(columns={"dominant_EUNIS": "EUNIS_code", **available})

    # Add name
    name_map = eunis_gdf.drop_duplicates("dominant_EUNIS").set_index("dominant_EUNIS")["dominant_EUNIS_name"]
    supply["EUNIS_name"] = supply["EUNIS_code"].map(name_map)

    return supply


def build_accounts_summary(extent: pd.DataFrame, condition: pd.DataFrame) -> pd.DataFrame:
    """Build BBT8-format accounts table."""
    accounts = extent[["EUNIS_code", "EUNIS_name", "area_m2"]].merge(
        condition[["EUNIS_code", "Habitat_EV", "Habitat_confidence"]],
        on="EUNIS_code", how="left",
    )
    return accounts


def suggest_feature_classifications(eunis_gdf, feature_names):
    """Suggest HFS/BH and ESF classifications based on EUNIS habitat codes.

    For subzones where the dominant EUNIS type is a biogenic/reef habitat,
    any species features present in those subzones are candidates for HFS/BH.

    Args:
        eunis_gdf: EUNIS overlay with dominant_EUNIS per Subzone_ID
        feature_names: list of feature column names from the uploaded CSV

    Returns:
        dict: {feature_name: ["HFS_BH"]} for features in reef/biogenic subzones
              Only suggests, does not override existing user classifications.
    """
    from pa_config import EUNIS_HFS_BH_CODES, EUNIS_ESF_CODES

    # Find subzones with biogenic/reef habitats
    hfs_subzones = set()
    esf_subzones = set()
    for _, row in eunis_gdf.iterrows():
        code = row.get("dominant_EUNIS", "")
        if pd.isna(code):
            continue
        # Check if any HFS code is a prefix of or matches the dominant EUNIS
        for hfs_code in EUNIS_HFS_BH_CODES:
            if code.startswith(hfs_code) or hfs_code.startswith(code):
                hfs_subzones.add(row["Subzone_ID"])
                break
        for esf_code in EUNIS_ESF_CODES:
            if code.startswith(esf_code) or esf_code.startswith(code):
                esf_subzones.add(row["Subzone_ID"])
                break

    suggestions = {}
    # We can't know WHICH features are habitat-forming from EUNIS alone,
    # but we can flag that HFS/BH-type habitats exist in the study area
    if hfs_subzones:
        suggestions["_hfs_subzone_count"] = len(hfs_subzones)
        suggestions["_hfs_subzone_ids"] = hfs_subzones
    if esf_subzones:
        suggestions["_esf_subzone_count"] = len(esf_subzones)
        suggestions["_esf_subzone_ids"] = esf_subzones

    return suggestions


def build_missing_values(
    eunis_gdf: gpd.GeoDataFrame, eva_gdf: gpd.GeoDataFrame,
    total_bbt_area_m2: float,
) -> pd.DataFrame:
    """Identify subzones with no EUNIS match or no EVA data."""
    rows = []
    eunis_ids = set(eunis_gdf["Subzone_ID"])
    eva_ids = set(eva_gdf["Subzone_ID"]) if "Subzone_ID" in eva_gdf.columns else set()

    # Subzones in EUNIS but not in EVA
    for sid in eunis_ids - eva_ids:
        rows.append({"Subzone_ID": sid, "issue_type": "no_eva", "notes": "No EVA score data"})

    # Subzones with low EUNIS coverage
    if "coverage_pct" in eunis_gdf.columns:
        low_cov = eunis_gdf[eunis_gdf["coverage_pct"] < 50]
        for _, row in low_cov.iterrows():
            rows.append({
                "Subzone_ID": row["Subzone_ID"],
                "issue_type": "low_coverage",
                "notes": f"EUNIS coverage only {row['coverage_pct']:.0f}%",
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Subzone_ID", "issue_type", "notes"])
