# Polygon Selection + Hexagonal Grid Generation

**Date:** 2026-04-01
**Status:** Draft

## Overview

Add a new first tab to the EVA Algorithms Shiny app that lets users define a study area polygon (by upload or drawing on a map) and generate a hexagonal grid inside it using Uber's H3 library. The generated grid feeds directly into the existing EVA pipeline as `geo_data` and can be downloaded as GeoJSON for reuse.

## Requirements

1. New tab appears as the **first tab** in the navbar, before "Data Input"
2. Users can provide a polygon boundary via **two methods**:
   - **Upload**: GeoJSON, Shapefile (zipped), or GeoPackage file containing one or more polygons
   - **Draw**: Interactive drawing on a Folium map using the Leaflet Draw plugin (polygon tool only)
3. Users select hex cell size from **three presets**:
   - Small: H3 resolution 9 (~174m edge length, ~0.105 km² per cell)
   - Medium: H3 resolution 8 (~461m edge length, ~0.737 km² per cell)
   - Large: H3 resolution 7 (~1.22 km edge length, ~5.161 km² per cell)
4. Each hex cell receives an auto-generated `Subzone ID` (format: `HEX_001`, `HEX_002`, ...)
5. Generated grid is **previewed** on a Folium map before confirmation
6. Users can **download** the grid as GeoJSON
7. Confirming the grid stores it in the `geo_data` reactive value, making it available to all downstream tabs

## Architecture

### New module: `eva_hexgrid.py`

Two public functions:

```python
def generate_h3_grid(polygon_gdf: gpd.GeoDataFrame, resolution: int) -> gpd.GeoDataFrame:
    """
    Generate H3 hexagonal grid cells that cover the given polygon(s).

    Args:
        polygon_gdf: GeoDataFrame with polygon geometry (any CRS, will be reprojected to WGS84)
        resolution: H3 resolution level (7, 8, or 9)

    Returns:
        GeoDataFrame with columns:
        - Subzone ID: str (HEX_001, HEX_002, ...)
        - geometry: Polygon (hex cell boundaries in WGS84 / EPSG:4326)
    """

def parse_drawn_polygon(geojson_str: str) -> gpd.GeoDataFrame:
    """
    Parse GeoJSON string from Leaflet Draw into a GeoDataFrame.

    Args:
        geojson_str: GeoJSON FeatureCollection string from the draw plugin

    Returns:
        GeoDataFrame with polygon geometry in EPSG:4326
    """
```

### Implementation details

**H3 polyfill approach:**
1. Reproject polygon to WGS84 (EPSG:4326) — H3 requires lat/lng
2. Use `h3.geo_to_cells()` (H3 v4 API) to get all H3 cell indices that fall within the polygon
3. Convert each H3 index to a cell boundary polygon via `h3.cell_to_boundary()`
4. Build GeoDataFrame with sequential `Subzone ID` values
5. Include all hex cells whose **center** falls within the polygon (no clipping — keeps cells as regular hexagons for consistent area calculations downstream)

**Draw-on-map implementation:**
1. Create a Folium map with `folium.plugins.Draw` configured for polygon-only drawing
2. Add a JavaScript callback that auto-captures the drawn GeoJSON on draw completion (no separate "Capture" button needed) and sends it to a hidden Shiny input via `Shiny.setInputValue()`
3. Server-side: listen on the input, parse via `parse_drawn_polygon()`, store as reactive value
4. Display the drawn polygon back on the map for confirmation. User can clear and redraw if needed.

### UI layout in `eva_ui.py`

New nav panel added at position 0 in `ui.page_navbar()`:

```
Tab: "Grid Setup" (icon: grid/hexagon)
├── Section: "1. Define Study Area"
│   ├── Radio buttons: "Upload boundary file" / "Draw on map"
│   ├── Conditional panel (upload):
│   │   └── File input (accept: .geojson, .zip, .gpkg)
│   └── Conditional panel (draw):
│       └── Folium map with Leaflet Draw (rendered as ui.HTML, auto-captures on draw completion)
├── Section: "2. Grid Parameters"
│   └── Select input: "Small (~174m)" / "Medium (~461m)" / "Large (~1.2km)"
├── Section: "3. Generate & Preview"
│   ├── "Generate Grid" action button
│   ├── Info text: cell count, total area
│   ├── Folium map showing generated hex grid preview
│   ├── "Download GeoJSON" download button
│   └── "Use This Grid" action button → stores in geo_data, navigates to Data Input
```

### Server-side handlers in `app.py`

New reactive values:
- `boundary_polygon`: GeoDataFrame — the uploaded or drawn polygon
- `generated_grid`: GeoDataFrame — the H3 hex grid (before confirmation)

New reactive effects:
- `handle_boundary_upload()`: reads uploaded file → sets `boundary_polygon`
- `handle_drawn_polygon()`: parses JS input → sets `boundary_polygon`
- `handle_generate_grid()`: calls `generate_h3_grid()` → sets `generated_grid`, renders preview map
- `handle_use_grid()`: copies `generated_grid` into `geo_data` and `geo_data_full`
- `handle_download_grid()`: exports `generated_grid` to GeoJSON file for download

### Data flow

```
[Upload file] ──┐
                 ├──→ boundary_polygon (GeoDataFrame, EPSG:4326)
[Draw on map] ──┘
                         │
                         ▼
              generate_h3_grid(boundary, resolution)
                         │
                         ▼
              generated_grid (GeoDataFrame with Subzone ID + geometry)
                         │
                    ┌────┴─────┐
                    ▼          ▼
            Preview map    Download GeoJSON
                    │
                    ▼
              "Use This Grid" button
                    │
                    ▼
              geo_data reactive value (existing pipeline continues)
```

## Dependencies

**New Python package:**
- `h3` — Uber's H3 hexagonal hierarchical geospatial indexing system

**Existing packages already in use:**
- `geopandas`, `shapely`, `folium`, `json`

## Edge Cases

1. **Very large polygons at high resolution**: H3 res 9 on a large area could generate thousands of cells. Show a warning if cell count exceeds a threshold (e.g., 5000) and ask user to confirm or pick a coarser resolution.
2. **Multi-polygon upload**: If the uploaded file contains multiple polygons, union them into a single boundary before polyfill.
3. **Invalid drawn polygon**: If the user draws a self-intersecting polygon, call `shapely.validation.make_valid()` before proceeding.
4. **CRS handling**: Uploaded files may be in any CRS. Always reproject to EPSG:4326 before H3 operations. Store `original_crs` for reference.
5. **Empty polyfill**: If the polygon is too small for the chosen resolution (no H3 cells fit), show an error and suggest a finer resolution.

## Testing

- Unit tests for `generate_h3_grid()`: known polygon → expected cell count and Subzone ID format
- Unit tests for `parse_drawn_polygon()`: valid and invalid GeoJSON inputs
- Edge case tests: empty polyfill, multi-polygon, self-intersecting polygon
- Integration: verify generated grid is accepted by downstream EVA pipeline (merge with sample CSV data)
