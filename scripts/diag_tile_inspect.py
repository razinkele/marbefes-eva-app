"""Deep inspection of WMS tile content for EUNIS vs substrate."""
import io, ssl, numpy as np, urllib.request, urllib.parse
from PIL import Image

SSL = ssl.create_default_context()
SSL.check_hostname = False
SSL.verify_mode = ssl.CERT_NONE
WMS = "https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_view/wms"

# North Sea — known EuSEAMAP coverage area
BBOX = "2.0,51.0,4.0,53.0"
LAYERS = [
    "eusm2025_eunis2007_full",
    "eusm2025_eunis2019_full",
    "eusm2025_subs_full",
    "eusm2025_msfd_full",
    "eusm2025_bio_full",
]

for layer in LAYERS:
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": layer, "STYLES": "", "FORMAT": "image/png", "TRANSPARENT": "true",
        "WIDTH": "256", "HEIGHT": "256", "CRS": "CRS:84", "BBOX": BBOX,
    }
    url = WMS + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "test"})
        resp = urllib.request.urlopen(req, context=SSL, timeout=30)
        content_type = resp.getheader("Content-Type", "?")
        raw = resp.read()
        arr = np.array(Image.open(io.BytesIO(raw)).convert("RGBA"))
        alpha = arr[:, :, 3]
        print(f"{layer.replace('eusm2025_',''):20s} ct={content_type:20s} "
              f"opaque={int((alpha>128).sum()):5d} "
              f"semi={int(((alpha>0)&(alpha<=128)).sum()):5d} "
              f"bytes={len(raw)}")
    except Exception as exc:
        print(f"{layer}: ERROR {exc}")

# Also try with explicit EPSG:4326 CRS
print("\n--- Try with EPSG:4326 (axis-swapped BBOX) ---")
BBOX_SWAPPED = "51.0,2.0,53.0,4.0"  # lat,lon order for EPSG:4326
for layer in ["eusm2025_eunis2007_full", "eusm2025_subs_full"]:
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": layer, "STYLES": "", "FORMAT": "image/png", "TRANSPARENT": "true",
        "WIDTH": "256", "HEIGHT": "256", "CRS": "EPSG:4326", "BBOX": BBOX_SWAPPED,
    }
    url = WMS + "?" + urllib.parse.urlencode(params)
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "test"}),
            context=SSL, timeout=30,
        ).read()
        arr = np.array(Image.open(io.BytesIO(raw)).convert("RGBA"))
        opaque = int((arr[:, :, 3] > 128).sum())
        print(f"{layer.replace('eusm2025_',''):20s} EPSG:4326 opaque={opaque}")
    except Exception as exc:
        print(f"{layer}: ERROR {exc}")
