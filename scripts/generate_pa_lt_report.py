"""Generate the Lithuanian BBT5 Physical Accounts report end-to-end.

Produces in ``accounts_lithuania/`` a bundle that mirrors the
``accounts_crete/`` pattern plus SEEA EA tables + narrative:

  * eunis_aq_lt.gpkg   - per-hex EUNIS + AQ scores   (Crete: euniGRaq.shp)
  * habs_ev_lt.gpkg    - per-habitat rollup + habEV  (Crete: habsev.shp)
  * bbtland_lt.gpkg    - Lithuanian coastal land     (Crete: bbtland.shp)
  * maps/*.png         - EUNIS + AQ indicator maps   (Crete: aq*.JPG, habsEVclasses.JPG)
  * PhysicalAccounts_BBT8_LithuanianBBT5.xlsx - SEEA EA tables (BBT8 format)
  * PA_report.md       - narrative summary

Key pipeline detail: the EUNIS overlay (425 hexes, R###_C### Subzone_ID) and
ALL4EVA (721k features, sequential I###### Subzone_ID) use different grids
with no shared key. Reconciliation is a spatial join (representative points
of EVA polygons into hexes) + area-weighted aggregation per hex.

The Excel writer uses a direct pandas ExcelWriter path (without the
openpyxl restyle loop used by ``pa_export.generate_bbt8_workbook``). The
restyle loop reliably triggers STATUS_ACCESS_VIOLATION on this environment
when combined with the full GIS stack; the data content is identical.

Run with:
    micromamba run -n shiny python scripts/generate_pa_lt_report.py

Override EVA location with the ``EVA_FINAL_CORRECTED_DIR`` env var.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Paths + constants
# ---------------------------------------------------------------------------
def _resolve_eva_corrected_dir() -> Path:
    env_override = os.environ.get("EVA_FINAL_CORRECTED_DIR")
    if env_override:
        p = Path(env_override)
        if p.is_dir():
            return p
    candidate = PROJECT_ROOT.parent / "EVA_FINAL_corrected"
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(
        "Could not locate EVA_FINAL_corrected. Set EVA_FINAL_CORRECTED_DIR "
        f"or ensure it sits next to {PROJECT_ROOT.name}."
    )


EVA_CORRECTED_DIR = _resolve_eva_corrected_dir()
EUNIS_PATH = PROJECT_ROOT / "tutorial" / "eunis_l3_lithuanian.gpkg"
LAND_PATH = PROJECT_ROOT / "data" / "ne_10m_land.gpkg"
OUTPUT_DIR = PROJECT_ROOT / "accounts_lithuania"
MAPS_DIR = OUTPUT_DIR / "maps"

AQ_COLS = [
    "AQ7_HABITATS", "ZooScore", "PhytoScore",
    "AQ6_benthos", "AQ9_benthos", "AQ13_benthos",
    "MaxBenthos", "EVA_all_fish",
    "TotalEV_MAX", "TotalEV_MEAN",
]

EUNIS_COLORS = {
    "A3.4":                     "#006400",
    "A4.4":                     "#2e8b57",
    "A5.13":                    "#deb887",
    "A5.14":                    "#d2b48c",
    "A5.23":                    "#ffe4b5",
    "A5.24 or A5.33 or A5.34":  "#cd853f",
    "A5.25":                    "#f4a460",
    "A5.26 or A5.35 or A5.36":  "#8b7355",
    "A5.27 or A5.37":           "#a0522d",
}

EV_CLASS_COLORS = {
    "No Data":   "#eeeeee",
    "Very Low":  "#d73027",
    "Low":       "#fc8d59",
    "Medium":    "#fee08b",
    "High":      "#91cf60",
    "Very High": "#1a9850",
}


def classify_eva(val):
    if pd.isna(val):
        return "No Data"
    if val <= 1:
        return "Very Low"
    if val <= 2:
        return "Low"
    if val <= 3:
        return "Medium"
    if val <= 4:
        return "High"
    return "Very High"


def weighted_mean(values, weights):
    mask = values.notna() & (weights > 0)
    if not mask.any():
        return np.nan
    v = values[mask].astype(float)
    w = weights[mask].astype(float)
    return float(np.average(v, weights=w))


# ---------------------------------------------------------------------------
# 1. Load
# ---------------------------------------------------------------------------
def load_inputs():
    logger.info("Loading inputs...")
    logger.info("  EUNIS overlay: %s", EUNIS_PATH)
    overlay = gpd.read_file(str(EUNIS_PATH))
    logger.info("    %d hexes (CRS %s)", len(overlay), overlay.crs)

    eva_path = EVA_CORRECTED_DIR / "ALL4EVA_2025_fixed_geometries.gpkg"
    logger.info("  ALL4EVA: %s", eva_path)
    eva = gpd.read_file(str(eva_path))
    logger.info("    %d features (CRS %s)", len(eva), eva.crs)

    if overlay.crs != eva.crs:
        raise ValueError(
            f"CRS mismatch: overlay={overlay.crs} vs eva={eva.crs}. "
            "Reproject one before calling spatial_join_eva_to_hexes()."
        )
    return overlay, eva


# ---------------------------------------------------------------------------
# 2. Spatial join + per-hex aggregation
# ---------------------------------------------------------------------------
def spatial_join_eva_to_hexes(overlay: gpd.GeoDataFrame, eva: gpd.GeoDataFrame) -> pd.DataFrame:
    logger.info("Spatial join: EVA representative points -> EUNIS hexes...")
    attrs = [c for c in AQ_COLS if c in eva.columns]
    eva_pts = eva[attrs].copy()
    eva_pts["geometry"] = eva.geometry.representative_point()
    eva_pts["_eva_area_m2"] = eva.geometry.area
    eva_pts = gpd.GeoDataFrame(eva_pts, crs=eva.crs)

    hex_slim = overlay[["Subzone_ID", "geometry"]].rename(
        columns={"Subzone_ID": "hex_Subzone_ID"}
    )
    joined = gpd.sjoin(eva_pts, hex_slim, how="left", predicate="within")
    matched = int(joined["hex_Subzone_ID"].notna().sum())
    logger.info("  %d EVA points | %d matched a hex", len(joined), matched)

    logger.info("Aggregating per hex (area-weighted mean of %d fields)...", len(attrs))
    rows = []
    for hex_id, g in joined.dropna(subset=["hex_Subzone_ID"]).groupby("hex_Subzone_ID"):
        row = {"Subzone_ID": hex_id, "n_eva_points": int(len(g))}
        for c in attrs:
            row[c] = weighted_mean(g[c], g["_eva_area_m2"])
        rows.append(row)
    per_hex = pd.DataFrame(rows)
    logger.info("  %d hexes with EVA data", len(per_hex))
    return per_hex


# ---------------------------------------------------------------------------
# 3. Spatial products (eunis_aq_lt, habs_ev_lt, bbtland_lt)
# ---------------------------------------------------------------------------
def build_eunis_aq_lt(overlay: gpd.GeoDataFrame, per_hex: pd.DataFrame) -> gpd.GeoDataFrame:
    out = overlay[[
        "Subzone_ID", "dominant_EUNIS", "dominant_EUNIS_name",
        "habitat_count", "dominant_pct", "coverage_pct", "geometry",
    ]].merge(per_hex, on="Subzone_ID", how="left")
    if "TotalEV_MAX" in out.columns:
        out["TotalEV_class"] = out["TotalEV_MAX"].apply(classify_eva)
    for c in out.columns:
        if c != "geometry" and pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].round(3)
    return out


def build_habs_ev_lt(eunis_aq: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    df = eunis_aq.dropna(subset=["dominant_EUNIS"]).copy()
    df["area_m2"] = df.geometry.area
    rows = []
    for code, g in df.groupby("dominant_EUNIS"):
        name = (g["dominant_EUNIS_name"].dropna().iloc[0]
                if not g["dominant_EUNIS_name"].dropna().empty else code)
        area_m2 = float(g["area_m2"].sum())
        row = {
            "EUNIS_code": code,
            "EUNIS_name": name,
            "n_subzones": int(len(g)),
            "area_m2": round(area_m2, 2),
            "area_Ha": round(area_m2 / 10_000, 2),
            "habEV":            weighted_mean(g.get("TotalEV_MAX",  pd.Series([np.nan]*len(g))), g["area_m2"]),
            "AQ7_HABITATS_avg": weighted_mean(g.get("AQ7_HABITATS", pd.Series([np.nan]*len(g))), g["area_m2"]),
            "ZooScore_avg":     weighted_mean(g.get("ZooScore",     pd.Series([np.nan]*len(g))), g["area_m2"]),
            "PhytoScore_avg":   weighted_mean(g.get("PhytoScore",   pd.Series([np.nan]*len(g))), g["area_m2"]),
            "MaxBenthos_avg":   weighted_mean(g.get("MaxBenthos",   pd.Series([np.nan]*len(g))), g["area_m2"]),
            "AQ6_benthos_avg":  weighted_mean(g.get("AQ6_benthos",  pd.Series([np.nan]*len(g))), g["area_m2"]),
            "AQ9_benthos_avg":  weighted_mean(g.get("AQ9_benthos",  pd.Series([np.nan]*len(g))), g["area_m2"]),
            "AQ13_benthos_avg": weighted_mean(g.get("AQ13_benthos", pd.Series([np.nan]*len(g))), g["area_m2"]),
            "EVA_all_fish_avg": weighted_mean(g.get("EVA_all_fish", pd.Series([np.nan]*len(g))), g["area_m2"]),
            "geometry": g.geometry.union_all(),
        }
        rows.append(row)
    out = gpd.GeoDataFrame(rows, crs=eunis_aq.crs)
    out["habEV_class"] = out["habEV"].apply(classify_eva)
    for c in out.columns:
        if c != "geometry" and pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].round(3)
    return out.sort_values("area_Ha", ascending=False).reset_index(drop=True)


def build_bbtland_lt(overlay: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if not LAND_PATH.exists():
        logger.warning("  ne_10m_land.gpkg not found; skipping bbtland")
        return gpd.GeoDataFrame(columns=["context", "geometry"], crs=overlay.crs)
    land = gpd.read_file(str(LAND_PATH))
    bounds = overlay.to_crs(land.crs).total_bounds
    buf = 0.2
    envelope = gpd.GeoSeries.from_xy(
        [bounds[0] - buf, bounds[2] + buf],
        [bounds[1] - buf, bounds[3] + buf],
        crs=land.crs,
    ).union_all().envelope
    clip_box = gpd.GeoDataFrame({"geometry": [envelope]}, crs=land.crs)
    land_clip = gpd.overlay(land, clip_box, how="intersection")
    land_clip["context"] = "coastal_land"
    return land_clip.to_crs(overlay.crs)[["context", "geometry"]]


# ---------------------------------------------------------------------------
# 4. Maps
# ---------------------------------------------------------------------------
def _save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("  %s", path.name)


def map_eunis_classes(overlay, bbtland, out_path: Path):
    gdf = overlay.to_crs(epsg=4326)
    land = bbtland.to_crs(epsg=4326) if len(bbtland) else None
    fig, ax = plt.subplots(figsize=(10, 8))
    if land is not None and len(land):
        land.plot(ax=ax, color="#e8e4d9", edgecolor="#9c9588", linewidth=0.5, zorder=0)
    no_data = gdf[gdf["dominant_EUNIS"].isna()]
    if not no_data.empty:
        no_data.plot(ax=ax, color="#eeeeee", edgecolor="#bbb", linewidth=0.3, zorder=1)
    for code, color in EUNIS_COLORS.items():
        sub = gdf[gdf["dominant_EUNIS"] == code]
        if not sub.empty:
            sub.plot(ax=ax, color=color, edgecolor="#333", linewidth=0.3, zorder=2)
    ax.set_title("EUNIS L3 Habitat Classes - Lithuanian BBT5",
                 fontsize=13, fontweight="bold", color="#006994")
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    patches = [mpatches.Patch(color=c, label=code) for code, c in EUNIS_COLORS.items()]
    patches.append(mpatches.Patch(color="#eeeeee", label="No data"))
    ax.legend(handles=patches, loc="lower left", fontsize=7, framealpha=0.9)
    plt.tight_layout()
    _save(fig, out_path)


def map_indicator(eunis_aq, bbtland, column, title, out_path: Path):
    gdf = eunis_aq.to_crs(epsg=4326)
    land = bbtland.to_crs(epsg=4326) if len(bbtland) else None
    fig, ax = plt.subplots(figsize=(10, 8))
    if land is not None and len(land):
        land.plot(ax=ax, color="#e8e4d9", edgecolor="#9c9588", linewidth=0.5, zorder=0)
    gdf.plot(column=column, ax=ax, cmap="RdYlGn", vmin=0, vmax=5,
             edgecolor="#333", linewidth=0.2, legend=True,
             missing_kwds={"color": "#eeeeee"}, zorder=2,
             legend_kwds={"label": f"{title} (0-5)", "shrink": 0.7})
    ax.set_title(f"{title} - Lithuanian BBT5",
                 fontsize=13, fontweight="bold", color="#006994")
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    plt.tight_layout()
    _save(fig, out_path)


def map_habEV_classes(habs_ev, bbtland, out_path: Path):
    gdf = habs_ev.to_crs(epsg=4326)
    land = bbtland.to_crs(epsg=4326) if len(bbtland) else None
    fig, ax = plt.subplots(figsize=(10, 8))
    if land is not None and len(land):
        land.plot(ax=ax, color="#e8e4d9", edgecolor="#9c9588", linewidth=0.5, zorder=0)
    for cls, color in EV_CLASS_COLORS.items():
        sub = gdf[gdf["habEV_class"] == cls]
        if not sub.empty:
            sub.plot(ax=ax, color=color, edgecolor="#333", linewidth=0.4, zorder=2)
    ax.set_title("habEV Classes - Lithuanian BBT5 (area-weighted TotalEV per habitat)",
                 fontsize=12, fontweight="bold", color="#006994")
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    patches = [mpatches.Patch(color=c, label=n) for n, c in EV_CLASS_COLORS.items()]
    ax.legend(handles=patches, loc="lower left", fontsize=9, framealpha=0.9)
    plt.tight_layout()
    _save(fig, out_path)


# ---------------------------------------------------------------------------
# 5. Excel workbook (BBT8 format)
# ---------------------------------------------------------------------------
def write_excel(overlay, eunis_aq, habs_ev, out_path: Path):
    logger.info("Writing Excel workbook...")
    extent = habs_ev[["EUNIS_code", "EUNIS_name", "n_subzones",
                       "area_m2", "area_Ha"]].copy()
    extent["pct_of_total"] = (extent["area_Ha"] / extent["area_Ha"].sum() * 100).round(2)
    extent = extent.rename(columns={"area_Ha": "total_area"})

    condition = habs_ev[[
        "EUNIS_code", "EUNIS_name", "n_subzones",
        "habEV", "habEV_class",
        "AQ7_HABITATS_avg", "MaxBenthos_avg",
        "ZooScore_avg", "PhytoScore_avg",
    ]].rename(columns={"habEV": "Habitat_EV"}).copy()

    supply = habs_ev[["EUNIS_code", "EUNIS_name",
                       "EVA_all_fish_avg", "ZooScore_avg", "PhytoScore_avg"]].rename(columns={
        "EVA_all_fish_avg": "Fisheries_proxy",
        "ZooScore_avg":     "FoodWeb_proxy",
        "PhytoScore_avg":   "PrimaryProd_proxy",
    }).copy()

    mv_cols = [c for c in ["Subzone_ID", "dominant_EUNIS", "TotalEV_MAX"]
               if c in eunis_aq.columns]
    mv = eunis_aq[mv_cols].rename(columns={
        "dominant_EUNIS": "EUNIS_code",
        "TotalEV_MAX":    "Habitat_EV",
    }).copy()
    mv["Habitat_confidence"] = np.nan

    # Missing values: hexes with no EUNIS or low coverage
    miss_rows = []
    for _, r in overlay.iterrows():
        if pd.isna(r.get("dominant_EUNIS")):
            miss_rows.append({
                "Subzone_ID": r["Subzone_ID"], "issue_type": "no_eunis",
                "notes": "No EUNIS attribution (outside EMODnet EUSeaMap 2023 coverage)",
            })
        elif r.get("coverage_pct", 100) < 50:
            miss_rows.append({
                "Subzone_ID": r["Subzone_ID"], "issue_type": "low_coverage",
                "notes": f"EUNIS coverage only {r['coverage_pct']:.0f}%",
            })
    missing = pd.DataFrame(miss_rows) if miss_rows else pd.DataFrame(
        columns=["Subzone_ID", "issue_type", "notes"]
    )

    area_sum = habs_ev[["EUNIS_code", "area_m2"]].rename(
        columns={"EUNIS_code": "EUNIS2019C", "area_m2": "Sum of area_m2"}
    )
    accounts = habs_ev[["EUNIS_code", "EUNIS_name", "area_m2", "habEV"]].rename(
        columns={"habEV": "Habitat_EV", "EUNIS_code": "EUNIS2019C", "EUNIS_name": "Habitat"}
    )
    accounts["Habitat_confidence"] = np.nan

    metadata = {
        "Report": "SEEA EA Physical Accounts (BBT8 format)",
        "BBT": "BBT5 - Lithuanian Baltic Sea coast and Curonian Lagoon",
        "EAA": "Lithuanian territorial waters + Curonian Lagoon",
        "Year": "2017-2023",
        "Framework": "SEEA EA / MARBEFES WP4",
        "Generated": datetime.now().strftime("%Y-%m-%d"),
        "EUNIS_Source": "EMODnet EUSeaMap 2023",
        "EVA_Source": f"{EVA_CORRECTED_DIR.name}/ALL4EVA_2025_fixed_geometries.gpkg",
        "Join_Method": "Spatial join (representative points of EVA polygons into "
                        "EUNIS hexes), area-weighted per-hex aggregation",
        "Contact": "Klaipeda University / MARBEFES",
    }
    readme_df = pd.DataFrame(list(metadata.items()), columns=["Parameter", "Value"])

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        readme_df.to_excel(writer, sheet_name="ReadMe", index=False)
        mv.to_excel(writer, sheet_name="main_values", index=False)
        area_sum.to_excel(writer, sheet_name="habitat_area_sum", index=False)
        accounts.to_excel(writer, sheet_name="accounts", index=False)
        if not missing.empty:
            missing.to_excel(writer, sheet_name="missing_values", index=False)
        extent.to_excel(writer, sheet_name="extent", index=False)
        condition.to_excel(writer, sheet_name="condition", index=False)
        supply.to_excel(writer, sheet_name="supply", index=False)
    logger.info("  %s", out_path)
    return extent, condition, supply, accounts, missing


# ---------------------------------------------------------------------------
# 6. Narrative
# ---------------------------------------------------------------------------
def write_narrative(overlay, eva, extent, habs_ev, out_path: Path):
    now = datetime.now().strftime("%Y-%m-%d")
    total_area_ha = float(extent["total_area"].sum())
    n_habitats = int(len(extent))
    top = extent.sort_values("total_area", ascending=False).head(3)
    with_ev = int(habs_ev["habEV"].notna().sum())

    md = f"""# Physical Accounts - Lithuanian BBT5 (Curonian Lagoon & Baltic Sea coast)

*MARBEFES WP4 | SEEA EA Framework | Generated {now}*

## 1. Overview

This report presents ecosystem **extent**, **condition**, and **supply**
accounts for the Lithuanian BBT5, following the SEEA Ecosystem Accounting
framework and the MARBEFES WP4 guidance (Luisetti & Burdon, 2023). Habitat
classification is **EUNIS Level 3**, derived from EMODnet EUSeaMap 2023
and pre-joined to a 3 km hexagonal grid covering the LT BBT
(`tutorial/eunis_l3_lithuanian.gpkg`, 425 hexes). Ecological Value scores
come from the MARBEFES EVA pipeline (`ALL4EVA_2025_fixed_geometries`,
sentinel-corrected Sept 2025, 721,900 features on a finer native grid).

**Note on join method.** The EUNIS overlay and the EVA pipeline use two
different Subzone_ID schemes (`R###_C###` vs `I######`). This report
therefore uses a **spatial join** (representative points of EVA polygons
into the EUNIS hexes) with area-weighted per-hex aggregation - see
`Join_Method` in the ReadMe sheet.

**Headline figures**

| Metric | Value |
|---|---:|
| EUNIS L3 classes identified | {n_habitats} |
| Hexagonal subzones total | {len(overlay)} |
| Subzones with EUNIS attribution | {int(overlay['dominant_EUNIS'].notna().sum())} |
| Habitats with habEV computed | {with_ev} / {n_habitats} |
| Total mapped extent | {total_area_ha:,.0f} Ha |
| EVA source features | {len(eva):,} |

**Top three habitats by area**

| Rank | EUNIS | Name | Area (Ha) | % | habEV |
|---:|---|---|---:|---:|---:|
"""
    for i, (_, row) in enumerate(top.iterrows(), start=1):
        code = row["EUNIS_code"]
        habev_val = habs_ev.loc[habs_ev["EUNIS_code"] == code, "habEV"].iloc[0]
        habev_txt = f"{habev_val:.2f}" if pd.notna(habev_val) else "n/a"
        md += (f"| {i} | {code} | {row['EUNIS_name']} | "
               f"{row['total_area']:,.0f} | {row['pct_of_total']:.1f} | {habev_txt} |\n")

    md += """
## 2. Extent Account

See `PhysicalAccounts_BBT8_LithuanianBBT5.xlsx` -> *extent*, *habitat_area_sum*
and *accounts* sheets, plus `habs_ev_lt.gpkg` for per-habitat geometries
(dissolved from hexagonal subzones).

## 3. Condition Account

Condition is expressed through per-habitat **habEV**, an area-weighted mean
of the MARBEFES EVA TotalEV_MAX aggregated score (0-5 scale). The companion
`habs_ev_lt.gpkg` encodes this as the `habEV` field plus a `habEV_class`
categorical bin (Very Low -> Very High), visualized in `maps/habEV_classes.png`.

All EVA Confidence scores in the LT pipeline are Low - each ecosystem
component answered only 1-4 of 7-8 possible Assessment Questions (see
`EVA_FINAL_corrected/validation_report.md`).

## 4. Supply Account (Proxy)

Three ecosystem-service proxies derived from EVA scores, per EUNIS class:

- **Fisheries_proxy** - EVA_all_fish (0-5 scale)
- **FoodWeb_proxy** - ZooScore (0-5 scale)
- **PrimaryProd_proxy** - PhytoScore (0-5 scale)

Full SEEA EA supply accounting in physical units (tonnes of fish, tCO2eq,
visitor-days, tonnes N removed, Ha protected) is not yet available for the
LT BBT and is flagged as *future work* per the DOCX methodology.

## 5. Data Quality

The *missing_values* sheet lists hexes with no EUNIS attribution (outside
EMODnet EUSeaMap 2023 coverage) or partial coverage (<50% EMODnet overlap).

## Methodology

- **Framework:** SEEA Ecosystem Accounting (UN, 2021).
- **Guidance:** MARBEFES WP4.3 Deliverable D4.2 (Luisetti & Burdon, 2023).
- **Habitat classification:** EUNIS Level 3 (EMODnet EUSeaMap 2023).
- **Spatial unit:** 3 km hexagonal grid (EPSG:3346 / LKS94).
- **EVA reconciliation:** representative-point spatial join + area-weighted
  per-hex aggregation.
- **Ecological Value:** MARBEFES EVA aggregated score (0-5), area-weighted
  to habitat level as *habEV*.

## Files in this bundle

| File | Role | Analogue in accounts_crete/ |
|---|---|---|
| `PhysicalAccounts_BBT8_LithuanianBBT5.xlsx` | SEEA EA tables (BBT8 format) | - |
| `eunis_aq_lt.gpkg` | Per-hex EUNIS + AQ | `euniGRaq.shp` |
| `habs_ev_lt.gpkg` | Per-habitat rollup with habEV | `habsev.shp` |
| `bbtland_lt.gpkg` | Coastal land context | `bbtland.shp` |
| `maps/EUNIS_classes.png` | Habitat classification map | - |
| `maps/habEV_classes.png` | habEV class map | `habsEVclasses.JPG` |
| `maps/TotalEV_MAX.png`, `maps/AQ_*.png`, etc. | Indicator maps | `aq1_2_7_8.JPG`, `aq9.JPG` |
| `PA_report.md` | This narrative | - |

## References

- Luisetti T., Burdon D. et al. (2023). *Draft Guidance on Socio-Economic
  Frameworks and Methods - Physical Accounts Section.* MARBEFES D4.2.
- UN (2021). *System of Environmental-Economic Accounting - Ecosystem
  Accounting (SEEA EA).*
- EMODnet (2023). *EUSeaMap 2023.*
- Razinkovas-Baziukas A. et al. (2025). *Lithuanian BBT5 EVA report.* KU/MARBEFES.
- Franco A. & Amorim E. (2025). *EVA guidance.* MARBEFES WP4.1.
"""
    out_path.write_text(md, encoding="utf-8")
    logger.info("  %s", out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MAPS_DIR.mkdir(parents=True, exist_ok=True)

    overlay, eva = load_inputs()
    per_hex = spatial_join_eva_to_hexes(overlay, eva)

    logger.info("Building spatial products...")
    eunis_aq = build_eunis_aq_lt(overlay, per_hex)
    eunis_aq.to_file(str(OUTPUT_DIR / "eunis_aq_lt.gpkg"),
                     layer="eunis_aq_lt", driver="GPKG")
    logger.info("  eunis_aq_lt.gpkg: %d hexes", len(eunis_aq))

    habs_ev = build_habs_ev_lt(eunis_aq)
    habs_ev.to_file(str(OUTPUT_DIR / "habs_ev_lt.gpkg"),
                    layer="habs_ev_lt", driver="GPKG")
    logger.info("  habs_ev_lt.gpkg: %d habitats", len(habs_ev))

    bbtland = build_bbtland_lt(overlay)
    if len(bbtland):
        bbtland.to_file(str(OUTPUT_DIR / "bbtland_lt.gpkg"),
                        layer="bbtland_lt", driver="GPKG")
        logger.info("  bbtland_lt.gpkg: %d land polygons", len(bbtland))

    logger.info("Rendering maps...")
    map_eunis_classes(overlay, bbtland, MAPS_DIR / "EUNIS_classes.png")
    map_habEV_classes(habs_ev, bbtland, MAPS_DIR / "habEV_classes.png")
    for column, title, fname in [
        ("TotalEV_MAX",   "Total Ecological Value",         "TotalEV_MAX.png"),
        ("MaxBenthos",    "Benthos AQ (max)",               "Benthos_MAX.png"),
        ("ZooScore",      "Zooplankton AQ",                 "AQ_Zooplankton.png"),
        ("PhytoScore",    "Phytoplankton AQ",               "AQ_Phytoplankton.png"),
        ("AQ7_HABITATS",  "AQ7 - Habitat-forming species",  "AQ7_Habitats.png"),
    ]:
        if column in eunis_aq.columns:
            map_indicator(eunis_aq, bbtland, column, title, MAPS_DIR / fname)

    extent, _condition, _supply, _accounts, _missing = write_excel(
        overlay, eunis_aq, habs_ev,
        OUTPUT_DIR / "PhysicalAccounts_BBT8_LithuanianBBT5.xlsx",
    )

    write_narrative(overlay, eva, extent, habs_ev, OUTPUT_DIR / "PA_report.md")
    logger.info("\nDone. Outputs: %s", OUTPUT_DIR)


if __name__ == "__main__":
    main()
