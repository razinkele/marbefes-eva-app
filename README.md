# MARBEFES EVA Phase 2

Ecological Value Assessment (EVA) web application for the [MARBEFES](https://marbefes.eu/) project, funded by the European Union's Horizon Europe Research Programme.

EVA is a framework for evaluating the ecological value of marine areas by scoring ecosystem components (species or habitats) across spatial subzones using 15 standardised Assessment Questions (AQ1-AQ15), producing an Ecological Value (EV) score on a 0-5 scale.

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

1. Go to **Data Input** and upload a CSV file (rows = subzones, columns = features)
2. Optionally upload a spatial grid file (GeoJSON/Shapefile/GeoPackage) with matching `Subzone ID` attributes
3. Configure features in the **EC Features** tab
4. View calculated AQ scores and EV in the **AQ + EV Results** tab
5. Explore aggregated results in the **Total EV** tab
6. See spatial results on the **Map** tab

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
requirements.txt        # Python dependencies
data/
  test_grid.geojson     # Sample hexagonal grid for testing
  sample_data.csv       # Sample CSV dataset
www/
  marbefes.png          # MARBEFES logo
  iecs.png              # IECS logo
docs/plans/             # Design and implementation documents
```

## Requirements

- Python 3.10+
- Dependencies: shiny, pandas, numpy, plotly, openpyxl, uvicorn, geopandas, folium

## Reference

Franco A. and Amorim E. (2025) *Ecological Value Assessment (EVA) - Guidance including FAQs*. MARBEFES WP4.1.

## License

This project is part of the MARBEFES Horizon Europe research programme.
