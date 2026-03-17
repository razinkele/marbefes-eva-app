# Changelog

All notable changes to the MARBEFES EVA application are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

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
- **Unit test suite** for PA calculations (14 tests)

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
