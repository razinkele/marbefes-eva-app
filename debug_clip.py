"""Debug script: investigate land clipping end-to-end."""
import geopandas as gpd
import json
import sys
import eva_hexgrid
from shapely.geometry import Polygon

# ------------------------------------------------------------------
# 1. Generate raw + clipped grid for a coastal area
# ------------------------------------------------------------------
area = Polygon([(20.8, 55.5), (21.5, 55.5), (21.5, 56.0), (20.8, 56.0), (20.8, 55.5)])
gdf = gpd.GeoDataFrame(geometry=[area], crs="EPSG:4326")

raw = eva_hexgrid.generate_h3_grid(gdf, resolution=7, clip_to_sea=False)
clipped = eva_hexgrid.generate_h3_grid(gdf, resolution=7, clip_to_sea=True)

print(f"Raw: {len(raw)} cells, geom types: {raw.geometry.geom_type.value_counts().to_dict()}")
print(f"Clipped: {len(clipped)} cells, geom types: {clipped.geometry.geom_type.value_counts().to_dict()}")

# Check total area difference
raw_area = raw.to_crs(3857).geometry.area.sum() / 1e6
clipped_area = clipped.to_crs(3857).geometry.area.sum() / 1e6
print(f"Raw total area: {raw_area:.1f} km²")
print(f"Clipped total area: {clipped_area:.1f} km²  (reduction: {100*(1-clipped_area/raw_area):.1f}%)")

# ------------------------------------------------------------------
# 2. Check what the map renderer sees
# ------------------------------------------------------------------
print("\n--- First 3 clipped geometries ---")
for i in range(min(3, len(clipped))):
    row = clipped.iloc[i]
    g = row.geometry
    print(f"  [{i}] {row['Subzone ID']}: type={g.geom_type}, valid={g.is_valid}, "
          f"bounds=({g.bounds[0]:.4f},{g.bounds[1]:.4f},{g.bounds[2]:.4f},{g.bounds[3]:.4f})")

# ------------------------------------------------------------------
# 3. Simulate what eva_map.py does — convert to GeoJSON
# ------------------------------------------------------------------
geojson_str = clipped.to_json()
data = json.loads(geojson_str)
print(f"\nGeoJSON features: {len(data['features'])}")
feat0 = data["features"][0]
print(f"First feature type: {feat0['geometry']['type']}")
print(f"First feature coords rings: {len(feat0['geometry']['coordinates'])}")
print(f"First ring length: {len(feat0['geometry']['coordinates'][0])}")

# ------------------------------------------------------------------
# 4. Check land mask coverage of Baltic/Klaipeda area
# ------------------------------------------------------------------
land = eva_hexgrid._load_land_mask()
from shapely.geometry import box
roi = box(20.8, 55.5, 21.5, 56.0)
local_land = land[land.geometry.intersects(roi)]
print(f"\nLand polygons intersecting ROI: {len(local_land)}")
land_union = local_land.geometry.union_all()
print(f"Land union area in ROI: {land_union.area:.6f} sq deg")

# Check if Klaipeda city is covered
from shapely.geometry import Point
klaipeda = Point(21.13, 55.72)
print(f"Klaipeda (21.13, 55.72) on land: {land_union.contains(klaipeda)}")

# Save outputs for visual inspection
raw.to_file("debug_raw_grid.geojson", driver="GeoJSON")
clipped.to_file("debug_clipped_grid.geojson", driver="GeoJSON")
print("\nSaved: debug_raw_grid.geojson, debug_clipped_grid.geojson")

# ------------------------------------------------------------------
# 5. Check eva_map.py to see how it renders the grid
# ------------------------------------------------------------------
import inspect, eva_map
src = inspect.getsource(eva_map.create_grid_only_map)
# Look for how GeoJSON is created from geo_data
geo_lines = [l for l in src.split('\n') if 'geo' in l.lower() or 'json' in l.lower() or 'h3' in l.lower()]
print("\n--- eva_map.create_grid_only_map relevant lines ---")
for l in geo_lines[:20]:
    print(" ", l)
