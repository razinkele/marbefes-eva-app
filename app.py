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
                        choices=["EV by Subzone", "Feature Distribution", "AQ Scores"]
                    ),
                    ui.input_select(
                        "color_scheme",
                        "Color Scheme:",
                        choices=["Viridis", "Plasma", "Blues", "Greens"]
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
                    logger.error(f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({MAX_FILE_SIZE_MB} MB)")
                    return
            except Exception as e:
                logger.error(f"Could not check file size: {e}")
                return

            # Read CSV and handle missing data
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                uploaded_data.set(None)
                logger.error(f"Could not read CSV file: {e}")
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
            df = df.drop_duplicates(subset=['Subzone ID'])

            # 3. Convert feature columns to numeric, but preserve NaN
            feature_cols = [col for col in df.columns if col != 'Subzone ID']
            for col in feature_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 4. Sort by Subzone ID for consistent ordering
            df = df.sort_values('Subzone ID').reset_index(drop=True)

            uploaded_data.set(df)

            # Automatically detect data type
            auto_detected_type = detect_data_type(df)
            detected_data_type.set(auto_detected_type)

            # Update the input selector to the detected type
            ui.update_select("data_type", selected=auto_detected_type)

    # Handle GeoJSON upload
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

        match_html = ""
        if match_info and match_info.get('matched', 0) > 0:
            extra = ""
            if match_info.get('csv_only', 0) > 0 or match_info.get('geo_only', 0) > 0:
                extra = f'<p style="margin: 0.25rem 0 0; color: #ff9800; font-size: 0.9rem;">⚠️ {match_info["csv_only"]} CSV-only, {match_info["geo_only"]} GeoJSON-only</p>'
            match_html = f'''
                <div style="margin-top: 1rem; padding: 1rem; background: #e8f5e9; border-radius: 8px; border-left: 4px solid #28a745;">
                    <p style="margin: 0; color: #28a745; font-weight: 600;">
                        ✅ {match_info['matched']} subzones matched between CSV and GeoJSON
                    </p>
                    {extra}
                </div>
            '''
        elif match_info:
            match_html = '''
                <div style="margin-top: 1rem; padding: 1rem; background: #fff3e0; border-radius: 8px; border-left: 4px solid #ff9800;">
                    <p style="margin: 0; color: #ff9800; font-weight: 600;">
                        ⚠️ Upload CSV data to see match status
                    </p>
                </div>
            '''

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
                        "🔄 Displayed in WGS84 (EPSG:4326)",
                        style="color: #6c757d; line-height: 2;"
                    ),
                    ui.HTML(match_html),
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
        
        feature_rows = []
        for feature in feature_names:
            feature_rows.append(
                ui.row(
                    ui.column(4, ui.p(ui.strong(feature))),
                    ui.column(8, ui.input_checkbox_group(
                        f"class_{feature}",
                        "",
                        choices={
                            "RRF": "RRF (Regionally Rare)",
                            "NRF": "NRF (Nationally Rare)",
                            "ESF": "ESF (Ecologically Significant)",
                            "HFS_BH": "HFS/BH (Habitat Forming)",
                            "SS": "SS (Symbiotic Species)"
                        },
                        inline=True
                    ))
                )
            )

        return ui.TagList(
            ui.p(f"Detected {len(feature_names)} features. Please classify them below:"),
            ui.div(
                ui.row(
                    ui.column(4, ui.h5("Feature Name")),
                    ui.column(8, ui.h5("Classifications"))
                ),
                *feature_rows,
                style="margin-top: 1.5rem;"
            )
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

        current_classifications = {}
        for feature in feature_names:
            # The input ID is constructed as f"class_{feature}"
            try:
                class_input = getattr(input, f"class_{feature}", None)
                if class_input is not None:
                    # Get the selected classifications for the current feature
                    current_classifications[feature] = class_input()
                else:
                    current_classifications[feature] = []
            except AttributeError:
                # If input doesn't exist yet, use empty list
                current_classifications[feature] = []

        # Update the central reactive value
        feature_classifications.set(current_classifications)
    
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

    def classify_features(df, user_classifications):
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

            is_lrf = 1 if proportion > 0 and proportion <= LOCALLY_RARE_THRESHOLD else 0
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

    def calculate_aq9_special(df, classifications):
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
                        percentile_95 = np.percentile(positive_values, PERCENTILE_95)
                        sum_top_5_percent = values[values >= percentile_95].sum()
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

        # Step 1: Rescale data
        rescaled_qual = rescale_qualitative(df)
        rescaled_quant = rescale_quantitative(df)

        # Step 2: Classify features using data and user input
        classifications = classify_features(df, user_classifications)

        # Step 3: Calculate AQ9 special rescaling
        aq9_rescaled = calculate_aq9_special(df, classifications)

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
            # Analyze which AQs have values
            aq_cols = [col for col in results.columns if col.startswith('AQ')]
            non_nan_aqs = [col for col in aq_cols if not results[col].isna().all()]
            all_nan_aqs = [col for col in aq_cols if results[col].isna().all()]

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
                        ui.p(
                            f"✅ Active AQs ({len(non_nan_aqs)}): {', '.join(non_nan_aqs) if non_nan_aqs else 'None'}",
                            style="color: #28a745; margin: 0.5rem 0;"
                        ),
                        ui.p(
                            f"⚠️ Inactive AQs ({len(all_nan_aqs)}): {', '.join(all_nan_aqs) if all_nan_aqs else 'None'}",
                            style="color: #ff9800; margin: 0.5rem 0;"
                        ),
                        style="padding: 1rem; background: linear-gradient(135deg, #e3f2fd 0%, #f1f8e9 100%); border-radius: 8px; margin-bottom: 1.5rem;"
                    )
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
        display_df = results[display_cols].head(RESULTS_DISPLAY_LIMIT).copy()

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

        # Add data rows
        for idx, row in display_df.iterrows():
            html += "<tr>"
            for col in display_cols:
                value = row[col]
                if pd.isna(value):
                    # Display NA for missing values
                    html += '<td style="color: #999; font-style: italic; text-align: center;">NA</td>'
                elif isinstance(value, (int, float)):
                    # Format numbers nicely
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
                        ui.value_box(
                            "Total EV",
                            f"{total_ev:.2f}",
                            theme="primary"
                        ),
                        ui.value_box(
                            "Average EV",
                            f"{avg_ev:.2f}",
                            theme="info"
                        ),
                        ui.value_box(
                            "Max EV",
                            f"{max_ev:.2f}",
                            theme="success"
                        ),
                        ui.value_box(
                            "Min EV",
                            f"{min_ev:.2f}",
                            theme="warning"
                        ),
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
        results = calculate_results()
        if results is not None:
            return results[['Subzone ID', 'EV']].head(RESULTS_DISPLAY_LIMIT)
        return pd.DataFrame()
    
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


# Create the app with static file serving
app = App(app_ui, server, static_assets=Path(__file__).parent / "www")
