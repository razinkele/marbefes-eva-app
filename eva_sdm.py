"""
MARBEFES EVA — Species Distribution Modelling (SDM) Module

Combines spatial interpolation and machine-learning/geostatistical models with
EUNIS 2019, EMODnet bathymetry, substrate, and Copernicus Marine covariates to
predict species distributions over hex grid cells.

Methods
-------
- IDW                : Inverse Distance Weighting (scipy-based, pure spatial)
- Kriging (OK)       : Ordinary Kriging via pykrige (spherical/gaussian/exponential
                       variogram; returns predictions + kriging variance)
- GAM                : Generalized Additive Model via pygam
                       (LinearGAM for continuous/count, LogisticGAM for presence/absence)
- Random Forest (RF) : sklearn RandomForest — covariate-driven, non-parametric;
                       returns feature importances
- Gaussian Process   : sklearn GaussianProcessRegressor (RBF + WhiteKernel);
                       probabilistic predictions with uncertainty (std)
- Regression Kriging : pykrige RegressionKriging — RF trend + OK on residuals;
                       state-of-the-art hybrid for SDM with spatial structure
- Ensemble           : weighted average of any combination of the above

Workflow
--------
1. extract_covariates_at_sites()    — join sampling sites to nearest grid cell
2. prepare_features()               — encode predictors (numeric + EUNIS dummies)
3. fit_idw() / fit_kriging() /
   fit_gam() / fit_random_forest() /
   fit_gaussian_process() /
   fit_regression_kriging()         — fit chosen model(s)
4. predict_grid()                   — predict for all grid cells
5. model_diagnostics()              — R², RMSE, AUC (binary), pseudo-R²,
                                       feature importances
6. plot_variogram_html()            — interactive variogram Plotly chart
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
MethodType   = Literal[
    "gam", "idw", "kriging", "rf", "xgboost", "lightgbm",
    "gp", "regression_kriging", "ensemble"
]

# Variogram models supported by pykrige
VARIOGRAM_MODELS = ["spherical", "gaussian", "exponential", "linear", "power"]

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
# 3c. Ordinary Kriging (pykrige)
# ---------------------------------------------------------------------------

def fit_kriging(
    sites_df: pd.DataFrame,
    response_col: str,
    variogram_model: str = "spherical",
    lat_col: str = "lat",
    lon_col: str = "lon",
    n_closest_points: int | None = None,
    enable_ols_nugget: bool = True,
):
    """
    Fit Ordinary Kriging using pykrige.OrdinaryKriging.

    Uses metric EPSG:3857 coordinates for a meaningful variogram range.

    Parameters
    ----------
    variogram_model : 'spherical' | 'gaussian' | 'exponential' | 'linear' | 'power'
    n_closest_points : limit neighbourhood to speed up large-grid prediction

    Returns
    -------
    pykrige OrdinaryKriging instance (fitted).  Access variogram parameters via
    ``ok.variogram_model_parameters`` and empirical lags via ``ok.lags``.
    """
    try:
        from pykrige.ok import OrdinaryKriging
    except ImportError:
        raise ImportError("pykrige is required. Install: pip install pykrige")

    y = sites_df[response_col].values.astype(float)
    mask = ~np.isnan(y)
    coords_m = _sites_to_metric(sites_df, lat_col, lon_col)

    ok_kwargs: dict = dict(
        variogram_model=variogram_model,
        verbose=False,
        enable_plotting=False,
        coordinates_type="euclidean",
    )
    if n_closest_points is not None:
        ok_kwargs["n_closest_points"] = n_closest_points

    ok = OrdinaryKriging(
        coords_m[mask, 0], coords_m[mask, 1], y[mask],
        **ok_kwargs,
    )
    logger.info(
        "Ordinary Kriging fitted: %d obs, variogram=%s, params=%s",
        mask.sum(), variogram_model, ok.variogram_model_parameters,
    )
    return ok


# ---------------------------------------------------------------------------
# 3d. Random Forest
# ---------------------------------------------------------------------------

def fit_random_forest(
    X: np.ndarray,
    y: np.ndarray,
    response_type: ResponseType = "continuous",
    n_estimators: int = 200,
    max_features: float | str = "sqrt",
    random_state: int = 42,
):
    """
    Fit a Random Forest via scikit-learn.

    Returns the fitted sklearn estimator.  Feature importances are accessible
    via ``model.feature_importances_``.
    """
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

    kwargs = dict(
        n_estimators=n_estimators,
        max_features=max_features,
        n_jobs=-1,
        random_state=random_state,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if response_type == "binary":
            model = RandomForestClassifier(**kwargs).fit(X, y.astype(int))
        else:
            model = RandomForestRegressor(**kwargs).fit(X, y)

    logger.info(
        "Random Forest fitted: %d obs, %d trees, %d features",
        len(y), n_estimators, X.shape[1],
    )
    return model


# ---------------------------------------------------------------------------
# 3e-ext. XGBoost
# ---------------------------------------------------------------------------

def fit_xgboost(
    X: np.ndarray,
    y: np.ndarray,
    response_type: ResponseType = "continuous",
    n_estimators: int = 300,
    learning_rate: float = 0.05,
    max_depth: int = 4,
    subsample: float = 0.8,
    random_state: int = 42,
):
    """
    Fit an XGBoost model (XGBClassifier / XGBRegressor).

    XGBoost is consistently among the best-performing methods in marine SDM
    benchmarks (Sequeira et al. 2018). Handles missing values natively.

    Returns the fitted xgboost estimator with ``feature_importances_`` attribute.
    """
    try:
        from xgboost import XGBClassifier, XGBRegressor
    except ImportError:
        raise ImportError("xgboost is required. Install: pip install xgboost")

    common = dict(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        subsample=subsample,
        colsample_bytree=0.8,
        random_state=random_state,
        n_jobs=-1,
        verbosity=0,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if response_type == "binary":
            model = XGBClassifier(
                use_label_encoder=False, eval_metric="logloss", **common
            ).fit(X, y.astype(int))
        else:
            model = XGBRegressor(**common).fit(X, y)

    logger.info(
        "XGBoost fitted: %d obs, %d estimators, %d features",
        len(y), n_estimators, X.shape[1],
    )
    return model


# ---------------------------------------------------------------------------
# 3e-ext2. LightGBM
# ---------------------------------------------------------------------------

def fit_lightgbm(
    X: np.ndarray,
    y: np.ndarray,
    response_type: ResponseType = "continuous",
    n_estimators: int = 300,
    learning_rate: float = 0.05,
    num_leaves: int = 31,
    subsample: float = 0.8,
    random_state: int = 42,
):
    """
    Fit a LightGBM model (LGBMClassifier / LGBMRegressor).

    LightGBM uses leaf-wise tree growth — faster than XGBoost on large
    datasets and large spatial prediction grids.

    Returns the fitted lightgbm estimator with ``feature_importances_`` attribute.
    """
    try:
        from lightgbm import LGBMClassifier, LGBMRegressor
    except ImportError:
        raise ImportError("lightgbm is required. Install: pip install lightgbm")

    common = dict(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        num_leaves=num_leaves,
        subsample=subsample,
        colsample_bytree=0.8,
        min_child_samples=10,
        random_state=random_state,
        n_jobs=-1,
        verbose=-1,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if response_type == "binary":
            model = LGBMClassifier(**common).fit(X, y.astype(int))
        else:
            model = LGBMRegressor(**common).fit(X, y)

    logger.info(
        "LightGBM fitted: %d obs, %d leaves, %d features",
        len(y), num_leaves, X.shape[1],
    )
    return model



def fit_gaussian_process(
    X: np.ndarray,
    y: np.ndarray,
    response_type: ResponseType = "continuous",
    length_scale_bounds: tuple = (1e-3, 1e3),
    noise_level_bounds: tuple = (1e-5, 1e1),
    n_restarts: int = 3,
):
    """
    Fit a Gaussian Process Regressor (sklearn).

    Kernel: RBF + WhiteKernel (noise).  This is mathematically equivalent to
    Simple Kriging with a squared-exponential variogram.

    Returns predictions AND standard deviation via ``model.predict(X, return_std=True)``.

    .. warning::
        Fitting is O(n³) — for n > 2000 sampling sites expect several minutes.
        Prediction on large grids is O(n² × m) — use sparingly.
    """
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, WhiteKernel
    from sklearn.preprocessing import StandardScaler

    # Scale features — crucial for GP
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kernel = (
        RBF(length_scale=1.0, length_scale_bounds=length_scale_bounds)
        + WhiteKernel(noise_level=1.0, noise_level_bounds=noise_level_bounds)
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gpr = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=n_restarts,
            normalize_y=True,
            random_state=42,
        ).fit(X_scaled, y)

    # Attach scaler so predict_grid can transform grid features
    gpr._eva_scaler = scaler

    logger.info(
        "Gaussian Process fitted: %d obs, %d features, kernel=%s",
        len(y), X.shape[1], gpr.kernel_,
    )
    return gpr


# ---------------------------------------------------------------------------
# 3f. Regression Kriging (pykrige)
# ---------------------------------------------------------------------------

def fit_regression_kriging(
    X: np.ndarray,
    y: np.ndarray,
    sites_df: pd.DataFrame,
    variogram_model: str = "spherical",
    n_estimators: int = 200,
    lat_col: str = "lat",
    lon_col: str = "lon",
):
    """
    Regression Kriging: Random Forest trend + Ordinary Kriging on residuals.

    Uses ``pykrige.rk.RegressionKriging`` which:
    1. Fits a sklearn estimator (RF) on covariates X → ŷ
    2. Kriging-interpolates the residuals (y - ŷ) at unsampled locations
    3. Final prediction = RF(X) + OK(residuals)

    This is the most powerful SDM method when both covariate information and
    spatial autocorrelation are present.

    Returns the fitted ``pykrige.rk.RegressionKriging`` instance.
    """
    try:
        from pykrige.rk import RegressionKriging
    except ImportError:
        raise ImportError("pykrige is required. Install: pip install pykrige")
    from sklearn.ensemble import RandomForestRegressor

    coords_m = _sites_to_metric(sites_df, lat_col, lon_col)
    mask = ~np.isnan(y)

    rf = RandomForestRegressor(
        n_estimators=n_estimators, n_jobs=-1, random_state=42
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rk = RegressionKriging(
            regression_model=rf,
            method="ordinary",
            variogram_model=variogram_model,
            verbose=False,
        )
        rk.fit(X[mask], coords_m[mask], y[mask])

    logger.info(
        "Regression Kriging fitted: %d obs, variogram=%s",
        mask.sum(), variogram_model,
    )
    return rk


# ---------------------------------------------------------------------------
# 4. Predict over the full grid
# ---------------------------------------------------------------------------

def predict_grid(
    grid_gdf: gpd.GeoDataFrame,
    predictor_cols: list[str],
    gam_model=None,
    idw_model: IDWModel | None = None,
    kriging_model=None,
    rf_model=None,
    xgb_model=None,
    lgbm_model=None,
    gp_model=None,
    rk_model=None,
    method: MethodType = "ensemble",
    ensemble_weights: dict | None = None,
    response_type: ResponseType = "continuous",
    lat_col: str = "lat",
    lon_col: str = "lon",
) -> tuple[pd.Series, pd.Series | None]:
    """
    Predict species distribution for every grid cell.

    Parameters
    ----------
    grid_gdf        : hex grid GeoDataFrame with covariate columns
    predictor_cols  : list of covariate column names (used by covariate-based models)
    gam_model       : fitted pygam model
    idw_model       : fitted IDWModel
    kriging_model   : fitted pykrige OrdinaryKriging
    rf_model        : fitted sklearn RandomForest estimator
    xgb_model       : fitted xgboost XGBClassifier/XGBRegressor
    lgbm_model      : fitted lightgbm LGBMClassifier/LGBMRegressor
    gp_model        : fitted sklearn GaussianProcessRegressor (must have _eva_scaler)
    rk_model        : fitted pykrige RegressionKriging
    method          : which model to use for final predictions
    ensemble_weights: dict mapping method names to weights, e.g.
                      {"gam": 0.3, "rf": 0.4, "kriging": 0.3}
                      Defaults to equal weights for models that are provided.
    response_type   : 'continuous' | 'binary' | 'count'

    Returns
    -------
    (predictions, uncertainty)
    - predictions : pd.Series aligned to grid_gdf.index
    - uncertainty : pd.Series of kriging variance or GP std (None if unavailable)
    """
    n = len(grid_gdf)
    nan_series = pd.Series(np.full(n, np.nan), index=grid_gdf.index)

    # ── Grid centroids in metric (for spatial models) ───────────────────────
    centroids_3857 = grid_gdf.to_crs("EPSG:3857").geometry.centroid
    centroids_4326 = centroids_3857.to_crs("EPSG:4326")
    fake_sites_df = pd.DataFrame({
        lat_col: centroids_4326.y.values,
        lon_col: centroids_4326.x.values,
    })
    grid_coords_m = _sites_to_metric(fake_sites_df, lat_col, lon_col)

    # ── Grid feature matrix (for covariate-based models) ────────────────────
    work = grid_gdf[predictor_cols].copy() if predictor_cols else pd.DataFrame(index=grid_gdf.index)
    cat_cols = [c for c in predictor_cols if c.lower() in _EUNIS_COLS
                or work[c].dtype == object]
    num_cols = [c for c in predictor_cols if c not in cat_cols]
    if cat_cols:
        dummies = pd.get_dummies(work[cat_cols], drop_first=True, dtype=float)
        work = pd.concat([work[num_cols], dummies], axis=1)
    valid_mask = work.notna().all(axis=1) if not work.empty else pd.Series(True, index=grid_gdf.index)
    X_grid = work[valid_mask].values.astype(float) if not work.empty else np.empty((valid_mask.sum(), 0))

    collected: dict[str, np.ndarray] = {}
    uncertainty_arr: np.ndarray | None = None

    # ── Per-method predictions ────────────────────────────────────────────────
    def _fill(arr_or_series, valid=None):
        out = np.full(n, np.nan)
        idx = valid_mask.values if valid is None else valid
        if hasattr(arr_or_series, "values"):
            out[idx] = arr_or_series.values
        else:
            out[idx] = arr_or_series
        return out

    # GAM
    if gam_model is not None and predictor_cols:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gam_raw = gam_model.predict(X_grid)
        arr = np.full(n, np.nan)
        arr[valid_mask.values] = gam_raw
        if response_type == "binary":
            arr = np.clip(arr, 0, 1)
        collected["gam"] = arr

    # IDW
    if idw_model is not None:
        idw_raw = idw_model.predict(grid_coords_m)
        if response_type == "binary":
            idw_raw = np.clip(idw_raw, 0, 1)
        collected["idw"] = idw_raw

    # Ordinary Kriging
    if kriging_model is not None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            z_ok, ss_ok = kriging_model.execute(
                "points",
                grid_coords_m[:, 0],
                grid_coords_m[:, 1],
            )
        ok_arr = np.asarray(z_ok).ravel().astype(float)
        if response_type == "binary":
            ok_arr = np.clip(ok_arr, 0, 1)
        collected["kriging"] = ok_arr
        uncertainty_arr = np.asarray(ss_ok).ravel().astype(float)  # kriging variance

    # Random Forest
    if rf_model is not None and predictor_cols:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from sklearn.ensemble import RandomForestClassifier
            if isinstance(rf_model, RandomForestClassifier):
                rf_raw = rf_model.predict_proba(X_grid)[:, 1]
            else:
                rf_raw = rf_model.predict(X_grid)
        arr = np.full(n, np.nan)
        arr[valid_mask.values] = rf_raw
        collected["rf"] = arr

    # XGBoost
    if xgb_model is not None and predictor_cols:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                from xgboost import XGBClassifier
                if isinstance(xgb_model, XGBClassifier):
                    xgb_raw = xgb_model.predict_proba(X_grid)[:, 1]
                else:
                    xgb_raw = xgb_model.predict(X_grid)
            except ImportError:
                xgb_raw = xgb_model.predict(X_grid)
        arr = np.full(n, np.nan)
        arr[valid_mask.values] = xgb_raw
        collected["xgboost"] = arr

    # LightGBM
    if lgbm_model is not None and predictor_cols:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                from lightgbm import LGBMClassifier
                if isinstance(lgbm_model, LGBMClassifier):
                    lgbm_raw = lgbm_model.predict_proba(X_grid)[:, 1]
                else:
                    lgbm_raw = lgbm_model.predict(X_grid)
            except ImportError:
                lgbm_raw = lgbm_model.predict(X_grid)
        arr = np.full(n, np.nan)
        arr[valid_mask.values] = lgbm_raw
        collected["lightgbm"] = arr


    if gp_model is not None and predictor_cols:
        scaler = getattr(gp_model, "_eva_scaler", None)
        X_sc = scaler.transform(X_grid) if scaler is not None else X_grid
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gp_mean, gp_std = gp_model.predict(X_sc, return_std=True)
        arr = np.full(n, np.nan)
        std_arr = np.full(n, np.nan)
        arr[valid_mask.values] = gp_mean
        std_arr[valid_mask.values] = gp_std
        if response_type == "binary":
            arr = np.clip(arr, 0, 1)
        collected["gp"] = arr
        if uncertainty_arr is None:   # prefer kriging variance if also present
            uncertainty_arr = std_arr

    # Regression Kriging
    if rk_model is not None and predictor_cols:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rk_raw = rk_model.predict(X_grid, grid_coords_m)
        arr = np.full(n, np.nan)
        arr[valid_mask.values] = rk_raw
        if response_type == "binary":
            arr = np.clip(arr, 0, 1)
        collected["regression_kriging"] = arr

    # ── Combine ───────────────────────────────────────────────────────────────
    if method == "ensemble":
        if not collected:
            return nan_series, None
        if ensemble_weights:
            keys = [k for k in ensemble_weights if k in collected]
            weights = np.array([ensemble_weights[k] for k in keys], dtype=float)
        else:
            keys = list(collected.keys())
            weights = np.ones(len(keys))
        weights = weights / weights.sum()

        stack = np.column_stack([collected[k] for k in keys])   # (n, models)
        # Per-cell: ignore NaN models
        final = np.full(n, np.nan)
        for i in range(n):
            row = stack[i]
            valid_idx = ~np.isnan(row)
            if valid_idx.any():
                w = weights[valid_idx]
                final[i] = (row[valid_idx] * w / w.sum()).sum()
        predictions = pd.Series(final, index=grid_gdf.index, name="sdm_prediction")
    else:
        arr = collected.get(method)
        if arr is None:
            return nan_series, None
        predictions = pd.Series(arr, index=grid_gdf.index, name="sdm_prediction")

    unc_series = (
        pd.Series(uncertainty_arr, index=grid_gdf.index, name="sdm_uncertainty")
        if uncertainty_arr is not None else None
    )
    return predictions, unc_series


# ---------------------------------------------------------------------------
# 5. Model diagnostics
# ---------------------------------------------------------------------------

def model_diagnostics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    response_type: ResponseType = "continuous",
    feature_names: list[str] | None = None,
    gam_model=None,
    rf_model=None,
    xgb_model=None,
    lgbm_model=None,
) -> dict:
    """
    Compute model performance metrics.

    Returns dict with keys: r2, rmse, mae, [auc], [n_obs],
    [feature_importances], [pseudo_r2_mcfadden]
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

    # GAM-specific: pseudo-R²
    if gam_model is not None:
        try:
            stats = gam_model.statistics_
            result["pseudo_r2_mcfadden"] = float(
                stats.get("pseudo_r2", {}).get("McFadden", np.nan)
            )
        except Exception:
            pass

    # Random Forest: feature importances
    if rf_model is not None and feature_names is not None:
        try:
            importances = rf_model.feature_importances_
            result["feature_importances"] = dict(zip(feature_names, importances.tolist()))
            result["feature_importance_model"] = "Random Forest"
        except Exception:
            pass

    # XGBoost: feature importances
    if xgb_model is not None and feature_names is not None and "feature_importances" not in result:
        try:
            importances = xgb_model.feature_importances_
            result["feature_importances"] = dict(zip(feature_names, importances.tolist()))
            result["feature_importance_model"] = "XGBoost"
        except Exception:
            pass

    # LightGBM: feature importances
    if lgbm_model is not None and feature_names is not None and "feature_importances" not in result:
        try:
            importances = lgbm_model.feature_importances_ / (lgbm_model.feature_importances_.sum() + 1e-10)
            result["feature_importances"] = dict(zip(feature_names, importances.tolist()))
            result["feature_importance_model"] = "LightGBM"
        except Exception:
            pass

    return result


def format_diagnostics_html(diag: dict, feature_names: list[str] | None = None) -> str:
    """Render diagnostics dict as a small HTML table, including feature importances."""
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

    # Feature importance bar (RF / XGBoost / LightGBM)
    fi = diag.get("feature_importances")
    if fi:
        fi_model_label = diag.get("feature_importance_model", "Model")
        sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)
        bars = "".join(
            f"<tr><td style='font-size:0.78rem'>{n}</td>"
            f"<td><div style='background:#4a90d9;height:14px;width:{v*100:.1f}%;border-radius:3px'></div></td>"
            f"<td style='font-size:0.78rem'>{v:.3f}</td></tr>"
            for n, v in sorted_fi[:15]
        )
        html += (
            f"<p style='margin-top:10px'><strong>Feature Importances ({fi_model_label})</strong></p>"
            '<table class="table table-sm" style="font-size:0.82rem;">'
            "<thead><tr><th>Feature</th><th>Importance</th><th>Value</th></tr></thead>"
            f"<tbody>{bars}</tbody></table>"
        )

    return html


def plot_variogram_html(
    kriging_model,
    title: str = "Variogram",
    height: int = 350,
) -> str:
    """
    Generate an interactive Plotly HTML chart showing the empirical variogram
    points and the fitted variogram model curve.

    Parameters
    ----------
    kriging_model : fitted pykrige OrdinaryKriging
    title         : chart title
    height        : chart height in pixels

    Returns
    -------
    HTML string with embedded Plotly chart (no external dependencies).
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        return "<p>plotly is required for variogram plots.</p>"

    # Empirical variogram from pykrige
    lags      = np.asarray(kriging_model.lags)
    semivar   = np.asarray(kriging_model.semivariance)
    n_pts     = np.asarray(kriging_model.variogram_model_parameters)

    # Fitted variogram curve
    lags_fine = np.linspace(0, lags.max() * 1.05, 200)
    fitted_sv = kriging_model.variogram_function(
        kriging_model.variogram_model_parameters, lags_fine
    )

    vmp = kriging_model.variogram_model_parameters
    param_labels = {
        "spherical":   ["sill", "range", "nugget"],
        "gaussian":    ["sill", "range", "nugget"],
        "exponential": ["sill", "range", "nugget"],
        "linear":      ["slope", "nugget"],
        "power":       ["scale", "exponent", "nugget"],
    }
    param_keys = param_labels.get(kriging_model.variogram_model, [])
    param_str = "  |  ".join(
        f"{k}={v:.4g}" for k, v in zip(param_keys, vmp)
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=lags / 1000, y=semivar,
        mode="markers",
        marker=dict(size=8, color="#4a90d9"),
        name="Empirical",
    ))
    fig.add_trace(go.Scatter(
        x=lags_fine / 1000, y=fitted_sv,
        mode="lines",
        line=dict(color="#e05c5c", width=2),
        name=f"Fitted ({kriging_model.variogram_model})",
    ))
    fig.update_layout(
        title=dict(text=f"{title}<br><sup>{param_str}</sup>", font=dict(size=13)),
        xaxis_title="Lag distance (km)",
        yaxis_title="Semivariance",
        height=height,
        margin=dict(l=40, r=20, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="#f9f9f9",
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


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
