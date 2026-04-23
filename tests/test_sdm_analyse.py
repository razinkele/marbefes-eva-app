"""Tests for scripts/sdm_analyse.py — the script's testable functions."""
import numpy as np
import pandas as pd
import pytest

from scripts.sdm_analyse import analyse_collinearity, _align_valid_for_residuals, detect_coord_cols


class TestAnalyseCollinearityNaN:
    def test_nan_in_eunis_does_not_raise(self):
        """Regression: sorted() on a series with NaN + strings used to raise TypeError."""
        sites = pd.DataFrame({
            "dominant_EUNIS2019": ["A5.25", "A5.25", np.nan, "A4.4"],
            "depth_m": [10.0, 20.0, 30.0, 40.0],
        })
        out = analyse_collinearity(sites, env_cols=["depth_m"])
        assert "habitat_counts" in out

    def test_nan_not_present_as_habitat_key(self):
        """NaN must not appear as a key in habitat_counts or depth_by_habitat."""
        sites = pd.DataFrame({
            "dominant_EUNIS2019": ["A5.25", np.nan, "A4.4", "A5.25"],
            "depth_m": [10.0, 20.0, 30.0, 40.0],
        })
        out = analyse_collinearity(sites, env_cols=["depth_m"])
        assert not any(pd.isna(k) for k in out["habitat_counts"])
        assert not any(pd.isna(k) for k in out["depth_by_habitat"])


class TestAlignValidForResiduals:
    """Helper extraction: the DataFrame rebuild that must align with what
    eva_sdm.prepare_features kept, so residual-kriging can safely assign
    a residual Series onto the surviving rows."""

    def test_helper_drops_species_nan(self):
        sites = pd.DataFrame({
            "sp": [1.0, 2.0, np.nan, 4.0],     # row index 2 has NaN response
            "depth_m": [10.0, 20.0, 30.0, 40.0],
            "slope": [0.1, 0.2, 0.3, 0.4],
        })
        valid = _align_valid_for_residuals(sites, ["depth_m", "slope"], "sp")
        assert len(valid) == 3                  # row 2 dropped
        assert valid["sp"].isna().sum() == 0

    def test_helper_drops_feature_nan(self):
        sites = pd.DataFrame({
            "sp": [1.0, 2.0, 3.0, 4.0],
            "depth_m": [10.0, np.nan, 30.0, 40.0],   # row 1 has NaN feature
            "slope": [0.1, 0.2, 0.3, 0.4],
        })
        valid = _align_valid_for_residuals(sites, ["depth_m", "slope"], "sp")
        assert len(valid) == 3
        assert valid["depth_m"].isna().sum() == 0

    def test_helper_reset_index(self):
        """valid must have a contiguous RangeIndex starting at 0 so residual assignment by position is safe."""
        sites = pd.DataFrame({
            "sp": [1.0, np.nan, 3.0],
            "x": [1.0, 2.0, 3.0],
        })
        valid = _align_valid_for_residuals(sites, ["x"], "sp")
        assert list(valid.index) == [0, 1]

    def test_helper_ignores_all_nan_columns(self):
        """Mirror prepare_features: a column that is 100% NaN must not drop all rows."""
        sites = pd.DataFrame({
            "sp": [1.0, 2.0, 3.0],
            "depth_m": [10.0, 20.0, 30.0],
            "all_nan_feature": [np.nan, np.nan, np.nan],  # column fully NaN
        })
        valid = _align_valid_for_residuals(
            sites, ["depth_m", "all_nan_feature"], "sp"
        )
        assert len(valid) == 3, f"expected all 3 rows kept, got {len(valid)}"


class TestCompareMethodsCoordCols:
    """Ensure compare_methods accepts aliased lat/lon column names."""

    def _sites(self, lat_name="latitude", lon_name="longitude"):
        coords = [(20 + i * 0.1, 55 + i * 0.1) for i in range(12)]
        return pd.DataFrame({
            lat_name: [c[1] for c in coords],
            lon_name: [c[0] for c in coords],
            "depth_m": [10.0 + i for i in range(12)],
            "sp": [0.1 * i + 0.5 for i in range(12)],
        })

    def _cov_grid(self):
        import geopandas as gpd
        from shapely.geometry import Point
        return gpd.GeoDataFrame(
            {"depth_m": [10.0, 20.0, 30.0]},
            geometry=[Point(20.1, 55.1), Point(20.2, 55.2), Point(20.3, 55.3)],
            crs="EPSG:4326",
        )

    def test_rf_method_accepts_aliased_coord_cols(self):
        """rf branch does not touch _sites_to_metric, but the signature must accept the kwargs."""
        from scripts.sdm_analyse import compare_methods
        sites = self._sites()
        cov = self._cov_grid()
        results = compare_methods(
            sites, "sp", cov,
            methods=["rf"],
            env_cols=["depth_m"],
            eunis_cols=[],
            lat_col="latitude", lon_col="longitude",
        )
        # At least one RF result dict present, no signature error raised
        assert any("RF" in k or k == "rf" for k in results), f"got: {list(results)!r}"

    def test_kriging_method_accepts_aliased_coord_cols(self):
        """kriging branch passes lat_col/lon_col to _sites_to_metric — no KeyError on aliases."""
        pytest.importorskip("pykrige")
        from scripts.sdm_analyse import compare_methods
        sites = self._sites()
        cov = self._cov_grid()
        results = compare_methods(
            sites, "sp", cov,
            methods=["kriging"],
            env_cols=["depth_m"],
            eunis_cols=[],
            lat_col="latitude", lon_col="longitude",
        )
        err = results.get("Ordinary Kriging", {}).get("error", "")
        assert "lat" not in err and "lon" not in err, \
            f"coord-name KeyError suggests threading failed: {err!r}"


class TestDetectCoordCols:
    def test_defaults_when_no_match(self):
        df = pd.DataFrame({"x": [1.0], "y": [2.0]})
        assert detect_coord_cols(df) == ("lat", "lon")

    def test_exact_match(self):
        df = pd.DataFrame({"lat": [1.0], "lon": [2.0]})
        assert detect_coord_cols(df) == ("lat", "lon")

    def test_case_insensitive_title(self):
        df = pd.DataFrame({"Latitude": [1.0], "Longitude": [2.0]})
        assert detect_coord_cols(df) == ("Latitude", "Longitude")

    def test_case_insensitive_upper(self):
        df = pd.DataFrame({"LATITUDE": [1.0], "LONGITUDE": [2.0]})
        assert detect_coord_cols(df) == ("LATITUDE", "LONGITUDE")

    def test_dwca_pascalcase(self):
        """DecimalLatitude is the DwC-A canonical form."""
        df = pd.DataFrame({"DecimalLatitude": [1.0], "DecimalLongitude": [2.0]})
        assert detect_coord_cols(df) == ("DecimalLatitude", "DecimalLongitude")

    def test_returns_column_name_preserving_case(self):
        """When the match is case-insensitive, the original column name must be returned."""
        df = pd.DataFrame({"lAtItUdE": [1.0], "lOngItUdE": [2.0]})
        lat, lon = detect_coord_cols(df)
        assert lat == "lAtItUdE"
        assert lon == "lOngItUdE"
