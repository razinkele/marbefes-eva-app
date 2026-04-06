# SDM Knowledge Base — MARBEFES EVA

_Species Distribution Modelling: methods, libraries, evaluation, and marine applications_

**Last updated**: January 2025  
**Maintainer**: MARBEFES WP4 (Marine Research Institute, Klaipeda University)

---

## Table of Contents

1. [Overview & Method Selection Guide](#1-overview--method-selection-guide)
2. [Classical Statistical Methods](#2-classical-statistical-methods)
3. [Machine Learning Methods](#3-machine-learning-methods)
4. [Geostatistical / Spatial Interpolation Methods](#4-geostatistical--spatial-interpolation-methods)
5. [Adaptive Spatio-Temporal Methods](#5-adaptive-spatio-temporal-methods)
6. [Deep Learning Methods](#6-deep-learning-methods)
7. [Ensemble Methods](#7-ensemble-methods)
8. [Presence-Only Considerations](#8-presence-only-considerations)
9. [Uncertainty Quantification](#9-uncertainty-quantification)
10. [Evaluation Metrics](#10-evaluation-metrics)
11. [Spatial Validation](#11-spatial-validation)
12. [Marine-Specific Covariate Stack](#12-marine-specific-covariate-stack)
13. [Python Library Ecosystem](#13-python-library-ecosystem)
14. [Implementation Roadmap for EVA](#14-implementation-roadmap-for-eva)
15. [Key References](#15-key-references)

---

## 1. Overview & Method Selection Guide

### Quick decision tree

```
How many occurrence records?
├── < 20 records → Ensembles of Small Models (ESM) or MaxEnt with sparse regularization
├── 20–500 records → GAM, MaxEnt, OK/UK, RF (with regularisation), BRT
└── > 500 records → All methods valid; RF, BRT/XGBoost/LightGBM, GP, AdaSTEM

Presence-only or presence-absence?
├── Presence-only → MaxEnt (elapid), One-class SVM, HSI, BIOCLIM
└── Presence-absence → GLM, GAM, RF, BRT, XGBoost, GP, Kriging

Covariate-driven or spatially-driven?
├── Spatial structure dominates → Ordinary Kriging, GP, IDW
├── Covariates dominate → RF, BRT, GAM, GLM, MaxEnt
└── Both → Regression Kriging, GWR, AdaSTEM

Need uncertainty maps?
├── Kriging variance → OK, UK, Indicator Kriging
├── Probabilistic CI → GP (std), Conformal Prediction (MAPIE), Quantile RF
└── Ensemble spread → Std dev of ensemble predictions

Marine environment priorities:
1. BRT/XGBoost/LightGBM — best benchmark performance
2. Regression Kriging — captures spatial autocorrelation + CMEMS covariates
3. MaxEnt (elapid) — if only occurrence records, no absences
4. GAM — interpretable response curves for management applications
5. AdaSTEM — for multi-species or spatio-temporal modelling
```

---

## 2. Classical Statistical Methods

### 2.1 GLM — Generalized Linear Model

| Property | Value |
|----------|-------|
| Python | `statsmodels.formula.api.glm`, `sklearn.linear_model.LogisticRegression` |
| Response | Binary (logistic), count (Poisson), continuous (Gaussian) |
| Strength | Interpretable coefficients, well-understood statistics |
| Weakness | Linear predictor; cannot capture unimodal responses without manual polynomial terms |
| Marine use | Baseline; useful for management reports requiring statistical tables |

### 2.2 GAM — Generalized Additive Model ✓ Implemented in EVA

| Property | Value |
|----------|-------|
| Python | `pygam` (LinearGAM, LogisticGAM, GammaGAM) |
| Response | Flexible smooth functions `s(x)` per predictor |
| Strength | Captures non-linear unimodal habitat responses without overfitting |
| Weakness | No interactions (unless manually specified with `te(x,y)`) |
| Marine use | **Excellent** for SST/salinity/depth response curves |

```python
from pygam import LogisticGAM, s
gam = LogisticGAM(s(0) + s(1) + s(2))
gam.fit(X_train, y_train)
# Response curves:
XX = gam.generate_X_grid(term=0)
pdep, confi = gam.partial_dependence(term=0, X=XX, width=0.95)
```

### 2.3 MaxEnt ★ Top recommendation for presence-only

| Property | Value |
|----------|-------|
| Python | `elapid.MaxentModel` (pip install elapid) |
| Java | MaxEnt 3.4.4 binary (AMNH) |
| Strength | Maximum entropy principle; excellent regularization prevents overfitting; handles complex feature transformations (hinge, product, threshold) |
| Weakness | Requires background points; sensitive to sampling bias |
| Marine use | **Excellent** for sparse occurrence records from EMODnet Biology / GBIF |
| Citation | Phillips et al. 2006 *Ecol Model*; Phillips et al. 2017 *Ecography* |

```python
import elapid

# Background point sampling within study area polygon
background = elapid.sample_vector(aoi_polygon, n=10000)

# Annotate with covariates
occ_annotated = elapid.annotate(occurrences, covariate_stack)
bg_annotated  = elapid.annotate(background,  covariate_stack)

# Fit MaxEnt
model = elapid.MaxentModel()
model.fit(occ_annotated, bg_annotated)

# Predict to grid
predictions = model.predict(grid_annotated)
```

**Sampling bias correction**: Use target-group background — occurrence records of the same taxonomic group (e.g., all polychaetes) as background for modelling one polychaete species. This corrects for the spatial pattern of survey effort.

```python
background_biased = elapid.sample_bias_file(survey_raster, n=10000)
```

---

## 3. Machine Learning Methods

### 3.1 Random Forest ✓ Implemented in EVA

| Property | Value |
|----------|-------|
| Python | `sklearn.ensemble.RandomForestClassifier/Regressor` |
| Hyperparameters | `n_estimators=500, max_features='sqrt', min_samples_leaf=5` |
| Feature importance | `model.feature_importances_` (MDI) + permutation importance |
| Strength | Handles non-linearity, interactions, missing data; fast; no scaling needed |
| Weakness | Biased feature importance with correlated predictors; no built-in uncertainty |
| Marine use | **Excellent** across all taxa and response types |

**SHAP values** (preferred over Gini importance):
```python
import shap
explainer = shap.TreeExplainer(rf_model)
shap_values = explainer.shap_values(X_test)
shap.summary_plot(shap_values, X_test, feature_names=feat_names)
```

### 3.2 BRT — Boosted Regression Trees (most cited marine SDM method)

| Property | Value |
|----------|-------|
| Python | `sklearn.GradientBoostingClassifier`, `xgboost.XGBClassifier`, `lightgbm.LGBMClassifier` |
| Key hyperparams | `n_estimators=2000, learning_rate=0.01, max_depth=3-5, subsample=0.6` |
| Strength | **Best benchmark performance in marine SDM literature**; handles complex interactions; native missing value handling (XGBoost); partial dependence plots |
| Weakness | Slower training than RF; many hyperparameters |
| Marine use | **Primary recommendation** from Sequeira et al. 2018 for marine taxa |
| Citation | Elith et al. 2008 *J Anim Ecol*; Sequeira et al. 2018 *Glob Ecol Biogeogr* |

```python
import xgboost as xgb
from sklearn.model_selection import cross_val_score

model = xgb.XGBClassifier(
    n_estimators=500, learning_rate=0.05, max_depth=4,
    subsample=0.8, colsample_bytree=0.8,
    use_label_encoder=False, eval_metric='auc', tree_method='hist'
)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)], early_stopping_rounds=50)
```

### 3.3 LightGBM

| Property | Value |
|----------|-------|
| Python | `pip install lightgbm` |
| Strength | **Faster than XGBoost** on large datasets (leaf-wise growth); GPU support; handles categorical features natively |
| Weakness | Slightly more prone to overfitting on small datasets |
| Marine use | **Excellent** for large spatial grids (100k+ prediction cells) |

```python
import lightgbm as lgb
model = lgb.LGBMClassifier(
    n_estimators=1000, learning_rate=0.05,
    num_leaves=31, min_child_samples=20,
    subsample=0.8, colsample_bytree=0.8
)
```

### 3.4 SVM — Support Vector Machine

- Best for small datasets (< 500 sites) with clear class separation
- RBF kernel captures non-linearity; requires feature scaling (`StandardScaler`)
- `sklearn.svm.SVC(kernel='rbf', probability=True, C=10, gamma='scale')`
- Generally outperformed by RF/BRT on ecological data; use as ensemble member

---

## 4. Geostatistical / Spatial Interpolation Methods

### 4.1 IDW — Inverse Distance Weighting ✓ Implemented in EVA

- Pure spatial interpolation; no covariates; fast
- `power=2` (default); higher power = more local influence
- Suitable as baseline or in sparse-data areas

### 4.2 Ordinary Kriging ✓ Implemented in EVA

| Property | Value |
|----------|-------|
| Python | `pykrige.ok.OrdinaryKriging` |
| Variogram models | spherical (default), gaussian, exponential, linear, hole-effect |
| Output | `z_pred`, `sigma_sq` (kriging variance = uncertainty) |
| Strength | BLUP (Best Linear Unbiased Predictor); provides rigorous spatial uncertainty |
| Weakness | Requires sufficient data to estimate variogram (≥ 30 sites); stationary assumption |
| Marine use | **Excellent** for mapping patchy benthic data |

**Variogram selection guide**:
- Spherical: most common; finite range; flat nugget
- Gaussian: smooth variation; continuous derivatives
- Exponential: faster decay; good for irregular sampling
- Hole-effect: periodic/oscillating spatial structure (e.g., sediment ripples)
- Linear: no sill; non-stationary; avoid unless range is very large

### 4.3 Universal Kriging

```python
from pykrige.uk import UniversalKriging
uk = UniversalKriging(x, y, z,
    variogram_model='spherical',
    drift_terms=['regional_linear'])  # or functional: f(depth)
```

- Use when there is a **systematic trend** (e.g., along a depth gradient, salinity gradient)
- Separates deterministic trend from stochastic residuals

### 4.4 Regression Kriging ✓ Implemented in EVA

```python
from pykrige.rk import RegressionKriging
rk = RegressionKriging(regression_model=rf_model, method='ordinary')
rk.fit(X_covariates, coords_metric, y)
predictions = rk.predict(X_grid, grid_coords)
```

- **Best spatial-covariate hybrid method** for benthic habitat mapping
- RF/GLM models the covariate trend; OK interpolates the spatial residuals
- Equivalent to external drift kriging when drift = regression prediction

### 4.5 Indicator Kriging

- Transform continuous response to binary (exceed threshold)
- Interpolate binary values → probability map of exceedance
- Example: P(seagrass cover > 30%) across study area
- Useful for compliance mapping (WFD ecological status boundaries)

```python
z_indicator = (z > threshold).astype(float)
ok = OrdinaryKriging(x, y, z_indicator, variogram_model='spherical')
p_exceedance, sigma_sq = ok.execute('grid', xi, yi)
```

### 4.6 Gaussian Process Regression ✓ Implemented in EVA

| Property | Value |
|----------|-------|
| Python | `sklearn.gaussian_process.GaussianProcessRegressor` |
| Kernel | `RBF(length_scale=1) + WhiteKernel(noise_level=1)` |
| Output | mean prediction + std (aleatoric + epistemic uncertainty) |
| Complexity | O(n³) training; O(n²·m) prediction — limit to < 2000 training points |
| Strength | Probabilistic; handles all kernels (Matérn, periodic); equivalent to kriging |
| Weakness | Not scalable; use sparse GP (GPyTorch/GPflow) for large datasets |

**Sparse GP alternatives for large datasets**:
- `gpytorch` (pip install gpytorch): scalable GP with inducing points
- `GPflow`: TensorFlow-based GP with SVGP (stochastic variational GP)
- Both support GPU acceleration and scale to 100k+ points

### 4.7 GWR — Geographically Weighted Regression

| Property | Value |
|----------|-------|
| Python | `mgwr` (pip install mgwr); `pysal` ecosystem |
| Concept | Local regression: each location has its own set of coefficients |
| Output | Spatially-varying coefficient maps + local R² |
| Strength | Captures spatial non-stationarity: species-environment relationship may differ by sub-region |
| Weakness | Computationally expensive; needs moderate data density |
| Marine use | **Excellent** where oceanographic regimes create spatially varying responses (e.g., Atlantic vs. Mediterranean) |

```python
from mgwr.gwr import GWR
from mgwr.sel_bw import Sel_BW

# Bandwidth selection
selector = Sel_BW(coords, y, X, kernel='bisquare', fixed=False)
bw = selector.search(bw_min=2, bw_max=100)

# Fit GWR
model = GWR(coords, y, X, bw=bw, kernel='bisquare', fixed=False)
results = model.fit()
# results.params has shape (n_locations, n_predictors)
```

---

## 5. Adaptive Spatio-Temporal Methods

### 5.1 AdaSTEM (stemflow) ★ Cutting-edge recommendation

| Property | Value |
|----------|-------|
| Python | `pip install stemflow` |
| Publication | Chen et al. 2024 *JOSS*; Fink et al. 2010 *AAAI* |
| Concept | Adaptive Spatio-Temporal Ensemble Model: divides space into quadtree stixels (spatially adaptive cells), trains local RF models per stixel, aggregates predictions |
| Strength | Handles spatial heterogeneity; naturally avoids over-generalisation; handles multi-species; supports temporal covariates |
| Weakness | More complex setup; needs sufficient records per stixel |
| Marine use | **Excellent** for multi-species mapping, monitoring time series analysis, seasonal dynamics |

```python
from stemflow.model.STEM import STEM
from sklearn.ensemble import RandomForestClassifier

base_model = RandomForestClassifier(n_estimators=100, n_jobs=-1)
model = STEM(
    base_model=base_model,
    task='binary',                # or 'regression'
    grid_len_upper_bound=1.0,     # degrees; upper stixel size
    grid_len_lower_bound=0.05,    # degrees; minimum stixel size
    points_lower_threshold=50,    # min points per stixel
    Spatio1='longitude',
    Spatio2='latitude',
    temporal_start=1, temporal_end=52,  # week of year
    temporal_step=1,
    temporal_bin_interval=4
)
model.fit(X_train)  # X must include lon, lat, temporal columns
predictions = model.predict(X_test)
```

---

## 6. Deep Learning Methods

### 6.1 SINR — Spatial Implicit Neural Representation

| Property | Value |
|----------|-------|
| Publication | Cole et al. 2023 *ICML* |
| GitHub | https://github.com/elijahcole/sinr |
| Concept | Neural network that learns a continuous function mapping (lat, lon) → species presence probability. Jointly models 47k species from iNaturalist. Implicit neural representation (NeRF-style). |
| Strength | Global scale; no covariate rasters needed; handles 47k species simultaneously |
| Weakness | Training data must be global iNaturalist scale; not suitable for local fine-tuning without significant work |
| Marine use | Could provide global priors for common coastal species |

### 6.2 MALPOLON Deep-SDM Framework

| Property | Value |
|----------|-------|
| Publication | Picek et al. 2024 *arXiv:2409.18102* |
| GitHub | https://github.com/plantnet/malpolon |
| PyPI | `pip install malpolon` |
| Concept | PyTorch framework for multi-modal deep-SDM: satellite image patches + bioclimatic rasters + time series as input to CNN/ViT |
| Configuration | YAML-based; press-button examples; supports multi-GPU |
| Strength | Multimodal inputs; pretrained backbone models; handles GeoLifeClef competition data format |
| Marine use | **Potentially very valuable** if Sentinel-2 marine water quality or EMODnet bathymetric rasters used as image patches |

### 6.3 ResNet/EfficientNet on Environmental Rasters

```python
import torchgeo  # pip install torchgeo
# torchgeo provides: pretrained models for remote sensing, 
# geospatial dataset classes (Sentinel-2, Landsat, DEM, etc.),
# and spatial samplers that handle CRS reprojection
```

- Fine-tune pretrained ImageNet/remote sensing models on 64×64 environmental raster patches
- Extract patch around each occurrence/grid cell, feed through CNN
- Currently top approach in GeoLifeClef competition (2020–2024)

---

## 7. Ensemble Methods

### 7.1 Stacked Ensemble (Super-Learner)

```python
from sklearn.ensemble import StackingClassifier

estimators = [
    ('gam', GAMWrapper()),      # pygam wrapped with sklearn API
    ('rf', RandomForestClassifier(n_estimators=500)),
    ('xgb', xgb.XGBClassifier()),
    ('ok', KrigingWrapper()),
]
meta = LogisticRegression()
stacked = StackingClassifier(estimators=estimators, final_estimator=meta, cv=5)
```

### 7.2 Weighted Ensemble by TSS/AUC

```python
# After spatial CV:
tss_scores = {name: tss for name, tss in model_tss.items()}
weights = np.array([max(0, tss_scores[m]) for m in methods])
weights /= weights.sum()
ensemble_pred = sum(w * preds[m] for m, w in zip(methods, weights))
```

### 7.3 Ensembles of Small Models (ESM) — for rare species (< 20 records)

- For each pair of predictors, fit a simple bivariate GAM/GLM
- Average predictions across all bivariate models
- **Critical for rare benthic taxa** where data scarcity prevents complex model fitting
- See `enmSdmX::trainESM` in R or implement manually

---

## 8. Presence-Only Considerations

### Sampling Bias Correction

Marine biological occurrence data (EMODnet Biology, GBIF) is heavily biased toward:
- Coastal areas near ports
- Areas with intensive fisheries monitoring
- Historically surveyed stations (North Sea, Mediterranean coasts)

**Correction strategies**:
1. **Target-group background**: Use all records of the taxonomic group as background
2. **Survey effort raster**: Create kernel density raster of all surveys; sample background proportionally
3. **Spatial thinning**: 1 record per grid cell to reduce spatial clumping
4. **MESS analysis**: Multivariate Environmental Similarity Surface — flag extrapolation regions

### Pseudo-Absence Generation

When no true absences available:
1. **Random background**: Draw from study area extent
2. **Environmental stratification**: Sample background to match covariate distribution
3. **Minimum distance buffer**: Exclude background within N km of presences (assumes detection radius)

---

## 9. Uncertainty Quantification

### 9.1 Kriging Variance (already in EVA)

- σ²(x) from OK/UK/RK: distance-based uncertainty (higher away from observations)
- `sigma_sq` from pykrige; display as map

### 9.2 Gaussian Process Std (already in EVA)

- `gp.predict(X, return_std=True)` → (mean, std)
- Captures both model uncertainty and observation noise

### 9.3 Conformal Prediction (MAPIE) ★ Recommended addition

```python
from mapie.regression import MapieRegressor  # pip install mapie
from mapie.classification import MapieClassifier

# Works with any sklearn-compatible model
mapie = MapieRegressor(estimator=rf_model, method='plus', cv=10)
mapie.fit(X_train, y_train)
y_pred, y_pi = mapie.predict(X_test, alpha=0.1)  # 90% prediction interval
lower, upper = y_pi[:, 0, 0], y_pi[:, 1, 0]
uncertainty = upper - lower  # interval width as uncertainty measure
```

**Advantages of conformal prediction**:
- Distribution-free: no Gaussian assumption
- Guaranteed coverage: 90% PI contains true value at least 90% of the time
- Works with any black-box model (RF, XGBoost, neural networks)

### 9.4 Quantile Random Forest

```python
from quantile_forest import RandomForestQuantileRegressor  # pip install quantile-forest
qrf = RandomForestQuantileRegressor(n_estimators=500)
qrf.fit(X_train, y_train)
# Predict median + 90% PI
y_pred = qrf.predict(X_test, quantiles=[0.05, 0.5, 0.95])
```

### 9.5 Ensemble Spread

- Standard deviation of ensemble member predictions = uncertainty
- Cheap to compute; requires diverse ensemble members
- `uncertainty = np.std([m.predict(X) for m in models], axis=0)`

---

## 10. Evaluation Metrics

### For Presence-Absence / Continuous

| Metric | Range | Target | Notes |
|--------|-------|--------|-------|
| AUC-ROC | 0–1 | > 0.7 good, > 0.8 excellent | Threshold-independent; sensitive to prevalence |
| TSS | -1 to 1 | > 0.4 good, > 0.6 excellent | Threshold-dependent; independent of prevalence |
| Sensitivity | 0–1 | maximize | True positive rate (proportion of presences correctly predicted) |
| Specificity | 0–1 | maximize | True negative rate |
| Kappa | 0–1 | > 0.4 | Prevalence-corrected; less preferred than TSS |
| RMSE | ≥ 0 | minimize | For continuous predictions |
| R² | 0–1 | maximize | Variance explained |

### For Presence-Only (preferred)

| Metric | Notes |
|--------|-------|
| **Continuous Boyce Index (CBI)** | Pearson correlation between predicted habitat suitability and observed occurrence frequency. Range -1 to 1; > 0.5 good. **Preferred for MaxEnt/presence-only** |
| Partial ROC | Evaluates AUC only in ecologically relevant range (0.5–1.0) |
| Omission rate | Fraction of occurrences in predicted unsuitable habitat |

```python
# CBI calculation
def continuous_boyce_index(predicted, observed_suitabilities, window=0.1):
    """Hirzel et al. 2006 approach — Spearman rank correlation"""
    bins = np.arange(0, 1 + window, window)
    bin_centers = (bins[:-1] + bins[1:]) / 2
    expected = np.histogram(predicted, bins=bins)[0]
    observed = np.histogram(observed_suitabilities, bins=bins)[0]
    expected_norm = expected / expected.sum()
    observed_norm = observed / observed.sum()
    ratio = observed_norm / (expected_norm + 1e-10)
    return np.corrcoef(bin_centers, ratio)[0, 1]
```

### For Spatial Predictions (mandatory with spatial CV)

- Use **spatially blocked k-fold** cross-validation (not random)
- Report metrics with and without spatial CV to show model transferability
- **Roberts et al. 2017** *Ecography* — critical paper on spatial CV for SDM

---

## 11. Spatial Validation

### 11.1 Geographically Blocked K-Fold

```python
# Manual implementation for marine data
from sklearn.model_selection import KFold
import numpy as np

def spatial_kfold(coords, n_splits=5, buffer_km=10):
    """Assign spatial blocks based on latitude bands or custom polygons"""
    lat = coords[:, 1]
    lat_bins = np.percentile(lat, np.linspace(0, 100, n_splits + 1))
    fold_ids = np.digitize(lat, lat_bins[1:-1])
    return fold_ids
```

**Recommended tools**:
- `blockCV` (R package) — most comprehensive spatial CV implementation
- Custom checkerboard splits: divide space into N×M grid, alternate train/test
- `mlr3spatial` / `sperrorest` (R)

### 11.2 Environmental Extrapolation Check (MESS)

```python
def mess_surface(reference_env, prediction_env):
    """Multivariate Environmental Similarity Surface — Elith et al. 2010"""
    n_vars = reference_env.shape[1]
    mess_scores = np.zeros(prediction_env.shape[0])
    for j in range(n_vars):
        ref = reference_env[:, j]
        pred = prediction_env[:, j]
        p_min = np.percentile(ref, np.searchsorted(np.sort(ref), pred) / len(ref) * 100)
        # ... simplified; use full Elith 2010 formula
    return mess_scores
```

---

## 12. Marine-Specific Covariate Stack

### EMODnet / Copernicus Marine Priority Variables

| Variable | Source | Relevance |
|----------|--------|-----------|
| Bathymetry (depth) | EMODnet Bathymetry | **Critical** — fundamental niche axis |
| Substrate type (EUNIS) | EMODnet Geology WMS | **Critical** — benthic habitat |
| Sea Surface Temperature (SST) | CMEMS GLOBAL-ANALYSIS | **Critical** — physiological tolerance |
| Salinity (surface/bottom) | CMEMS GLOBAL-ANALYSIS | High — estuarine gradients |
| Bottom temperature | CMEMS | High — deep benthic species |
| Chlorophyll-a | CMEMS OCEANCOLOUR | High — primary productivity proxy |
| Mixed Layer Depth (MLD) | CMEMS | Medium — vertical mixing, upwelling |
| Current speed / shear | CMEMS | Medium — larval dispersal, suspension feeders |
| Dissolved oxygen | CMEMS SEAWATER | High — hypoxia risk |
| Nitrate / Phosphate | CMEMS BIOGEOCHEMISTRY | Medium — eutrophication |
| Net Primary Production (NPP) | CMEMS | Medium — food availability |
| Wave height (Hs) | CMEMS WAVES | Medium — physical disturbance in shallow water |
| Distance to coast | Custom (geopandas) | Medium — human disturbance proxy |
| Tidal range | OTPS model | Medium — intertidal species |
| Seabed slope | Derived from bathymetry | Low-Medium |

### Covariate Collinearity

Before modelling, assess multicollinearity:
```python
import pandas as pd
from scipy.stats import spearmanr

# Spearman correlation matrix
corr_matrix = pd.DataFrame(X).corr(method='spearman')
# Remove one of pair with |r| > 0.7
# Alternatively: VIF (variance inflation factor)
from statsmodels.stats.outliers_influence import variance_inflation_factor
vif = [variance_inflation_factor(X, i) for i in range(X.shape[1])]
# Remove features with VIF > 10
```

---

## 13. Python Library Ecosystem

### Core SDM Libraries

| Library | Install | Purpose | Maturity |
|---------|---------|---------|---------|
| `elapid` | `pip install elapid` | MaxEnt, NicheEnvelope, background sampling, zonal stats | ★★★★ JOSS 2023 |
| `stemflow` | `pip install stemflow` | AdaSTEM quadtree local models | ★★★★ JOSS 2024 |
| `pykrige` | `pip install pykrige` | Ordinary/Universal/Regression Kriging | ★★★★★ |
| `gstools` | `pip install gstools` | Advanced geostatistics, variogram fitting | ★★★★ |
| `mgwr` | `pip install mgwr` | Multiscale GWR | ★★★★ |
| `mapie` | `pip install mapie` | Conformal prediction intervals | ★★★★ |
| `quantile-forest` | `pip install quantile-forest` | Quantile RF | ★★★★ |
| `shap` | `pip install shap` | SHAP feature importance | ★★★★★ |
| `malpolon` | `pip install malpolon` | Deep-SDM PyTorch framework | ★★★ |

### Supporting Libraries

| Library | Purpose |
|---------|---------|
| `xgboost` | Gradient boosting (XGBoost) |
| `lightgbm` | Gradient boosting (LightGBM) — fast |
| `imbalanced-learn` | SMOTE oversampling for imbalanced presence/absence |
| `pysal` / `esda` | Spatial autocorrelation (Moran's I, LISA) |
| `rasterio` | Raster I/O for env covariate rasters |
| `geopandas` | Vector operations (occurrence data, polygons) |
| `torchgeo` | Geospatial PyTorch datasets + pretrained models |

### R Libraries (reference)

| Library | Purpose |
|---------|---------|
| `enmSdmX` | Full SDM suite: MaxEnt, MaxNet, BRT, GAM, GLM, NS, RF + evaluation |
| `dismo` | Classic SDM: BIOCLIM, Mahal, MaxEnt wrapper |
| `biomod2` | Ensemble SDM platform |
| `blockCV` | Spatial cross-validation |
| `CAST` | Area of applicability, spatial CV for ML |

---

## 14. Implementation Roadmap for EVA

### Currently Implemented (✓)

- IDW, GAM, Ordinary Kriging, Gaussian Process, Random Forest, Regression Kriging
- Ensemble (GAM + IDW + Kriging, configurable weights)
- Uncertainty maps (kriging variance, GP std)
- Variogram chart (interactive Plotly)
- Feature importance (RF MDI)

### Phase 2 — High Priority

| Method | Package | Effort | Impact |
|--------|---------|--------|--------|
| **XGBoost / LightGBM** | `xgboost`, `lightgbm` | Low | **Very High** — best benchmark performance |
| **Universal Kriging** | `pykrige` | Low | High — for depth/trend gradient areas |
| **SHAP explanations** | `shap` | Medium | High — replaces simple MDI feature importance |
| **MaxEnt** (elapid) | `elapid` | Medium | High — for presence-only records |
| **Spatial CV** | custom | Medium | High — prevents inflated metrics |

### Phase 3 — Medium Priority

| Method | Package | Effort | Impact |
|--------|---------|--------|--------|
| Conformal Prediction (MAPIE) | `mapie` | Low | Medium — rigorous uncertainty CI |
| GWR | `mgwr` | Medium | Medium — spatially-varying responses |
| AdaSTEM | `stemflow` | High | High — multi-species, spatio-temporal |
| Continuous Boyce Index | custom | Low | Medium — better eval for presence-only |
| Indicator Kriging | `pykrige` | Low | Medium — exceedance probability maps |
| ESM (rare species) | custom | Medium | High — for rare benthic taxa |

### Phase 4 — Research / Future

| Method | Notes |
|--------|-------|
| Sparse GP (GPyTorch) | Scale GP to large grids |
| MALPOLON / ResNet | If remote sensing imagery as covariates |
| SINR | Global priors for common coastal species |
| Bayesian NN / MC Dropout | Deep probabilistic SDM |

---

## 15. Key References

### Foundational SDM

- **Elith et al. 2006** — Comparative evaluation of SDMs for 226 species. *Ecology Letters*.
- **Phillips et al. 2006** — MaxEnt: Maximum entropy modeling of species geographic distributions. *Ecol Model*.
- **Thuiller et al. 2009** — BIOMOD — A platform for ensemble forecasting of species distributions. *Ecography*.

### Machine Learning for SDM

- **Elith, Leathwick & Hastie 2008** — A working guide to BRT. *J Anim Ecol* 77:802–813.
- **Cutler et al. 2007** — RF for classification: applications to remote sensing and ecology. *Ecology*.
- **Chen & Guestrin 2016** — XGBoost. *KDD*.
- **Ke et al. 2017** — LightGBM. *NeurIPS*.

### Geostatistical SDM

- **Cressie 1993** — Statistics for Spatial Data. John Wiley.
- **Hengl et al. 2007** — Regression Kriging as a generic framework for spatial prediction. *Comput Geosci*.
- **Rasmussen & Williams 2006** — Gaussian Processes for Machine Learning. MIT Press.

### Marine SDM Specifically

- **Sequeira et al. 2018** — Transferring marine species distribution models: insights from ocean trophic interactions. *Glob Ecol Biogeogr*.
- **Reiss et al. 2011** — Marine biodiversity and ecosystem functioning: what's the link? *J Sea Res*.
- **Guisan & Zimmermann 2000** — Predictive habitat distribution models in ecology. *Ecol Model*.

### Spatial Validation

- **Roberts et al. 2017** — Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography*.
- **Valavi et al. 2019** — blockCV: an R package for generating spatially or environmentally separated folds. *Methods Ecol Evol*.

### Uncertainty

- **Angelopoulos & Bates 2021** — A Gentle Introduction to Conformal Prediction. *arXiv:2107.07511*.
- **Meinshausen 2006** — Quantile Regression Forests. *JMLR* 7:983–999.

### Cutting-Edge (2023–2024)

- **Cole et al. 2023** — SINR: Spatial Implicit Neural Representations. *ICML 2023*.
- **Chen et al. 2024** — stemflow: A Python package for spatio-temporal modelling. *JOSS*.
- **Picek et al. 2024** — MALPOLON: A Framework for Deep Species Distribution Modeling. *arXiv:2409.18102*.
- **Exposito-Alonso et al. 2024** — Challenging the state of the art for plant identification. *PNAS*.

---

*This knowledge base is part of MARBEFES Work Package 4 — Ecological Value Assessment tool development.*  
*Horizon Europe grant agreement No. 101059218.*
