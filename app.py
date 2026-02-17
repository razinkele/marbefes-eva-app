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
import plotly.graph_objects as go
import plotly.express as px
import geopandas as gpd
import folium
import folium.plugins
import branca.colormap as cm
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Application Constants
MAX_FEATURES = 100  # Maximum number of features allowed
LOCALLY_RARE_THRESHOLD = 0.05  # 5% threshold for locally rare features
PERCENTILE_95 = 95  # 95th percentile for concentration calculations
MAX_EV_SCALE = 5  # Maximum value on the EV scale (0-5)
PREVIEW_ROWS_LIMIT = 10  # Number of rows to show in data preview
RESULTS_DISPLAY_LIMIT = 20  # Number of results to display in tables
MAX_FILE_SIZE_MB = 50  # Maximum file size for uploads in MB

# Custom CSS for enhanced styling
custom_css = """
<style>
    /* Main color scheme */
    :root {
        --primary-blue: #0066cc;
        --secondary-blue: #4da6ff;
        --accent-teal: #00b8d4;
        --success-green: #28a745;
        --ocean-blue: #006994;
        --light-bg: #f8f9fa;
    }
    
    /* Header styling */
    .navbar {
        background: linear-gradient(135deg, var(--ocean-blue) 0%, var(--accent-teal) 100%) !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        padding: 0.5rem 1rem;
    }
    
    .navbar-brand {
        font-weight: 700;
        font-size: 1.5rem;
        color: white !important;
        display: flex;
        align-items: center;
        gap: 15px;
    }
    
    .logo-container {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .logo-circle {
        width: 50px;
        height: 50px;
        background: linear-gradient(135deg, #fff 0%, #e3f2fd 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 1.2rem;
        color: var(--ocean-blue);
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        border: 3px solid rgba(255,255,255,0.3);
    }
    
    .nav-link {
        color: rgba(255,255,255,0.9) !important;
        font-weight: 500;
        transition: all 0.3s ease;
        border-radius: 5px;
        padding: 0.5rem 1rem;
    }
    
    .nav-link:hover {
        background-color: rgba(255,255,255,0.15);
        color: white !important;
    }
    
    .nav-link.active {
        background-color: rgba(255,255,255,0.25) !important;
        color: white !important;
        font-weight: 600;
    }
    
    /* Card enhancements */
    .card {
        border: none;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.07);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        overflow: hidden;
    }
    
    .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
    }
    
    .card-header {
        background: linear-gradient(135deg, var(--ocean-blue) 0%, var(--secondary-blue) 100%);
        color: white;
        font-weight: 600;
        font-size: 1.2rem;
        padding: 1rem 1.5rem;
        border-bottom: none;
    }
    
    .card-body {
        padding: 1.5rem;
    }
    
    /* Sidebar styling */
    .bslib-sidebar-layout > .sidebar {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
        border-right: 2px solid #dee2e6;
        border-radius: 8px 0 0 8px;
        padding: 1.5rem;
    }
    
    .sidebar h4 {
        color: var(--ocean-blue);
        font-weight: 700;
        margin-bottom: 1rem;
        border-bottom: 3px solid var(--accent-teal);
        padding-bottom: 0.5rem;
    }
    
    /* Button styling */
    .btn-primary {
        background: linear-gradient(135deg, var(--ocean-blue) 0%, var(--accent-teal) 100%);
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    .btn-primary:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }
    
    .btn-secondary {
        background: linear-gradient(135deg, #6c757d 0%, #5a6268 100%);
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
    }
    
    /* Input styling */
    .form-control, .form-select {
        border: 2px solid #dee2e6;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        transition: all 0.3s ease;
    }
    
    .form-control:focus, .form-select:focus {
        border-color: var(--accent-teal);
        box-shadow: 0 0 0 0.2rem rgba(0, 184, 212, 0.25);
    }
    
    /* Value box enhancements */
    .bslib-value-box {
        border-radius: 12px;
        border: none;
        box-shadow: 0 4px 8px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
    }
    
    .bslib-value-box:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 15px rgba(0,0,0,0.12);
    }
    
    .bslib-value-box .value-box-value {
        font-size: 2.5rem;
        font-weight: 700;
    }
    
    /* Table styling */
    table {
        border-radius: 8px;
        overflow: hidden;
    }
    
    table thead {
        background: linear-gradient(135deg, var(--ocean-blue) 0%, var(--secondary-blue) 100%);
        color: white;
    }
    
    table tbody tr:hover {
        background-color: rgba(0, 184, 212, 0.1);
    }
    
    /* Markdown content */
    .markdown-content {
        line-height: 1.8;
    }
    
    .markdown-content h3 {
        color: var(--ocean-blue);
        font-weight: 700;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid var(--accent-teal);
        padding-left: 1rem;
    }
    
    .markdown-content h4 {
        color: var(--ocean-blue);
        font-weight: 600;
        margin-top: 1rem;
    }
    
    .markdown-content code {
        background-color: #f8f9fa;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
        color: #e83e8c;
        font-size: 0.9em;
    }
    
    /* Horizontal rule */
    hr {
        border-top: 2px solid var(--accent-teal);
        margin: 1.5rem 0;
    }
    
    /* Welcome banner */
    .welcome-banner {
        background: linear-gradient(135deg, var(--ocean-blue) 0%, var(--accent-teal) 100%);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .welcome-banner h2 {
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .welcome-banner p {
        font-size: 1.1rem;
        opacity: 0.95;
    }
    
    /* Info boxes */
    .info-box {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-left: 4px solid var(--primary-blue);
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* Footer */
    .app-footer {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        color: white;
        padding: 1.5rem;
        text-align: center;
        margin-top: 2rem;
        border-radius: 12px;
        font-size: 0.9rem;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .card, .bslib-value-box {
        animation: fadeIn 0.5s ease-out;
    }
    
    /* Icons */
    .icon {
        margin-right: 8px;
    }
    
    /* Responsive adjustments */
    @media (max-width: 768px) {
        .navbar-brand {
            font-size: 1.2rem;
        }
        
        .logo-circle {
            width: 40px;
            height: 40px;
            font-size: 1rem;
        }
    }
    .classification-group {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 0.8rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid #006994;
    }
    .classification-group-header {
        font-weight: 600;
        color: #006994;
        margin-bottom: 0.5rem;
        font-size: 0.95rem;
    }
    .classification-help {
        font-size: 0.8rem;
        color: #6c757d;
        font-style: italic;
        margin-bottom: 0.3rem;
    }
    .classification-summary {
        background: linear-gradient(135deg, #e3f2fd 0%, #f1f8e9 100%);
        border-radius: 8px;
        padding: 0.8rem;
        margin-top: 1rem;
    }
    .feature-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 4px;
    }
    .aq-max-cell {
        background-color: #c8e6c9 !important;
        font-weight: 700;
        border: 2px solid #4caf50;
    }
</style>
"""

# App UI
app_ui = ui.page_navbar(
    ui.nav_panel(
        "🏠 Home",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div(
                    ui.div(
                        ui.div(
                            ui.HTML('<img src="marbefes.png" alt="MARBEFES Logo" style="height: 50px; margin-right: 10px;">'),
                            ui.HTML('<img src="iecs.png" alt="IECS Logo" style="height: 50px;">'),
                            style="display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem; padding: 10px; background: white; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"
                        ),
                        ui.h4("MARBEFES EVA", style="text-align: center; color: #006994; font-weight: 700;"),
                        ui.p("Phase 2 Assessment Tool", style="text-align: center; color: #6c757d; font-size: 0.9rem;"),
                        style="margin-bottom: 1.5rem;"
                    ),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("✨ Features", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.tags.ul(
                        ui.tags.li("📊 Calculate assessment questions (AQ)"),
                        ui.tags.li("🌍 Compute ecological value (EV)"),
                        ui.tags.li("📈 Aggregate total EV scores"),
                        style="line-height: 2; color: #495057;"
                    ),
                    class_="info-box"
                ),
                ui.hr(),
                ui.div(
                    ui.h5("📋 Quick Start", style="color: #006994; font-weight: 600; margin-bottom: 0.5rem;"),
                    ui.p(
                        "1. Upload your data",
                        ui.br(),
                        "2. Configure features",
                        ui.br(),
                        "3. View results",
                        style="line-height: 2; color: #495057;"
                    )
                ),
                width=320
            ),
            ui.div(
                # Welcome Banner
                ui.div(
                    ui.div(
                        ui.h1(
                            ui.div(
                                ui.HTML('<img src="marbefes.png" alt="MARBEFES Logo" style="height: 60px; margin-right: 15px;">'),
                                ui.span("MARBEFES", style="font-weight: 800;"),
                                ui.HTML('<img src="iecs.png" alt="IECS Logo" style="height: 60px; margin-left: 15px;">'),
                                style="display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem; justify-content: center;"
                            ),
                            style="margin: 0;"
                        ),
                        ui.h2("Ecological Value Assessment - Phase 2", style="font-weight: 300; font-size: 1.8rem; margin: 0.5rem 0;"),
                        ui.p(
                            "🇪🇺 Funded by the European Union's Horizon Europe Research Programme",
                            style="font-size: 1rem; margin-top: 1rem; opacity: 0.9;"
                        ),
                        class_="welcome-banner"
                    )
                ),
                
                # Main content cards
                ui.layout_column_wrap(
                    ui.card(
                        ui.card_header("🎯 About This Tool"),
                        ui.div(
                            ui.p(
                                "This application implements Phase 2 of the Ecological Value Assessment (EVA) framework, "
                                "providing a comprehensive toolkit for marine biodiversity assessment.",
                                style="font-size: 1.05rem; line-height: 1.8;"
                            ),
                            ui.tags.ul(
                                ui.tags.li("📍 Analyze gridded ecosystem data"),
                                ui.tags.li("🔬 Apply multiple assessment criteria"),
                                ui.tags.li("📊 Generate comprehensive EV scores"),
                                ui.tags.li("💾 Export results for further analysis"),
                                style="line-height: 2.2; font-size: 1rem;"
                            ),
                            class_="markdown-content"
                        )
                    ),
                    
                    ui.card(
                        ui.card_header("🚀 Getting Started"),
                        ui.div(
                            ui.tags.ol(
                                ui.tags.li(
                                    ui.strong("📖 Learn the Methodology: "),
                                    "Visit the Method tab for terminology and AQ guide"
                                ),
                                ui.tags.li(
                                    ui.strong("📁 Upload Your Data: "),
                                    "Use the Data Input tab with your CSV file"
                                ),
                                ui.tags.li(
                                    ui.strong("⚙️ Configure Features: "),
                                    "Set up your ecosystem components"
                                ),
                                ui.tags.li(
                                    ui.strong("📊 View Results: "),
                                    "Analyze AQ scores and EV values"
                                ),
                                ui.tags.li(
                                    ui.strong("💾 Export Data: "),
                                    "Download comprehensive results"
                                ),
                                style="line-height: 2.5; font-size: 1rem;"
                            ),
                            class_="markdown-content"
                        )
                    ),
                    width=1/2
                ),
                
                ui.hr(),
                
                # Key concepts
                ui.card(
                    ui.card_header("📖 Key Concepts"),
                    ui.layout_column_wrap(
                        ui.div(
                            ui.h4("EVA", style="color: #006994; font-weight: 700; margin-bottom: 0.5rem;"),
                            ui.p("Ecological Value Assessment", style="color: #6c757d; margin: 0;"),
                            ui.p("Framework for evaluating marine ecosystem importance", style="font-size: 0.9rem; margin-top: 0.5rem;"),
                            style="padding: 1rem; background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-radius: 8px;"
                        ),
                        ui.div(
                            ui.h4("EV", style="color: #00b8d4; font-weight: 700; margin-bottom: 0.5rem;"),
                            ui.p("Ecological Value", style="color: #6c757d; margin: 0;"),
                            ui.p("Quantitative measure of ecosystem significance", style="font-size: 0.9rem; margin-top: 0.5rem;"),
                            style="padding: 1rem; background: linear-gradient(135deg, #e0f7fa 0%, #b2ebf2 100%); border-radius: 8px;"
                        ),
                        ui.div(
                            ui.h4("AQ", style="color: #28a745; font-weight: 700; margin-bottom: 0.5rem;"),
                            ui.p("Assessment Questions", style="color: #6c757d; margin: 0;"),
                            ui.p("Criteria for evaluating ecological features", style="font-size: 0.9rem; margin-top: 0.5rem;"),
                            style="padding: 1rem; background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); border-radius: 8px;"
                        ),
                        ui.div(
                            ui.h4("EC", style="color: #ff9800; font-weight: 700; margin-bottom: 0.5rem;"),
                            ui.p("Ecosystem Component", style="color: #6c757d; margin: 0;"),
                            ui.p("Species or habitats being assessed", style="font-size: 0.9rem; margin-top: 0.5rem;"),
                            style="padding: 1rem; background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%); border-radius: 8px;"
                        ),
                        width=1/4
                    )
                ),
                
                # Footer
                ui.div(
                    ui.p(
                        "📄 ", ui.strong("Reference: "), 
                        "Franco A. and Amorim E. (2025) Ecological Value Assessment (EVA)",
                        style="margin: 0.5rem 0;"
                    ),
                    ui.p(
                        "👤 ", ui.strong("Template by: "), 
                        "A. Franco (15/10/2025)",
                        style="margin: 0.5rem 0;"
                    ),
                    ui.p(
                        "🔬 ", ui.strong("Project: "), 
                        "MARBEFES - Marine Biodiversity and Ecosystem Functioning",
                        style="margin: 0.5rem 0;"
                    ),
                    class_="app-footer"
                )
            )
        )
    ),
    
    ui.nav_panel(
        "📁 Data Input",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div(
                    ui.h5("🗂️ EC Management", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_select(
                        "select_ec",
                        "Saved ECs:",
                        choices=[],
                        width="100%"
                    ),
                    ui.div(
                        ui.input_action_button("save_ec", "💾 Save Current EC", class_="btn-primary btn-sm", style="margin-right: 0.3rem;"),
                        ui.input_action_button("new_ec", "➕ New EC", class_="btn-outline-secondary btn-sm", style="margin-right: 0.3rem;"),
                        ui.input_action_button("delete_ec", "🗑️ Delete", class_="btn-outline-danger btn-sm"),
                        style="display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.5rem;"
                    ),
                    ui.output_ui("ec_list_summary"),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("📝 Metadata", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_text(
                        "ec_name", 
                        "🏷️ EC Name:", 
                        placeholder="Enter ecosystem component name"
                    ),
                    ui.input_text(
                        "study_area", 
                        "📍 Study Area:", 
                        placeholder="Enter study area"
                    ),
                    ui.input_select(
                        "data_type",
                        "📊 Data Type:",
                        choices=["TO SPECIFY", "qualitative", "quantitative"]
                    ),
                    ui.input_text_area(
                        "data_description", 
                        "📄 Description:", 
                        placeholder="Describe your data",
                        rows=4
                    ),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("📤 Upload Data", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_file(
                        "upload_data", 
                        "Choose CSV File", 
                        accept=[".csv"], 
                        multiple=False,
                        button_label="Browse...",
                    ),
                    ui.download_button(
                        "download_template", 
                        "⬇️ Download Template",
                        class_="btn-secondary",
                        style="margin-top: 1rem; width: 100%;"
                    ),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("🗺️ Upload Spatial Grid", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.p(
                        "Optional: Upload a spatial grid file to enable map visualization.",
                        style="font-size: 0.9rem; color: #6c757d; line-height: 1.6;"
                    ),
                    ui.input_file(
                        "upload_geojson",
                        "Choose Spatial File",
                        accept=[".geojson", ".json", ".zip", ".gpkg"],
                        multiple=False,
                        button_label="Browse...",
                    ),
                    ui.p(
                        "Supported: GeoJSON, Zipped Shapefile (.zip), GeoPackage (.gpkg). "
                        "Each feature must have a 'Subzone ID' attribute matching the CSV data.",
                        style="font-size: 0.85rem; color: #ff9800; margin-top: 0.5rem;"
                    ),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("⚙️ Advanced Settings", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_slider(
                        "lrf_threshold",
                        "Locally Rare Threshold (%):",
                        min=1, max=20, value=5, step=1, post="%"
                    ),
                    ui.input_select(
                        "concentration_percentile",
                        "Concentration Percentile:",
                        choices={"90": "90th", "95": "95th", "99": "99th"},
                        selected="95"
                    ),
                    ui.input_select(
                        "results_display_limit",
                        "Results Display Limit:",
                        choices={"10": "10 rows", "20": "20 rows", "50": "50 rows", "0": "All rows"},
                        selected="20"
                    ),
                ),
                width=380
            ),
            ui.div(
                ui.card(
                    ui.card_header("📋 Data Input Instructions"),
                    ui.div(
                        ui.div(
                            ui.h4("📌 How to Input Your Data", style="color: #006994; font-weight: 600;"),
                            ui.p(
                                "This is where you upload your gridded data for a specific Ecosystem Component (EC).",
                                style="font-size: 1.05rem; line-height: 1.8;"
                            ),
                            ui.div(
                                ui.h5("⚠️ Important Notes", style="color: #ff9800; font-weight: 600; margin-top: 1.5rem;"),
                                ui.tags.ul(
                                    ui.tags.li("The spreadsheet accommodates one dataset per EC"),
                                    ui.tags.li("If multiple datasets are available, run separate assessments"),
                                    ui.tags.li("Data organization:", 
                                        ui.tags.ul(
                                            ui.tags.li(ui.strong("Rows: "), "Subzones (grid cells)"),
                                            ui.tags.li(ui.strong("Columns: "), "Features (species or habitats)")
                                        )
                                    ),
                                    style="line-height: 2;"
                                ),
                                class_="info-box"
                            ),
                            ui.div(
                                ui.h5("📝 Data Format", style="color: #28a745; font-weight: 600; margin-top: 1.5rem;"),
                                ui.tags.ul(
                                    ui.tags.li("Upload a CSV file with first row as feature names"),
                                    ui.tags.li("First column should contain Subzone IDs"),
                                    ui.tags.li("Remaining columns contain your feature data"),
                                    style="line-height: 2;"
                                ),
                                style="padding: 1rem; background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); border-radius: 8px; margin-top: 1rem;"
                            ),
                            ui.div(
                                ui.h5("💡 Example Structure", style="color: #006994; font-weight: 600; margin-top: 1.5rem;"),
                                ui.tags.pre(
                                    """Subzone ID, Habitat1, Habitat2, Habitat3, ...
A0, 1, 0, 1, ...
A1, 0, 1, 0, ...
A2, 1, 1, 0, ...""",
                                    style="background: #2d3748; color: #68d391; padding: 1rem; border-radius: 8px; font-size: 0.9rem;"
                                ),
                            ),
                            class_="markdown-content"
                        )
                    )
                ),
                ui.output_ui("validation_report_ui"),
                ui.output_ui("data_preview_ui"),
                ui.output_ui("geo_preview_ui")
            )
        )
    ),

    ui.nav_panel(
        "⚙️ EC Features",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div(
                    ui.h5("🔧 Configuration", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.p("Configure ecosystem component features and their characteristics.", style="line-height: 1.6;"),
                    ui.input_numeric(
                        "num_features",
                        "Number of Features:",
                        value=5,
                        min=1,
                        max=MAX_FEATURES
                    ),
                    ui.input_action_button(
                        "apply_features", 
                        "✓ Apply Configuration", 
                        class_="btn-primary",
                        style="width: 100%; margin-top: 1rem;"
                    ),
                ),
                width=320
            ),
            ui.div(
                ui.card(
                    ui.card_header("⚙️ Feature Configuration"),
                    ui.div(
                        ui.output_ui("features_config_ui"),
                        style="padding: 1rem;"
                    )
                ),
                ui.card(
                    ui.card_header("📊 Feature Summary Statistics"),
                    ui.div(
                        ui.output_table("features_summary_table"),
                        style="padding: 1rem;"
                    )
                )
            )
        )
    ),
    
    ui.nav_panel(
        "📊 AQ + EV Results",
        ui.div(
            ui.card(
                ui.card_header("📈 Assessment Questions and Ecological Value Results"),
                ui.div(
                    ui.div(
                        ui.h4("🎯 Calculated Results", style="color: #006994; font-weight: 600;"),
                        ui.p(
                            "This section displays Assessment Question (AQ) scores and Ecological Value (EV) for each subzone. "
                            "For detailed explanations of all Assessment Questions, visit the Method tab.",
                            style="font-size: 1.05rem; line-height: 1.8;"
                        ),
                        class_="markdown-content"
                    ),
                    ui.hr(),
                    ui.output_ui("results_ui"),
                    style="padding: 1rem;"
                )
            )
        )
    ),
    
    ui.nav_panel(
        "🏆 Total EV",
        ui.div(
            ui.card(
                ui.card_header("🏆 Total Ecological Value Across All ECs"),
                ui.div(
                    ui.div(
                        ui.h4("📊 Aggregated Ecological Values", style="color: #006994; font-weight: 600;"),
                        ui.p(
                            "This section aggregates the ecological values across all ecosystem components.",
                            style="font-size: 1.05rem; line-height: 1.8; margin-bottom: 2rem;"
                        ),
                        ui.div(
                            ui.p("💡 ", ui.strong("Total EV: "), "Sum of all EV values for each subzone", style="margin: 0.5rem 0;"),
                            ui.p("📍 Individual EV contributions from each EC are shown below", style="margin: 0.5rem 0;"),
                            class_="info-box"
                        ),
                    ),
                    ui.output_ui("total_ev_ui"),
                    ui.hr(),
                    ui.div(
                        ui.download_button(
                            "download_results",
                            "📊 Download Complete Analysis (Excel)",
                            class_="btn-primary",
                            style="font-size: 1.1rem; padding: 0.8rem 2rem;"
                        ),
                        ui.p(
                            "Includes: Summary, Metadata, Original Data, AQ Results, Feature Classifications, Methodology Reference",
                            style="margin-top: 0.5rem; color: #6c757d; font-size: 0.9rem; text-align: center;"
                        )
                    ),
                    style="padding: 1rem;"
                )
            )
        )
    ),
    
    ui.nav_panel(
        "📈 Visualization",
        ui.card(
            ui.card_header("📈 Data Visualization"),
            ui.layout_sidebar(
                ui.sidebar(
                    ui.h5("🎨 Chart Options", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_select(
                        "plot_type",
                        "Visualization Type:",
                        choices=["EV by Subzone", "Feature Distribution", "AQ Scores",
                                 "AQ Breakdown by Subzone", "AQ Radar Comparison", "AQ Heatmap"]
                    ),
                    ui.input_select(
                        "color_scheme",
                        "Color Scheme:",
                        choices=["Viridis", "Plasma", "Blues", "Greens"]
                    ),
                    ui.panel_conditional(
                        "input.plot_type === 'AQ Radar Comparison'",
                        ui.input_selectize(
                            "radar_subzones",
                            "Select Subzones to Compare (max 5):",
                            choices=[],
                            multiple=True,
                            options={"maxItems": 5, "placeholder": "Upload data first..."}
                        )
                    ),
                    width=280
                ),
                ui.div(
                    ui.output_ui("visualization_ui"),
                    style="padding: 1.5rem;"
                )
            )
        )
    ),

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

    ui.nav_panel(
        "📖 Method",
        ui.div(
            ui.div(
                ui.h2("📖 EVA Methodology Reference", style="color: #006994; font-weight: 700; margin-bottom: 1.5rem;"),
                ui.p(
                    "Comprehensive guide to the Ecological Value Assessment framework terminology and methodology.",
                    style="font-size: 1.1rem; color: #6c757d; margin-bottom: 2rem;"
                )
            ),

            # Acronyms Table
            ui.card(
                ui.card_header("🔤 EVA Terminology Reference"),
                ui.div(
                    ui.output_table("acronyms_table"),
                    style="padding: 1rem;"
                )
            ),

            # Assessment Questions Guide
            ui.card(
                ui.card_header("ℹ️ Assessment Questions (AQ) Guide"),
                ui.div(
                    ui.p(
                        "Detailed explanations of all 15 Assessment Questions used in the EVA methodology.",
                        style="margin-bottom: 1.5rem; font-size: 1.05rem; color: #495057;"
                    ),
                    ui.output_ui("aq_guide_content"),
                    style="padding: 1rem;"
                )
            )
        )
    ),

    title=ui.div(
        ui.HTML('<img src="marbefes.png" alt="MARBEFES Logo" style="height: 35px; margin-right: 10px;">'),
        ui.span("MARBEFES EVA Phase 2", style="font-weight: 700;"),
        style="display: flex; align-items: center;",
        class_="logo-container"
    ),
    id="navbar",
    header=ui.tags.head(
        ui.HTML(custom_css)
    )
)


# Server logic
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
    validation_report = reactive.Value(None)

    # Multi-EC support
    ec_store = reactive.Value({})      # {ec_name: {data, data_type, classifications, results, feature_count}}
    current_ec = reactive.Value(None)  # Name of the active EC

    def detect_data_type(df):
        """
        Automatically detect if data is qualitative or quantitative

        Logic:
        - Qualitative: Binary data (only 0 and 1 values, or very few unique values)
        - Quantitative: Continuous data (many unique values, decimals, or range > 1)
        """
        feature_cols = [col for col in df.columns if col != 'Subzone ID']

        # Analyze each feature column
        is_binary_count = 0
        is_continuous_count = 0

        for col in feature_cols:
            values = df[col].dropna()
            if len(values) == 0:
                continue

            unique_values = values.unique()
            num_unique = len(unique_values)

            # Check if binary (only 0 and 1)
            is_binary = set(unique_values).issubset({0, 1, 0.0, 1.0})

            # Check if has decimals
            try:
                has_decimals = any(
                    isinstance(v, (int, float)) and v != int(v)
                    for v in values if pd.notna(v) and v != 0
                )
            except (TypeError, ValueError):
                has_decimals = False

            # Check value range
            val_range = values.max() - values.min() if len(values) > 0 else 0

            # Decision logic
            if is_binary:
                is_binary_count += 1
            elif has_decimals or val_range > 1 or num_unique > 10:
                is_continuous_count += 1
            else:
                # Few unique values, likely categorical/qualitative
                is_binary_count += 1

        # Determine overall data type (default to qualitative if no data)
        if is_binary_count == 0 and is_continuous_count == 0:
            return "qualitative"
        elif is_binary_count > is_continuous_count:
            return "qualitative"
        else:
            return "quantitative"
    
    # Acronyms table
    @output
    @render.table
    def acronyms_table():
        acronyms = {
            "Acronym": ["EVA", "EV", "EC", "AQ", "LRF", "RRF", "NRF", "ROF", "ESF", "HFS", "BH", "SS"],
            "Full Name": [
                "Ecological value assessment",
                "Ecological value",
                "Ecosystem component",
                "Assessment question",
                "Locally rare feature",
                "Regionally rare feature",
                "Nationally rare feature",
                "Regularly occurring feature",
                "Ecologically significant feature",
                "Habitat forming species",
                "Biogenic habitat",
                "Symbiotic species"
            ]
        }
        return pd.DataFrame(acronyms)

    # AQ Guide Content
    @output
    @render.ui
    def aq_guide_content():
        return ui.HTML(get_aq_guide_html())

    def get_aq_guide_html():
        """Generate comprehensive AQ guide HTML"""
        return """
        <div style="line-height: 1.8;">
            <h4 style="color: #006994; margin-top: 1.5rem; margin-bottom: 1rem;">🔍 Rarity-Based Assessment Questions</h4>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #2196F3;">
                <h5 style="color: #2196F3; margin-top: 0;"><strong>AQ1</strong> - Locally Rare Features (LRF) - Qualitative</h5>
                <p><strong>Purpose:</strong> Identifies features that are rare at the local scale.</p>
                <p><strong>Applies to:</strong> Qualitative (presence/absence) data only</p>
                <p><strong>Calculation:</strong> Average of rescaled values for features present in ≤5% of subzones</p>
                <p><strong>Returns NaN when:</strong> No features are locally rare (all occur in >5% of subzones)</p>
                <p><strong>Higher values indicate:</strong> More locally rare features present in the subzone</p>
            </div>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #2196F3;">
                <h5 style="color: #2196F3; margin-top: 0;"><strong>AQ2</strong> - Locally Rare Features (LRF) - Quantitative</h5>
                <p><strong>Purpose:</strong> Measures abundance of locally rare features.</p>
                <p><strong>Applies to:</strong> Quantitative (count/measurement) data only</p>
                <p><strong>Calculation:</strong> Average abundance of locally rare features</p>
                <p><strong>Returns NaN when:</strong> Qualitative data or when no LRF exist</p>
            </div>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #ff9800;">
                <h5 style="color: #ff9800; margin-top: 0;"><strong>AQ3</strong> - Regionally Rare Features (RRF) - Qualitative</h5>
                <p><strong>Purpose:</strong> Identifies features defined as regionally rare.</p>
                <p><strong>Applies to:</strong> Qualitative data with RRF-classified features</p>
                <p><strong>Calculation:</strong> Average of rescaled values for RRF-classified features</p>
                <p><strong>Returns NaN when:</strong> No features classified as RRF</p>
            </div>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #ff9800;">
                <h5 style="color: #ff9800; margin-top: 0;"><strong>AQ4</strong> - Regionally Rare Features (RRF) - Quantitative</h5>
                <p><strong>Purpose:</strong> Measures abundance of regionally rare features.</p>
                <p><strong>Applies to:</strong> Quantitative data with RRF-classified features</p>
                <p><strong>Returns NaN when:</strong> Qualitative data or no RRF</p>
            </div>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #d32f2f;">
                <h5 style="color: #d32f2f; margin-top: 0;"><strong>AQ5</strong> - Nationally Rare Features (NRF) - Qualitative</h5>
                <p><strong>Purpose:</strong> Highest rarity classification - nationally rare features.</p>
                <p><strong>Applies to:</strong> Qualitative data with NRF features</p>
                <p><strong>Returns NaN when:</strong> No features classified as NRF</p>
            </div>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #d32f2f;">
                <h5 style="color: #d32f2f; margin-top: 0;"><strong>AQ6</strong> - Nationally Rare Features (NRF) - Quantitative</h5>
                <p><strong>Purpose:</strong> Abundance of nationally rare features.</p>
                <p><strong>Applies to:</strong> Quantitative data with NRF features</p>
                <p><strong>Returns NaN when:</strong> Qualitative data or no NRF</p>
            </div>

            <h4 style="color: #006994; margin-top: 2rem; margin-bottom: 1rem;">⭐ General Assessment</h4>

            <div style="background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%); padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #ff9800;">
                <h5 style="color: #ff9800; margin-top: 0;"><strong>AQ7</strong> - All Features - Qualitative ⭐</h5>
                <p><strong>Purpose:</strong> Uses ALL features without any classification filter.</p>
                <p><strong>Applies to:</strong> Qualitative data</p>
                <p><strong>Special:</strong> ALWAYS ACTIVE for qualitative data - does not require rare features</p>
                <p><strong>Calculation:</strong> Average of rescaled values for ALL features</p>
                <p><strong>Why important:</strong> Provides baseline assessment when no features meet special criteria</p>
            </div>

            <h4 style="color: #006994; margin-top: 2rem; margin-bottom: 1rem;">📍 Occurrence-Based Assessment Questions</h4>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #28a745;">
                <h5 style="color: #28a745; margin-top: 0;"><strong>AQ8</strong> - Regularly Occurring Features (ROF) - Quantitative</h5>
                <p><strong>Purpose:</strong> Assesses features that occur regularly (>5% of subzones).</p>
                <p><strong>Applies to:</strong> Quantitative data only</p>
                <p><strong>Calculation:</strong> Average abundance of regularly occurring features</p>
                <p><strong>Returns NaN when:</strong> Qualitative data</p>
            </div>

            <div style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #28a745;">
                <h5 style="color: #28a745; margin-top: 0;"><strong>AQ9</strong> - ROF Concentration-Weighted - Quantitative 🔬</h5>
                <p><strong>Purpose:</strong> Most complex calculation - identifies spatial hotspots of regularly occurring features.</p>
                <p><strong>Applies to:</strong> Quantitative data only</p>
                <p><strong>Special 3-step calculation:</strong></p>
                <ol style="margin-left: 1.5rem;">
                    <li><strong>Step 1:</strong> Normalize by mean: <code>value / feature_mean</code></li>
                    <li><strong>Step 2:</strong> Weight by concentration: <code>(% in top 5% / occurrence count) × normalized_value</code></li>
                    <li><strong>Step 3:</strong> Rescale to 0-5: <code>5 × weighted / MAX(all_weighted)</code></li>
                </ol>
                <p><strong>Returns NaN when:</strong> Qualitative data</p>
                <p><strong>Higher values indicate:</strong> Subzones with concentrated abundances of regularly occurring features</p>
            </div>

            <h4 style="color: #006994; margin-top: 2rem; margin-bottom: 1rem;">🌿 Ecological Significance Assessment Questions</h4>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #00b8d4;">
                <h5 style="color: #00b8d4; margin-top: 0;"><strong>AQ10</strong> - Ecologically Significant Features (ESF) - Qualitative</h5>
                <p><strong>Purpose:</strong> Identifies keystone species and ecosystem engineers.</p>
                <p><strong>Examples:</strong> Keystone predators, ecosystem engineers</p>
                <p><strong>Returns NaN when:</strong> No features classified as ESF</p>
            </div>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #00b8d4;">
                <h5 style="color: #00b8d4; margin-top: 0;"><strong>AQ11</strong> - Ecologically Significant Features (ESF) - Quantitative</h5>
                <p><strong>Purpose:</strong> Abundance of ecologically important features.</p>
                <p><strong>Returns NaN when:</strong> Qualitative data or no ESF</p>
            </div>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #9c27b0;">
                <h5 style="color: #9c27b0; margin-top: 0;"><strong>AQ12</strong> - Habitat Forming Species/Biogenic Habitat (HFS/BH) - Qualitative</h5>
                <p><strong>Purpose:</strong> Features creating habitat structure.</p>
                <p><strong>Examples:</strong> Corals, seagrasses, oyster reefs, kelp forests, sponge grounds</p>
                <p><strong>Returns NaN when:</strong> No features classified as HFS/BH</p>
            </div>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #9c27b0;">
                <h5 style="color: #9c27b0; margin-top: 0;"><strong>AQ13</strong> - Habitat Forming Species/Biogenic Habitat (HFS/BH) - Quantitative</h5>
                <p><strong>Purpose:</strong> Extent of habitat-forming features.</p>
                <p><strong>Returns NaN when:</strong> Qualitative data or no HFS/BH</p>
            </div>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #673ab7;">
                <h5 style="color: #673ab7; margin-top: 0;"><strong>AQ14</strong> - Symbiotic Species (SS) - Qualitative</h5>
                <p><strong>Purpose:</strong> Species in symbiotic relationships.</p>
                <p><strong>Examples:</strong> Mutualistic, commensalistic, or parasitic relationships</p>
                <p><strong>Returns NaN when:</strong> No features classified as SS</p>
            </div>

            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #673ab7;">
                <h5 style="color: #673ab7; margin-top: 0;"><strong>AQ15</strong> - Symbiotic Species (SS) - Quantitative</h5>
                <p><strong>Purpose:</strong> Abundance of symbiotic species.</p>
                <p><strong>Returns NaN when:</strong> Qualitative data or no SS</p>
            </div>

            <h4 style="color: #006994; margin-top: 2rem; margin-bottom: 1rem;">📊 EV (Ecological Value) Calculation</h4>

            <div style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); padding: 1.5rem; border-radius: 8px; border-left: 4px solid #2196F3;">
                <p style="font-size: 1.1rem; margin-bottom: 1rem;"><strong>EV = MAX of applicable AQs (not average or sum!)</strong></p>
                <p><strong>For Qualitative data:</strong></p>
                <p style="margin-left: 1.5rem;"><code>EV = MAX(AQ1, AQ3, AQ5, AQ7, AQ10, AQ12, AQ14)</code></p>
                <p style="margin-top: 1rem;"><strong>For Quantitative data:</strong></p>
                <p style="margin-left: 1.5rem;"><code>EV = MAX(AQ2, AQ4, AQ6, AQ8, AQ9, AQ11, AQ13, AQ15)</code></p>
                <p style="margin-top: 1rem; font-style: italic;">⚠️ <strong>Important:</strong> EV takes the MAXIMUM value to ensure that any significant ecological value is captured, even if only one criterion is met.</p>
            </div>
        </div>
        """

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
    
    # Handle file upload
    @reactive.Effect
    @reactive.event(input.upload_data)
    def handle_upload():
        file_info = input.upload_data()
        if file_info is not None and len(file_info) > 0:
            file_path = file_info[0]["datapath"]

            # Validate file size
            try:
                file_size_bytes = os.path.getsize(file_path)
                file_size_mb = file_size_bytes / (1024 * 1024)

                if file_size_mb > MAX_FILE_SIZE_MB:
                    # File is too large, reset uploaded_data and return
                    uploaded_data.set(None)
                    ui.notification_show(f"File too large ({file_size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB.", type="error", duration=8)
                    return
            except Exception as e:
                logger.error(f"Could not check file size: {e}")
                return

            # Read CSV and handle missing data
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                uploaded_data.set(None)
                ui.notification_show(f"Could not read CSV file: {e}", type="error", duration=8)
                return

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
            }
            validation_report.set(report)

            # Automatically detect data type
            auto_detected_type = detect_data_type(df)
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

    # Handle spatial file upload (GeoJSON, Shapefile ZIP, GeoPackage)
    @reactive.Effect
    @reactive.event(input.upload_geojson)
    def handle_geojson_upload():
        file_info = input.upload_geojson()
        if file_info is None or len(file_info) == 0:
            return

        file_path = file_info[0]["datapath"]
        file_name = file_info[0]["name"].lower()

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
                ui.notification_show(f"CRS reprojection failed: {e}. File used without reprojection.", type="warning", duration=8)
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

        # Keep only Subzone ID and geometry
        gdf = gdf[['Subzone ID', 'geometry']]
        geo_data.set(gdf)
        logger.info(f"GeoJSON loaded: {len(gdf)} features, CRS: {original_crs.get()}")

    # GeoJSON spatial preview
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

            # Show unmatched IDs if any
            if match_info.get('csv_only_ids') or match_info.get('geo_only_ids'):
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
                items.append(ui.div(
                    ui.tags.details(
                        ui.tags.summary("Show unmatched IDs"),
                        *unmatched_items
                    ),
                    style="margin-top: 0.5rem;"
                ))
        elif match_info:
            # No matched IDs — could be no CSV uploaded or truly zero matches
            if match_info.get('matched', 0) == 0 and (match_info.get('csv_only', 0) > 0 or match_info.get('geo_only', 0) > 0):
                match_style = "color: #d32f2f; font-weight: 600;"
                match_text = "🔴 No matching Subzone IDs found"
                items.append(ui.p(match_text, style=match_style))

                # Show unmatched IDs if any
                if match_info.get('csv_only_ids') or match_info.get('geo_only_ids'):
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
                    items.append(ui.div(
                        ui.tags.details(
                            ui.tags.summary("Show unmatched IDs"),
                            *unmatched_items
                        ),
                        style="margin-top: 0.5rem;"
                    ))
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

        badge_colors = {'RRF': '#e91e63', 'NRF': '#9c27b0', 'ESF': '#2196F3', 'HFS_BH': '#4caf50', 'SS': '#ff9800'}

        feature_rows = []
        for feature in feature_names:
            current = classifications.get(feature, [])
            badges = [ui.span(
                cls, class_="feature-badge",
                style=f"background: {badge_colors.get(cls, '#999')}; color: white;"
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
                                choices={"RRF": "RRF (Regionally Rare) \u2192 AQ5/AQ6", "NRF": "NRF (Nationally Rare) \u2192 AQ7/AQ8"},
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
            except Exception:
                rarity = []
            try:
                role = list(input[f"class_role_{feature}"]() or [])
            except Exception:
                role = []
            combined = rarity + role
            if combined:
                new_classifications[feature] = combined

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
            
            # Calculate X, Y, Z metrics for each feature
            summaries = []
            for col in feature_names:
                values = df[col].dropna()
                if not pd.api.types.is_numeric_dtype(values) or values.empty:
                    summaries.append({
                        "Feature Name": col, "X (Mean)": "N/A", "Y (95th Pct %)": "N/A", 
                        "Z (Occurrence)": "N/A", "Count": "N/A", "Average": "N/A"
                    })
                    continue

                mean_val = values.mean()
                
                # 95th percentile of positive values
                positive_values = values[values > 0]
                if not positive_values.empty:
                    percentile_95 = np.percentile(positive_values, 95)
                    sum_top_5_percent = values[values >= percentile_95].sum()
                    total_sum = values.sum()
                    y_metric = (sum_top_5_percent / total_sum * 100) if total_sum > 0 else 0
                else:
                    y_metric = 0

                z_metric = (values > 0).sum()
                
                summaries.append({
                    "Feature Name": col,
                    "X (Mean)": f"{mean_val:.2f}",
                    "Y (95th Pct %)": f"{y_metric:.2f}%",
                    "Z (Occurrence)": z_metric,
                    "Count": f"{values.sum():.2f}",
                    "Average": f"{mean_val:.2f}"
                })

            return pd.DataFrame(summaries)
        return pd.DataFrame()

    def rescale_qualitative(df):
        """
        Rescale qualitative (binary) data to 0-MAX_EV_SCALE scale
        For presence/absence data: presence (1) = MAX_EV_SCALE, absence (0) = 0
        Handles NaN by replacing with 0
        """
        feature_cols = [col for col in df.columns if col != 'Subzone ID']
        rescaled = df.copy()

        for col in feature_cols:
            # Fill any NaN with 0 first
            values = df[col].fillna(0)

            # Simple rescaling: 1 -> MAX_EV_SCALE, 0 -> 0
            rescaled[col] = values * MAX_EV_SCALE

            # Ensure no NaN in output
            rescaled[col] = rescaled[col].fillna(0)

        return rescaled

    def rescale_quantitative(df):
        """
        Rescale quantitative data to 0-MAX_EV_SCALE scale using min-max normalization
        Formula: MAX_EV_SCALE * (value - min) / (max - min)
        Handles NaN by replacing with 0
        """
        feature_cols = [col for col in df.columns if col != 'Subzone ID']
        rescaled = df.copy()

        for col in feature_cols:
            # Fill any NaN with 0 first
            values = df[col].fillna(0)

            # Calculate min and max (skipna=True by default, but we already filled NaN)
            min_val = values.min()
            max_val = values.max()

            # Check for division by zero and handle NaN
            if pd.isna(min_val) or pd.isna(max_val):
                # If still NaN, set to 0
                rescaled[col] = 0
            elif max_val > min_val:
                # Rescale to 0-MAX_EV_SCALE
                rescaled[col] = MAX_EV_SCALE * (values - min_val) / (max_val - min_val)

                # Ensure no NaN in output
                rescaled[col] = rescaled[col].fillna(0)
            else:
                # All values are the same
                rescaled[col] = 0

        return rescaled

    def classify_features(df, user_classifications, lrf_threshold=LOCALLY_RARE_THRESHOLD):
        """
        Classify features based on intrinsic properties (LRF, ROF) and user input.
        
        Args:
            df (pd.DataFrame): The input data.
            user_classifications (dict): A dictionary from the reactive value 
                                         holding user-defined classifications.
        """
        feature_cols = [col for col in df.columns if col != 'Subzone ID']
        classifications = {
            'LRF': {}, 'ROF': {}, 'RRF': {}, 'NRF': {}, 
            'ESF': {}, 'HFS_BH': {}, 'SS': {}
        }

        for col in feature_cols:
            # Intrinsic classification based on data
            positive_count = (df[col] > 0).sum()
            total_count = df[col].notna().sum()
            proportion = positive_count / total_count if total_count > 0 else 0

            is_lrf = 1 if proportion > 0 and proportion <= lrf_threshold else 0
            classifications['LRF'][col] = is_lrf
            classifications['ROF'][col] = 1 - is_lrf

            # User-defined classifications
            user_settings = user_classifications.get(col, [])
            classifications['RRF'][col] = 1 if "RRF" in user_settings else 0
            classifications['NRF'][col] = 1 if "NRF" in user_settings else 0
            classifications['ESF'][col] = 1 if "ESF" in user_settings else 0
            classifications['HFS_BH'][col] = 1 if "HFS_BH" in user_settings else 0
            classifications['SS'][col] = 1 if "SS" in user_settings else 0

        return classifications

    def calculate_aq9_special(df, classifications, percentile=PERCENTILE_95):
        """
        Calculate AQ9 special 3-step concentration-weighted values
        Step 1: Normalize by mean
        Step 2: Apply concentration ratio
        Step 3: Rescale to 0-MAX_EV_SCALE
        Handles NaN by replacing with 0
        """
        feature_cols = [col for col in df.columns if col != 'Subzone ID']
        aq9_rescaled = pd.DataFrame(index=df.index)
        aq9_rescaled['Subzone ID'] = df['Subzone ID']

        for col in feature_cols:
            if classifications['ROF'][col] == 1:
                # Step 1: Calculate concentration metrics
                # Fill NaN with 0 first
                values = df[col].fillna(0)
                mean_val = values.mean()

                if mean_val == 0 or pd.isna(mean_val):
                    aq9_rescaled[col] = 0
                    continue

                # Step 2: Normalize by mean (with safety check)
                try:
                    normalized = values / mean_val
                except (ZeroDivisionError, FloatingPointError):
                    aq9_rescaled[col] = 0
                    continue

                # Step 3: Calculate concentration weighting
                # Find 95th percentile
                positive_values = values[values > 0]
                if len(positive_values) > 0:
                    try:
                        percentile_val = np.percentile(positive_values, percentile)
                        sum_top_5_percent = values[values >= percentile_val].sum()
                        total_sum = values.sum()

                        # Y metric: percentage in top 5% (with division safety)
                        y_metric = (sum_top_5_percent / total_sum) if total_sum > 0 else 0

                        # Z metric: occurrence count
                        z_metric = (values > 0).sum()

                        # Concentration ratio (with division safety)
                        concentration_ratio = (y_metric / z_metric) if z_metric > 0 else 0

                        # Apply concentration weighting
                        weighted = normalized * concentration_ratio
                    except (ZeroDivisionError, FloatingPointError, ValueError):
                        weighted = normalized * 0
                else:
                    weighted = normalized * 0

                aq9_rescaled[col] = weighted
            else:
                aq9_rescaled[col] = 0

        # Step 4: Rescale all weighted values to 0-MAX_EV_SCALE range
        for col in feature_cols:
            if classifications['ROF'][col] == 1:
                max_weighted = aq9_rescaled[col].max()
                if max_weighted > 0 and not pd.isna(max_weighted):
                    try:
                        aq9_rescaled[col] = MAX_EV_SCALE * aq9_rescaled[col] / max_weighted
                    except (ZeroDivisionError, FloatingPointError):
                        aq9_rescaled[col] = 0
                else:
                    aq9_rescaled[col] = 0

        return aq9_rescaled

    def calculate_all_aqs(df, data_type, rescaled_qual, rescaled_quant, aq9_rescaled, classifications):
        """Calculate all 15 Assessment Questions (AQ1-AQ15) in a refactored way."""
        results = pd.DataFrame(index=df.index)
        results['Subzone ID'] = df['Subzone ID']
        feature_cols = [col for col in df.columns if col != 'Subzone ID']

        # Define AQ properties
        aq_map = {
            'AQ1': {'type': 'qualitative', 'features': 'LRF', 'df': rescaled_qual},
            'AQ2': {'type': 'quantitative', 'features': 'LRF', 'df': rescaled_quant},
            'AQ3': {'type': 'qualitative', 'features': 'RRF', 'df': rescaled_qual},
            'AQ4': {'type': 'quantitative', 'features': 'RRF', 'df': rescaled_quant},
            'AQ5': {'type': 'qualitative', 'features': 'NRF', 'df': rescaled_qual},
            'AQ6': {'type': 'quantitative', 'features': 'NRF', 'df': rescaled_quant},
            'AQ7': {'type': 'qualitative', 'features': 'ALL', 'df': rescaled_qual},
            'AQ8': {'type': 'quantitative', 'features': 'ROF', 'df': rescaled_quant},
            'AQ9': {'type': 'quantitative', 'features': 'ROF', 'df': aq9_rescaled},
            'AQ10': {'type': 'qualitative', 'features': 'ESF', 'df': rescaled_qual},
            'AQ11': {'type': 'quantitative', 'features': 'ESF', 'df': rescaled_quant},
            'AQ12': {'type': 'qualitative', 'features': 'HFS_BH', 'df': rescaled_qual},
            'AQ13': {'type': 'quantitative', 'features': 'HFS_BH', 'df': rescaled_quant},
            'AQ14': {'type': 'qualitative', 'features': 'SS', 'df': rescaled_qual},
            'AQ15': {'type': 'quantitative', 'features': 'SS', 'df': rescaled_quant},
        }

        for aq, props in aq_map.items():
            if data_type == props['type']:
                rescaled_df = props['df']
                feature_type = props['features']
                
                # Get the list of features that match the classification for this AQ
                if feature_type == 'ALL':
                    matching_features = feature_cols
                else:
                    matching_features = [
                        col for col in feature_cols 
                        if classifications[feature_type].get(col) == 1
                    ]

                if not matching_features:
                    results[aq] = np.nan
                    continue

                # Select only the data for the matching features
                try:
                    aq_data = rescaled_df[matching_features]

                    # Calculate the mean across the row for the selected features
                    # Replace any NaN values with 0 before calculating mean
                    aq_data_clean = aq_data.fillna(0)

                    # Calculate mean across columns (axis=1)
                    results[aq] = aq_data_clean.mean(axis=1)

                    # If all values in a row are 0, keep it as 0 (not NaN)
                    results[aq] = results[aq].fillna(0)
                except Exception as e:
                    logger.error(f"Error calculating {aq}: {e}")
                    results[aq] = 0
            else:
                results[aq] = np.nan

        return results

    def calculate_ev(aq_results, data_type):
        """Calculate EV as MAX of appropriate AQs based on data type"""
        ev_values = []

        for idx in aq_results.index:
            if data_type == "qualitative":
                # EV = MAX(AQ1, AQ3, AQ5, AQ7, AQ10, AQ12, AQ14)
                aq_cols = ['AQ1', 'AQ3', 'AQ5', 'AQ7', 'AQ10', 'AQ12', 'AQ14']
            elif data_type == "quantitative":
                # EV = MAX(AQ2, AQ4, AQ6, AQ8, AQ9, AQ11, AQ13, AQ15)
                aq_cols = ['AQ2', 'AQ4', 'AQ6', 'AQ8', 'AQ9', 'AQ11', 'AQ13', 'AQ15']
            else:
                ev_values.append(0)
                continue

            # Get values, treating NaN as 0
            values = []
            for col in aq_cols:
                val = aq_results.loc[idx, col]
                if pd.notna(val) and val != 0:
                    values.append(val)

            # Calculate max, defaulting to 0 if no valid values
            ev_values.append(np.max(values) if values else 0)

        return ev_values

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

        # Step 1: Rescale data
        rescaled_qual = rescale_qualitative(df)
        rescaled_quant = rescale_quantitative(df)

        # Step 2: Classify features using data and user input
        classifications = classify_features(df, user_classifications, lrf_threshold=lrf_threshold)

        # Step 3: Calculate AQ9 special rescaling
        aq9_rescaled = calculate_aq9_special(df, classifications, percentile=concentration_pct)

        # Step 4: Calculate all AQs
        aq_results = calculate_all_aqs(df, data_type, rescaled_qual, rescaled_quant, aq9_rescaled, classifications)

        # Step 5: Calculate EV
        aq_results['EV'] = calculate_ev(aq_results, data_type)

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
            results.rename(columns={'index': 'Subzone ID'}, inplace=True)

            # Fill any remaining NaN values in AQ columns with 0
            aq_cols = [col for col in results.columns if col.startswith('AQ') or col == 'EV']
            results[aq_cols] = results[aq_cols].fillna(0)

            return results
        except (KeyError, ValueError, IndexError) as e:
            # Log error and return None if concatenation fails
            logger.error(f"Error in DataFrame concatenation: {e}")
            logger.debug(f"df shape: {df.shape if df is not None else 'None'}")
            logger.debug(f"aq_results shape: {aq_results.shape if aq_results is not None else 'None'}")
            return None

    def get_aq_status(data_type, classifications, results):
        """Analyze each AQ and return status with explanation."""
        qual_aqs = ['AQ1', 'AQ3', 'AQ5', 'AQ7', 'AQ10', 'AQ12', 'AQ14']
        quant_aqs = ['AQ2', 'AQ4', 'AQ6', 'AQ8', 'AQ9', 'AQ11', 'AQ13', 'AQ15']

        has_rrf = any('RRF' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
        has_nrf = any('NRF' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
        has_esf = any('ESF' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
        has_hfs = any('HFS_BH' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
        has_ss = any('SS' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())

        statuses = {}
        for aq in qual_aqs + quant_aqs:
            aq_num = int(aq[2:])

            if data_type == 'qualitative' and aq in quant_aqs:
                statuses[aq] = ('inactive', 'Quantitative data required')
            elif data_type == 'quantitative' and aq in qual_aqs:
                statuses[aq] = ('inactive', 'Qualitative data required')
            elif aq_num in [5, 6] and not has_rrf:
                statuses[aq] = ('inactive', 'No features classified as RRF')
            elif aq_num in [7, 8] and not has_nrf:
                statuses[aq] = ('inactive', 'No features classified as NRF')
            elif aq_num in [10, 11] and not has_esf:
                statuses[aq] = ('inactive', 'No features classified as ESF')
            elif aq_num in [12, 13] and not has_hfs:
                statuses[aq] = ('inactive', 'No features classified as HFS/BH')
            elif aq_num in [14, 15] and not has_ss:
                statuses[aq] = ('inactive', 'No features classified as SS')
            else:
                statuses[aq] = ('active', 'Active')

        return statuses

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
            aq_statuses = get_aq_status(data_type, user_classifications, results)

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

    # Define tooltips for each AQ
    def get_aq_tooltip(aq_name):
        tooltips = {
            "AQ1": "Locally Rare Features (LRF) - Qualitative | Average of rescaled values for features in ≤5% of subzones | Returns NaN when no features are locally rare",
            "AQ2": "Locally Rare Features (LRF) - Quantitative | Average abundance of locally rare features | Returns NaN for qualitative data or when no LRF exist",
            "AQ3": "Regionally Rare Features (RRF) - Qualitative | Average of rescaled values for RRF-classified features | Returns NaN when no RRF features defined",
            "AQ4": "Regionally Rare Features (RRF) - Quantitative | Average abundance of regionally rare features | Returns NaN for qualitative data or no RRF",
            "AQ5": "Nationally Rare Features (NRF) - Qualitative | Average of rescaled values for NRF features | Highest rarity classification",
            "AQ6": "Nationally Rare Features (NRF) - Quantitative | Average abundance of nationally rare features | Returns NaN for qualitative data or no NRF",
            "AQ7": "All Features - Qualitative ⭐ | Average of ALL features (no filter) | ALWAYS ACTIVE for qualitative data",
            "AQ8": "Regularly Occurring Features (ROF) - Quantitative | Average abundance of features in >5% of subzones | Returns NaN for qualitative data",
            "AQ9": "ROF Concentration-Weighted - Quantitative 🔬 | Complex 3-step calculation considering spatial concentration | Identifies hotspots",
            "AQ10": "Ecologically Significant Features (ESF) - Qualitative | Keystone species, ecosystem engineers | Returns NaN when no ESF defined",
            "AQ11": "Ecologically Significant Features (ESF) - Quantitative | Abundance of ecologically significant features | Returns NaN for qualitative or no ESF",
            "AQ12": "Habitat Forming Species/Biogenic Habitat (HFS/BH) - Qualitative | Features creating habitat structure (corals, seagrasses, etc.) | Returns NaN when no HFS/BH defined",
            "AQ13": "Habitat Forming Species/Biogenic Habitat (HFS/BH) - Quantitative | Extent of habitat-forming features | Returns NaN for qualitative or no HFS/BH",
            "AQ14": "Symbiotic Species (SS) - Qualitative | Species in symbiotic relationships | Returns NaN when no SS defined",
            "AQ15": "Symbiotic Species (SS) - Quantitative | Abundance of symbiotic species | Returns NaN for qualitative or no SS",
            "EV": "Ecological Value | MAX of applicable AQs (not average!) | Qualitative: MAX(AQ1,3,5,7,10,12,14) | Quantitative: MAX(AQ2,4,6,8,9,11,13,15)"
        }
        return tooltips.get(aq_name, "")

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

        # Do NOT replace NaN values; keep them as NaN so we can display NA/empty in the table
        # display_df = display_df.fillna(0)

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
            tooltip = get_aq_tooltip(col)
            if tooltip:
                # Use Bootstrap tooltip with data-bs attributes
                escaped_tooltip = tooltip.replace('"', '&quot;')
                html += f'<th class="has-tooltip" data-bs-toggle="tooltip" data-bs-placement="top" data-bs-html="true" title="{escaped_tooltip}">{col}</th>'
            else:
                html += f'<th>{col}</th>'

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
                    html += f'<td>{value}</td>'
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
            ev_frames = {}
            for ec_name, ec in store.items():
                if ec['results'] is not None:
                    ev_frames[ec_name] = ec['results'][['Subzone ID', 'EV']].rename(columns={'EV': ec_name})

            if not ev_frames:
                return ui.p("No ECs have computed results. Configure and save ECs first.")

            # Merge all EV columns on Subzone ID
            merged = None
            for ec_name, df in ev_frames.items():
                if merged is None:
                    merged = df
                else:
                    merged = merged.merge(df, on='Subzone ID', how='outer')

            # Fill NaN with 0 and compute Total EV
            ec_names = list(ev_frames.keys())
            merged[ec_names] = merged[ec_names].fillna(0)
            merged['Total EV'] = merged[ec_names].sum(axis=1)

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
            ev_frames = {}
            for ec_name, ec in store.items():
                if ec['results'] is not None:
                    ev_frames[ec_name] = ec['results'][['Subzone ID', 'EV']].rename(columns={'EV': ec_name})

            if not ev_frames:
                return pd.DataFrame()

            merged = None
            for ec_name, df in ev_frames.items():
                if merged is None:
                    merged = df
                else:
                    merged = merged.merge(df, on='Subzone ID', how='outer')

            ec_names = list(ev_frames.keys())
            merged[ec_names] = merged[ec_names].fillna(0)
            merged['Total EV'] = merged[ec_names].sum(axis=1)
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
        """Export comprehensive analysis results to Excel with multiple annotated sheets"""
        results = calculate_results()
        df = uploaded_data.get()
        data_type = input.data_type()
        user_classifications = feature_classifications.get()

        if results is None or df is None:
            # Return empty workbook if no data
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                pd.DataFrame({"Message": ["No data available"]}).to_excel(writer, sheet_name='Info', index=False)
            buffer.seek(0)
            return buffer

        # Create Excel writer
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:

            # Sheet 1: Summary & Metadata
            summary_data = {
                'Parameter': [
                    'Analysis Date',
                    'Analysis Time',
                    'Application Version',
                    'EC Name',
                    'Study Area',
                    'Data Type',
                    'Data Description',
                    '',
                    'Dataset Statistics',
                    'Number of Subzones',
                    'Number of Features',
                    'Total EV (Sum)',
                    'Average EV',
                    'Maximum EV',
                    'Minimum EV',
                    '',
                    'Reference',
                    'Funding',
                ],
                'Value': [
                    pd.Timestamp.now().strftime('%Y-%m-%d'),
                    pd.Timestamp.now().strftime('%H:%M:%S'),
                    '2.1.2',
                    input.ec_name() if input.ec_name() else 'Not specified',
                    input.study_area() if input.study_area() else 'Not specified',
                    data_type if data_type else 'Not specified',
                    input.data_description() if input.data_description() else 'Not specified',
                    '',
                    '',
                    len(results),
                    len([col for col in df.columns if col != 'Subzone ID']),
                    f"{results['EV'].sum():.4f}",
                    f"{results['EV'].mean():.4f}",
                    f"{results['EV'].max():.4f}",
                    f"{results['EV'].min():.4f}",
                    '',
                    'Franco A. and Amorim E. (2025) Ecological Value Assessment (EVA)',
                    'European Union Horizon Europe Research Programme - MARBEFES Project',
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary & Metadata', index=False)

            # Sheet 2: Original Data (with NaN replaced by 0)
            df_export = df.copy()
            feature_cols_export = [col for col in df_export.columns if col != 'Subzone ID']
            df_export[feature_cols_export] = df_export[feature_cols_export].fillna(0)
            df_export.to_excel(writer, sheet_name='Original Data', index=False)

            # Sheet 3: Assessment Questions Results (with NaN replaced by 0)
            aq_cols = ['Subzone ID'] + [col for col in results.columns if col.startswith('AQ')] + ['EV']
            results_export = results[aq_cols].copy()
            results_export = results_export.fillna(0)
            results_export.to_excel(writer, sheet_name='AQ & EV Results', index=False)

            # Sheet 4: Feature Classifications
            if user_classifications:
                feature_cols = [col for col in df.columns if col != 'Subzone ID']
                classifications_data = []
                for feature in feature_cols:
                    user_class = user_classifications.get(feature, [])
                    classifications_data.append({
                        'Feature Name': feature,
                        'RRF (Regionally Rare)': 'Yes' if 'RRF' in user_class else 'No',
                        'NRF (Nationally Rare)': 'Yes' if 'NRF' in user_class else 'No',
                        'ESF (Ecologically Significant)': 'Yes' if 'ESF' in user_class else 'No',
                        'HFS/BH (Habitat Forming)': 'Yes' if 'HFS_BH' in user_class else 'No',
                        'SS (Symbiotic Species)': 'Yes' if 'SS' in user_class else 'No'
                    })
                classifications_df = pd.DataFrame(classifications_data)
                classifications_df.to_excel(writer, sheet_name='Feature Classifications', index=False)

            # Sheet 5: AQ Methodology Reference
            methodology_data = {
                'AQ': ['AQ1', 'AQ2', 'AQ3', 'AQ4', 'AQ5', 'AQ6', 'AQ7', 'AQ8', 'AQ9', 'AQ10', 'AQ11', 'AQ12', 'AQ13', 'AQ14', 'AQ15'],
                'Name': [
                    'Locally Rare Features (LRF) - Qualitative',
                    'Locally Rare Features (LRF) - Quantitative',
                    'Regionally Rare Features (RRF) - Qualitative',
                    'Regionally Rare Features (RRF) - Quantitative',
                    'Nationally Rare Features (NRF) - Qualitative',
                    'Nationally Rare Features (NRF) - Quantitative',
                    'All Features - Qualitative',
                    'Regularly Occurring Features (ROF) - Quantitative',
                    'ROF Concentration-Weighted - Quantitative',
                    'Ecologically Significant Features (ESF) - Qualitative',
                    'Ecologically Significant Features (ESF) - Quantitative',
                    'Habitat Forming Species/Biogenic Habitat - Qualitative',
                    'Habitat Forming Species/Biogenic Habitat - Quantitative',
                    'Symbiotic Species (SS) - Qualitative',
                    'Symbiotic Species (SS) - Quantitative'
                ],
                'Description': [
                    'Features present in ≤5% of subzones',
                    'Abundance of features in ≤5% of subzones',
                    'User-defined regionally rare features',
                    'Abundance of regionally rare features',
                    'User-defined nationally rare features',
                    'Abundance of nationally rare features',
                    'All features without filter (baseline assessment)',
                    'Features present in >5% of subzones',
                    'Spatially concentrated regularly occurring features',
                    'Keystone species and ecosystem engineers',
                    'Abundance of ecologically significant features',
                    'Corals, seagrasses, habitat-creating species',
                    'Extent of habitat-forming features',
                    'Species in symbiotic relationships',
                    'Abundance of symbiotic species'
                ],
                'Data Type': [
                    'Qualitative', 'Quantitative', 'Qualitative', 'Quantitative',
                    'Qualitative', 'Quantitative', 'Qualitative', 'Quantitative',
                    'Quantitative', 'Qualitative', 'Quantitative', 'Qualitative',
                    'Quantitative', 'Qualitative', 'Quantitative'
                ],
                'Returns NaN when': [
                    'No locally rare features',
                    'Qualitative data or no LRF',
                    'No RRF defined',
                    'Qualitative data or no RRF',
                    'No NRF defined',
                    'Qualitative data or no NRF',
                    'Never (always active for qualitative)',
                    'Qualitative data',
                    'Qualitative data',
                    'No ESF defined',
                    'Qualitative data or no ESF',
                    'No HFS/BH defined',
                    'Qualitative data or no HFS/BH',
                    'No SS defined',
                    'Qualitative data or no SS'
                ]
            }
            methodology_df = pd.DataFrame(methodology_data)
            methodology_df.to_excel(writer, sheet_name='AQ Methodology', index=False)

            # Sheet 6: EV Calculation Explanation
            ev_explanation = {
                'Concept': [
                    'EV Calculation Method',
                    'For Qualitative Data',
                    'For Quantitative Data',
                    '',
                    'Scale',
                    'Interpretation',
                    '',
                    'Important Notes',
                ],
                'Explanation': [
                    'EV = MAXIMUM of applicable AQ scores (not average or sum)',
                    'EV = MAX(AQ1, AQ3, AQ5, AQ7, AQ10, AQ12, AQ14)',
                    'EV = MAX(AQ2, AQ4, AQ6, AQ8, AQ9, AQ11, AQ13, AQ15)',
                    '',
                    'All values range from 0 to 5',
                    'Higher values indicate greater ecological importance',
                    '',
                    'EV uses MAX to ensure any significant ecological value is captured, even if only one criterion is met',
                ]
            }
            ev_df = pd.DataFrame(ev_explanation)
            ev_df.to_excel(writer, sheet_name='EV Calculation', index=False)

            # Sheet 7: Complete Results (All Data with NaN replaced by 0)
            results_complete = results.copy()
            results_complete = results_complete.fillna(0)
            results_complete.to_excel(writer, sheet_name='Complete Results', index=False)

            # Format worksheets
            workbook = writer.book

            # Format Summary sheet
            summary_sheet = workbook['Summary & Metadata']
            summary_sheet.column_dimensions['A'].width = 30
            summary_sheet.column_dimensions['B'].width = 60

            # Format methodology sheet
            methodology_sheet = workbook['AQ Methodology']
            methodology_sheet.column_dimensions['A'].width = 8
            methodology_sheet.column_dimensions['B'].width = 45
            methodology_sheet.column_dimensions['C'].width = 50
            methodology_sheet.column_dimensions['D'].width = 15
            methodology_sheet.column_dimensions['E'].width = 40

        buffer.seek(0)
        return buffer
    
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
        store[ec_name] = {
            'data': df.copy(),
            'data_type': input.data_type(),
            'classifications': feature_classifications.get().copy(),
            'results': results.copy() if results is not None else None,
            'feature_count': len([c for c in df.columns if c != 'Subzone ID']),
        }
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
    @reactive.event(ec_store)
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
                    "⚠️ No data to visualize. Please upload data in the Data Input tab first.",
                    style="font-size: 1.1rem; text-align: center; color: #6c757d; padding: 2rem;"
                )
            )
        
        plot_type = input.plot_type()
        
        if plot_type == "EV by Subzone":
            # Create EV bar chart
            fig = go.Figure(data=[
                go.Bar(
                    x=results['Subzone ID'],
                    y=results['EV'],
                    marker=dict(
                        color=results['EV'],
                        colorscale='Viridis',
                        showscale=True,
                        colorbar=dict(title="EV")
                    ),
                    text=results['EV'].round(2),
                    textposition='outside'
                )
            ])
            
            fig.update_layout(
                title="Ecological Value by Subzone",
                xaxis_title="Subzone ID",
                yaxis_title="Ecological Value (EV)",
                height=500,
                hovermode='x unified',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            
            return ui.HTML(fig.to_html(include_plotlyjs="cdn", div_id="ev_plot"))
            
        elif plot_type == "Feature Distribution":
            # Create feature heatmap
            df = uploaded_data.get()
            if df is not None and 'Subzone ID' in df.columns:
                # Get feature columns (exclude Subzone ID)
                feature_cols = [col for col in df.columns if col != 'Subzone ID']
                
                # Create heatmap data
                heatmap_data = df[feature_cols].values
                
                fig = go.Figure(data=go.Heatmap(
                    z=heatmap_data,
                    x=feature_cols,
                    y=df['Subzone ID'],
                    colorscale='Blues',
                    hoverongaps=False,
                    colorbar=dict(title="Presence")
                ))
                
                fig.update_layout(
                    title="Feature Distribution Across Subzones",
                    xaxis_title="Features",
                    yaxis_title="Subzone ID",
                    height=max(400, len(df) * 20),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                
                return ui.HTML(fig.to_html(include_plotlyjs="cdn", div_id="feature_plot"))
            
            return ui.p("Unable to generate feature distribution chart")

        elif plot_type == "AQ Breakdown by Subzone":
            # Grouped bar chart showing active AQ scores per subzone with EV line
            aq_columns = [col for col in results.columns if col.startswith('AQ')]
            if not aq_columns:
                return ui.p("No AQ scores available")

            # Filter to active AQs (those with at least one non-zero value)
            active_aqs = [col for col in aq_columns if results[col].abs().sum() > 0]
            if not active_aqs:
                return ui.p("No active AQ scores to display. All AQ values are zero.")

            fig = go.Figure()

            # Add bars for each active AQ
            colors = px.colors.qualitative.Plotly
            for i, aq in enumerate(active_aqs):
                fig.add_trace(go.Bar(
                    name=aq,
                    x=results['Subzone ID'],
                    y=results[aq],
                    marker_color=colors[i % len(colors)],
                    hovertemplate=f'{aq}: %{{y:.2f}}<extra></extra>'
                ))

            # Add EV line overlay
            fig.add_trace(go.Scatter(
                name='EV',
                x=results['Subzone ID'],
                y=results['EV'],
                mode='lines+markers',
                line=dict(color='black', width=2, dash='dot'),
                marker=dict(size=6, color='black'),
                hovertemplate='EV: %{y:.2f}<extra></extra>'
            ))

            fig.update_layout(
                title="AQ Score Breakdown by Subzone",
                xaxis_title="Subzone ID",
                yaxis_title="Score (0-5)",
                yaxis=dict(range=[0, 5.5]),
                barmode='group',
                height=550,
                hovermode='x unified',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )

            return ui.HTML(fig.to_html(include_plotlyjs="cdn", div_id="aq_breakdown_plot"))

        elif plot_type == "AQ Radar Comparison":
            # Radar chart comparing AQ profiles across selected subzones
            selected = list(input.radar_subzones()) if input.radar_subzones() else []
            if not selected:
                return ui.div(
                    ui.p("👈 Select 1-5 subzones from the sidebar to compare their AQ profiles.",
                         style="font-size: 1.1rem; text-align: center; color: #6c757d; padding: 2rem;")
                )

            aq_columns = [col for col in results.columns if col.startswith('AQ')]
            if not aq_columns:
                return ui.p("No AQ scores available")

            fig = go.Figure()

            line_colors = px.colors.qualitative.Plotly
            fill_colors = [
                'rgba(99,110,250,0.15)', 'rgba(239,85,59,0.15)', 'rgba(0,204,150,0.15)',
                'rgba(171,99,250,0.15)', 'rgba(255,161,90,0.15)'
            ]

            for i, subzone in enumerate(selected):
                row = results[results['Subzone ID'] == subzone]
                if row.empty:
                    continue
                values = row[aq_columns].values.flatten().tolist()
                values.append(values[0])  # Close the polygon
                categories = aq_columns + [aq_columns[0]]

                fig.add_trace(go.Scatterpolar(
                    r=values,
                    theta=categories,
                    fill='toself',
                    fillcolor=fill_colors[i % len(fill_colors)],
                    name=str(subzone),
                    line=dict(color=line_colors[i % len(line_colors)], width=2),
                    hovertemplate='%{theta}: %{r:.2f}<extra>' + str(subzone) + '</extra>'
                ))

            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 5]),
                    angularaxis=dict(direction="clockwise")
                ),
                title="AQ Profile Comparison by Subzone",
                height=600,
                showlegend=True,
                legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
                paper_bgcolor='rgba(0,0,0,0)'
            )

            return ui.HTML(fig.to_html(include_plotlyjs="cdn", div_id="radar_plot"))

        elif plot_type == "AQ Heatmap":
            # Heatmap of AQ scores across subzones, sorted by EV descending
            aq_columns = [col for col in results.columns if col.startswith('AQ')]
            if not aq_columns:
                return ui.p("No AQ scores available")

            display_cols = aq_columns + ['EV']
            sorted_results = results.sort_values('EV', ascending=True)

            z_data = sorted_results[display_cols].values
            x_labels = display_cols
            y_labels = sorted_results['Subzone ID'].tolist()

            color_scheme = input.color_scheme()

            fig = go.Figure(data=go.Heatmap(
                z=z_data,
                x=x_labels,
                y=y_labels,
                colorscale=color_scheme,
                zmin=0,
                zmax=5,
                text=np.round(z_data, 1),
                texttemplate="%{text}",
                textfont={"size": 10},
                hoverongaps=False,
                colorbar=dict(title="Score")
            ))

            fig.update_layout(
                title="AQ Scores × Subzones (sorted by EV)",
                xaxis_title="Assessment Questions",
                yaxis_title="Subzone ID",
                height=max(450, len(sorted_results) * 25),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )

            return ui.HTML(fig.to_html(include_plotlyjs="cdn", div_id="aq_heatmap_plot"))

        else:  # AQ Scores
            # Create AQ scores histogram
            aq_columns = [col for col in results.columns if col.startswith('AQ')]
            
            if aq_columns:
                # Melt the dataframe to get all AQ scores in one column
                aq_data = results[aq_columns].values.flatten()
                
                fig = go.Figure(data=[
                    go.Histogram(
                        x=aq_data,
                        nbinsx=30,
                        marker=dict(
                            color='rgba(255, 152, 0, 0.7)',
                            line=dict(color='rgba(255, 152, 0, 1)', width=1)
                        )
                    )
                ])
                
                fig.update_layout(
                    title="Distribution of Assessment Question Scores",
                    xaxis_title="AQ Score",
                    yaxis_title="Frequency",
                    height=400,
                    showlegend=False,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                
                return ui.HTML(fig.to_html(include_plotlyjs="cdn", div_id="aq_plot"))
            
            return ui.p("No AQ scores available")

    # === GIS MAP FUNCTIONS ===

    def auto_zoom_level(bounds):
        """Calculate appropriate zoom level from bounding box [minx, miny, maxx, maxy]."""
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

    def create_ev_map(map_gdf, variable, color_scheme_name, classification, basemap_name, opacity):
        """Create a folium choropleth map from a GeoDataFrame with EVA results."""
        bounds = map_gdf.total_bounds
        center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
        zoom = auto_zoom_level(bounds)

        tiles = BASEMAP_TILES.get(basemap_name, "cartodbpositron")
        m = folium.Map(location=center, zoom_start=zoom, tiles=tiles)

        # Prepare variable data
        map_gdf = map_gdf.copy()
        if variable in map_gdf.columns:
            map_gdf[variable] = pd.to_numeric(map_gdf[variable], errors='coerce').fillna(0)
        else:
            map_gdf[variable] = 0

        vmin = float(map_gdf[variable].min())
        vmax = float(map_gdf[variable].max())
        if vmax == vmin:
            vmax = vmin + 1

        use_5class = classification.startswith("EVA")

        if use_5class:
            def style_fn(feature):
                val = feature['properties'].get(variable, 0)
                if val is None:
                    val = 0
                color = EVA_5CLASS_COLORS[-1]
                for i in range(len(EVA_5CLASS_BINS) - 1):
                    if val <= EVA_5CLASS_BINS[i + 1]:
                        color = EVA_5CLASS_COLORS[i]
                        break
                return {
                    'fillColor': color,
                    'color': '#333333',
                    'weight': 0.5,
                    'fillOpacity': opacity
                }
        else:
            color_schemes = {
                "YlOrRd": cm.linear.YlOrRd_09,
                "Viridis": cm.linear.viridis,
                "Blues": cm.linear.Blues_09,
                "RdYlGn": cm.linear.RdYlGn_11,
                "Plasma": cm.linear.plasma,
            }
            colormap = color_schemes.get(color_scheme_name, cm.linear.YlOrRd_09)
            colormap = colormap.scale(vmin, vmax)
            colormap.caption = variable

            def style_fn(feature):
                val = feature['properties'].get(variable, 0)
                if val is None:
                    val = 0
                return {
                    'fillColor': colormap(val),
                    'color': '#333333',
                    'weight': 0.5,
                    'fillOpacity': opacity
                }

        # Build tooltip fields
        tooltip_fields = ['Subzone ID', variable]
        tooltip_aliases = ['Subzone:', f'{variable}:']
        if variable != 'EV' and 'EV' in map_gdf.columns:
            tooltip_fields.append('EV')
            tooltip_aliases.append('EV:')

        # Round numeric columns for tooltips
        for col in tooltip_fields:
            if col in map_gdf.columns and col != 'Subzone ID':
                map_gdf[col] = map_gdf[col].round(3)

        folium.GeoJson(
            map_gdf.to_json(),
            style_function=style_fn,
            tooltip=folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=tooltip_aliases,
                sticky=True,
                style="font-size: 13px; padding: 8px;"
            )
        ).add_to(m)

        # Add legend
        if use_5class:
            legend_html = '<div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000; background: white; padding: 12px 16px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.3); font-size: 13px;">'
            legend_html += f'<p style="margin: 0 0 8px; font-weight: 700;">{variable}</p>'
            for i in range(len(EVA_5CLASS_COLORS)):
                legend_html += f'<p style="margin: 2px 0;"><span style="background:{EVA_5CLASS_COLORS[i]}; width:18px; height:14px; display:inline-block; margin-right:6px; border-radius:2px;"></span>{EVA_5CLASS_LABELS[i]}</p>'
            legend_html += '</div>'
            m.get_root().html.add_child(folium.Element(legend_html))
        else:
            colormap.add_to(m)

        folium.plugins.Fullscreen(position='topright').add_to(m)
        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

        return m._repr_html_()

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

        if results is None:
            return ui.div(
                ui.p(
                    "⚠️ Calculate EVA results first (upload CSV and select data type) to see values on the map.",
                    style="text-align: center; color: #ff9800; font-size: 1.1rem; padding: 3rem;"
                )
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

            map_html = create_ev_map(merged, variable, color_scheme, classification, basemap, opacity)

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


# Create the app with static file serving
app = App(app_ui, server, static_assets=Path(__file__).parent / "www")
