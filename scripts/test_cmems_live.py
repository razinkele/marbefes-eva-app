"""Test all 10 CMEMS layers live with credentials from .env"""
import os, logging

for line in open('.env'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ[k] = v

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

import geopandas as gpd
from shapely.geometry import Polygon
import eva_cmems

cells = []
for i in range(4):
    x, y = 19.0 + i * 0.2, 56.5
    cells.append(Polygon([(x, y), (x + 0.2, y), (x + 0.2, y + 0.2), (x, y + 0.2)]))
grid = gpd.GeoDataFrame(
    {'Subzone_ID': [f'SZ{i}' for i in range(4)]},
    geometry=cells, crs=4326
)

all_layers = list(eva_cmems.CMEMS_LAYERS.keys())
print(f'Testing {len(all_layers)} layers: {all_layers}')

result = eva_cmems.fetch_cmems_covariates(
    grid, all_layers, bgc_start_year=2018, bgc_end_year=2020
)

print()
print("Results:")
for lk, cfg in eva_cmems.CMEMS_LAYERS.items():
    col = cfg['col']
    vals = result[col].dropna()
    if len(vals):
        unit = cfg['unit']
        print(f"  {col:28s}  n={len(vals)}  mean={vals.mean():.4f} {unit}")
    else:
        print(f"  {col:28s}  NO DATA")

print()
print("ALL DONE")
