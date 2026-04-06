"""Extract EUNIS Level 3 habitat codes from EMODnet EuSEAMAP 2025 WMS.

Uses WMS GetMap PNG centroid-sampling for rapid hex grid annotation.
Also supports custom habitat polygon layers via spatial intersection.
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

EUSM_WMS_URL = "https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_view/wms"
EUSM_LAYER = "eusm2025_eunis2007_full"

# Max tile side (degrees) — keeps WMS scale denominator in acceptable range
_MAX_TILE_DEG = 2.0
# WMS tile pixel size
_TILE_PX = 1024

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Module-level legend cache: {(R, G, B): (eunis_code, eunis_name)}
_legend_cache: Optional[dict] = None


def _build_legend() -> dict:
    """Download EuSEAMAP WMS legend and build colour → EUNIS code/name lookup."""
    global _legend_cache
    if _legend_cache is not None:
        return _legend_cache

    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetLegendGraphic",
        "LAYER": EUSM_LAYER, "FORMAT": "application/json",
    }
    url = EUSM_WMS_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "MARBEFES-EVA/1.0"})
    try:
        raw = urllib.request.urlopen(req, context=_SSL_CTX, timeout=20).read()
        legend_data = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"Cannot fetch EuSEAMAP WMS legend: {exc}") from exc

    rules = legend_data.get("Legend", [{}])[0].get("rules", [])
    color_map: dict = {}
    for rule in rules:
        m = re.search(r"euniscomb = '([^']+)'", rule.get("filter", ""))
        if not m:
            continue
        code = m.group(1)
        title = rule.get("title", "")
        name = title.split(":", 1)[1].strip() if ":" in title else title
        for sym in rule.get("symbolizers", []):
            poly = sym.get("Polygon", {})
            fill = poly.get("fill", "")
            if fill and len(fill) == 7 and fill.startswith("#"):
                rgb = (int(fill[1:3], 16), int(fill[3:5], 16), int(fill[5:7], 16))
                color_map[rgb] = (code, name)

    _legend_cache = color_map
    logger.info("EuSEAMAP legend loaded: %d EUNIS colour entries", len(color_map))
    return color_map


def _fetch_wms_tile(lon0: float, lat0: float, lon1: float, lat1: float) -> np.ndarray:
    """Fetch one WMS GetMap PNG tile; return RGBA numpy array (H × W × 4, uint8)."""
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": EUSM_LAYER, "STYLES": "",
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
        raise RuntimeError(f"WMS tile request failed ({lon0},{lat0},{lon1},{lat1}): {exc}") from exc
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    return np.array(img)


def _sample_tile(arr: np.ndarray, lon: float, lat: float,
                 tile_lon0: float, tile_lat0: float,
                 tile_lon1: float, tile_lat1: float) -> tuple:
    """Return (r, g, b, alpha) for a geographic point within a loaded tile."""
    H, W = arr.shape[:2]
    col_px = int((lon - tile_lon0) / (tile_lon1 - tile_lon0) * W)
    row_px = int((tile_lat1 - lat) / (tile_lat1 - tile_lat0) * H)
    if not (0 <= row_px < H and 0 <= col_px < W):
        return (0, 0, 0, 0)
    return tuple(int(v) for v in arr[row_px, col_px])


def fetch_eunis_for_grid(
    grid_gdf: gpd.GeoDataFrame,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> gpd.GeoDataFrame:
    """Sample EuSEAMAP 2025 WMS at each hexagon centroid to assign EUNIS L3 codes.

    Tiles the study area into ≤ 2° × 2° WMS requests to avoid scale-denominator
    transparency. Results are cached per tile so overlapping hexagons reuse tiles.

    Args:
        grid_gdf: GeoDataFrame with 'Subzone ID' (or 'Subzone_ID') + geometry, EPSG:4326.
        progress_cb: Optional callback(n_done, total) called every 50 hexagons.

    Returns:
        GeoDataFrame with columns Subzone_ID, dominant_EUNIS, dominant_EUNIS_name,
        habitat_count, dominant_pct, coverage_pct, geometry. CRS = grid_gdf.crs.
    """
    legend = _build_legend()

    gdf = grid_gdf
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    id_col = "Subzone ID" if "Subzone ID" in gdf.columns else "Subzone_ID"
    centroids = gdf.geometry.centroid

    tile_cache: dict = {}

    def _get_tile(tlon0, tlat0, tlon1, tlat1):
        key = (round(tlon0, 6), round(tlat0, 6), round(tlon1, 6), round(tlat1, 6))
        if key not in tile_cache:
            logger.debug("Fetching WMS tile: %s", key)
            tile_cache[key] = _fetch_wms_tile(tlon0, tlat0, tlon1, tlat1)
        return tile_cache[key]

    results = []
    total = len(gdf)

    for i, (idx, row) in enumerate(gdf.iterrows()):
        if progress_cb and (i % 50 == 0 or i == total - 1):
            progress_cb(i + 1, total)

        sid = row[id_col]
        centroid = centroids.iloc[i]
        clon, clat = centroid.x, centroid.y

        # Tile aligned to _MAX_TILE_DEG grid
        tile_lon0 = math.floor(clon / _MAX_TILE_DEG) * _MAX_TILE_DEG
        tile_lat0 = math.floor(clat / _MAX_TILE_DEG) * _MAX_TILE_DEG
        tile_lon1 = tile_lon0 + _MAX_TILE_DEG
        tile_lat1 = tile_lat0 + _MAX_TILE_DEG

        try:
            arr = _get_tile(tile_lon0, tile_lat0, tile_lon1, tile_lat1)
        except Exception as exc:
            logger.warning("WMS tile unavailable for %s: %s", sid, exc)
            results.append(_no_data_row(sid, row.geometry))
            continue

        r, g, b, a = _sample_tile(arr, clon, clat, tile_lon0, tile_lat0, tile_lon1, tile_lat1)

        if a < 128:
            results.append(_no_data_row(sid, row.geometry))
            continue

        code, name = legend.get((r, g, b), (None, None))
        if code is None:
            results.append(_no_data_row(sid, row.geometry))
            continue

        results.append({
            "Subzone_ID": sid,
            "dominant_EUNIS": code,
            "dominant_EUNIS_name": name,
            "habitat_count": 1,
            "dominant_pct": 100.0,
            "coverage_pct": 100.0,
            "geometry": row.geometry,
        })

    result_gdf = gpd.GeoDataFrame(results, crs=grid_gdf.crs)
    n_with = result_gdf["dominant_EUNIS"].notna().sum()
    logger.info("EuSEAMAP annotation: %d/%d hexagons assigned, %d WMS tiles used",
                n_with, total, len(tile_cache))
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
