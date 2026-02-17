# GIS Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add interactive map visualization to the MARBEFES EVA Shiny app so users can see EV/AQ results on a choropleth map of their hexagonal grid.

**Architecture:** Users upload a GeoJSON file (hexagonal grid) alongside their CSV data. GeoPandas joins them by Subzone ID, reprojects to WGS84, and Folium renders an interactive Leaflet map inside the Shiny app. A new "Map" tab provides controls for variable selection, color scheme, classification method, and basemap.

**Tech Stack:** Python Shiny, GeoPandas, Folium, Shapely (already installed: geopandas 1.1.2, shapely 2.1.2; needs install: folium)

**Key files:**
- `app.py` (2233 lines) - the entire Shiny application, both UI and server
- `requirements.txt` (6 lines) - Python dependencies
- No test directory exists yet

**Design doc:** `docs/plans/2026-02-17-gis-integration-design.md`

---

### Task 1: Add folium dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add folium and geopandas to requirements.txt**

Add these lines to `requirements.txt` after the existing dependencies:

```
geopandas>=0.14.0
folium>=0.15.0
```

**Step 2: Install folium**

Run: `pip install folium`
Expected: Successfully installed folium and branca

**Step 3: Verify imports work**

Run: `python -c "import folium; import geopandas; import branca; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add geopandas and folium dependencies for GIS integration"
```

---

### Task 2: Add GeoJSON imports and reactive values

**Files:**
- Modify: `app.py:11-16` (imports section)
- Modify: `app.py:778-786` (server function, reactive values)

**Step 1: Add imports at top of app.py**

After the existing imports (line 16, after `import plotly.express as px`), add:

```python
import geopandas as gpd
import folium
import folium.plugins
import branca.colormap as cm
import json
```

**Step 2: Add reactive values in server function**

After line 786 (`detected_data_type = reactive.Value(None)`), add:

```python
    # GIS reactive values
    geo_data = reactive.Value(None)  # GeoDataFrame with grid geometries
    original_crs = reactive.Value(None)  # Original CRS string from uploaded GeoJSON
    geo_match_info = reactive.Value(None)  # Dict with match statistics
```

**Step 3: Verify app still starts**

Run: `python -m shiny run app.py --port 8000`
Expected: App starts without import errors. Stop with Ctrl+C.

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add GIS imports and reactive values for spatial data"
```

---

### Task 3: Add GeoJSON upload UI to Data Input tab

**Files:**
- Modify: `app.py:526-542` (sidebar of Data Input tab, upload section)

**Step 1: Add GeoJSON upload input**

Find the existing upload section in the Data Input sidebar (around line 526-542). After the `download_template` button (line 541), add a new section for GeoJSON upload:

```python
                ui.hr(),
                ui.div(
                    ui.h5("🗺️ Upload Spatial Grid", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.p(
                        "Optional: Upload a GeoJSON file with your hexagonal grid to enable map visualization.",
                        style="font-size: 0.9rem; color: #6c757d; line-height: 1.6;"
                    ),
                    ui.input_file(
                        "upload_geojson",
                        "Choose GeoJSON File",
                        accept=[".geojson", ".json"],
                        multiple=False,
                        button_label="Browse...",
                    ),
                    ui.p(
                        "Each feature must have a 'Subzone ID' property matching the CSV data.",
                        style="font-size: 0.85rem; color: #ff9800; margin-top: 0.5rem;"
                    ),
                ),
```

**Step 2: Add spatial data preview output below the existing data preview**

Find line 594 (`ui.output_ui("data_preview_ui")`). After it, add:

```python
                ui.output_ui("geo_preview_ui"),
```

**Step 3: Verify app still starts and Data Input tab renders**

Run: `python -m shiny run app.py --port 8000`
Expected: Data Input tab shows the new GeoJSON upload section in the sidebar. The file input is visible. No errors.

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add GeoJSON upload UI to Data Input tab"
```

---

### Task 4: Implement GeoJSON upload handler and validation

**Files:**
- Modify: `app.py` (server function, after the existing `handle_upload` effect around line 1089)

**Step 1: Add GeoJSON upload handler**

After the existing `handle_upload` effect (after line 1089), add the GeoJSON handler:

```python
    @reactive.Effect
    @reactive.event(input.upload_geojson)
    def handle_geojson_upload():
        file_info = input.upload_geojson()
        if file_info is None or len(file_info) == 0:
            return

        file_path = file_info[0]["datapath"]

        try:
            gdf = gpd.read_file(file_path)
        except Exception as e:
            geo_data.set(None)
            logger.error(f"Could not read GeoJSON file: {e}")
            return

        # Store original CRS
        if gdf.crs is not None:
            original_crs.set(str(gdf.crs))
        else:
            original_crs.set("Unknown (no CRS defined)")

        # Reproject to WGS84 for Leaflet if needed
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            try:
                gdf = gdf.to_crs(epsg=4326)
                logger.info(f"Reprojected from {original_crs.get()} to EPSG:4326")
            except Exception as e:
                logger.error(f"CRS reprojection failed: {e}")
                return
        elif gdf.crs is None:
            # Assume WGS84 if no CRS defined
            gdf = gdf.set_crs(epsg=4326)

        # Normalize Subzone ID column
        subzone_col = None
        for col in gdf.columns:
            if col.lower().replace(' ', '').replace('_', '') in ['subzoneid', 'subzone_id', 'id', 'name']:
                subzone_col = col
                break

        if subzone_col is None:
            # Use first non-geometry column
            non_geom_cols = [c for c in gdf.columns if c != 'geometry']
            if non_geom_cols:
                subzone_col = non_geom_cols[0]
            else:
                logger.error("GeoJSON has no attribute columns to use as Subzone ID")
                return

        if subzone_col != 'Subzone ID':
            gdf = gdf.rename(columns={subzone_col: 'Subzone ID'})

        gdf['Subzone ID'] = gdf['Subzone ID'].astype(str).str.strip()

        # Calculate match info with CSV data
        csv_df = uploaded_data.get()
        match_info = {'total_features': len(gdf)}
        if csv_df is not None:
            csv_ids = set(csv_df['Subzone ID'].astype(str).str.strip())
            geo_ids = set(gdf['Subzone ID'])
            matched = csv_ids & geo_ids
            match_info['matched'] = len(matched)
            match_info['csv_only'] = len(csv_ids - geo_ids)
            match_info['geo_only'] = len(geo_ids - csv_ids)
        else:
            match_info['matched'] = 0
            match_info['csv_only'] = 0
            match_info['geo_only'] = 0

        geo_match_info.set(match_info)

        # Keep only Subzone ID and geometry
        gdf = gdf[['Subzone ID', 'geometry']]
        geo_data.set(gdf)
        logger.info(f"GeoJSON loaded: {len(gdf)} features, CRS: {original_crs.get()}")
```

**Step 2: Add the geo preview UI renderer**

After the GeoJSON upload handler, add:

```python
    @output
    @render.ui
    def geo_preview_ui():
        gdf = geo_data.get()
        crs = original_crs.get()
        match_info = geo_match_info.get()

        if gdf is None:
            return ui.div()

        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]

        match_status_html = ""
        if match_info and match_info.get('matched', 0) > 0:
            match_status_html = f"""
                <div style="margin-top: 1rem; padding: 1rem; background: #e8f5e9; border-radius: 8px; border-left: 4px solid #28a745;">
                    <p style="margin: 0; color: #28a745; font-weight: 600;">
                        ✅ {match_info['matched']} subzones matched between CSV and GeoJSON
                    </p>
                    {f'<p style="margin: 0.25rem 0 0; color: #ff9800; font-size: 0.9rem;">⚠️ {match_info["csv_only"]} CSV-only, {match_info["geo_only"]} GeoJSON-only</p>' if match_info.get('csv_only', 0) > 0 or match_info.get('geo_only', 0) > 0 else ''}
                </div>
            """
        elif match_info:
            match_status_html = """
                <div style="margin-top: 1rem; padding: 1rem; background: #fff3e0; border-radius: 8px; border-left: 4px solid #ff9800;">
                    <p style="margin: 0; color: #ff9800; font-weight: 600;">
                        ⚠️ Upload CSV data to see match status
                    </p>
                </div>
            """

        return ui.card(
            ui.card_header("🗺️ Spatial Grid Preview"),
            ui.div(
                ui.div(
                    ui.h5(f"📐 Grid: {len(gdf)} features loaded",
                          style="color: #28a745; font-weight: 600; margin-bottom: 1rem;"),
                    ui.p(
                        f"📍 Original CRS: {crs}",
                        ui.br(),
                        f"🌐 Bounding box: [{bounds[0]:.4f}, {bounds[1]:.4f}] to [{bounds[2]:.4f}, {bounds[3]:.4f}]",
                        ui.br(),
                        f"🔄 Displayed in WGS84 (EPSG:4326)",
                        style="color: #6c757d; line-height: 2;"
                    ),
                    ui.HTML(match_status_html),
                    class_="info-box"
                ),
                style="padding: 1rem;"
            )
        )
```

**Step 3: Verify upload works**

Run the app, upload a test GeoJSON file. Check that the preview card appears showing feature count, CRS, and bounding box.

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: implement GeoJSON upload handler with CRS detection and validation"
```

---

### Task 5: Create the Map tab UI

**Files:**
- Modify: `app.py:727-728` (between Visualization and Method nav_panels)

**Step 1: Add the Map nav_panel**

After the closing of the Visualization `ui.nav_panel` (line 727, the `),`) and before the Method `ui.nav_panel` (line 729), insert the new Map tab:

```python
    ui.nav_panel(
        "🗺️ Map",
        ui.card(
            ui.card_header("🗺️ Spatial Map Visualization"),
            ui.layout_sidebar(
                ui.sidebar(
                    ui.h5("🎛️ Map Controls", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_select(
                        "map_variable",
                        "Display Variable:",
                        choices=["EV", "AQ1", "AQ2", "AQ3", "AQ4", "AQ5", "AQ6", "AQ7",
                                 "AQ8", "AQ9", "AQ10", "AQ11", "AQ12", "AQ13", "AQ14", "AQ15"]
                    ),
                    ui.input_select(
                        "map_color_scheme",
                        "Color Scheme:",
                        choices=["YlOrRd", "Viridis", "Blues", "RdYlGn", "Plasma"]
                    ),
                    ui.input_select(
                        "map_classification",
                        "Classification:",
                        choices=["Continuous", "EVA 5-class (VL/L/M/H/VH)"]
                    ),
                    ui.input_select(
                        "map_basemap",
                        "Basemap:",
                        choices=["CartoDB Positron", "OpenStreetMap", "CartoDB Dark Matter"]
                    ),
                    ui.input_slider(
                        "map_opacity",
                        "Fill Opacity:",
                        min=0.3,
                        max=1.0,
                        value=0.7,
                        step=0.1
                    ),
                    width=280
                ),
                ui.div(
                    ui.output_ui("map_output"),
                    style="min-height: 600px;"
                )
            )
        )
    ),
```

**Step 2: Verify app starts and Map tab is visible**

Run: `python -m shiny run app.py --port 8000`
Expected: Map tab appears in the navbar between Visualization and Method. Shows sidebar controls and empty main panel.

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add Map tab UI with sidebar controls for variable, color, classification"
```

---

### Task 6: Implement the map rendering logic

**Files:**
- Modify: `app.py` (server function, add map helper functions and the map_output renderer)

**Step 1: Add map helper functions**

Add these helper functions inside the `server()` function, after the existing `calculate_ev` function (around line 1554) and before `calculate_results`:

```python
    def auto_zoom_level(bounds):
        """Calculate appropriate zoom level from a GeoDataFrame bounding box [minx, miny, maxx, maxy]."""
        lat_diff = bounds[3] - bounds[1]
        lon_diff = bounds[2] - bounds[0]
        max_diff = max(lat_diff, lon_diff)
        if max_diff > 10:
            return 5
        elif max_diff > 5:
            return 7
        elif max_diff > 1:
            return 9
        elif max_diff > 0.1:
            return 12
        else:
            return 14

    EVA_5CLASS_BINS = [0, 1, 2, 3, 4, 5]
    EVA_5CLASS_COLORS = ['#3288bd', '#99d594', '#e6f598', '#fc8d59', '#d53e4f']
    EVA_5CLASS_LABELS = ['Very Low (0-1)', 'Low (1-2)', 'Medium (2-3)', 'High (3-4)', 'Very High (4-5)']

    BASEMAP_TILES = {
        "CartoDB Positron": "cartodbpositron",
        "OpenStreetMap": "openstreetmap",
        "CartoDB Dark Matter": "cartodbdark_matter",
    }

    COLOR_SCHEMES = {
        "YlOrRd": cm.linear.YlOrRd_09,
        "Viridis": cm.linear.viridis,
        "Blues": cm.linear.Blues_09,
        "RdYlGn": cm.linear.RdYlGn_11,
        "Plasma": cm.linear.plasma,
    }

    def create_ev_map(geo_df, variable, color_scheme_name, classification, basemap_name, opacity):
        """Create a folium choropleth map from a GeoDataFrame with EVA results."""
        bounds = geo_df.total_bounds
        center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
        zoom = auto_zoom_level(bounds)

        tiles = BASEMAP_TILES.get(basemap_name, "cartodbpositron")
        m = folium.Map(location=center, zoom_start=zoom, tiles=tiles)

        # Prepare the variable data - fill NaN with 0 for display
        geo_df = geo_df.copy()
        if variable in geo_df.columns:
            geo_df[variable] = pd.to_numeric(geo_df[variable], errors='coerce').fillna(0)
        else:
            geo_df[variable] = 0

        vmin = geo_df[variable].min()
        vmax = geo_df[variable].max()
        if vmax == vmin:
            vmax = vmin + 1  # Avoid division by zero

        use_5class = classification.startswith("EVA")

        if use_5class:
            def style_function(feature):
                val = feature['properties'].get(variable, 0)
                if val is None:
                    val = 0
                # Assign color based on EVA 5-class bins
                for i in range(len(EVA_5CLASS_BINS) - 1):
                    if val <= EVA_5CLASS_BINS[i + 1]:
                        color = EVA_5CLASS_COLORS[i]
                        break
                else:
                    color = EVA_5CLASS_COLORS[-1]
                return {
                    'fillColor': color,
                    'color': '#333333',
                    'weight': 0.5,
                    'fillOpacity': opacity
                }
        else:
            colormap = COLOR_SCHEMES.get(color_scheme_name, cm.linear.YlOrRd_09)
            colormap = colormap.scale(vmin, vmax)
            colormap.caption = variable

            def style_function(feature):
                val = feature['properties'].get(variable, 0)
                if val is None:
                    val = 0
                return {
                    'fillColor': colormap(val),
                    'color': '#333333',
                    'weight': 0.5,
                    'fillOpacity': opacity
                }

        # Build tooltip fields - show Subzone ID + the selected variable + EV if different
        tooltip_fields = ['Subzone ID', variable]
        tooltip_aliases = ['Subzone:', f'{variable}:']
        if variable != 'EV' and 'EV' in geo_df.columns:
            tooltip_fields.append('EV')
            tooltip_aliases.append('EV:')

        # Round numeric columns for cleaner tooltips
        for col in tooltip_fields:
            if col in geo_df.columns and col != 'Subzone ID':
                geo_df[col] = geo_df[col].round(3)

        folium.GeoJson(
            geo_df.to_json(),
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=tooltip_aliases,
                sticky=True,
                style="font-size: 13px; padding: 8px;"
            )
        ).add_to(m)

        # Add legend
        if use_5class:
            # Manual legend for 5-class
            legend_html = '<div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000; background: white; padding: 12px 16px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.3); font-size: 13px;">'
            legend_html += f'<p style="margin: 0 0 8px; font-weight: 700;">{variable}</p>'
            for i in range(len(EVA_5CLASS_COLORS)):
                legend_html += f'<p style="margin: 2px 0;"><span style="background:{EVA_5CLASS_COLORS[i]}; width:18px; height:14px; display:inline-block; margin-right:6px; border-radius:2px;"></span>{EVA_5CLASS_LABELS[i]}</p>'
            legend_html += '</div>'
            m.get_root().html.add_child(folium.Element(legend_html))
        else:
            colormap.add_to(m)

        # Fullscreen button
        folium.plugins.Fullscreen(position='topright').add_to(m)

        # Fit map to data bounds
        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

        return m._repr_html_()
```

**Step 2: Add the map_output renderer**

Add this after the map helper functions (still inside `server()`), ideally near the end of the server function before the visualization section or after it:

```python
    @output
    @render.ui
    def map_output():
        gdf = geo_data.get()
        results = calculate_results()

        if gdf is None:
            return ui.div(
                ui.div(
                    ui.h4("🗺️ No Spatial Data", style="color: #006994; text-align: center; margin-top: 3rem;"),
                    ui.p(
                        "Upload a GeoJSON file in the Data Input tab to enable map visualization.",
                        style="text-align: center; color: #6c757d; font-size: 1.1rem; max-width: 500px; margin: 1rem auto;"
                    ),
                    ui.div(
                        ui.p("📋 Requirements:", style="font-weight: 600; color: #006994;"),
                        ui.tags.ol(
                            ui.tags.li("Upload your CSV data (species/habitat features)"),
                            ui.tags.li("Upload a GeoJSON file with your hexagonal grid"),
                            ui.tags.li("Ensure 'Subzone ID' properties match between files"),
                        ),
                        style="max-width: 400px; margin: 1.5rem auto; text-align: left; line-height: 2;"
                    ),
                    style="padding: 2rem;"
                )
            )

        if results is None:
            return ui.div(
                ui.p(
                    "⚠️ Calculate EVA results first (upload CSV and select data type) to see values on the map.",
                    style="text-align: center; color: #ff9800; font-size: 1.1rem; padding: 3rem;"
                )
            )

        # Merge results with geometry
        try:
            # Get AQ and EV columns from results
            aq_ev_cols = ['Subzone ID'] + [c for c in results.columns if c.startswith('AQ') or c == 'EV']
            results_subset = results[aq_ev_cols].copy()

            merged = gdf.merge(results_subset, on='Subzone ID', how='inner')

            if len(merged) == 0:
                return ui.div(
                    ui.p(
                        "❌ No matching Subzone IDs found between GeoJSON and CSV data.",
                        style="text-align: center; color: #d32f2f; font-size: 1.1rem; padding: 3rem;"
                    )
                )

            variable = input.map_variable()
            color_scheme = input.map_color_scheme()
            classification = input.map_classification()
            basemap = input.map_basemap()
            opacity = input.map_opacity()

            # Generate the map HTML
            map_html = create_ev_map(merged, variable, color_scheme, classification, basemap, opacity)

            # Stats for info bar
            vals = merged[variable] if variable in merged.columns else pd.Series([0])
            vals = pd.to_numeric(vals, errors='coerce').fillna(0)

            return ui.TagList(
                ui.div(
                    ui.span(f"📊 {variable}: ", style="font-weight: 600; color: #006994;"),
                    ui.span(f"Min={vals.min():.2f}  Mean={vals.mean():.2f}  Max={vals.max():.2f}", style="color: #495057;"),
                    ui.span(f"  |  🗺️ {len(merged)} subzones mapped", style="color: #6c757d; margin-left: 1rem;"),
                    style="padding: 0.75rem 1rem; background: #f8f9fa; border-radius: 8px; margin-bottom: 0.5rem; font-size: 0.95rem;"
                ),
                ui.div(
                    ui.HTML(map_html),
                    style="height: 600px; width: 100%; border-radius: 8px; overflow: hidden; border: 1px solid #dee2e6;"
                )
            )

        except Exception as e:
            logger.error(f"Error generating map: {e}")
            return ui.div(
                ui.p(
                    f"❌ Error generating map: {str(e)}",
                    style="text-align: center; color: #d32f2f; padding: 2rem;"
                )
            )
```

**Step 3: Test end-to-end**

1. Run: `python -m shiny run app.py --port 8000`
2. Upload a CSV file in the Data Input tab
3. Upload a matching GeoJSON file
4. Navigate to the Map tab
5. Expected: Interactive Leaflet map with colored hexagonal cells, hover tooltips showing EV values

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: implement interactive choropleth map rendering with Folium"
```

---

### Task 7: Create a test GeoJSON fixture for manual testing

**Files:**
- Create: `data/test_grid.geojson`

**Step 1: Create a sample GeoJSON grid**

Create a small hexagonal-like grid for testing. This represents 10 subzones in a fictional coastal area (near Klaipeda, Lithuania - relevant to MARBEFES BBT5).

```json
{
  "type": "FeatureCollection",
  "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:EPSG::4326" } },
  "features": [
    {"type": "Feature", "properties": {"Subzone ID": "A0"}, "geometry": {"type": "Polygon", "coordinates": [[[21.05, 55.70], [21.06, 55.71], [21.07, 55.70], [21.07, 55.69], [21.06, 55.68], [21.05, 55.69], [21.05, 55.70]]]}},
    {"type": "Feature", "properties": {"Subzone ID": "A1"}, "geometry": {"type": "Polygon", "coordinates": [[[21.07, 55.70], [21.08, 55.71], [21.09, 55.70], [21.09, 55.69], [21.08, 55.68], [21.07, 55.69], [21.07, 55.70]]]}},
    {"type": "Feature", "properties": {"Subzone ID": "A2"}, "geometry": {"type": "Polygon", "coordinates": [[[21.09, 55.70], [21.10, 55.71], [21.11, 55.70], [21.11, 55.69], [21.10, 55.68], [21.09, 55.69], [21.09, 55.70]]]}},
    {"type": "Feature", "properties": {"Subzone ID": "A3"}, "geometry": {"type": "Polygon", "coordinates": [[[21.06, 55.72], [21.07, 55.73], [21.08, 55.72], [21.08, 55.71], [21.07, 55.70], [21.06, 55.71], [21.06, 55.72]]]}},
    {"type": "Feature", "properties": {"Subzone ID": "A4"}, "geometry": {"type": "Polygon", "coordinates": [[[21.08, 55.72], [21.09, 55.73], [21.10, 55.72], [21.10, 55.71], [21.09, 55.70], [21.08, 55.71], [21.08, 55.72]]]}},
    {"type": "Feature", "properties": {"Subzone ID": "A5"}, "geometry": {"type": "Polygon", "coordinates": [[[21.05, 55.68], [21.06, 55.69], [21.07, 55.68], [21.07, 55.67], [21.06, 55.66], [21.05, 55.67], [21.05, 55.68]]]}},
    {"type": "Feature", "properties": {"Subzone ID": "A6"}, "geometry": {"type": "Polygon", "coordinates": [[[21.07, 55.68], [21.08, 55.69], [21.09, 55.68], [21.09, 55.67], [21.08, 55.66], [21.07, 55.67], [21.07, 55.68]]]}},
    {"type": "Feature", "properties": {"Subzone ID": "A7"}, "geometry": {"type": "Polygon", "coordinates": [[[21.09, 55.68], [21.10, 55.69], [21.11, 55.68], [21.11, 55.67], [21.10, 55.66], [21.09, 55.67], [21.09, 55.68]]]}},
    {"type": "Feature", "properties": {"Subzone ID": "A8"}, "geometry": {"type": "Polygon", "coordinates": [[[21.10, 55.72], [21.11, 55.73], [21.12, 55.72], [21.12, 55.71], [21.11, 55.70], [21.10, 55.71], [21.10, 55.72]]]}},
    {"type": "Feature", "properties": {"Subzone ID": "A9"}, "geometry": {"type": "Polygon", "coordinates": [[[21.11, 55.70], [21.12, 55.71], [21.13, 55.70], [21.13, 55.69], [21.12, 55.68], [21.11, 55.69], [21.11, 55.70]]]}}
  ]
}
```

Note: The existing CSV template in the app generates Subzone IDs A0-A9, which matches this GeoJSON.

**Step 2: Verify the GeoJSON is valid**

Run: `python -c "import geopandas as gpd; gdf = gpd.read_file('data/test_grid.geojson'); print(f'{len(gdf)} features, CRS: {gdf.crs}')"`
Expected: `10 features, CRS: EPSG:4326`

**Step 3: Commit**

```bash
git add data/test_grid.geojson
git commit -m "test: add sample GeoJSON grid fixture for map testing"
```

---

### Task 8: Final integration test and polish

**Files:**
- Modify: `app.py` (minor tweaks if needed)

**Step 1: Full end-to-end test**

1. Run: `python -m shiny run app.py --port 8000`
2. Go to Data Input tab
3. Download the CSV template (generates A0-A9 subzones with zeros)
4. Edit the template to add some non-zero values, or upload `data/test_grid.geojson`
5. Upload both files
6. Select data type (qualitative or quantitative)
7. Navigate to Map tab
8. Verify:
   - Map renders with colored hexagons
   - Hover tooltips show Subzone ID and variable values
   - Changing variable dropdown updates the map
   - Changing color scheme updates colors
   - EVA 5-class classification shows discrete color bands
   - Basemap toggle works
   - Opacity slider works
   - Stats bar shows min/mean/max

**Step 2: Check the spatial data preview on Data Input tab**

Verify:
- GeoJSON preview card appears after upload
- Shows feature count, CRS, bounding box
- Shows match count with CSV data

**Step 3: Commit any polish fixes**

```bash
git add app.py
git commit -m "feat: finalize GIS map integration - Phase 1 complete"
```

---

## Summary

| Task | Description | Files | Estimated Effort |
|------|-------------|-------|-----------------|
| 1 | Add folium dependency | requirements.txt | 2 min |
| 2 | Add imports and reactive values | app.py (imports + server) | 3 min |
| 3 | Add GeoJSON upload UI | app.py (Data Input tab) | 5 min |
| 4 | Implement GeoJSON handler + validation | app.py (server) | 10 min |
| 5 | Create Map tab UI | app.py (navbar) | 5 min |
| 6 | Implement map rendering logic | app.py (server) | 15 min |
| 7 | Create test GeoJSON fixture | data/test_grid.geojson | 3 min |
| 8 | Integration test and polish | app.py | 10 min |

**Total: 8 tasks, ~53 minutes**

Each task produces one commit. The implementation is incremental - the app remains functional after each commit.
