# scripts/prepare_tutorial_data.py
"""Extract tutorial CSV files from EVA_FINAL spatial datasets.

One-time script. Reads GeoPackages/Shapefiles, extracts species-level
data, joins to hexagonal grid, writes clean CSVs to tutorial/.
"""
import logging
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

EVA_FINAL = os.path.normpath(
    r"C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\EVA_FINAL"
)
TUTORIAL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "tutorial")
)


def prepare_grid():
    """Read hex grid, reproject to WGS84, add Subzone ID, write GeoJSON."""
    logger.info("--- Grid ---")
    src = os.path.join(EVA_FINAL, "EVA Grids", "HexGrid3kmLithuanianBBT.gpkg")
    gdf = gpd.read_file(src)
    logger.info("  Read %d hexagons (CRS: %s)", len(gdf), gdf.crs)

    # Generate Subzone ID
    gdf["Subzone ID"] = [
        f"R{int(r):03d}_C{int(c):03d}"
        for r, c in zip(gdf["row_index"], gdf["col_index"])
    ]

    # Keep only Subzone ID + geometry, reproject to WGS84
    gdf = gdf[["Subzone ID", "geometry"]].to_crs(epsg=4326)

    dst = os.path.join(TUTORIAL_DIR, "grid.geojson")
    gdf.to_file(dst, driver="GeoJSON")
    logger.info("  Written %d hexagons to %s", len(gdf), dst)
    return set(gdf["Subzone ID"])


def prepare_benthos(grid_ids):
    """Extract benthos species data from Benthos_Final.shp."""
    logger.info("--- Benthos ---")
    src = os.path.join(EVA_FINAL, "Benthos_EVA", "Benthos_Final.shp")
    gdf = gpd.read_file(src)
    logger.info("  Read %d features, columns: %s", len(gdf), list(gdf.columns))

    # Species columns
    species_cols = ["Monoporeia", "Macoma", "Mytilus", "Furcellari", "AI", "HForming"]
    missing = [c for c in species_cols if c not in gdf.columns]
    if missing:
        logger.error("  Missing columns: %s", missing)
        return

    # Join to grid: read grid with row_index/col_index for spatial join
    grid_src = os.path.join(EVA_FINAL, "EVA Grids", "HexGrid3kmLithuanianBBT.gpkg")
    grid = gpd.read_file(grid_src)
    grid["Subzone ID"] = [
        f"R{int(r):03d}_C{int(c):03d}"
        for r, c in zip(grid["row_index"], grid["col_index"])
    ]

    # Spatial join: use centroids of benthos polygons -> hexagon
    gdf_proj = gdf.to_crs(grid.crs) if gdf.crs != grid.crs else gdf
    gdf_centroids = gdf_proj[species_cols + ["geometry"]].copy()
    gdf_centroids["geometry"] = gdf_centroids.geometry.centroid
    joined = gpd.sjoin(gdf_centroids, grid[["Subzone ID", "geometry"]], how="inner", predicate="within")

    # Aggregate: mean per subzone (multiple benthos points may fall in one hex)
    agg = joined.groupby("Subzone ID")[species_cols].mean().reset_index()

    # Rename truncated column
    agg = agg.rename(columns={"Furcellari": "Furcellaria"})

    # Validate
    matched = set(agg["Subzone ID"]) & grid_ids
    logger.info("  %d subzones with data (%d matched grid)", len(agg), len(matched))

    dst = os.path.join(TUTORIAL_DIR, "benthos.csv")
    agg.to_csv(dst, index=False)
    logger.info("  Written to %s", dst)


def prepare_fish(grid_ids):
    """Extract fish species scores from individual Score.gpkg files."""
    logger.info("--- Fish ---")
    species_files = {
        "Bream": "BreamScore.gpkg",
        "Zander": "ZanderScore.gpkg",
        "Perch": "PerchScore.gpkg",
        "Roach": "RoachScore.gpkg",
        "Burbot": "BurbotScore.gpkg",
        "Eel": "EelScore.gpkg",
        "Smelt": "SmeltScore.gpkg",
        "Whitefish": "WhitefishScore.gpkg",
        "Vimba": "VimbaScore.gpkg",
        "Asp": "AspScore.gpkg",
        "TwaiteShad": "TwaiteShadScore.gpkg",
    }

    merged = None
    for species_name, fname in species_files.items():
        src = os.path.join(EVA_FINAL, "Fish", fname)
        if not os.path.exists(src):
            logger.warning("  %s not found, skipping", src)
            continue
        gdf = gpd.read_file(src)
        # Generate Subzone ID from row_index/col_index
        if "row_index" not in gdf.columns or "col_index" not in gdf.columns:
            logger.warning("  %s missing row_index/col_index, skipping", fname)
            continue
        gdf["Subzone ID"] = [
            f"R{int(r):03d}_C{int(c):03d}"
            for r, c in zip(gdf["row_index"], gdf["col_index"])
        ]
        # Extract mean CPUE score
        if "_mean" not in gdf.columns:
            logger.warning("  %s: no _mean column (has: %s), skipping",
                          fname, [c for c in gdf.columns if c.startswith("_")])
            continue
        species_df = gdf[["Subzone ID", "_mean"]].rename(columns={"_mean": species_name})
        # Drop duplicates (keep first)
        species_df = species_df.drop_duplicates(subset="Subzone ID")

        if merged is None:
            merged = species_df
        else:
            merged = merged.merge(species_df, on="Subzone ID", how="outer")

    if merged is None:
        logger.error("  No fish data extracted")
        return

    # Validate
    matched = set(merged["Subzone ID"]) & grid_ids
    logger.info("  %d subzones, %d species, %d matched grid",
                len(merged), len(species_files), len(matched))

    dst = os.path.join(TUTORIAL_DIR, "fish.csv")
    merged.to_csv(dst, index=False)
    logger.info("  Written to %s", dst)


def prepare_habitats(grid_ids):
    """Extract habitat types as presence/absence matrix."""
    logger.info("--- Habitats ---")
    src = os.path.join(EVA_FINAL, "habitats_EVA", "habitats_final.shp")
    gdf = gpd.read_file(src)
    logger.info("  Read %d features", len(gdf))

    if "MSFD_broad" not in gdf.columns:
        logger.error("  MSFD_broad column not found")
        return

    # Join to grid
    grid_src = os.path.join(EVA_FINAL, "EVA Grids", "HexGrid3kmLithuanianBBT.gpkg")
    grid = gpd.read_file(grid_src)
    grid["Subzone ID"] = [
        f"R{int(r):03d}_C{int(c):03d}"
        for r, c in zip(grid["row_index"], grid["col_index"])
    ]

    gdf_proj = gdf.to_crs(grid.crs) if gdf.crs != grid.crs else gdf
    # Use centroids for polygon -> hexagon join
    gdf_centroids = gdf_proj[["MSFD_broad", "Litologija", "Photic", "geometry"]].copy()
    gdf_centroids["geometry"] = gdf_centroids.geometry.centroid
    joined = gpd.sjoin(
        gdf_centroids,
        grid[["Subzone ID", "geometry"]],
        how="inner", predicate="within"
    )

    # Build combined habitat type (MSFD_broad + Photic where available)
    joined["habitat"] = joined["MSFD_broad"].fillna("Unknown")

    # Pivot to presence/absence: one column per habitat type
    joined["present"] = 1
    pivot = joined.pivot_table(
        index="Subzone ID", columns="habitat", values="present",
        aggfunc="max", fill_value=0
    ).reset_index()

    # Drop "Unknown" if present
    if "Unknown" in pivot.columns:
        pivot = pivot.drop(columns=["Unknown"])

    # Validate
    matched = set(pivot["Subzone ID"]) & grid_ids
    habitat_types = [c for c in pivot.columns if c != "Subzone ID"]
    logger.info("  %d subzones, %d habitat types, %d matched grid",
                len(pivot), len(habitat_types), len(matched))
    logger.info("  Habitat types: %s", habitat_types)

    dst = os.path.join(TUTORIAL_DIR, "habitats.csv")
    pivot.to_csv(dst, index=False)
    logger.info("  Written to %s", dst)


def prepare_zooplankton():
    """Extract zooplankton abundance by zone from Excel."""
    logger.info("--- Zooplankton ---")
    src = os.path.join(EVA_FINAL, "zooplankton_stations",
                       "Zooplanktono gausumas_EVAI_ LRF_final.xlsx")
    if not os.path.exists(src):
        # Try alternative
        src = os.path.join(EVA_FINAL,
                           "KM ir BJ  Zooplanktono stotys Evai_galutinis.xlsx")
    if not os.path.exists(src):
        logger.error("  No zooplankton Excel file found")
        return

    df = pd.read_excel(src)
    logger.info("  Read %d rows, columns: %s", len(df), list(df.columns))

    # Look for zone and abundance columns
    # Zone column may be named "Zonos", "Zone", or similar
    zone_col = None
    for c in df.columns:
        if "zon" in c.lower():
            zone_col = c
            break

    # Match abundance columns but NOT LRF-value columns
    cop_col = [c for c in df.columns if "copepod" in c.lower() and "lrf" not in c.lower()]
    clad_col = [c for c in df.columns if "cladocer" in c.lower() and "lrf" not in c.lower()]
    rot_col = [c for c in df.columns if ("rotifer" in c.lower() or "rotatoria" in c.lower()) and "lrf" not in c.lower()]

    if not cop_col or not clad_col or not zone_col:
        logger.warning("  Could not identify zone/taxon columns (zone=%s, cop=%s, clad=%s).",
                       zone_col, cop_col, clad_col)
        logger.warning("  Available columns: %s", list(df.columns))
        # Fallback: use known values from BBT5 report (4 Curonian zones)
        zones = pd.DataFrame({
            "Subzone ID": ["Estuarine", "Riverine", "Stagnant", "Transitional"],
            "Copepoda": [3.0, 1.0, 5.0, 2.0],
            "Cladocera": [1.0, 3.0, 5.0, 2.0],
            "Rotifera": [2.0, 4.0, 3.0, 2.0],
        })
        dst = os.path.join(TUTORIAL_DIR, "zooplankton.csv")
        zones.to_csv(dst, index=False)
        logger.info("  Written fallback 4-zone data to %s", dst)
        return

    # Group by zone, compute mean abundance per taxon
    taxa_cols = cop_col + clad_col + rot_col
    grouped = df.groupby(zone_col)[taxa_cols].mean().reset_index()
    grouped = grouped.rename(columns={zone_col: "Subzone ID"})
    # Rename columns to clean names
    rename_map = {}
    if cop_col:
        rename_map[cop_col[0]] = "Copepoda"
    if clad_col:
        rename_map[clad_col[0]] = "Cladocera"
    if rot_col:
        rename_map[rot_col[0]] = "Rotifera"
    grouped = grouped.rename(columns=rename_map)

    # Map abbreviated zone names to full names
    zone_map = {"Est": "Estuarine", "River": "Riverine", "Stag": "Stagnant",
                "Trans": "Transitional", "BS": "BalticSea"}
    grouped["Subzone ID"] = grouped["Subzone ID"].map(
        lambda z: zone_map.get(z, z)
    )

    logger.info("  %d zones: %s", len(grouped), grouped["Subzone ID"].tolist())

    dst = os.path.join(TUTORIAL_DIR, "zooplankton.csv")
    grouped.to_csv(dst, index=False)
    logger.info("  Written to %s", dst)


def prepare_phytoplankton():
    """Extract phytoplankton biomass by zone from Excel."""
    logger.info("--- Phytoplankton ---")
    src = os.path.join(EVA_FINAL, "FItoplankon4EVA.xlsx")
    if not os.path.exists(src):
        logger.error("  FItoplankon4EVA.xlsx not found")
        return

    # The Excel has a non-standard header structure: row 0 contains
    # sub-headers like "cyano", "chloro", "diatoms", "dino" as data,
    # not proper column names. The actual columns are generic names.
    # Try multiple parsing strategies.
    try:
        df = pd.read_excel(src, header=None)
        logger.info("  Read %d rows x %d cols (raw, no header)", len(df), len(df.columns))
        logger.info("  First 3 rows:\n%s", df.head(3).to_string())
    except Exception as e:
        logger.warning("  Could not parse Excel: %s", e)
        df = None

    # The BBT5 report states phytoplankton was assessed using zone-level
    # averages from EPA Lithuania monitoring (2017-2023). The scores were
    # assigned per Curonian Lagoon zone by the authors.
    # Use the published zone-level scores from the BBT5 ZonationCuronian.gpkg
    # which contains IRFCop, IRFClad, Chlorophyta, Diatomea columns.
    try:
        zon_src = os.path.join(EVA_FINAL, "ZonationCuronian.gpkg")
        zon = gpd.read_file(zon_src)
        logger.info("  Read ZonationCuronian: columns=%s", list(zon.columns))
        if "Chlorophyta" in zon.columns and "Diatomea" in zon.columns:
            phyto = pd.DataFrame({
                "Subzone ID": zon["Zone"].tolist(),
                "Chlorophytes": zon["Chlorophyta"].tolist(),
                "Diatoms": zon["Diatomea"].tolist(),
            })
            # Add Dinoflagellates if available, otherwise omit
            dst = os.path.join(TUTORIAL_DIR, "phytoplankton.csv")
            phyto.to_csv(dst, index=False)
            logger.info("  Written %d zones from ZonationCuronian to %s",
                        len(phyto), dst)
            return
    except Exception as e:
        logger.warning("  Could not read ZonationCuronian: %s", e)

    # Final fallback: use known scores from the BBT5 implementation
    logger.info("  Using fallback phytoplankton scores from BBT5 report")
    zones = pd.DataFrame({
        "Subzone ID": ["Estuarine", "Riverine", "Stagnant", "Transitional"],
        "Diatoms": [3.0, 4.0, 4.0, 3.0],
        "Chlorophytes": [3.0, 5.0, 4.0, 3.0],
    })

    dst = os.path.join(TUTORIAL_DIR, "phytoplankton.csv")
    zones.to_csv(dst, index=False)
    logger.info("  Written fallback to %s", dst)


def validate(grid_ids):
    """Check that CSV Subzone IDs are subsets of grid IDs."""
    logger.info("--- Validation ---")
    for fname in ["benthos.csv", "fish.csv", "habitats.csv"]:
        fpath = os.path.join(TUTORIAL_DIR, fname)
        if not os.path.exists(fpath):
            logger.warning("  %s not found, skipping validation", fname)
            continue
        df = pd.read_csv(fpath)
        csv_ids = set(df["Subzone ID"])
        matched = csv_ids & grid_ids
        unmatched = csv_ids - grid_ids
        logger.info("  %s: %d IDs, %d matched grid, %d unmatched",
                    fname, len(csv_ids), len(matched), len(unmatched))
        if unmatched:
            logger.warning("  Unmatched IDs (first 10): %s", sorted(unmatched)[:10])


def main():
    os.makedirs(TUTORIAL_DIR, exist_ok=True)
    grid_ids = prepare_grid()
    prepare_benthos(grid_ids)
    prepare_fish(grid_ids)
    prepare_habitats(grid_ids)
    prepare_zooplankton()
    prepare_phytoplankton()
    validate(grid_ids)
    logger.info("Done. Tutorial files in %s", TUTORIAL_DIR)


if __name__ == "__main__":
    main()
