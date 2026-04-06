"""Step 03: Generate unique Subzone_ID for every feature."""
import os
import warnings

import geopandas as gpd

from scripts.config import OUTPUT_DIR


def generate_subzone_ids(gdf):
    """Add a *Subzone_ID* column based on available index columns.

    Strategy (in priority order):
    1. ``row_index`` + ``col_index`` → ``"R012_C017"``
    2. ``fid`` → ``"F000001"``
    3. DataFrame index → ``"I000000"`` (with a warning)

    Returns a copy of *gdf* with the new column.
    """
    gdf = gdf.copy()

    if "row_index" in gdf.columns and "col_index" in gdf.columns:
        gdf["Subzone_ID"] = [
            f"R{int(r):03d}_C{int(c):03d}"
            for r, c in zip(gdf["row_index"], gdf["col_index"])
        ]
    elif "fid" in gdf.columns:
        gdf["Subzone_ID"] = [f"F{int(f):06d}" for f in gdf["fid"]]
    else:
        warnings.warn(
            "No row_index/col_index or fid columns found; falling back to "
            "DataFrame index for Subzone_ID generation."
        )
        gdf["Subzone_ID"] = [f"I{int(i):06d}" for i in gdf.index]

    return gdf


def run():
    """Add Subzone_ID to every .gpkg and .shp file in OUTPUT_DIR."""
    if not os.path.isdir(OUTPUT_DIR):
        print(f"  OUTPUT_DIR does not exist: {OUTPUT_DIR}")
        return

    for filename in os.listdir(OUTPUT_DIR):
        if not (filename.endswith(".gpkg") or filename.endswith(".shp")):
            continue

        src = os.path.join(OUTPUT_DIR, filename)
        print(f"  Processing: {filename}")
        gdf = gpd.read_file(src)
        gdf = generate_subzone_ids(gdf)

        driver = "GPKG" if filename.endswith(".gpkg") else "ESRI Shapefile"
        gdf.to_file(src, driver=driver)
        print(f"  Written: {src}")


if __name__ == "__main__":
    run()
