"""Compare WMS tile coverage: Baltic vs Mediterranean."""
import io, ssl, numpy as np, urllib.request, urllib.parse
from PIL import Image

SSL = ssl.create_default_context()
SSL.check_hostname = False
SSL.verify_mode = ssl.CERT_NONE
WMS = "https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_view/wms"


def check_tile(layer, lon0, lat0, lon1, lat1):
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": layer, "STYLES": "", "FORMAT": "image/png", "TRANSPARENT": "true",
        "WIDTH": "512", "HEIGHT": "512", "CRS": "CRS:84",
        "BBOX": f"{lon0},{lat0},{lon1},{lat1}",
    }
    url = WMS + "?" + urllib.parse.urlencode(params)
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "test"}),
        context=SSL, timeout=30,
    ).read()
    arr = np.array(Image.open(io.BytesIO(raw)).convert("RGBA"))
    opaque = int((arr[:, :, 3] > 128).sum())
    unique = len(set(map(tuple, arr[arr[:, :, 3] > 128][:, :3].tolist()))) if opaque else 0
    return opaque, unique


TESTS = [
    ("Baltic-Klaipeda",    "eusm2025_eunis2007_full", 20.0, 54.0, 22.0, 56.0),
    ("Baltic-Klaipeda",    "eusm2025_subs_full",      20.0, 54.0, 22.0, 56.0),
    ("Baltic-Klaipeda",    "eusm2025_bio_full",        20.0, 54.0, 22.0, 56.0),
    ("Crete-North",        "eusm2025_eunis2007_full", 24.0, 35.0, 26.0, 37.0),
    ("Crete-North",        "eusm2025_subs_full",      24.0, 35.0, 26.0, 37.0),
    ("Crete-North",        "eusm2025_bio_full",        24.0, 35.0, 26.0, 37.0),
    ("NorthSea-central",   "eusm2025_eunis2007_full",  2.0, 51.0,  4.0, 53.0),
    ("NorthSea-central",   "eusm2025_subs_full",       2.0, 51.0,  4.0, 53.0),
]

for region, layer, lon0, lat0, lon1, lat1 in TESTS:
    short_layer = layer.replace("eusm2025_", "").replace("_full", "")
    try:
        opaque, unique = check_tile(layer, lon0, lat0, lon1, lat1)
        print(f"{region:20s} {short_layer:12s}: opaque={opaque:6d}  unique_colors={unique}")
    except Exception as exc:
        print(f"{region:20s} {short_layer:12s}: ERROR {exc}")
