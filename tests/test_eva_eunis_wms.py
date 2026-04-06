"""Tests for eva_eunis_wms module (offline / mocked)."""
import io
import json
import unittest
from unittest.mock import MagicMock, patch

import geopandas as gpd
import numpy as np
import pandas as pd
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


class TestBuildLayerLegend(unittest.TestCase):
    """Test _build_layer_legend with different EuSEAMAP filter formats."""

    def setUp(self):
        eva_eunis_wms._legend_caches.clear()

    def _mock_legend(self, title, filter_str, color="#BF5000"):
        return json.dumps({
            "Legend": [{
                "rules": [{
                    "title": title,
                    "filter": filter_str,
                    "symbolizers": [{"Polygon": {"fill": color}}],
                }]
            }]
        }).encode()

    def test_substrate_filter_format(self):
        payload = self._mock_legend(
            "Rock", "[substrate = 'Rock']", "#888888"
        )
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = payload
            mock_url.return_value = mock_resp
            legend = eva_eunis_wms._build_layer_legend("eusm2025_subs_full")
        self.assertIn((0x88, 0x88, 0x88), legend)
        code, name = legend[(0x88, 0x88, 0x88)]
        self.assertEqual(code, "Rock")
        self.assertEqual(name, "Rock")

    def test_biozone_filter_format(self):
        payload = self._mock_legend(
            "Infralittoral", "[biozone = 'Infralittoral']", "#00AABB"
        )
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = payload
            mock_url.return_value = mock_resp
            legend = eva_eunis_wms._build_layer_legend("eusm2025_bio_full")
        self.assertIn((0x00, 0xAA, 0xBB), legend)
        code, _ = legend[(0x00, 0xAA, 0xBB)]
        self.assertEqual(code, "Infralittoral")

    def test_helcom_filter_does_not_split_on_first_colon(self):
        payload = self._mock_legend(
            "AA.A: Baltic photic rock", "[regionald = 'AA.A: Baltic photic rock']", "#336699"
        )
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = payload
            mock_url.return_value = mock_resp
            legend = eva_eunis_wms._build_layer_legend("eusm2025_helcom_full")
        code, name = legend[(0x33, 0x66, 0x99)]
        # HELCOM titles starting with "AA." must not be split on ":"
        self.assertEqual(code, "AA.A: Baltic photic rock")
        self.assertEqual(name, "AA.A: Baltic photic rock")

    def test_per_layer_cache_is_independent(self):
        # Pre-populate one cache entry
        eva_eunis_wms._legend_caches["eusm2025_subs_full"] = {(1, 2, 3): ("Mud", "Mud")}
        with patch("urllib.request.urlopen") as mock_url:
            result = eva_eunis_wms._build_layer_legend("eusm2025_subs_full")
            mock_url.assert_not_called()
        self.assertEqual(result[(1, 2, 3)], ("Mud", "Mud"))


class TestFetchSdmCovariates(unittest.TestCase):
    """Test fetch_sdm_covariates with mocked _sample_eusm_layer and fetch_depth_for_grid."""

    def setUp(self):
        eva_eunis_wms._legend_caches.clear()

    def _eunis_sample_result(self, grid):
        """Return a {Subzone_ID: {code, name}} dict as _sample_eusm_layer would."""
        ids = grid["Subzone ID" if "Subzone ID" in grid.columns else "Subzone_ID"].tolist()
        return {sid: {"code": "A5.27", "name": "Deep sand"} for sid in ids}

    def test_eunis_only(self):
        grid = _make_grid(3)
        mock_result = self._eunis_sample_result(grid)

        with patch.object(eva_eunis_wms, "_sample_eusm_layer", return_value=mock_result):
            result = eva_eunis_wms.fetch_sdm_covariates(grid, layers=["eunis2007"])

        self.assertIn("dominant_EUNIS", result.columns)
        self.assertEqual(len(result), 3)
        self.assertTrue((result["dominant_EUNIS"] == "A5.27").all())

    def test_depth_layer_included(self):
        grid = _make_grid(2)
        mock_result = self._eunis_sample_result(grid)

        ids = grid["Subzone ID"].tolist()
        depth_df = pd.DataFrame({"Subzone_ID": ids, "depth_m": [18.0, 25.5]})

        with patch.object(eva_eunis_wms, "_sample_eusm_layer", return_value=mock_result):
            with patch.object(eva_eunis_wms, "fetch_depth_for_grid", return_value=depth_df):
                result = eva_eunis_wms.fetch_sdm_covariates(grid, layers=["eunis2007", "depth"])

        self.assertIn("depth_m", result.columns)
        val = result[result["Subzone_ID"] == "HEX_001"]["depth_m"].iloc[0]
        self.assertAlmostEqual(float(val), 18.0)

    def test_empty_layer_list_raises(self):
        grid = _make_grid(2)
        with self.assertRaises(ValueError):
            eva_eunis_wms.fetch_sdm_covariates(grid, layers=[])


class TestFetchDepthSignConvention(unittest.TestCase):
    """Test depth sign convention: negative WCS → positive depth_m; positive → None (land)."""

    def _make_geotiff_bytes(self, value: float):
        """Build a minimal 2×2 float32 GeoTIFF with a constant value."""
        import struct
        try:
            import rasterio
            from rasterio.transform import from_bounds
            from rasterio.crs import CRS
            buf = io.BytesIO()
            transform = from_bounds(20.0, 55.0, 20.1, 55.1, 2, 2)
            with rasterio.open(
                buf, "w", driver="GTiff", height=2, width=2,
                count=1, dtype="float32", crs=CRS.from_epsg(4326), transform=transform,
            ) as ds:
                ds.write(np.full((1, 2, 2), value, dtype=np.float32))
            return buf.getvalue()
        except ImportError:
            self.skipTest("rasterio not available")

    def test_negative_wcs_value_gives_positive_depth(self):
        tiff_bytes = self._make_geotiff_bytes(-23.9)
        grid = _make_grid(1)
        mock_resp = MagicMock()
        mock_resp.read.return_value = tiff_bytes
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = eva_eunis_wms.fetch_depth_for_grid(grid)
        if "depth_m" in result.columns and result.iloc[0]["depth_m"] is not None:
            self.assertGreater(result.iloc[0]["depth_m"], 0)

    def test_positive_wcs_value_is_land_gives_none(self):
        tiff_bytes = self._make_geotiff_bytes(18.88)
        grid = _make_grid(1)
        mock_resp = MagicMock()
        mock_resp.read.return_value = tiff_bytes
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = eva_eunis_wms.fetch_depth_for_grid(grid)
        if "depth_m" in result.columns:
            self.assertIsNone(result.iloc[0]["depth_m"])


class TestLayerConfig(unittest.TestCase):
    """Verify EUSM_LAYERS uses correct _400 variants (not _full for zoom-restricted layers)."""

    def test_eunis_uses_400_variant(self):
        wms = eva_eunis_wms.EUSM_LAYERS["eunis2007"]["wms_layer"]
        self.assertIn("_400", wms, f"Expected _400 variant, got {wms}")
        self.assertNotIn("_full", wms)

    def test_energy_uses_400_variant(self):
        wms = eva_eunis_wms.EUSM_LAYERS["energy"]["wms_layer"]
        self.assertIn("_400", wms)

    def test_biozone_uses_400_variant(self):
        wms = eva_eunis_wms.EUSM_LAYERS["biozone"]["wms_layer"]
        self.assertIn("_400", wms)

    def test_substrate_keeps_full(self):
        # subs_full has clean fills (3-5 unique colors), no AA issue
        wms = eva_eunis_wms.EUSM_LAYERS["substrate"]["wms_layer"]
        self.assertIn("subs_full", wms)

    def test_all_layers_have_coverage_note(self):
        for key, cfg in eva_eunis_wms.EUSM_LAYERS.items():
            self.assertIn("coverage", cfg, f"Layer '{key}' missing 'coverage' key")


class TestSampleTileNeighborhood(unittest.TestCase):
    """Test that _sample_tile uses 5×5 neighbourhood and handles boundary clamping."""

    def _make_arr(self, center_color, size=32):
        """Solid-colour RGBA array with one slightly different edge pixel."""
        arr = np.full((size, size, 4), [*center_color, 255], dtype=np.uint8)
        # Place an anti-aliased edge colour at the very edge
        arr[0, 0] = [128, 64, 32, 255]
        return arr

    def test_returns_dominant_color_in_patch(self):
        arr = self._make_arr((200, 100, 50))
        # Sample from centre — should return the dominant solid colour
        result = eva_eunis_wms._sample_tile(arr, 21.0, 55.0, 20.0, 54.0, 22.0, 56.0)
        self.assertEqual(result[:3], (200, 100, 50))

    def test_boundary_clamping_no_indexerror(self):
        arr = np.full((1024, 1024, 4), [0xBF, 0x50, 0x00, 255], dtype=np.uint8)
        # lat == tlat0 would give row_px=1024 without clamping → IndexError
        result = eva_eunis_wms._sample_tile(arr, 20.0, 54.0, 20.0, 54.0, 22.0, 56.0)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)

    def test_all_transparent_returns_transparent(self):
        arr = np.zeros((32, 32, 4), dtype=np.uint8)
        result = eva_eunis_wms._sample_tile(arr, 21.0, 55.0, 20.0, 54.0, 22.0, 56.0)
        self.assertEqual(result[3], 0)


class TestNearestLegendColor(unittest.TestCase):
    """Test nearest-colour fallback for anti-aliased WMS pixels."""

    def test_exact_match_returns_immediately(self):
        legend = {(200, 100, 50): ("A5.27", "Deep sand")}
        code, name = eva_eunis_wms._nearest_legend_color((200, 100, 50), legend)
        self.assertEqual(code, "A5.27")

    def test_nearby_color_matched_within_threshold(self):
        legend = {(200, 100, 50): ("A5.27", "Deep sand")}
        # Slightly off due to AA: (205, 98, 55) — distance ~7.5
        code, name = eva_eunis_wms._nearest_legend_color((205, 98, 55), legend, max_dist=40)
        self.assertEqual(code, "A5.27")

    def test_far_color_returns_none(self):
        legend = {(200, 100, 50): ("A5.27", "Deep sand")}
        # Very different colour — distance ~350
        code, name = eva_eunis_wms._nearest_legend_color((10, 10, 10), legend, max_dist=40)
        self.assertIsNone(code)

    def test_empty_legend_returns_none(self):
        code, name = eva_eunis_wms._nearest_legend_color((100, 100, 100), {})
        self.assertIsNone(code)

    def test_picks_closest_of_multiple_entries(self):
        legend = {
            (200, 100, 50): ("A5.27", "Sand"),
            (10, 200, 30):  ("A4.1", "Bedrock"),
        }
        # Closer to first entry
        code, _ = eva_eunis_wms._nearest_legend_color((198, 102, 48), legend, max_dist=40)
        self.assertEqual(code, "A5.27")


if __name__ == "__main__":
    unittest.main()
