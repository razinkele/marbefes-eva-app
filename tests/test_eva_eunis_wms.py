"""Tests for eva_eunis_wms module (offline / mocked)."""
import io
import json
import unittest
from unittest.mock import MagicMock, patch

import geopandas as gpd
import numpy as np
from PIL import Image
from shapely.geometry import Polygon

import eva_eunis_wms


def _make_grid(n=4):
    """Create a tiny synthetic hex-like grid GeoDataFrame."""
    polys = [
        Polygon([(20 + i * 0.1, 55), (20 + i * 0.1 + 0.05, 55.05),
                 (20 + i * 0.1 + 0.1, 55), (20 + i * 0.1 + 0.05, 54.95),
                 (20 + i * 0.1, 55)])
        for i in range(n)
    ]
    return gpd.GeoDataFrame(
        {"Subzone ID": [f"HEX_{i + 1:03d}" for i in range(n)]},
        geometry=polys,
        crs="EPSG:4326",
    )


def _make_legend_json(code="A5.27", color="#BF5000"):
    return json.dumps({
        "Legend": [{
            "rules": [{
                "title": f"A5.27: Deep circalittoral sand",
                "filter": f"[euniscomb = '{code}']",
                "symbolizers": [{"Polygon": {"fill": color}}],
            }]
        }]
    }).encode()


def _make_rgba_png(r, g, b, a=255, size=1024):
    arr = np.full((size, size, 4), [r, g, b, a], dtype=np.uint8)
    img = Image.fromarray(arr, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestBuildLegend(unittest.TestCase):
    def setUp(self):
        # Clear module-level cache
        eva_eunis_wms._legend_cache = None

    def test_parses_legend_correctly(self):
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = _make_legend_json("A5.27", "#BF5000")
            mock_url.return_value.__enter__ = lambda s: mock_resp
            mock_url.return_value.__exit__ = MagicMock(return_value=False)
            mock_url.return_value = mock_resp

            legend = eva_eunis_wms._build_legend()

        self.assertIn((0xBF, 0x50, 0x00), legend)
        code, name = legend[(0xBF, 0x50, 0x00)]
        self.assertEqual(code, "A5.27")
        self.assertIn("sand", name.lower())

    def test_caches_after_first_call(self):
        eva_eunis_wms._legend_cache = {(1, 2, 3): ("A1", "test")}
        with patch("urllib.request.urlopen") as mock_url:
            legend = eva_eunis_wms._build_legend()
            mock_url.assert_not_called()
        self.assertEqual(legend[(1, 2, 3)], ("A1", "test"))


class TestFetchEunisForGrid(unittest.TestCase):
    def setUp(self):
        eva_eunis_wms._legend_cache = {(0xBF, 0x50, 0x00): ("A5.27", "Deep circalittoral sand")}

    def test_assigns_eunis_from_solid_tile(self):
        grid = _make_grid(4)
        png_bytes = _make_rgba_png(0xBF, 0x50, 0x00)

        with patch.object(eva_eunis_wms, "_fetch_wms_tile", return_value=np.array(
            Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        )):
            result = eva_eunis_wms.fetch_eunis_for_grid(grid)

        self.assertEqual(len(result), 4)
        self.assertTrue((result["dominant_EUNIS"] == "A5.27").all())
        self.assertIn("Subzone_ID", result.columns)

    def test_transparent_tile_returns_no_data(self):
        grid = _make_grid(2)
        transparent_arr = np.zeros((1024, 1024, 4), dtype=np.uint8)

        with patch.object(eva_eunis_wms, "_fetch_wms_tile", return_value=transparent_arr):
            result = eva_eunis_wms.fetch_eunis_for_grid(grid)

        self.assertTrue(result["dominant_EUNIS"].isna().all())

    def test_subzone_id_column_set(self):
        grid = _make_grid(3)
        solid_arr = np.full((1024, 1024, 4), [0xBF, 0x50, 0x00, 255], dtype=np.uint8)

        with patch.object(eva_eunis_wms, "_fetch_wms_tile", return_value=solid_arr):
            result = eva_eunis_wms.fetch_eunis_for_grid(grid)

        self.assertListEqual(list(result["Subzone_ID"]), ["HEX_001", "HEX_002", "HEX_003"])


class TestComputeOverlayFromFile(unittest.TestCase):
    def test_dominant_by_area(self):
        # Create a hex and two overlapping habitat polygons
        hex_poly = Polygon([(20, 55), (20.1, 55), (20.1, 55.1), (20, 55.1), (20, 55)])
        grid = gpd.GeoDataFrame(
            {"Subzone ID": ["HEX_001"]},
            geometry=[hex_poly],
            crs="EPSG:4326",
        )
        # Two habitat polygons — A covers 70%, B covers 20%
        hab_a = Polygon([(20, 55), (20.07, 55), (20.07, 55.1), (20, 55.1), (20, 55)])
        hab_b = Polygon([(20.07, 55), (20.1, 55), (20.1, 55.1), (20.07, 55.1), (20.07, 55)])
        habitat = gpd.GeoDataFrame(
            {"EUNIScomb": ["A5.27", "A5.26"], "EUNIScombD": ["Sand", "Mud"]},
            geometry=[hab_a, hab_b],
            crs="EPSG:4326",
        )
        result = eva_eunis_wms.compute_overlay_from_file(grid, habitat)
        self.assertEqual(result.iloc[0]["dominant_EUNIS"], "A5.27")
        self.assertEqual(result.iloc[0]["Subzone_ID"], "HEX_001")

    def test_no_intersection_returns_null(self):
        hex_poly = Polygon([(20, 55), (20.1, 55), (20.1, 55.1), (20, 55.1), (20, 55)])
        grid = gpd.GeoDataFrame(
            {"Subzone ID": ["HEX_001"]},
            geometry=[hex_poly],
            crs="EPSG:4326",
        )
        far_away = Polygon([(30, 60), (31, 60), (31, 61), (30, 61), (30, 60)])
        habitat = gpd.GeoDataFrame(
            {"EUNIScomb": ["A5.27"]},
            geometry=[far_away],
            crs="EPSG:4326",
        )
        result = eva_eunis_wms.compute_overlay_from_file(grid, habitat)
        self.assertTrue(result.iloc[0]["dominant_EUNIS"] is None)


if __name__ == "__main__":
    unittest.main()
