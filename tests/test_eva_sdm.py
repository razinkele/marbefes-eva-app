"""Tests for eva_sdm — Species Distribution Modelling module."""

import numpy as np
import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import Polygon, Point

import eva_sdm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_hex_grid(n=20, with_covariates=True):
    """Create a synthetic hex-like grid GeoDataFrame."""
    rows = []
    for i in range(n):
        lat = 54.0 + (i % 5) * 0.05
        lon = 21.0 + (i // 5) * 0.05
        geom = Point(lon, lat).buffer(0.02, resolution=6)
        row = {"geometry": geom, "cell_id": i}
        if with_covariates:
            row["depth_m"] = float(10 + i * 2)
            row["sst_mean_c"] = float(15.0 + i * 0.3)
            row["eunis_code"] = "A5" if i % 2 == 0 else "A3"
        rows.append(row)
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    return gdf


def _make_sites(n=15, with_response=True):
    """Create synthetic sampling sites DataFrame."""
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "lat": 54.0 + rng.uniform(0, 0.25, n),
        "lon": 21.0 + rng.uniform(0, 0.20, n),
    })
    if with_response:
        df["abundance"] = rng.uniform(0, 100, n)
        df["presence"] = (df["abundance"] > 50).astype(int)
    return df


# ---------------------------------------------------------------------------
# extract_covariates_at_sites
# ---------------------------------------------------------------------------

class TestExtractCovariates:
    def test_returns_merged_dataframe(self):
        grid = _make_hex_grid(20)
        sites = _make_sites(10)
        result = eva_sdm.extract_covariates_at_sites(sites, grid)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 10
        assert "depth_m" in result.columns
        assert "sst_mean_c" in result.columns

    def test_dist_column_present(self):
        grid = _make_hex_grid(20)
        sites = _make_sites(5)
        result = eva_sdm.extract_covariates_at_sites(sites, grid)
        assert "_dist_to_cell_m" in result.columns
        assert (result["_dist_to_cell_m"] >= 0).all()

    def test_missing_lat_lon_raises(self):
        grid = _make_hex_grid(10)
        bad_sites = pd.DataFrame({"x": [54.0], "y": [21.0]})
        with pytest.raises(ValueError, match="lat"):
            eva_sdm.extract_covariates_at_sites(bad_sites, grid)

    def test_drops_nan_coordinates(self):
        grid = _make_hex_grid(10)
        sites = _make_sites(5)
        sites.loc[2, "lat"] = np.nan
        result = eva_sdm.extract_covariates_at_sites(sites, grid)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# prepare_features
# ---------------------------------------------------------------------------

class TestPrepareFeatures:
    def test_numeric_only(self):
        grid = _make_hex_grid(20)
        sites = _make_sites(15)
        sites_cov = eva_sdm.extract_covariates_at_sites(sites, grid)
        X, y, names = eva_sdm.prepare_features(
            sites_cov, ["depth_m", "sst_mean_c"], "abundance"
        )
        assert X.shape[1] == 2
        assert len(y) == len(X)
        assert "depth_m" in names

    def test_categorical_encoding(self):
        grid = _make_hex_grid(20)
        sites = _make_sites(15)
        sites_cov = eva_sdm.extract_covariates_at_sites(sites, grid)
        X, y, names = eva_sdm.prepare_features(
            sites_cov, ["depth_m", "eunis_code"], "abundance"
        )
        # eunis_code gets one-hot encoded → more than 2 features
        assert X.shape[1] >= 2
        assert not np.isnan(X).any()

    def test_binary_response_clipped(self):
        grid = _make_hex_grid(20)
        sites = _make_sites(15)
        sites_cov = eva_sdm.extract_covariates_at_sites(sites, grid)
        X, y, _ = eva_sdm.prepare_features(
            sites_cov, ["depth_m"], "abundance", response_type="binary"
        )
        assert set(y).issubset({0.0, 1.0})

    def test_too_few_obs_raises(self):
        df = pd.DataFrame({"y": [1.0, 2.0], "x": [0.5, 0.6]})
        with pytest.raises(ValueError, match="enough"):
            eva_sdm.prepare_features(df, ["x"], "y")


# ---------------------------------------------------------------------------
# IDW model
# ---------------------------------------------------------------------------

class TestIDW:
    def test_fit_predict_roundtrip(self):
        rng = np.random.default_rng(0)
        coords = rng.uniform(0, 100, (30, 2))
        y = rng.uniform(0, 50, 30)
        model = eva_sdm.IDWModel(power=2, n_neighbors=5)
        model.fit(coords, y)
        preds = model.predict(coords[:5])
        assert preds.shape == (5,)
        assert not np.isnan(preds).any()

    def test_at_exact_training_point(self):
        coords = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]])
        y = np.array([1.0, 2.0, 3.0])
        model = eva_sdm.IDWModel(power=2, n_neighbors=3)
        model.fit(coords, y)
        preds = model.predict(np.array([[0.0, 0.0]]))
        # At exact training point, prediction should be very close to true value
        assert abs(preds[0] - 1.0) < 0.1

    def test_fit_idw_from_sites(self):
        grid = _make_hex_grid(20)
        sites = _make_sites(15)
        sites_cov = eva_sdm.extract_covariates_at_sites(sites, grid)
        model = eva_sdm.fit_idw(sites_cov, "abundance")
        assert model._tree is not None


# ---------------------------------------------------------------------------
# GAM model
# ---------------------------------------------------------------------------

class TestGAM:
    def test_fit_linear_gam(self):
        rng = np.random.default_rng(1)
        X = rng.uniform(0, 10, (50, 2))
        y = X[:, 0] * 2 + rng.normal(0, 0.5, 50)
        model = eva_sdm.fit_gam(X, y, response_type="continuous", n_splines=6)
        assert model is not None
        preds = model.predict(X)
        assert preds.shape == (50,)

    def test_fit_logistic_gam(self):
        rng = np.random.default_rng(2)
        X = rng.uniform(0, 5, (50, 1))
        y = (X[:, 0] > 2.5).astype(float)
        model = eva_sdm.fit_gam(X, y, response_type="binary", n_splines=5)
        preds = model.predict(X)
        assert ((preds >= 0) & (preds <= 1)).all()


# ---------------------------------------------------------------------------
# predict_grid
# ---------------------------------------------------------------------------

class TestPredictGrid:
    def test_idw_prediction_shape(self):
        grid = _make_hex_grid(20)
        sites = _make_sites(15)
        sites_cov = eva_sdm.extract_covariates_at_sites(sites, grid)
        idw = eva_sdm.fit_idw(sites_cov, "abundance")
        preds = eva_sdm.predict_grid(
            grid, ["depth_m", "sst_mean_c"],
            idw_model=idw, method="idw"
        )
        assert len(preds) == len(grid)

    def test_gam_prediction_shape(self):
        grid = _make_hex_grid(20)
        sites = _make_sites(15)
        sites_cov = eva_sdm.extract_covariates_at_sites(sites, grid)
        X, y, feat_names = eva_sdm.prepare_features(
            sites_cov, ["depth_m", "sst_mean_c"], "abundance"
        )
        gam = eva_sdm.fit_gam(X, y, n_splines=5)
        preds = eva_sdm.predict_grid(
            grid, ["depth_m", "sst_mean_c"],
            gam_model=gam, method="gam"
        )
        assert len(preds) == len(grid)

    def test_ensemble_no_nan_where_both_valid(self):
        grid = _make_hex_grid(20)
        sites = _make_sites(15)
        sites_cov = eva_sdm.extract_covariates_at_sites(sites, grid)
        idw = eva_sdm.fit_idw(sites_cov, "abundance")
        X, y, _ = eva_sdm.prepare_features(
            sites_cov, ["depth_m", "sst_mean_c"], "abundance"
        )
        gam = eva_sdm.fit_gam(X, y, n_splines=5)
        preds = eva_sdm.predict_grid(
            grid, ["depth_m", "sst_mean_c"],
            gam_model=gam, idw_model=idw, method="ensemble"
        )
        assert not preds.isna().all()


# ---------------------------------------------------------------------------
# model_diagnostics
# ---------------------------------------------------------------------------

class TestDiagnostics:
    def test_continuous_metrics(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_pred = y_true + 0.1
        diag = eva_sdm.model_diagnostics(y_true, y_pred)
        assert "r2" in diag
        assert "rmse" in diag
        assert diag["r2"] > 0.99

    def test_binary_auc(self):
        y_true = np.array([0, 0, 1, 1, 1])
        y_pred = np.array([0.1, 0.2, 0.8, 0.9, 0.7])
        diag = eva_sdm.model_diagnostics(y_true, y_pred, response_type="binary")
        assert "auc" in diag
        assert diag["auc"] > 0.9

    def test_format_html(self):
        diag = {"n_obs": 50, "r2": 0.85, "rmse": 2.3}
        html = eva_sdm.format_diagnostics_html(diag, ["depth_m", "sst_mean_c"])
        assert "<table" in html
        assert "R²" in html
        assert "depth_m" in html


# ---------------------------------------------------------------------------
# available_predictor_cols
# ---------------------------------------------------------------------------

class TestAvailablePredictors:
    def test_returns_numeric_and_eunis(self):
        grid = _make_hex_grid(10)
        cols = eva_sdm.available_predictor_cols(grid)
        assert "depth_m" in cols
        assert "sst_mean_c" in cols
        assert "eunis_code" in cols
        assert "geometry" not in cols
        assert "cell_id" not in cols
