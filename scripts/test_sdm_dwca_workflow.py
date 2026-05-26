"""
Standalone SDM workflow test using dwca-macrosoft-v2.1.zip.

End-to-end pipeline:
  1. Parse DwC-A archive → sites × species matrix
  2. Generate H3 hex grid covering the spatial extent
  3. Fetch EMODnet covariates (depth, EUNIS, substrate)
  4. Fetch Copernicus Marine covariates (SST, salinity, etc.)
  5. Run data analysis → suggest best SDM method
  6. Fit the recommended model and produce predictions

Usage:
    python -m scripts.test_sdm_dwca_workflow
    python -m scripts.test_sdm_dwca_workflow --skip-cmems   # skip Copernicus Marine
    python -m scripts.test_sdm_dwca_workflow --method rf     # force a specific method
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dwca_reader
import eva_hexgrid
import eva_eunis_wms
import eva_sdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sdm_test")

# Suppress noisy warnings from pykrige / sklearn / pygam
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pykrige")

DWCA_PATH = PROJECT_ROOT / "data" / "dwca-macrosoft-v2.1.zip"
H3_RESOLUTION = 7  # ~5 km² per hex cell — good balance for test data


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1 — Parse DwC-A archive
# ═══════════════════════════════════════════════════════════════════════════════

def step_parse_dwca() -> tuple[pd.DataFrame, dict]:
    """Parse DwC-A archive into sites × species DataFrame."""
    logger.info("═" * 60)
    logger.info("STEP 1: Parsing DwC-A archive")
    logger.info("═" * 60)

    if not DWCA_PATH.exists():
        logger.error("DwC-A file not found: %s", DWCA_PATH)
        sys.exit(1)

    df, info = dwca_reader.read_dwca_for_sdm(str(DWCA_PATH), value="auto")

    logger.info("  Source type  : %s", info["source_type"])
    logger.info("  Value type   : %s", info["value_type"])
    logger.info("  Sites        : %d", info["n_sites"])
    logger.info("  Species      : %d", info["n_species"])
    logger.info("  Lat range    : %.4f – %.4f", df["lat"].min(), df["lat"].max())
    logger.info("  Lon range    : %.4f – %.4f", df["lon"].min(), df["lon"].max())
    logger.info("  Has abundance: %s", info["has_abundance"])
    logger.info("  First 5 species: %s", info["species_list"][:5])

    return df, info


# ═══════════════════════════════════════════════════════════════════════════════
# Step 2 — Generate hex grid covering spatial extent
# ═══════════════════════════════════════════════════════════════════════════════

def step_generate_grid(sites_df: pd.DataFrame, h3_resolution: int = H3_RESOLUTION) -> gpd.GeoDataFrame:
    """Create H3 hex grid from bounding box of sampling sites."""
    logger.info("")
    logger.info("═" * 60)
    logger.info("STEP 2: Generating H3 hex grid (resolution %d)", h3_resolution)
    logger.info("═" * 60)

    # Build bounding box with 10% buffer
    lat_min, lat_max = sites_df["lat"].min(), sites_df["lat"].max()
    lon_min, lon_max = sites_df["lon"].min(), sites_df["lon"].max()
    lat_buf = max((lat_max - lat_min) * 0.1, 0.05)
    lon_buf = max((lon_max - lon_min) * 0.1, 0.05)

    bbox = box(
        lon_min - lon_buf, lat_min - lat_buf,
        lon_max + lon_buf, lat_max + lat_buf,
    )
    bbox_gdf = gpd.GeoDataFrame(geometry=[bbox], crs="EPSG:4326")

    logger.info("  Bounding box: [%.4f, %.4f] – [%.4f, %.4f]",
                lon_min - lon_buf, lat_min - lat_buf,
                lon_max + lon_buf, lat_max + lat_buf)

    grid = eva_hexgrid.generate_h3_grid(bbox_gdf, resolution=h3_resolution, clip_to_sea=True)

    logger.info("  Grid cells   : %d (after sea clipping)", len(grid))
    logger.info("  CRS          : %s", grid.crs)

    return grid


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3 — Fetch EMODnet covariates
# ═══════════════════════════════════════════════════════════════════════════════

def step_fetch_emodnet(grid: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Fetch EMODnet covariates (EUNIS, substrate, depth) for each hex cell."""
    logger.info("")
    logger.info("═" * 60)
    logger.info("STEP 3: Fetching EMODnet covariates")
    logger.info("═" * 60)

    emodnet_layers = ["eunis2019", "substrate", "depth"]

    def _progress(label, idx, total):
        logger.info("  [%d/%d] %s", idx + 1, total, label)

    covariates = eva_eunis_wms.fetch_sdm_covariates(
        grid, layers=emodnet_layers, progress_cb=_progress,
    )

    # Report coverage
    for col in covariates.columns:
        if col in ("Subzone_ID", "geometry"):
            continue
        n_valid = int(covariates[col].notna().sum())
        logger.info("  %-25s: %d/%d hexagons (%.0f%%)",
                    col, n_valid, len(covariates), 100 * n_valid / len(covariates))

    return covariates


# ═══════════════════════════════════════════════════════════════════════════════
# Step 4 — Fetch Copernicus Marine covariates
# ═══════════════════════════════════════════════════════════════════════════════

def step_fetch_cmems(
    covariates: gpd.GeoDataFrame,
    username: str,
    password: str,
) -> gpd.GeoDataFrame:
    """Fetch CMEMS climatological covariates and merge with existing."""
    logger.info("")
    logger.info("═" * 60)
    logger.info("STEP 4: Fetching Copernicus Marine covariates")
    logger.info("═" * 60)

    import eva_cmems

    cmems_layers = ["sst", "bottom_temp", "salinity", "current_speed",
                    "chlorophyll", "oxygen"]

    logger.info("  Layers: %s", ", ".join(cmems_layers))
    logger.info("  Fetching (this may take a few minutes)...")

    cmems_gdf = eva_cmems.fetch_cmems_covariates(
        grid_gdf=covariates,
        layers=cmems_layers,
        username=username,
        password=password,
    )

    # Merge CMEMS columns into existing covariates
    new_cols = [c for c in cmems_gdf.columns
                if c not in covariates.columns and c != "geometry"]
    for col in new_cols:
        covariates = covariates.copy()
        covariates[col] = cmems_gdf[col].values

    for col in new_cols:
        n_valid = int(covariates[col].notna().sum())
        mean_val = covariates[col].mean()
        logger.info("  %-25s: %d/%d hexagons, mean=%.3g",
                    col, n_valid, len(covariates), mean_val)

    return covariates


# ═══════════════════════════════════════════════════════════════════════════════
# Step 5 — Analyse data and recommend SDM method
# ═══════════════════════════════════════════════════════════════════════════════

def step_analyse_data(
    sites_df: pd.DataFrame,
    response_col: str,
    covariates: gpd.GeoDataFrame,
) -> dict:
    """Run data analysis and get method recommendation."""
    logger.info("")
    logger.info("═" * 60)
    logger.info("STEP 5: Analysing data → method recommendation")
    logger.info("═" * 60)

    info = eva_sdm.analyse_sampling_data(
        sites_df, response_col,
        lat_col="lat", lon_col="lon",
        covariates_gdf=covariates,
    )

    if "error" in info:
        logger.error("  Analysis error: %s", info["error"])
        return info

    logger.info("  Response       : %s", response_col)
    logger.info("  Data type      : %s", info["data_type"])
    logger.info("  Sites          : %d valid / %d total", info["n_valid"], info["n_sites"])
    logger.info("  Prevalence     : %.1f%%", info["prevalence"] * 100)
    logger.info("  Range          : %.3g – %.3g", info["response_min"], info["response_max"])
    logger.info("  Mean ± SD      : %.3g ± %.3g", info["response_mean"], info["response_std"])
    logger.info("  Zero inflation : %.0f%%", info["zero_inflation"] * 100)
    logger.info("  Spatial extent : %.1f km²", info.get("spatial_extent_km2", 0) or 0)
    logger.info("  Has covariates : %s", info["has_covariates"])
    logger.info("  Categorical    : %s", info["categorical_cols"])
    logger.info("")

    method_label = eva_sdm._METHOD_LABELS.get(info["suggested_method"],
                                                info["suggested_method"])
    logger.info("  ╔══════════════════════════════════════════════╗")
    logger.info("  ║  💡 RECOMMENDED METHOD: %-21s ║", method_label.split("(")[0].strip())
    logger.info("  ╚══════════════════════════════════════════════╝")
    for reason in info["suggestion_reasons"]:
        logger.info("    → %s", reason)
    for warn in info["warnings"]:
        logger.info("    ⚠️  %s", warn)

    return info


# ═══════════════════════════════════════════════════════════════════════════════
# Step 6 — Fit recommended model and produce predictions
# ═══════════════════════════════════════════════════════════════════════════════

def step_fit_and_predict(
    sites_df: pd.DataFrame,
    response_col: str,
    covariates: gpd.GeoDataFrame,
    method: str,
    response_type: str,
) -> gpd.GeoDataFrame | None:
    """Fit the SDM model and predict across the grid."""
    logger.info("")
    logger.info("═" * 60)
    logger.info("STEP 6: Fitting %s model and predicting", method.upper())
    logger.info("═" * 60)

    # 6a. Extract covariates at sampling sites
    logger.info("  Extracting covariates at sampling sites...")
    sites_with_cov = eva_sdm.extract_covariates_at_sites(
        sites_df, covariates, lat_col="lat", lon_col="lon",
    )
    logger.info("  Sites with covariates: %d (max dist to cell: %.0f m)",
                len(sites_with_cov), sites_with_cov["_dist_to_cell_m"].max())

    # 6b. Identify predictor columns (numeric + categorical from covariates)
    skip_cols = {"Subzone_ID", "Subzone ID", "geometry", "cell_id", "h3_index",
                 "_dist_to_cell_m", "lat", "lon", "site_id"}
    species_cols = set(sites_df.columns) - {"lat", "lon", "site_id"}
    predictor_cols = [c for c in sites_with_cov.columns
                      if c not in skip_cols and c not in species_cols
                      and c != response_col]
    # Keep only columns that have some data
    predictor_cols = [c for c in predictor_cols
                      if sites_with_cov[c].notna().sum() > 0]

    logger.info("  Predictor columns (%d): %s", len(predictor_cols), predictor_cols)

    if not predictor_cols:
        logger.warning("  No predictor columns available — falling back to IDW")
        method = "idw"

    # 6c. Prepare feature matrix
    logger.info("  Preparing features...")
    X, y, feat_names = eva_sdm.prepare_features(
        sites_with_cov, predictor_cols, response_col,
        response_type=response_type,
    )
    logger.info("  Feature matrix: X=%s, y=%s", X.shape, y.shape)
    logger.info("  Feature names: %s", feat_names[:10])

    # 6d. Site coordinates (for spatial models)
    coords_m = eva_sdm._sites_to_metric(sites_with_cov, "lat", "lon")
    logger.info("  Site coordinates (metric): %s", coords_m.shape)

    # 6e. Fit model(s)
    models = {}
    logger.info("  Fitting model: %s ...", method)

    try:
        if method in ("idw", "ensemble"):
            idw_power = 2.0
            models["idw"] = eva_sdm.fit_idw(coords_m, y, power=idw_power)
            logger.info("    ✓ IDW fitted (power=%.1f)", idw_power)

        if method in ("kriging", "regression_kriging", "ensemble"):
            models["kriging"] = eva_sdm.fit_kriging(
                coords_m, y, variogram_model="spherical",
            )
            logger.info("    ✓ Ordinary Kriging fitted")

        if method in ("gam", "ensemble") and len(predictor_cols) > 0:
            models["gam"] = eva_sdm.fit_gam(
                X, y, response_type=response_type,
            )
            logger.info("    ✓ GAM fitted")

        if method in ("rf", "regression_kriging", "ensemble") and len(predictor_cols) > 0:
            models["rf"] = eva_sdm.fit_random_forest(
                X, y, response_type=response_type,
            )
            logger.info("    ✓ Random Forest fitted")

        if method == "xgboost" and len(predictor_cols) > 0:
            models["xgb"] = eva_sdm.fit_xgboost(
                X, y, response_type=response_type,
            )
            logger.info("    ✓ XGBoost fitted")

        if method == "lightgbm" and len(predictor_cols) > 0:
            models["lgbm"] = eva_sdm.fit_lightgbm(
                X, y, response_type=response_type,
            )
            logger.info("    ✓ LightGBM fitted")

        if method in ("gp", "ensemble"):
            models["gp"] = eva_sdm.fit_gaussian_process(
                coords_m, y, response_type=response_type,
            )
            logger.info("    ✓ Gaussian Process fitted")

        if method == "regression_kriging" and len(predictor_cols) > 0:
            models["rk"] = eva_sdm.fit_regression_kriging(
                X, y, coords_m, variogram_model="spherical",
            )
            logger.info("    ✓ Regression Kriging fitted")

    except Exception as exc:
        logger.error("  ✗ Model fitting failed: %s", exc, exc_info=True)
        return None

    # 6f. Predict across the grid
    logger.info("  Predicting across %d grid cells...", len(covariates))

    try:
        predictions, uncertainty = eva_sdm.predict_grid(
            grid_gdf=covariates,
            predictor_cols=predictor_cols,
            gam_model=models.get("gam"),
            idw_model=models.get("idw"),
            kriging_model=models.get("kriging"),
            rf_model=models.get("rf"),
            xgb_model=models.get("xgb"),
            lgbm_model=models.get("lgbm"),
            gp_model=models.get("gp"),
            rk_model=models.get("rk"),
            method=method,
            response_type=response_type,
            feat_names=feat_names,
        )
    except Exception as exc:
        logger.error("  ✗ Prediction failed: %s", exc, exc_info=True)
        return None

    n_valid = int(predictions.notna().sum())
    logger.info("  Predictions: %d/%d valid cells", n_valid, len(predictions))
    if n_valid > 0:
        logger.info("  Prediction range: %.4g – %.4g (mean=%.4g)",
                    predictions.min(), predictions.max(), predictions.mean())
    if uncertainty is not None:
        logger.info("  Uncertainty range: %.4g – %.4g",
                    uncertainty.min(), uncertainty.max())

    # 6g. In-sample diagnostics
    logger.info("  Computing in-sample diagnostics...")
    try:
        # Get in-sample predictions from the primary fitted model
        y_pred = None
        if "rf" in models and X.shape[1] > 0:
            y_pred = models["rf"].predict(X)
        elif "gam" in models and X.shape[1] > 0:
            y_pred = models["gam"].predict(X)
        elif "xgb" in models and X.shape[1] > 0:
            y_pred = models["xgb"].predict(X)
        elif "lgbm" in models and X.shape[1] > 0:
            y_pred = models["lgbm"].predict(X)

        if y_pred is not None:
            diag = eva_sdm.model_diagnostics(
                y_true=y, y_pred=y_pred,
                response_type=response_type,
                feature_names=feat_names,
                gam_model=models.get("gam"),
                rf_model=models.get("rf"),
                xgb_model=models.get("xgb"),
                lgbm_model=models.get("lgbm"),
            )
            logger.info("  R²   = %.4f", diag.get("r2", float("nan")))
            logger.info("  RMSE = %.4f", diag.get("rmse", float("nan")))
            logger.info("  MAE  = %.4f", diag.get("mae", float("nan")))
            if "auc" in diag:
                logger.info("  AUC  = %.4f", diag["auc"])
            if diag.get("feature_importances"):
                top5 = sorted(diag["feature_importances"].items(),
                              key=lambda x: -x[1])[:5]
                logger.info("  Top 5 features:")
                for fname, imp in top5:
                    logger.info("    %-30s %.4f", fname, imp)
        else:
            logger.info("  Skipped diagnostics (no covariate-based model available)")
    except Exception as exc:
        logger.warning("  Diagnostics failed: %s", exc)

    # Attach predictions to grid
    result = covariates.copy()
    result["prediction"] = predictions.values
    if uncertainty is not None:
        result["uncertainty"] = uncertainty.values

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="SDM workflow test with DwC-A data")
    parser.add_argument("--skip-cmems", action="store_true",
                        help="Skip Copernicus Marine data fetch")
    parser.add_argument("--method", type=str, default=None,
                        help="Force a specific SDM method (overrides recommendation)")
    parser.add_argument("--species", type=str, default=None,
                        help="Use a specific species as response variable")
    parser.add_argument("--h3-res", type=int, default=H3_RESOLUTION,
                        help="H3 grid resolution (default: 7)")
    parser.add_argument("--skip-fit", action="store_true",
                        help="Skip model fitting (analysis only)")
    parser.add_argument("--output", type=str, default=None,
                        help="Save predictions GeoPackage to this path")
    args = parser.parse_args()

    h3_res = args.h3_res

    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║   MARBEFES EVA — SDM Workflow Test (DwC-A Pipeline)     ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    logger.info("")

    # ── Step 1: Parse DwC-A ──────────────────────────────────────────────────
    sites_df, dwca_info = step_parse_dwca()

    # ── Choose response variable ─────────────────────────────────────────────
    species_cols = dwca_info["species_list"]
    if args.species:
        if args.species not in sites_df.columns:
            logger.error("Species '%s' not found. Available: %s",
                         args.species, species_cols[:10])
            sys.exit(1)
        response_col = args.species
    else:
        # Pick the most prevalent species for a meaningful test
        prevalences = {sp: float((sites_df[sp] > 0).mean()) for sp in species_cols}
        # Prefer species with 20-80% prevalence for best SDM testing
        best = sorted(prevalences.items(),
                      key=lambda x: -abs(x[1] - 0.5) if x[1] > 0 else 999)
        # Among those with decent prevalence, pick one
        good_species = [(sp, p) for sp, p in best if 0.1 < p < 0.9]
        if good_species:
            response_col = good_species[0][0]
        else:
            # Fallback to most prevalent species
            response_col = max(prevalences, key=prevalences.get)

    logger.info("")
    logger.info("  📊 Selected response: '%s' (prevalence=%.1f%%)",
                response_col,
                float((sites_df[response_col] > 0).mean()) * 100)

    # ── Step 2: Generate hex grid ────────────────────────────────────────────
    grid = step_generate_grid(sites_df, h3_resolution=h3_res)

    # ── Step 3: EMODnet covariates ───────────────────────────────────────────
    covariates = step_fetch_emodnet(grid)

    # ── Step 4: CMEMS covariates (optional) ──────────────────────────────────
    if not args.skip_cmems:
        username = os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME", "")
        password = os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD", "")

        if not username:
            logger.info("")
            logger.info("  Copernicus Marine credentials required.")
            logger.info("  Register free at: https://marine.copernicus.eu")
            try:
                username = input("  CMEMS username: ").strip()
                password = getpass.getpass("  CMEMS password: ").strip()
            except (EOFError, KeyboardInterrupt):
                logger.info("  Skipping CMEMS (no credentials provided)")
                username = ""

        if username and password:
            try:
                covariates = step_fetch_cmems(covariates, username, password)
            except Exception as exc:
                logger.warning("  CMEMS fetch failed: %s", exc)
                logger.info("  Continuing with EMODnet covariates only.")
        else:
            logger.info("  Skipping CMEMS (no credentials)")
    else:
        logger.info("")
        logger.info("  Skipping CMEMS (--skip-cmems flag)")

    # ── Step 5: Analyse and recommend ────────────────────────────────────────
    analysis = step_analyse_data(sites_df, response_col, covariates)

    if "error" in analysis:
        sys.exit(1)

    # ── Step 6: Fit and predict ──────────────────────────────────────────────
    if args.skip_fit:
        logger.info("")
        logger.info("  Skipping model fitting (--skip-fit flag)")
    else:
        method = args.method or analysis["suggested_method"]
        response_type = analysis["data_type"]
        if response_type == "count":
            response_type = "continuous"  # treat counts as continuous for fitting

        logger.info("")
        logger.info("  Using method: %s %s",
                    method,
                    "(user override)" if args.method else "(recommended)")

        result = step_fit_and_predict(
            sites_df, response_col, covariates, method, response_type,
        )

        if result is not None:
            # Save output
            out_path = args.output or str(
                PROJECT_ROOT / f"sdm_test_output_{method}.gpkg"
            )
            try:
                result.to_file(out_path, driver="GPKG")
                logger.info("")
                logger.info("  💾 Predictions saved to: %s", out_path)
            except Exception as exc:
                logger.warning("  Could not save GPKG: %s", exc)

            # Also save as CSV for quick inspection
            csv_path = out_path.replace(".gpkg", ".csv")
            try:
                result.drop(columns="geometry").to_csv(csv_path, index=False)
                logger.info("  💾 CSV export saved to: %s", csv_path)
            except Exception:
                pass

    # ── Summary ──────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║   ✅ SDM WORKFLOW COMPLETE                              ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    logger.info("  DwC-A file   : %s", DWCA_PATH.name)
    logger.info("  Sites        : %d", dwca_info["n_sites"])
    logger.info("  Species      : %d", dwca_info["n_species"])
    logger.info("  Response     : %s", response_col)
    logger.info("  Grid cells   : %d", len(covariates))
    logger.info("  Covariates   : %s",
                [c for c in covariates.columns
                 if c not in ("Subzone_ID", "geometry")])
    logger.info("  Recommended  : %s", analysis.get("suggested_method", "N/A"))


if __name__ == "__main__":
    main()
