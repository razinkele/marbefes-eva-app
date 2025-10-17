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
import plotly.graph_objects as go
import plotly.express as px

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
                                    ui.strong("📚 Learn the Terminology: "),
                                    "Visit the Acronyms tab"
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
        "📚 Acronyms",
        ui.div(
            ui.div(
                ui.h2("📚 Acronyms and Definitions", style="color: #006994; font-weight: 700; margin-bottom: 1.5rem;"),
                ui.p(
                    "Understanding the terminology used in the Ecological Value Assessment framework.",
                    style="font-size: 1.1rem; color: #6c757d; margin-bottom: 2rem;"
                )
            ),
            ui.card(
                ui.card_header("🔤 EVA Terminology Reference"),
                ui.div(
                    ui.output_table("acronyms_table"),
                    style="padding: 1rem;"
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
                ui.output_ui("data_preview_ui")
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
                        max=100
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
                            "This section displays Assessment Question (AQ) scores and Ecological Value (EV) for each subzone.",
                            style="font-size: 1.05rem; line-height: 1.8;"
                        ),
                        ui.div(
                            ui.h5("📋 Assessment Questions", style="color: #28a745; font-weight: 600; margin-top: 1.5rem;"),
                            ui.tags.ul(
                                ui.tags.li("AQ1: Locally rare features (LRF)"),
                                ui.tags.li("AQ2: Regionally rare features (RRF)"),
                                ui.tags.li("AQ3: Nationally rare features (NRF)"),
                                ui.tags.li("AQ4: Regularly occurring features (ROF)"),
                                ui.tags.li("AQ5: Ecologically significant features (ESF)"),
                                ui.tags.li("AQ6: Habitat forming species (HFS)"),
                                ui.tags.li("AQ7: Biogenic habitat (BH)"),
                                ui.tags.li("AQ8: Symbiotic species (SS)"),
                                ui.tags.li("AQ9: Combined score"),
                                style="line-height: 2; column-count: 2; column-gap: 2rem;"
                            ),
                            class_="info-box"
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
                    ui.download_button(
                        "download_results", 
                        "⬇️ Download All Results",
                        class_="btn-primary",
                        style="font-size: 1.1rem; padding: 0.8rem 2rem;"
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
    features_data = reactive.Value(None)
    results_data = reactive.Value(None)
    
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
            df = pd.read_csv(file_path)
            uploaded_data.set(df)
    
    # Data preview
    @output
    @render.ui
    def data_preview_ui():
        df = uploaded_data.get()
        if df is not None:
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
            return df.head(10)
        return pd.DataFrame()
    
    # Features configuration UI
    @output
    @render.ui
    def features_config_ui():
        df = uploaded_data.get()
        if df is None:
            return ui.p("Please upload data first in the Data Input tab.")
        
        num_features = df.shape[1] - 1  # Exclude Subzone ID column
        feature_names = df.columns[1:].tolist()
        
        return ui.TagList(
            ui.p(f"Detected {num_features} features in uploaded data."),
            ui.p("Configure characteristics for each feature:"),
            ui.markdown("*(In a full implementation, you would set rarity status, significance, etc. for each feature)*")
        )
    
    @output
    @render.table
    def features_summary_table():
        df = uploaded_data.get()
        if df is not None:
            feature_names = df.columns[1:].tolist()
            summary = {
                "Feature Name": feature_names,
                "Count": [df[col].sum() for col in feature_names],
                "Average": [df[col].mean() for col in feature_names]
            }
            return pd.DataFrame(summary)
        return pd.DataFrame()
    
    # Calculate results (simplified version)
    @reactive.Calc
    def calculate_results():
        df = uploaded_data.get()
        if df is None:
            return None
        
        # Simplified AQ and EV calculation
        # In a real implementation, this would include all 9 AQ calculations
        results = df.copy()
        
        # Calculate simple EV score (sum of features per subzone)
        feature_cols = df.columns[1:]
        results['AQ_Score'] = df[feature_cols].sum(axis=1)
        results['EV'] = results['AQ_Score'] / len(feature_cols)  # Normalized EV
        
        return results
    
    # Results UI
    @output
    @render.ui
    def results_ui():
        results = calculate_results()
        if results is not None:
            return ui.TagList(
                ui.div(
                    ui.h5(f"✅ Analysis Complete: {len(results)} subzones analyzed", 
                          style="color: #28a745; font-weight: 600; margin-bottom: 1.5rem;"),
                    class_="info-box"
                ),
                ui.card(
                    ui.card_header("📊 Detailed Results Table"),
                    ui.div(
                        ui.output_table("results_table"),
                        style="padding: 1rem;"
                    )
                )
            )
        return ui.div(
            ui.p(
                "⚠️ No results to display. Please upload data in the Data Input tab first.",
                style="font-size: 1.1rem; text-align: center; color: #6c757d; padding: 2rem;"
            )
        )
    
    @output
    @render.table
    def results_table():
        results = calculate_results()
        if results is not None:
            return results[['Subzone ID', 'AQ_Score', 'EV']].head(20)
        return pd.DataFrame()
    
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
            return results[['Subzone ID', 'EV']].head(20)
        return pd.DataFrame()
    
    # Download results
    @render.download(filename="eva_results.csv")
    def download_results():
        results = calculate_results()
        if results is not None:
            return io.StringIO(results.to_csv(index=False))
        return io.StringIO("")
    
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
            df = uploaded_data()
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
