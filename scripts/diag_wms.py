"""Diagnostic script: probe EuSEAMAP WMS via GetFeatureInfo at multiple points."""
import ssl
import json
import urllib.request
import urllib.parse

SSL = ssl.create_default_context()
SSL.check_hostname = False
SSL.verify_mode = ssl.CERT_NONE
WMS = "https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_view/wms"

POINTS = [
    (25.1, 35.5, "Crete coast +0.2deg"),
    (25.1, 35.8, "Crete coast +0.5deg"),
    (25.1, 36.5, "Sea of Crete open"),
    (21.0, 55.7, "Baltic-Klaipeda (reference)"),
    (3.0,  51.5, "North Sea (reference)"),
]
LAYERS = ["eusm2025_eunis2007_full", "eusm2025_subs_full", "eusm2025_bio_full"]


def gfi(lon, lat, layer):
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetFeatureInfo",
        "LAYERS": layer, "QUERY_LAYERS": layer, "INFO_FORMAT": "application/json",
        "WIDTH": "101", "HEIGHT": "101", "CRS": "CRS:84",
        "BBOX": f"{lon-0.1},{lat-0.1},{lon+0.1},{lat+0.1}",
        "I": "50", "J": "50",
    }
    url = WMS + "?" + urllib.parse.urlencode(params)
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "MARBEFES-diag"}),
            context=SSL, timeout=15,
        ).read()
        data = json.loads(raw)
        feats = data.get("features", [])
        if feats:
            props = feats[0].get("properties", {})
            return f"HIT {props}"
        return "empty"
    except Exception as exc:
        return f"ERROR: {exc}"


for lon, lat, label in POINTS:
    print(f"\n=== {label} ({lon},{lat}) ===")
    for layer in LAYERS:
        short = layer.replace("eusm2025_", "").replace("_full", "")
        result = gfi(lon, lat, layer)
        print(f"  {short:15s}: {result[:120]}")
