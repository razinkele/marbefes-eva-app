"""
MARBEFES EVA — Local Data SDM Analysis Pipeline

Reusable infrastructure for analyzing any local species/habitat dataset:
  1. Load data (CSV or DwC-A)
  2. Generate spatial grid
  3. Fetch environmental covariates (EMODnet + CMEMS)
  4. Run predictor comparison (env vs EUNIS vs combined, multiple methods)
  5. Multi-species analysis across prevalence gradient
  6. Generate Markdown report with tables and conclusions

Usage:
    # Analyse a DwC-A archive
    python -m scripts.sdm_analyse --input data/dwca-macrosoft-v2.1.zip

    # Analyse a CSV (must have lat, lon columns + species columns)
    python -m scripts.sdm_analyse --input my_data.csv

    # Customise analysis
    python -m scripts.sdm_analyse --input data.csv \\
        --species "Amphiura chiajei" "Aponuphis brementi" \\
        --methods rf kriging regression_kriging \\
        --h3-res 7 --skip-cmems \\
        --output results/my_analysis

    # Use all species above a prevalence threshold
    python -m scripts.sdm_analyse --input data.csv --min-prevalence 0.1

    # Quick run: env-only RF, no CMEMS
    python -m scripts.sdm_analyse --input data.csv --quick
"""

from __future__ import annotations

import argparse
import datetime
import getpass
import json
import logging
import os
import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.model_selection import cross_val_predict
from sklearn.ensemble import RandomForestRegressor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dwca_reader
import eva_hexgrid
import eva_eunis_wms
import eva_sdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sdm_analyse")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pykrige")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _align_valid_for_residuals(
    sites_cov: pd.DataFrame, cols: list[str], species_col: str
) -> pd.DataFrame:
    """Return rows of ``sites_cov`` that survive NaN-dropping on both the
    response column (``species_col``) and the numeric predictor columns.

    Matches the row set that ``eva_sdm.prepare_features`` would keep:
    numeric-only predictor filtering, plus exclusion of columns that are
    entirely NaN (``prepare_features`` drops those from its dropna subset
    at eva_sdm.py:173-180).
    """
    numeric = [c for c in cols if pd.api.types.is_numeric_dtype(sites_cov[c])]
    numeric = [c for c in numeric if not sites_cov[c].isna().all()]
    return sites_cov.dropna(subset=numeric + [species_col]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def load_input(path: str) -> tuple[pd.DataFrame, dict]:
    """
    Load input data from CSV or DwC-A archive.

    Returns (sites_df, info) where sites_df has lat, lon, and species columns.
    info contains: n_sites, n_species, species_list, source_type, value_type.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    if p.suffix == ".zip" and dwca_reader.is_dwca_zip(str(p)):
        logger.info("Loading DwC-A archive: %s", p.name)
        df, info = dwca_reader.read_dwca_for_sdm(str(p), value="auto")
        return df, info

    if p.suffix in (".csv", ".tsv", ".txt"):
        logger.info("Loading CSV: %s", p.name)
        sep = "\t" if p.suffix == ".tsv" else ","
        df = pd.read_csv(str(p), sep=sep)

        # Find lat/lon columns
        lat_col = _find_col(df, ["lat", "latitude", "decimallatitude", "y"])
        lon_col = _find_col(df, ["lon", "longitude", "decimallongitude", "x"])
        if lat_col is None or lon_col is None:
            raise ValueError(
                "CSV must contain latitude/longitude columns. "
                "Expected: lat/lon, latitude/longitude, or decimalLatitude/decimalLongitude"
            )
        df = df.rename(columns={lat_col: "lat", lon_col: "lon"})

        meta_cols = {"lat", "lon", "eventid", "locationid", "site_id", "station",
                     "date", "depth", "geometry"}
        species_cols = [c for c in df.columns
                        if c.lower() not in meta_cols
                        and pd.api.types.is_numeric_dtype(df[c])]

        info = {
            "source_type": "csv",
            "value_type": "auto",
            "n_sites": len(df),
            "n_species": len(species_cols),
            "species_list": species_cols,
            "has_abundance": any(df[c].max() > 1 for c in species_cols if df[c].notna().any()),
        }
        return df, info

    raise ValueError(f"Unsupported file type: {p.suffix}. Use .csv, .tsv, or .zip (DwC-A)")


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find a column matching one of the candidate names (case-insensitive)."""
    col_map = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in col_map:
            return col_map[name.lower()]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Species selection
# ─────────────────────────────────────────────────────────────────────────────

def select_species(
    df: pd.DataFrame,
    species_list: list[str],
    requested: list[str] | None = None,
    min_prevalence: float = 0.05,
    max_species: int = 8,
) -> list[tuple[str, float, int]]:
    """
    Select species for analysis.

    Returns list of (name, prevalence, n_present) sorted by prevalence descending.
    """
    if requested:
        result = []
        for sp in requested:
            if sp not in df.columns:
                logger.warning("Species '%s' not found in data — skipping", sp)
                continue
            vals = df[sp].dropna()
            n_pres = int((vals > 0).sum())
            prev = n_pres / len(vals) if len(vals) > 0 else 0
            result.append((sp, prev, n_pres))
        return result

    # Auto-select: species with ≥5 presences and above min_prevalence
    candidates = []
    for sp in species_list:
        if sp not in df.columns or not pd.api.types.is_numeric_dtype(df[sp]):
            continue
        vals = df[sp].dropna()
        n_pres = int((vals > 0).sum())
        prev = n_pres / len(vals) if len(vals) > 0 else 0
        if n_pres >= 5 and prev >= min_prevalence:
            candidates.append((sp, prev, n_pres))

    candidates.sort(key=lambda x: -x[1])

    if len(candidates) <= max_species:
        return candidates

    # Sample across the prevalence gradient
    selected = []
    n_bins = max_species
    prev_values = [c[1] for c in candidates]
    bin_edges = np.linspace(min(prev_values), max(prev_values), n_bins + 1)

    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        for sp, prev, n in candidates:
            if lo <= prev <= hi + 0.01 and sp not in [s[0] for s in selected]:
                selected.append((sp, prev, n))
                break

    # Fill remaining slots with highest-prevalence species not yet selected
    for sp, prev, n in candidates:
        if len(selected) >= max_species:
            break
        if sp not in [s[0] for s in selected]:
            selected.append((sp, prev, n))

    selected.sort(key=lambda x: -x[1])
    return selected


# ─────────────────────────────────────────────────────────────────────────────
# Covariate setup
# ─────────────────────────────────────────────────────────────────────────────

ENV_COLS = ["depth_m", "sst_mean_c", "bottom_temp_c", "sss_mean",
            "current_speed_ms", "chl_mean", "o2_mean_mmol"]

EUNIS_COLS = ["dominant_EUNIS2019", "dominant_EUNIS2019_name",
              "substrate_type", "substrate_type_name"]


def build_covariate_grid(
    sites_df: pd.DataFrame,
    h3_resolution: int = 7,
    emodnet_layers: list[str] | None = None,
    cmems_layers: list[str] | None = None,
    cmems_username: str = "",
    cmems_password: str = "",
) -> gpd.GeoDataFrame:
    """
    Generate hex grid and fetch all covariates.

    Returns GeoDataFrame with columns: geometry, Subzone_ID, and all covariates.
    """
    if emodnet_layers is None:
        emodnet_layers = ["eunis2019", "substrate", "depth"]
    if cmems_layers is None:
        cmems_layers = ["sst", "bottom_temp", "salinity", "current_speed",
                        "chlorophyll", "oxygen"]

    # Build bbox with 10% buffer
    lat_min, lat_max = sites_df["lat"].min(), sites_df["lat"].max()
    lon_min, lon_max = sites_df["lon"].min(), sites_df["lon"].max()
    lat_buf = max((lat_max - lat_min) * 0.1, 0.05)
    lon_buf = max((lon_max - lon_min) * 0.1, 0.05)
    bbox = box(lon_min - lon_buf, lat_min - lat_buf,
               lon_max + lon_buf, lat_max + lat_buf)
    bbox_gdf = gpd.GeoDataFrame(geometry=[bbox], crs="EPSG:4326")

    logger.info("Bounding box: [%.4f, %.4f] – [%.4f, %.4f]",
                lon_min - lon_buf, lat_min - lat_buf,
                lon_max + lon_buf, lat_max + lat_buf)

    # Generate grid
    grid = eva_hexgrid.generate_h3_grid(bbox_gdf, resolution=h3_resolution,
                                        clip_to_sea=True)
    logger.info("H3 grid: %d cells (res %d)", len(grid), h3_resolution)

    # EMODnet covariates
    logger.info("Fetching EMODnet covariates: %s", emodnet_layers)
    cov = eva_eunis_wms.fetch_sdm_covariates(grid, layers=emodnet_layers)
    _log_coverage(cov, "EMODnet")

    # CMEMS covariates
    if cmems_username and cmems_password:
        logger.info("Fetching CMEMS covariates: %s", cmems_layers)
        try:
            import eva_cmems
            cmems = eva_cmems.fetch_cmems_covariates(
                grid_gdf=cov, layers=cmems_layers,
                username=cmems_username, password=cmems_password,
            )
            for c in cmems.columns:
                if c not in cov.columns and c != "geometry":
                    cov[c] = cmems[c].values
            _log_coverage(cov, "CMEMS")
        except Exception as exc:
            logger.warning("CMEMS fetch failed: %s — continuing without", exc)
    else:
        logger.info("Skipping CMEMS (no credentials)")

    return cov


def _log_coverage(gdf: gpd.GeoDataFrame, label: str) -> None:
    """Log non-geometry column coverage."""
    for col in gdf.columns:
        if col in ("Subzone_ID", "geometry"):
            continue
        n = int(gdf[col].notna().sum())
        logger.info("  %s %-25s: %d/%d (%.0f%%)",
                    label, col, n, len(gdf), 100 * n / len(gdf))


# ─────────────────────────────────────────────────────────────────────────────
# Single-species model comparison
# ─────────────────────────────────────────────────────────────────────────────

def compare_predictor_sets(
    sites_cov: pd.DataFrame,
    species: str,
    env_cols: list[str] | None = None,
    eunis_cols: list[str] | None = None,
    do_cv: bool = True,
    cv_folds: int = 5,
) -> dict[str, Any]:
    """
    Compare RF models with different predictor sets for one species.

    Returns dict with keys: env, eunis, both, each containing:
      r2_train, r2_cv, rmse_cv, mae_cv, n_obs, n_features, importances
    """
    if env_cols is None:
        env_cols = [c for c in ENV_COLS if c in sites_cov.columns]
    if eunis_cols is None:
        eunis_cols = [c for c in EUNIS_COLS if c in sites_cov.columns]

    configs = {
        "env":   env_cols,
        "eunis": eunis_cols,
        "both":  env_cols + eunis_cols,
    }

    results = {}
    for tag, cols in configs.items():
        if not cols:
            results[tag] = {"r2_train": np.nan, "r2_cv": np.nan, "error": "no columns"}
            continue

        try:
            X, y, feat_names = eva_sdm.prepare_features(
                sites_cov, cols, species, response_type="continuous")
        except ValueError as e:
            results[tag] = {"r2_train": np.nan, "r2_cv": np.nan, "error": str(e)}
            continue

        model = eva_sdm.fit_random_forest(X, y, response_type="continuous")
        y_pred = model.predict(X)
        r2_train = float(r2_score(y, y_pred))

        r2_cv = rmse_cv = mae_cv = np.nan
        if do_cv and len(y) >= cv_folds * 3:
            try:
                rf_cv = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
                y_cv = cross_val_predict(rf_cv, X, y, cv=cv_folds)
                r2_cv = float(r2_score(y, y_cv))
                rmse_cv = float(np.sqrt(mean_squared_error(y, y_cv)))
                mae_cv = float(mean_absolute_error(y, y_cv))
            except Exception:
                pass

        importances = dict(zip(feat_names, model.feature_importances_.tolist()))

        results[tag] = {
            "r2_train": r2_train,
            "r2_cv": r2_cv,
            "rmse_cv": rmse_cv,
            "mae_cv": mae_cv,
            "n_obs": len(y),
            "n_features": X.shape[1],
            "importances": importances,
            "feat_names": feat_names,
        }

    return results


def compare_methods(
    sites_cov: pd.DataFrame,
    species: str,
    covariates: gpd.GeoDataFrame,
    methods: list[str] = None,
    env_cols: list[str] | None = None,
    eunis_cols: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compare multiple SDM methods for one species.

    Returns dict keyed by method name with r2, rmse, n_predictions, etc.
    """
    if methods is None:
        methods = ["rf", "kriging", "regression_kriging"]
    if env_cols is None:
        env_cols = [c for c in ENV_COLS if c in sites_cov.columns]
    if eunis_cols is None:
        eunis_cols = [c for c in EUNIS_COLS if c in sites_cov.columns]

    all_pred_cols = env_cols + eunis_cols
    results = {}

    for method in methods:
        try:
            if method == "kriging":
                # Ordinary Kriging — spatial only
                ok = eva_sdm.fit_kriging(sites_cov, species, variogram_model="spherical")
                preds, unc = eva_sdm.predict_grid(
                    grid_gdf=covariates, predictor_cols=[],
                    kriging_model=ok, method="kriging",
                    response_type="continuous", feat_names=[])
                n_valid = int(preds.notna().sum())

                # In-sample evaluation
                coords_m = eva_sdm._sites_to_metric(sites_cov, "lat", "lon")
                y_vals = sites_cov[species].values.astype(float)
                mask = ~np.isnan(y_vals)
                ok_preds = []
                for i in np.where(mask)[0]:
                    val, var = ok.execute("points",
                                          np.array([coords_m[i, 0]]),
                                          np.array([coords_m[i, 1]]))
                    ok_preds.append(float(val))
                r2 = float(r2_score(y_vals[mask], np.array(ok_preds)))
                rmse = float(np.sqrt(mean_squared_error(y_vals[mask], np.array(ok_preds))))

                results["Ordinary Kriging"] = {
                    "r2_insample": r2, "rmse_insample": rmse,
                    "n_predictions": n_valid, "predictors": "spatial only",
                }

            elif method == "rf":
                for label, cols in [("RF — env only", env_cols),
                                    ("RF — EUNIS only", eunis_cols),
                                    ("RF — env + EUNIS", all_pred_cols)]:
                    try:
                        X, y, fn = eva_sdm.prepare_features(
                            sites_cov, cols, species, response_type="continuous")
                        model = eva_sdm.fit_random_forest(X, y, response_type="continuous")
                        y_pred = model.predict(X)
                        results[label] = {
                            "r2_insample": float(r2_score(y, y_pred)),
                            "rmse_insample": float(np.sqrt(mean_squared_error(y, y_pred))),
                            "n_obs": len(y), "n_features": X.shape[1],
                            "predictors": "env" if cols == env_cols else
                                          "EUNIS" if cols == eunis_cols else "env+EUNIS",
                            "importances": dict(zip(fn, model.feature_importances_.tolist())),
                        }
                    except Exception as e:
                        results[label] = {"error": str(e)}

            elif method == "regression_kriging":
                for label, cols in [("RegKrig — env", env_cols),
                                    ("RegKrig — env + EUNIS", all_pred_cols)]:
                    try:
                        X, y, fn = eva_sdm.prepare_features(
                            sites_cov, cols, species, response_type="continuous")
                        rf = eva_sdm.fit_random_forest(X, y, response_type="continuous")
                        residuals = y - rf.predict(X)
                        valid = _align_valid_for_residuals(sites_cov, cols, species)
                        valid["__resid__"] = residuals
                        rk = eva_sdm.fit_kriging(valid, "__resid__", variogram_model="spherical")

                        preds, unc = eva_sdm.predict_grid(
                            grid_gdf=covariates, predictor_cols=cols,
                            rf_model=rf, kriging_model=rk,
                            method="regression_kriging",
                            response_type="continuous", feat_names=fn)

                        results[label] = {
                            "r2_insample": float(r2_score(y, rf.predict(X))),
                            "rmse_insample": float(np.sqrt(mean_squared_error(y, rf.predict(X)))),
                            "n_predictions": int(preds.notna().sum()),
                            "predictors": "env" if cols == env_cols else "env+EUNIS",
                            "importances": dict(zip(fn, rf.feature_importances_.tolist())),
                        }
                    except Exception as e:
                        results[label] = {"error": str(e)}

        except Exception as e:
            results[method] = {"error": str(e)}

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Collinearity analysis
# ─────────────────────────────────────────────────────────────────────────────

def analyse_collinearity(
    sites_cov: pd.DataFrame,
    env_cols: list[str] | None = None,
) -> dict:
    """Analyse correlation between EUNIS categories and continuous variables."""
    if env_cols is None:
        env_cols = [c for c in ENV_COLS if c in sites_cov.columns]

    eunis_col = None
    for c in ["dominant_EUNIS2019", "dominant_EUNIS2007"]:
        if c in sites_cov.columns:
            eunis_col = c
            break

    if eunis_col is None:
        return {"error": "No EUNIS column found"}

    # Habitat distribution — drop NaN habitats so iteration and value_counts
    # do not surface NaN keys to downstream formatters.
    eunis_series = sites_cov[eunis_col].dropna()
    hab_counts = eunis_series.value_counts().to_dict()

    # Depth by habitat
    depth_by_hab = {}
    if "depth_m" in sites_cov.columns:
        for h in sorted(eunis_series.unique()):
            sub = sites_cov[sites_cov[eunis_col] == h]["depth_m"].dropna()
            depth_by_hab[h] = {
                "count": len(sub),
                "mean": float(sub.mean()) if len(sub) > 0 else None,
                "min": float(sub.min()) if len(sub) > 0 else None,
                "max": float(sub.max()) if len(sub) > 0 else None,
            }

    # Dummy correlations with env vars
    dummies = pd.get_dummies(sites_cov[eunis_col], prefix="EUNIS", dtype=float)
    correlations = {}
    for env_c in env_cols:
        if env_c in sites_cov.columns and pd.api.types.is_numeric_dtype(sites_cov[env_c]):
            corrs = {}
            for d in dummies.columns:
                r = float(dummies[d].corr(sites_cov[env_c].astype(float)))
                corrs[d] = r
            correlations[env_c] = corrs

    # Substrate distribution
    substrate = {}
    if "substrate_type" in sites_cov.columns:
        substrate = sites_cov["substrate_type"].value_counts().to_dict()

    return {
        "eunis_col": eunis_col,
        "habitat_counts": hab_counts,
        "depth_by_habitat": depth_by_hab,
        "dummy_correlations": correlations,
        "substrate_distribution": substrate,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Habitat preference analysis
# ─────────────────────────────────────────────────────────────────────────────

def habitat_preference_table(
    sites_cov: pd.DataFrame,
    species_list: list[tuple[str, float, int]],
) -> pd.DataFrame:
    """
    Build habitat preference table: presence rate by EUNIS zone for each species.
    """
    eunis_col = None
    for c in ["dominant_EUNIS2019", "dominant_EUNIS2007"]:
        if c in sites_cov.columns:
            eunis_col = c
            break
    if eunis_col is None:
        return pd.DataFrame()

    habitats = sorted(sites_cov[eunis_col].unique())
    rows = []
    for sp, prev, n_pres in species_list:
        row = {"Species": sp, "Prevalence": f"{prev:.0%}"}
        for h in habitats:
            sub = sites_cov[sites_cov[eunis_col] == h]
            if sp in sub.columns:
                n = int((sub[sp] > 0).sum())
                total = len(sub)
                row[h] = f"{n}/{total} ({100*n/total:.0f}%)" if total > 0 else "—"
            else:
                row[h] = "—"
        rows.append(row)

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_report(
    input_path: str,
    data_info: dict,
    species_results: dict[str, dict],
    collinearity: dict,
    habitat_pref: pd.DataFrame,
    method_results: dict[str, dict],
    output_path: str,
    species_info: list[tuple[str, float, int]] | None = None,
) -> str:
    """Generate a Markdown report from analysis results."""
    lines = []
    _a = lines.append

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    _a(f"# SDM Predictor Comparison Report")
    _a(f"")
    _a(f"**MARBEFES EVA — Species Distribution Modelling**")
    _a(f"**Generated:** {now}")
    _a(f"**Input:** `{Path(input_path).name}`")
    _a(f"")
    _a(f"---")
    _a(f"")

    # Data summary
    _a(f"## 1. Data Summary")
    _a(f"")
    _a(f"| Parameter | Value |")
    _a(f"|---|---|")
    _a(f"| Source type | {data_info.get('source_type', 'unknown')} |")
    _a(f"| Total sites | {data_info.get('n_sites', '?')} |")
    _a(f"| Total species | {data_info.get('n_species', '?')} |")
    _a(f"| Has abundance | {data_info.get('has_abundance', '?')} |")
    _a(f"")

    # Collinearity
    if "error" not in collinearity:
        _a(f"## 2. EUNIS Habitat Classification")
        _a(f"")
        _a(f"### Habitat distribution at sites")
        _a(f"")
        _a(f"| Habitat | Sites |")
        _a(f"|---|---:|")
        for h, n in sorted(collinearity["habitat_counts"].items(), key=lambda x: -x[1]):
            _a(f"| {h} | {n} |")
        _a(f"")

        if collinearity["depth_by_habitat"]:
            _a(f"### Depth ranges by habitat")
            _a(f"")
            _a(f"| Habitat | Sites | Depth mean | Depth range |")
            _a(f"|---|---:|---:|---|")
            for h, d in sorted(collinearity["depth_by_habitat"].items()):
                if d["mean"] is not None:
                    _a(f"| {h} | {d['count']} | {d['mean']:.1f} m | {d['min']:.1f}–{d['max']:.1f} m |")
            _a(f"")

        if "depth_m" in collinearity.get("dummy_correlations", {}):
            _a(f"### EUNIS–depth correlation")
            _a(f"")
            _a(f"| EUNIS dummy | Pearson r with depth |")
            _a(f"|---|---:|")
            for d, r in sorted(collinearity["dummy_correlations"]["depth_m"].items()):
                bold = "**" if abs(r) > 0.5 else ""
                _a(f"| {d} | {bold}{r:+.3f}{bold} |")
            _a(f"")

        if collinearity["substrate_distribution"]:
            _a(f"### Substrate distribution")
            _a(f"")
            _a(f"| Substrate | Sites |")
            _a(f"|---|---:|")
            for s, n in sorted(collinearity["substrate_distribution"].items(), key=lambda x: -x[1]):
                _a(f"| {s} | {n} |")
            _a(f"")

    # Predictor comparison
    _a(f"## 3. Predictor Comparison (Random Forest)")
    _a(f"")
    _a(f"### Does EUNIS 2019 improve predictions?")
    _a(f"")
    _a(f"| Species | Prev. | R² env | R² EUNIS | R² both | Δ (both−env) |")
    _a(f"|---|---:|---:|---:|---:|---:|")
    for sp, res in species_results.items():
        env_r2 = res.get("env", {}).get("r2_train", np.nan)
        eunis_r2 = res.get("eunis", {}).get("r2_train", np.nan)
        both_r2 = res.get("both", {}).get("r2_train", np.nan)
        delta = both_r2 - env_r2 if not (np.isnan(both_r2) or np.isnan(env_r2)) else np.nan
        # Look up prevalence from species_info list
        prev = 0
        if species_info:
            for si_name, si_prev, _ in species_info:
                if si_name == sp:
                    prev = si_prev
                    break

        def _fmt(v):
            return f"{v:.4f}" if not np.isnan(v) else "—"

        _a(f"| *{sp}* | {prev:.0%} | {_fmt(env_r2)} | {_fmt(eunis_r2)} | {_fmt(both_r2)} | {'+' if delta > 0 else ''}{_fmt(delta)} |")
    _a(f"")

    # Top features
    _a(f"### Top features in combined models")
    _a(f"")
    for sp, res in species_results.items():
        both = res.get("both", {})
        imp = both.get("importances", {})
        if imp:
            top5 = sorted(imp.items(), key=lambda x: -x[1])[:5]
            _a(f"**{sp}** (R²={both.get('r2_train', 0):.4f}):")
            _a(f"")
            for fname, val in top5:
                bar = "█" * int(val * 50)
                _a(f"- `{fname}`: {val:.3f} {bar}")
            _a(f"")

    # Cross-validation (if available)
    has_cv = any(
        not np.isnan(res.get("env", {}).get("r2_cv", np.nan))
        for res in species_results.values()
    )
    if has_cv:
        _a(f"### Cross-validated performance (5-fold)")
        _a(f"")
        _a(f"| Species | R² CV (env) | R² CV (both) | RMSE CV (env) |")
        _a(f"|---|---:|---:|---:|")
        for sp, res in species_results.items():
            def _fmt(v):
                return f"{v:.4f}" if not np.isnan(v) else "—"
            _a(f"| *{sp}* | {_fmt(res.get('env',{}).get('r2_cv',np.nan))} | {_fmt(res.get('both',{}).get('r2_cv',np.nan))} | {_fmt(res.get('env',{}).get('rmse_cv',np.nan))} |")
        _a(f"")

    # Method comparison
    if method_results:
        _a(f"## 4. Method Comparison")
        _a(f"")
        _a(f"| Method | R² (in-sample) | RMSE | Grid predictions | Predictors |")
        _a(f"|---|---:|---:|---:|---|")
        for name, m in method_results.items():
            if "error" in m:
                _a(f"| {name} | — | — | — | error: {m['error'][:40]} |")
            else:
                r2 = m.get("r2_insample", np.nan)
                rmse = m.get("rmse_insample", np.nan)
                n_pred = m.get("n_predictions", "—")
                pred_type = m.get("predictors", "—")
                _a(f"| {name} | {r2:.4f} | {rmse:.4f} | {n_pred} | {pred_type} |")
        _a(f"")

    # Habitat preference
    if not habitat_pref.empty:
        _a(f"## 5. Habitat Preference Patterns")
        _a(f"")
        _a(f"Presence counts by EUNIS zone:")
        _a(f"")
        # Manual markdown table (avoid tabulate dependency)
        cols = list(habitat_pref.columns)
        _a("| " + " | ".join(cols) + " |")
        _a("|" + "|".join(["---"] * len(cols)) + "|")
        for _, row in habitat_pref.iterrows():
            _a("| " + " | ".join(str(row[c]) for c in cols) + " |")
        _a(f"")

    # Conclusions
    _a(f"## 6. Conclusions")
    _a(f"")

    # Auto-generate conclusions from results
    all_deltas = []
    for sp, res in species_results.items():
        env_r2 = res.get("env", {}).get("r2_train", np.nan)
        both_r2 = res.get("both", {}).get("r2_train", np.nan)
        if not np.isnan(env_r2) and not np.isnan(both_r2):
            all_deltas.append(both_r2 - env_r2)

    if all_deltas:
        mean_delta = np.mean(all_deltas)
        max_delta = np.max(all_deltas)
        if max_delta < 0.01:
            _a(f"1. **EUNIS habitats do not improve predictions** — adding EUNIS 2019 to "
               f"environmental variables gave a maximum R² improvement of {max_delta:+.4f} "
               f"across all species tested.")
        elif max_delta < 0.05:
            _a(f"1. **EUNIS habitats provide marginal improvement** — maximum R² gain "
               f"of {max_delta:+.4f}. Consider including only if computational cost is low.")
        else:
            _a(f"1. **EUNIS habitats provide meaningful improvement** — maximum R² gain "
               f"of {max_delta:+.4f}. Include in final models.")

    # Check collinearity conclusion
    if "depth_m" in collinearity.get("dummy_correlations", {}):
        max_corr = max(abs(r) for r in collinearity["dummy_correlations"]["depth_m"].values())
        if max_corr > 0.7:
            _a(f"2. **High collinearity with depth** — EUNIS dummy correlations with depth "
               f"reach |r|={max_corr:.2f}, explaining the redundancy.")
        elif max_corr > 0.4:
            _a(f"2. **Moderate collinearity with depth** — EUNIS correlations with depth "
               f"reach |r|={max_corr:.2f}.")
        else:
            _a(f"2. **Low collinearity** — EUNIS categories appear to capture different "
               f"gradients than continuous variables.")

    # Substrate conclusion
    sub_dist = collinearity.get("substrate_distribution", {})
    if sub_dist:
        total = sum(sub_dist.values())
        max_sub = max(sub_dist.values())
        if max_sub / total > 0.9:
            dom = [k for k, v in sub_dist.items() if v == max_sub][0]
            _a(f"3. **Substrate is homogeneous** — {max_sub/total:.0%} of sites have "
               f"'{dom}', providing negligible discriminatory power.")

    _a(f"")
    _a(f"---")
    _a(f"")
    _a(f"*Generated by MARBEFES EVA SDM analysis pipeline (`scripts/sdm_analyse.py`)*")

    report_text = "\n".join(lines)

    # Write report
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report_text, encoding="utf-8")
    logger.info("Report saved to: %s", out)

    return report_text


# ─────────────────────────────────────────────────────────────────────────────
# JSON results export
# ─────────────────────────────────────────────────────────────────────────────

def export_json(results: dict, path: str) -> None:
    """Export full analysis results as JSON for programmatic use."""
    def _convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj) if not np.isnan(obj) else None
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient="records")
        return str(obj)

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=_convert)
    logger.info("JSON results saved to: %s", p)


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_analysis(
    input_path: str,
    species: list[str] | None = None,
    methods: list[str] | None = None,
    h3_resolution: int = 7,
    min_prevalence: float = 0.05,
    max_species: int = 8,
    skip_cmems: bool = False,
    cmems_username: str = "",
    cmems_password: str = "",
    emodnet_layers: list[str] | None = None,
    output_dir: str | None = None,
    do_cv: bool = True,
    quick: bool = False,
) -> dict:
    """
    Run the full SDM analysis pipeline.

    Returns dict with all results for programmatic access.
    """
    if methods is None:
        methods = ["rf"] if quick else ["rf", "kriging", "regression_kriging"]
    if output_dir is None:
        output_dir = str(PROJECT_ROOT / "sdm_analysis_output")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("MARBEFES EVA — SDM Predictor Analysis Pipeline")
    logger.info("=" * 70)

    # Step 1: Load data
    logger.info("\n── Step 1: Loading data ──")
    df, data_info = load_input(input_path)
    logger.info("  %d sites, %d species", data_info["n_sites"], data_info["n_species"])

    # Step 2: Select species
    logger.info("\n── Step 2: Selecting species ──")
    species_sel = select_species(df, data_info["species_list"],
                                 requested=species,
                                 min_prevalence=min_prevalence,
                                 max_species=max_species)
    logger.info("  Selected %d species:", len(species_sel))
    for sp, prev, n in species_sel:
        logger.info("    %-35s prev=%.1f%% (%d/%d)", sp, prev*100, n, data_info["n_sites"])

    # Step 3: Build covariate grid
    logger.info("\n── Step 3: Building covariate grid ──")
    covariates = build_covariate_grid(
        df, h3_resolution=h3_resolution,
        emodnet_layers=emodnet_layers,
        cmems_layers=None if skip_cmems else None,
        cmems_username="" if skip_cmems else cmems_username,
        cmems_password="" if skip_cmems else cmems_password,
    )

    # Step 4: Extract covariates at sites
    logger.info("\n── Step 4: Extracting covariates at sites ──")
    sites_cov = eva_sdm.extract_covariates_at_sites(df, covariates, lat_col="lat", lon_col="lon")
    logger.info("  Sites with covariates: %d", len(sites_cov))

    # Identify available env/eunis columns
    env_cols = [c for c in ENV_COLS if c in sites_cov.columns and sites_cov[c].notna().any()]
    eunis_cols = [c for c in EUNIS_COLS if c in sites_cov.columns and sites_cov[c].notna().any()]
    logger.info("  Env columns: %s", env_cols)
    logger.info("  EUNIS columns: %s", eunis_cols)

    # Step 5: Collinearity analysis
    logger.info("\n── Step 5: Collinearity analysis ──")
    collinearity = analyse_collinearity(sites_cov, env_cols)
    if "error" not in collinearity:
        logger.info("  EUNIS column: %s", collinearity["eunis_col"])
        logger.info("  Habitats: %d types", len(collinearity["habitat_counts"]))
        if "depth_m" in collinearity.get("dummy_correlations", {}):
            max_r = max(abs(r) for r in collinearity["dummy_correlations"]["depth_m"].values())
            logger.info("  Max |r| EUNIS-depth: %.3f", max_r)

    # Step 6: Per-species predictor comparison
    logger.info("\n── Step 6: Per-species predictor comparison ──")
    species_results = {}
    for sp, prev, n in species_sel:
        logger.info("  Analysing: %s (prev=%.1f%%)", sp, prev*100)
        species_results[sp] = compare_predictor_sets(
            sites_cov, sp, env_cols=env_cols, eunis_cols=eunis_cols,
            do_cv=do_cv and not quick,
        )
        env_r2 = species_results[sp].get("env", {}).get("r2_train", np.nan)
        both_r2 = species_results[sp].get("both", {}).get("r2_train", np.nan)
        delta = both_r2 - env_r2 if not (np.isnan(env_r2) or np.isnan(both_r2)) else 0
        logger.info("    R2 env=%.4f  EUNIS=%.4f  both=%.4f  delta=%+.4f",
                    env_r2,
                    species_results[sp].get("eunis", {}).get("r2_train", np.nan),
                    both_r2, delta)

    # Step 7: Method comparison (for first species)
    logger.info("\n── Step 7: Method comparison ──")
    method_results = {}
    if species_sel:
        primary_sp = species_sel[0][0]
        logger.info("  Primary species: %s", primary_sp)
        method_results = compare_methods(
            sites_cov, primary_sp, covariates,
            methods=methods, env_cols=env_cols, eunis_cols=eunis_cols,
        )
        for name, m in method_results.items():
            if "error" in m:
                logger.info("    %s: ERROR — %s", name, m["error"])
            else:
                logger.info("    %s: R2=%.4f RMSE=%.4f",
                            name, m.get("r2_insample", np.nan), m.get("rmse_insample", np.nan))

    # Step 8: Habitat preference table
    logger.info("\n── Step 8: Habitat preference ──")
    hab_pref = habitat_preference_table(sites_cov, species_sel)

    # Step 9: Generate report
    logger.info("\n── Step 9: Generating report ──")
    report_path = str(out / "SDM_Analysis_Report.md")
    generate_report(
        input_path, data_info, species_results, collinearity,
        hab_pref, method_results, report_path,
        species_info=species_sel,
    )

    # Export JSON
    json_path = str(out / "SDM_Analysis_Results.json")
    export_json({
        "input": input_path,
        "data_info": data_info,
        "species": [(s, p, n) for s, p, n in species_sel],
        "species_results": species_results,
        "collinearity": collinearity,
        "method_results": method_results,
    }, json_path)

    logger.info("\n" + "=" * 70)
    logger.info("ANALYSIS COMPLETE")
    logger.info("  Report:  %s", report_path)
    logger.info("  JSON:    %s", json_path)
    logger.info("=" * 70)

    return {
        "data_info": data_info,
        "species": species_sel,
        "species_results": species_results,
        "collinearity": collinearity,
        "method_results": method_results,
        "report_path": report_path,
        "json_path": json_path,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="MARBEFES EVA — SDM predictor analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.sdm_analyse --input data/dwca-macrosoft-v2.1.zip
  python -m scripts.sdm_analyse --input my_data.csv --skip-cmems --quick
  python -m scripts.sdm_analyse --input data.csv --species "Amphiura chiajei" --methods rf kriging
""",
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input file: CSV or DwC-A .zip")
    parser.add_argument("--species", "-s", nargs="*", default=None,
                        help="Species to analyse (default: auto-select by prevalence)")
    parser.add_argument("--methods", "-m", nargs="*", default=None,
                        choices=["rf", "kriging", "regression_kriging"],
                        help="SDM methods to compare (default: all three)")
    parser.add_argument("--h3-res", type=int, default=7,
                        help="H3 grid resolution (default: 7, ~5.2 km²)")
    parser.add_argument("--min-prevalence", type=float, default=0.05,
                        help="Minimum species prevalence for auto-selection (default: 0.05)")
    parser.add_argument("--max-species", type=int, default=8,
                        help="Maximum species for auto-selection (default: 8)")
    parser.add_argument("--skip-cmems", action="store_true",
                        help="Skip Copernicus Marine data fetch")
    parser.add_argument("--output", "-o", default=None,
                        help="Output directory (default: sdm_analysis_output/)")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: RF only, no CV, no kriging")
    parser.add_argument("--no-cv", action="store_true",
                        help="Skip cross-validation")
    args = parser.parse_args()

    # CMEMS credentials
    cmems_user = os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME", "")
    cmems_pass = os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD", "")

    if not args.skip_cmems and not cmems_user:
        logger.info("Copernicus Marine credentials needed for oceanographic data.")
        logger.info("Set COPERNICUSMARINE_SERVICE_USERNAME/PASSWORD env vars,")
        logger.info("or use --skip-cmems to skip.")
        try:
            cmems_user = input("CMEMS username (or Enter to skip): ").strip()
            if cmems_user:
                cmems_pass = getpass.getpass("CMEMS password: ").strip()
        except (EOFError, KeyboardInterrupt):
            pass

    run_analysis(
        input_path=args.input,
        species=args.species,
        methods=args.methods,
        h3_resolution=args.h3_res,
        min_prevalence=args.min_prevalence,
        max_species=args.max_species,
        skip_cmems=args.skip_cmems or not cmems_user,
        cmems_username=cmems_user,
        cmems_password=cmems_pass,
        output_dir=args.output,
        do_cv=not args.no_cv,
        quick=args.quick,
    )


if __name__ == "__main__":
    main()
