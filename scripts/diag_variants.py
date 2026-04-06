"""Check eusm2025 layer resolution variants and available styles."""
import io, ssl, numpy as np, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from PIL import Image

SSL = ssl.create_default_context()
SSL.check_hostname = False
SSL.verify_mode = ssl.CERT_NONE
WMS = "https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_view/wms"

# 1. Check styles from GetCapabilities
raw = urllib.request.urlopen(
    urllib.request.Request(WMS + "?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities", headers={"User-Agent": "test"}),
    context=SSL, timeout=20,
).read()
tree = ET.fromstring(raw)
ns = {"wms": "http://www.opengis.net/wms"}
LAYERS_TO_CHECK = {
    "eusm2025_eunis2007_full", "eusm2025_eunis2007_200",
    "eusm2025_subs_full", "eusm2025_subs_200",
    "eusm2025_bio_full", "eusm2025_bio_200",
}
print("=== Styles per layer ===")
for layer in tree.findall(".//wms:Layer", ns):
    name_el = layer.find("wms:Name", ns)
    if name_el is None or name_el.text not in LAYERS_TO_CHECK:
        continue
    styles = [s.find("wms:Name", ns).text for s in layer.findall("wms:Style", ns) if s.find("wms:Name", ns) is not None]
    min_scale = layer.find("wms:MinScaleDenominator", ns)
    max_scale = layer.find("wms:MaxScaleDenominator", ns)
    print(f"  {name_el.text}: styles={styles} minScale={getattr(min_scale,'text','?')} maxScale={getattr(max_scale,'text','?')}")

# 2. Test resolution variants at North Sea bbox
print("\n=== Resolution variants — North Sea 2-4E 51-53N ===")
BBOX = "2.0,51.0,4.0,53.0"
VARIANTS = [
    "eusm2025_eunis2007_full", "eusm2025_eunis2007_800",
    "eusm2025_eunis2007_400", "eusm2025_eunis2007_200",
    "eusm2025_subs_full", "eusm2025_subs_200",
]
for layer in VARIANTS:
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": layer, "STYLES": "", "FORMAT": "image/png", "TRANSPARENT": "true",
        "WIDTH": "256", "HEIGHT": "256", "CRS": "CRS:84", "BBOX": BBOX,
    }
    url = WMS + "?" + urllib.parse.urlencode(params)
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "test"}), context=SSL, timeout=30).read()
        arr = np.array(Image.open(io.BytesIO(raw)).convert("RGBA"))
        opaque = int((arr[:, :, 3] > 128).sum())
        print(f"  {layer.replace('eusm2025_',''):25s} opaque={opaque:5d} bytes={len(raw)}")
    except Exception as exc:
        print(f"  {layer}: ERROR {exc}")

# 3. Try a larger bbox where eunis data should definitely be present
print("\n=== Larger bbox 0-10E 50-60N ===")
BBOX2 = "0.0,50.0,10.0,60.0"
for layer in ["eusm2025_eunis2007_full", "eusm2025_eunis2019_full", "eusm2025_subs_full"]:
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": layer, "STYLES": "", "FORMAT": "image/png", "TRANSPARENT": "true",
        "WIDTH": "512", "HEIGHT": "512", "CRS": "CRS:84", "BBOX": BBOX2,
    }
    url = WMS + "?" + urllib.parse.urlencode(params)
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "test"}), context=SSL, timeout=30).read()
        arr = np.array(Image.open(io.BytesIO(raw)).convert("RGBA"))
        opaque = int((arr[:, :, 3] > 128).sum())
        unique = len(set(map(tuple, arr[arr[:,:,3]>128][:,:3].tolist()))) if opaque else 0
        print(f"  {layer.replace('eusm2025_',''):25s} opaque={opaque:6d} unique={unique} bytes={len(raw)}")
    except Exception as exc:
        print(f"  {layer}: ERROR {exc}")
