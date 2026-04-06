"""Confirm correct layer variants for all regions and fix layer mapping."""
import io, ssl, numpy as np, urllib.request, urllib.parse, re, json
from PIL import Image
from collections import Counter

SSL = ssl.create_default_context()
SSL.check_hostname = False
SSL.verify_mode = ssl.CERT_NONE
WMS = "https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_view/wms"

CANDIDATE_LAYERS = [
    # (key, layer_name)
    ("eunis2007_400",  "eusm2025_eunis2007_400"),
    ("eunis2019_400",  "eusm2025_eunis2019_400"),
    ("subs_full",      "eusm2025_subs_full"),
    ("subs_400",       "eusm2025_subs_400"),
    ("bio_400",        "eusm2025_bio_400"),
    ("bio_800",        "eusm2025_bio_800"),
    ("ene_400",        "eusm2025_ene_400"),
    ("msfd_400",       "eusm2025_msfd_400"),
]

REGIONS = [
    ("NorthSea",  "2.0,51.0,4.0,53.0"),
    ("Baltic",    "20.0,54.0,22.0,56.0"),
    ("Med-Crete", "24.0,35.0,26.0,37.0"),
]

def tile_stats(layer, bbox):
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": layer, "STYLES": "", "FORMAT": "image/png", "TRANSPARENT": "true",
        "WIDTH": "512", "HEIGHT": "512", "CRS": "CRS:84", "BBOX": bbox,
    }
    url = WMS + "?" + urllib.parse.urlencode(params)
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "MARBEFES"}),
        context=SSL, timeout=30,
    ).read()
    arr = np.array(Image.open(io.BytesIO(raw)).convert("RGBA"))
    opaque = int((arr[:, :, 3] > 128).sum())
    unique = len(set(map(tuple, arr[arr[:,:,3]>128][:,:3].tolist()))) if opaque else 0
    return opaque, unique

print(f"{'Layer':25s} {'NorthSea':>20s} {'Baltic':>20s} {'Med-Crete':>20s}")
print("-" * 90)
for key, layer in CANDIDATE_LAYERS:
    row = f"{key:25s}"
    for region_name, bbox in REGIONS:
        try:
            opaque, unique = tile_stats(layer, bbox)
            row += f"  op={opaque:6d} u={unique:3d}"
        except Exception as exc:
            row += f"  ERROR:{str(exc)[:12]}"
    print(row)
