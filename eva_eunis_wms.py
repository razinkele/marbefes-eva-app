"""Extract SDM covariate layers from EMODnet services for hexagonal grids.

Layers supported:
  - EuSEAMAP 2025 (WMS PNG sampling): EUNIS L3, substrate type, energy class,
    biological zone, HELCOM HUB classification
  - EMODnet Bathymetry (WCS float32 GeoTIFF + rasterio): water depth
  - Custom habitat maps (polygon intersection)

All EuSEAMAP layers share the same GeoServer WMS, so tiles are cached across
layers within a single fetch_sdm_covariates() call.
"""
import io
import json
import logging
import math
import re
import ssl
import urllib.parse
import urllib.request
from typing import Callable, Optional

import geopandas as gpd
import numpy as np
import pandas as pd
from PIL import Image

logger = logging.getLogger(__name__)

# ── EMODnet Seabed Habitats WMS ───────────────────────────────────────────────
EUSM_WMS_URL = "https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_view/wms"

# Available EuSEAMAP 2025 layers with column naming and labels.
#
# Layer naming convention: _full = full detail (renders only at high zoom ~1:500k).
# _400 = 400m simplified (renders down to ~1:3M). Our 2°×2° tiles at 1024px are
# ~1:440k–1:3M depending on latitude, so _400 variants are required.
# Exception: eusm2025_subs_full uses simple polygon fill (few colours, no AA issue).
#
# Coverage notes (verified via WMS tile inspection):
#   eunis2007, substrate, biozone, msfd: pan-European incl. Mediterranean
#   energy (ene): Atlantic/North Sea/Baltic only — no Mediterranean data
#   helcom: Baltic Sea only
EUSM_LAYERS: dict = {
    "eunis2007": {
        "wms_layer": "eusm2025_eunis2007_400",
        "col": "dominant_EUNIS",
        "name_col": "dominant_EUNIS_name",
        "label": "EUNIS 2007 L3 Habitat",
        "coverage": "pan-European",
    },
    "substrate": {
        "wms_layer": "eusm2025_subs_full",
        "col": "substrate_type",
        "name_col": "substrate_type_name",
        "label": "Seabed Substrate Type",
        "coverage": "pan-European",
    },
    "energy": {
        "wms_layer": "eusm2025_ene_400",
        "col": "energy_class",
        "name_col": "energy_class_name",
        "label": "Energy Class (wave/current exposure)",
        "coverage": "Atlantic/North Sea/Baltic — no Mediterranean data",
    },
    "biozone": {
        "wms_layer": "eusm2025_bio_400",
        "col": "bio_zone",
        "name_col": "bio_zone_name",
        "label": "Biological Zone",
        "coverage": "pan-European (partial Mediterranean)",
    },
    "helcom": {
        "wms_layer": "eusm2025_helcom_full",
        "col": "helcom_class",
        "name_col": "helcom_class_name",
        "label": "HELCOM HUB Class (Baltic)",
        "coverage": "Baltic Sea only",
    },
}

# Backward-compat alias used by existing code
EUSM_LAYER = EUSM_LAYERS["eunis2007"]["wms_layer"]

# ── EMODnet Bathymetry ────────────────────────────────────────────────────────
EMODNET_BATHY_WCS = "https://ows.emodnet-bathymetry.eu/wcs"
BATHY_COVERAGE = "emodnet:mean"

# ── Shared HTTP / tile settings ───────────────────────────────────────────────
_MAX_TILE_DEG = 2.0
_TILE_PX = 1024

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Per-layer legend caches: {wms_layer_name: {(R,G,B): (code, name)}}
_legend_caches: dict = {}

# Backward-compat single-legend alias (eunis2007 layer)
_legend_cache: Optional[dict] = None


# ── Legend building ───────────────────────────────────────────────────────────

def _build_layer_legend(wms_layer: str) -> dict:
    """Download GetLegendGraphic JSON for *wms_layer* and build {(R,G,B):(code,name)}.

    Supports all EuSEAMAP filter attribute names (euniscomb, substrate, energy,
    biozone, regionald) via a generic `= '...'` pattern.
    """
    if wms_layer in _legend_caches:
        return _legend_caches[wms_layer]

    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetLegendGraphic",
        "LAYER": wms_layer, "FORMAT": "application/json",
    }
    url = EUSM_WMS_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "MARBEFES-EVA/1.0"})
    try:
        raw = urllib.request.urlopen(req, context=_SSL_CTX, timeout=20).read()
        legend_data = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"Cannot fetch WMS legend for {wms_layer}: {exc}") from exc

    rules = legend_data.get("Legend", [{}])[0].get("rules", [])
    color_map: dict = {}
    for rule in rules:
        # Generic: extract value after any `attr = 'value'` pattern
        m = re.search(r"= '([^']+)'", rule.get("filter", ""))
        if not m:
            continue
        code = m.group(1)
        title = rule.get("title", "")
        # For EUNIS codes like "A5.27: Deep circalittoral sand" split to get name
        name = title.split(":", 1)[1].strip() if ":" in title and not title.startswith("AA.") else title
        for sym in rule.get("symbolizers", []):
            fill = sym.get("Polygon", {}).get("fill", "")
            if fill and len(fill) == 7 and fill.startswith("#"):
                rgb = (int(fill[1:3], 16), int(fill[3:5], 16), int(fill[5:7], 16))
                color_map[rgb] = (code, name)

    _legend_caches[wms_layer] = color_map
    logger.info("Legend loaded for %s: %d colour entries", wms_layer, len(color_map))
    return color_map


def _build_legend() -> dict:
    """Backward-compatible legend builder for EUNIS 2007 layer."""
    global _legend_cache
    if _legend_cache is None:
        _legend_cache = _build_layer_legend(EUSM_LAYERS["eunis2007"]["wms_layer"])
    return _legend_cache


# ── WMS tile fetching / sampling ──────────────────────────────────────────────

def _fetch_wms_tile(
    lon0: float, lat0: float, lon1: float, lat1: float,
    wms_layer: str = EUSM_LAYER,
) -> np.ndarray:
    """Fetch one WMS GetMap PNG tile; return RGBA numpy array (H × W × 4, uint8)."""
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": wms_layer, "STYLES": "",
        "FORMAT": "image/png", "TRANSPARENT": "true",
        "WIDTH": str(_TILE_PX), "HEIGHT": str(_TILE_PX),
        "CRS": "CRS:84",
        "BBOX": f"{lon0},{lat0},{lon1},{lat1}",
    }
    url = EUSM_WMS_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "MARBEFES-EVA/1.0"})
    try:
        raw = urllib.request.urlopen(req, context=_SSL_CTX, timeout=30).read()
    except Exception as exc:
        raise RuntimeError(
            f"WMS tile failed for {wms_layer} ({lon0},{lat0},{lon1},{lat1}): {exc}"
        ) from exc
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    return np.array(img)


def _sample_tile(
    arr: np.ndarray,
    lon: float, lat: float,
    tile_lon0: float, tile_lat0: float,
    tile_lon1: float, tile_lat1: float,
) -> tuple:
    """Return (r, g, b, alpha) for a geographic point within a loaded tile array.

    Samples a 5×5 pixel neighbourhood and returns the most frequent opaque colour
    to handle WMS PNG anti-aliasing artefacts at polygon edges.
    """
    H, W = arr.shape[:2]
    col_px = int((lon - tile_lon0) / (tile_lon1 - tile_lon0) * W)
    row_px = int((tile_lat1 - lat) / (tile_lat1 - tile_lat0) * H)
    # Clamp to valid range (handles centroids exactly on tile boundary)
    col_px = min(col_px, W - 1)
    row_px = min(row_px, H - 1)
    if not (0 <= row_px < H and 0 <= col_px < W):
        return (0, 0, 0, 0)
    # Sample 5×5 neighbourhood
    r0, r1 = max(0, row_px - 2), min(H, row_px + 3)
    c0, c1 = max(0, col_px - 2), min(W, col_px + 3)
    patch = arr[r0:r1, c0:c1]
    opaque = patch[patch[:, :, 3] > 128]
    if len(opaque) == 0:
        return (0, 0, 0, 0)
    # Return the most common opaque colour
    pixels = [tuple(int(v) for v in px) for px in opaque]
    from collections import Counter
    most_common = Counter(pixels).most_common(1)[0][0]
    return most_common


def _nearest_legend_color(rgb: tuple, legend: dict, max_dist: int = 40) -> tuple:
    """Return (code, name) for the legend entry closest to *rgb* in Euclidean RGB space.

    Returns (None, None) if the closest match exceeds *max_dist*.
    Anti-aliasing near polygon edges produces blended colours; this allows
    a tolerance match to the nearest legend entry.
    """
    if not legend:
        return (None, None)
    r, g, b = rgb[:3]
    best_dist, best_val = float("inf"), (None, None)
    for (lr, lg, lb), val in legend.items():
        dist = ((r - lr) ** 2 + (g - lg) ** 2 + (b - lb) ** 2) ** 0.5
        if dist < best_dist:
            best_dist, best_val = dist, val
    return best_val if best_dist <= max_dist else (None, None)


def _tile_key(lon: float, lat: float) -> tuple:
    """Return the aligned 2°×2° tile origin for a point."""
    tlon0 = math.floor(lon / _MAX_TILE_DEG) * _MAX_TILE_DEG
    tlat0 = math.floor(lat / _MAX_TILE_DEG) * _MAX_TILE_DEG
    return tlon0, tlat0, tlon0 + _MAX_TILE_DEG, tlat0 + _MAX_TILE_DEG


def _sample_eusm_layer(
    gdf: gpd.GeoDataFrame,
    layer_key: str,
    shared_tile_cache: Optional[dict] = None,
) -> dict:
    """Sample one EuSEAMAP layer at hex centroids.

    Args:
        gdf: grid GDF in EPSG:4326 with id column.
        layer_key: key in EUSM_LAYERS ('eunis2007', 'substrate', …).
        shared_tile_cache: optional dict keyed by (wms_layer, tile_tuple) to
            share tiles across multiple layer calls.

    Returns:
        dict {subzone_id: {'code': str, 'name': str}} for hexagons with data.
    """
    config = EUSM_LAYERS[layer_key]
    wms_layer = config["wms_layer"]
    legend = _build_layer_legend(wms_layer)

    if shared_tile_cache is None:
        shared_tile_cache = {}

    id_col = "Subzone ID" if "Subzone ID" in gdf.columns else "Subzone_ID"
    centroids = gdf.geometry.centroid
    result: dict = {}

    for i, (_, row) in enumerate(gdf.iterrows()):
        sid = row[id_col]
        clon, clat = centroids.iloc[i].x, centroids.iloc[i].y
        tile_bounds = _tile_key(clon, clat)
        cache_key = (wms_layer,) + tile_bounds

        if cache_key not in shared_tile_cache:
            try:
                shared_tile_cache[cache_key] = _fetch_wms_tile(*tile_bounds, wms_layer=wms_layer)
            except Exception as exc:
                logger.warning("WMS tile unavailable (%s, %s): %s", wms_layer, tile_bounds, exc)
                shared_tile_cache[cache_key] = None

        arr = shared_tile_cache[cache_key]
        if arr is None:
            continue

        r, g, b, a = _sample_tile(arr, clon, clat, *tile_bounds)
        if a < 128:
            continue

        # Exact match first; fall back to nearest-colour to handle AA artefacts
        code, name = legend.get((r, g, b), (None, None))
        if code is None:
            code, name = _nearest_legend_color((r, g, b), legend, max_dist=40)
        if code is not None:
            result[sid] = {"code": code, "name": name}

    n_with = len(result)
    coverage_note = config.get("coverage", "")
    logger.info(
        "%s (%s): %d/%d hexagons annotated%s",
        layer_key, config["wms_layer"], n_with, len(gdf),
        f" [coverage: {coverage_note}]" if coverage_note else "",
    )
    if n_with == 0 and len(gdf) > 0:
        logger.warning(
            "%s returned no data. Coverage note: %s. "
            "The WMS layer may not cover this geographic region.",
            layer_key, coverage_note or "unknown",
        )
    return result


# ── Depth via WCS ─────────────────────────────────────────────────────────────

def fetch_depth_for_grid(grid_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Sample EMODnet Bathymetry WCS at each hexagon centroid for water depth.

    Returns a GeoDataFrame with columns:
        Subzone_ID, depth_m (positive = depth below sea surface; None = land), geometry.
    Depth values > 0 from the WCS (i.e. elevation above sea level) are set to None.
    """
    import rasterio
    from rasterio.io import MemoryFile

    gdf = grid_gdf
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    lon0, lat0, lon1, lat1 = gdf.total_bounds
    buf = max(0.05, (lon1 - lon0) * 0.02)
    bbox = (lon0 - buf, lat0 - buf, lon1 + buf, lat1 + buf)

    params = {
        "SERVICE": "WCS", "VERSION": "1.0.0", "REQUEST": "GetCoverage",
        "COVERAGE": BATHY_COVERAGE,
        "BBOX": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "CRS": "EPSG:4326", "RESPONSE_CRS": "EPSG:4326",
        "WIDTH": "1024", "HEIGHT": "1024",
        "FORMAT": "GeoTIFF",
    }
    url = EMODNET_BATHY_WCS + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "MARBEFES-EVA/1.0"})
    try:
        raw = urllib.request.urlopen(req, context=_SSL_CTX, timeout=45).read()
    except Exception as exc:
        raise RuntimeError(f"Bathymetry WCS request failed: {exc}") from exc

    id_col = "Subzone ID" if "Subzone ID" in gdf.columns else "Subzone_ID"
    centroids = gdf.geometry.centroid
    coords = [(c.x, c.y) for c in centroids]

    results = []
    with MemoryFile(raw) as memfile:
        with memfile.open() as dataset:
            nodata = dataset.nodata
            samples = list(dataset.sample(coords))

    for i, (_, row) in enumerate(gdf.iterrows()):
        sid = row[id_col]
        val = float(samples[i][0])
        # WCS returns negative values for below-sea-level; NaN/nodata → None
        if nodata is not None and abs(val - nodata) < 1.0:
            depth_m = None
        elif val >= 0:
            depth_m = None   # above sea level (land)
        else:
            depth_m = round(-val, 1)  # convert to positive depth
        results.append({"Subzone_ID": sid, "depth_m": depth_m, "geometry": row.geometry})

    logger.info(
        "Bathymetry: %d/%d hexagons with depth data",
        sum(1 for r in results if r["depth_m"] is not None), len(results),
    )
    return gpd.GeoDataFrame(results, crs=grid_gdf.crs)


# ── Combined SDM covariates ───────────────────────────────────────────────────

def fetch_sdm_covariates(
    grid_gdf: gpd.GeoDataFrame,
    layers: Optional[list] = None,
    progress_cb: Optional[Callable[[str, int, int], None]] = None,
) -> gpd.GeoDataFrame:
    """Fetch multiple SDM predictor layers and return a combined GeoDataFrame.

    Tiles are shared across EuSEAMAP layers to minimise HTTP requests.

    Args:
        grid_gdf: hex grid with 'Subzone ID' or 'Subzone_ID' column, EPSG:4326.
        layers: list of layer keys to fetch. Valid keys:
            'eunis2007', 'substrate', 'energy', 'biozone', 'helcom', 'depth'.
            Default: all layers.
        progress_cb: optional callback(layer_label, layer_index, total_layers).

    Returns:
        GeoDataFrame with Subzone_ID, geometry, and one or two columns per layer
        (code + name for EuSEAMAP layers; depth_m for bathymetry).
    """
    if layers is None:
        layers = list(EUSM_LAYERS.keys()) + ["depth"]
    if not layers:
        raise ValueError("layers must be a non-empty list. Provide at least one layer key.")

    gdf = grid_gdf
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    id_col = "Subzone ID" if "Subzone ID" in gdf.columns else "Subzone_ID"

    result = gpd.GeoDataFrame(
        {"Subzone_ID": gdf[id_col].values, "geometry": gdf.geometry.values},
        crs=gdf.crs,
    )

    shared_tile_cache: dict = {}
    total = len(layers)

    for i, layer_key in enumerate(layers):
        if layer_key == "depth":
            label = "Water depth (EMODnet Bathymetry)"
        elif layer_key in EUSM_LAYERS:
            label = EUSM_LAYERS[layer_key]["label"]
        else:
            logger.warning("Unknown layer key '%s', skipping.", layer_key)
            continue

        if progress_cb:
            progress_cb(label, i, total)

        if layer_key == "depth":
            try:
                depth_gdf = fetch_depth_for_grid(gdf)
                depth_map = depth_gdf.set_index("Subzone_ID")["depth_m"]
                result["depth_m"] = result["Subzone_ID"].map(depth_map)
            except Exception as exc:
                logger.warning("Depth fetch failed: %s", exc)
                result["depth_m"] = None

        elif layer_key in EUSM_LAYERS:
            config = EUSM_LAYERS[layer_key]
            try:
                sampled = _sample_eusm_layer(gdf, layer_key, shared_tile_cache)
                result[config["col"]] = result["Subzone_ID"].map(
                    {sid: v["code"] for sid, v in sampled.items()}
                )
                result[config["name_col"]] = result["Subzone_ID"].map(
                    {sid: v["name"] for sid, v in sampled.items()}
                )
            except Exception as exc:
                logger.warning("Layer '%s' fetch failed: %s", layer_key, exc)
                result[config["col"]] = None
                result[config["name_col"]] = None

    if progress_cb:
        progress_cb("Done", total, total)

    logger.info("SDM covariates done: %d hexagons, layers: %s", len(result), layers)
    return result


# ── Backward-compatible public API ───────────────────────────────────────────

def fetch_eunis_for_grid(
    grid_gdf: gpd.GeoDataFrame,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> gpd.GeoDataFrame:
    """Sample EuSEAMAP 2025 WMS at each hexagon centroid for EUNIS L3 codes.

    Backward-compatible wrapper around fetch_sdm_covariates(['eunis2007']).

    Returns:
        GeoDataFrame with Subzone_ID, dominant_EUNIS, dominant_EUNIS_name,
        habitat_count, dominant_pct, coverage_pct, geometry.
    """
    gdf = grid_gdf
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    id_col = "Subzone ID" if "Subzone ID" in gdf.columns else "Subzone_ID"
    shared: dict = {}

    def _prog(label, idx, total):
        if progress_cb:
            progress_cb(idx, total)

    sampled = _sample_eusm_layer(gdf, "eunis2007", shared)
    results = []
    for _, row in gdf.iterrows():
        sid = row[id_col]
        v = sampled.get(sid)
        if v:
            results.append({
                "Subzone_ID": sid,
                "dominant_EUNIS": v["code"],
                "dominant_EUNIS_name": v["name"],
                "habitat_count": 1,
                "dominant_pct": 100.0,
                "coverage_pct": 100.0,
                "geometry": row.geometry,
            })
        else:
            results.append(_no_data_row(sid, row.geometry))

    result_gdf = gpd.GeoDataFrame(results, crs=grid_gdf.crs)
    n_with = result_gdf["dominant_EUNIS"].notna().sum()
    logger.info("EUNIS annotation: %d/%d hexagons assigned", n_with, len(result_gdf))
    return result_gdf


def _no_data_row(sid, geom):
    return {
        "Subzone_ID": sid,
        "dominant_EUNIS": None,
        "dominant_EUNIS_name": None,
        "habitat_count": 0,
        "dominant_pct": 0.0,
        "coverage_pct": 0.0,
        "geometry": geom,
    }


def compute_overlay_from_file(
    grid_gdf: gpd.GeoDataFrame,
    habitat_gdf: gpd.GeoDataFrame,
    eunis_col: str = "EUNIScomb",
    name_col: Optional[str] = "EUNIScombD",
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> gpd.GeoDataFrame:
    """Compute dominant EUNIS from a user-supplied habitat polygon layer.

    Performs polygon intersection to determine the dominant EUNIS type within
    each hexagon by area (same algorithm as scripts/extract_eunis_for_bbt.py).

    Args:
        grid_gdf: hex grid GeoDataFrame with 'Subzone ID' or 'Subzone_ID' column.
        habitat_gdf: polygon layer with EUNIS code column (eunis_col).
        eunis_col: column name in habitat_gdf containing EUNIS codes.
        name_col: column name with EUNIS descriptions (optional).
        progress_cb: Optional callback(n_done, total).

    Returns:
        GeoDataFrame with Subzone_ID, dominant_EUNIS, dominant_EUNIS_name,
        habitat_count, dominant_pct, coverage_pct, geometry columns.
    """
    id_col = "Subzone ID" if "Subzone ID" in grid_gdf.columns else "Subzone_ID"

    if habitat_gdf.crs != grid_gdf.crs:
        habitat_gdf = habitat_gdf.to_crs(grid_gdf.crs)

    valid_hab = habitat_gdf[
        habitat_gdf[eunis_col].notna() & (habitat_gdf[eunis_col].astype(str) != "Na")
    ].copy()

    has_name_col = name_col and name_col in valid_hab.columns

    results = []
    total = len(grid_gdf)

    for i, (_, hex_row) in enumerate(grid_gdf.iterrows()):
        if progress_cb and (i % 50 == 0 or i == total - 1):
            progress_cb(i + 1, total)

        hex_geom = hex_row.geometry
        hex_area = hex_geom.area
        sid = hex_row[id_col]

        candidates = valid_hab[valid_hab.intersects(hex_geom)]
        if candidates.empty:
            results.append(_no_data_row(sid, hex_geom))
            continue

        intersections = []
        for _, hab_row in candidates.iterrows():
            try:
                inter = hex_geom.intersection(hab_row.geometry)
                if not inter.is_empty:
                    intersections.append({
                        "code": str(hab_row[eunis_col]),
                        "name": str(hab_row[name_col]) if has_name_col else "",
                        "area": inter.area,
                    })
            except Exception:
                continue

        if not intersections:
            results.append(_no_data_row(sid, hex_geom))
            continue

        df = pd.DataFrame(intersections)
        by_code = (
            df.groupby("code")
            .agg(name=("name", "first"), total_area=("area", "sum"))
            .sort_values("total_area", ascending=False)
        )
        dom_code = by_code.index[0]
        dom_name = by_code.iloc[0]["name"]
        dom_area = by_code.iloc[0]["total_area"]
        total_eunis_area = by_code["total_area"].sum()

        results.append({
            "Subzone_ID": sid,
            "dominant_EUNIS": dom_code,
            "dominant_EUNIS_name": dom_name,
            "habitat_count": len(by_code),
            "dominant_pct": round(dom_area / hex_area * 100, 1) if hex_area > 0 else 0.0,
            "coverage_pct": round(total_eunis_area / hex_area * 100, 1) if hex_area > 0 else 0.0,
            "geometry": hex_geom,
        })

    return gpd.GeoDataFrame(results, crs=grid_gdf.crs)
