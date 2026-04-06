# Changelog

All notable changes to the MARBEFES EVA application are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

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
