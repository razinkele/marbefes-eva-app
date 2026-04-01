"""Tests for eva_hexgrid module."""

import pytest
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon


# A small square polygon near Klaipeda, Lithuania (~1km x 1km)
SMALL_POLYGON = Polygon([
    (21.12, 55.70),
    (21.13, 55.70),
    (21.13, 55.71),
    (21.12, 55.71),
    (21.12, 55.70),
])

# A larger polygon (~5km x 5km)
LARGE_POLYGON = Polygon([
    (21.10, 55.68),
    (21.17, 55.68),
    (21.17, 55.73),
    (21.10, 55.73),
    (21.10, 55.68),
])


def _make_gdf(geom, crs="EPSG:4326"):
    return gpd.GeoDataFrame(geometry=[geom], crs=crs)


class TestGenerateH3Grid:
    """Tests for generate_h3_grid()."""

    def test_returns_geodataframe(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        assert isinstance(result, gpd.GeoDataFrame)

    def test_has_subzone_id_column(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        assert "Subzone ID" in result.columns

    def test_has_geometry_column(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        assert "geometry" in result.columns
        assert result.geometry.geom_type.unique().tolist() == ["Polygon"]

    def test_subzone_id_format(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        n = len(result)
        width = max(3, len(str(n)))
        # IDs should be HEX_001, HEX_002, etc. (zero-padded to consistent width)
        assert result["Subzone ID"].iloc[0] == f"HEX_{1:0{width}d}"
        assert result["Subzone ID"].iloc[-1] == f"HEX_{n:0{width}d}"

    def test_subzone_ids_are_unique(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(LARGE_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        assert result["Subzone ID"].is_unique

    def test_crs_is_wgs84(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        assert result.crs.to_epsg() == 4326

    def test_nonwgs84_input_reprojected(self):
        """Input in a different CRS should be reprojected automatically."""
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON, crs="EPSG:4326")
        gdf_3857 = gdf.to_crs(epsg=3857)
        result = generate_h3_grid(gdf_3857, resolution=8)
        assert result.crs.to_epsg() == 4326
        assert len(result) > 0

    def test_higher_resolution_more_cells(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(LARGE_POLYGON)
        res7 = generate_h3_grid(gdf, resolution=7)
        res8 = generate_h3_grid(gdf, resolution=8)
        assert len(res8) > len(res7)

    def test_multipolygon_input(self):
        from eva_hexgrid import generate_h3_grid
        mp = MultiPolygon([SMALL_POLYGON, SMALL_POLYGON.buffer(0.02)])
        gdf = _make_gdf(mp)
        result = generate_h3_grid(gdf, resolution=8)
        assert len(result) > 0

    def test_empty_polyfill_raises(self):
        """A tiny polygon that fits no H3 cells should raise ValueError."""
        from eva_hexgrid import generate_h3_grid
        tiny = Polygon([
            (21.12, 55.70),
            (21.12001, 55.70),
            (21.12001, 55.70001),
            (21.12, 55.70001),
            (21.12, 55.70),
        ])
        gdf = _make_gdf(tiny)
        with pytest.raises(ValueError, match="No H3 cells"):
            generate_h3_grid(gdf, resolution=7)


class TestParsDrawnPolygon:
    """Tests for parse_drawn_polygon()."""

    def test_valid_geojson(self):
        from eva_hexgrid import parse_drawn_polygon
        import json
        geojson = json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[21.12, 55.70], [21.13, 55.70],
                                     [21.13, 55.71], [21.12, 55.71],
                                     [21.12, 55.70]]]
                },
                "properties": {}
            }]
        })
        result = parse_drawn_polygon(geojson)
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 1
        assert result.crs.to_epsg() == 4326

    def test_invalid_geojson_raises(self):
        from eva_hexgrid import parse_drawn_polygon
        with pytest.raises(ValueError, match="Invalid"):
            parse_drawn_polygon("not json at all")

    def test_self_intersecting_polygon_fixed(self):
        """Self-intersecting polygons should be made valid."""
        from eva_hexgrid import parse_drawn_polygon
        import json
        # Bowtie polygon (self-intersecting)
        geojson = json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]
                },
                "properties": {}
            }]
        })
        result = parse_drawn_polygon(geojson)
        assert result.geometry.is_valid.all()


class TestIntegration:
    """Integration tests: generated grid works with EVA pipeline."""

    def test_grid_has_correct_columns_for_pipeline(self):
        """Generated grid should have exactly the columns the pipeline expects."""
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(LARGE_POLYGON)
        grid = generate_h3_grid(gdf, resolution=8)
        # Pipeline expects at minimum: 'Subzone ID' and 'geometry'
        assert "Subzone ID" in grid.columns
        assert "geometry" in grid.columns
        # Accept both legacy object dtype and modern pandas StringDtype
        import pandas as pd
        sid_dtype = grid["Subzone ID"].dtype
        assert sid_dtype == object or isinstance(sid_dtype, pd.StringDtype)

    def test_grid_can_merge_with_sample_csv(self):
        """Grid should merge with CSV data on Subzone ID."""
        import pandas as pd
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        grid = generate_h3_grid(gdf, resolution=8)
        # Simulate CSV data with matching Subzone IDs
        csv_data = pd.DataFrame({
            "Subzone ID": grid["Subzone ID"].tolist(),
            "Species_A": range(len(grid)),
        })
        merged = grid.merge(csv_data, on="Subzone ID", how="inner")
        assert len(merged) == len(grid)
        assert "Species_A" in merged.columns
