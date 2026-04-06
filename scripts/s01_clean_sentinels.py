"""Step 01: Replace sentinel values (<= -9998) with NaN in AQ columns."""
import os

import geopandas as gpd
import numpy as np

from scripts.config import (
    EVA_FINAL_DIR,
    OUTPUT_DIR,
    SENTINEL_FILES,
    SENTINEL_THRESHOLD,
)


def find_aq_columns(columns):
    """Return column names starting with 'AQ' (excluding 'geometry')."""
    return [c for c in columns if c.startswith("AQ") and c != "geometry"]


def clean_sentinels(gdf):
    """Replace values <= SENTINEL_THRESHOLD with NaN in AQ columns. Returns a copy."""
    gdf = gdf.copy()
    aq_cols = find_aq_columns(gdf.columns)
    for col in aq_cols:
        gdf[col] = gdf[col].astype(float)
        gdf.loc[gdf[col] <= SENTINEL_THRESHOLD, col] = np.nan
    return gdf


def run():
    """Read SENTINEL_FILES from EVA_FINAL_DIR, clean, and write to OUTPUT_DIR."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for filename in SENTINEL_FILES:
        src = os.path.join(EVA_FINAL_DIR, filename)
        if not os.path.exists(src):
            print(f"  SKIP (not found): {filename}")
            continue

        print(f"  Processing: {filename}")
        gdf = gpd.read_file(src)
        gdf = clean_sentinels(gdf)

        dst = os.path.join(OUTPUT_DIR, filename)
        gdf.to_file(dst, driver="GPKG" if filename.endswith(".gpkg") else "ESRI Shapefile")
        print(f"  Written: {dst}")


if __name__ == "__main__":
    run()
