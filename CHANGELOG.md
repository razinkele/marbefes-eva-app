# Changelog

All notable changes to the MARBEFES EVA application are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [3.8.0] - 2026-04-23 "Report Ready"

### Added

- **Physical Accounts: Word (DOCX) export** — new "📝 Download BBT8 Report (Word)" button in the Physical Accounts sidebar generates a styled Word document from the live EUNIS overlay + EVA data: cover page, narrative, 6 styled tables (headline figures, top habitats, detailed extent/condition/supply, missing-values summary), and 7 embedded habitat/indicator maps.
- **New module: `pa_docx.py`** — stateless DOCX renderer (parses Markdown + builds native `python-docx` structure with banded tables and in-memory matplotlib map images). Consumed by both `app.py` and the `scripts/render_pa_lt_docx.py` CLI so the two flows never drift.
- **`scripts/bump_version.py`** — one-shot version bumper that updates `version.py`, `CHANGELOG.md`, `README.md`, `docs/USER_MANUAL.md`, and `docs/TUTORIAL.md` in a single command with `--dry-run` support and 27 tests. UI About dialog + sidebar footer + page title + XLSX/DOCX export metadata all read from `version.py` so they update automatically on the next render.
- **Module-level EVA cache + background prewarm thread** in `app.py` — amortises the 254 MB `ALL4EVA` GeoPackage load across all Shiny sessions on a worker (was reloading once per session = 12–15s on server, 54s on OneDrive-synced local).
- **New SDM helpers in `scripts/sdm_analyse.py`**: `detect_coord_cols` (case-insensitive matching of DwC-A coord aliases: `decimalLatitude`/`decimalLongitude`/`latitude`/`Latitude` etc), `filter_species_columns` (auto-select excludes coord aliases + id columns + date/depth columns), `_align_valid_for_residuals` (mirrors `eva_sdm.prepare_features` drop behaviour so regression kriging doesn't misalign).

### Changed

- **`@render.download` handlers raise `RuntimeError` on error paths instead of `return None`** — Shiny's session-side streaming code iterates over the return value; `None` falls through to the Iterable branch and hangs the half-open connection until shiny-server's hard-coded 45-second socket timeout fires. Raising produces a clean HTTP 500 immediately.
- **`compare_methods` accepts `lat_col` / `lon_col` kwargs** and threads them through to both `eva_sdm._sites_to_metric` and `eva_sdm.fit_kriging`, so DwC-A uploads with aliased coordinate columns work end-to-end.
- **`deploy_to_laguna_razinka.sh`** is now tracked in git (previously gitignored as a "deployment artefact"). Verifies imports against the real runtime `/opt/micromamba/envs/shiny/bin/python3` (not the unused `./venv/` the script builds). Auto-vendors missing runtime deps via `pip install --user` + copy into the app dir with a distribution-name map (`docx`→`python-docx`, `PIL`→`Pillow`, etc). Uploads `scripts/*.py` (previously skipped — caused silent drift).
- **`scripts/compute_physical_accounts.py`, `scripts/generate_pa_report.py`, `scripts/generate_pa_bbt8_report.py`** now import `__version__` from `version.py` instead of hardcoded strings (were drifting 4 major versions out of date; bump script now doesn't need to touch them).
- **`scripts/config.py`** — replaced hardcoded `C:\Users\DELL\…` paths with `EVA_FINAL_DIR` / `EVA_FINAL_CORRECTED_DIR` env-var overrides and a project-root-sibling fallback matching `generate_pa_lt_report.py`.

### Fixed

- **BBT8 Word download was never actually reachable in production** — the EVA GeoPackage was mode 600 in a mode-700 directory; the `shiny` user that runs the app couldn't read it; `cached_eva_data()` silently returned `None`; the handler returned `None` which triggered the 45s Shiny streaming-hang above. Every user who clicked the download button since the feature existed got a blank-response hang. Fix is permission + env-var work on the server (documented in memory + the code now raises cleanly if permissions regress).
- **`analyse_collinearity`** / **`habitat_preference_table`**: `sorted(sites_cov[eunis_col].unique())` raised `TypeError: '<' not supported between 'float' and 'str'` on Python 3.13 / pandas 2.x when the EUNIS column had NaN mixed with habitat codes.
- **Regression kriging residual alignment**: `prepare_features` drops rows where response OR feature is NaN, but the old code rebuilt `valid` dropping only on features, so `valid["__resid__"] = residuals` raised `ValueError` when the response had NaN.
- **SDM species auto-select picked up coordinate columns** from DwC-A uploads (`decimalLatitude`/`decimalLongitude` were being treated as species because the filter only excluded a short `meta_cols` set).
- **Silent failure when every SDM species errored** — the per-species loop caught `Exception` with `logger.warning` and stored an empty `species_results` as if the analysis had succeeded, leaving stale UI state. Now raises a user-visible error and resets stale results.
- **`eva_ui.py:2097`** — duplicate `id="sdm_tabs"` on the wrapper `ui.div` (the inner `ui.navset_tab` already had it). Invalid HTML; broke CSS selector precedence.
- **Local `shiny` micromamba env was missing five packages** listed in `requirements.txt` (`pygam`, `pykrige`, `gstools`, `xgboost`, `lightgbm`). 22 tests in `tests/test_eva_sdm.py` were failing (14) or skipping (8). Installed from conda-forge.
- **Server micromamba env: `lightgbm` import failed** via `dask.array.chunk_types → cupy.ndarray` chain because `zarr` had drifted to 3.1.5 (violating the `zarr<3.0` pin in `requirements.txt`) and had pulled in a stub `cupy` package that was registered as a namespace package. Removed the cupy ghost + downgraded zarr.
- **`scripts/sdm_analyse.compare_methods`: hardcoded `"lat"`/`"lon"`** in `_sites_to_metric` call — fails on any DataFrame using coord-column aliases.
- **Three dead `NotImplementedError` stubs** removed from `pa_calculations.py` (`compute_use_table`, `compute_condition_account`, `compute_extent_changes` — pure trap-holes with zero callers; working implementations live in `scripts/compute_physical_accounts.py`).

### Removed

- **`scripts/generate_pa_docx.py`** — stale 570-line script targeting an obsolete MSFD/HELCOM classification with hardcoded `C:\Users\DELL\` paths. Replaced by the generic `pa_docx.py` + `scripts/render_pa_lt_docx.py` CLI wrapper.

### Tests

- `tests/test_pa_docx.py` — 25 new tests (MD parser, inline-run rendering, DOCX assembly, **structural invariant**: `sectPr` must remain the last element of `<w:body>` across all section injections).
- `tests/test_sdm_analyse.py` — 18 new tests covering every new helper, with `pytest.importorskip("pykrige")` gating the kriging-branch tests so they skip cleanly without pykrige available.
- `tests/test_bump_version.py` — 27 new tests: version math, `read_version_py`/`rewrite_version_py`, changelog entry building, README title-rewrite regression guard against an `\s*$`-ate-the-blank-line bug I hit during live dry-run, full end-to-end CLI runs on `tmp_path` fake trees.
- Overall suite: **389 passed, 0 failed, 0 skipped** across 15 test files (was 25 passed, 14 failed, 8 skipped at session start).

## [3.7.0] - 2026-04-06 "SDM Intelligence"

### Added
- **SDM: Darwin Core Archive (DwC-A) upload** — upload standardised biodiversity sampling data directly into the Species Distribution Modelling workflow; supports both Occurrence-core and Event-core + Occurrence-extension layouts; handles presence/absence, abundance, and auto-detect modes
- **SDM: Sampling site map overlay** — loaded sampling sites appear as colour-coded CircleMarkers on the SDM map (pre-fit centred on data, post-fit overlaid on prediction grid); tooltip shows site ID and response value
- **SDM: Hex grid wireframe overlay** — the analysis grid is drawn as a semi-transparent blue wireframe on all SDM map views (prediction, uncertainty) with Subzone ID tooltips
- **SDM: 📋 Data Analysis tab** — automatic pre-modelling data analysis showing response statistics (n sites, min/max/mean/SD, zero count, prevalence), histogram sparkline, method recommendation with reasoning, and categorical predictor notes; placed as the first tab in the SDM panel
- **SDM: Auto response-type detection** — binary/count/continuous radio button updates automatically when sampling data and response column are selected
- **SDM: Method recommendation engine** — `analyse_sampling_data()` selects optimal SDM method based on sample size, data type, zero-inflation, covariate availability, and prevalence

### Fixed
- **SDM: Categorical encoding consistency** — `prepare_features()` now uses `drop_first=False` and returns `feat_names`; `predict_grid()` aligns grid dummies to training columns using `reindex`, preventing silent shape mismatches when EUNIS categories differ between training data and prediction grid
- **CMEMS: Input validation order** — empty-layers and missing-credentials checks now happen before the `copernicusmarine` import attempt; validation tests pass correctly even when the library is not installed locally
- **CMEMS: zarr v3 / cupy crash** — pinned `zarr<3.0` in `requirements.txt` to prevent zarr v3 pulling in cupy which crashes on CPU-only servers with `NoneType` path error

### Changed
- **UI:** Species Distribution panel moved before Data Input in the sidebar menu for more logical workflow ordering

### Tests
- Added 9 DwC-A SDM tests (`TestReadDwcaForSdm`) covering Event-core, Occurrence-core, abundance/presence/auto modes, coordinate extraction, and info metadata
- All 321 tests now pass (0 failures) with `pykrige` and `pygam` installed; 8 skipped (optional heavy deps)

## [3.5.1] - 2026-03-18 "Test Hardening"

### Added
- 150 tests total — expanded pa_export coverage and math verification tests
- Comprehensive edge-case tests for NaN rescaling and constant-value columns

### Fixed
- Minor test stability improvements across all test modules

## [3.5.0] - 2026-03-18 "Deep EUNIS"

### Added
- **HFS/BH auto-classification** — EUNIS codes automatically mapped to habitat-forming species / biogenic habitat roles
- **EUNIS-aware export** — "EV by Habitat Type" sheet included in Excel export when EUNIS overlay is loaded
- **EUNIS habitat base layer toggle** on the Map tab — display EUNIS habitat polygons underneath EVA results
- BBT8 export button for EUNIS-level physical accounts

## [3.4.1] - 2026-03-18

### Fixed
- **Critical:** Total EV export used SUM aggregation instead of MAX — now correctly uses MAX
- **Critical:** Constant-value columns caused division-by-zero in rescaling — now handled gracefully
- **Critical:** State leak between ECs when switching — reactive values properly isolated
- Removed hardcoded data path — replaced with `MARBEFES_EVA_DATA_PATH` environment variable

## [3.4.0] - 2026-03-18 "EUNIS L3 Integration"

### Added
- **EUNIS L3 overlay upload** — upload a GeoPackage/GeoJSON with EUSeaMap habitat polygons
- Spatial overlay intersects EUNIS polygons with grid cells, assigns dominant habitat per subzone
- **BBT8 physical accounts export** — EUNIS-aware extent and supply tables

## [3.3.1] - 2026-03-18 "Tutorial"

### Added
- **Tutorial dataset** — 5 EC datasets (benthos, fish, habitats, zooplankton, phytoplankton) + spatial grid
- `tutorial/README.txt` with data provenance and citations
- `docs/TUTORIAL.md` — step-by-step walkthrough (~30 min)
- `eunis_l3_lithuanian.gpkg` tutorial file for EUNIS overlay demonstration

## [3.3.0] - 2026-03-18 "Data Repair Pipeline"

### Added
- **6 data repair scripts** for cleaning and preparing EVA_FINAL input data
- Automated detection and repair of common CSV issues (encoding, missing headers, duplicate rows)

## [3.2.0] - 2026-03-17 "Hardening"

### Fixed
- **Security:** XSS sanitisation applied to all user-supplied strings rendered in HTML
- NaN handling improvements across all AQ calculations
- Exception handling tightened — broad `except Exception` replaced with specific types
- Vectorized rescaling operations for improved performance

## [3.1.0] - 2026-03-17 "Modularization"

### Changed
- Split monolithic `app.py` into focused modules: `eva_calculations.py`, `eva_export.py`, `eva_config.py`, `pa_calculations.py`, `pa_export.py`
- Improved import structure and reduced circular dependencies

## [3.0.0] - 2026-03-16 "Physical Accounts"

### Added
- **Physical Accounts module** — SEEA EA physical natural capital accounting
  - Ecosystem Extent Account from spatial grid (EUNIS Level 3 habitats)
  - Supply Table for societal benefits (5 defaults + custom)
  - Habitat type categorical choropleth map visualization
  - Excel export (standalone PA workbook or combined with EVA)
  - Built-in EUNIS Level 3 marine habitat reference (~40 codes)
  - Auto-detection of habitat columns in spatial files
- **Centralized version management** (`version.py`) — single source of truth for all version info
- **Comprehensive user manual** (`docs/USER_MANUAL.md`) linked from the app Help tab
- **CHANGELOG.md** for tracking all releases
- **Unit test suite** — 150 tests covering EVA calculations, PA export, and math verification

### Fixed
- **Critical:** AQ status mapping was wrong — AQ3/4 now correctly linked to RRF, AQ5/6 to NRF
- **Critical:** Absent features (proportion=0) were incorrectly classified as Regularly Occurring
- **Critical:** NaN values filled with 0 before min-max rescaling, biasing quantitative normalization
- **Security:** XSS vulnerability in results table — all user-supplied values now HTML-escaped
- Broad `except Exception` in AQ calculation replaced with targeted `except KeyError`
- CRS reprojection error message now correctly reports file was not loaded
- Shallow-copy aliasing bug in `_auto_update_stored_ec` fixed
- Silent upload failures now show user notifications
- Stale validation report cleared on new upload attempt

### Changed
- `calculate_ev()` vectorized — uses `pandas.max(axis=1)` instead of row-by-row loop
- Only the rescaling variant matching the data type is computed (performance)
- `eva_export.py` refactored to expose `build_workbook()` for PA combined export
- File size validation added for spatial file uploads

## [2.1.2] - 2026-02-18

### Changed
- Modularized codebase: extracted `eva_config.py`, `eva_calculations.py`, `eva_export.py` from monolithic `app.py`
- Removed inline map/badge constants, cleaned up unused imports

## [2.1.1] - 2026-02-17

### Added
- Multi-EC support: save, restore, delete, and aggregate multiple ecosystem components
- Aggregated EV table and per-EC export sheets
- Enhanced Excel export: professional styling, conditional formatting, embedded Plotly charts
- AQ Breakdown by Subzone grouped bar chart with EV line
- AQ Radar Comparison chart with subzone selector
- AQ x Subzone heatmap with score annotations
- Configurable thresholds for LRF, percentile, and display limit
- Feature classification UI redesign with grouped layout and badges
- AQ status badges with explanations and EV info box
- Max AQ cell highlighting in results table
- CSV validation report with user-facing error notifications
- Spatial upload colour-coded match status feedback

## [2.1.0] - 2026-02-17

### Added
- GIS Map tab with interactive choropleth maps (Folium/Leaflet)
  - Continuous and EVA 5-class (VL/L/M/H/VH) colour schemes
  - Multiple basemaps (CartoDB Positron, OpenStreetMap, CartoDB Dark Matter)
  - Adjustable opacity
- Support for GeoJSON, zipped Shapefiles (.zip), and GeoPackage (.gpkg) uploads
- Automatic CRS detection and reprojection to WGS84
- Sample hexagonal grid fixture (`data/test_grid.geojson`)

## [2.0.0] - 2025-10-15

### Added
- Complete reimplementation as Python Shiny application
- All 15 Assessment Questions (AQ1-AQ15) calculation engine
- Ecological Value (EV) computation as MAX of applicable AQs
- Auto-detection of qualitative vs quantitative data
- Interactive Plotly visualizations (bar charts, heatmaps)
- Excel export with multiple sheets
- MARBEFES and IECS branding

### Changed
- Migrated from original Excel-based tool to web application
