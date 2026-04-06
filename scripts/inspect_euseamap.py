"""Inspect EUSeaMap 2023 GDB for Lithuanian BBT5 area."""
import geopandas as gpd
import fiona
import zipfile
import tempfile
import os

src_zip = r"C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\BBTs\EMODNET\EUSeaMap_2023.zip"

# Extract GDB to temp dir
print("Extracting GDB from zip...")
tmpdir = tempfile.mkdtemp()
with zipfile.ZipFile(src_zip) as z:
    z.extractall(tmpdir)

gdb_path = os.path.join(tmpdir, "EUSeaMap_2023.gdb")
print(f"GDB path: {gdb_path}")

# List layers
layers = fiona.listlayers(gdb_path)
print(f"Layers: {layers}")

# Read with bbox filter
bbox = (20.0, 54.5, 22.5, 56.5)
for layer in layers[:3]:
    print(f"\nReading layer '{layer}' with Lithuanian bbox...")
    gdf = gpd.read_file(gdb_path, layer=layer, bbox=bbox)
    print(f"  Features: {len(gdf)}")
    print(f"  CRS: {gdf.crs}")
    cols = [c for c in gdf.columns if c != "geometry" and c != "Shape"]
    print(f"  Columns ({len(cols)}):")
    for c in cols[:25]:
        sample = gdf[c].iloc[0] if len(gdf) > 0 else "N/A"
        print(f"    {c}: {gdf[c].dtype} — e.g. {sample}")

    eunis_cols = [c for c in cols if "eunis" in c.lower() or "EUNIS" in c
                  or "Allcomb" in c or "All2019" in c]
    print(f"  EUNIS columns: {eunis_cols}")

    for col in eunis_cols[:3]:
        vals = gdf[col].dropna().unique()
        print(f"\n  {col}: {len(vals)} unique values")
        for v in sorted(vals)[:20]:
            count = (gdf[col] == v).sum()
            print(f"    {v}: {count} polygons")

# Cleanup
import shutil
shutil.rmtree(tmpdir, ignore_errors=True)
