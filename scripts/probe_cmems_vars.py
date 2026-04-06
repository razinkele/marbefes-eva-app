"""Probe CMEMS dataset variable names for PHY and BGC products."""
import copernicusmarine as cm
import json, re

for product_id, ds_filter in [
    ("GLOBAL_MULTIYEAR_PHY_001_030", "climatology"),
    ("GLOBAL_MULTIYEAR_BGC_001_029", "P1M-m"),
]:
    result = cm.describe(contains=[product_id])
    for p in result.products[:1]:
        for ds in p.datasets:
            if ds_filter in ds.dataset_id:
                d = ds.model_dump()
                txt = json.dumps(d, default=str)
                names = re.findall(r'"short_name": "([^"]+)"', txt)
                print(f"\n{product_id} / {ds.dataset_id}")
                print(f"  variables: {names}")
                break
