"""
MARBEFES EVA — Species Distribution Modelling (SDM) Module

Combines spatial interpolation (IDW) and Generalized Additive Models (GAM)
with EUNIS 2019, EMODnet bathymetry, substrate, and Copernicus Marine
covariates to predict species distributions over hex grid cells.

Methods
-------
- IDW       : Inverse Distance Weighting (scipy-based)
- GAM       : Generalized Additive Model via pygam
              (LinearGAM for continuous/count, LogisticGAM for presence/absence)
- Ensemble  : weighted average of IDW and GAM predictions

Workflow
--------
1. extract_covariates_at_sites()  — join sampling sites to nearest grid cell
2. prepare_features()             — encode predictors (numeric + EUNIS dummies)
3. fit_idw()                      — fit IDW interpolation model
4. fit_gam()                      — fit GAM
5. predict_grid()                 — predict for all grid cells
6. model_diagnostics()            — R², RMSE, AUC (binary), pseudo-R²
"""

from __future__ import annotations

import logging
import warnings
from typing import Literal

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree
from shapely.geometry import Point

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
ResponseType = Literal["continuous", "binary", "count"]
MethodType   = Literal["gam", "idw", "ensemble"]

# ---------------------------------------------------------------------------
# Column names recognised as EUNIS habitat (categorical)
# ---------------------------------------------------------------------------
_EUNIS_COLS = {"eunis_code", "eunis2019", "eunis_habitat", "habitat_code"}

# ---------------------------------------------------------------------------
# 1. Covariate extraction — join sites to grid cells
# ---------------------------------------------------------------------------

def extract_covariates_at_sites(
    sites_df: pd.DataFrame,
    grid_gdf: gpd.GeoDataFrame,
    lat_col: str = "lat",
    lon_col: str = "lon",
) -> pd.DataFrame:
    """
    For each sampling site, find the nearest hex grid cell and attach its
    covariate values.

    Parameters
    ----------
    sites_df  : DataFrame with lat/lon columns and response variable(s)
    grid_gdf  : GeoDataFrame with hex grid cells and covariate columns
    lat_col   : name of latitude column in sites_df
    lon_col   : name of longitude column in sites_df

    Returns
    -------
    DataFrame with original site columns plus covariate columns appended.
    Sites that fall outside the grid extent are dropped.
    """
    if lat_col not in sites_df.columns or lon_col not in sites_df.columns:
        raise ValueError(f"sites_df must have '{lat_col}' and '{lon_col}' columns")

    sites_df = sites_df.dropna(subset=[lat_col, lon_col]).copy()

    # Build GeoDataFrame of sites (WGS-84)
    sites_geom = [Point(row[lon_col], row[lat_col]) for _, row in sites_df.iterrows()]
    sites_gdf = gpd.GeoDataFrame(sites_df, geometry=sites_geom, crs="EPSG:4326")

    # Reproject both to a metric CRS for KD-tree distance (EPSG:3857)
    sites_m = sites_gdf.to_crs("EPSG:3857")
    grid_m  = grid_gdf.to_crs("EPSG:3857")

    # Centroids of hex cells
    grid_centroids = np.column_stack([
        grid_m.geometry.centroid.x,
        grid_m.geometry.centroid.y,
    ])
    site_coords = np.column_stack([
        sites_m.geometry.x,
        sites_m.geometry.y,
    ])

    tree = cKDTree(grid_centroids)
    distances, indices = tree.query(site_coords, k=1, workers=-1)

    # Covariate columns (drop geometry, cell_id, index columns)
    skip = {"geometry", "cell_id", "h3_index"}
    cov_cols = [c for c in grid_gdf.columns if c not in skip]

    matched_covs = grid_gdf.iloc[indices][cov_cols].reset_index(drop=True)
    result = pd.concat(
        [sites_df.reset_index(drop=True), matched_covs],
        axis=1,
    )
    result["_dist_to_cell_m"] = distances
    logger.info("Extracted covariates for %d sites (max dist %.0f m)", len(result), distances.max())
    return result


# ---------------------------------------------------------------------------
# 2. Feature preparation — encode predictors for model fitting
# ---------------------------------------------------------------------------

def prepare_features(
    df: pd.DataFrame,
    predictor_cols: list[str],
    response_col: str,
    response_type: ResponseType = "continuous",
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Build X (feature matrix) and y (response vector) ready for model fitting.

    Numeric columns are kept as-is (NaN rows dropped).
    EUNIS / categorical columns are one-hot encoded (drop_first=True to avoid
    perfect multicollinearity).

    Returns
    -------
    X          : ndarray, shape (n_samples, n_features)
    y          : ndarray, shape (n_samples,)
    feat_names : list of feature column names (for diagnostics)
    """
    work = df[[response_col] + predictor_cols].copy()

    # Identify categorical vs numeric predictors
    cat_cols = [c for c in predictor_cols if c.lower() in _EUNIS_COLS
                or work[c].dtype == object]
    num_cols = [c for c in predictor_cols if c not in cat_cols]

    # One-hot encode categorical columns
    if cat_cols:
        dummies = pd.get_dummies(work[cat_cols], drop_first=True, dtype=float)
        work = pd.concat([work[num_cols + [response_col]], dummies], axis=1)
        feat_cols = num_cols + list(dummies.columns)
    else:
        feat_cols = num_cols

    # Drop rows with any NaN in features or response
    work = work.dropna(subset=[response_col] + feat_cols)

    if len(work) < 5:
        raise ValueError(
            f"Only {len(work)} complete observations after dropping NaN — "
            "not enough to fit a model. Check your sampling sites and covariates."
        )

    y = work[response_col].values.astype(float)
    if response_type == "binary":
        y = (y > 0).astype(float)

    X = work[feat_cols].values.astype(float)
    return X, y, feat_cols


# ---------------------------------------------------------------------------
# 3a. IDW fitting and prediction
# ---------------------------------------------------------------------------

class IDWModel:
    """Inverse Distance Weighting interpolator."""

    def __init__(self, power: float = 2.0, n_neighbors: int = 8):
        self.power = power
        self.n_neighbors = n_neighbors
        self._tree: cKDTree | None = None
        self._train_coords: np.ndarray | None = None
        self._train_y: np.ndarray | None = None

    def fit(self, coords: np.ndarray, y: np.ndarray) -> "IDWModel":
        """coords : (n, 2) array of x, y in metric CRS."""
        self._train_coords = coords
        self._train_y = y
        self._tree = cKDTree(coords)
        return self

    def predict(self, coords: np.ndarray) -> np.ndarray:
        k = min(self.n_neighbors, len(self._train_y))
        distances, indices = self._tree.query(coords, k=k, workers=-1)
        # Avoid division by zero at exact query points
        distances = np.where(distances == 0, 1e-10, distances)
        weights = 1.0 / distances ** self.power
        weights /= weights.sum(axis=1, keepdims=True)
        return (weights * self._train_y[indices]).sum(axis=1)


def fit_idw(
    sites_df: pd.DataFrame,
    response_col: str,
    power: float = 2.0,
    n_neighbors: int = 8,
    lat_col: str = "lat",
    lon_col: str = "lon",
) -> IDWModel:
    """
    Fit an IDW model from site lat/lon and response values.
    Returns a fitted IDWModel.
    """
    coords = _sites_to_metric(sites_df, lat_col, lon_col)
    y = sites_df[response_col].values.astype(float)
    mask = ~np.isnan(y)
    model = IDWModel(power=power, n_neighbors=n_neighbors)
    model.fit(coords[mask], y[mask])
    return model


# ---------------------------------------------------------------------------
# 3b. GAM fitting
# ---------------------------------------------------------------------------

def fit_gam(
    X: np.ndarray,
    y: np.ndarray,
    response_type: ResponseType = "continuous",
    n_splines: int = 10,
) -> object:
    """
    Fit a GAM using pygam.

    Continuous / count → LinearGAM
    Binary            → LogisticGAM

    Returns the fitted pygam model.
    """
    try:
        from pygam import LinearGAM, LogisticGAM, s, f
    except ImportError:
        raise ImportError(
            "pygam is required for GAM fitting. "
            "Install it with: pip install pygam"
        )

    n_features = X.shape[1]
    # Build spline terms for all features
    terms = s(0, n_splines=n_splines)
    for i in range(1, n_features):
        terms = terms + s(i, n_splines=n_splines)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if response_type == "binary":
            model = LogisticGAM(terms).fit(X, y)
        else:
            model = LinearGAM(terms).fit(X, y)

    logger.info(
        "GAM fitted: %d obs, %d features, pseudo-R²=%.3f",
        len(y), n_features, model.statistics_["pseudo_r2"]["McFadden"],
    )
    return model


# ---------------------------------------------------------------------------
# 4. Predict over the full grid
# ---------------------------------------------------------------------------

def predict_grid(
    grid_gdf: gpd.GeoDataFrame,
    predictor_cols: list[str],
    gam_model=None,
    idw_model: IDWModel | None = None,
    method: MethodType = "ensemble",
    ensemble_weight_gam: float = 0.5,
    response_type: ResponseType = "continuous",
    lat_col: str = "lat",
    lon_col: str = "lon",
) -> pd.Series:
    """
    Predict species distribution for every grid cell.

    Returns a pd.Series aligned to grid_gdf.index with predicted values.
    Cells with missing covariates receive NaN.
    """
    # ── Prepare grid feature matrix (same encoding as training) ────────────
    work = grid_gdf[predictor_cols].copy()

    cat_cols = [c for c in predictor_cols if c.lower() in _EUNIS_COLS
                or work[c].dtype == object]
    num_cols = [c for c in predictor_cols if c not in cat_cols]

    if cat_cols:
        dummies = pd.get_dummies(work[cat_cols], drop_first=True, dtype=float)
        work = pd.concat([work[num_cols], dummies], axis=1)

    valid_mask = work.notna().all(axis=1)
    X_grid = work[valid_mask].values.astype(float)

    predictions = np.full(len(grid_gdf), np.nan)

    if method in ("gam", "ensemble") and gam_model is not None:
        gam_pred = np.full(len(grid_gdf), np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gam_pred[valid_mask.values] = gam_model.predict(X_grid)
        if response_type == "binary":
            gam_pred = np.clip(gam_pred, 0, 1)

    if method in ("idw", "ensemble") and idw_model is not None:
        # IDW uses geographic coordinates of grid cell centroids
        centroids_4326 = grid_gdf.to_crs("EPSG:3857").geometry.centroid.to_crs("EPSG:4326")
        fake_sites = pd.DataFrame({
            lat_col: centroids_4326.y,
            lon_col: centroids_4326.x,
        })
        grid_coords = _sites_to_metric(fake_sites, lat_col, lon_col)
        idw_pred = idw_model.predict(grid_coords)
        if response_type == "binary":
            idw_pred = np.clip(idw_pred, 0, 1)

    if method == "gam":
        predictions = gam_pred
    elif method == "idw":
        predictions = idw_pred
    else:  # ensemble
        w_gam = ensemble_weight_gam
        w_idw = 1.0 - w_gam
        predictions = np.where(
            np.isnan(gam_pred) | np.isnan(idw_pred),
            np.where(np.isnan(gam_pred), idw_pred, gam_pred),
            w_gam * gam_pred + w_idw * idw_pred,
        )

    return pd.Series(predictions, index=grid_gdf.index, name="sdm_prediction")


# ---------------------------------------------------------------------------
# 5. Model diagnostics
# ---------------------------------------------------------------------------

def model_diagnostics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    response_type: ResponseType = "continuous",
    feature_names: list[str] | None = None,
    gam_model=None,
) -> dict:
    """
    Compute model performance metrics.

    Returns dict with keys: r2, rmse, mae, [auc], [n_obs], [feature_importance]
    """
    from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    yt, yp = y_true[mask], y_pred[mask]

    result = {
        "n_obs": int(mask.sum()),
        "r2":   float(r2_score(yt, yp)),
        "rmse": float(np.sqrt(mean_squared_error(yt, yp))),
        "mae":  float(mean_absolute_error(yt, yp)),
    }

    if response_type == "binary":
        try:
            from sklearn.metrics import roc_auc_score
            result["auc"] = float(roc_auc_score(yt, yp))
        except Exception:
            pass

    # GAM-specific: pseudo-R² and p-values
    if gam_model is not None:
        try:
            stats = gam_model.statistics_
            result["pseudo_r2_mcfadden"] = float(
                stats.get("pseudo_r2", {}).get("McFadden", np.nan)
            )
        except Exception:
            pass

    return result


def format_diagnostics_html(diag: dict, feature_names: list[str] | None = None) -> str:
    """Render diagnostics dict as a small HTML table."""
    rows = []
    labels = {
        "n_obs": "Observations",
        "r2": "R²",
        "rmse": "RMSE",
        "mae": "MAE",
        "auc": "AUC (ROC)",
        "pseudo_r2_mcfadden": "Pseudo-R² (McFadden)",
    }
    for k, lbl in labels.items():
        if k in diag:
            v = diag[k]
            fmt = f"{v:.4f}" if isinstance(v, float) else str(v)
            rows.append(f"<tr><td><strong>{lbl}</strong></td><td>{fmt}</td></tr>")

    html = (
        '<table class="table table-sm table-bordered" style="font-size:0.85rem;">'
        "<thead><tr><th>Metric</th><th>Value</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )
    if feature_names:
        html += (
            "<p style='margin-top:8px;font-size:0.82rem;color:#555;'>"
            f"<strong>Predictors used:</strong> {', '.join(feature_names)}</p>"
        )
    return html


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sites_to_metric(
    df: pd.DataFrame, lat_col: str = "lat", lon_col: str = "lon"
) -> np.ndarray:
    """Convert lat/lon columns to EPSG:3857 metric coordinates."""
    pts = gpd.GeoDataFrame(
        geometry=[Point(row[lon_col], row[lat_col]) for _, row in df.iterrows()],
        crs="EPSG:4326",
    ).to_crs("EPSG:3857")
    return np.column_stack([pts.geometry.x, pts.geometry.y])


def available_predictor_cols(grid_gdf: gpd.GeoDataFrame) -> list[str]:
    """Return numeric and EUNIS columns available as SDM predictors."""
    skip = {"geometry", "cell_id", "h3_index", "ev_score", "ev_class", "sdm_prediction"}
    cols = []
    for c in grid_gdf.columns:
        if c in skip:
            continue
        if pd.api.types.is_numeric_dtype(grid_gdf[c]):
            cols.append(c)
        elif c.lower() in _EUNIS_COLS or grid_gdf[c].dtype == object:
            cols.append(c)
    return cols
