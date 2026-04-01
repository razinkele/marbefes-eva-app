"""Hexagonal grid generation using Uber H3 for EVA spatial analysis."""

import json
import logging

import geopandas as gpd
import h3
from shapely.geometry import Polygon
from shapely.validation import make_valid

logger = logging.getLogger(__name__)


def generate_h3_grid(polygon_gdf: gpd.GeoDataFrame, resolution: int) -> gpd.GeoDataFrame:
    """Generate H3 hexagonal grid cells covering the given polygon(s).

    Args:
        polygon_gdf: GeoDataFrame with polygon geometry (any CRS).
        resolution: H3 resolution level (7, 8, or 9).

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
