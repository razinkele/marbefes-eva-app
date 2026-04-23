"""
MARBEFES Physical Accounts — Calculation Module

Pure, stateless functions for ecosystem extent accounts, supply tables,
and validation.  No Shiny / UI dependencies.
"""

import logging
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj

from pa_config import (
    AREA_CONVERSIONS,
    DEFAULT_BENEFITS,
    EUNIS_LOOKUP,
    HABITAT_COLUMN_CANDIDATES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def reproject_to_metric(gdf: gpd.GeoDataFrame, original_crs=None) -> gpd.GeoDataFrame:
    """Reproject a WGS-84 GeoDataFrame to a metric CRS for area calculation.

    Strategy:
    1. If *original_crs* is supplied and is already projected, use it.
    2. Otherwise auto-detect the UTM zone from the centroid.
    3. Fallback to EPSG:3857 with a logged warning.
    """
    if original_crs is not None:
        crs_obj = None
        try:
            crs_obj = pyproj.CRS.from_user_input(original_crs)
        except Exception:
            # Extract EPSG:#### from decorated strings like "EPSG:32633 (UTM zone 33N)"
            match = re.search(r"EPSG:(\d+)", str(original_crs))
            if match:
                try:
                    crs_obj = pyproj.CRS.from_epsg(int(match.group(1)))
                except Exception:
                    logger.warning(
                        "Could not parse original_crs=%r; falling back to auto-detect.",
                        original_crs,
                    )
            else:
                logger.warning(
                    "Could not parse original_crs=%r; falling back to auto-detect.",
                    original_crs,
                )
        if crs_obj is not None and crs_obj.is_projected:
            return gdf.to_crs(crs_obj)

    try:
        bounds = gdf.total_bounds  # minx, miny, maxx, maxy
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        zone = int((center_lon + 180) / 6) + 1
        if center_lat >= 0:
            epsg = 32600 + zone
        else:
            epsg = 32700 + zone
        return gdf.to_crs(epsg=epsg)
    except Exception:
        logger.warning("UTM auto-detect failed; falling back to EPSG:3857.")
        return gdf.to_crs(epsg=3857)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_extent(
    gdf: gpd.GeoDataFrame,
    habitat_assignments: dict,
    unit: str = "Ha",
    original_crs=None,
    custom_lookup: dict | None = None,
) -> pd.DataFrame:
    """Compute habitat extent from assigned subzones.

    Parameters
    ----------
    gdf : GeoDataFrame
        Must be in WGS-84 (EPSG:4326) with columns 'Subzone ID' and 'geometry'.
    habitat_assignments : dict
        ``{subzone_id: eunis_code}`` mapping.
    unit : str
        Area unit key (``"Ha"`` or ``"km2"``).
    original_crs : str | None
        Optional CRS string to reproject to for area calculation.

    Returns
    -------
    pd.DataFrame
        Columns: ``eunis_code, habitat_name, area, pct_total``.
    """
    if "Subzone ID" not in gdf.columns:
        raise ValueError(
            "GeoDataFrame is missing required 'Subzone ID' column. "
            "Available columns: " + ", ".join(map(str, gdf.columns))
        )
    if gdf.crs is None:
        raise ValueError(
            "GeoDataFrame has no CRS defined. Please upload a spatial file "
            "with a defined coordinate reference system."
        )
    if not habitat_assignments:
        return pd.DataFrame(columns=["eunis_code", "habitat_name", "area", "pct_total"])

    # Filter to assigned subzones
    assigned_ids = set(habitat_assignments.keys())
    mask = gdf["Subzone ID"].isin(assigned_ids)
    subset = gdf.loc[mask].copy()

    if subset.empty:
        return pd.DataFrame(columns=["eunis_code", "habitat_name", "area", "pct_total"])

    # Map EUNIS code
    subset["eunis_code"] = subset["Subzone ID"].map(habitat_assignments)

    # Reproject and compute area in m²
    metric = reproject_to_metric(subset, original_crs)
    if unit not in AREA_CONVERSIONS:
        raise ValueError(
            f"Unknown area unit {unit!r}. Supported units: {list(AREA_CONVERSIONS.keys())}. "
            "Please select a valid unit in the Physical Accounts settings."
        )
    conversion = AREA_CONVERSIONS.get(unit, 10_000)
    metric["_area"] = metric.geometry.area / conversion

    # Aggregate by habitat
    agg = metric.groupby("eunis_code", as_index=False)["_area"].sum()
    agg.rename(columns={"_area": "area"}, inplace=True)
    total = agg["area"].sum()
    agg["pct_total"] = (agg["area"] / total * 100) if total > 0 else 0.0
    merged_lookup = dict(EUNIS_LOOKUP)
    if custom_lookup:
        merged_lookup.update(custom_lookup)
    agg["habitat_name"] = agg["eunis_code"].map(merged_lookup).fillna("Unknown")

    return agg[["eunis_code", "habitat_name", "area", "pct_total"]].reset_index(drop=True)


def detect_habitat_column(columns: list[str]) -> str | None:
    """Return the first column name that matches a known habitat-column candidate."""
    col_set = set(columns)
    for candidate in HABITAT_COLUMN_CANDIDATES:
        if candidate in col_set:
            return candidate
    return None


def assemble_supply_table(
    supply_data: dict,
    habitat_codes: list[str],
) -> pd.DataFrame:
    """Build a tidy supply table from nested supply data.

    Parameters
    ----------
    supply_data : dict
        ``{benefit_name: {eunis_code: quantity}}``.
    habitat_codes : list[str]
        EUNIS codes to use as columns.

    Returns
    -------
    pd.DataFrame
        Columns: ``Benefit, Unit, <code1>, <code2>, ...``
    """
    if not supply_data and not habitat_codes:
        return pd.DataFrame(columns=["Benefit", "Unit"])

    # Build a quick lookup for default benefit units
    unit_lookup = {b["name"]: b["unit"] for b in DEFAULT_BENEFITS}

    rows = []
    for benefit_name, code_map in supply_data.items():
        row: dict = {
            "Benefit": benefit_name,
            "Unit": unit_lookup.get(benefit_name, "units"),
        }
        for code in habitat_codes:
            row[code] = code_map.get(code, np.nan)
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["Benefit", "Unit"] + list(habitat_codes))

    return pd.DataFrame(rows, columns=["Benefit", "Unit"] + list(habitat_codes))


def validate_completeness(
    supply_data: dict,
    habitat_codes: list[str],
    benefit_names: list[str],
) -> dict:
    """Check how many supply-table cells are filled.

    Returns
    -------
    dict
        ``{filled, total, pct, empty_benefits, empty_habitats}``
    """
    total = len(benefit_names) * len(habitat_codes)
    if total == 0:
        return {
            "filled": 0,
            "total": 0,
            "pct": 0.0,
            "empty_benefits": list(benefit_names),
            "empty_habitats": list(habitat_codes),
        }

    filled = 0
    empty_benefits = []
    empty_habitats_set = set(habitat_codes)

    for bn in benefit_names:
        code_map = supply_data.get(bn, {})
        bn_filled = 0
        for code in habitat_codes:
            val = code_map.get(code)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                filled += 1
                bn_filled += 1
                empty_habitats_set.discard(code)
        if bn_filled == 0:
            empty_benefits.append(bn)

    return {
        "filled": filled,
        "total": total,
        "pct": round(filled / total * 100, 1) if total else 0.0,
        "empty_benefits": empty_benefits,
        "empty_habitats": sorted(empty_habitats_set),
    }


def validate_benefit_names(names: list[str]) -> bool:
    """Return True if all benefit names are unique."""
    return len(names) == len(set(names))


def clean_supply_value(val) -> float | None:
    """Return ``val`` as a non-negative finite float, or None if invalid.

    Rejects: None, non-numeric strings, NaN, ±infinity, and negative values.
    A physical supply quantity (tonnes, visitor-days, etc.) must be a real
    finite non-negative number.
    """
    if val is None:
        return None
    try:
        out = float(val)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(out) or out < 0:
        return None
    return out


# Deferred SEEA EA accounts (use table, condition account, extent-change
# account) are not implemented here. The one working flow — per-habitat
# condition from the EUNIS + EVA join — lives in
# `scripts/compute_physical_accounts.py`. See
# `docs/plans/2026-03-16-physical-accounts-plan.md` for the intended API.
