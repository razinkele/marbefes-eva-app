# GIS Integration Design for MARBEFES EVA Application

**Date:** 2026-02-17
**Status:** Approved
**Approach:** Progressive (Phase 1: visualization, then incremental spatial capabilities)
**Stack:** Folium + GeoPandas + Leaflet (via folium HTML rendering in Shiny)

---

## 1. Background

The EVA (Ecological Value Assessment) is fundamentally a spatial assessment. The guidance
document (MARBEFES-WP4.1_EVA Guidance-incl.FAQs_20251017.docx) requires:

- Study areas divided into hexagonal grid cells (250m for benthic ECs, 3km for pelagic)
- EV results mapped across subzones as choropleth maps
- Multi-resolution spatial aggregation when combining ECs at different grid sizes
- Overlay with management zones (MPAs, ICES rectangles) for comparison

The current app.py has zero GIS capability - subzone IDs are plain text, visualization is
bar charts and heatmaps only (Plotly). This design adds spatial visualization and lays the
foundation for future spatial operations.

## 2. Data Architecture

### 2.1 New Inputs

- **GeoJSON upload** (.geojson) - polygon features representing hexagonal or square grid cells
- Each feature must have a `Subzone ID` property matching the CSV data column
- Uploaded alongside the existing CSV (feature/species data)

### 2.2 Data Flow

```
CSV (feature data) ────┐
                        ├──► GeoPandas join by "Subzone ID" ──► GeoDataFrame
GeoJSON (grid) ─────────┘         │
                                  ├──► CRS detection + reproject to WGS84
                                  ├──► Validation (unmatched IDs)
                                  └──► Store as reactive.Value(geo_data)
```

### 2.3 CRS Handling

1. Detect CRS from GeoJSON using `geopandas` on upload
2. If not WGS84 (EPSG:4326), reproject automatically for Leaflet rendering
3. Store original CRS for reference, display in UI
4. On spatial data export, offer original CRS or WGS84
5. Notify user: "Reprojected from EPSG:XXXXX to EPSG:4326 for map display"

### 2.4 Validation

- Warn if Subzone IDs in GeoJSON don't match CSV
- Show count of matched/unmatched IDs
- Allow proceeding with partial matches (only matched subzones shown on map)

### 2.5 Internal Storage

New reactive values:
- `geo_data = reactive.Value(None)` - joined GeoDataFrame
- `original_crs = reactive.Value(None)` - original CRS string

### 2.6 New Dependencies

- `geopandas` - spatial data handling, joins, CRS operations
- `folium` - Leaflet map generation in Python
- `shapely` - geometry operations (transitive via geopandas)
- `branca` - color maps for folium (transitive via folium)

## 3. UI Design - New "Map" Tab

### 3.1 Tab Position

New tab `"Map"` added to the navbar after "Visualization" and before "Method".

### 3.2 Sidebar Controls

| Control | Type | Options | Default |
|---------|------|---------|---------|
| Map variable | Dropdown | EV, AQ1-AQ15, Feature count | EV |
| Color scheme | Dropdown | Viridis, YlOrRd, Blues, RdYlGn, Plasma | Viridis |
| Classification | Dropdown | Continuous, EVA 5-class | Continuous |
| Basemap | Dropdown | OpenStreetMap, CartoDB Positron, CartoDB Dark, Esri Ocean | CartoDB Positron |
| Opacity | Slider | 0.3 - 1.0 | 0.7 |
| Show legend | Toggle | On/Off | On |
| Download map | Button | PNG export | - |

### 3.3 Main Panel

- Interactive Leaflet map (full available width/height)
- Hexagonal grid cells colored by selected variable
- **Hover tooltip**: Subzone ID, selected variable value, EV score
- **Legend**: color scale with value range or 5-class labels
- **Info box**: CRS info, matched subzone count, min/max/mean of displayed variable
- Zoom controls, scale bar, fullscreen button

### 3.4 Data Input Tab Updates

- Add GeoJSON file upload input below the existing CSV upload
- Add a spatial data preview section showing:
  - Number of features in GeoJSON
  - Detected CRS
  - Bounding box coordinates
  - Match status with CSV Subzone IDs

## 4. Map Generation Logic

### 4.1 Core Map Function

```python
def create_ev_map(geo_df, variable, color_scheme, classification, basemap, opacity):
    # Center map on data extent
    bounds = geo_df.total_bounds  # [minx, miny, maxx, maxy]
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    # Create base map
    m = folium.Map(location=center, tiles=basemap, zoom_start=auto_zoom(bounds))

    # Color function based on classification method
    if classification == "EVA 5-class":
        # Discrete: VL(0-1), L(1-2), M(2-3), H(3-4), VH(4-5)
        bins = [0, 1, 2, 3, 4, 5]
        colors = ['#3288bd', '#99d594', '#e6f598', '#fc8d59', '#d53e4f']
    else:
        # Continuous color scale
        colormap = branca.colormap.linear.from_scheme(color_scheme)

    # Add GeoJson layer with styling and tooltips
    folium.GeoJson(
        geo_df.to_json(),
        style_function=lambda feature: {
            'fillColor': get_color(feature['properties'][variable]),
            'color': '#333',
            'weight': 0.5,
            'fillOpacity': opacity
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['Subzone ID', variable],
            aliases=['Subzone:', f'{variable}:'],
            sticky=True
        )
    ).add_to(m)

    # Add legend, scale bar, layer control
    colormap.add_to(m)
    folium.plugins.Fullscreen().add_to(m)

    return m._repr_html_()
```

### 4.2 EVA 5-Class Color Scheme

From EVA guidance Section 2.2.3:

| Class | Range | Label | Color |
|-------|-------|-------|-------|
| Very Low | 0-1 | VL | #3288bd (blue) |
| Low | 1-2 | L | #99d594 (green) |
| Medium | 2-3 | M | #e6f598 (yellow-green) |
| High | 3-4 | H | #fc8d59 (orange) |
| Very High | 4-5 | VH | #d53e4f (red) |

### 4.3 Auto-Zoom Calculation

```python
def auto_zoom(bounds):
    """Calculate appropriate zoom level from bounding box."""
    lat_diff = bounds[3] - bounds[1]
    lon_diff = bounds[2] - bounds[0]
    max_diff = max(lat_diff, lon_diff)
    if max_diff > 10: return 5
    elif max_diff > 5: return 7
    elif max_diff > 1: return 9
    elif max_diff > 0.1: return 12
    else: return 14
```

## 5. Shiny Integration

### 5.1 Map Rendering

The folium map HTML is rendered within Shiny using `ui.output_ui()` + `@render.ui`:

```python
@output
@render.ui
def map_output():
    geo_df = geo_data.get()
    results = calculate_results()
    if geo_df is None or results is None:
        return ui.p("Upload both CSV and GeoJSON data to see the map.")

    # Merge EVA results into GeoDataFrame
    merged = geo_df.merge(results, on='Subzone ID', how='left')

    variable = input.map_variable()
    html = create_ev_map(merged, variable, ...)
    return ui.HTML(html)
```

### 5.2 Map Container Sizing

```python
ui.div(
    ui.output_ui("map_output"),
    style="height: 600px; width: 100%; border-radius: 12px; overflow: hidden;"
)
```

## 6. Phased Roadmap

### Phase 1: Map Visualization (This implementation)

- GeoJSON upload + CSV join by Subzone ID
- CRS detection and automatic reprojection to WGS84
- Choropleth maps for EV, all AQ scores
- EVA 5-class classification and continuous color scales
- Interactive tooltips and legends
- Multiple basemap options
- PNG map export

### Phase 2: Multi-EC Spatial Aggregation

- Upload multiple EC results with different grid sizes
- Spatial join between overlapping grids (weighted by area overlap)
- MAX aggregation across EC-specific EVs (as per guidance)
- Combined Total EV map from multiple resolution grids

### Phase 3: Grid Generation

- Upload study area boundary (polygon)
- Generate hexagonal or square grid cells at specified resolution
- Uses `shapely` or `h3-py` for hexagonal tessellation
- Export generated grid as GeoJSON for use in QGIS

### Phase 4: Spatial Overlay Analysis

- Upload reference layers (MPAs, ICES zones, depth contours)
- Compare EV distribution inside/outside management areas
- Zonal statistics (mean EV by management zone)
- Side-by-side map comparison

## 7. File Structure Changes

```
app.py                          # Modified: new Map tab, GeoJSON handling
requirements.txt                # Modified: add geopandas, folium
```

No new files needed for Phase 1 - all code is added to app.py.

## 8. References

- EVA Guidance: Franco A. and Amorim E. (2025) MARBEFES-WP4.1_EVA Guidance
- Folium docs: https://python-visualization.github.io/folium/
- GeoPandas docs: https://geopandas.org/
- QGIS hexagonal grid tutorial: https://nc-marbefes.iopan.pl/nextcloud/s/retGAGYs97B6fRt
