"""Hexagonal grid generation using Uber H3 for EVA spatial analysis."""

import json
import logging
from pathlib import Path

import geopandas as gpd
import h3
from shapely.geometry import Polygon
from shapely.validation import make_valid

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Land mask — cached module-level to avoid re-downloading each call
# ---------------------------------------------------------------------------

_LAND_MASK: gpd.GeoDataFrame | None = None
_LAND_MASK_CACHE_PATH = Path(__file__).parent / "data" / "ne_50m_land.gpkg"
_LAND_MASK_URL = (
    "https://naturalearth.s3.amazonaws.com/50m_physical/ne_50m_land.zip"
)


def _load_land_mask() -> gpd.GeoDataFrame | None:
    """Return the Natural Earth 50m land polygon GDF (cached after first load).

    Tries the local cache first; falls back to downloading from Natural Earth.
    Returns None if both fail (graceful degradation — no clipping applied).
    """
    global _LAND_MASK
    if _LAND_MASK is not None:
        return _LAND_MASK

    # 1. Local cache
    if _LAND_MASK_CACHE_PATH.exists():
        try:
            _LAND_MASK = gpd.read_file(_LAND_MASK_CACHE_PATH)
            logger.info("Land mask loaded from local cache: %s", _LAND_MASK_CACHE_PATH)
            return _LAND_MASK
        except Exception as exc:
            logger.warning("Could not read cached land mask: %s", exc)

    # 2. Download from Natural Earth
    try:
        logger.info("Downloading Natural Earth 50m land polygons…")
        land = gpd.read_file(_LAND_MASK_URL)
        _LAND_MASK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        land.to_file(_LAND_MASK_CACHE_PATH, driver="GPKG")
        _LAND_MASK = land
        logger.info("Land mask downloaded and cached to %s", _LAND_MASK_CACHE_PATH)
        return _LAND_MASK
    except Exception as exc:
        logger.warning(
            "Could not download land mask — grid will not be clipped to sea: %s", exc
        )
        return None


def _clip_grid_to_sea(
    grid_gdf: gpd.GeoDataFrame, land_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Clip hex geometries to sea areas, removing land portions entirely.

    Computes sea = grid_bbox − land_union, clips each hex to that sea polygon,
    then drops slivers smaller than 5% of the median hex area.
    Subzone IDs are renumbered sequentially after clipping.
    """
    from shapely.geometry import box

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
        land = _load_land_mask()
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
