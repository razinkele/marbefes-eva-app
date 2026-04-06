"""
MARBEFES Ecological Value Assessment (EVA) - Phase 2
Python Shiny Application

This application implements Phase 2 of the ECOLOGICAL VALUE ASSESSMENT (EVA) framework
for the MARBEFES project.

Based on: Franco A. and Amorim E. (2025) Ecological Value Assessment (EVA)
"""

from shiny import App, ui, render, reactive
import pandas as pd
import numpy as np
from pathlib import Path
import io
import os
import logging
import geopandas as gpd
from html import escape as html_escape
import eva_calculations
import eva_export
import eunis_data
import pa_config
import pa_calculations
import pa_export
import eva_visualizations
import eva_map
import eva_hexgrid
import dwca_reader
from eva_ui import app_ui, get_aq_guide_html

from version import get_version

from eva_config import (
    MAX_FEATURES, PREVIEW_ROWS_LIMIT, RESULTS_DISPLAY_LIMIT, MAX_FILE_SIZE_MB,
    ACRONYMS, CLASSIFICATION_BADGE_COLORS, ECEntry, HEX_PRESETS,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def server(input, output, session):

    # Reactive values for storing data
    uploaded_data = reactive.Value(None)

    # Store a dictionary of feature classifications from user input
    feature_classifications = reactive.Value({})

    detected_data_type = reactive.Value(None)

    # GIS reactive values
    geo_data = reactive.Value(None)  # GeoDataFrame with grid geometries
    original_crs = reactive.Value(None)  # Original CRS string from uploaded GeoJSON
    geo_match_info = reactive.Value(None)  # Dict with match statistics
    geo_data_full = reactive.Value(None)  # Full GeoDataFrame with all attributes (for PA module)
    validation_report = reactive.Value(None)

    # Grid Setup reactive values
    boundary_polygon = reactive.Value(None)   # GeoDataFrame with boundary polygon
    generated_grid = reactive.Value(None)     # GeoDataFrame with generated hex grid

    # DwC-A state
    dwca_info = reactive.Value(None)   # DwC-A summary dict or None if CSV

    # Multi-EC support
    ec_store = reactive.Value({})      # {ec_name: {data, data_type, classifications, results, feature_count}}
    current_ec = reactive.Value(None)  # Name of the active EC

    # Acronyms table
    @output
    @render.table
    def acronyms_table():
        return pd.DataFrame(ACRONYMS)

    # AQ Guide Content
    @output
    @render.ui
    def aq_guide_content():
        return ui.HTML(get_aq_guide_html())

    # Download CSV template
    @render.download(filename="data_template.csv")
    def download_template():
        template_data = {
            "Subzone ID": [f"A{i}" for i in range(10)],
            "Feature1": [0] * 10,
            "Feature2": [0] * 10,
            "Feature3": [0] * 10,
            "Feature4": [0] * 10,
            "Feature5": [0] * 10
        }
        df = pd.DataFrame(template_data)
        return io.StringIO(df.to_csv(index=False))
    
    # DwC-A options UI (shown only when a DwC-A file is detected)
    @output
    @render.ui
    def dwca_options_ui():
        info = dwca_info.get()
        if info is None:
            return ui.TagList()
        return ui.div(
            ui.hr(style="margin: 0.8rem 0;"),
            ui.h6("🦠 Darwin Core Archive Detected", style="color: #006994; font-weight: 600;"),
            ui.p(
                f"{info['event_count']} events, "
                f"{info['species_count']} species, "
                f"{info['occurrence_count']} occurrences",
                style="font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;"
            ),
            ui.input_select(
                "dwca_value_mode",
                "Value mode:",
                choices={
                    "abundance": "Abundance (individualCount)" if info["has_abundance"] else "Abundance (not available — defaults to 1)",
                    "presence": "Presence / Absence (0/1)",
                },
                selected="abundance" if info["has_abundance"] else "presence",
            ),
            ui.input_action_button(
                "dwca_load",
                "📥 Load DwC-A Data",
                class_="btn-primary btn-sm",
                style="width: 100%; margin-top: 0.5rem;"
            ),
        )

    # Handle file upload
    @reactive.Effect
    @reactive.event(input.upload_data)
    def handle_upload():
        file_info = input.upload_data()
        if file_info is not None and len(file_info) > 0:
            file_path = file_info[0]["datapath"]

            # Reset stale validation report and match info from previous upload
            validation_report.set(None)
            dwca_info.set(None)
            geo_match_info.set(None)

            # Use the original filename (not the server temp path) for type detection
            original_name = file_info[0].get("name", "").lower()

            # Validate file size
            try:
                file_size_bytes = os.path.getsize(file_path)
                file_size_mb = file_size_bytes / (1024 * 1024)

                if file_size_mb > MAX_FILE_SIZE_MB:
                    uploaded_data.set(None)
                    ui.notification_show(f"File too large ({file_size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB.", type="error", duration=8)
                    return
            except Exception as e:
                logger.error(f"Could not check file size: {e}")
                ui.notification_show(f"Could not process uploaded file: {e}", type="error", duration=8)
                return

            # Check if this is a DwC-A zip (use original filename, not temp path)
            if original_name.endswith(".zip"):
                if dwca_reader.is_dwca_zip(file_path):
                    try:
                        summary = dwca_reader.get_dwca_summary(file_path)
                        summary["_file_path"] = file_path
                        summary["_file_size_mb"] = round(file_size_mb, 2)
                        dwca_info.set(summary)
                        ui.notification_show(
                            f"DwC-A detected: {summary['event_count']} events, "
                            f"{summary['species_count']} species. "
                            "Select value mode and click 'Load DwC-A Data'.",
                            type="message", duration=6,
                        )
                    except Exception as e:
                        logger.error(f"Could not parse DwC-A: {e}")
                        ui.notification_show(f"Could not parse Darwin Core Archive: {e}", type="error", duration=8)
                    return
                else:
                    uploaded_data.set(None)
                    ui.notification_show(
                        "This zip file is not a Darwin Core Archive (no meta.xml found). "
                        "For data upload, use a CSV file or a DwC-A zip.",
                        type="error", duration=8,
                    )
                    return

            # Reject non-CSV, non-ZIP files before attempting to parse
            if not original_name.endswith(".csv"):
                uploaded_data.set(None)
                ui.notification_show(
                    f"Unsupported file type. Please upload a CSV file or a DwC-A ZIP.",
                    type="error", duration=8,
                )
                return

            # Read CSV and handle missing data
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                uploaded_data.set(None)
                ui.notification_show(f"Could not read CSV file: {e}", type="error", duration=8)
                return

            _ingest_dataframe(df, file_size_mb)

    @reactive.Effect
    @reactive.event(input.dwca_load)
    def handle_dwca_load():
        """Load and pivot DwC-A data when user clicks the load button."""
        info = dwca_info.get()
        if info is None:
            return
        file_path = info.get("_file_path")
        if not file_path or not os.path.exists(file_path):
            ui.notification_show("Upload file is no longer available. Please re-upload.", type="error", duration=6)
            return
        try:
            value_mode = input.dwca_value_mode()
        except Exception:
            value_mode = "abundance"
        try:
            df = dwca_reader.read_dwca(file_path, value_column=value_mode)
        except Exception as e:
            logger.error(f"Could not load DwC-A data: {e}")
            ui.notification_show(f"Failed to load DwC-A data: {e}", type="error", duration=8)
            return

        _ingest_dataframe(df, info.get("_file_size_mb", 0), source="dwca")

        # Auto-extract spatial data from DwC-A event coordinates
        geo_msg = ""
        if info.get("has_coordinates"):
            try:
                gdf = dwca_reader.extract_geodataframe(file_path)
                if gdf is not None and not gdf.empty:
                    original_crs.set("EPSG:4326 (WGS84)")
                    # Compute match info
                    csv_ids = set(df['Subzone ID'].astype(str).str.strip())
                    geo_ids = set(gdf['Subzone ID'])
                    matched = csv_ids & geo_ids
                    geo_match_info.set({
                        'total_features': len(gdf),
                        'matched': len(matched),
                        'csv_only': len(csv_ids - geo_ids),
                        'geo_only': len(geo_ids - csv_ids),
                        'csv_only_ids': sorted(list(csv_ids - geo_ids))[:20],
                        'geo_only_ids': sorted(list(geo_ids - csv_ids))[:20],
                    })
                    geo_data_full.set(gdf.copy())
                    geo_data.set(gdf[['Subzone ID', 'geometry']])
                    geo_msg = f" + {len(gdf)} point locations mapped"
            except Exception as e:
                logger.warning(f"Could not extract DwC-A coordinates: {e}")

        ui.notification_show(
            f"DwC-A loaded: {len(df)} subzones x "
            f"{len([c for c in df.columns if c != 'Subzone ID'])} species "
            f"({value_mode} mode){geo_msg}",
            type="message", duration=5,
        )

    def _ingest_dataframe(df: pd.DataFrame, file_size_mb: float, source: str = "csv"):
        """Common pipeline for cleaning and ingesting a DataFrame (CSV or DwC-A)."""
        # Clean up the data:
        # 1. Replace any string variations of NA/missing with NaN
        df = df.replace(['NA', 'N/A', 'na', 'n/a', 'null', 'NULL', 'None', ''], np.nan)

        # 2. Ensure Subzone ID column exists and is clean
        if 'Subzone ID' not in df.columns:
            possible_id_cols = [col for col in df.columns if 'id' in col.lower() or 'subzone' in col.lower()]
            if possible_id_cols:
                df = df.rename(columns={possible_id_cols[0]: 'Subzone ID'})
            else:
                df['Subzone ID'] = [f"S{i+1}" for i in range(len(df))]

        df = df.dropna(subset=['Subzone ID'])
        df['Subzone ID'] = df['Subzone ID'].astype(str).str.strip()
        original_dup_count = int(df.duplicated(subset=['Subzone ID']).sum())
        df = df.drop_duplicates(subset=['Subzone ID'])

        # 3. Convert feature columns to numeric, but preserve NaN
        feature_cols = [col for col in df.columns if col != 'Subzone ID']
        for col in feature_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 4. Sort by Subzone ID for consistent ordering
        df = df.sort_values('Subzone ID').reset_index(drop=True)

        uploaded_data.set(df)

        # Build validation report
        feature_cols = [col for col in df.columns if col != 'Subzone ID']
        report = {
            'rows': len(df),
            'columns': len(feature_cols),
            'features': feature_cols,
            'missing': {col: int(df[col].isna().sum()) for col in feature_cols},
            'missing_pct': {col: round(df[col].isna().sum() / len(df) * 100, 1) for col in feature_cols},
            'non_numeric': [col for col in feature_cols if not pd.api.types.is_numeric_dtype(df[col])],
            'duplicate_ids': original_dup_count,
            'file_size_mb': round(file_size_mb, 2),
            'source': source,
        }
        validation_report.set(report)

        # Automatically detect data type
        auto_detected_type = eva_calculations.detect_data_type(df)
        detected_data_type.set(auto_detected_type)

        # Update the input selector to the detected type
        ui.update_select("data_type", selected=auto_detected_type)

    # Validation report UI
    @output
    @render.ui
    def validation_report_ui():
        report = validation_report.get()
        if report is None:
            return ui.TagList()

        items = []
        items.append(ui.p(
            f"✅ Loaded {report['rows']} subzones × {report['columns']} features ({report['file_size_mb']} MB)",
            style="color: #28a745; font-weight: 600; margin-bottom: 0.5rem;"
        ))

        if report['duplicate_ids'] > 0:
            items.append(ui.p(
                f"⚠️ {report['duplicate_ids']} duplicate Subzone IDs were removed",
                style="color: #ff9800;"
            ))
        if report['non_numeric']:
            items.append(ui.p(
                f"⚠️ Non-numeric columns: {', '.join(report['non_numeric'])}",
                style="color: #ff9800;"
            ))

        cols_with_missing = {k: v for k, v in report['missing'].items() if v > 0}
        if cols_with_missing:
            items.append(ui.p(
                f"ℹ️ {len(cols_with_missing)} columns have missing values (treated as 0):",
                style="color: #2196F3; margin-top: 0.5rem;"
            ))
            for col, count in list(cols_with_missing.items())[:5]:
                pct = report['missing_pct'][col]
                items.append(ui.p(
                    f"  • {col}: {count} missing ({pct}%)",
                    style="color: #6c757d; margin-left: 1rem; margin-bottom: 0.2rem;"
                ))
            if len(cols_with_missing) > 5:
                items.append(ui.p(
                    f"  ... and {len(cols_with_missing) - 5} more",
                    style="color: #6c757d; margin-left: 1rem;"
                ))
        else:
            items.append(ui.p("✅ No missing values detected", style="color: #28a745;"))

        return ui.card(
            ui.card_header("📋 Data Validation Report"),
            ui.div(*items, style="padding: 1rem;")
        )

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

    @output
    @render.ui
    def draw_map_output():
        import folium
        import folium.plugins
        from branca.element import MacroElement, Template
        m = folium.Map(location=[55.7, 21.1], zoom_start=10, tiles="OpenStreetMap")
        # Create the draw feature group and draw control
        draw_fg = folium.FeatureGroup(name="drawn_items")
        draw_fg.add_to(m)
        draw = folium.plugins.Draw(
            draw_options={
                "polyline": False,
                "rectangle": True,
                "polygon": True,
                "circle": False,
                "marker": False,
                "circlemarker": False,
            },
            edit_options={"edit": True, "remove": True, "featureGroup": "placeholder"},
        )
        draw.add_to(m)
        # Inject JS into the Folium map to capture drawn shapes and post to parent
        js_bridge = MacroElement()
        js_bridge._template = Template("""
            {% macro script(this, kwargs) %}
            (function(){
                var map = {{ this._parent.get_name() }};
                var drawnItems = new L.FeatureGroup();
                map.addLayer(drawnItems);

                // Override the draw control's featureGroup
                map.eachLayer(function(layer) {
                    if (layer.options && layer.options.draw) {
                        layer.options.edit = layer.options.edit || {};
                        layer.options.edit.featureGroup = drawnItems;
                    }
                });

                map.on(L.Draw.Event.CREATED, function(e) {
                    drawnItems.addLayer(e.layer);
                    var geojson = JSON.stringify(drawnItems.toGeoJSON());
                    // Post to parent Shiny app (Folium renders in an iframe)
                    if (window.parent && window.parent.Shiny) {
                        window.parent.Shiny.setInputValue('drawn_polygon', geojson, {priority: 'event'});
                    }
                });
                map.on(L.Draw.Event.EDITED, function(e) {
                    var geojson = JSON.stringify(drawnItems.toGeoJSON());
                    if (window.parent && window.parent.Shiny) {
                        window.parent.Shiny.setInputValue('drawn_polygon', geojson, {priority: 'event'});
                    }
                });
                map.on(L.Draw.Event.DELETED, function(e) {
                    var geojson = JSON.stringify(drawnItems.toGeoJSON());
                    if (window.parent && window.parent.Shiny) {
                        window.parent.Shiny.setInputValue('drawn_polygon', geojson, {priority: 'event'});
                    }
                });
            })();
            {% endmacro %}
        """)
        js_bridge.add_to(m)
        map_html = m._repr_html_()
        return ui.HTML(f'<div style="height: 500px;">{map_html}</div>')

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
        # Auto-load into the map pipeline so the Map tab shows it immediately
        geo_data.set(grid[["Subzone ID", "geometry"]])
        geo_data_full.set(grid.copy())
        original_crs.set("EPSG:4326 (WGS84)")
        # Update match info if CSV data is already loaded
        csv_df = uploaded_data.get()
        if csv_df is not None:
            csv_ids = set(csv_df["Subzone ID"].astype(str).str.strip())
            geo_ids = set(grid["Subzone ID"])
            matched = csv_ids & geo_ids
            geo_match_info.set({
                'total_features': len(grid),
                'matched': len(matched),
                'csv_only': len(csv_ids - geo_ids),
                'geo_only': len(geo_ids - csv_ids),
                'csv_only_ids': sorted(list(csv_ids - geo_ids))[:20],
                'geo_only_ids': sorted(list(geo_ids - csv_ids))[:20],
            })
        ui.notification_show(f"Grid generated: {len(grid)} hexagonal cells — visible on Map tab", type="message", duration=5)

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

    # Handle spatial file upload (GeoJSON, Shapefile ZIP, GeoPackage)
    @reactive.Effect
    @reactive.event(input.upload_geojson)
    def handle_geojson_upload():
        file_info = input.upload_geojson()
        if file_info is None or len(file_info) == 0:
            return

        file_path = file_info[0]["datapath"]
        file_name = file_info[0]["name"].lower()

        # Validate file size
        try:
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                ui.notification_show(f"Spatial file too large ({file_size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB.", type="error", duration=8)
                return
        except Exception as e:
            logger.error(f"Could not check spatial file size: {e}")
            ui.notification_show(f"Could not process spatial file: {e}", type="error", duration=8)
            return

        try:
            if file_name.endswith('.zip'):
                # Zipped shapefile - read via zip:// protocol
                gdf = gpd.read_file(f"zip://{file_path}")
            else:
                # GeoJSON, GeoPackage, or other formats geopandas supports
                gdf = gpd.read_file(file_path)
        except Exception as e:
            geo_data.set(None)
            ui.notification_show(f"Could not read spatial file: {e}", type="error", duration=8)
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
                ui.notification_show(f"CRS reprojection failed: {e}. Spatial file could not be loaded.", type="error", duration=8)
                return
        elif gdf.crs is None:
            gdf = gdf.set_crs(epsg=4326)

        # Normalize Subzone ID column
        subzone_col = None
        for col in gdf.columns:
            if col.lower().replace(' ', '').replace('_', '') in ['subzoneid', 'subzone_id', 'id', 'name']:
                subzone_col = col
                break

        if subzone_col is None:
            non_geom_cols = [c for c in gdf.columns if c != 'geometry']
            if non_geom_cols:
                subzone_col = non_geom_cols[0]
            else:
                logger.error("GeoJSON has no attribute columns to use as Subzone ID")
                ui.notification_show("Spatial file has no attribute columns for Subzone ID matching.", type="error", duration=8)
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
            csv_only = csv_ids - geo_ids
            geo_only = geo_ids - csv_ids
            match_info['matched'] = len(matched)
            match_info['csv_only'] = len(csv_only)
            match_info['geo_only'] = len(geo_only)
            match_info['csv_only_ids'] = sorted(list(csv_only))[:20]
            match_info['geo_only_ids'] = sorted(list(geo_only))[:20]
        else:
            match_info['matched'] = 0
            match_info['csv_only'] = 0
            match_info['geo_only'] = 0

        geo_match_info.set(match_info)

        # Store full GeoDataFrame for Physical Accounts habitat auto-detection
        geo_data_full.set(gdf.copy())

        # Keep only Subzone ID and geometry
        gdf = gdf[['Subzone ID', 'geometry']]
        geo_data.set(gdf)
        logger.info(f"GeoJSON loaded: {len(gdf)} features, CRS: {original_crs.get()}")

    # GeoJSON spatial preview
    def _render_unmatched_ids(match_info: dict) -> ui.Tag | None:
        """Return a <details> widget listing CSV-only and GeoJSON-only IDs, or None."""
        if not (match_info.get('csv_only_ids') or match_info.get('geo_only_ids')):
            return None
        unmatched_items = []
        if match_info.get('csv_only_ids'):
            unmatched_items.append(ui.p(
                f"CSV-only IDs: {', '.join(str(x) for x in match_info['csv_only_ids'])}",
                style="color: #6c757d; font-size: 0.85rem; margin: 0.3rem 0;"
            ))
        if match_info.get('geo_only_ids'):
            unmatched_items.append(ui.p(
                f"GeoJSON-only IDs: {', '.join(str(x) for x in match_info['geo_only_ids'])}",
                style="color: #6c757d; font-size: 0.85rem; margin: 0.3rem 0;"
            ))
        return ui.div(
            ui.tags.details(
                ui.tags.summary("Show unmatched IDs"),
                *unmatched_items
            ),
            style="margin-top: 0.5rem;"
        )

    @output
    @render.ui
    def geo_preview_ui():
        gdf = geo_data.get()
        crs = original_crs.get()
        match_info = geo_match_info.get()

        if gdf is None:
            return ui.div()

        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]

        items = []
        items.append(ui.h5(f"📐 Grid: {len(gdf)} features loaded",
                          style="color: #28a745; font-weight: 600; margin-bottom: 1rem;"))
        items.append(ui.p(
            f"📍 Original CRS: {crs}",
            ui.br(),
            f"🌐 Bounding box: [{bounds[0]:.4f}, {bounds[1]:.4f}] to [{bounds[2]:.4f}, {bounds[3]:.4f}]",
            ui.br(),
            "🔄 Displayed in WGS84 (EPSG:4326)",
            style="color: #6c757d; line-height: 2;"
        ))

        if match_info and match_info.get('matched', 0) > 0:
            # Determine match quality
            if match_info['csv_only'] == 0 and match_info['geo_only'] == 0:
                match_style = "color: #28a745; font-weight: 600;"
                match_text = f"✅ {match_info['matched']} subzones fully matched"
            elif match_info['matched'] > 0:
                match_style = "color: #ff9800; font-weight: 600;"
                match_text = f"⚠️ {match_info['matched']} matched, {match_info['csv_only']} CSV-only, {match_info['geo_only']} GeoJSON-only"
            else:
                match_style = "color: #d32f2f; font-weight: 600;"
                match_text = "🔴 No matching Subzone IDs found"

            items.append(ui.p(match_text, style=match_style))

            unmatched_widget = _render_unmatched_ids(match_info)
            if unmatched_widget:
                items.append(unmatched_widget)
        elif match_info:
            # No matched IDs — could be no CSV uploaded or truly zero matches
            if match_info.get('matched', 0) == 0 and (match_info.get('csv_only', 0) > 0 or match_info.get('geo_only', 0) > 0):
                match_style = "color: #d32f2f; font-weight: 600;"
                match_text = "🔴 No matching Subzone IDs found"
                items.append(ui.p(match_text, style=match_style))
                unmatched_widget = _render_unmatched_ids(match_info)
                if unmatched_widget:
                    items.append(unmatched_widget)
            else:
                items.append(ui.p("⚠️ Upload CSV data to see match status",
                                  style="color: #ff9800; font-weight: 600;"))

        return ui.card(
            ui.card_header("🗺️ Spatial Grid Preview"),
            ui.div(
                ui.div(
                    *items,
                    class_="info-box"
                ),
                style="padding: 1rem;"
            )
        )

    # Data preview
    @output
    @render.ui
    def data_preview_ui():
        df = uploaded_data.get()
        detected_type = detected_data_type.get()

        if df is not None:
            # Analyze data characteristics for display
            feature_cols = [col for col in df.columns if col != 'Subzone ID']
            unique_values_per_col = [len(df[col].dropna().unique()) for col in feature_cols]
            avg_unique = np.mean(unique_values_per_col) if unique_values_per_col else 0

            return ui.card(
                ui.card_header("✅ Data Preview"),
                ui.div(
                    ui.div(
                        ui.h5(f"📊 Dataset: {df.shape[0]} subzones × {df.shape[1]-1} features",
                              style="color: #28a745; font-weight: 600; margin-bottom: 1rem;"),
                        ui.p(
                            f"✓ Successfully loaded data with {df.shape[0]} rows and {df.shape[1]} columns",
                            style="color: #6c757d;"
                        ),
                        class_="info-box"
                    ),
                    ui.div(
                        ui.h5("🤖 Auto-Detected Data Type", style="color: #006994; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.5rem;"),
                        ui.div(
                            ui.div(
                                ui.h4(
                                    "📌 " + detected_type.upper() if detected_type else "DETECTING...",
                                    style=f"color: {'#28a745' if detected_type == 'qualitative' else '#2196F3'}; font-weight: 700; margin: 0;"
                                ),
                                ui.p(
                                    f"Based on analysis of {len(feature_cols)} features",
                                    style="color: #6c757d; margin: 0.5rem 0 0 0; font-size: 0.9rem;"
                                ),
                                style="padding: 1.5rem; background: linear-gradient(135deg, #e3f2fd 0%, #f1f8e9 100%); border-radius: 8px; border-left: 4px solid #2196F3;"
                            ),
                            ui.div(
                                ui.p(
                                    ui.strong("Detection criteria:"),
                                    ui.br(),
                                    f"• Average unique values per feature: {avg_unique:.1f}",
                                    ui.br(),
                                    f"• Data range: {df[feature_cols].values.min():.2f} to {df[feature_cols].values.max():.2f}",
                                    ui.br(),
                                    "• Qualitative: Binary (0/1) or few unique values",
                                    ui.br(),
                                    "• Quantitative: Continuous, decimals, or many unique values",
                                    style="color: #616161; font-size: 0.9rem; line-height: 1.8; margin-top: 1rem;"
                                ),
                                ui.p(
                                    "💡 You can manually change the data type in the sidebar if needed.",
                                    style="color: #ff9800; font-weight: 500; margin-top: 1rem; font-size: 0.95rem;"
                                )
                            )
                        )
                    ),
                    ui.hr(),
                    ui.output_table("data_preview_table"),
                    style="padding: 1rem;"
                )
            )
        else:
            return ui.card(
                ui.card_header("📁 No Data Uploaded"),
                ui.div(
                    ui.div(
                        ui.p(
                            "⬆️ Please upload a CSV file using the sidebar to get started.",
                            style="font-size: 1.1rem; text-align: center; color: #6c757d; padding: 2rem;"
                        ),
                        ui.p(
                            "💡 You can download a template file to see the expected format.",
                            style="text-align: center; color: #6c757d;"
                        )
                    )
                )
            )
    
    @output
    @render.table
    def data_preview_table():
        df = uploaded_data.get()
        if df is not None:
            return df.head(PREVIEW_ROWS_LIMIT)
        return pd.DataFrame()
    
    # Features configuration UI
    @output
    @render.ui
    def features_config_ui():
        df = uploaded_data.get()
        if df is None:
            return ui.p("Please upload data first in the Data Input tab.")

        feature_names = df.columns[1:].tolist()
        classifications = feature_classifications.get() or {}

        feature_rows = []
        for feature in feature_names:
            current = classifications.get(feature, [])
            badges = [ui.span(
                cls, class_="feature-badge",
                style=f"background: {CLASSIFICATION_BADGE_COLORS.get(cls, '#999')}; color: white;"
            ) for cls in current]

            feature_rows.append(
                ui.div(
                    ui.div(
                        ui.strong(feature), " ", *badges,
                        style="margin-bottom: 0.3rem;"
                    ),
                    ui.div(
                        ui.div(
                            ui.div("Rarity", class_="classification-group-header"),
                            ui.p("Features rare at regional or national level", class_="classification-help"),
                            ui.input_checkbox_group(
                                f"class_rarity_{feature}", "",
                                choices={"RRF": "RRF (Regionally Rare) \u2192 AQ3/AQ4", "NRF": "NRF (Nationally Rare) \u2192 AQ5/AQ6"},
                                selected=[c for c in current if c in ['RRF', 'NRF']],
                                inline=True
                            ),
                            class_="classification-group"
                        ),
                        ui.div(
                            ui.div("Ecological Role", class_="classification-group-header"),
                            ui.p("Functional importance in the ecosystem", class_="classification-help"),
                            ui.input_checkbox_group(
                                f"class_role_{feature}", "",
                                choices={
                                    "ESF": "ESF (Ecologically Significant) \u2192 AQ10/AQ11",
                                    "HFS_BH": "HFS/BH (Habitat Forming) \u2192 AQ12/AQ13",
                                    "SS": "SS (Symbiotic) \u2192 AQ14/AQ15"
                                },
                                selected=[c for c in current if c in ['ESF', 'HFS_BH', 'SS']],
                                inline=True
                            ),
                            class_="classification-group"
                        ),
                    ),
                    style="padding: 0.8rem; border-bottom: 1px solid #e0e0e0; margin-bottom: 0.5rem;"
                )
            )

        # Live summary
        summary_counts = {}
        for feature, classes in classifications.items():
            for cls in classes:
                summary_counts[cls] = summary_counts.get(cls, 0) + 1
        summary_text = ", ".join([f"{count} {cls}" for cls, count in sorted(summary_counts.items())]) if summary_counts else "No features classified yet"

        return ui.TagList(
            ui.div(
                ui.p(f"\U0001f4cb {len(feature_names)} features detected. Classify each feature below."),
                ui.p(f"\U0001f4ca Summary: {summary_text}", style="font-weight: 600; color: #006994;"),
                class_="classification-summary"
            ),
            ui.input_action_button("reset_classifications", "\U0001f504 Reset All Classifications", class_="btn-outline-secondary btn-sm", style="margin: 1rem 0;"),
            ui.div(*feature_rows, style="margin-top: 1rem;")
        )
    
    @reactive.Effect
    def _update_feature_classifications():
        """
        An effect that triggers whenever a feature classification checkbox changes.
        It collects all user-defined classifications into a single reactive dictionary.
        Only runs when data is available to avoid unnecessary processing.
        """
        df = uploaded_data.get()
        if df is None:
            # Only reset if classifications are not already empty
            if feature_classifications.get() != {}:
                feature_classifications.set({})
            return

        feature_names = df.columns[1:].tolist()

        # Early exit if no features
        if not feature_names:
            feature_classifications.set({})
            return

        new_classifications = {}
        for feature in feature_names:
            try:
                rarity = list(input[f"class_rarity_{feature}"]() or [])
            except (KeyError, TypeError):
                rarity = []
            try:
                role = list(input[f"class_role_{feature}"]() or [])
            except (KeyError, TypeError):
                role = []
            combined = rarity + role
            if combined:
                new_classifications[feature] = combined

        if new_classifications != feature_classifications.get():
            feature_classifications.set(new_classifications)

    @reactive.Effect
    @reactive.event(input.reset_classifications)
    def _reset_classifications():
        feature_classifications.set({})
        ui.notification_show("All classifications cleared.", type="message", duration=3)
    
    @output
    @render.table
    def features_summary_table():
        df = uploaded_data.get()
        if df is not None:
            feature_names = df.columns[1:].tolist()
            feature_df = df[feature_names]

            # Identify numeric columns for vectorized ops
            numeric_mask = feature_df.apply(lambda c: pd.api.types.is_numeric_dtype(c.dropna()))
            numeric_cols = [c for c in feature_names if numeric_mask[c] and feature_df[c].dropna().shape[0] > 0]
            non_numeric_cols = [c for c in feature_names if c not in numeric_cols]

            # Vectorized stats for all numeric columns at once
            num_df = feature_df[numeric_cols]
            means = num_df.mean()
            sums = num_df.sum()
            occurrences = (num_df > 0).sum()

            # Y metric still needs per-column percentile logic
            y_metrics = {}
            for col in numeric_cols:
                positive_values = num_df[col].dropna()
                positive_values = positive_values[positive_values > 0]
                if not positive_values.empty:
                    percentile_95 = np.percentile(positive_values, 95)
                    sum_top_5_percent = num_df[col][num_df[col] >= percentile_95].sum()
                    total_sum = sums[col]
                    y_metrics[col] = (sum_top_5_percent / total_sum * 100) if total_sum > 0 else 0
                else:
                    y_metrics[col] = 0

            # Build result rows
            summaries = []
            for col in non_numeric_cols:
                summaries.append({
                    "Feature Name": col, "X (Mean)": "N/A", "Y (95th Pct %)": "N/A",
                    "Z (Occurrence)": "N/A", "Count": "N/A", "Average": "N/A"
                })
            for col in numeric_cols:
                summaries.append({
                    "Feature Name": col,
                    "X (Mean)": f"{means[col]:.2f}",
                    "Y (95th Pct %)": f"{y_metrics[col]:.2f}%",
                    "Z (Occurrence)": occurrences[col],
                    "Count": f"{sums[col]:.2f}",
                    "Average": f"{means[col]:.2f}"
                })

            return pd.DataFrame(summaries)
        return pd.DataFrame()

    # Main calculation function
    @reactive.Calc
    def calculate_results():
        df = uploaded_data.get()

        if df is None:
            return None

        data_type = input.data_type()
        if data_type == "TO SPECIFY":
            return None

        # Get user classifications (can be empty, will default to empty dict)
        user_classifications = feature_classifications.get()
        if user_classifications is None:
            user_classifications = {}

        # Get configurable threshold values from UI
        lrf_threshold = input.lrf_threshold() / 100  # Convert from percentage to decimal
        concentration_pct = int(input.concentration_percentile())

        # Step 1: Rescale data (only compute the variant matching data type)
        empty_df = pd.DataFrame(index=df.index, columns=[c for c in df.columns if c != 'Subzone ID'])
        empty_df.insert(0, 'Subzone ID', df['Subzone ID'])
        rescaled_qual = eva_calculations.rescale_qualitative(df) if data_type == "qualitative" else empty_df
        rescaled_quant = eva_calculations.rescale_quantitative(df) if data_type == "quantitative" else empty_df

        # Step 2: Classify features using data and user input
        classifications = eva_calculations.classify_features(df, user_classifications, lrf_threshold=lrf_threshold)

        # Step 3: Calculate AQ9 special rescaling
        aq9_rescaled = eva_calculations.calculate_aq9_special(df, classifications, percentile=concentration_pct)

        # Step 4: Calculate all AQs
        aq_results = eva_calculations.calculate_all_aqs(df, data_type, rescaled_qual, rescaled_quant, aq9_rescaled, classifications)

        # Step 5: Calculate EV
        aq_results['EV'] = eva_calculations.calculate_ev(aq_results, data_type)

        # Combine with original data for a full results set
        # Validate that both dataframes are not empty and have matching indices
        try:
            if df.empty or aq_results.empty:
                return None

            # Ensure both DataFrames have the same index (Subzone ID)
            df_indexed = df.set_index('Subzone ID')
            aq_results_indexed = aq_results.set_index('Subzone ID')

            # Reindex both DataFrames to ensure they have the same subzones
            # Use union of all subzones to handle missing data
            all_subzones = df_indexed.index.union(aq_results_indexed.index)
            df_indexed = df_indexed.reindex(all_subzones, fill_value=0)
            aq_results_indexed = aq_results_indexed.reindex(all_subzones, fill_value=np.nan)

            # Now concatenate with matching indices
            results = pd.concat([df_indexed, aq_results_indexed], axis=1).reset_index()

            return results
        except (KeyError, ValueError, IndexError) as e:
            # Log error and return None if concatenation fails
            logger.error(f"Error in DataFrame concatenation: {e}")
            logger.debug(f"df shape: {df.shape if df is not None else 'None'}")
            logger.debug(f"aq_results shape: {aq_results.shape if aq_results is not None else 'None'}")
            return None

    # Results UI
    @output
    @render.ui
    def results_ui():
        df = uploaded_data.get()
        data_type = input.data_type()
        results = calculate_results()

        if df is None:
            return ui.div(
                ui.card(
                    ui.card_header("⚠️ No Data Uploaded"),
                    ui.div(
                        ui.p(
                            "🔴 Please upload data first!",
                            style="font-size: 1.2rem; text-align: center; color: #d32f2f; font-weight: 600; padding: 1rem; margin-bottom: 1rem;"
                        ),
                        ui.p(
                            ui.br(),
                            "1. Go to the 'Data Input' tab",
                            ui.br(),
                            "2. Upload your CSV file",
                            ui.br(),
                            "3. Select the data type (qualitative or quantitative)",
                            ui.br(),
                            "4. Return to this tab to view results",
                            style="text-align: center; color: #6c757d; line-height: 2;"
                        )
                    )
                )
            )

        if data_type == "TO SPECIFY":
            return ui.div(
                ui.card(
                    ui.card_header("⚠️ Data Type Not Selected", style="background: linear-gradient(135deg, #ff9800 0%, #ff5722 100%);"),
                    ui.div(
                        ui.p(
                            "🔴 Please select a data type to proceed with analysis!",
                            style="font-size: 1.2rem; text-align: center; color: #d32f2f; font-weight: 600; padding: 1rem; margin-bottom: 1rem;"
                        ),
                        ui.p(
                            "Your data has been uploaded successfully, but you need to specify the data type:",
                            style="font-size: 1.1rem; text-align: center; color: #6c757d; padding: 1rem;"
                        ),
                        ui.div(
                            ui.p(
                                "👉 Go to the 'Data Input' tab",
                                ui.br(),
                                "👉 In the sidebar, change 'Data Type' from 'TO SPECIFY' to:",
                                ui.br(),
                                "   • ", ui.strong("qualitative"), " - for presence/absence data (0 or 1)",
                                ui.br(),
                                "   • ", ui.strong("quantitative"), " - for continuous numerical data",
                                style="text-align: left; color: #424242; line-height: 2.2; font-size: 1.05rem; padding: 1rem; background: #fff3e0; border-radius: 8px; border-left: 4px solid #ff9800;"
                            ),
                            style="max-width: 600px; margin: 0 auto;"
                        ),
                        ui.p(
                            "Then return to this tab to view your analysis results.",
                            style="font-size: 1rem; text-align: center; color: #6c757d; padding: 1rem; margin-top: 1rem;"
                        )
                    )
                )
            )

        if results is not None:
            # Get AQ statuses with explanations
            user_classifications = feature_classifications.get() or {}
            aq_statuses = eva_calculations.get_aq_status(data_type, user_classifications, results)

            active_badges = []
            inactive_badges = []
            for aq, (status, reason) in sorted(aq_statuses.items(), key=lambda x: int(x[0][2:])):
                if status == 'active':
                    active_badges.append(ui.span(
                        aq,
                        style="display: inline-block; padding: 4px 10px; margin: 2px; border-radius: 12px; "
                        "background: #28a745; color: white; font-size: 0.85rem; font-weight: 600;"
                    ))
                else:
                    inactive_badges.append(ui.span(
                        f"{aq}: {reason}",
                        style="display: inline-block; padding: 4px 10px; margin: 2px; border-radius: 12px; "
                        "background: #e0e0e0; color: #666; font-size: 0.8rem;"
                    ))

            return ui.TagList(
                ui.div(
                    ui.h5(f"✅ Analysis Complete: {len(results)} subzones analyzed",
                          style="color: #28a745; font-weight: 600; margin-bottom: 1.5rem;"),
                    class_="info-box"
                ),
                ui.div(
                    ui.h5("📋 Assessment Questions Summary", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.div(
                        ui.p(
                            ui.strong(f"Data Type: {data_type.upper()}"),
                            style="font-size: 1.1rem; color: #2196F3; margin-bottom: 0.5rem;"
                        ),
                        ui.p("Active AQs:", style="font-weight: 600; color: #28a745; margin-bottom: 0.3rem;"),
                        ui.div(*active_badges, style="margin-bottom: 0.8rem;") if active_badges else ui.p("None", style="color: #999;"),
                        ui.p("Inactive AQs:", style="font-weight: 600; color: #999; margin-bottom: 0.3rem;"),
                        ui.div(*inactive_badges) if inactive_badges else ui.p("None — all AQs are active!", style="color: #28a745;"),
                        style="padding: 1rem; background: linear-gradient(135deg, #e3f2fd 0%, #f1f8e9 100%); border-radius: 8px; margin-bottom: 1.5rem;"
                    )
                ),
                ui.div(
                    ui.tags.details(
                        ui.tags.summary(ui.strong("ℹ️ How is EV calculated?")),
                        ui.p("EV = MAX of all active AQ scores for each subzone. "
                             "Each AQ evaluates a different aspect of ecological value. "
                             "The highest-scoring AQ determines the EV for that subzone."),
                        ui.p(f"Active AQs for your data: {', '.join(aq for aq, (s, _) in sorted(aq_statuses.items(), key=lambda x: int(x[0][2:])) if s == 'active')}"),
                        ui.p("To activate more AQs, classify features in the EC Features tab "
                             "(e.g., mark features as RRF to enable AQ5/AQ6)."),
                    ),
                    style="margin-bottom: 1.5rem; padding: 1rem; background: #f5f5f5; border-radius: 8px;"
                ),
                ui.hr(),
                ui.h5("📊 Results Table", style="color: #006994; font-weight: 600; margin: 1.5rem 0 1rem 0;"),
                ui.output_ui("results_table_with_tooltips")
            )

        return ui.div(
            ui.p(
                "⚠️ Unable to calculate results. Please check your data and settings.",
                style="font-size: 1.1rem; text-align: center; color: #6c757d; padding: 2rem;"
            )
        )

    @output
    @render.ui
    def results_table_with_tooltips():
        results = calculate_results()
        if results is None:
            return ui.div()

        # Show Subzone ID, all AQ columns, and EV
        aq_cols = [col for col in results.columns if col.startswith('AQ') or col == 'EV']
        display_cols = ['Subzone ID'] + aq_cols

        # Create display dataframe
        display_limit = int(input.results_display_limit())
        display_df = results[display_cols].head(display_limit).copy() if display_limit > 0 else results[display_cols].copy()

        # Round numeric columns to 3 decimal places
        numeric_cols = display_df.select_dtypes(include=[np.number]).columns
        display_df[numeric_cols] = display_df[numeric_cols].round(3)

        # Build HTML table with Bootstrap tooltips
        html = """
        <style>
            .tooltip-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9rem;
            }
            .tooltip-table th {
                background: linear-gradient(135deg, #006994 0%, #4da6ff 100%);
                color: white;
                padding: 12px 8px;
                text-align: left;
                font-weight: 600;
            }
            .tooltip-table th.has-tooltip {
                cursor: help;
            }
            .tooltip-table th:hover {
                background: linear-gradient(135deg, #00527a 0%, #0088cc 100%);
            }
            .tooltip-table td {
                padding: 10px 8px;
                border-bottom: 1px solid #dee2e6;
            }
            .tooltip-table tr:hover {
                background-color: rgba(0, 184, 212, 0.1);
            }
        </style>
        <table class="tooltip-table">
            <thead>
                <tr>
        """

        # Add headers with Bootstrap tooltips
        for col in display_cols:
            safe_col = html_escape(str(col))
            tooltip = eva_calculations.get_aq_tooltip(col)
            if tooltip:
                # Use Bootstrap tooltip with data-bs attributes
                escaped_tooltip = html_escape(tooltip)
                html += f'<th class="has-tooltip" data-bs-toggle="tooltip" data-bs-placement="top" data-bs-html="true" title="{escaped_tooltip}">{safe_col}</th>'
            else:
                html += f'<th>{safe_col}</th>'

        html += """
                </tr>
            </thead>
            <tbody>
        """

        # Identify AQ columns for max-highlighting
        aq_cols = [col for col in display_cols if col.startswith('AQ')]

        # Add data rows
        for idx, row in display_df.iterrows():
            # Find the AQ column with the max value for this row
            aq_values = {col: row[col] for col in aq_cols if pd.notna(row[col]) and isinstance(row[col], (int, float)) and row[col] > 0}
            max_aq_col = max(aq_values, key=aq_values.get) if aq_values else None

            html += "<tr>"
            for col in display_cols:
                value = row[col]
                if pd.isna(value):
                    # Display NA for missing values
                    html += '<td style="color: #999; font-style: italic; text-align: center;">NA</td>'
                elif isinstance(value, (int, float)):
                    # Format numbers nicely, highlight max AQ cell
                    if col == max_aq_col:
                        html += f'<td class="aq-max-cell">{value}</td>'
                    else:
                        html += f'<td>{value}</td>'
                else:
                    html += f'<td>{html_escape(str(value))}</td>'
            html += "</tr>"

        html += """
            </tbody>
        </table>
        <script>
            // Initialize Bootstrap tooltips
            (function() {
                // Wait a bit for the table to be fully rendered
                setTimeout(function() {
                    var tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
                    var tooltipList = Array.from(tooltipTriggerList).map(function (tooltipTriggerEl) {
                        return new bootstrap.Tooltip(tooltipTriggerEl, {
                            trigger: 'hover',
                            delay: { show: 100, hide: 100 }
                        });
                    });
                }, 100);
            })();
        </script>
        """

        return ui.HTML(html)
    
    # Total EV UI
    @output
    @render.ui
    def total_ev_ui():
        store = ec_store.get()

        # If multiple ECs saved, aggregate across them
        if len(store) >= 2:
            # Build aggregation DataFrame
            merged = eva_calculations.merge_multi_ec_ev(store)

            if merged is None:
                return ui.p("No ECs have computed results. Configure and save ECs first.")

            ec_names = [c for c in merged.columns if c not in ('Subzone ID', 'Total EV')]

            total_ev = merged['Total EV'].sum()
            avg_ev = merged['Total EV'].mean()
            max_ev = merged['Total EV'].max()
            min_ev = merged['Total EV'].min()

            return ui.TagList(
                ui.card(
                    ui.card_header(f"Aggregated Total EV ({len(ec_names)} ECs)"),
                    ui.layout_column_wrap(
                        ui.value_box("Total EV (Max)", f"{total_ev:.2f}", theme="primary"),
                        ui.value_box("Average Total EV", f"{avg_ev:.2f}", theme="info"),
                        ui.value_box("Max Total EV", f"{max_ev:.2f}", theme="success"),
                        ui.value_box("Min Total EV", f"{min_ev:.2f}", theme="warning"),
                        width=1/4
                    )
                ),
                ui.hr(),
                ui.h5("Per-EC Summary"),
                ui.output_table("ec_summary_table"),
                ui.hr(),
                ui.h5("Aggregated EV by Subzone"),
                ui.output_table("total_ev_table")
            )

        # Single EC or no ECs: use existing behavior
        results = calculate_results()
        if results is not None:
            total_ev = results['EV'].sum()
            avg_ev = results['EV'].mean()
            max_ev = results['EV'].max()
            min_ev = results['EV'].min()

            return ui.TagList(
                ui.card(
                    ui.card_header("Summary Statistics"),
                    ui.layout_column_wrap(
                        ui.value_box("Total EV", f"{total_ev:.2f}", theme="primary"),
                        ui.value_box("Average EV", f"{avg_ev:.2f}", theme="info"),
                        ui.value_box("Max EV", f"{max_ev:.2f}", theme="success"),
                        ui.value_box("Min EV", f"{min_ev:.2f}", theme="warning"),
                        width=1/4
                    )
                ),
                ui.hr(),
                ui.h5("Detailed EV by Subzone"),
                ui.output_table("total_ev_table")
            )
        return ui.p("No data available. Please upload data and calculate results.")
    
    @output
    @render.table
    def total_ev_table():
        store = ec_store.get()
        display_limit = int(input.results_display_limit())

        if len(store) >= 2:
            merged = eva_calculations.merge_multi_ec_ev(store)

            if merged is None:
                return pd.DataFrame()

            merged = merged.sort_values('Total EV', ascending=False)

            return merged.head(display_limit) if display_limit > 0 else merged

        results = calculate_results()
        if results is not None:
            df = results[['Subzone ID', 'EV']]
            return df.head(display_limit) if display_limit > 0 else df
        return pd.DataFrame()

    @output
    @render.table
    def ec_summary_table():
        store = ec_store.get()
        if len(store) < 2:
            return pd.DataFrame()

        rows = []
        for ec_name, ec in store.items():
            mean_ev = ec['results']['EV'].mean() if ec['results'] is not None else 0
            rows.append({
                'EC Name': ec_name,
                'Data Type': ec['data_type'],
                'Features': ec['feature_count'],
                'Mean EV': round(mean_ev, 2)
            })
        return pd.DataFrame(rows)

    # Download results as Excel with multiple sheets and annotations
    @render.download(filename=lambda: f"MARBEFES_EVA_Results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    def download_results():
        """Export comprehensive analysis results to Excel."""
        # Pass EUNIS overlay if available for habitat-level EV summary
        eunis_data_for_export = None
        try:
            overlay = eunis_overlay.get()
            if overlay is not None:
                eunis_data_for_export = overlay[["Subzone_ID", "dominant_EUNIS", "dominant_EUNIS_name"]].copy()
        except Exception as e:
            logger.warning("Could not fetch EUNIS overlay for export: %s", e)

        return eva_export.generate_workbook(
            results=calculate_results(),
            uploaded_data=uploaded_data.get(),
            user_classifications=feature_classifications.get(),
            data_type=input.data_type(),
            metadata={
                'ec_name': input.ec_name() if input.ec_name() else 'Not specified',
                'study_area': input.study_area() if input.study_area() else 'Not specified',
                'data_description': input.data_description() if input.data_description() else 'Not specified',
            },
            ec_store=ec_store.get(),
            pa_summary_data=eunis_data_for_export,
        )
    
    @reactive.Effect
    @reactive.event(input.save_ec)
    def _save_current_ec():
        ec_name = input.ec_name().strip()
        if not ec_name:
            ui.notification_show("Please enter an EC Name before saving.", type="warning")
            return

        df = uploaded_data.get()
        if df is None:
            ui.notification_show("No data uploaded. Upload a CSV first.", type="warning")
            return

        results = calculate_results()
        store = ec_store.get().copy()
        store[ec_name] = ECEntry(
            data=df.copy(),
            data_type=input.data_type(),
            classifications=feature_classifications.get().copy(),
            results=results.copy() if results is not None else None,
        )
        ec_store.set(store)
        current_ec.set(ec_name)
        ui.notification_show(f"EC '{ec_name}' saved successfully.", type="message")

    @reactive.Effect
    @reactive.event(input.select_ec)
    def _restore_ec():
        ec_name = input.select_ec()
        if not ec_name or ec_name == "":
            return
        store = ec_store.get()
        if ec_name not in store:
            return

        ec = store[ec_name]
        uploaded_data.set(ec['data'].copy())
        feature_classifications.set(ec['classifications'].copy())
        detected_data_type.set(ec['data_type'])
        current_ec.set(ec_name)
        # Clear stale state from the previous EC
        validation_report.set(None)
        geo_match_info.set(None)

        # Update the data type dropdown to match
        ui.update_select("data_type", selected=ec['data_type'])
        # Update EC name field
        ui.update_text("ec_name", value=ec_name)

        ui.notification_show(f"Switched to EC '{ec_name}'.", type="message")

    @reactive.Effect
    @reactive.event(input.new_ec)
    def _new_ec():
        uploaded_data.set(None)
        feature_classifications.set({})
        detected_data_type.set(None)
        validation_report.set(None)
        dwca_info.set(None)
        geo_match_info.set(None)
        current_ec.set(None)
        ui.update_text("ec_name", value="")
        ui.update_select("data_type", selected="TO SPECIFY")
        ui.notification_show("Ready for a new EC. Upload a CSV file.", type="message")

    @reactive.Effect
    @reactive.event(input.delete_ec)
    def _delete_ec():
        ec_name = input.select_ec()
        if not ec_name:
            return
        store = ec_store.get().copy()
        if ec_name in store:
            del store[ec_name]
            ec_store.set(store)
            if current_ec.get() == ec_name:
                current_ec.set(None)
            ui.notification_show(f"EC '{ec_name}' removed.", type="message")
            # Update the select dropdown
            ui.update_select("select_ec", choices=[""] + list(store.keys()), selected="")

    @reactive.Effect
    @reactive.event(calculate_results)
    def _auto_update_stored_ec():
        ec_name = current_ec.get()
        if ec_name is None:
            return
        store = ec_store.get()
        if ec_name not in store:
            return
        results = calculate_results()
        df = uploaded_data.get()
        if results is not None and df is not None:
            updated = store.copy()
            entry = store[ec_name].copy()
            entry.results = results.copy()
            entry.classifications = feature_classifications.get().copy()
            entry.data_type = input.data_type()
            updated[ec_name] = entry
            ec_store.set(updated)

    @output
    @render.ui
    def ec_list_summary():
        store = ec_store.get()
        if not store:
            return ui.p("No ECs saved yet.", style="color: #999; font-size: 0.85rem; margin-top: 0.5rem;")

        active = current_ec.get()
        items = []
        for name, ec in store.items():
            badge_color = "#28a745" if name == active else "#6c757d"
            dt_badge = "Q" if ec['data_type'] == 'qualitative' else "QN"
            items.append(ui.div(
                ui.span(f"● {name}", style=f"font-weight: {'600' if name == active else '400'}; color: {badge_color};"),
                ui.span(f" ({dt_badge}, {ec['feature_count']} features)", style="color: #999; font-size: 0.8rem;"),
                style="margin: 0.2rem 0;"
            ))
        return ui.div(
            ui.p(f"📋 {len(store)} EC(s) saved:", style="font-weight: 600; margin: 0.5rem 0 0.3rem 0; font-size: 0.9rem;"),
            *items
        )

    @reactive.Effect
    @reactive.event(ec_store, current_ec)
    def _update_ec_selector():
        store = ec_store.get()
        choices = [""] + list(store.keys())
        current = current_ec.get() or ""
        ui.update_select("select_ec", choices=choices, selected=current)

    @reactive.Effect
    @reactive.event(uploaded_data)
    def _update_radar_choices():
        df = uploaded_data.get()
        if df is not None and 'Subzone ID' in df.columns:
            subzone_ids = df['Subzone ID'].tolist()
            ui.update_selectize(
                "radar_subzones",
                choices=subzone_ids,
                selected=subzone_ids[:3]
            )


    # Visualization
    @output
    @render.ui
    def visualization_ui():
        results = calculate_results()
        if results is None:
            return ui.div(
                ui.p(
                    "\u26a0\ufe0f No data to visualize. Please upload data in the Data Input tab first.",
                    style="font-size: 1.1rem; text-align: center; color: #6c757d; padding: 2rem;"
                )
            )

        plot_type = input.plot_type()

        if plot_type == "EV by Subzone":
            html_str = eva_visualizations.create_ev_bar_chart(results)
            return ui.HTML(html_str)

        elif plot_type == "Feature Distribution":
            df = uploaded_data.get()
            if df is not None and 'Subzone ID' in df.columns:
                html_str = eva_visualizations.create_feature_heatmap(df)
                return ui.HTML(html_str)
            return ui.p("Unable to generate feature distribution chart")

        elif plot_type == "AQ Breakdown by Subzone":
            html_str = eva_visualizations.create_aq_breakdown_chart(results)
            if html_str is None:
                return ui.p("No active AQ scores to display.")
            return ui.HTML(html_str)

        elif plot_type == "AQ Radar Comparison":
            selected = list(input.radar_subzones()) if input.radar_subzones() else []
            if not selected:
                return ui.div(
                    ui.p("\U0001f448 Select 1-5 subzones from the sidebar to compare their AQ profiles.",
                         style="font-size: 1.1rem; text-align: center; color: #6c757d; padding: 2rem;")
                )
            html_str = eva_visualizations.create_aq_radar_chart(results, selected)
            if html_str is None:
                return ui.p("No AQ scores available")
            return ui.HTML(html_str)

        elif plot_type == "AQ Heatmap":
            color_scheme = input.color_scheme()
            html_str = eva_visualizations.create_aq_heatmap(results, color_scheme)
            if html_str is None:
                return ui.p("No AQ scores available")
            return ui.HTML(html_str)

        else:  # AQ Scores
            html_str = eva_visualizations.create_aq_histogram(results)
            if html_str is None:
                return ui.p("No AQ scores available")
            return ui.HTML(html_str)

    # === GIS MAP FUNCTIONS ===

    # Map output renderer
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

        if input.map_variable() == "Habitat Type (PA)":
            assignments = pa_habitat_assignments.get()
            if not assignments:
                return ui.p("No habitat assignments available.", style="color: #6c757d; text-align: center; padding: 2rem;")

            map_html = eva_map.create_habitat_map(
                gdf, assignments,
                basemap_name=input.map_basemap(),
                opacity=float(input.map_opacity())
            )
            return ui.HTML(map_html)

        if results is None:
            map_html = eva_map.create_grid_only_map(gdf, basemap_name=input.map_basemap())
            return ui.div(
                ui.HTML(map_html),
                style="height: 600px; width: 100%; border-radius: 8px; overflow: hidden; border: 1px solid #dee2e6;"
            )

        try:
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

            eunis = eunis_overlay.get()
            map_html = eva_map.create_ev_map(merged, variable, color_scheme, classification, basemap, opacity, eunis_gdf=eunis)

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

    # =====================================================================
    # Physical Accounts (PA) server logic
    # =====================================================================

    # PA reactive values
    pa_habitat_assignments = reactive.Value({})
    pa_custom_habitats = reactive.Value([])
    pa_custom_benefits = reactive.Value([])

    def _lookup_habitat_name(code):
        """Resolve habitat name from custom habitats first, then global lookup."""
        for h in pa_custom_habitats.get():
            if h["code"] == code:
                return h["name"]
        return pa_config.EUNIS_LOOKUP.get(code, code)

    @output
    @render.ui
    def pa_habitat_assignment_ui():
        gdf = geo_data.get()
        gdf_full = geo_data_full.get()
        if gdf is None:
            return ui.div(
                ui.p("⬆️ Upload a spatial grid file in the Data Input tab to begin habitat assignment.",
                     style="text-align: center; color: #6c757d; padding: 2rem; font-size: 1.1rem;")
            )

        subzone_ids = gdf["Subzone ID"].tolist()
        selected_habitats = list(input.pa_habitat_select() or [])
        custom_habs = pa_custom_habitats.get()
        all_habitat_choices = {}
        for h in pa_config.EUNIS_HABITATS:
            if h["code"] in selected_habitats:
                all_habitat_choices[h["code"]] = f"{h['code']} - {h['name']}"
        for ch in custom_habs:
            all_habitat_choices[ch["code"]] = f"{ch['code']} - {ch['name']}"

        # Auto-detect
        auto_col = None
        auto_assignments = {}
        if gdf_full is not None:
            auto_col = pa_calculations.detect_habitat_column(list(gdf_full.columns))
            if auto_col:
                for _, row in gdf_full.iterrows():
                    sid = str(row.get("Subzone ID", ""))
                    val = str(row.get(auto_col, ""))
                    if sid and val:
                        auto_assignments[sid] = val

        items = []
        if auto_col:
            items.append(ui.p(f"✅ Auto-detected habitat column: '{auto_col}'",
                             style="color: #28a745; font-weight: 600; margin-bottom: 1rem;"))
        else:
            items.append(ui.p("ℹ️ No habitat column detected — assign habitats manually below.",
                             style="color: #ff9800; margin-bottom: 1rem;"))

        if not all_habitat_choices:
            items.append(ui.p("👈 Select habitat types in the sidebar first.", style="color: #6c757d;"))
        else:
            for sid in subzone_ids:
                default = auto_assignments.get(sid, "")
                items.append(
                    ui.div(
                        ui.div(ui.strong(sid), style="width: 120px; display: inline-block;"),
                        ui.input_select(
                            f"pa_assign_{sid}", "",
                            choices={"": "(unassigned)", **all_habitat_choices},
                            selected=default if default in all_habitat_choices else "",
                            width="300px"
                        ),
                        style="display: flex; align-items: center; gap: 1rem; margin-bottom: 0.3rem;"
                    )
                )

        return ui.div(*items)

    @reactive.Effect
    @reactive.event(geo_data)
    def _update_pa_assignments():
        gdf = geo_data.get()
        if gdf is None:
            pa_habitat_assignments.set({})
            return
        assignments = {}
        for sid in gdf["Subzone ID"].tolist():
            try:
                val = input[f"pa_assign_{sid}"]()
                if val:
                    assignments[sid] = val
            except (KeyError, TypeError):
                pass
        pa_habitat_assignments.set(assignments)

    @output
    @render.ui
    def pa_extent_ui():
        gdf = geo_data.get()
        assignments = pa_habitat_assignments.get()
        if gdf is None:
            return ui.p("Upload a spatial grid to compute extent.", style="color: #6c757d; text-align: center; padding: 2rem;")
        if not assignments:
            return ui.p("Assign habitats to subzones above to compute extent.", style="color: #6c757d; text-align: center; padding: 2rem;")

        unit = input.pa_area_unit()
        crs = original_crs.get()
        extent_df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs)

        if extent_df.empty:
            return ui.p("No extent data computed.", style="color: #6c757d;")

        return ui.TagList(
            ui.output_table("pa_extent_table"),
            ui.div(
                ui.p("ℹ️ Opening/closing stock tracking and change analysis will be available in a future version.",
                     style="color: #6c757d; font-size: 0.9rem; margin-top: 1rem;"),
                class_="info-box"
            )
        )

    @output
    @render.table
    def pa_extent_table():
        gdf = geo_data.get()
        assignments = pa_habitat_assignments.get()
        if gdf is None or not assignments:
            return pd.DataFrame()
        unit = input.pa_area_unit()
        crs = original_crs.get()
        df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs)
        df["area"] = df["area"].round(2)
        df["pct_total"] = df["pct_total"].round(1)
        df.columns = ["EUNIS Code", "Habitat Name", f"Area ({unit})", "% of Total"]
        return df

    @output
    @render.ui
    def pa_supply_ui():
        assignments = pa_habitat_assignments.get()
        selected_benefits = list(input.pa_benefits_select() or [])
        custom_bens = pa_custom_benefits.get()
        all_benefits = selected_benefits + [b["name"] for b in custom_bens]

        if not assignments:
            return ui.p("Assign habitats first to enter supply data.", style="color: #6c757d; text-align: center; padding: 2rem;")
        if not all_benefits:
            return ui.p("Select at least one benefit in the sidebar.", style="color: #6c757d; text-align: center; padding: 2rem;")

        habitat_codes = sorted(set(assignments.values()))

        grid_size = len(all_benefits) * len(habitat_codes)
        items = []
        if grid_size > 100:
            items.append(ui.p(f"⚠️ Large grid ({grid_size} cells). Consider reducing habitats or benefits.",
                             style="color: #ff9800; font-weight: 600;"))

        header_cells = [ui.tags.th("Benefit"), ui.tags.th("Unit")]
        for code in habitat_codes:
            name = _lookup_habitat_name(code)
            header_cells.append(ui.tags.th(code, title=name, style="cursor: help;"))

        body_rows = []
        for ben_name in all_benefits:
            slug = pa_config.benefit_slug(ben_name)
            ben_unit = "units"
            for b in pa_config.DEFAULT_BENEFITS:
                if b["name"] == ben_name:
                    ben_unit = b["unit"]
                    break
            for cb in custom_bens:
                if cb["name"] == ben_name:
                    ben_unit = cb["unit"]
                    break

            cells = [ui.tags.td(ui.strong(ben_name)), ui.tags.td(ben_unit)]
            for code in habitat_codes:
                input_id = f"supply_{slug}_{code}"
                cells.append(ui.tags.td(
                    ui.input_numeric(input_id, "", value=None, width="100px"),
                    style="padding: 2px;"
                ))
            body_rows.append(ui.tags.tr(*cells))

        items.append(ui.tags.table(
            ui.tags.thead(ui.tags.tr(*header_cells)),
            ui.tags.tbody(*body_rows),
            class_="table table-sm table-bordered",
            style="font-size: 0.9rem;"
        ))

        supply_data = _collect_pa_supply_data(all_benefits, habitat_codes)
        completeness = pa_calculations.validate_completeness(supply_data, habitat_codes, all_benefits)
        items.append(ui.p(
            f"📊 Data completeness: {completeness['filled']} of {completeness['total']} cells filled ({completeness['pct']}%)",
            style=f"font-weight: 600; color: {'#28a745' if completeness['pct'] == 100 else '#ff9800'}; margin-top: 1rem;"
        ))

        items.append(ui.div(
            ui.p("ℹ️ Use Table (sector disaggregation) and Condition Account will be available in a future version.",
                 style="color: #6c757d; font-size: 0.9rem; margin-top: 1rem;"),
            class_="info-box"
        ))

        return ui.div(*items)

    def _collect_pa_supply_data(benefit_names, habitat_codes):
        supply_data = {}
        for name in benefit_names:
            slug = pa_config.benefit_slug(name)
            quantities = {}
            for code in habitat_codes:
                try:
                    val = input[f"supply_{slug}_{code}"]()
                    if val is not None:
                        quantities[code] = float(val)
                except (KeyError, TypeError, ValueError):
                    pass
            if quantities:
                supply_data[name] = quantities
        return supply_data

    @reactive.Effect
    @reactive.event(input.pa_add_custom_habitat)
    def _add_custom_habitat():
        code = input.pa_custom_habitat_code().strip()
        name = input.pa_custom_habitat_name().strip()
        if not code or not name:
            ui.notification_show("Please enter both code and name.", type="warning")
            return
        current = pa_custom_habitats.get().copy()
        if any(h["code"] == code for h in current):
            ui.notification_show(f"Habitat code '{code}' already exists.", type="warning")
            return
        current.append({"code": code, "name": name})
        pa_custom_habitats.set(current)
        # Do NOT mutate pa_config.EUNIS_LOOKUP — it leaks between sessions.
        # Custom habitats are stored in pa_custom_habitats reactive value only.
        ui.notification_show(f"Added custom habitat: {code} - {name}", type="message")

    @reactive.Effect
    @reactive.event(input.pa_add_custom_benefit)
    def _add_custom_benefit():
        name = input.pa_custom_benefit_name().strip()
        unit = input.pa_custom_benefit_unit().strip()
        if not name or not unit:
            ui.notification_show("Please enter both name and unit.", type="warning")
            return
        current = pa_custom_benefits.get().copy()
        all_names = list(input.pa_benefits_select() or []) + [b["name"] for b in current]
        if name in all_names:
            ui.notification_show(f"Benefit '{name}' already exists.", type="warning")
            return
        current.append({"name": name, "unit": unit})
        pa_custom_benefits.set(current)
        ui.notification_show(f"Added custom benefit: {name} ({unit})", type="message")

    @render.download(filename=lambda: f"MARBEFES_PhysicalAccounts_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    def pa_download_standalone():
        gdf = geo_data.get()
        assignments = pa_habitat_assignments.get()
        unit = input.pa_area_unit()
        crs = original_crs.get()

        extent_df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs) if gdf is not None and assignments else pd.DataFrame()

        selected_benefits = list(input.pa_benefits_select() or [])
        custom_bens = pa_custom_benefits.get()
        all_benefits = selected_benefits + [b["name"] for b in custom_bens]
        habitat_codes = sorted(set(assignments.values())) if assignments else []

        supply_data = _collect_pa_supply_data(all_benefits, habitat_codes)
        supply_df = pa_calculations.assemble_supply_table(supply_data, habitat_codes)
        completeness = pa_calculations.validate_completeness(supply_data, habitat_codes, all_benefits)

        metadata = {
            "eaa_name": input.pa_eaa_name() or "Not specified",
            "boundary_description": input.pa_boundary_desc() or "Not specified",
            "accounting_year": input.pa_accounting_year() or 2024,
        }

        return pa_export.generate_pa_workbook(
            extent_df=extent_df, supply_df=supply_df,
            assignments=assignments, metadata=metadata,
            completeness=completeness, unit=unit,
        )

    @render.download(filename=lambda: f"MARBEFES_EVA_PA_Combined_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    def pa_download_combined():
        gdf = geo_data.get()
        assignments = pa_habitat_assignments.get()
        unit = input.pa_area_unit()
        crs = original_crs.get()

        extent_df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs) if gdf is not None and assignments else pd.DataFrame()

        selected_benefits = list(input.pa_benefits_select() or [])
        custom_bens = pa_custom_benefits.get()
        all_benefits = selected_benefits + [b["name"] for b in custom_bens]
        habitat_codes = sorted(set(assignments.values())) if assignments else []

        supply_data = _collect_pa_supply_data(all_benefits, habitat_codes)
        supply_df = pa_calculations.assemble_supply_table(supply_data, habitat_codes)
        completeness = pa_calculations.validate_completeness(supply_data, habitat_codes, all_benefits)

        pa_metadata = {
            "eaa_name": input.pa_eaa_name() or "Not specified",
            "boundary_description": input.pa_boundary_desc() or "Not specified",
            "accounting_year": input.pa_accounting_year() or 2024,
        }

        eva_args = {
            "results": calculate_results(),
            "uploaded_data": uploaded_data.get(),
            "user_classifications": feature_classifications.get(),
            "data_type": input.data_type(),
            "metadata": {
                "ec_name": input.ec_name() if input.ec_name() else "Not specified",
                "study_area": input.study_area() if input.study_area() else "Not specified",
                "data_description": input.data_description() if input.data_description() else "Not specified",
            },
            "ec_store": ec_store.get(),
        }

        return pa_export.generate_combined_workbook(
            eva_args=eva_args,
            pa_extent_df=extent_df, pa_supply_df=supply_df,
            pa_assignments=assignments, pa_metadata=pa_metadata,
            pa_completeness=completeness, pa_unit=unit,
        )

    # =====================================================================
    # EUNIS L3 Overlay (EUSeaMap integration)
    # =====================================================================
    eunis_overlay = reactive.Value(None)

    @reactive.Calc
    def cached_eva_data():
        eva_path = os.environ.get("MARBEFES_EVA_DATA_PATH", "")
        if not eva_path or not os.path.exists(eva_path):
            return None
        logger.info("Loading EVA data from %s (cached)", eva_path)
        return gpd.read_file(eva_path)

    @reactive.Effect
    @reactive.event(input.upload_eunis_overlay)
    def _handle_eunis_upload():
        file_info = input.upload_eunis_overlay()
        if file_info is None or len(file_info) == 0:
            return
        try:
            gdf = eunis_data.load_eunis_overlay(file_info[0]["datapath"])
            eunis_overlay.set(gdf)
            # Auto-populate habitat assignments from overlay
            assignments = {
                row["Subzone_ID"]: row["dominant_EUNIS"]
                for _, row in gdf.iterrows()
                if pd.notna(row.get("dominant_EUNIS"))
            }
            pa_habitat_assignments.set(assignments)
            n_types = gdf["dominant_EUNIS"].nunique()
            n_with = gdf["dominant_EUNIS"].notna().sum()
            ui.notification_show(
                f"EUNIS overlay loaded: {n_types} habitat types, "
                f"{n_with} subzones with data.",
                type="message", duration=5,
            )
            # Check for HFS/BH habitats and notify user
            suggestions = eunis_data.suggest_feature_classifications(gdf, [])
            hfs_count = suggestions.get("_hfs_subzone_count", 0)
            if hfs_count > 0:
                ui.notification_show(
                    f"Note: {hfs_count} subzones have reef/biogenic habitats (EUNIS A3/A4/MC35). "
                    f"Consider classifying relevant species as HFS/BH in the EC Features tab.",
                    type="message", duration=8,
                )
        except Exception as e:
            logger.error("EUNIS upload error: %s", e)
            ui.notification_show(f"Error loading EUNIS overlay: {e}", type="error")

    @output
    @render.ui
    def eunis_status_ui():
        overlay = eunis_overlay.get()
        if overlay is None:
            return ui.div()
        n_types = overlay["dominant_EUNIS"].nunique()
        n_with = overlay["dominant_EUNIS"].notna().sum()
        n_total = len(overlay)
        return ui.div(
            ui.p(
                f"✅ {n_types} EUNIS types, {n_with}/{n_total} subzones matched",
                style="color: #28a745; font-weight: 600; margin-top: 0.5rem;",
            ),
            class_="info-box",
        )

    @output
    @render.ui
    def eunis_accounts_ui():
        overlay = eunis_overlay.get()
        if overlay is None:
            return ui.p(
                "Upload a EUNIS overlay (.gpkg) in the sidebar to see BBT8 accounts.",
                style="color: #6c757d; text-align: center; padding: 2rem;",
            )
        return ui.TagList(
            ui.output_table("eunis_accounts_table"),
        )

    @output
    @render.table
    def eunis_accounts_table():
        overlay = eunis_overlay.get()
        if overlay is None:
            return pd.DataFrame()
        eva = cached_eva_data()
        if eva is None:
            return pd.DataFrame({"Error": ["EVA data not found"]})
        extent = eunis_data.compute_eunis_extent(overlay, unit=input.pa_area_unit())
        condition = eunis_data.compute_eunis_condition(overlay, eva)
        accounts = eunis_data.build_accounts_summary(extent, condition)
        accounts.columns = ["EUNIS Code", "Habitat", "Area (m2)", "Habitat EV", "Confidence"]
        accounts["Habitat EV"] = accounts["Habitat EV"].round(2)
        accounts["Confidence"] = accounts["Confidence"].round(2)
        accounts["Area (m2)"] = accounts["Area (m2)"].apply(lambda x: f"{x:,.0f}")
        return accounts

    @render.download(
        filename=lambda: f"MARBEFES_BBT8_PhysicalAccounts_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx"
    )
    def pa_download_bbt8():
        overlay = eunis_overlay.get()
        if overlay is None:
            ui.notification_show("Upload a EUNIS overlay first.", type="warning")
            return None
        from pa_export import generate_bbt8_workbook

        eva = cached_eva_data()
        if eva is None:
            ui.notification_show("EVA data not found.", type="error")
            return None

        unit = input.pa_area_unit()
        extent = eunis_data.compute_eunis_extent(overlay, unit=unit)
        condition = eunis_data.compute_eunis_condition(overlay, eva)
        supply = eunis_data.compute_eunis_supply(overlay, eva)
        accounts = eunis_data.build_accounts_summary(extent, condition)
        missing = eunis_data.build_missing_values(overlay, eva, total_bbt_area_m2=0)

        # main_values: per-subzone
        eva_sub = eva[["Subzone_ID", "TotalEV_MAX", "Confidence"]].copy() if "Subzone_ID" in eva.columns else pd.DataFrame()
        if not eva_sub.empty:
            # Drop geometry if present
            if "geometry" in eva_sub.columns:
                eva_sub = eva_sub.drop(columns="geometry")
            mv = overlay[["Subzone_ID", "dominant_EUNIS"]].merge(
                eva_sub, on="Subzone_ID", how="left",
            )
            mv.columns = ["Subzone_ID", "EUNIS_code", "Habitat_EV", "Habitat_confidence"]
        else:
            mv = overlay[["Subzone_ID", "dominant_EUNIS"]].copy()
            mv.columns = ["Subzone_ID", "EUNIS_code"]
            mv["Habitat_EV"] = np.nan
            mv["Habitat_confidence"] = np.nan

        metadata = {
            "Report": "SEEA EA Physical Accounts (BBT8 format)",
            "BBT": input.pa_eaa_name() or "Not specified",
            "Boundary": input.pa_boundary_desc() or "Not specified",
            "Year": str(input.pa_accounting_year()),
            "Framework": "SEEA EA / MARBEFES WP4",
            "Generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "EUNIS Source": "EMODnet EUSeaMap 2023",
            "EVA Version": f"MARBEFES EVA v{get_version()}",
        }

        return generate_bbt8_workbook(
            accounts=accounts, main_values=mv, extent=extent,
            condition=condition, supply=supply, metadata=metadata,
            missing_values=missing,
        )

    @reactive.Effect
    @reactive.event(pa_habitat_assignments)
    def _update_map_variable_for_pa():
        assignments = pa_habitat_assignments.get()
        base_choices = ["EV", "AQ1", "AQ2", "AQ3", "AQ4", "AQ5", "AQ6", "AQ7",
                        "AQ8", "AQ9", "AQ10", "AQ11", "AQ12", "AQ13", "AQ14", "AQ15"]
        if assignments:
            base_choices.append("Habitat Type (PA)")
        ui.update_select("map_variable", choices=base_choices)


# Create the app with static file serving


# Create the app with static file serving
app = App(app_ui, server, static_assets=Path(__file__).parent / "www")
