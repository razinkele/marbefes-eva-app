"""Tests for eva_map helper functions."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eva_map import auto_zoom_level, _build_legend_html, create_ev_map, create_grid_only_map, create_habitat_map
import geopandas as gpd
from shapely.geometry import box


# ── auto_zoom_level edge cases ──────────────────────────────────────────────

class TestAutoZoomLevel:
    def test_large_bounds(self):
        """max_diff > 10 -> zoom 5."""
        bounds = [0, 0, 20, 20]
        assert auto_zoom_level(bounds) == 5

    def test_medium_bounds(self):
        """5 < max_diff <= 10 -> zoom 7."""
        bounds = [0, 0, 8, 8]
        assert auto_zoom_level(bounds) == 7

    def test_small_bounds(self):
        """1 < max_diff <= 5 -> zoom 9."""
        bounds = [10, 50, 13, 53]
        assert auto_zoom_level(bounds) == 9

    def test_tiny_bounds(self):
        """0.1 < max_diff <= 1 -> zoom 12."""
        bounds = [10, 50, 10.5, 50.5]
        assert auto_zoom_level(bounds) == 12

    def test_micro_bounds(self):
        """max_diff <= 0.1 -> zoom 14."""
        bounds = [10, 50, 10.05, 50.05]
        assert auto_zoom_level(bounds) == 14

    def test_boundary_exactly_10(self):
        """max_diff == 10 is not > 10, so should be zoom 7."""
        bounds = [0, 0, 10, 10]
        assert auto_zoom_level(bounds) == 7

    def test_boundary_exactly_5(self):
        """max_diff == 5 is not > 5, so should be zoom 9."""
        bounds = [0, 0, 5, 5]
        assert auto_zoom_level(bounds) == 9

    def test_lat_dominated(self):
        """When lat diff is larger than lon diff."""
        bounds = [10, 0, 11, 20]  # lon_diff=1, lat_diff=20
        assert auto_zoom_level(bounds) == 5


# ── _build_legend_html ──────────────────────────────────────────────────────

class TestBuildLegendHtml:
    def test_xss_in_title(self):
        """Script tags in title must be escaped."""
        html = _build_legend_html("<script>alert(1)</script>", [])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_xss_in_label(self):
        """Script tags in item labels must be escaped."""
        html = _build_legend_html("Safe", [("#ff0000", '<img src=x onerror="alert(1)">')])
        assert 'onerror="alert(1)"' not in html
        assert "&lt;img" in html

    def test_xss_in_color(self):
        """Malicious content in color field must be escaped (quotes neutralised)."""
        html = _build_legend_html("Title", [('" onclick="alert(1)', "Label")])
        # The raw double-quote must be escaped so it cannot break out of the style attribute
        assert 'onclick="alert' not in html
        assert "&quot;" in html

    def test_normal_labels(self):
        """Normal text labels appear correctly."""
        html = _build_legend_html("My Legend", [("#00ff00", "Category A"), ("#0000ff", "Category B")])
        assert "My Legend" in html
        assert "Category A" in html
        assert "Category B" in html
        assert "#00ff00" in html

    def test_empty_items(self):
        """Empty items list produces a legend with just a title."""
        html = _build_legend_html("Empty", [])
        assert "Empty" in html
        assert html.count("<p") == 1  # only the title paragraph

    def test_returns_closed_div(self):
        """Legend HTML must be a complete div."""
        html = _build_legend_html("T", [("#fff", "L")])
        assert html.startswith("<div")
        assert html.endswith("</div>")


# ── create_ev_map smoke tests ────────────────────────────────────────────────

class TestCreateEvMap:
    def test_returns_html_string(self):
        """Basic smoke test: create_ev_map returns HTML."""
        gdf = gpd.GeoDataFrame({
            "Subzone ID": ["A", "B"],
            "EV": [2.5, 4.0],
        }, geometry=[box(21.0, 55.5, 21.1, 55.6), box(21.1, 55.5, 21.2, 55.6)],
           crs="EPSG:4326")

        html = create_ev_map(gdf, "EV", "Viridis", "Continuous", "CartoDB Positron", 0.7)
        assert isinstance(html, str)
        assert "folium" in html.lower() or "leaflet" in html.lower()
        assert len(html) > 100

    def test_with_5class_classification(self):
        gdf = gpd.GeoDataFrame({
            "Subzone ID": ["A", "B"],
            "EV": [1.0, 4.5],
        }, geometry=[box(21.0, 55.5, 21.1, 55.6), box(21.1, 55.5, 21.2, 55.6)],
           crs="EPSG:4326")

        html = create_ev_map(gdf, "EV", "Viridis", "EVA 5-class (VL/L/M/H/VH)", "CartoDB Positron", 0.7)
        assert isinstance(html, str)
        assert len(html) > 100


# ── create_grid_only_map smoke tests ────────────────────────────────────────

class TestCreateGridOnlyMap:
    def _make_gdf(self):
        return gpd.GeoDataFrame(
            {"Subzone ID": ["A1", "A2", "A3"]},
            geometry=[box(21.0, 55.5, 21.1, 55.6), box(21.1, 55.5, 21.2, 55.6), box(21.2, 55.5, 21.3, 55.6)],
            crs="EPSG:4326",
        )

    def test_returns_html_string(self):
        html = create_grid_only_map(self._make_gdf())
        assert isinstance(html, str)
        assert "leaflet" in html.lower() or "folium" in html.lower()
        assert len(html) > 100

    def test_shows_subzone_count_in_legend(self):
        html = create_grid_only_map(self._make_gdf())
        assert "3 subzones" in html


# ── create_habitat_map smoke tests ───────────────────────────────────────────

class TestCreateHabitatMap:
    def _make_gdf(self):
        return gpd.GeoDataFrame(
            {"Subzone ID": ["A1", "A2"]},
            geometry=[box(21.0, 55.5, 21.1, 55.6), box(21.1, 55.5, 21.2, 55.6)],
            crs="EPSG:4326",
        )

    def test_returns_html_string(self):
        assignments = {"A1": "A5.53", "A2": "MC35"}
        html = create_habitat_map(self._make_gdf(), assignments, "CartoDB Positron", 0.7)
        assert isinstance(html, str)
        assert len(html) > 100

    def test_legend_shows_habitat_codes(self):
        assignments = {"A1": "A5.53", "A2": "MC35"}
        html = create_habitat_map(self._make_gdf(), assignments, "CartoDB Positron", 0.7)
        assert "A5.53" in html
        assert "MC35" in html

    def test_layer_control_present(self):
        assignments = {"A1": "A5.53", "A2": "MC35"}
        html = create_habitat_map(self._make_gdf(), assignments, "CartoDB Positron", 0.7)
        # LayerControl JS is entity-encoded inside the iframe srcdoc
        assert "control.layers" in html or "layer_control" in html

