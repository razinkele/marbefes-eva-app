"""Test eusm2025_eunis2019_400 live: legend format, tile coverage, colour matching."""
import io, json, re, ssl, urllib.request, urllib.parse, numpy as np
from PIL import Image
from collections import Counter

SSL = ssl.create_default_context()
SSL.check_hostname = False
SSL.verify_mode = ssl.CERT_NONE
WMS = "https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_view/wms"
LAYER = "eusm2025_eunis2019_400"

# 1. Legend
print("=== Legend ===")
params = {"SERVICE":"WMS","VERSION":"1.3.0","REQUEST":"GetLegendGraphic","LAYER":LAYER,"FORMAT":"application/json"}
url = WMS + "?" + urllib.parse.urlencode(params)
raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"MARBEFES"}), context=SSL, timeout=20).read()
data = json.loads(raw)
rules = data.get("Legend",[{}])[0].get("rules",[])
legend = {}
for r in rules:
    m = re.search(r"= '([^']+)'", r.get("filter",""))
    if not m: continue
    code = m.group(1)
    title = r.get("title","")
    name = title.split(":",1)[1].strip() if ":" in title and not title.startswith("AA.") else title
    for sym in r.get("symbolizers",[]):
        fill = sym.get("Polygon",{}).get("fill","")
        if fill and len(fill)==7:
            rgb = (int(fill[1:3],16), int(fill[3:5],16), int(fill[5:7],16))
            legend[rgb] = (code, name)
print(f"  {len(rules)} rules, {len(legend)} colours")
print(f"  Filter sample: {[r.get('filter','') for r in rules[:3]]}")
print(f"  First 5 entries: {list(legend.items())[:5]}")

# 2. Tile coverage
print("\n=== Tile coverage ===")
REGIONS = [
    ("NorthSea",  "2.0,51.0,4.0,53.0"),
    ("Baltic",    "20.0,54.0,22.0,56.0"),
    ("Med-Crete", "24.0,35.0,26.0,37.0"),
]
for region, bbox in REGIONS:
    params2 = {"SERVICE":"WMS","VERSION":"1.3.0","REQUEST":"GetMap","LAYERS":LAYER,
               "STYLES":"","FORMAT":"image/png","TRANSPARENT":"true",
               "WIDTH":"512","HEIGHT":"512","CRS":"CRS:84","BBOX":bbox}
    url2 = WMS + "?" + urllib.parse.urlencode(params2)
    raw2 = urllib.request.urlopen(urllib.request.Request(url2, headers={"User-Agent":"MARBEFES"}), context=SSL, timeout=30).read()
    arr = np.array(Image.open(io.BytesIO(raw2)).convert("RGBA"))
    opaque = arr[arr[:,:,3]>128][:,:3]
    n_opaque = len(opaque)
    if n_opaque:
        counts = Counter(map(tuple, opaque.tolist()))
        exact_hits = sum(1 for px, cnt in counts.items() if px in legend for _ in range(cnt))
        # nearest-colour hits (max_dist=40)
        near_hits = 0
        for px, cnt in counts.items():
            if px in legend:
                near_hits += cnt
                continue
            r,g,b = px
            best = min(((r-lr)**2+(g-lg)**2+(b-lb)**2)**0.5 for lr,lg,lb in legend) if legend else 999
            if best <= 40:
                near_hits += cnt
        pct_exact = 100*exact_hits//n_opaque
        pct_near = 100*near_hits//n_opaque
        print(f"  {region:12s}: {n_opaque:6d} opaque px, exact={pct_exact}% near40={pct_near}%")
    else:
        print(f"  {region:12s}: 0 opaque — NO DATA")
