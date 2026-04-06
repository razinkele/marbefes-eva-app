"""Step 02: Reproject GeoPackage layers to a common CRS (EPSG:3346)."""
import os

import geopandas as gpd
from pyproj import CRS

from scripts.config import (
    CRS_FILES,
    EVA_FINAL_DIR,
    OUTPUT_DIR,
    TARGET_CRS,
)


def standardize_crs(gdf, target_crs=TARGET_CRS):
    """Reproject *gdf* to *target_crs* if its CRS differs. Returns a copy.

    If the GeoDataFrame has no CRS set, it is assigned *target_crs* (assumed
    to already be in that projection).
    """
    gdf = gdf.copy()
    target = CRS.from_user_input(target_crs)
    if gdf.crs is None:
        gdf = gdf.set_crs(target)
    elif not gdf.crs.equals(target):
        gdf = gdf.to_crs(target)
    return gdf


def run():
    """Read CRS_FILES from EVA_FINAL_DIR, reproject, and write to OUTPUT_DIR."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for filename in CRS_FILES:
        src = os.path.join(EVA_FINAL_DIR, filename)
        if not os.path.exists(src):
            print(f"  SKIP (not found): {filename}")
            continue

        print(f"  Processing: {filename}")
        gdf = gpd.read_file(src)
        gdf = standardize_crs(gdf)

        dst = os.path.join(OUTPUT_DIR, filename)
        gdf.to_file(dst, driver="GPKG")
        print(f"  Written: {dst}")


if __name__ == "__main__":
    run()
