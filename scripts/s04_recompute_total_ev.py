"""Task 5: Recompute TotalEV (MAX / MEAN) and verify Benthos MAX."""
import logging
import os

import geopandas as gpd
import numpy as np
import pandas as pd

from scripts.config import (
    BENTHOS_AQ_COLUMNS,
    COMBINED_LAYER,
    EC_SCORE_COLUMNS,
    OUTPUT_DIR,
)

logger = logging.getLogger(__name__)


def verify_benthos_max(gdf: gpd.GeoDataFrame) -> list[str]:
    """Check that MaxBenthos == max(AQ6_benthos, AQ8_benthos, AQ9_benthos, AQ13_benthos).

    Returns a list of issue descriptions (empty if all OK).
    Tolerance: 0.01.
    """
    issues: list[str] = []
    if "MaxBenthos" not in gdf.columns:
        return issues
    present = [c for c in BENTHOS_AQ_COLUMNS if c in gdf.columns]
    if not present:
        return issues

    expected_max = gdf[present].max(axis=1, skipna=True)
    actual = gdf["MaxBenthos"]

    # Compare where both are non-null
    mask = actual.notna() & expected_max.notna()
    diff = (actual[mask] - expected_max[mask]).abs()
    bad = diff[diff > 0.01]
    if not bad.empty:
        issues.append(
            f"MaxBenthos mismatch in {len(bad)} rows "
            f"(max diff={bad.max():.4f})"
        )
    return issues


def compute_total_ev(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add TotalEV_MAX, TotalEV_MEAN, EC_count, Dominant_EC columns."""
    gdf = gdf.copy()

    # Build matrix of EC scores
    ec_names: list[str] = []
    ec_cols: list[str] = []
    for name, col in EC_SCORE_COLUMNS.items():
        if col in gdf.columns:
            ec_names.append(name)
            ec_cols.append(col)

    if not ec_cols:
        gdf["TotalEV_MAX"] = np.nan
        gdf["TotalEV_MEAN"] = np.nan
        gdf["EC_count"] = 0
        gdf["Dominant_EC"] = None
        return gdf

    ec_matrix = gdf[ec_cols].astype(float)

    gdf["TotalEV_MAX"] = ec_matrix.max(axis=1, skipna=True)
    gdf["TotalEV_MEAN"] = ec_matrix.mean(axis=1, skipna=True)
    gdf["EC_count"] = ec_matrix.notna().sum(axis=1)

    # All-NaN rows → NaN for MAX and MEAN
    all_nan = ec_matrix.isna().all(axis=1)
    gdf.loc[all_nan, "TotalEV_MAX"] = np.nan
    gdf.loc[all_nan, "TotalEV_MEAN"] = np.nan

    # Dominant EC — idxmax raises on all-NaN rows, so fill temporarily
    col_to_name = {col: name for name, col in zip(ec_names, ec_cols)}
    if all_nan.any():
        filled = ec_matrix.copy()
        filled.loc[all_nan] = 0  # temporary fill so idxmax won't raise
        dominant = filled.idxmax(axis=1, skipna=True)
    else:
        dominant = ec_matrix.idxmax(axis=1, skipna=True)
    gdf["Dominant_EC"] = dominant.map(col_to_name)
    gdf.loc[all_nan, "Dominant_EC"] = None

    return gdf


def run() -> None:
    """Read corrected combined layer, verify benthos, compute total EV, write back."""
    path = os.path.join(OUTPUT_DIR, COMBINED_LAYER)
    logger.info("Reading %s", path)
    gdf = gpd.read_file(path)

    # Verify benthos MAX
    issues = verify_benthos_max(gdf)
    if issues:
        for issue in issues:
            logger.warning("Benthos MAX issue: %s", issue)
        logger.info("Recomputing MaxBenthos from AQ columns")
        present = [c for c in BENTHOS_AQ_COLUMNS if c in gdf.columns]
        if present:
            gdf["MaxBenthos"] = gdf[present].max(axis=1, skipna=True)
            # All-NaN → NaN
            all_nan = gdf[present].isna().all(axis=1)
            gdf.loc[all_nan, "MaxBenthos"] = np.nan
    else:
        logger.info("Benthos MAX verification passed")

    # Compute total EV
    gdf = compute_total_ev(gdf)

    # Log stats
    logger.info(
        "TotalEV_MAX — min=%.3f, max=%.3f, mean=%.3f, NaN=%d",
        gdf["TotalEV_MAX"].min(),
        gdf["TotalEV_MAX"].max(),
        gdf["TotalEV_MAX"].mean(),
        gdf["TotalEV_MAX"].isna().sum(),
    )
    logger.info(
        "TotalEV_MEAN — min=%.3f, max=%.3f, mean=%.3f, NaN=%d",
        gdf["TotalEV_MEAN"].min(),
        gdf["TotalEV_MEAN"].max(),
        gdf["TotalEV_MEAN"].mean(),
        gdf["TotalEV_MEAN"].isna().sum(),
    )
    logger.info("EC_count distribution:\n%s", gdf["EC_count"].value_counts().sort_index())
    logger.info("Dominant_EC distribution:\n%s", gdf["Dominant_EC"].value_counts())

    # Write back
    logger.info("Writing %s", path)
    gdf.to_file(path, driver="GPKG")
    logger.info("Done — %d features written", len(gdf))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
