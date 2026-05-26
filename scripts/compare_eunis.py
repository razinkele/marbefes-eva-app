"""Compare EUNIS 2007 vs 2019 habitat classifications for the DwC-A study area."""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import eva_eunis_wms
import eva_hexgrid
import geopandas as gpd
from shapely.geometry import box

# Build same grid as the SDM test (Crete, Greece — dwca-macrosoft-v2.1)
bbox = box(25.0583, 35.2888, 25.3536, 35.4682)
bbox_gdf = gpd.GeoDataFrame(geometry=[bbox], crs="EPSG:4326")
grid = eva_hexgrid.generate_h3_grid(bbox_gdf, resolution=7, clip_to_sea=True)

print(f"Grid: {len(grid)} sea hexagons\n")

# Fetch both classifications
cov07 = eva_eunis_wms.fetch_sdm_covariates(grid, layers=["eunis2007", "substrate", "depth"])
cov19 = eva_eunis_wms.fetch_sdm_covariates(grid, layers=["eunis2019", "substrate", "depth"])


def show_habitats(df, col, name_col, title):
    print("=" * 78)
    print(title)
    print("=" * 78)
    vc = df[col].value_counts()
    for code, n in vc.items():
        matches = df.loc[df[col] == code, name_col].dropna()
        name = matches.iloc[0] if len(matches) > 0 else "(no name in legend)"
        print(f"  {str(code):48s} n={n:3d}  {name}")
    total = df[col].notna().sum()
    print(f"  {'TOTAL':48s}     {total}/{len(df)} hexagons, {len(vc)} unique codes")
    print()


show_habitats(cov07, "dominant_EUNIS", "dominant_EUNIS_name",
              "EUNIS 2007 — Habitats (Crete study area)")

show_habitats(cov19, "dominant_EUNIS2019", "dominant_EUNIS2019_name",
              "EUNIS 2019 — Habitats (Crete study area)")

show_habitats(cov07, "substrate_type", "substrate_type_name",
              "Substrate types (shared)")

# Depth
d = cov07["depth_m"].dropna()
print(f"Depth: {d.min():.1f} – {d.max():.1f} m  (mean {d.mean():.1f} m)  "
      f"{len(d)}/{len(cov07)} hexagons\n")

# Legend size comparison
lc = eva_eunis_wms._legend_caches
n07 = len(lc.get("eusm2025_eunis2007_400", {}))
n19 = len(lc.get("eusm2025_eunis2019_400", {}))
print(f"Legend palette: EUNIS 2007 = {n07} colours, EUNIS 2019 = {n19} colours")
print()

# Summary comparison table
print("=" * 78)
print("COMPARISON SUMMARY")
print("=" * 78)
u07 = cov07["dominant_EUNIS"].nunique()
u19 = cov19["dominant_EUNIS2019"].nunique()
c07 = int(cov07["dominant_EUNIS"].notna().sum())
c19 = int(cov19["dominant_EUNIS2019"].notna().sum())
print(f"  {'Metric':<35s} {'EUNIS 2007':>15s} {'EUNIS 2019':>15s}")
print(f"  {'-'*35} {'-'*15} {'-'*15}")
print(f"  {'Legend colours (pan-European)':<35s} {n07:>15d} {n19:>15d}")
print(f"  {'Unique codes in study area':<35s} {u07:>15d} {u19:>15d}")
print(f"  {'Hexagons with data':<35s} {c07:>15d} {c19:>15d}")
print(f"  {'Coverage %':<35s} {100*c07/len(grid):>14.0f}% {100*c19/len(grid):>14.0f}%")
