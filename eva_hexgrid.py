"""Hexagonal grid generation using Uber H3 for EVA spatial analysis."""

import json
import logging
from pathlib import Path

import geopandas as gpd
import h3
from shapely.geometry import Polygon, box
from shapely.validation import make_valid

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Land mask — GADM Level-0 national boundaries (accurate, matches OSM)
# Falls back to Natural Earth 10m if GADM download fails.
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent / "data"

# GADM per-country cache (one GPKG per ISO3 country code)
_GADM_CACHE_DIR = _DATA_DIR / "gadm_cache"
_GADM_GPKG_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_{iso3}.gpkg"

# NE 10m admin countries — used to detect which ISO3 countries intersect the study area
_NE_COUNTRIES: gpd.GeoDataFrame | None = None
_NE_COUNTRIES_CACHE = _DATA_DIR / "ne_10m_countries.gpkg"
_NE_COUNTRIES_URL = (
    "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_countries.zip"
)

# NE 10m land polygons — fallback when GADM is unavailable
_LAND_MASK: gpd.GeoDataFrame | None = None
_LAND_MASK_CACHE_PATH = _DATA_DIR / "ne_10m_land.gpkg"
_LAND_MASK_URL = (
    "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_land.zip"
)


def _load_ne_countries() -> gpd.GeoDataFrame | None:
    """Load NE 10m admin-0 countries GDF for ISO3 country detection (cached)."""
    global _NE_COUNTRIES
    if _NE_COUNTRIES is not None:
        return _NE_COUNTRIES

    if _NE_COUNTRIES_CACHE.exists():
        try:
            _NE_COUNTRIES = gpd.read_file(_NE_COUNTRIES_CACHE)
            return _NE_COUNTRIES
        except Exception as exc:
            logger.warning("Could not read NE countries cache: %s", exc)

    try:
        logger.info("Downloading NE 10m admin-0 countries…")
        countries = gpd.read_file(_NE_COUNTRIES_URL)
        _NE_COUNTRIES_CACHE.parent.mkdir(parents=True, exist_ok=True)
        countries.to_file(_NE_COUNTRIES_CACHE, driver="GPKG")
        _NE_COUNTRIES = countries
        logger.info("NE countries cached to %s", _NE_COUNTRIES_CACHE)
        return _NE_COUNTRIES
    except Exception as exc:
        logger.warning("Could not download NE countries: %s", exc)
        return None


def _get_gadm_country(iso3: str) -> gpd.GeoDataFrame | None:
    """Return GADM Level-0 national boundary for *iso3* (ISO 3166-1 alpha-3).

    Uses GDAL HTTP range requests to fetch only the ADM_ADM_0 layer from the
    remote GPKG — no full file download required. Result is cached per country.
    """
    _GADM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _GADM_CACHE_DIR / f"ADM0_{iso3}.gpkg"

    if cache_file.exists():
        try:
            return gpd.read_file(cache_file)
        except Exception as exc:
            logger.warning("Corrupt GADM cache for %s, re-downloading: %s", iso3, exc)
            cache_file.unlink(missing_ok=True)

    remote_url = f"/vsicurl/{_GADM_GPKG_URL.format(iso3=iso3)}"
    try:
        logger.info("Fetching GADM L0 for %s via range request…", iso3)
        gdf = gpd.read_file(remote_url, layer="ADM_ADM_0")
        gdf = gdf[["geometry"]].copy()
        gdf.to_file(cache_file, driver="GPKG")
        logger.info("GADM L0 for %s cached to %s", iso3, cache_file)
        return gdf
    except Exception as exc:
        logger.warning("Could not fetch GADM for %s: %s", iso3, exc)
        return None


def _get_gadm_land_for_area(bounds: tuple) -> gpd.GeoDataFrame | None:
    """Return GADM Level-0 land GDF for all countries intersecting *bounds*.

    Downloads per-country on demand and caches results. Falls back gracefully.
    Returns None if no GADM data could be obtained.
    """
    countries = _load_ne_countries()
    if countries is None:
        return None

    minx, miny, maxx, maxy = bounds
    search_bbox = box(minx - 0.5, miny - 0.5, maxx + 0.5, maxy + 0.5)

    # Identify ISO3 codes for countries that overlap the study area
    iso_col = "ISO_A3" if "ISO_A3" in countries.columns else "ADM0_A3"
    intersecting = countries[countries.geometry.intersects(search_bbox)]
    iso3_codes = (
        intersecting[iso_col].dropna().unique().tolist()
        if iso_col in intersecting.columns
        else []
    )
    iso3_codes = [c for c in iso3_codes if len(c) == 3 and c != "-99"]

    if not iso3_codes:
        logger.info("No countries found in bbox — GADM land mask unavailable")
        return None

    gdfs = []
    for iso3 in iso3_codes:
        gdf = _get_gadm_country(iso3)
        if gdf is not None:
            gdfs.append(gdf)

    if not gdfs:
        return None

    import pandas as pd
    combined = gpd.GeoDataFrame(
        pd.concat([g[["geometry"]] for g in gdfs], ignore_index=True),
        crs="EPSG:4326",
    )
    logger.info("GADM land mask assembled from %d country/ies: %s", len(gdfs), iso3_codes)
    return combined


def _load_land_mask() -> gpd.GeoDataFrame | None:
    """Return NE 10m land polygon GDF (cached). Used as GADM fallback."""
    global _LAND_MASK
    if _LAND_MASK is not None:
        return _LAND_MASK

    if _LAND_MASK_CACHE_PATH.exists():
        try:
            _LAND_MASK = gpd.read_file(_LAND_MASK_CACHE_PATH)
            logger.info("NE 10m land mask loaded from cache")
            return _LAND_MASK
        except Exception as exc:
            logger.warning("Could not read NE land mask cache: %s", exc)

    try:
        logger.info("Downloading NE 10m land polygons…")
        land = gpd.read_file(_LAND_MASK_URL)
        _LAND_MASK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        land.to_file(_LAND_MASK_CACHE_PATH, driver="GPKG")
        _LAND_MASK = land
        logger.info("NE 10m land mask cached to %s", _LAND_MASK_CACHE_PATH)
        return _LAND_MASK
    except Exception as exc:
        logger.warning("Could not download NE land mask: %s", exc)
        return None


def _get_best_land_mask(bounds: tuple) -> gpd.GeoDataFrame | None:
    """Return the most accurate available land mask for the given bounding box.

    Tries GADM Level-0 national boundaries first (matches OSM within ~50 m).
    Falls back to Natural Earth 10m if GADM is unavailable.
    """
    gadm = _get_gadm_land_for_area(bounds)
    if gadm is not None:
        return gadm
    logger.info("GADM unavailable — falling back to NE 10m land mask")
    return _load_land_mask()


def _clip_grid_to_sea(
    grid_gdf: gpd.GeoDataFrame, land_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Clip hex geometries to sea areas, removing land portions entirely.

    Computes sea = grid_bbox − land_union, clips each hex to that sea polygon,
    then drops slivers smaller than 5% of the median hex area.
    Subzone IDs are renumbered sequentially after clipping.
    """
    # Restrict land polygons to those intersecting the grid area (speed)
    minx, miny, maxx, maxy = grid_gdf.total_bounds
    grid_bbox = box(minx - 0.1, miny - 0.1, maxx + 0.1, maxy + 0.1)
    local_land = land_gdf[land_gdf.geometry.intersects(grid_bbox)]

    if local_land.empty:
        logger.info("No land polygons intersect the grid area — no clipping applied")
        return grid_gdf

    land_union = local_land.geometry.union_all()
    sea_geom = grid_bbox.difference(land_union)
    sea_gdf = gpd.GeoDataFrame(geometry=[sea_geom], crs="EPSG:4326")

    # Clip all hexes against the sea polygon
    clipped = gpd.clip(grid_gdf, sea_gdf)

    # Drop tiny slivers (< 5% of median original hex area) — use projected CRS for area
    grid_proj = grid_gdf.to_crs(epsg=3857)
    clipped_proj = clipped.to_crs(epsg=3857)
    median_hex_area = grid_proj.geometry.area.median()
    clipped = clipped[clipped_proj.geometry.area > 0.05 * median_hex_area].reset_index(drop=True)

    removed = len(grid_gdf) - len(clipped)
    if removed:
        logger.info(
            "Land mask: clipped grid to sea — %d cells removed, %d remaining",
            removed, len(clipped),
        )

    # Renumber Subzone IDs sequentially
    width = max(3, len(str(len(clipped))))
    clipped["Subzone ID"] = [f"HEX_{i + 1:0{width}d}" for i in range(len(clipped))]

    return clipped


def generate_h3_grid(
    polygon_gdf: gpd.GeoDataFrame, resolution: int, clip_to_sea: bool = True
) -> gpd.GeoDataFrame:
    """Generate H3 hexagonal grid cells covering the given polygon(s).

    Args:
        polygon_gdf: GeoDataFrame with polygon geometry (any CRS).
        resolution: H3 resolution level (7, 8, or 9).
        clip_to_sea: If True (default), remove hexagons whose centroid falls
            on land using Natural Earth 50m land polygons.

    Returns:
        GeoDataFrame with 'Subzone ID' and 'geometry' columns in EPSG:4326.

    Raises:
        ValueError: If no H3 cells fit within the polygon at the given resolution.
    """
    # Reproject to WGS84 if needed
    gdf = polygon_gdf.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Collect all H3 cell indices across all geometries
    all_cells = set()
    for geom in gdf.geometry:
        if geom is None:
            continue
        # Handle MultiPolygon by iterating sub-geometries
        if geom.geom_type == "MultiPolygon":
            polygons = list(geom.geoms)
        else:
            polygons = [geom]

        for poly in polygons:
            geojson = poly.__geo_interface__
            cells = h3.geo_to_cells(geojson, res=resolution)
            all_cells.update(cells)

    if not all_cells:
        raise ValueError(
            f"No H3 cells fit within the polygon at resolution {resolution}. "
            "Try a finer resolution (higher number)."
        )

    # Convert H3 indices to polygons
    hex_polygons = []
    for cell_id in sorted(all_cells):
        boundary = h3.cell_to_boundary(cell_id)
        # h3 returns (lat, lng) pairs; shapely needs (lng, lat)
        coords = [(lng, lat) for lat, lng in boundary]
        coords.append(coords[0])  # close the ring
        hex_polygons.append(Polygon(coords))

    # Build GeoDataFrame
    width = max(3, len(str(len(hex_polygons))))
    subzone_ids = [f"HEX_{i+1:0{width}d}" for i in range(len(hex_polygons))]
    result = gpd.GeoDataFrame(
        {"Subzone ID": subzone_ids},
        geometry=hex_polygons,
        crs="EPSG:4326",
    )

    logger.info(
        f"Generated {len(result)} H3 cells at resolution {resolution}"
    )

    # Clip to sea: remove land portions from each hex geometry
    if clip_to_sea:
        land = _get_best_land_mask(result.total_bounds)
        if land is not None:
            result = _clip_grid_to_sea(result, land)
            if not len(result):
                raise ValueError(
                    "All generated hexagons fall on land. "
                    "Please draw a marine study area."
                )

    return result


def parse_drawn_polygon(geojson_str: str) -> gpd.GeoDataFrame:
    """Parse GeoJSON string from Leaflet Draw into a GeoDataFrame.

    Args:
        geojson_str: GeoJSON FeatureCollection string.

    Returns:
        GeoDataFrame with polygon geometry in EPSG:4326.

    Raises:
        ValueError: If the input is not valid GeoJSON.
    """
    try:
        data = json.loads(geojson_str)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Invalid GeoJSON: {exc}") from exc

    try:
        gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Invalid GeoJSON FeatureCollection: {exc}") from exc

    # Fix any invalid geometries
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: make_valid(g) if g is not None and not g.is_valid else g
    )

    return gdf
