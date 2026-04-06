"""Extract EUSeaMap EUNIS L3 overlay for a BBT hexagonal grid.

Usage:
    python scripts/extract_eunis_for_bbt.py \
        --euseamap path/to/EUSeaMap_2023.zip \
        --grid path/to/HexGrid.gpkg \
        --output tutorial/eunis_l3_lithuanian.gpkg
"""
import argparse
import logging
import os
import shutil
import sys
import tempfile
import zipfile

import fiona
import geopandas as gpd
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_gdb_from_zip(zip_path):
    """Extract FileGDB from zip to a temp directory. Returns (tmpdir, gdb_path)."""
    tmpdir = tempfile.mkdtemp()
    logger.info("Extracting %s to %s...", zip_path, tmpdir)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmpdir)
    # Find .gdb directory
    for item in os.listdir(tmpdir):
        if item.endswith(".gdb"):
            return tmpdir, os.path.join(tmpdir, item)
    raise FileNotFoundError("No .gdb found in zip")


def compute_overlay(grid_gdf, eunis_gdf):
    """For each hex cell, compute dominant EUNIS type by intersection area."""
    results = []
    total = len(grid_gdf)

    for i, (idx, hex_row) in enumerate(grid_gdf.iterrows()):
        if (i + 1) % 50 == 0 or i == 0:
            logger.info("  Processing hex %d/%d...", i + 1, total)

        hex_geom = hex_row.geometry
        hex_area = hex_geom.area

        # Find intersecting EUNIS polygons
        candidates = eunis_gdf[eunis_gdf.intersects(hex_geom)]
        if candidates.empty:
            results.append({
                "Subzone_ID": hex_row["Subzone_ID"],
                "dominant_EUNIS": np.nan,
                "dominant_EUNIS_name": np.nan,
                "habitat_count": 0,
                "dominant_pct": 0.0,
                "coverage_pct": 0.0,
                "geometry": hex_geom,
            })
            continue

        # Compute intersection areas
        intersections = []
        for _, eunis_row in candidates.iterrows():
            try:
                inter = hex_geom.intersection(eunis_row.geometry)
                if not inter.is_empty:
                    intersections.append({
                        "code": eunis_row["EUNIScomb"],
                        "name": eunis_row["EUNIScombD"],
                        "area": inter.area,
                    })
            except Exception:
                continue

        if not intersections:
            results.append({
                "Subzone_ID": hex_row["Subzone_ID"],
                "dominant_EUNIS": np.nan,
                "dominant_EUNIS_name": np.nan,
                "habitat_count": 0,
                "dominant_pct": 0.0,
                "coverage_pct": 0.0,
                "geometry": hex_geom,
            })
            continue

        inter_df = pd.DataFrame(intersections)
        # Group by code (same code may appear from multiple polygons)
        by_code = inter_df.groupby("code").agg(
            name=("name", "first"),
            total_area=("area", "sum"),
        ).sort_values("total_area", ascending=False)

        dominant_code = by_code.index[0]
        dominant_name = by_code.iloc[0]["name"]
        dominant_area = by_code.iloc[0]["total_area"]
        total_eunis_area = by_code["total_area"].sum()

        results.append({
            "Subzone_ID": hex_row["Subzone_ID"],
            "dominant_EUNIS": dominant_code,
            "dominant_EUNIS_name": dominant_name,
            "habitat_count": len(by_code),
            "dominant_pct": round(dominant_area / hex_area * 100, 1) if hex_area > 0 else 0,
            "coverage_pct": round(total_eunis_area / hex_area * 100, 1) if hex_area > 0 else 0,
            "geometry": hex_geom,
        })

    return gpd.GeoDataFrame(results, crs=grid_gdf.crs)


def main():
    parser = argparse.ArgumentParser(description="Extract EUSeaMap EUNIS overlay for a BBT grid")
    parser.add_argument("--euseamap", required=True, help="Path to EUSeaMap_2023.zip")
    parser.add_argument("--grid", required=True, help="Path to hex grid GeoPackage")
    parser.add_argument("--output", required=True, help="Output GeoPackage path")
    args = parser.parse_args()

    # Read grid
    logger.info("Reading grid: %s", args.grid)
    grid = gpd.read_file(args.grid)
    grid["Subzone_ID"] = [f"R{int(r):03d}_C{int(c):03d}"
                          for r, c in zip(grid["row_index"], grid["col_index"])]
    logger.info("  %d hexagons, CRS: %s", len(grid), grid.crs)

    # Get bbox in WGS84 for EUSeaMap query
    grid_4326 = grid.to_crs(epsg=4326)
    bbox = tuple(grid_4326.total_bounds)  # minx, miny, maxx, maxy
    logger.info("  BBox (WGS84): %s", bbox)

    # Extract and read EUSeaMap
    tmpdir, gdb_path = extract_gdb_from_zip(args.euseamap)
    try:
        layers = fiona.listlayers(gdb_path)
        # Prefer named layer; fall back to first
        layer = "EUSeaMap_2023" if "EUSeaMap_2023" in layers else layers[0]
        logger.info("Reading EUSeaMap layer '%s' with bbox filter...", layer)
        eunis = gpd.read_file(gdb_path, layer=layer, bbox=bbox)
        logger.info("  %d features in bbox", len(eunis))

        # Filter Na
        eunis = eunis[eunis["EUNIScomb"] != "Na"].copy()
        logger.info("  %d features after removing Na", len(eunis))

        if len(eunis) == 0:
            logger.error("No EUNIS features found in study area. Check bbox.")
            sys.exit(1)

        # Reproject to grid CRS
        eunis = eunis.to_crs(grid.crs)

        # Compute overlay
        logger.info("Computing spatial overlay...")
        result = compute_overlay(grid, eunis)

        # Write output
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        result.to_file(args.output, driver="GPKG")
        logger.info("Written %d hexagons to %s", len(result), args.output)

        # Summary
        valid = result["dominant_EUNIS"].notna()
        logger.info("  %d with EUNIS data, %d without", valid.sum(), (~valid).sum())
        logger.info("  Unique EUNIS types: %d", result["dominant_EUNIS"].nunique())
        logger.info("  Types: %s", result["dominant_EUNIS"].value_counts().to_dict())

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
