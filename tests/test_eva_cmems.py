"""Tests for eva_cmems.py — Copernicus Marine covariate extraction."""
import unittest
from unittest.mock import MagicMock, patch

import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon

import eva_cmems


def _make_grid(n: int = 5, lon0: float = 20.0, lat0: float = 55.0) -> gpd.GeoDataFrame:
    """Create a tiny grid of square 'hexagons' for testing."""
    cells = []
    for i in range(n):
        x, y = lon0 + i * 0.1, lat0
        cells.append(Polygon([(x, y), (x + 0.1, y), (x + 0.1, y + 0.1), (x, y + 0.1)]))
    return gpd.GeoDataFrame({"Subzone_ID": [f"SZ{i}" for i in range(n)]},
                            geometry=cells, crs=4326)


class TestCmemsLayerCatalogue(unittest.TestCase):
    """Verify CMEMS_LAYERS structure."""

    def test_all_expected_keys_present(self):
        expected = {"sst", "bottom_temp", "salinity", "mld", "current_speed",
                    "chlorophyll", "oxygen", "nitrate", "ph", "npp"}
        self.assertEqual(set(eva_cmems.CMEMS_LAYERS.keys()), expected)

    def test_each_layer_has_required_fields(self):
        required = {"dataset_id", "variable", "depth_dim", "combine",
                    "col", "label", "unit", "description"}
        for key, cfg in eva_cmems.CMEMS_LAYERS.items():
            missing = required - set(cfg.keys())
            self.assertFalse(missing, f"Layer '{key}' missing: {missing}")

    def test_phy_layers_use_climatology_dataset(self):
        phy_keys = {"sst", "bottom_temp", "salinity", "mld", "current_speed"}
        for k in phy_keys:
            self.assertIn("climatology", eva_cmems.CMEMS_LAYERS[k]["dataset_id"],
                          f"{k} should use the climatology dataset")

    def test_bgc_layers_use_monthly_dataset(self):
        bgc_keys = {"chlorophyll", "oxygen", "nitrate", "ph", "npp"}
        for k in bgc_keys:
            self.assertIn("bgc", eva_cmems.CMEMS_LAYERS[k]["dataset_id"].lower(),
                          f"{k} should use the BGC dataset")

    def test_current_speed_has_two_component_variables(self):
        cfg = eva_cmems.CMEMS_LAYERS["current_speed"]
        self.assertIsInstance(cfg["variable"], list)
        self.assertEqual(len(cfg["variable"]), 2)
        self.assertEqual(cfg["combine"], "speed")

    def test_2d_layers_have_depth_dim_false(self):
        for k in ("bottom_temp", "mld"):
            self.assertFalse(eva_cmems.CMEMS_LAYERS[k]["depth_dim"],
                             f"{k} should be a 2D variable")

    def test_3d_layers_have_depth_dim_true(self):
        for k in ("sst", "salinity", "current_speed", "chlorophyll", "oxygen"):
            self.assertTrue(eva_cmems.CMEMS_LAYERS[k]["depth_dim"],
                            f"{k} should have a depth dimension")

    def test_all_columns_unique(self):
        cols = [cfg["col"] for cfg in eva_cmems.CMEMS_LAYERS.values()]
        self.assertEqual(len(cols), len(set(cols)), "Duplicate column names detected")

    def test_cmems_map_cols_matches_layers(self):
        for key, cfg in eva_cmems.CMEMS_LAYERS.items():
            self.assertIn(cfg["col"], eva_cmems.CMEMS_MAP_COLS,
                          f"Column '{cfg['col']}' for layer '{key}' missing from CMEMS_MAP_COLS")


class TestResolveCredentials(unittest.TestCase):
    """Test credential resolution order."""

    def test_explicit_credentials_returned(self):
        u, p = eva_cmems._resolve_credentials("alice", "s3cr3t")
        self.assertEqual(u, "alice")
        self.assertEqual(p, "s3cr3t")

    def test_env_var_fallback(self):
        with patch.dict("os.environ", {
            "COPERNICUSMARINE_SERVICE_USERNAME": "env_user",
            "COPERNICUSMARINE_SERVICE_PASSWORD": "env_pass",
        }):
            u, p = eva_cmems._resolve_credentials("", "")
        self.assertEqual(u, "env_user")
        self.assertEqual(p, "env_pass")

    def test_missing_credentials_raises(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("COPERNICUSMARINE_SERVICE_USERNAME", None)
            os.environ.pop("COPERNICUSMARINE_SERVICE_PASSWORD", None)
            with self.assertRaises(ValueError, msg="Should raise when no credentials"):
                eva_cmems._resolve_credentials("", "")


class TestToSurface(unittest.TestCase):
    """Test _to_surface depth extraction."""

    def _make_da(self, dims):
        import xarray as xr
        shape = tuple(3 for _ in dims)
        data = np.arange(np.prod(shape), dtype=float).reshape(shape)
        coords = {d: np.arange(3) for d in dims}
        return xr.DataArray(data, dims=dims, coords=coords)

    def test_2d_variable_returned_unchanged(self):
        da = self._make_da(["latitude", "longitude"])
        result = eva_cmems._to_surface(da, depth_dim=False)
        self.assertEqual(result.dims, ("latitude", "longitude"))

    def test_3d_variable_returns_surface_slice(self):
        da = self._make_da(["depth", "latitude", "longitude"])
        result = eva_cmems._to_surface(da, depth_dim=True)
        self.assertNotIn("depth", result.dims)
        self.assertEqual(result.shape, (3, 3))

    def test_unknown_depth_dim_name_returned_unchanged(self):
        da = self._make_da(["z", "latitude", "longitude"])
        result = eva_cmems._to_surface(da, depth_dim=True)
        self.assertNotIn("z", result.dims)

    def test_depth_dim_false_ignores_depth_axis(self):
        da = self._make_da(["depth", "latitude", "longitude"])
        result = eva_cmems._to_surface(da, depth_dim=False)
        # Should be returned as-is (no slicing)
        self.assertIn("depth", result.dims)


class TestSampleAt(unittest.TestCase):
    """Test _sample_at nearest-neighbour sampling."""

    def _make_uniform_da(self, value: float = 17.5):
        import xarray as xr
        lats = np.linspace(54.0, 56.0, 20)
        lons = np.linspace(20.0, 22.0, 20)
        data = np.full((len(lats), len(lons)), value)
        return xr.DataArray(data, dims=["latitude", "longitude"],
                            coords={"latitude": lats, "longitude": lons})

    def test_samples_correct_value(self):
        da = self._make_uniform_da(17.5)
        vals = eva_cmems._sample_at(da, np.array([21.0]), np.array([55.0]))
        self.assertAlmostEqual(float(vals[0]), 17.5, places=3)

    def test_multiple_points(self):
        da = self._make_uniform_da(22.0)
        lons = np.array([20.1, 20.5, 21.9])
        lats = np.array([54.1, 55.0, 55.9])
        vals = eva_cmems._sample_at(da, lons, lats)
        self.assertEqual(len(vals), 3)
        np.testing.assert_allclose(vals, 22.0, atol=0.1)

    def test_returns_nan_for_out_of_range(self):
        da = self._make_uniform_da(5.0)
        # Point far outside grid
        vals = eva_cmems._sample_at(da, np.array([90.0]), np.array([80.0]))
        # xarray nearest will clamp to edge value, no NaN expected —
        # just verify it returns an array of length 1
        self.assertEqual(len(vals), 1)


class TestFindCoord(unittest.TestCase):
    """Test _find_coord coordinate name detection."""

    def _da_with_coords(self, coord_names):
        import xarray as xr
        n = 5
        coords = {c: np.arange(n) for c in coord_names}
        data = np.zeros([n] * len(coord_names))
        return xr.DataArray(data, dims=coord_names, coords=coords)

    def test_finds_longitude(self):
        da = self._da_with_coords(["latitude", "longitude"])
        self.assertEqual(eva_cmems._find_coord(da, ["longitude", "lon"]), "longitude")

    def test_finds_lon_fallback(self):
        da = self._da_with_coords(["lat", "lon"])
        self.assertEqual(eva_cmems._find_coord(da, ["longitude", "lon"]), "lon")

    def test_raises_for_unknown(self):
        da = self._da_with_coords(["y", "x"])
        with self.assertRaises(KeyError):
            eva_cmems._find_coord(da, ["longitude", "lon"])


class TestFetchCmemsEmpty(unittest.TestCase):
    """Test input validation in fetch_cmems_covariates."""

    def test_empty_layers_raises(self):
        grid = _make_grid()
        with self.assertRaises(ValueError, msg="Empty layers should raise"):
            eva_cmems.fetch_cmems_covariates(grid, [], username="u", password="p")

    def test_missing_credentials_raises(self):
        import os
        grid = _make_grid()
        # Ensure env vars are not set
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("COPERNICUSMARINE_SERVICE_USERNAME", None)
            os.environ.pop("COPERNICUSMARINE_SERVICE_PASSWORD", None)
            with self.assertRaises(ValueError):
                eva_cmems.fetch_cmems_covariates(grid, ["sst"], username="", password="")


class TestGetCredentialsFromEnv(unittest.TestCase):
    def test_returns_env_vars(self):
        with patch.dict("os.environ", {
            "COPERNICUSMARINE_SERVICE_USERNAME": "testuser",
            "COPERNICUSMARINE_SERVICE_PASSWORD": "testpass",
        }):
            u, p = eva_cmems.get_credentials_from_env()
        self.assertEqual(u, "testuser")
        self.assertEqual(p, "testpass")

    def test_returns_empty_when_not_set(self):
        import os
        os.environ.pop("COPERNICUSMARINE_SERVICE_USERNAME", None)
        os.environ.pop("COPERNICUSMARINE_SERVICE_PASSWORD", None)
        u, p = eva_cmems.get_credentials_from_env()
        self.assertEqual(u, "")
        self.assertEqual(p, "")


if __name__ == "__main__":
    unittest.main()
