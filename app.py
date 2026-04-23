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
import eva_sdm
import eunis_data
import folium
import folium.plugins
import pa_config
import pa_calculations
import pa_export
import pa_docx
import eva_visualizations
import eva_map

def _import_sdm_analyse():
    """Lazy import of SDM analysis functions (handles deployment sys.path)."""
    import importlib
    import sys as _s
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in _s.path:
        _s.path.insert(0, app_dir)
    mod = importlib.import_module("scripts.sdm_analyse")
    return mod

import eva_hexgrid
import eva_eunis_wms
import eva_cmems
import dwca_reader
from eva_ui import app_ui, get_aq_guide_html

from version import get_version
from branca.element import MacroElement, Template

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
    sdm_covariates = reactive.Value(None)     # GeoDataFrame with all SDM covariate layers

    # SDM reactive values
    sdm_results = reactive.Value(None)        # dict: gam_model, idw_model, predictions, diagnostics, feat_names
    sdm_fit_message = reactive.Value("")      # status message for fit button feedback
    sdm_dwca_df   = reactive.Value(None)      # DataFrame from DwC-A upload for SDM
    sdm_dwca_info = reactive.Value(None)      # dict with n_sites, n_species, species_list, ...
    sdm_analysis_results = reactive.Value(None)   # dict with predictor analysis results
    sdm_analysis_message = reactive.Value("")     # status message for analysis button

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
                    original_crs.set("EPSG:4326")
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

        # Guard against excessive feature columns that would overwhelm the UI
        if len(feature_cols) > MAX_FEATURES:
            uploaded_data.set(None)
            ui.notification_show(
                f"Too many feature columns ({len(feature_cols)}). Maximum is {MAX_FEATURES}. "
                "Please reduce the number of species/variables in your CSV.",
                type="error", duration=10,
            )
            return

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
    @reactive.event(input.bbt_coverage)
    def handle_bbt_coverage_select():
        name = (input.bbt_coverage() or "").strip()
        if not name:
            return
        import pathlib
        bbt_path = pathlib.Path(__file__).parent / "data" / "bbt_coverages.geojson"
        if not bbt_path.exists():
            ui.notification_show("BBT coverage file not found.", type="error", duration=6)
            return
        try:
            gdf = gpd.read_file(str(bbt_path))
            row = gdf[gdf["Name"] == name]
            if row.empty:
                ui.notification_show(f"BBT '{name}' not found.", type="warning", duration=5)
                return
            boundary_polygon.set(row.to_crs(epsg=4326))
            generated_grid.set(None)
            sdm_covariates.set(None)
            sdm_results.set(None)
            ui.notification_show(f"BBT boundary loaded: {name}", type="message", duration=4)
        except Exception as exc:
            ui.notification_show(f"Failed to load BBT coverage: {exc}", type="error", duration=8)

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

    # ── SDM layer colour helpers ──────────────────────────────────────────────

    # Column names in sdm_covariates GDF → human label mapping
    _SDM_MAP_COLS = {
        "dominant_EUNIS":      "EUNIS 2007 L3 Habitat",
        "dominant_EUNIS2019":  "EUNIS 2019 L3 Habitat",
        "substrate_type":      "Seabed Substrate",
        "energy_class":        "Energy Class",
        "bio_zone":            "Biological Zone",
        "helcom_class":        "HELCOM HUB Class",
        "depth_m":             "Water Depth (m)",
        # Copernicus Marine
        **{col: lbl for col, lbl in eva_cmems.CMEMS_MAP_COLS.items()},
    }

    def _covariate_choices() -> dict:
        """Return {col: label} dict for available covariate columns in sdm_covariates."""
        cov = sdm_covariates.get()
        if cov is None:
            return {}
        return {col: lbl for col, lbl in _SDM_MAP_COLS.items() if col in cov.columns}

    @output
    @render.ui
    def map_layer_selector_ui():
        grid = generated_grid.get()
        if grid is None:
            return ui.div()
        choices = _covariate_choices()
        if not choices:
            return ui.div()
        choices_with_none = {"none": "— Grid only (no colour) —"} | choices
        return ui.div(
            ui.input_select(
                "map_covariate_layer",
                None,
                choices=choices_with_none,
                selected="none",
                width="100%",
            ),
            style=(
                "display: flex; align-items: center; gap: 0.5rem; "
                "padding: 0.4rem 0.6rem; background: #f8f9fa; "
                "border-bottom: 1px solid #dee2e6; font-size: 0.85rem;"
            ),
        )

    @output
    @render.ui
    def unified_map_output():
        boundary = boundary_polygon.get()
        grid = generated_grid.get()
        cov = sdm_covariates.get()
        polygon_source = input.polygon_source()
        selected_layer = "none"
        try:
            selected_layer = input.map_covariate_layer() or "none"
        except Exception:
            pass

        # Determine map center/zoom
        if boundary is not None:
            bounds = boundary.total_bounds
        elif grid is not None:
            bounds = grid.total_bounds
        else:
            bounds = None

        if bounds is not None:
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lng = (bounds[0] + bounds[2]) / 2
            zoom = eva_map.auto_zoom_level(bounds)
        else:
            center_lat, center_lng, zoom = 55.7, 21.1, 10

        m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom, tiles="OpenStreetMap")

        # Draw tools (always added; user activates via sidebar radio)
        if polygon_source == "draw":
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
            js_bridge = MacroElement()
            js_bridge._template = Template("""
                {% macro script(this, kwargs) %}
                (function(){
                    var map = {{ this._parent.get_name() }};
                    var drawnItems = new L.FeatureGroup();
                    map.addLayer(drawnItems);

                    map.eachLayer(function(layer) {
                        if (layer.options && layer.options.draw) {
                            layer.options.edit = layer.options.edit || {};
                            layer.options.edit.featureGroup = drawnItems;
                        }
                    });

                    map.on(L.Draw.Event.CREATED, function(e) {
                        drawnItems.addLayer(e.layer);
                        var geojson = JSON.stringify(drawnItems.toGeoJSON());
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

        # Boundary overlay
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

        # Grid overlay — plain or coloured by SDM covariate
        if grid is not None:
            use_cov = (
                selected_layer not in (None, "none", "")
                and cov is not None
                and selected_layer in cov.columns
            )
            if use_cov:
                # Merge covariate column onto grid for styling
                id_col = "Subzone ID" if "Subzone ID" in grid.columns else "Subzone_ID"
                grid_with_cov = grid.merge(
                    cov[["Subzone_ID", selected_layer]].rename(columns={"Subzone_ID": id_col}),
                    on=id_col,
                    how="left",
                )
                is_numeric = pd.api.types.is_numeric_dtype(grid_with_cov[selected_layer])
                # Per-variable colormaps: temperature uses RdYlBu_r, depth Blues, etc.
                _LAYER_COLORMAPS = {
                    "depth_m":          "Blues_09",
                    "sst_mean_c":       "RdYlBu_11",
                    "bottom_temp_c":    "RdYlBu_11",
                    "sss_mean":         "YlOrBr_09",
                    "mld_mean_m":       "PuBu_09",
                    "current_speed_ms": "PuBu_09",
                    "chl_mean":         "YlGn_09",
                    "o2_mean_mmol":     "RdBu_11",
                    "no3_mean_mmol":    "YlOrRd_09",
                    "ph_mean":          "PiYG_11",
                    "npp_mean":         "YlGn_09",
                }
                if is_numeric:
                    vals = grid_with_cov[selected_layer].dropna()
                    vmin = float(vals.min()) if len(vals) else 0.0
                    vmax = float(vals.max()) if len(vals) else 1.0
                    import branca.colormap as cm
                    cmap_name = _LAYER_COLORMAPS.get(selected_layer, "Blues_09")
                    colormap = getattr(cm.linear, cmap_name).scale(vmin, vmax)
                    colormap.caption = _SDM_MAP_COLS.get(selected_layer, selected_layer)
                    colormap.add_to(m)
                    color_dict = {}
                else:
                    cats = grid_with_cov[selected_layer].dropna().unique().tolist()
                    palette = [
                        "#e41a1c","#377eb8","#4daf4a","#984ea3","#ff7f00",
                        "#a65628","#f781bf","#999999","#66c2a5","#fc8d62",
                        "#8da0cb","#e78ac3","#a6d854","#ffd92f","#e5c494",
                    ]
                    color_dict = {cat: palette[i % len(palette)] for i, cat in enumerate(sorted(cats))}
                    colormap = None

                tooltip_fields = [id_col, selected_layer]
                tooltip_fields = [f for f in tooltip_fields if f in grid_with_cov.columns]

                def _make_style(row_col, is_num, c_dict, c_map, v_min, v_max):
                    def style_fn(feature):
                        val = feature["properties"].get(row_col)
                        if val is None or (isinstance(val, float) and np.isnan(val)):
                            return {"fillColor": "#cccccc", "color": "#999", "weight": 0.5, "fillOpacity": 0.5}
                        if is_num:
                            color = c_map(float(val))
                        else:
                            color = c_dict.get(str(val), "#cccccc")
                        return {"fillColor": color, "color": "#555", "weight": 0.5, "fillOpacity": 0.75}
                    return style_fn

                style_fn = _make_style(
                    selected_layer, is_numeric, color_dict,
                    colormap if is_numeric else None,
                    vmin if is_numeric else 0, vmax if is_numeric else 1,
                )
                folium.GeoJson(
                    grid_with_cov.to_json(),
                    style_function=style_fn,
                    tooltip=folium.GeoJsonTooltip(fields=tooltip_fields),
                    name=f"Hex Grid — {_SDM_MAP_COLS.get(selected_layer, selected_layer)}",
                ).add_to(m)

                # Add simple legend for categorical layers
                if not is_numeric and color_dict:
                    legend_items = "".join(
                        f'<li><span style="background:{c};width:14px;height:14px;display:inline-block;'
                        f'border-radius:2px;margin-right:5px;"></span>{html_escape(str(v))}</li>'
                        for v, c in list(color_dict.items())[:15]
                    )
                    layer_label = html_escape(_SDM_MAP_COLS.get(selected_layer, selected_layer))
                    legend_html = (
                        '<div style="position:fixed;bottom:30px;right:10px;z-index:1000;'
                        'background:white;padding:8px 12px;border-radius:6px;'
                        'box-shadow:0 1px 5px rgba(0,0,0,0.4);font-size:12px;max-height:300px;overflow-y:auto;">'
                        f'<b>{layer_label}</b>'
                        f'<ul style="list-style:none;padding:0;margin:4px 0 0;">{legend_items}</ul></div>'
                    )
                    m.get_root().html.add_child(folium.Element(legend_html))
            else:
                folium.GeoJson(
                    grid.to_json(),
                    style_function=lambda x: {
                        "fillColor": "#4da6ff",
                        "color": "#006994",
                        "weight": 1,
                        "fillOpacity": 0.3,
                    },
                    tooltip=folium.GeoJsonTooltip(fields=["Subzone ID"]),
                    name="Hex Grid",
                ).add_to(m)

        folium.plugins.Fullscreen(position='topright').add_to(m)
        folium.LayerControl().add_to(m)
        return ui.HTML(f'<div style="height: 650px;">{m._repr_html_()}</div>')

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
        except Exception as e:
            logger.error("Unexpected error parsing drawn polygon: %s", e)
            ui.notification_show(f"Could not process polygon: {e}", type="error", duration=6)

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
            # Generate raw grid first to get pre-clip count, then clip to sea
            grid_raw = eva_hexgrid.generate_h3_grid(boundary, resolution, clip_to_sea=False)
            land = eva_hexgrid._get_best_land_mask(grid_raw.total_bounds)
            grid = eva_hexgrid._clip_grid_to_sea(grid_raw, land) if land is not None else grid_raw
            if len(grid) == 0:
                ui.notification_show("All hexagons fall on land. Please draw a marine area.", type="error", duration=6)
                return
        except ValueError as e:
            ui.notification_show(str(e), type="error", duration=6)
            return
        land_removed = len(grid_raw) - len(grid)
        clip_note = f" ({land_removed} land cells removed)" if land_removed else ""
        if len(grid) > 5000:
            ui.notification_show(
                f"Warning: {len(grid)} cells generated{clip_note}. This may be slow. "
                "Consider using a coarser resolution.",
                type="warning", duration=8,
            )
        generated_grid.set(grid)
        # Auto-load into the map pipeline so the Map tab shows it immediately
        geo_data.set(grid[["Subzone ID", "geometry"]])
        geo_data_full.set(grid.copy())
        original_crs.set("EPSG:4326")
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
        ui.notification_show(f"Grid generated: {len(grid)} hexagonal cells{clip_note}", type="message", duration=5)

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
            preset = HEX_PRESETS.get(preset_key, HEX_PRESETS["mobile"])
            total_area_km2 = len(grid) * preset["area_km2"]
            parts.append(f"Grid: {len(grid)} cells, ~{total_area_km2:.1f} km²")
        if not parts:
            return ui.p("Upload a boundary file or draw a polygon on the map to get started.",
                        style="color: #6c757d; font-style: italic;")
        return ui.div(
            *[ui.p(p, style="margin: 0.3rem 0; font-weight: 500;") for p in parts],
            style="padding: 0.5rem; background: #e8f5e9; border-radius: 6px; margin-bottom: 1rem;",
        )

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
        original_crs.set("EPSG:4326")
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
                # Zipped shapefile — use POSIX path for a valid zip:// URI
                gdf = gpd.read_file(f"zip://{Path(file_path).as_posix()}")
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
            original_crs.set(None)

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
                                    (
                                        f"• Data range: {df[feature_cols].values.min():.2f} to {df[feature_cols].values.max():.2f}"
                                        if feature_cols else "• Data range: N/A (no feature columns)"
                                    ),
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

            # aq_results is derived from df, so indices are always identical;
            # no reindex needed — just concatenate on matching axes
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

        # Identify AQ columns for max-highlighting (exclude EV)
        aq_highlight_cols = [col for col in display_cols if col.startswith('AQ')]

        # Add data rows
        for idx, row in display_df.iterrows():
            # Find the AQ column with the max value for this row
            aq_values = {col: row[col] for col in aq_highlight_cols if pd.notna(row[col]) and isinstance(row[col], (int, float)) and row[col] > 0}
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
                        ui.value_box("Total EV (Sum)", f"{total_ev:.2f}", theme="primary"),
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
            try:
                mean_ev = ec['results']['EV'].mean() if ec['results'] is not None else 0
            except (KeyError, AttributeError):
                mean_ev = 0
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

        results = calculate_results()
        if results is None:
            raise ValueError("No results to export — upload data and run the analysis first.")
        return eva_export.generate_workbook(
            results=results,
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
        eunis_overlay.set(None)
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
            # Use detected_data_type (set synchronously on upload/restore) rather than
            # input.data_type() which may lag one flush behind during EC restore.
            entry.data_type = detected_data_type.get() or input.data_type()
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

    def _pa_custom_lookup():
        """Return {code: name} for all custom habitats currently defined."""
        return {h["code"]: h["name"] for h in pa_custom_habitats.get()}

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
    def _reset_pa_assignments_on_new_grid():
        """Reset habitat assignments when a new spatial grid is loaded."""
        if geo_data.get() is None:
            pa_habitat_assignments.set({})

    @reactive.Effect
    def _update_pa_assignments():
        """Collect all pa_assign_* dropdown values into a single dict.

        This effect depends on all pa_assign_* inputs reactively, so it
        re-runs whenever any habitat assignment dropdown changes.
        It also depends on geo_data so it re-runs after a new grid is loaded.
        """
        gdf = geo_data.get()
        if gdf is None:
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
        extent_df = pa_calculations.compute_extent(
            gdf, assignments, unit=unit, original_crs=crs,
            custom_lookup=_pa_custom_lookup(),
        )

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
        df = pa_calculations.compute_extent(
            gdf, assignments, unit=unit, original_crs=crs,
            custom_lookup=_pa_custom_lookup(),
        )
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
                    raw = input[f"supply_{slug}_{code}"]()
                except (KeyError, TypeError):
                    continue
                cleaned = pa_calculations.clean_supply_value(raw)
                if cleaned is not None:
                    quantities[code] = cleaned
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

        extent_df = pa_calculations.compute_extent(
            gdf, assignments, unit=unit, original_crs=crs,
            custom_lookup=_pa_custom_lookup(),
        ) if gdf is not None and assignments else pd.DataFrame()

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

        extent_df = pa_calculations.compute_extent(
            gdf, assignments, unit=unit, original_crs=crs,
            custom_lookup=_pa_custom_lookup(),
        ) if gdf is not None and assignments else pd.DataFrame()

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
        file_name = file_info[0].get("name", "").lower()
        allowed_exts = (".gpkg", ".geojson", ".json", ".zip", ".shp")
        if not any(file_name.endswith(ext) for ext in allowed_exts):
            ui.notification_show(
                f"Unsupported file type for EUNIS overlay. Please upload a GeoPackage (.gpkg), GeoJSON, or zipped shapefile.",
                type="error", duration=8,
            )
            return
        try:
            gdf = eunis_data.load_eunis_overlay(file_info[0]["datapath"])
            eunis_overlay.set(gdf)
            # Auto-populate habitat assignments from overlay (vectorized)
            has_eunis = gdf["dominant_EUNIS"].notna()
            assignments = (
                gdf.loc[has_eunis]
                .set_index("Subzone_ID")["dominant_EUNIS"]
                .astype(str)
                .to_dict()
            )
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

    # -----------------------------------------------------------------
    # Grid Setup → Section 4: Environmental covariates (EUNIS + SDM)
    # -----------------------------------------------------------------

    @reactive.Effect
    @reactive.event(input.fetch_eunis)
    def handle_fetch_eunis():
        grid = generated_grid.get()
        if grid is None:
            ui.notification_show(
                "Generate a grid first (Step 3) before fetching data.",
                type="warning", duration=5,
            )
            return
        selected = list(input.sdm_layers()) if input.sdm_layers() else ["eunis2007"]
        if not selected:
            ui.notification_show("Select at least one layer to fetch.", type="warning", duration=4)
            return
        layer_labels = [
            eva_eunis_wms.EUSM_LAYERS.get(k, {}).get("label", k) if k != "depth"
            else "Water depth"
            for k in selected
        ]
        ui.notification_show(
            f"Fetching {len(selected)} layer(s) for {len(grid)} hexagons: "
            f"{', '.join(layer_labels)}. This may take a minute…",
            type="message", duration=10,
        )
        try:
            covariates = eva_eunis_wms.fetch_sdm_covariates(grid, layers=selected)
        except Exception as exc:
            logger.error("SDM covariate fetch error: %s", exc)
            ui.notification_show(
                f"Could not fetch covariate data: {exc}. "
                "Check your internet connection or try uploading a custom habitat map.",
                type="error", duration=10,
            )
            return

        sdm_covariates.set(covariates)

        # If EUNIS was fetched, also update eunis_overlay for Physical Accounts
        if "eunis2007" in selected and "dominant_EUNIS" in covariates.columns:
            eunis_cols = ["Subzone_ID", "dominant_EUNIS", "dominant_EUNIS_name", "geometry"]
            overlay = gpd.GeoDataFrame(
                covariates[[c for c in eunis_cols if c in covariates.columns]],
                crs=covariates.crs,
            )
            # Add habitat_count / pct columns expected by eunis_data functions
            for col in ("habitat_count", "dominant_pct", "coverage_pct"):
                if col not in overlay.columns:
                    overlay[col] = overlay["dominant_EUNIS"].notna().astype(float) * 100.0
            eunis_overlay.set(overlay)
            _apply_eunis_overlay(overlay)
            n_eunis = int(overlay["dominant_EUNIS"].notna().sum())
            n_types = int(overlay["dominant_EUNIS"].nunique())
            logger.info("EUNIS overlay set: %d types, %d/%d hexagons", n_types, n_eunis, len(overlay))

        # Summary notification — warn about zero-coverage layers
        parts = []
        zero_coverage = []
        for key in selected:
            if key == "depth" and "depth_m" in covariates.columns:
                n = int(covariates["depth_m"].notna().sum())
                parts.append(f"depth: {n}")
            elif key in eva_eunis_wms.EUSM_LAYERS:
                col = eva_eunis_wms.EUSM_LAYERS[key]["col"]
                if col in covariates.columns:
                    n = int(covariates[col].notna().sum())
                    lbl = eva_eunis_wms.EUSM_LAYERS[key]["label"]
                    if n == 0:
                        note = eva_eunis_wms.EUSM_LAYERS[key].get("coverage", "")
                        zero_coverage.append(f"{lbl} ({note})")
                    else:
                        parts.append(f"{lbl}: {n}")
        msg = "✅ " + " · ".join(parts) if parts else "✅ Fetch complete."
        ui.notification_show(msg, type="message", duration=8)
        for lbl in zero_coverage:
            ui.notification_show(
                f"⚠️ No data returned for: {lbl}. "
                "This layer may not cover your study area.",
                type="warning", duration=10,
            )

    @reactive.Effect
    @reactive.event(input.upload_habitat_source)
    def handle_upload_habitat_source():
        file_info = input.upload_habitat_source()
        if file_info is None or len(file_info) == 0:
            return
        grid = generated_grid.get()
        if grid is None:
            ui.notification_show(
                "Generate a grid first (Step 3) before uploading a habitat map.",
                type="warning", duration=5,
            )
            return
        file_name = file_info[0].get("name", "").lower()
        allowed_exts = (".gpkg", ".geojson", ".json", ".zip")
        if not any(file_name.endswith(ext) for ext in allowed_exts):
            ui.notification_show(
                "Unsupported file type. Please upload GeoPackage (.gpkg), GeoJSON, or zipped Shapefile/GDB.",
                type="error", duration=8,
            )
            return
        ui.notification_show(
            "Reading habitat file and computing EUNIS overlay…", type="message", duration=5,
        )
        try:
            habitat_gdf = _read_habitat_file(file_info[0]["datapath"], file_name)
        except Exception as exc:
            logger.error("Habitat file read error: %s", exc)
            ui.notification_show(f"Could not read habitat file: {exc}", type="error", duration=10)
            return
        try:
            eunis_col = "EUNIScomb"
            name_col = "EUNIScombD" if "EUNIScombD" in habitat_gdf.columns else None
            overlay = eva_eunis_wms.compute_overlay_from_file(grid, habitat_gdf, eunis_col, name_col)
        except Exception as exc:
            logger.error("Habitat overlay error: %s", exc)
            ui.notification_show(f"Error computing EUNIS overlay: {exc}", type="error", duration=10)
            return
        eunis_overlay.set(overlay)
        _apply_eunis_overlay(overlay)
        n_with = int(overlay["dominant_EUNIS"].notna().sum())
        n_types = int(overlay["dominant_EUNIS"].nunique())
        ui.notification_show(
            f"✅ Habitat overlay: {n_types} EUNIS types assigned to {n_with}/{len(overlay)} hexagons.",
            type="message", duration=7,
        )

    def _read_habitat_file(path: str, file_name: str) -> gpd.GeoDataFrame:
        """Read a user-uploaded habitat polygon file (GPKG, GeoJSON, or ZIP)."""
        import zipfile, tempfile, shutil, fiona
        if file_name.endswith(".zip"):
            tmpdir = tempfile.mkdtemp()
            try:
                with zipfile.ZipFile(path) as z:
                    z.extractall(tmpdir)
                # Find GPKG, GeoJSON, SHP, or GDB inside the zip
                for root, dirs, files in os.walk(tmpdir):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        if fn.lower().endswith((".gpkg", ".geojson", ".json", ".shp")):
                            return gpd.read_file(fp)
                    for d in dirs:
                        if d.lower().endswith(".gdb"):
                            gdb_path = os.path.join(root, d)
                            layers = fiona.listlayers(gdb_path)
                            # Prefer layer with "eunis" or "euseamap" in name
                            layer = next(
                                (l for l in layers if "eunis" in l.lower() or "eusea" in l.lower()),
                                layers[0],
                            )
                            return gpd.read_file(gdb_path, layer=layer)
                raise FileNotFoundError("No recognised vector layer found inside ZIP.")
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
        return gpd.read_file(path)

    def _apply_eunis_overlay(overlay: gpd.GeoDataFrame):
        """Apply EUNIS overlay to PA habitat assignments."""
        has_eunis = overlay["dominant_EUNIS"].notna()
        assignments = (
            overlay.loc[has_eunis]
            .set_index("Subzone_ID")["dominant_EUNIS"]
            .astype(str)
            .to_dict()
        )
        pa_habitat_assignments.set(assignments)
        suggestions = eunis_data.suggest_feature_classifications(overlay, [])
        hfs_count = suggestions.get("_hfs_subzone_count", 0)
        if hfs_count > 0:
            ui.notification_show(
                f"Note: {hfs_count} subzones have reef/biogenic habitats (EUNIS A3/A4). "
                "Consider classifying relevant species as HFS/BH in the EC Features tab.",
                type="message", duration=8,
            )

    @output
    @render.ui
    def eunis_grid_status():
        grid = generated_grid.get()
        if grid is None:
            return ui.p(
                "Generate a grid first.",
                style="font-size: 0.8rem; color: #6c757d; margin-top: 0.4rem;",
            )
        cov = sdm_covariates.get()
        overlay = eunis_overlay.get()
        if cov is None and overlay is None:
            return ui.p(
                "No data fetched yet. Select layers and click 'Fetch Selected Layers'.",
                style="font-size: 0.8rem; color: #6c757d; margin-top: 0.4rem;",
            )
        rows = []
        # Show SDM covariate summary
        if cov is not None:
            for key, cfg in eva_eunis_wms.EUSM_LAYERS.items():
                col = cfg["col"]
                if col in cov.columns:
                    n = int(cov[col].notna().sum())
                    n_types = int(cov[col].nunique())
                    rows.append(f"✅ {cfg['label']}: {n_types} classes, {n}/{len(cov)} hexagons")
            if "depth_m" in cov.columns:
                n = int(cov["depth_m"].notna().sum())
                rows.append(f"✅ Water depth: {n}/{len(cov)} hexagons")
        elif overlay is not None:
            n_with = int(overlay["dominant_EUNIS"].notna().sum())
            n_types = int(overlay["dominant_EUNIS"].nunique())
            rows.append(f"✅ EUNIS L3: {n_types} types, {n_with}/{len(overlay)} hexagons")
        items = [ui.p(r, style="margin: 0.1rem 0; font-size: 0.82rem; color: #28a745; font-weight: 600;") for r in rows]
        return ui.div(*items, style="margin-top: 0.4rem;")

    @render.download(filename="eunis_overlay.gpkg")
    def download_eunis_overlay():
        overlay = eunis_overlay.get()
        if overlay is None:
            return
        with io.BytesIO() as buf:
            overlay.to_file(buf, driver="GPKG")
            yield buf.getvalue()

    @render.download(filename="sdm_covariates.csv")
    def download_sdm_covariates():
        cov = sdm_covariates.get()
        if cov is None:
            # Fallback: export EUNIS overlay as CSV
            overlay = eunis_overlay.get()
            if overlay is None:
                return
            cov = overlay
        df = cov.drop(columns="geometry", errors="ignore")
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        yield buf.getvalue().encode()

    # ── Copernicus Marine fetch ───────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.fetch_cmems)
    def handle_fetch_cmems():
        grid = generated_grid.get()
        if grid is None:
            ui.notification_show("⚠️ Generate a hex grid first.", type="warning")
            return

        layers = list(input.cmems_layers()) if input.cmems_layers() else []
        if not layers:
            ui.notification_show("⚠️ Select at least one CMEMS variable.", type="warning")
            return

        username = (input.cmems_username() or "").strip()
        password = (input.cmems_password() or "").strip()
        # Also accept env vars (handled inside fetch_cmems_covariates)

        bgc_start = int(input.cmems_start_year())
        bgc_end   = int(input.cmems_end_year())
        if bgc_start > bgc_end:
            ui.notification_show("⚠️ BGC start year must be ≤ end year.", type="warning")
            return

        ui.notification_show("🛰️ Connecting to Copernicus Marine Service…", type="message", duration=None, id="cmems-progress")

        try:
            covariates = eva_cmems.fetch_cmems_covariates(
                grid_gdf=grid,
                layers=layers,
                username=username,
                password=password,
                bgc_start_year=bgc_start,
                bgc_end_year=bgc_end,
            )

            # Merge with existing SDM covariates if present
            existing = sdm_covariates.get()
            if existing is not None:
                new_cols = [c for c in covariates.columns if c not in existing.columns]
                for col in new_cols:
                    existing = existing.copy()
                    existing[col] = covariates[col].values
                sdm_covariates.set(existing)
            else:
                sdm_covariates.set(covariates)

            # Report per-layer results
            msgs = []
            for lk in layers:
                col = eva_cmems.CMEMS_LAYERS[lk]["col"]
                cov_gdf = sdm_covariates.get()
                if cov_gdf is not None and col in cov_gdf.columns:
                    n = int(cov_gdf[col].notna().sum())
                    total = len(cov_gdf)
                    unit  = eva_cmems.CMEMS_LAYERS[lk]["unit"]
                    mean_val = cov_gdf[col].mean()
                    msgs.append(f"• {eva_cmems.CMEMS_LAYERS[lk]['label']}: {n}/{total} hexagons"
                                f" (mean={mean_val:.3g} {unit})")
                    if n == 0:
                        ui.notification_show(
                            f"⚠️ {eva_cmems.CMEMS_LAYERS[lk]['label']}: no data for this area.",
                            type="warning",
                        )

            ui.notification_show(
                f"✅ CMEMS fetch complete: {len(layers)} variable(s) added.\n" + "\n".join(msgs),
                type="message",
                duration=8,
                id="cmems-progress",
            )

        except ValueError as exc:
            ui.notification_show(str(exc), type="error", id="cmems-progress")
        except Exception as exc:
            ui.notification_show(
                f"❌ CMEMS fetch failed: {exc}", type="error", id="cmems-progress"
            )

    @output
    @render.ui
    def cmems_status():
        cov = sdm_covariates.get()
        if cov is None:
            return ui.div()
        cmems_cols = [c for c in eva_cmems.CMEMS_MAP_COLS if c in cov.columns]
        if not cmems_cols:
            return ui.div()
        rows = []
        for col in cmems_cols:
            lbl = eva_cmems.CMEMS_MAP_COLS[col]
            n = int(cov[col].notna().sum())
            mean_v = cov[col].mean()
            rows.append(ui.tags.li(f"{lbl}: {n} hexagons, mean={mean_v:.3g}"))
        return ui.div(
            ui.tags.ul(*rows, style="font-size: 0.78rem; margin: 0.3rem 0 0 1rem; color: #28a745;"),
            class_="info-box",
        )

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

        eva = cached_eva_data()
        if eva is None:
            ui.notification_show("EVA data not found.", type="error")
            return None

        unit = input.pa_area_unit()
        extent = eunis_data.compute_eunis_extent(overlay, unit=unit)
        condition = eunis_data.compute_eunis_condition(overlay, eva)
        supply = eunis_data.compute_eunis_supply(overlay, eva)
        accounts = eunis_data.build_accounts_summary(extent, condition)
        total_area_m2 = float(extent["area_m2"].sum()) if "area_m2" in extent.columns else 0.0
        missing = eunis_data.build_missing_values(overlay, eva, total_bbt_area_m2=total_area_m2)

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

        return pa_export.generate_bbt8_workbook(
            accounts=accounts, main_values=mv, extent=extent,
            condition=condition, supply=supply, metadata=metadata,
            missing_values=missing,
        )

    @render.download(
        filename=lambda: f"MARBEFES_BBT8_PhysicalAccounts_{pd.Timestamp.now().strftime('%Y%m%d')}.docx"
    )
    def pa_download_bbt8_docx():
        overlay = eunis_overlay.get()
        if overlay is None:
            ui.notification_show("Upload a EUNIS overlay first.", type="warning")
            return None

        eva = cached_eva_data()
        if eva is None:
            ui.notification_show("EVA data not found.", type="error")
            return None

        unit = input.pa_area_unit()
        extent = eunis_data.compute_eunis_extent(overlay, unit=unit)
        condition = eunis_data.compute_eunis_condition(overlay, eva)
        supply = eunis_data.compute_eunis_supply(overlay, eva)
        total_area_m2 = float(extent["area_m2"].sum()) if "area_m2" in extent.columns else 0.0
        missing = eunis_data.build_missing_values(overlay, eva, total_bbt_area_m2=total_area_m2)

        bbt_name = input.pa_eaa_name() or "Ecosystem Accounting Area"
        metadata = {
            "bbt_name": bbt_name,
            "eaa_name": bbt_name,
            "generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "accounting_year": str(input.pa_accounting_year() or ""),
        }

        try:
            return pa_docx.generate_bbt8_docx_report(
                overlay=overlay, eva=eva,
                extent=extent, condition=condition,
                supply=supply, missing=missing,
                metadata=metadata,
            )
        except Exception as exc:
            logger.exception("DOCX report generation failed")
            ui.notification_show(f"DOCX report failed: {exc}", type="error", duration=12)
            return None

    @reactive.Effect
    @reactive.event(pa_habitat_assignments)
    def _update_map_variable_for_pa():
        assignments = pa_habitat_assignments.get()
        base_choices = ["EV", "AQ1", "AQ2", "AQ3", "AQ4", "AQ5", "AQ6", "AQ7",
                        "AQ8", "AQ9", "AQ10", "AQ11", "AQ12", "AQ13", "AQ14", "AQ15"]
        if assignments:
            base_choices.append("Habitat Type (PA)")
        ui.update_select("map_variable", choices=base_choices)

    # ── SDM: dynamic UI ──────────────────────────────────────────────────────

    @output
    @render.ui
    def sdm_prereq_status():
        grid = generated_grid.get()
        cov  = sdm_covariates.get()
        data_source = input.sdm_data_source() if hasattr(input, "sdm_data_source") else "csv"
        if data_source == "dwca":
            data = sdm_dwca_df.get()
            data_label = "DwC-A sampling data"
            data_hint  = "Upload a Darwin Core Archive in the SDM panel"
        else:
            data = uploaded_data.get()
            data_label = "Sampling data uploaded"
            data_hint  = "No data (upload in Data Input)"
        items = []
        ok  = lambda msg: ui.tags.li(ui.tags.span("✅ ", style="color:green;"),  msg)
        bad = lambda msg: ui.tags.li(ui.tags.span("⚠️ ", style="color:orange;"), msg)
        items.append(ok("Hex grid ready")    if grid is not None else bad("No hex grid (run Grid Setup)"))
        items.append(ok("Covariates loaded") if cov  is not None else bad("No covariates (fetch in Grid Setup)"))
        items.append(ok(data_label)          if data is not None else bad(data_hint))
        return ui.tags.ul(items, style="padding-left:1rem;font-size:0.83rem;")

    @output
    @render.ui
    def sdm_predictor_checkboxes():
        cov = sdm_covariates.get()
        if cov is None:
            return ui.p("Fetch covariates first.", style="color:#999;font-size:0.82rem;")
        cols = eva_sdm.available_predictor_cols(cov)
        label_map = {
            "depth_m": "Depth (m)",
            "eunis_code": "EUNIS 2019 habitat",
            "substrate": "Substrate type",
            "sst_mean_c": "SST (°C)",
            "bottom_temp_c": "Bottom temp (°C)",
            "sss_mean": "Salinity (PSU)",
            "mld_mean_m": "Mixed layer depth (m)",
            "current_speed_ms": "Current speed (m/s)",
            "chl_mean": "Chlorophyll-a (mg/m³)",
            "o2_mean_mmol": "Dissolved O₂ (mmol/m³)",
            "no3_mean_mmol": "Nitrate (mmol/m³)",
            "ph_mean": "pH",
            "npp_mean": "Net primary production",
        }
        choices = {c: label_map.get(c, c) for c in cols}
        return ui.input_checkbox_group(
            "sdm_predictors", None,
            choices=choices,
            selected=list(choices.keys()),
            width="100%",
        )

    @reactive.effect
    @reactive.event(sdm_covariates, uploaded_data, sdm_dwca_df)
    def _update_sdm_response_choices():
        data_source = input.sdm_data_source() if hasattr(input, "sdm_data_source") else "csv"
        if data_source == "dwca":
            info = sdm_dwca_info.get()
            if info is None:
                ui.update_select("sdm_response_col", choices=[], label="Column with species data")
                return
            species = info.get("species_list", [])
            ui.update_select("sdm_response_col", choices=species,
                             selected=species[0] if species else None,
                             label="Species to model")
        else:
            data = uploaded_data.get()
            if data is None:
                ui.update_select("sdm_response_col", choices=[], label="Column with species data")
                return
            numeric_cols = [c for c in data.columns
                            if pd.api.types.is_numeric_dtype(data[c])
                            and c.lower() not in {"lat", "lon", "latitude", "longitude",
                                                  "x", "y", "subzone id"}]
            ui.update_select("sdm_response_col", choices=numeric_cols,
                             selected=numeric_cols[0] if numeric_cols else None)

    # ── SDM: DwC-A upload handler ─────────────────────────────────────────────

    @reactive.effect
    @reactive.event(input.sdm_dwca_file)
    def _handle_sdm_dwca_upload():
        files = input.sdm_dwca_file()
        if not files:
            return
        try:
            file_path = files[0]["datapath"]
            value_pref = input.sdm_dwca_value() if hasattr(input, "sdm_dwca_value") else "auto"
            df, info = dwca_reader.read_dwca_for_sdm(file_path, value=value_pref)
            sdm_dwca_df.set(df)
            sdm_dwca_info.set(info)
        except Exception as exc:
            logger.error("DwC-A SDM upload error: %s", exc)
            sdm_dwca_df.set(None)
            sdm_dwca_info.set({"error": str(exc)})

    @output
    @render.ui
    def sdm_dwca_status():
        info = sdm_dwca_info.get()
        if info is None:
            return ui.p("No DwC-A loaded yet.", style="color:#999;font-size:0.82rem;")
        if "error" in info:
            return ui.div(
                ui.tags.span("❌ Error: ", style="color:red;font-weight:600;"),
                ui.p(info["error"], style="color:red;font-size:0.82rem;"),
            )
        return ui.div(
            ui.p(
                f"✅ {info['n_sites']} sites · {info['n_species']} species "
                f"({info['value_type']})",
                style="color:green;font-weight:600;font-size:0.82rem;margin-bottom:0.25rem;",
            ),
            ui.p(
                "Species: " + ", ".join(info["species_list"][:8])
                + ("…" if len(info["species_list"]) > 8 else ""),
                style="font-size:0.78rem;color:#555;",
            ),
        )

    # ── SDM: data analysis & method recommendation ────────────────────────────

    @reactive.effect
    @reactive.event(input.sdm_response_col, input.sdm_data_source,
                    sdm_dwca_df, uploaded_data)
    def _auto_set_response_type():
        """Detect binary vs continuous from data and update the radio button."""
        data, lat_col, lon_col = _get_sdm_sample_df()
        response_col = input.sdm_response_col() if hasattr(input, "sdm_response_col") else None
        if data is None or not response_col or response_col not in data.columns:
            return
        y = pd.to_numeric(data[response_col], errors="coerce").dropna()
        if len(y) == 0:
            return
        unique = set(y.unique())
        if unique.issubset({0.0, 1.0}):
            ui.update_radio_buttons("sdm_response_type", selected="binary")
        elif all(float(v).is_integer() for v in unique):
            ui.update_radio_buttons("sdm_response_type", selected="count")
        else:
            ui.update_radio_buttons("sdm_response_type", selected="continuous")

    @output
    @render.ui
    def sdm_data_analysis():
        data, lat_col, lon_col = _get_sdm_sample_df()
        response_col = input.sdm_response_col() if hasattr(input, "sdm_response_col") else None
        cov = sdm_covariates.get()

        if data is None:
            return ui.div(
                ui.p("📂 Load sampling data (CSV or DwC-A) to see analysis and recommendations.",
                     style="color:#999;padding:1rem;"),
            )
        if not response_col or response_col not in data.columns:
            return ui.p("Select a response variable to analyse.", style="color:#999;padding:1rem;")

        try:
            info = eva_sdm.analyse_sampling_data(
                data, response_col, lat_col=lat_col, lon_col=lon_col,
                covariates_gdf=cov,
            )
        except Exception as exc:
            return ui.p(f"Analysis error: {exc}", style="color:red;padding:1rem;")

        if "error" in info:
            return ui.p(info["error"], style="color:red;padding:1rem;")

        # ── Build response histogram sparkline (inline SVG) ───────────────
        hist_svg = ""
        if info.get("response_hist"):
            counts = info["response_hist"]["counts"]
            if max(counts) > 0:
                bar_w = 18; gap = 2; h = 50
                c_max = max(counts)
                bars = ""
                for i, c in enumerate(counts):
                    bar_h = int(c / c_max * h) if c_max else 0
                    x = i * (bar_w + gap)
                    bars += (f'<rect x="{x}" y="{h - bar_h}" width="{bar_w}" '
                             f'height="{bar_h}" fill="#2980b9" opacity="0.7"/>')
                total_w = len(counts) * (bar_w + gap)
                hist_svg = (f'<svg width="{total_w}" height="{h}" '
                            f'style="display:block;margin:4px 0;">{bars}</svg>')

        # ── Data type badge ───────────────────────────────────────────────
        type_colors = {
            "binary":     ("#155724", "#d4edda"),
            "count":      ("#856404", "#fff3cd"),
            "continuous": ("#0c5460", "#d1ecf1"),
        }
        dt = info["data_type"]
        tc, bc = type_colors.get(dt, ("#333", "#eee"))
        type_badge = (f'<span style="background:{bc};color:{tc};padding:2px 8px;'
                      f'border-radius:10px;font-size:0.78rem;font-weight:600;">'
                      f'{dt.upper()}</span>')

        # ── Method recommendation card ────────────────────────────────────
        method = info["suggested_method"]
        method_label = eva_sdm._METHOD_LABELS.get(method, method)
        reason_items = "".join(f"<li>{r}</li>" for r in info["suggestion_reasons"])
        warn_items   = "".join(
            f'<li style="color:#856404;">⚠️ {w}</li>'
            for w in info["warnings"]
        )

        # Categorical covariate note
        cat_note = ""
        if info["categorical_cols"]:
            cat_cols_str = ", ".join(f"<code>{c}</code>" for c in info["categorical_cols"])
            cat_note = (
                f'<div style="background:#f8f9fa;border-left:3px solid #6c757d;'
                f'padding:8px 12px;margin-top:8px;border-radius:0 4px 4px 0;font-size:0.82rem;">'
                f'<strong>🏷️ Categorical predictors:</strong> {cat_cols_str}<br>'
                f'<span style="color:#555;">Tree methods (RF, XGBoost, LightGBM) handle these natively. '
                f'GAM and Kriging use automatic one-hot encoding — categories unseen during training '
                f'receive a zero vector, which is equivalent to the reference category.</span>'
                f'</div>'
            )

        html = f"""
<div style="font-size:0.85rem;padding:0.5rem;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
    <strong>Response:</strong> <code>{response_col}</code>
    {type_badge}
  </div>
  <table style="width:100%;border-collapse:collapse;font-size:0.82rem;margin-bottom:6px;">
    <tr><td style="color:#555;padding:1px 4px;">Sites:</td>
        <td><strong>{info['n_valid']}</strong> / {info['n_sites']} valid</td>
        <td style="color:#555;padding:1px 4px;">Prevalence:</td>
        <td><strong>{info['prevalence']:.1%}</strong></td></tr>
    <tr><td style="color:#555;padding:1px 4px;">Min / Max:</td>
        <td><strong>{info['response_min']:.3g} – {info['response_max']:.3g}</strong></td>
        <td style="color:#555;padding:1px 4px;">Zeros:</td>
        <td><strong>{info['n_zeros']}</strong> ({info['zero_inflation']:.0%})</td></tr>
    <tr><td style="color:#555;padding:1px 4px;">Mean ± SD:</td>
        <td colspan="3"><strong>{info['response_mean']:.3g} ± {info['response_std']:.3g}</strong></td></tr>
  </table>
  {hist_svg}
  <hr style="margin:8px 0;">
  <div style="background:#e8f4f8;border:1px solid #bee5eb;border-radius:6px;padding:10px;margin-bottom:8px;">
    <div style="font-weight:700;color:#0c5460;margin-bottom:4px;">
      💡 Recommended method: {method_label}
    </div>
    <ul style="margin:4px 0 0 0;padding-left:1.2rem;color:#555;">
      {reason_items}
      {warn_items}
    </ul>
  </div>
  {cat_note}
</div>"""
        return ui.HTML(html)

    # ── SDM: Fit & Predict handler ───────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.sdm_fit_btn)
    def _handle_sdm_fit():
        grid = generated_grid.get()
        cov  = sdm_covariates.get()

        data_source = input.sdm_data_source() if hasattr(input, "sdm_data_source") else "csv"
        if data_source == "dwca":
            data = sdm_dwca_df.get()
            auto_lat = "lat"
            auto_lon = "lon"
        else:
            data = uploaded_data.get()
            auto_lat = None
            auto_lon = None

        if grid is None or cov is None or data is None:
            sdm_fit_message.set("⚠️ Please complete prerequisites: hex grid, covariates, and data upload.")
            return

        response_col  = input.sdm_response_col()
        response_type = input.sdm_response_type()
        method        = input.sdm_method()
        predictor_cols = list(input.sdm_predictors()) if input.sdm_predictors() else []
        lat_col = (input.sdm_lat_col() or auto_lat or "lat").strip()
        lon_col = (input.sdm_lon_col() or auto_lon or "lon").strip()

        if not response_col:
            sdm_fit_message.set("⚠️ Select a response variable.")
            return
        if not predictor_cols:
            sdm_fit_message.set("⚠️ Select at least one predictor.")
            return
        if lat_col not in data.columns or lon_col not in data.columns:
            sdm_fit_message.set(f"⚠️ Columns '{lat_col}' / '{lon_col}' not found in uploaded data.")
            return

        sdm_fit_message.set("⏳ Extracting covariates at sampling sites…")

        try:
            # 1. Extract covariates at sampling sites
            sites_with_cov = eva_sdm.extract_covariates_at_sites(
                data, cov, lat_col=lat_col, lon_col=lon_col
            )

            # 2. Prepare features
            predictor_cols_available = [c for c in predictor_cols if c in sites_with_cov.columns]
            if not predictor_cols_available:
                sdm_fit_message.set("⚠️ None of the selected predictors found after covariate extraction.")
                return

            X, y, feat_names = eva_sdm.prepare_features(
                sites_with_cov, predictor_cols_available, response_col, response_type
            )

            idw_power       = float(input.sdm_idw_power() or 2.0)
            gam_splines     = int(input.sdm_gam_splines() or 10)
            ens_weight      = float(input.sdm_ensemble_weight() or 0.5)
            rf_trees        = int(getattr(input, "sdm_rf_trees", lambda: 200)() or 200)
            variogram_model = getattr(input, "sdm_variogram_model", lambda: "spherical")() or "spherical"

            gam_model = idw_model = kriging_model = rf_model = gp_model = rk_model = None
            xgb_model = lgbm_model = None

            # 3. Fit models based on selected method
            needs_gam     = method in ("gam", "ensemble")
            needs_idw     = method in ("idw", "ensemble")
            needs_kriging = method in ("kriging", "ensemble")
            needs_rf      = method in ("rf", "ensemble")
            needs_xgb     = method in ("xgboost",)
            needs_lgbm    = method in ("lightgbm",)
            needs_gp      = method in ("gp",)
            needs_rk      = method in ("regression_kriging",)

            if needs_gam:
                sdm_fit_message.set("⏳ Fitting GAM…")
                gam_model = eva_sdm.fit_gam(X, y, response_type, n_splines=gam_splines)

            if needs_idw:
                sdm_fit_message.set("⏳ Fitting IDW…")
                idw_model = eva_sdm.fit_idw(
                    sites_with_cov, response_col,
                    power=idw_power, lat_col=lat_col, lon_col=lon_col
                )

            if needs_kriging:
                sdm_fit_message.set(f"⏳ Fitting Ordinary Kriging ({variogram_model})…")
                kriging_model = eva_sdm.fit_kriging(
                    sites_with_cov, response_col,
                    variogram_model=variogram_model,
                    lat_col=lat_col, lon_col=lon_col,
                )

            if needs_rf:
                sdm_fit_message.set(f"⏳ Fitting Random Forest ({rf_trees} trees)…")
                rf_model = eva_sdm.fit_random_forest(
                    X, y, response_type=response_type, n_estimators=rf_trees
                )

            if needs_xgb:
                sdm_fit_message.set("⏳ Fitting XGBoost…")
                xgb_model = eva_sdm.fit_xgboost(
                    X, y, response_type=response_type, n_estimators=rf_trees
                )

            if needs_lgbm:
                sdm_fit_message.set("⏳ Fitting LightGBM…")
                lgbm_model = eva_sdm.fit_lightgbm(
                    X, y, response_type=response_type, n_estimators=rf_trees
                )

            if needs_gp:
                n_gp = len(y)
                if n_gp > 2000:
                    sdm_fit_message.set(
                        f"⏳ Fitting Gaussian Process ({n_gp} pts — may take a few minutes)…"
                    )
                else:
                    sdm_fit_message.set("⏳ Fitting Gaussian Process…")
                gp_model = eva_sdm.fit_gaussian_process(X, y, response_type=response_type)

            if needs_rk:
                sdm_fit_message.set(f"⏳ Fitting Regression Kriging (RF + {variogram_model} OK)…")
                rk_model = eva_sdm.fit_regression_kriging(
                    X, y, sites_with_cov, variogram_model=variogram_model,
                    n_estimators=rf_trees, lat_col=lat_col, lon_col=lon_col,
                )

            # 4. Predict for all grid cells
            sdm_fit_message.set("⏳ Predicting distribution over grid…")
            ens_weights = None
            if method == "ensemble":
                ens_weights = {}
                if gam_model:     ens_weights["gam"]     = ens_weight
                if idw_model:     ens_weights["idw"]     = (1.0 - ens_weight) * 0.5
                if kriging_model: ens_weights["kriging"] = (1.0 - ens_weight) * 0.5
                if rf_model:      ens_weights["rf"]      = (1.0 - ens_weight) * 0.5

            predictions, uncertainty = eva_sdm.predict_grid(
                cov, predictor_cols_available,
                gam_model=gam_model, idw_model=idw_model,
                kriging_model=kriging_model, rf_model=rf_model,
                xgb_model=xgb_model, lgbm_model=lgbm_model,
                gp_model=gp_model, rk_model=rk_model,
                method=method,
                ensemble_weights=ens_weights,
                response_type=response_type,
                lat_col=lat_col, lon_col=lon_col,
                feat_names=feat_names,
            )

            # 5. Diagnostics — in-sample predictions at sites
            primary = gam_model or rf_model or xgb_model or lgbm_model or gp_model
            if primary is not None:
                if gp_model is not None:
                    from sklearn.preprocessing import StandardScaler
                    scaler = getattr(gp_model, "_eva_scaler", None)
                    Xs = scaler.transform(X) if scaler else X
                    y_pred_sites = gp_model.predict(Xs)
                elif xgb_model is not None:
                    import warnings as _w
                    with _w.catch_warnings():
                        _w.simplefilter("ignore")
                        try:
                            from xgboost import XGBClassifier
                            if isinstance(xgb_model, XGBClassifier):
                                y_pred_sites = xgb_model.predict_proba(X)[:, 1]
                            else:
                                y_pred_sites = xgb_model.predict(X)
                        except ImportError:
                            y_pred_sites = xgb_model.predict(X)
                elif lgbm_model is not None:
                    import warnings as _w
                    with _w.catch_warnings():
                        _w.simplefilter("ignore")
                        try:
                            from lightgbm import LGBMClassifier
                            if isinstance(lgbm_model, LGBMClassifier):
                                y_pred_sites = lgbm_model.predict_proba(X)[:, 1]
                            else:
                                y_pred_sites = lgbm_model.predict(X)
                        except ImportError:
                            y_pred_sites = lgbm_model.predict(X)
                elif rf_model is not None:
                    from sklearn.ensemble import RandomForestClassifier
                    if isinstance(rf_model, RandomForestClassifier):
                        y_pred_sites = rf_model.predict_proba(X)[:, 1]
                    else:
                        y_pred_sites = rf_model.predict(X)
                else:
                    import warnings as _w
                    with _w.catch_warnings():
                        _w.simplefilter("ignore")
                        y_pred_sites = gam_model.predict(X)
            elif idw_model is not None:
                site_c = eva_sdm._sites_to_metric(sites_with_cov, lat_col, lon_col)
                y_pred_sites = idw_model.predict(site_c)
            elif kriging_model is not None:
                site_c = eva_sdm._sites_to_metric(sites_with_cov, lat_col, lon_col)
                import warnings as _w
                with _w.catch_warnings():
                    _w.simplefilter("ignore")
                    zk, _ = kriging_model.execute("points", site_c[:, 0], site_c[:, 1])
                y_pred_sites = zk.data
            else:
                y_pred_sites = predictions.reindex(range(len(y))).values

            diag = eva_sdm.model_diagnostics(
                y, y_pred_sites, response_type, feat_names,
                gam_model=gam_model, rf_model=rf_model,
                xgb_model=xgb_model, lgbm_model=lgbm_model,
            )

            sdm_results.set({
                "gam_model":      gam_model,
                "idw_model":      idw_model,
                "kriging_model":  kriging_model,
                "rf_model":       rf_model,
                "xgb_model":      xgb_model,
                "lgbm_model":     lgbm_model,
                "gp_model":       gp_model,
                "rk_model":       rk_model,
                "predictions":    predictions,
                "uncertainty":    uncertainty,
                "diagnostics":    diag,
                "feat_names":     feat_names,
                "response_col":   response_col,
                "method":         method,
                "n_sites":        len(y),
            })
            sdm_fit_message.set(f"✅ Done — {len(y)} sites, {len(cov)} grid cells predicted.")

        except Exception as e:
            import traceback
            sdm_fit_message.set(f"❌ Error: {e}")
            logger.error("SDM fit error: %s", traceback.format_exc())

    @output
    @render.ui
    def sdm_fit_status():
        msg = sdm_fit_message.get()
        if not msg:
            return ui.div()
        color = "#155724" if msg.startswith("✅") else ("#721c24" if msg.startswith("❌") else "#856404")
        bg    = "#d4edda" if msg.startswith("✅") else ("#f8d7da" if msg.startswith("❌") else "#fff3cd")
        return ui.div(msg, style=f"margin-top:8px;padding:8px;border-radius:4px;font-size:0.82rem;background:{bg};color:{color};")

    # ── SDM: Analyse Predictors handler ──────────────────────────────────────

    @reactive.effect
    @reactive.event(input.sdm_analyse_btn)
    def _handle_sdm_analyse():
        cov = sdm_covariates.get()
        data, lat_col, lon_col = _get_sdm_sample_df()

        if data is None or cov is None:
            sdm_analysis_message.set("⚠️ Load data and fetch covariates first.")
            return

        sdm_analysis_message.set("⏳ Running predictor analysis…")

        try:
            # Lazy import of analysis module
            _sdm_mod = _import_sdm_analyse()

            # Extract covariates at sampling sites
            sites_cov = eva_sdm.extract_covariates_at_sites(
                data, cov, lat_col=lat_col, lon_col=lon_col
            )

            # Identify species columns from data
            dwca_info = sdm_dwca_info.get()
            if dwca_info and "species_list" in dwca_info:
                species_list = dwca_info["species_list"]
            else:
                meta_cols = {"lat", "lon", "eventid", "locationid", "site_id",
                             "station", "date", "depth", "geometry"}
                species_list = [c for c in data.columns
                                if c.lower() not in meta_cols
                                and pd.api.types.is_numeric_dtype(data[c])]

            # Auto-select species across prevalence gradient
            selected = _sdm_mod.select_species(
                sites_cov, species_list, requested=None,
                min_prevalence=0.05, max_species=8
            )

            if not selected:
                sdm_analysis_message.set("⚠️ No species with sufficient prevalence (≥5%) found.")
                return

            # Run predictor comparison for each species
            sdm_analysis_message.set(f"⏳ Comparing predictors for {len(selected)} species…")
            species_results = {}
            for sp, prev, n_pres in selected:
                try:
                    species_results[sp] = _sdm_mod.compare_predictor_sets(
                        sites_cov, sp, do_cv=False
                    )
                except Exception as exc:
                    logger.warning("Predictor analysis failed for %s: %s", sp, exc)

            # Run collinearity analysis
            sdm_analysis_message.set("⏳ Analysing collinearity…")
            collinearity = _sdm_mod.analyse_collinearity(sites_cov)

            # Build habitat preference table
            hab_pref = _sdm_mod.habitat_preference_table(sites_cov, selected)

            # Method comparison on primary species
            sdm_analysis_message.set(f"⏳ Comparing methods for {selected[0][0]}…")
            method_results = _sdm_mod.compare_methods(
                sites_cov, selected[0][0], cov,
                methods=["rf", "kriging"],
            )

            sdm_analysis_results.set({
                "species_results": species_results,
                "species_info": selected,
                "collinearity": collinearity,
                "habitat_pref": hab_pref,
                "method_results": method_results,
                "n_sites": len(sites_cov),
            })
            sdm_analysis_message.set(f"✅ Analysis complete — {len(selected)} species, {len(sites_cov)} sites.")

        except Exception as e:
            import traceback
            sdm_analysis_message.set(f"❌ Analysis error: {e}")
            logger.error("SDM analysis error: %s", traceback.format_exc())

    @output
    @render.ui
    def sdm_analyse_status():
        msg = sdm_analysis_message.get()
        if not msg:
            return ui.div()
        color = "#155724" if msg.startswith("✅") else ("#721c24" if msg.startswith("❌") else "#856404")
        bg    = "#d4edda" if msg.startswith("✅") else ("#f8d7da" if msg.startswith("❌") else "#fff3cd")
        return ui.div(msg, style=f"margin-top:8px;padding:8px;border-radius:4px;font-size:0.82rem;background:{bg};color:{color};")

    @output
    @render.ui
    def sdm_predictor_analysis():
        res = sdm_analysis_results.get()
        if res is None:
            return ui.div(
                ui.p("🔬 Click ", ui.tags.strong("Analyse Predictors"),
                     " to compare environmental variables vs EUNIS habitats, "
                     "run collinearity checks, and evaluate method performance.",
                     style="color:#999;padding:1rem;"),
            )

        species_results = res["species_results"]
        species_info = res["species_info"]
        collinearity = res["collinearity"]
        hab_pref = res["habitat_pref"]
        method_results = res["method_results"]

        html_parts = ['<div style="font-size:0.85rem;padding:0.5rem;">']

        # ── 1. Predictor comparison table ──────────────────────────────────
        html_parts.append("""
<h5 style="color:#006994;margin-bottom:8px;">📊 Predictor Comparison (Random Forest)</h5>
<p style="font-size:0.8rem;color:#666;margin-bottom:6px;">
  Does adding EUNIS 2019 habitats improve species predictions over environmental variables alone?
</p>
<table style="width:100%;border-collapse:collapse;font-size:0.82rem;margin-bottom:12px;">
<thead>
<tr style="background:#f0f7fb;">
  <th style="padding:4px 8px;text-align:left;border-bottom:2px solid #006994;">Species</th>
  <th style="padding:4px 8px;text-align:right;border-bottom:2px solid #006994;">Prev.</th>
  <th style="padding:4px 8px;text-align:right;border-bottom:2px solid #006994;">R² env</th>
  <th style="padding:4px 8px;text-align:right;border-bottom:2px solid #006994;">R² EUNIS</th>
  <th style="padding:4px 8px;text-align:right;border-bottom:2px solid #006994;">R² both</th>
  <th style="padding:4px 8px;text-align:right;border-bottom:2px solid #006994;">Δ (both−env)</th>
</tr>
</thead>
<tbody>""")

        for sp, prev, n_pres in species_info:
            if sp not in species_results:
                continue
            sr = species_results[sp]
            r2_env = sr.get("env", {}).get("r2_train", float("nan"))
            r2_eunis = sr.get("eunis", {}).get("r2_train", float("nan"))
            r2_both = sr.get("both", {}).get("r2_train", float("nan"))
            delta = r2_both - r2_env if not (np.isnan(r2_both) or np.isnan(r2_env)) else float("nan")
            delta_color = "#155724" if delta > 0.01 else ("#721c24" if delta < -0.01 else "#666")

            html_parts.append(f"""
<tr style="border-bottom:1px solid #eee;">
  <td style="padding:3px 8px;"><em>{html_escape(sp)}</em></td>
  <td style="padding:3px 8px;text-align:right;">{prev:.0%}</td>
  <td style="padding:3px 8px;text-align:right;">{r2_env:.4f}</td>
  <td style="padding:3px 8px;text-align:right;">{r2_eunis:.4f}</td>
  <td style="padding:3px 8px;text-align:right;">{r2_both:.4f}</td>
  <td style="padding:3px 8px;text-align:right;color:{delta_color};font-weight:600;">
    {delta:+.4f}
  </td>
</tr>""")

        html_parts.append("</tbody></table>")

        # ── 2. Feature importance for top species ──────────────────────────
        html_parts.append('<h5 style="color:#006994;margin:12px 0 8px;">🎯 Top Features (combined model)</h5>')
        for sp, prev, _ in species_info[:3]:
            sr = species_results.get(sp, {})
            both = sr.get("both", {})
            imp = both.get("importances", {})
            if not imp:
                continue
            top5 = sorted(imp.items(), key=lambda x: -x[1])[:5]
            max_imp = top5[0][1] if top5 else 1

            html_parts.append(f'<div style="margin-bottom:10px;">')
            html_parts.append(f'<strong><em>{html_escape(sp)}</em></strong> '
                            f'<span style="color:#666;font-size:0.78rem;">(R²={both.get("r2_train", 0):.3f})</span>')
            for fname, val in top5:
                bar_w = int(val / max_imp * 120) if max_imp > 0 else 0
                is_eunis = "EUNIS" in fname or "eunis" in fname.lower()
                bar_color = "#e67e22" if is_eunis else "#2980b9"
                html_parts.append(
                    f'<div style="display:flex;align-items:center;gap:6px;font-size:0.78rem;margin:1px 0;">'
                    f'<span style="width:200px;text-overflow:ellipsis;overflow:hidden;white-space:nowrap;">'
                    f'<code>{html_escape(fname[:30])}</code></span>'
                    f'<span style="background:{bar_color};height:10px;width:{bar_w}px;border-radius:2px;display:inline-block;"></span>'
                    f'<span style="color:#666;">{val:.3f}</span></div>'
                )
            html_parts.append('</div>')

        html_parts.append(
            '<p style="font-size:0.75rem;color:#888;">Legend: '
            '<span style="background:#2980b9;padding:1px 8px;border-radius:2px;color:white;">env</span> '
            '<span style="background:#e67e22;padding:1px 8px;border-radius:2px;color:white;">EUNIS</span></p>'
        )

        # ── 3. Collinearity analysis ──────────────────────────────────────
        if collinearity and "error" not in collinearity:
            html_parts.append('<hr style="margin:12px 0;">')
            html_parts.append('<h5 style="color:#006994;margin-bottom:8px;">🔗 EUNIS–Environment Collinearity</h5>')

            # Habitat distribution
            hab_counts = collinearity.get("habitat_counts", {})
            if hab_counts:
                html_parts.append('<p style="font-size:0.78rem;color:#555;margin-bottom:4px;"><strong>Habitat distribution:</strong></p>')
                html_parts.append('<table style="font-size:0.78rem;border-collapse:collapse;margin-bottom:8px;">')
                for h, cnt in sorted(hab_counts.items(), key=lambda x: -x[1]):
                    html_parts.append(
                        f'<tr><td style="padding:1px 8px;">{html_escape(str(h))}</td>'
                        f'<td style="padding:1px 8px;text-align:right;"><strong>{cnt}</strong> sites</td></tr>'
                    )
                html_parts.append('</table>')

            # Depth by habitat
            depth_by = collinearity.get("depth_by_habitat", {})
            if depth_by:
                html_parts.append('<p style="font-size:0.78rem;color:#555;margin-bottom:4px;"><strong>Depth ranges by habitat:</strong></p>')
                html_parts.append('<table style="font-size:0.78rem;border-collapse:collapse;margin-bottom:8px;">')
                html_parts.append(
                    '<tr style="background:#f0f7fb;">'
                    '<th style="padding:2px 8px;text-align:left;">Habitat</th>'
                    '<th style="padding:2px 8px;text-align:right;">Sites</th>'
                    '<th style="padding:2px 8px;text-align:right;">Depth mean</th>'
                    '<th style="padding:2px 8px;">Depth range</th></tr>'
                )
                for h, d in sorted(depth_by.items(), key=lambda x: x[1].get("mean", 0) or 0):
                    html_parts.append(
                        f'<tr><td style="padding:1px 8px;">{html_escape(str(h))}</td>'
                        f'<td style="padding:1px 8px;text-align:right;">{d["count"]}</td>'
                        f'<td style="padding:1px 8px;text-align:right;">{d["mean"]:.1f} m</td>'
                        f'<td style="padding:1px 8px;">{d["min"]:.1f}–{d["max"]:.1f} m</td></tr>'
                    )
                html_parts.append('</table>')

            # Dummy correlations with depth
            corrs = collinearity.get("dummy_correlations", {})
            depth_corrs = corrs.get("depth_m", {})
            if depth_corrs:
                html_parts.append('<p style="font-size:0.78rem;color:#555;margin-bottom:4px;"><strong>EUNIS–depth correlation:</strong></p>')
                html_parts.append('<table style="font-size:0.78rem;border-collapse:collapse;margin-bottom:8px;">')
                for d_name, r in sorted(depth_corrs.items(), key=lambda x: -abs(x[1])):
                    bold = "font-weight:700;" if abs(r) >= 0.7 else ""
                    color = "#c0392b" if abs(r) >= 0.7 else "#333"
                    html_parts.append(
                        f'<tr><td style="padding:1px 8px;">{html_escape(d_name)}</td>'
                        f'<td style="padding:1px 8px;text-align:right;{bold}color:{color};">'
                        f'{r:+.3f}</td></tr>'
                    )
                html_parts.append('</table>')

            # Substrate
            substrate = collinearity.get("substrate_distribution", {})
            if substrate:
                html_parts.append('<p style="font-size:0.78rem;color:#555;margin-bottom:4px;"><strong>Substrate:</strong> ')
                parts = [f'{html_escape(str(k))} ({v} sites)' for k, v in substrate.items()]
                html_parts.append(", ".join(parts))
                html_parts.append('</p>')

        # ── 4. Habitat preference table ───────────────────────────────────
        if hab_pref is not None and len(hab_pref) > 0:
            html_parts.append('<hr style="margin:12px 0;">')
            html_parts.append('<h5 style="color:#006994;margin-bottom:8px;">🏠 Habitat Preference Patterns</h5>')
            html_parts.append('<div style="overflow-x:auto;">')
            html_parts.append('<table style="font-size:0.78rem;border-collapse:collapse;width:100%;">')
            # Header
            cols = list(hab_pref.columns)
            html_parts.append('<tr style="background:#f0f7fb;">')
            for c in cols:
                html_parts.append(f'<th style="padding:3px 6px;text-align:left;border-bottom:2px solid #006994;">{html_escape(str(c))}</th>')
            html_parts.append('</tr>')
            # Rows
            for _, row in hab_pref.iterrows():
                html_parts.append('<tr style="border-bottom:1px solid #eee;">')
                for c in cols:
                    val = str(row[c])
                    style = "padding:2px 6px;"
                    if c == "Species":
                        style += "font-style:italic;"
                    html_parts.append(f'<td style="{style}">{html_escape(val)}</td>')
                html_parts.append('</tr>')
            html_parts.append('</table></div>')

        # ── 5. Method comparison ──────────────────────────────────────────
        if method_results:
            html_parts.append('<hr style="margin:12px 0;">')
            html_parts.append(f'<h5 style="color:#006994;margin-bottom:8px;">⚖️ Method Comparison '
                            f'({html_escape(species_info[0][0])})</h5>')
            html_parts.append(
                '<table style="font-size:0.78rem;border-collapse:collapse;width:100%;margin-bottom:8px;">'
                '<tr style="background:#f0f7fb;">'
                '<th style="padding:3px 8px;text-align:left;border-bottom:2px solid #006994;">Method</th>'
                '<th style="padding:3px 8px;text-align:right;border-bottom:2px solid #006994;">R² (in-sample)</th>'
                '<th style="padding:3px 8px;text-align:right;border-bottom:2px solid #006994;">RMSE</th>'
                '<th style="padding:3px 8px;border-bottom:2px solid #006994;">Predictors</th></tr>'
            )
            for method_name, mr in method_results.items():
                if "error" in mr:
                    html_parts.append(
                        f'<tr><td style="padding:2px 8px;">{html_escape(method_name)}</td>'
                        f'<td colspan="3" style="padding:2px 8px;color:#c0392b;">Error: {html_escape(mr["error"])}</td></tr>'
                    )
                else:
                    r2 = mr.get("r2_insample", float("nan"))
                    rmse = mr.get("rmse_insample", float("nan"))
                    preds = mr.get("predictors", "—")
                    html_parts.append(
                        f'<tr style="border-bottom:1px solid #eee;">'
                        f'<td style="padding:2px 8px;">{html_escape(method_name)}</td>'
                        f'<td style="padding:2px 8px;text-align:right;">{r2:.4f}</td>'
                        f'<td style="padding:2px 8px;text-align:right;">{rmse:.4f}</td>'
                        f'<td style="padding:2px 8px;">{html_escape(str(preds))}</td></tr>'
                    )
            html_parts.append('</table>')

        # ── Conclusions ───────────────────────────────────────────────────
        html_parts.append('<hr style="margin:12px 0;">')
        html_parts.append('<div style="background:#f8f9fa;border-left:4px solid #006994;padding:10px 14px;border-radius:0 4px 4px 0;">')
        html_parts.append('<strong style="color:#006994;">💡 Key Findings</strong><ul style="margin:4px 0;padding-left:1.2rem;font-size:0.82rem;color:#555;">')

        # Auto-generate conclusions from data
        max_delta = 0
        for sp, sr in species_results.items():
            r2_env = sr.get("env", {}).get("r2_train", float("nan"))
            r2_both = sr.get("both", {}).get("r2_train", float("nan"))
            if not (np.isnan(r2_env) or np.isnan(r2_both)):
                max_delta = max(max_delta, abs(r2_both - r2_env))

        if max_delta < 0.01:
            html_parts.append(
                '<li>EUNIS habitats add <strong>negligible predictive value</strong> '
                f'(max Δ R² = {max_delta:.4f}). Environmental variables alone are sufficient.</li>'
            )
        else:
            html_parts.append(
                f'<li>EUNIS habitats show <strong>some additional value</strong> '
                f'(max Δ R² = {max_delta:.4f}).</li>'
            )

        depth_corrs = collinearity.get("dummy_correlations", {}).get("depth_m", {})
        max_corr = max((abs(v) for v in depth_corrs.values()), default=0)
        if max_corr >= 0.7:
            html_parts.append(
                f'<li>High collinearity between EUNIS and depth (max |r| = {max_corr:.2f}) '
                'explains the redundancy.</li>'
            )

        substrate = collinearity.get("substrate_distribution", {})
        if len(substrate) == 1:
            html_parts.append(
                '<li>Substrate is <strong>homogeneous</strong> — provides no discriminatory power.</li>'
            )

        html_parts.append('</ul></div>')
        html_parts.append('</div>')

        return ui.HTML("\n".join(html_parts))

    # ── SDM: sampling-site overlay helper ────────────────────────────────────

    def _get_sdm_sample_df():
        """Return the sampling DataFrame for the current SDM data source."""
        try:
            data_source = input.sdm_data_source()
        except Exception:
            data_source = "csv"
        if data_source == "dwca":
            return sdm_dwca_df.get(), "lat", "lon"
        else:
            data = uploaded_data.get()
            if data is None:
                return None, None, None
            lat_col = (input.sdm_lat_col() or "lat").strip() if hasattr(input, "sdm_lat_col") else "lat"
            lon_col = (input.sdm_lon_col() or "lon").strip() if hasattr(input, "sdm_lon_col") else "lon"
            # Fall back to common names if the explicit ones are missing
            if lat_col not in data.columns:
                for cand in ("lat", "latitude", "decimalLatitude", "y", "Y"):
                    if cand in data.columns:
                        lat_col = cand; break
            if lon_col not in data.columns:
                for cand in ("lon", "longitude", "decimalLongitude", "x", "X"):
                    if cand in data.columns:
                        lon_col = cand; break
            return data, lat_col, lon_col

    def _add_sdm_sample_sites(m, response_col=None):
        """
        Add a toggleable FeatureGroup of sampling site markers to folium map m.
        Markers are colour-coded by the response column value when available.
        """
        import branca.colormap as cm
        data, lat_col, lon_col = _get_sdm_sample_df()
        if data is None or lat_col not in data.columns or lon_col not in data.columns:
            return

        lats = pd.to_numeric(data[lat_col], errors="coerce")
        lons = pd.to_numeric(data[lon_col], errors="coerce")
        valid_mask = lats.notna() & lons.notna()
        if not valid_mask.any():
            return

        # Build colour scale from response column if available
        use_col = response_col if (response_col and response_col in data.columns) else None
        if use_col:
            vals = pd.to_numeric(data.loc[valid_mask, use_col], errors="coerce")
            v_min, v_max = float(vals.min(skipna=True)), float(vals.max(skipna=True))
            if v_max > v_min:
                site_cmap = cm.linear.BuPu_09.scale(v_min, v_max)
            else:
                site_cmap = None
        else:
            site_cmap = None

        fg = folium.FeatureGroup(name="Sampling sites", show=True)
        for idx in data.index[valid_mask]:
            lat = float(lats[idx]); lon = float(lons[idx])
            tip_parts = []
            if "site_id" in data.columns:
                tip_parts.append(f"Site: {data.at[idx, 'site_id']}")
            if use_col:
                v = data.at[idx, use_col]
                tip_parts.append(f"{use_col}: {v}")
                try:
                    fill = site_cmap(float(v)) if site_cmap else "#e67e22"
                except Exception:
                    fill = "#e67e22"
            else:
                fill = "#e67e22"

            folium.CircleMarker(
                location=[lat, lon],
                radius=6,
                color="#333",
                weight=1,
                fill=True,
                fill_color=fill,
                fill_opacity=0.85,
                tooltip="; ".join(tip_parts) if tip_parts else f"{lat:.4f}, {lon:.4f}",
            ).add_to(fg)
        fg.add_to(m)

    def _add_sdm_grid(m, grid):
        """Add the hex grid as a semi-transparent toggleable layer to folium map m."""
        if grid is None:
            return
        try:
            grid_4326 = grid.to_crs("EPSG:4326") if grid.crs and grid.crs.to_epsg() != 4326 else grid
            folium.GeoJson(
                grid_4326.__geo_interface__,
                style_function=lambda _: {
                    "fillColor": "none",
                    "color": "#1a6496",
                    "weight": 0.6,
                    "fillOpacity": 0,
                    "opacity": 0.5,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["Subzone ID"] if "Subzone ID" in grid_4326.columns else [],
                    aliases=["Subzone:"] if "Subzone ID" in grid_4326.columns else [],
                ),
                name="Hex Grid",
                show=True,
            ).add_to(m)
        except Exception as exc:
            logger.warning("Could not add grid to SDM map: %s", exc)

    # ── SDM: map output ──────────────────────────────────────────────────────

    @output
    @render.ui
    def sdm_map_output():
        import folium, branca.colormap as cm
        res = sdm_results.get()
        cov = sdm_covariates.get()
        grid = generated_grid.get()

        # ── No model yet: show grid + sampling sites if available ────────────
        if res is None or cov is None:
            data, lat_col, lon_col = _get_sdm_sample_df()
            if grid is not None:
                g4326 = grid.to_crs("EPSG:4326") if grid.crs and grid.crs.to_epsg() != 4326 else grid
                center = [float(g4326.geometry.centroid.y.mean()),
                          float(g4326.geometry.centroid.x.mean())]
                zoom = 7
            elif data is not None and lat_col in data.columns and lon_col in data.columns:
                lats = pd.to_numeric(data[lat_col], errors="coerce").dropna()
                lons = pd.to_numeric(data[lon_col], errors="coerce").dropna()
                if len(lats) > 0:
                    center = [float(lats.median()), float(lons.median())]
                    zoom = 7
                else:
                    center = [54.0, 21.0]; zoom = 5
            else:
                center = [54.0, 21.0]; zoom = 5
            m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB positron")
            folium.plugins.Fullscreen(position="topright").add_to(m)
            _add_sdm_grid(m, grid)
            _add_sdm_sample_sites(m)
            folium.LayerControl().add_to(m)
            if res is None:
                folium.Marker(center, popup="Fit the SDM model to see predictions.").add_to(m)
            return ui.HTML(m._repr_html_())

        predictions = res["predictions"]
        response_col = res["response_col"]

        plot_gdf = cov.copy()
        plot_gdf["sdm_pred"] = predictions.values

        center = [plot_gdf.geometry.centroid.y.mean(), plot_gdf.geometry.centroid.x.mean()]
        m = folium.Map(location=center, zoom_start=7, tiles="CartoDB positron")
        folium.plugins.Fullscreen(position="topright").add_to(m)

        valid = plot_gdf["sdm_pred"].dropna()
        if len(valid) == 0:
            return ui.div(
                ui.p("All grid cells have no prediction (all NaN). "
                     "Check that sampling sites overlap the study grid.",
                     style="color:#c00;padding:1rem;")
            )
        vmin, vmax = float(valid.min()), float(valid.max())
        colormap = cm.linear.YlOrRd_09.scale(vmin, vmax)
        colormap.caption = f"Predicted: {response_col}"
        colormap.add_to(m)

        plot_gdf_4326 = plot_gdf.to_crs("EPSG:4326")

        def style_fn(feature):
            val = feature["properties"].get("sdm_pred")
            try:
                color = colormap(float(val)) if val is not None and not (val != val) else "#cccccc"
            except Exception:
                color = "#cccccc"
            return {"fillColor": color, "fillOpacity": 0.75, "color": "none", "weight": 0}

        folium.GeoJson(
            plot_gdf_4326.__geo_interface__,
            style_function=style_fn,
            tooltip=folium.GeoJsonTooltip(
                fields=["sdm_pred"],
                aliases=[f"Predicted {response_col}:"],
                localize=True,
            ),
            name=f"SDM — {response_col}",
        ).add_to(m)

        _add_sdm_grid(m, grid)
        _add_sdm_sample_sites(m, response_col=response_col)

        folium.LayerControl().add_to(m)
        return ui.HTML(m._repr_html_())

    # ── SDM: diagnostics ─────────────────────────────────────────────────────

    @output
    @render.ui
    def sdm_diagnostics_output():
        res = sdm_results.get()
        if res is None:
            return ui.p("Run 'Fit & Predict' to see model diagnostics.", style="color:#999;")

        diag_html = eva_sdm.format_diagnostics_html(res["diagnostics"], res["feat_names"])
        method_labels = {
            "gam": "GAM", "idw": "IDW",
            "kriging": "Ordinary Kriging",
            "rf": "Random Forest",
            "xgboost": "XGBoost",
            "lightgbm": "LightGBM",
            "gp": "Gaussian Process",
            "regression_kriging": "Regression Kriging (RF + OK)",
            "ensemble": "Ensemble",
        }

        summary = ui.div(
            ui.h5(f"Model: {method_labels.get(res['method'], res['method'])}",
                  style="color:#006994;"),
            ui.p(f"Response: {res['response_col']} | Sites used: {res['n_sites']}",
                 style="font-size:0.85rem;color:#555;"),
            ui.HTML(diag_html),
        )
        return summary

    # ── SDM: uncertainty map ──────────────────────────────────────────────────

    @output
    @render.ui
    def sdm_uncertainty_map_output():
        import folium, branca.colormap as cm
        res = sdm_results.get()
        cov = sdm_covariates.get()

        if res is None or cov is None:
            return ui.p("Run 'Fit & Predict' using a Kriging or Gaussian Process method to see the uncertainty map.",
                        style="color:#999;padding:1rem;")

        uncertainty = res.get("uncertainty")
        if uncertainty is None:
            return ui.p("Uncertainty is only available for Kriging (variance) and Gaussian Process (std) methods.",
                        style="color:#888;padding:1rem;")

        plot_gdf = cov.copy()
        plot_gdf["sdm_unc"] = uncertainty.values

        center = [plot_gdf.geometry.centroid.y.mean(), plot_gdf.geometry.centroid.x.mean()]
        m = folium.Map(location=center, zoom_start=7, tiles="CartoDB positron")
        folium.plugins.Fullscreen(position="topright").add_to(m)

        valid = plot_gdf["sdm_unc"].dropna()
        if len(valid) == 0:
            return ui.p("No uncertainty values to display.", style="color:#999;padding:1rem;")
        vmin, vmax = float(valid.min()), float(valid.max())
        colormap = cm.linear.PuBu_09.scale(vmin, vmax)
        label = "Kriging variance" if res["method"] in ("kriging", "regression_kriging") else "GP std"
        colormap.caption = label
        colormap.add_to(m)

        plot_gdf_4326 = plot_gdf.to_crs("EPSG:4326")

        def style_unc(feature):
            val = feature["properties"].get("sdm_unc")
            try:
                color = colormap(float(val)) if val is not None and not (val != val) else "#eeeeee"
            except Exception:
                color = "#eeeeee"
            return {"fillColor": color, "fillOpacity": 0.75, "color": "none", "weight": 0}

        folium.GeoJson(
            plot_gdf_4326.__geo_interface__,
            style_function=style_unc,
            tooltip=folium.GeoJsonTooltip(
                fields=["sdm_unc"],
                aliases=[f"{label}:"],
                localize=True,
            ),
            name="Prediction uncertainty",
        ).add_to(m)

        _add_sdm_sample_sites(m)
        _add_sdm_grid(m, generated_grid.get())

        folium.LayerControl().add_to(m)
        return ui.HTML(m._repr_html_())

    # ── SDM: variogram ────────────────────────────────────────────────────────

    @output
    @render.ui
    def sdm_variogram_output():
        res = sdm_results.get()
        if res is None:
            return ui.p("Run a Kriging-based method to see the variogram.", style="color:#999;")

        km = res.get("kriging_model")
        if km is None:
            rk = res.get("rk_model")
            if rk is not None:
                km = getattr(rk, "ok_", None)  # pykrige RK exposes underlying OK
        if km is None:
            return ui.p("Variogram is only available for Ordinary Kriging and Regression Kriging methods.",
                        style="color:#888;")
        try:
            html = eva_sdm.plot_variogram_html(km, title="Variogram")
            return ui.HTML(html)
        except Exception as e:
            return ui.p(f"Could not render variogram: {e}", style="color:#c00;")

    @output
    @render.ui
    def sdm_partial_effects_output():
        res = sdm_results.get()
        if res is None:
            return ui.p("Run 'Fit & Predict' to see partial effects.", style="color:#999;")
        gam_model = res.get("gam_model")
        if gam_model is None:
            return ui.p("Partial effects are only available for GAM and Ensemble methods.",
                        style="color:#999;")
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            feat_names = res["feat_names"]
            n = len(feat_names)
            ncols = min(3, n)
            nrows = (n + ncols - 1) // ncols
            fig = make_subplots(rows=nrows, cols=ncols,
                                subplot_titles=[f for f in feat_names])
            for i, fname in enumerate(feat_names):
                row = i // ncols + 1
                col = i % ncols + 1
                XX = gam_model.generate_X_grid(term=i)
                pdep, confi = gam_model.partial_dependence(term=i, X=XX, width=0.95)
                x_vals = XX[:, i]
                fig.add_trace(go.Scatter(x=x_vals, y=pdep, mode="lines",
                                         name=fname, showlegend=False,
                                         line=dict(color="#006994", width=2)), row=row, col=col)
                fig.add_trace(go.Scatter(
                    x=list(x_vals) + list(x_vals[::-1]),
                    y=list(confi[:, 0]) + list(confi[:, 1][::-1]),
                    fill="toself", fillcolor="rgba(0,105,148,0.15)",
                    line=dict(color="rgba(255,255,255,0)"),
                    showlegend=False), row=row, col=col)
            fig.update_layout(height=280 * nrows, title="GAM Partial Effects (95% CI)",
                              font=dict(size=11))
            import plotly.io as pio
            return ui.HTML(pio.to_html(fig, full_html=False, include_plotlyjs="cdn"))
        except Exception as e:
            return ui.p(f"Could not render partial effects: {e}", style="color:#c00;")



# Create the app with static file serving


# Create the app with static file serving
app = App(app_ui, server, static_assets=Path(__file__).parent / "www")
