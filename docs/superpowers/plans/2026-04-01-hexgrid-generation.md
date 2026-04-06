# Hexagonal Grid Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new "Grid Setup" tab as the first tab in the EVA app, allowing users to upload or draw a polygon boundary and generate an H3 hexagonal grid that feeds into the existing EVA pipeline.

**Architecture:** New module `eva_hexgrid.py` handles H3 grid generation and polygon parsing. UI additions go into `eva_ui.py` as a new `ui.nav_panel` inserted before the Home tab. Server-side handlers in `app.py` wire up the reactive values and effects. Folium + Leaflet Draw provides the interactive drawing surface.

**Tech Stack:** h3 (Uber's H3 library), geopandas, shapely, folium (with Draw plugin), Python Shiny

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `eva_hexgrid.py` | H3 grid generation, polygon parsing, grid preview map |
| Create | `tests/test_eva_hexgrid.py` | Unit tests for grid generation and polygon parsing |
| Modify | `eva_ui.py:480` | Insert new "Grid Setup" nav_panel before Home tab |
| Modify | `app.py:42-65` | Add reactive values and server handlers for grid setup |

---

### Task 1: Install h3 and verify it works

**Files:**
- Modify: (none — environment setup only)

- [ ] **Step 1: Install h3**

Run:
```bash
pip install h3
```

- [ ] **Step 2: Verify h3 works**

Run:
```bash
python -c "import h3; cells = h3.geo_to_cells({'type': 'Polygon', 'coordinates': [[[24.0, 56.0], [24.1, 56.0], [24.1, 56.1], [24.0, 56.1], [24.0, 56.0]]]}, res=8); print(f'OK: {len(cells)} cells')"
```
Expected: `OK: <number> cells` (some positive number)

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: install h3 for hexagonal grid generation"
```

---

### Task 2: Write failing tests for `generate_h3_grid()`

**Files:**
- Create: `tests/test_eva_hexgrid.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_eva_hexgrid.py`:

```python
"""Tests for eva_hexgrid module."""

import pytest
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon


# A small square polygon near Klaipeda, Lithuania (~1km x 1km)
SMALL_POLYGON = Polygon([
    (21.12, 55.70),
    (21.13, 55.70),
    (21.13, 55.71),
    (21.12, 55.71),
    (21.12, 55.70),
])

# A larger polygon (~5km x 5km)
LARGE_POLYGON = Polygon([
    (21.10, 55.68),
    (21.17, 55.68),
    (21.17, 55.73),
    (21.10, 55.73),
    (21.10, 55.68),
])


def _make_gdf(geom, crs="EPSG:4326"):
    return gpd.GeoDataFrame(geometry=[geom], crs=crs)


class TestGenerateH3Grid:
    """Tests for generate_h3_grid()."""

    def test_returns_geodataframe(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        assert isinstance(result, gpd.GeoDataFrame)

    def test_has_subzone_id_column(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        assert "Subzone ID" in result.columns

    def test_has_geometry_column(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        assert "geometry" in result.columns
        assert result.geometry.geom_type.unique().tolist() == ["Polygon"]

    def test_subzone_id_format(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        n = len(result)
        width = max(3, len(str(n)))
        # IDs should be HEX_001, HEX_002, etc. (zero-padded to consistent width)
        assert result["Subzone ID"].iloc[0] == f"HEX_{1:0{width}d}"
        assert result["Subzone ID"].iloc[-1] == f"HEX_{n:0{width}d}"

    def test_subzone_ids_are_unique(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(LARGE_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        assert result["Subzone ID"].is_unique

    def test_crs_is_wgs84(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        result = generate_h3_grid(gdf, resolution=8)
        assert result.crs.to_epsg() == 4326

    def test_nonwgs84_input_reprojected(self):
        """Input in a different CRS should be reprojected automatically."""
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON, crs="EPSG:4326")
        gdf_3857 = gdf.to_crs(epsg=3857)
        result = generate_h3_grid(gdf_3857, resolution=8)
        assert result.crs.to_epsg() == 4326
        assert len(result) > 0

    def test_higher_resolution_more_cells(self):
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(LARGE_POLYGON)
        res7 = generate_h3_grid(gdf, resolution=7)
        res8 = generate_h3_grid(gdf, resolution=8)
        assert len(res8) > len(res7)

    def test_multipolygon_input(self):
        from eva_hexgrid import generate_h3_grid
        mp = MultiPolygon([SMALL_POLYGON, SMALL_POLYGON.buffer(0.02)])
        gdf = _make_gdf(mp)
        result = generate_h3_grid(gdf, resolution=8)
        assert len(result) > 0

    def test_empty_polyfill_raises(self):
        """A tiny polygon that fits no H3 cells should raise ValueError."""
        from eva_hexgrid import generate_h3_grid
        tiny = Polygon([
            (21.12, 55.70),
            (21.12001, 55.70),
            (21.12001, 55.70001),
            (21.12, 55.70001),
            (21.12, 55.70),
        ])
        gdf = _make_gdf(tiny)
        with pytest.raises(ValueError, match="No H3 cells"):
            generate_h3_grid(gdf, resolution=7)


class TestParsDrawnPolygon:
    """Tests for parse_drawn_polygon()."""

    def test_valid_geojson(self):
        from eva_hexgrid import parse_drawn_polygon
        import json
        geojson = json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[21.12, 55.70], [21.13, 55.70],
                                     [21.13, 55.71], [21.12, 55.71],
                                     [21.12, 55.70]]]
                },
                "properties": {}
            }]
        })
        result = parse_drawn_polygon(geojson)
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 1
        assert result.crs.to_epsg() == 4326

    def test_invalid_geojson_raises(self):
        from eva_hexgrid import parse_drawn_polygon
        with pytest.raises(ValueError, match="Invalid"):
            parse_drawn_polygon("not json at all")

    def test_self_intersecting_polygon_fixed(self):
        """Self-intersecting polygons should be made valid."""
        from eva_hexgrid import parse_drawn_polygon
        import json
        # Bowtie polygon (self-intersecting)
        geojson = json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]
                },
                "properties": {}
            }]
        })
        result = parse_drawn_polygon(geojson)
        assert result.geometry.is_valid.all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_eva_hexgrid.py -v
```
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'eva_hexgrid'`

- [ ] **Step 3: Commit**

```bash
git add tests/test_eva_hexgrid.py
git commit -m "test: add failing tests for eva_hexgrid module"
```

---

### Task 3: Implement `eva_hexgrid.py`

**Files:**
- Create: `eva_hexgrid.py`
- Test: `tests/test_eva_hexgrid.py`

- [ ] **Step 1: Write the implementation**

Create `eva_hexgrid.py`:

```python
"""Hexagonal grid generation using Uber H3 for EVA spatial analysis."""

import json
import logging

import geopandas as gpd
import h3
from shapely.geometry import Polygon
from shapely.validation import make_valid

logger = logging.getLogger(__name__)


def generate_h3_grid(polygon_gdf: gpd.GeoDataFrame, resolution: int) -> gpd.GeoDataFrame:
    """Generate H3 hexagonal grid cells covering the given polygon(s).

    Args:
        polygon_gdf: GeoDataFrame with polygon geometry (any CRS).
        resolution: H3 resolution level (7, 8, or 9).

    Returns:
        GeoDataFrame with 'Subzone ID' and 'geometry' columns in EPSG:4326.

    Raises:
        ValueError: If no H3 cells fit within the polygon at the given resolution.
    """
    # Reproject to WGS84 if needed
    gdf = polygon_gdf.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Collect all H3 cell indices across all geometries
    all_cells = set()
    for geom in gdf.geometry:
        if geom is None:
            continue
        # Handle MultiPolygon by iterating sub-geometries
        if geom.geom_type == "MultiPolygon":
            polygons = list(geom.geoms)
        else:
            polygons = [geom]

        for poly in polygons:
            geojson = poly.__geo_interface__
            cells = h3.geo_to_cells(geojson, res=resolution)
            all_cells.update(cells)

    if not all_cells:
        raise ValueError(
            f"No H3 cells fit within the polygon at resolution {resolution}. "
            "Try a finer resolution (higher number)."
        )

    # Convert H3 indices to polygons
    hex_polygons = []
    for cell_id in sorted(all_cells):
        boundary = h3.cell_to_boundary(cell_id)
        # h3 returns (lat, lng) pairs; shapely needs (lng, lat)
        coords = [(lng, lat) for lat, lng in boundary]
        coords.append(coords[0])  # close the ring
        hex_polygons.append(Polygon(coords))

    # Build GeoDataFrame
    width = max(3, len(str(len(hex_polygons))))
    subzone_ids = [f"HEX_{i+1:0{width}d}" for i in range(len(hex_polygons))]
    result = gpd.GeoDataFrame(
        {"Subzone ID": subzone_ids},
        geometry=hex_polygons,
        crs="EPSG:4326",
    )

    logger.info(
        f"Generated {len(result)} H3 cells at resolution {resolution}"
    )
    return result


def parse_drawn_polygon(geojson_str: str) -> gpd.GeoDataFrame:
    """Parse GeoJSON string from Leaflet Draw into a GeoDataFrame.

    Args:
        geojson_str: GeoJSON FeatureCollection string.

    Returns:
        GeoDataFrame with polygon geometry in EPSG:4326.

    Raises:
        ValueError: If the input is not valid GeoJSON.
    """
    try:
        data = json.loads(geojson_str)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Invalid GeoJSON: {exc}") from exc

    try:
        gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Invalid GeoJSON FeatureCollection: {exc}") from exc

    # Fix any invalid geometries
    gdf["geometry"] = gdf["geometry"].apply(
        lambda g: make_valid(g) if g is not None and not g.is_valid else g
    )

    return gdf
```

- [ ] **Step 2: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_eva_hexgrid.py -v
```
Expected: All 13 tests PASS

- [ ] **Step 3: Commit**

```bash
git add eva_hexgrid.py
git commit -m "feat: add eva_hexgrid module for H3 grid generation"
```

---

### Task 4: Add "Grid Setup" UI tab to `eva_ui.py`

**Files:**
- Modify: `eva_ui.py:1-9` (add import)
- Modify: `eva_ui.py:480` (insert new nav_panel before Home)

- [ ] **Step 1: Add the hex preset choices to eva_config.py**

Add at the end of `eva_config.py`:

```python
# H3 hexagonal grid resolution presets
HEX_PRESETS = {
    "small": {"label": "Small (~174m edge, ~0.1 km²)", "resolution": 9},
    "medium": {"label": "Medium (~461m edge, ~0.7 km²)", "resolution": 8},
    "large": {"label": "Large (~1.2km edge, ~5.2 km²)", "resolution": 7},
}
```

- [ ] **Step 2: Add the Grid Setup nav_panel**

In `eva_ui.py`, add the import at line 8 (after the existing `from eva_config import MAX_FEATURES` line):

```python
from eva_config import MAX_FEATURES, HEX_PRESETS
```

Then insert the following `ui.nav_panel(...)` as the **first argument** to `ui.page_navbar(` at line 480, before the existing `ui.nav_panel("🏠 Home", ...)`:

```python
    ui.nav_panel(
        "🔷 Grid Setup",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div(
                    ui.h5("1. Define Study Area", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_radio_buttons(
                        "polygon_source",
                        "Polygon source:",
                        choices={"upload": "Upload boundary file", "draw": "Draw on map"},
                        selected="upload",
                    ),
                    ui.panel_conditional(
                        "input.polygon_source === 'upload'",
                        ui.input_file(
                            "upload_boundary",
                            "Choose Boundary File",
                            accept=[".geojson", ".json", ".zip", ".gpkg"],
                            multiple=False,
                            button_label="Browse...",
                        ),
                        ui.p(
                            "Supported: GeoJSON, Zipped Shapefile (.zip), GeoPackage (.gpkg)",
                            style="font-size: 0.85rem; color: #6c757d; margin-top: 0.3rem;",
                        ),
                    ),
                    ui.panel_conditional(
                        "input.polygon_source === 'draw'",
                        ui.output_ui("draw_map_output"),
                        ui.p(
                            "Use the polygon tool on the map to draw your study area boundary.",
                            style="font-size: 0.85rem; color: #6c757d; margin-top: 0.5rem;",
                        ),
                    ),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("2. Grid Parameters", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_select(
                        "hex_preset",
                        "Hexagon size:",
                        choices={k: v["label"] for k, v in HEX_PRESETS.items()},
                        selected="medium",
                    ),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("3. Generate", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_action_button(
                        "generate_grid",
                        "Generate Grid",
                        class_="btn-primary",
                        style="width: 100%; margin-bottom: 0.5rem;",
                    ),
                    ui.download_button(
                        "download_grid",
                        "Download GeoJSON",
                        class_="btn-outline-secondary",
                        style="width: 100%; margin-bottom: 0.5rem;",
                    ),
                    ui.input_action_button(
                        "use_grid",
                        "Use This Grid →",
                        class_="btn-success",
                        style="width: 100%;",
                    ),
                ),
                width=380,
            ),
            ui.div(
                ui.card(
                    ui.card_header("🔷 Grid Setup"),
                    ui.div(
                        ui.output_ui("grid_status_output"),
                        ui.output_ui("grid_preview_map_output"),
                        style="padding: 1rem;",
                    ),
                ),
                class_="main-content",
            ),
        ),
    ),
```

- [ ] **Step 3: Verify the app starts without errors**

Run:
```bash
python -c "from eva_ui import app_ui; print('UI loaded OK')"
```
Expected: `UI loaded OK`

- [ ] **Step 4: Commit**

```bash
git add eva_config.py eva_ui.py
git commit -m "feat: add Grid Setup tab UI to eva_ui.py"
```

---

### Task 5: Add server-side handlers for Grid Setup in `app.py`

**Files:**
- Modify: `app.py:1-40` (add imports)
- Modify: `app.py:42-65` (add reactive values)
- Modify: `app.py` (add handler functions after line ~65)

- [ ] **Step 1: Add import**

At the top of `app.py`, after the existing imports (around line 20), add:

```python
import eva_hexgrid
from eva_config import HEX_PRESETS
```

- [ ] **Step 2: Add reactive values**

Inside `def server(input, output, session):`, after line 56 (`geo_data_full = reactive.Value(None)`), add:

```python
    # Grid Setup reactive values
    boundary_polygon = reactive.Value(None)   # GeoDataFrame with boundary polygon
    generated_grid = reactive.Value(None)     # GeoDataFrame with generated hex grid
```

- [ ] **Step 3: Add boundary upload handler**

Add after the new reactive values (before the existing `handle_geojson_upload` function):

```python
    # --- Grid Setup handlers ---

    @reactive.Effect
    @reactive.event(input.upload_boundary)
    def handle_boundary_upload():
        file_info = input.upload_boundary()
        if file_info is None or len(file_info) == 0:
            return
        file_path = file_info[0]["datapath"]
        file_name = file_info[0]["name"].lower()
        try:
            if file_name.endswith('.zip'):
                gdf = gpd.read_file(f"zip://{file_path}")
            else:
                gdf = gpd.read_file(file_path)
        except Exception as e:
            ui.notification_show(f"Could not read boundary file: {e}", type="error", duration=8)
            return
        # Reproject to WGS84
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        elif gdf.crs is None:
            gdf = gdf.set_crs(epsg=4326)
        boundary_polygon.set(gdf)
        generated_grid.set(None)
        ui.notification_show(f"Boundary loaded: {len(gdf)} polygon(s)", type="message", duration=4)
```

- [ ] **Step 4: Add draw-on-map handler and output**

```python
    @output
    @render.ui
    def draw_map_output():
        import folium
        import folium.plugins
        m = folium.Map(location=[55.7, 21.1], zoom_start=10, tiles="OpenStreetMap")
        draw = folium.plugins.Draw(
            draw_options={
                "polyline": False,
                "rectangle": True,
                "polygon": True,
                "circle": False,
                "marker": False,
                "circlemarker": False,
            },
            edit_options={"edit": True, "remove": True},
        )
        draw.add_to(m)
        # JavaScript to capture drawn shapes and send to Shiny
        js = """
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            var checkMap = setInterval(function() {
                var mapEl = document.querySelector('.folium-map');
                if (mapEl && mapEl._leaflet_map) {
                    var map = mapEl._leaflet_map;
                    var drawnItems = new L.FeatureGroup();
                    map.eachLayer(function(layer) {
                        if (layer instanceof L.FeatureGroup) {
                            drawnItems = layer;
                        }
                    });
                    map.on('draw:created', function(e) {
                        var geojson = JSON.stringify(drawnItems.toGeoJSON());
                        Shiny.setInputValue('drawn_polygon', geojson, {priority: 'event'});
                    });
                    map.on('draw:edited', function(e) {
                        var geojson = JSON.stringify(drawnItems.toGeoJSON());
                        Shiny.setInputValue('drawn_polygon', geojson, {priority: 'event'});
                    });
                    clearInterval(checkMap);
                }
            }, 500);
        });
        </script>
        """
        map_html = m._repr_html_()
        return ui.HTML(f'<div style="height: 400px;">{map_html}</div>{js}')

    @reactive.Effect
    @reactive.event(input.drawn_polygon)
    def handle_drawn_polygon():
        geojson_str = input.drawn_polygon()
        if not geojson_str:
            return
        try:
            gdf = eva_hexgrid.parse_drawn_polygon(geojson_str)
            if len(gdf) == 0:
                return
            boundary_polygon.set(gdf)
            generated_grid.set(None)
            ui.notification_show("Polygon captured from map", type="message", duration=3)
        except ValueError as e:
            ui.notification_show(f"Invalid polygon: {e}", type="error", duration=6)
```

- [ ] **Step 5: Add grid generation handler**

```python
    @reactive.Effect
    @reactive.event(input.generate_grid)
    def handle_generate_grid():
        boundary = boundary_polygon.get()
        if boundary is None:
            ui.notification_show("Please define a study area first.", type="warning", duration=4)
            return
        preset_key = input.hex_preset()
        resolution = HEX_PRESETS[preset_key]["resolution"]
        try:
            grid = eva_hexgrid.generate_h3_grid(boundary, resolution)
        except ValueError as e:
            ui.notification_show(str(e), type="error", duration=6)
            return
        if len(grid) > 5000:
            ui.notification_show(
                f"Warning: {len(grid)} cells generated. This may be slow. "
                "Consider using a coarser resolution.",
                type="warning", duration=8,
            )
        generated_grid.set(grid)
        ui.notification_show(f"Grid generated: {len(grid)} hexagonal cells", type="message", duration=4)
```

- [ ] **Step 6: Add grid preview, status, download, and "use grid" handlers**

```python
    @output
    @render.ui
    def grid_status_output():
        grid = generated_grid.get()
        boundary = boundary_polygon.get()
        parts = []
        if boundary is not None:
            parts.append(f"Boundary: {len(boundary)} polygon(s)")
        if grid is not None:
            preset_key = input.hex_preset()
            area_per_cell = {9: 0.105, 8: 0.737, 7: 5.161}
            res = HEX_PRESETS[preset_key]["resolution"]
            total_area_km2 = len(grid) * area_per_cell.get(res, 0.737)
            parts.append(f"Grid: {len(grid)} cells, ~{total_area_km2:.1f} km²")
        if not parts:
            return ui.p("Upload a boundary file or draw a polygon on the map to get started.",
                        style="color: #6c757d; font-style: italic;")
        return ui.div(
            *[ui.p(p, style="margin: 0.3rem 0; font-weight: 500;") for p in parts],
            style="padding: 0.5rem; background: #e8f5e9; border-radius: 6px; margin-bottom: 1rem;",
        )

    @output
    @render.ui
    def grid_preview_map_output():
        grid = generated_grid.get()
        boundary = boundary_polygon.get()
        if grid is None and boundary is None:
            return ui.HTML("")
        import folium
        # Determine map center from boundary or grid
        gdf_for_bounds = grid if grid is not None else boundary
        bounds = gdf_for_bounds.total_bounds
        center_lat = (bounds[1] + bounds[3]) / 2
        center_lng = (bounds[0] + bounds[2]) / 2
        from eva_map import auto_zoom_level
        zoom = auto_zoom_level(bounds)
        m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom, tiles="OpenStreetMap")
        # Show boundary
        if boundary is not None:
            folium.GeoJson(
                boundary.__geo_interface__,
                style_function=lambda x: {
                    "fillColor": "transparent",
                    "color": "#ff6600",
                    "weight": 3,
                    "dashArray": "5 5",
                },
                name="Boundary",
            ).add_to(m)
        # Show hex grid
        if grid is not None:
            folium.GeoJson(
                grid.__geo_interface__,
                style_function=lambda x: {
                    "fillColor": "#4da6ff",
                    "color": "#006994",
                    "weight": 1,
                    "fillOpacity": 0.3,
                },
                tooltip=folium.GeoJsonTooltip(fields=["Subzone ID"]),
                name="Hex Grid",
            ).add_to(m)
        folium.LayerControl().add_to(m)
        return ui.HTML(f'<div style="height: 600px;">{m._repr_html_()}</div>')

    @render.download(filename="hex_grid.geojson")
    def download_grid():
        grid = generated_grid.get()
        if grid is None:
            return
        yield grid.to_json()

    @reactive.Effect
    @reactive.event(input.use_grid)
    def handle_use_grid():
        grid = generated_grid.get()
        if grid is None:
            ui.notification_show("Generate a grid first.", type="warning", duration=4)
            return
        geo_data.set(grid[["Subzone ID", "geometry"]])
        geo_data_full.set(grid.copy())
        original_crs.set("EPSG:4326 (WGS84)")
        ui.notification_show(
            f"Grid with {len(grid)} cells loaded into pipeline. Proceed to Data Input.",
            type="message", duration=5,
        )
```

- [ ] **Step 7: Verify the app starts**

Run:
```bash
python -c "from app import app; print('App loaded OK')"
```
Expected: `App loaded OK` (no import errors)

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "feat: add Grid Setup server handlers to app.py"
```

---

### Task 6: Integration test — full round-trip

**Files:**
- Modify: `tests/test_eva_hexgrid.py` (add integration test)

- [ ] **Step 1: Add integration test**

Add to `tests/test_eva_hexgrid.py`:

```python
class TestIntegration:
    """Integration tests: generated grid works with EVA pipeline."""

    def test_grid_has_correct_columns_for_pipeline(self):
        """Generated grid should have exactly the columns the pipeline expects."""
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(LARGE_POLYGON)
        grid = generate_h3_grid(gdf, resolution=8)
        # Pipeline expects at minimum: 'Subzone ID' and 'geometry'
        assert "Subzone ID" in grid.columns
        assert "geometry" in grid.columns
        assert grid["Subzone ID"].dtype == object  # string type

    def test_grid_can_merge_with_sample_csv(self):
        """Grid should merge with CSV data on Subzone ID."""
        import pandas as pd
        from eva_hexgrid import generate_h3_grid
        gdf = _make_gdf(SMALL_POLYGON)
        grid = generate_h3_grid(gdf, resolution=8)
        # Simulate CSV data with matching Subzone IDs
        csv_data = pd.DataFrame({
            "Subzone ID": grid["Subzone ID"].tolist(),
            "Species_A": range(len(grid)),
        })
        merged = grid.merge(csv_data, on="Subzone ID", how="inner")
        assert len(merged) == len(grid)
        assert "Species_A" in merged.columns
```

- [ ] **Step 2: Run all tests**

Run:
```bash
python -m pytest tests/test_eva_hexgrid.py -v
```
Expected: All 15 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_eva_hexgrid.py
git commit -m "test: add integration tests for hex grid pipeline compatibility"
```

---

### Task 7: Manual smoke test

**Files:** (none — verification only)

- [ ] **Step 1: Run the app**

Run:
```bash
python -m shiny run app.py --port 8000
```

- [ ] **Step 2: Verify the Grid Setup tab**

In the browser at `http://localhost:8000`:
1. Confirm "Grid Setup" tab appears first in the navbar
2. Switch to "Upload boundary file" — verify file input appears
3. Switch to "Draw on map" — verify Folium map with draw tools appears
4. Upload a test GeoJSON boundary file (or draw a polygon)
5. Select "Medium" preset and click "Generate Grid"
6. Verify the preview map shows the hex grid
7. Click "Download GeoJSON" — verify file downloads
8. Click "Use This Grid" — verify notification and that Data Input tab recognizes the grid

- [ ] **Step 3: Run the full test suite**

Run:
```bash
python -m pytest tests/ -v
```
Expected: All tests pass (existing + new)

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete hex grid generation feature with Grid Setup tab"
```
