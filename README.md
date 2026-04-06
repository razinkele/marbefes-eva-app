# MARBEFES EVA v3.7.0

Ecological Value Assessment (EVA) web application for the [MARBEFES](https://marbefes.eu/) project, funded by the European Union's Horizon Europe Research Programme.

EVA is a framework for evaluating the ecological value of marine areas by scoring ecosystem components (species or habitats) across spatial subzones using 15 standardised Assessment Questions (AQ1-AQ15), producing an Ecological Value (EV) score on a 0-5 scale.

**Current version:** 3.7.0 "SDM Intelligence" (2026-04-06) | [Changelog](CHANGELOG.md) | [User Manual](docs/USER_MANUAL.md)

## Features

- **Data Input** - Upload CSV data with species/habitat presence-absence or abundance per subzone
- **EC Features** - Configure ecosystem component features, data types (qualitative/quantitative), and rarity settings
- **Assessment Questions** - Automated calculation of all 15 AQs per subzone following the EVA guidance methodology
- **Ecological Value** - EV score computation and aggregation across subzones with Total EV summary
- **Visualization** - Interactive bar charts, heatmaps, and summary statistics (Plotly)
- **GIS Map** - Interactive choropleth maps of EV/AQ scores on spatial grids (Folium/Leaflet)
  - Continuous and EVA 5-class (VL/L/M/H/VH) colour schemes
  - Multiple basemaps, adjustable opacity
  - Supports GeoJSON, zipped Shapefiles, and GeoPackage uploads
  - Automatic CRS detection and reprojection to WGS84
- **Physical Accounts** - SEEA EA physical natural capital accounting
  - Ecosystem Extent Account from spatial grid (EUNIS Level 3 habitats)
  - Supply Table for societal benefits (configurable, 5 defaults)
  - Habitat type categorical map visualization
  - Excel export (standalone or combined with EVA)
- **Species Distribution Modelling (SDM)** - Model and predict species distributions across the study area
  - Upload sampling sites as CSV or Darwin Core Archive (DwC-A)
  - Copernicus Marine (CMEMS) and EUNIS 2019 habitat covariates
  - Methods: IDW, GAM, Ordinary Kriging, Regression Kriging, Random Forest, XGBoost, LightGBM, Gaussian Process, Ensemble
  - 📋 Data Analysis tab — automatic statistics, method recommendation, and categorical variable guidance
  - Interactive prediction and uncertainty maps with hex grid and sampling site overlays
  - Variogram plots and feature importance diagnostics
- **Export** - Download results as Excel or CSV

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
shiny run app.py --port 8790
```

Open http://localhost:8790 in your browser.

## Usage

1. Go to **Species Distribution** to model and predict species distributions from sampling data (CSV or DwC-A)
2. Go to **Data Input** and upload a CSV file (rows = subzones, columns = features)
3. Optionally upload a spatial grid file (GeoJSON/Shapefile/GeoPackage) with matching `Subzone ID` attributes
4. Configure features in the **EC Features** tab
5. View calculated AQ scores and EV in the **AQ + EV Results** tab
6. Explore aggregated results in the **Total EV** tab
7. See spatial results on the **Map** tab

## Data Format

### CSV (required)

| Subzone ID | Habitat1 | Habitat2 | Habitat3 |
|------------|----------|----------|----------|
| A0         | 1        | 0        | 1        |
| A1         | 0        | 1        | 0        |
| A2         | 1        | 1        | 0        |

- First column: `Subzone ID` (grid cell identifiers)
- Remaining columns: feature presence/absence (0/1) or abundance values
- A template can be downloaded from within the app

### Spatial Grid (optional)

Upload a polygon grid where each feature has a `Subzone ID` property matching the CSV:

- **GeoJSON** (`.geojson`, `.json`)
- **Zipped Shapefile** (`.zip` containing `.shp`, `.dbf`, `.shx`, `.prj`)
- **GeoPackage** (`.gpkg`)

A sample grid is provided at `data/test_grid.geojson` with 10 hexagonal cells near the Lithuanian coast.

## Project Structure

```
app.py                  # Main Shiny application (UI + server)
eva_config.py           # EVA constants and metadata
version.py              # Centralized version management
eva_calculations.py     # EVA calculation functions
eva_export.py           # EVA Excel export
eva_map.py              # GIS map helpers
eva_ui.py               # UI component definitions
eva_sdm.py              # Species Distribution Modelling engine
eva_cmems.py            # Copernicus Marine covariate fetcher
eva_hexgrid.py          # Hexagonal grid generation
eva_eunis_wms.py        # EUNIS WMS covariate extraction
eva_visualizations.py   # Plotly chart helpers
dwca_reader.py          # Darwin Core Archive parser
pa_config.py            # Physical Accounts constants and EUNIS reference
pa_calculations.py      # Physical Accounts calculation functions
pa_export.py            # Physical Accounts Excel export
requirements.txt        # Python dependencies
CHANGELOG.md            # Release history
tests/                  # Unit tests (321 passing)
data/
  test_grid.geojson     # Sample hexagonal grid for testing
  sample_data.csv       # Sample CSV dataset
www/
  marbefes.png          # MARBEFES logo
  iecs.png              # IECS logo
docs/
  USER_MANUAL.md        # Comprehensive user manual
  plans/                # Implementation plans
  specs/                # Design specifications
```

## Requirements

- Python 3.10+
- Core: `shiny`, `pandas`, `numpy`, `plotly`, `openpyxl`, `geopandas`, `folium`
- SDM: `scikit-learn`, `pygam`, `pykrige`, `xgboost`, `lightgbm`, `scipy`
- CMEMS: `copernicusmarine`, `xarray` (server-side; free registration at marine.copernicus.eu)

## Reference

Franco A. and Amorim E. (2025) *Ecological Value Assessment (EVA) - Guidance including FAQs*. MARBEFES WP4.1.

## License

This project is part of the MARBEFES Horizon Europe research programme.
