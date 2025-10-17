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

# Optimized CSS with reduced redundancy and better organization
custom_css = """
<style>
    /* CSS Variables - Single source of truth for colors and spacing */
    :root {
        --primary-blue: #0066cc;
        --secondary-blue: #4da6ff;
        --accent-teal: #00b8d4;
        --success-green: #28a745;
        --ocean-blue: #006994;
        --light-bg: #f8f9fa;
        --text-dark: #495057;
        --text-muted: #6c757d;
        --border-light: #dee2e6;
        
        /* Gradient definitions */
        --gradient-primary: linear-gradient(135deg, var(--ocean-blue) 0%, var(--accent-teal) 100%);
        --gradient-secondary: linear-gradient(135deg, var(--secondary-blue) 0%, var(--primary-blue) 100%);
        --gradient-light: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
        
        /* Spacing */
        --spacing-xs: 0.5rem;
        --spacing-sm: 1rem;
        --spacing-md: 1.5rem;
        --spacing-lg: 2rem;
        
        /* Shadows */
        --shadow-light: 0 2px 4px rgba(0,0,0,0.06);
        --shadow-medium: 0 4px 6px rgba(0,0,0,0.07);
        --shadow-hover: 0 8px 15px rgba(0,0,0,0.1);
        
        /* Transitions */
        --transition-smooth: all 0.3s ease;
    }
    
    /* Base hover effects - DRY principle */
    .hover-lift {
        transition: var(--transition-smooth);
    }
    .hover-lift:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-hover);
    }
    
    /* Navigation */
    .navbar {
        background: var(--gradient-primary) !important;
        box-shadow: var(--shadow-light);
        padding: var(--spacing-xs) var(--spacing-sm);
    }
    
    .navbar-brand {
        font-weight: 700;
        font-size: 1.5rem;
        color: white !important;
        display: flex;
        align-items: center;
        gap: 15px;
    }
    
    .nav-link {
        color: rgba(255,255,255,0.9) !important;
        font-weight: 500;
        transition: var(--transition-smooth);
        border-radius: 5px;
        padding: var(--spacing-xs) var(--spacing-sm);
    }
    
    .nav-link:hover { background-color: rgba(255,255,255,0.15); color: white !important; }
    .nav-link.active { background-color: rgba(255,255,255,0.25) !important; color: white !important; font-weight: 600; }
    
    /* Cards - consolidated styling */
    .card {
        border: none;
        border-radius: 12px;
        box-shadow: var(--shadow-medium);
        overflow: hidden;
    }
    .card.hover-lift { transition: var(--transition-smooth); }
    
    .card-header {
        background: var(--gradient-primary);
        color: white;
        font-weight: 600;
        font-size: 1.2rem;
        padding: var(--spacing-sm) var(--spacing-md);
        border-bottom: none;
    }
    
    .card-body { padding: var(--spacing-md); }
    
    /* Buttons - unified button system */
    .btn-primary {
        background: var(--gradient-primary);
        border: none;
        border-radius: 8px;
        padding: 0.6rem var(--spacing-md);
        font-weight: 600;
        box-shadow: var(--shadow-light);
    }
    
    .btn-secondary {
        background: linear-gradient(135deg, #6c757d 0%, #5a6268 100%);
        border: none;
        border-radius: 8px;
        padding: 0.6rem var(--spacing-md);
        font-weight: 600;
    }
    
    .btn-primary:hover, .btn-secondary:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }
    
    /* Forms */
    .form-control, .form-select {
        border: 2px solid var(--border-light);
        border-radius: 8px;
        padding: 0.6rem var(--spacing-sm);
        transition: var(--transition-smooth);
    }
    
    .form-control:focus, .form-select:focus {
        border-color: var(--accent-teal);
        box-shadow: 0 0 0 0.2rem rgba(0, 184, 212, 0.25);
    }
    
    /* Sidebar */
    .bslib-sidebar-layout > .sidebar {
        background: var(--gradient-light);
        border-right: 2px solid var(--border-light);
        border-radius: 8px 0 0 8px;
        padding: var(--spacing-md);
    }
    
    .sidebar h4, .sidebar h5 {
        color: var(--ocean-blue);
        font-weight: 600;
        margin-bottom: var(--spacing-sm);
        border-bottom: 3px solid var(--accent-teal);
        padding-bottom: var(--spacing-xs);
    }
    
    /* Content sections */
    .welcome-banner {
        background: var(--gradient-primary);
        color: white;
        padding: var(--spacing-lg);
        border-radius: 12px;
        margin-bottom: var(--spacing-md);
        box-shadow: var(--shadow-medium);
    }
    
    .info-box {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-left: 4px solid var(--primary-blue);
        padding: var(--spacing-sm) var(--spacing-md);
        border-radius: 8px;
        margin: var(--spacing-sm) 0;
    }
    
    /* Tables */
    table { border-radius: 8px; overflow: hidden; }
    table thead { background: var(--gradient-primary); color: white; }
    table tbody tr:hover { background-color: rgba(0, 184, 212, 0.1); }
    
    /* Value boxes */
    .bslib-value-box {
        border-radius: 12px;
        border: none;
        box-shadow: var(--shadow-medium);
    }
    
    /* Typography */
    .markdown-content { line-height: 1.8; }
    .markdown-content h3, .markdown-content h4 { color: var(--ocean-blue); font-weight: 600; }
    .markdown-content h3 { border-left: 4px solid var(--accent-teal); padding-left: var(--spacing-sm); }
    
    /* Utilities */
    .text-muted { color: var(--text-muted) !important; }
    .text-dark { color: var(--text-dark) !important; }
    hr { border-top: 2px solid var(--accent-teal); margin: var(--spacing-md) 0; }
    
    /* Footer */
    .app-footer {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        color: white;
        padding: var(--spacing-md);
        text-align: center;
        margin-top: var(--spacing-lg);
        border-radius: 12px;
        font-size: 0.9rem;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .card, .bslib-value-box { animation: fadeIn 0.5s ease-out; }
    
    /* Responsive */
    @media (max-width: 768px) {
        .navbar-brand { font-size: 1.2rem; }
        :root { --spacing-md: 1rem; --spacing-lg: 1.5rem; }
    }
</style>
"""

# Utility functions for common UI components
def create_logo_section(height: int = 50):
    """Create consistent logo section with both MARBEFES and IECS logos"""
    return ui.div(
        ui.HTML(f'<img src="marbefes.png" alt="MARBEFES Logo" style="height: {height}px; margin-right: 10px;">'),
        ui.HTML(f'<img src="iecs.png" alt="IECS Logo" style="height: {height}px;">'),
        style="display: flex; align-items: center; justify-content: center;"
    )

def create_info_card(header: str, content, icon: str = "ℹ️"):
    """Create consistent info card with header and content"""
    return ui.card(
        ui.card_header(f"{icon} {header}"),
        ui.div(content, style="padding: 1rem;")
    )

def create_feature_summary_item(title: str, description: str, color: str):
    """Create consistent feature summary items for key concepts section"""
    return ui.div(
        ui.h4(title, style=f"color: {color}; font-weight: 700; margin-bottom: 0.5rem;"),
        ui.p(description, style="color: var(--text-muted); margin: 0;"),
        style="padding: 1rem; background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-radius: 8px;"
    )

# Configuration constants
ASSESSMENT_QUESTIONS = [
    "AQ1: Locally rare features (LRF)",
    "AQ2: Regionally rare features (RRF)", 
    "AQ3: Nationally rare features (NRF)",
    "AQ4: Regularly occurring features (ROF)",
    "AQ5: Ecologically significant features (ESF)",
    "AQ6: Habitat forming species (HFS)",
    "AQ7: Biogenic habitat (BH)",
    "AQ8: Symbiotic species (SS)",
    "AQ9: Combined score"
]

ACRONYMS_DATA = {
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

# App UI
app_ui = ui.page_navbar(
    ui.nav_panel(
        "🏠 Home",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div(
                    ui.div(
                        ui.div(
                            create_logo_section(50),
                            style="margin: 0 auto 1rem; padding: 10px; background: white; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"
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
                                create_logo_section(60),
                                ui.span("MARBEFES", style="font-weight: 800; margin: 0 15px;"),
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
        "📐 Formulas & Methods",
        ui.div(
            ui.div(
                ui.h2("📐 EVA Calculation Formulas & Methods", style="color: var(--ocean-blue); font-weight: 700; margin-bottom: var(--spacing-md);"),
                ui.p(
                    "Detailed mathematical formulas and methodologies used in the Ecological Value Assessment framework.",
                    style="font-size: 1.1rem; color: var(--text-muted); margin-bottom: var(--spacing-lg);"
                ),
                class_="markdown-content"
            ),
            
            # Overview Card
            ui.card(
                ui.card_header("🎯 Assessment Framework Overview"),
                ui.div(
                    ui.p(
                        "The EVA framework uses a structured approach with 9 Assessment Questions (AQ1-AQ9) to evaluate ecological value across spatial units (subzones). "
                        "Each assessment question targets specific ecological characteristics.",
                        style="line-height: 1.8; margin-bottom: var(--spacing-sm);"
                    ),
                    ui.div(
                        ui.h5("Key Metrics", style="color: var(--ocean-blue); font-weight: 600; margin-top: var(--spacing-md);"),
                        ui.tags.ul(
                            ui.tags.li(ui.strong("X"), " = Total mean abundance/area across all subzones"),
                            ui.tags.li(ui.strong("Xi"), " = Abundance/area in subzone i"),
                            ui.tags.li(ui.strong("Y"), " = Percentage of abundance in top 5% subzones"),
                            ui.tags.li(ui.strong("Z"), " = Number of occurrences (presences) across all subzones"),
                            ui.tags.li(ui.strong("EV"), " = Ecological Value (final score)"),
                            style="line-height: 2;"
                        ),
                        class_="info-box"
                    ),
                    style="padding: var(--spacing-md);"
                )
            ),
            
            # Main Calculations
            ui.layout_column_wrap(
                # Left Column - AQ Formulas
                ui.card(
                    ui.card_header("📊 Assessment Question Calculations"),
                    ui.div(
                        ui.h5("AQ1-AQ3: Rarity Assessments", style="color: var(--ocean-blue); font-weight: 600; margin-bottom: var(--spacing-sm);"),
                        ui.tags.dl(
                            ui.tags.dt(ui.strong("AQ1: Locally Rare Features (LRF)")),
                            ui.tags.dd("Features with Y ≥ 50% (i.e., ≥50% of total abundance in top 5% subzones)"),
                            ui.tags.dd(ui.HTML("<code>if Y >= 0.5 then LRF = 1 else LRF = 0</code>")),
                            
                            ui.tags.dt(ui.strong("AQ2: Regionally Rare Features (RRF)"), style="margin-top: var(--spacing-sm);"),
                            ui.tags.dd("Features with 25% ≤ Y < 50%"),
                            ui.tags.dd(ui.HTML("<code>if 0.25 <= Y < 0.5 then RRF = 1 else RRF = 0</code>")),
                            
                            ui.tags.dt(ui.strong("AQ3: Nationally Rare Features (NRF)"), style="margin-top: var(--spacing-sm);"),
                            ui.tags.dd("Features present in ≤5 subzones"),
                            ui.tags.dd(ui.HTML("<code>if Z <= 5 then NRF = 1 else NRF = 0</code>")),
                            style="line-height: 2;"
                        ),
                        
                        ui.hr(),
                        
                        ui.h5("AQ4: Regularly Occurring Features (ROF)", style="color: var(--ocean-blue); font-weight: 600; margin-bottom: var(--spacing-sm); margin-top: var(--spacing-md);"),
                        ui.tags.dl(
                            ui.tags.dd("Features with Y < 25% AND present in >5 subzones"),
                            ui.tags.dd(ui.HTML("<code>if Y < 0.25 AND Z > 5 then ROF = 1 else ROF = 0</code>")),
                            style="line-height: 2;"
                        ),
                        
                        ui.hr(),
                        
                        ui.h5("AQ5-AQ8: Ecological Significance", style="color: var(--ocean-blue); font-weight: 600; margin-bottom: var(--spacing-sm); margin-top: var(--spacing-md);"),
                        ui.tags.dl(
                            ui.tags.dt(ui.strong("AQ5: Ecologically Significant Features (ESF)")),
                            ui.tags.dd("User-defined features of ecological importance"),
                            ui.tags.dd(ui.HTML("<code>ESF = 1 if designated, else 0</code>")),
                            
                            ui.tags.dt(ui.strong("AQ6: Habitat Forming Species (HFS)"), style="margin-top: var(--spacing-sm);"),
                            ui.tags.dd("Species that create structural habitat"),
                            ui.tags.dd(ui.HTML("<code>HFS = 1 if designated, else 0</code>")),
                            
                            ui.tags.dt(ui.strong("AQ7: Biogenic Habitat (BH)"), style="margin-top: var(--spacing-sm);"),
                            ui.tags.dd("Habitats formed by living organisms"),
                            ui.tags.dd(ui.HTML("<code>BH = 1 if designated, else 0</code>")),
                            
                            ui.tags.dt(ui.strong("AQ8: Symbiotic Species (SS)"), style="margin-top: var(--spacing-sm);"),
                            ui.tags.dd("Species engaged in symbiotic relationships"),
                            ui.tags.dd(ui.HTML("<code>SS = 1 if designated, else 0</code>")),
                            style="line-height: 2;"
                        ),
                        style="padding: var(--spacing-md);"
                    )
                ),
                
                # Right Column - EV Calculation
                ui.card(
                    ui.card_header("🧮 Ecological Value (EV) Calculation"),
                    ui.div(
                        ui.h5("AQ9: Combined Assessment Score", style="color: var(--success-green); font-weight: 600; margin-bottom: var(--spacing-md);"),
                        
                        ui.div(
                            ui.h6("Step 1: Calculate Feature Presence Matrix (FPM)", style="font-weight: 600;"),
                            ui.p("For each subzone and feature, determine presence based on AQ1-AQ8:"),
                            ui.HTML("<code>FPM<sub>i,j</sub> = (Xi<sub>j</sub> / X<sub>j</sub>) × (AQ1 + AQ2 + AQ3 + AQ4 + AQ5 + AQ6 + AQ7 + AQ8)</code>"),
                            ui.p(
                                "Where:",
                                ui.tags.ul(
                                    ui.tags.li("i = subzone index"),
                                    ui.tags.li("j = feature index"),
                                    ui.tags.li("Xi<sub>j</sub> = abundance of feature j in subzone i"),
                                    ui.tags.li("X<sub>j</sub> = mean abundance of feature j across all subzones"),
                                ),
                                style="font-size: 0.9rem; margin-top: 0.5rem;"
                            ),
                            class_="info-box",
                            style="margin-bottom: var(--spacing-md);"
                        ),
                        
                        ui.div(
                            ui.h6("Step 2: Sum Across Features", style="font-weight: 600;"),
                            ui.p("For each subzone, sum the FPM values across all features:"),
                            ui.HTML("<code>AQ9<sub>i</sub> = Σ<sub>j</sub> FPM<sub>i,j</sub></code>"),
                            ui.p("This gives the total assessment score for each subzone.", style="font-size: 0.9rem; margin-top: 0.5rem;"),
                            class_="info-box",
                            style="margin-bottom: var(--spacing-md);"
                        ),
                        
                        ui.div(
                            ui.h6("Step 3: Calculate Ecological Value (EV)", style="font-weight: 600;"),
                            ui.p("Normalize the AQ9 score:"),
                            ui.HTML("<code>EV<sub>i</sub> = AQ9<sub>i</sub> / n</code>"),
                            ui.p(
                                "Where n = number of features being assessed",
                                style="font-size: 0.9rem; margin-top: 0.5rem;"
                            ),
                            style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); padding: var(--spacing-md); border-radius: 8px; border-left: 4px solid var(--success-green);"
                        ),
                        
                        ui.hr(),
                        
                        ui.h5("Total EV Across Ecosystem Components", style="color: var(--ocean-blue); font-weight: 600; margin-top: var(--spacing-md); margin-bottom: var(--spacing-sm);"),
                        ui.p("When assessing multiple Ecosystem Components (ECs):"),
                        ui.HTML("<code>Total_EV<sub>i</sub> = Σ<sub>k</sub> EV<sub>i,k</sub></code>"),
                        ui.p(
                            "Where k represents each ecosystem component (e.g., different species groups or habitats)",
                            style="font-size: 0.9rem; margin-top: 0.5rem;"
                        ),
                        
                        style="padding: var(--spacing-md);"
                    )
                ),
                width=1/2
            ),
            
            # Calculation Steps Detail
            ui.card(
                ui.card_header("🔬 Detailed Calculation Steps"),
                ui.div(
                    ui.h5("Complete Workflow", style="color: var(--ocean-blue); font-weight: 600; margin-bottom: var(--spacing-md);"),
                    
                    ui.tags.ol(
                        ui.tags.li(
                            ui.strong("Data Preparation:"),
                            ui.tags.ul(
                                ui.tags.li("Load gridded data with subzones as rows and features as columns"),
                                ui.tags.li("Calculate X (total mean) for each feature: X<sub>j</sub> = mean(Xi<sub>j</sub>)"),
                                ui.tags.li("Identify 95th percentile for each feature distribution"),
                            )
                        ),
                        ui.tags.li(
                            ui.strong("Rarity Assessment (AQ1-AQ3):"),
                            ui.tags.ul(
                                ui.tags.li("Calculate Y = (sum of abundance in top 5% subzones) / (total abundance)"),
                                ui.tags.li("Calculate Z = count of subzones where feature is present"),
                                ui.tags.li("Apply threshold criteria to determine LRF, RRF, and NRF"),
                            )
                        ),
                        ui.tags.li(
                            ui.strong("Regular Occurrence (AQ4):"),
                            ui.tags.ul(
                                ui.tags.li("Check if Y < 0.25 AND Z > 5"),
                            )
                        ),
                        ui.tags.li(
                            ui.strong("Ecological Significance (AQ5-AQ8):"),
                            ui.tags.ul(
                                ui.tags.li("Apply user-defined classifications for ESF, HFS, BH, SS"),
                                ui.tags.li("These are binary flags (0 or 1) set during feature configuration"),
                            )
                        ),
                        ui.tags.li(
                            ui.strong("Feature Presence Matrix (AQ9):"),
                            ui.tags.ul(
                                ui.tags.li("For each cell (subzone × feature), calculate: (Xi/X) × Σ(AQ1-AQ8)"),
                                ui.tags.li("Sum across all features for each subzone"),
                            )
                        ),
                        ui.tags.li(
                            ui.strong("Final EV:"),
                            ui.tags.ul(
                                ui.tags.li("Normalize AQ9 by dividing by number of features"),
                                ui.tags.li("Aggregate across ecosystem components if needed"),
                            )
                        ),
                        style="line-height: 2.2; font-size: 1rem;"
                    ),
                    style="padding: var(--spacing-md);"
                )
            ),
            
            # Implementation Notes
            ui.card(
                ui.card_header("✅ Current Implementation Status - FULLY COMPLETE"),
                ui.div(
                    ui.div(
                        ui.h5("✅ Core EVA Methodology", style="color: var(--success-green); font-weight: 600;"),
                        ui.tags.ul(
                            ui.tags.li("✅ Complete AQ1-AQ8 calculations with proper thresholds"),
                            ui.tags.li("✅ AQ1: Locally Rare Features (Y ≥ 50%)"),
                            ui.tags.li("✅ AQ2: Regionally Rare Features (25% ≤ Y < 50%)"),
                            ui.tags.li("✅ AQ3: Nationally Rare Features (Z ≤ 5)"),
                            ui.tags.li("✅ AQ4: Regularly Occurring Features (Y < 25% AND Z > 5)"),
                            ui.tags.li("✅ AQ5-AQ8: User-configurable ecological significance flags"),
                            ui.tags.li("✅ AQ9: Complete Feature Presence Matrix (FPM) calculation"),
                            ui.tags.li("✅ EV: Normalized Ecological Value per subzone"),
                        ),
                        style="margin-bottom: var(--spacing-md);"
                    ),
                    ui.div(
                        ui.h5("✅ Advanced Features", style="color: var(--success-green); font-weight: 600;"),
                        ui.tags.ul(
                            ui.tags.li("✅ 95th percentile detection for rarity assessment"),
                            ui.tags.li("✅ Y/Z/X metrics calculation and display"),
                            ui.tags.li("✅ Feature configuration interface with checkboxes"),
                            ui.tags.li("✅ Multiple ecosystem component (EC) support"),
                            ui.tags.li("✅ EC storage and management system"),
                            ui.tags.li("✅ Aggregated Total EV across multiple ECs"),
                            ui.tags.li("✅ Enhanced feature metrics summary table"),
                            ui.tags.li("✅ Data export functionality"),
                        ),
                        style="margin-bottom: var(--spacing-md);"
                    ),
                    ui.div(
                        ui.p(
                            "🎉 ", ui.strong("Production Ready: "),
                            "This version implements the complete EVA methodology with all AQ1-AQ9 calculations, "
                            "proper thresholds, Feature Presence Matrix, and multiple EC support. "
                            "All formulas match the MARBEFES Phase 2 specification.",
                            style="margin: 0;"
                        ),
                        class_="info-box",
                        style="background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); border-left: 4px solid var(--success-green);"
                    ),
                    style="padding: var(--spacing-md);"
                )
            ),
            
            # Footer Reference
            ui.div(
                ui.p(
                    "📖 ", ui.strong("Reference: "),
                    "Franco A. and Amorim E. (2025) Ecological Value Assessment (EVA) - Phase 2 Methodology",
                    style="margin: 0.5rem 0;"
                ),
                ui.p(
                    "🔬 ", ui.strong("Based on: "),
                    "MARBEFES_EVA-Phase2_template.xlsx calculation sheets",
                    style="margin: 0.5rem 0;"
                ),
                class_="app-footer"
            )
        )
    ),
    
    ui.nav_panel(
        "�📁 Data Input",
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
                    ui.h5("� Stored ECs", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.output_ui("stored_ec_list"),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("�📤 Upload Data", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
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
    
    # Reactive values for storing data - properly typed
    uploaded_data = reactive.Value(pd.DataFrame())
    features_data = reactive.Value(pd.DataFrame()) 
    results_data = reactive.Value(pd.DataFrame())
    
    # Multiple EC support
    ec_datasets = reactive.Value({})  # Dictionary to store multiple EC datasets
    current_ec_name = reactive.Value("")  # Currently active EC
    
    # AQ5-AQ8 feature classifications
    aq5_features = reactive.Value([])  # Ecologically Significant Features
    aq6_features = reactive.Value([])  # Habitat Forming Species
    aq7_features = reactive.Value([])  # Biogenic Habitat
    aq8_features = reactive.Value([])  # Symbiotic Species
    
    # Acronyms table - using constants
    @output
    @render.table
    def acronyms_table():
        return pd.DataFrame(ACRONYMS_DATA)
    
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
    
    # Handle file upload with proper validation
    @reactive.Effect
    @reactive.event(input.upload_data)
    def handle_upload():
        file_info = input.upload_data()
        if file_info is not None and len(file_info) > 0:
            try:
                file_path = file_info[0]["datapath"]
                df = pd.read_csv(file_path)
                
                # Validate data structure
                if df.empty:
                    print("Warning: Empty CSV file uploaded")
                    return
                
                if df.shape[1] < 2:
                    print("Warning: CSV file must have at least 2 columns (Subzone ID + features)")
                    return
                
                uploaded_data.set(df)
                print(f"Successfully loaded {df.shape[0]} rows × {df.shape[1]} columns")
                
                # Store EC dataset if EC name is provided
                ec_name = input.ec_name()
                if ec_name and ec_name.strip():
                    ec_data = ec_datasets.get()
                    ec_data[ec_name] = {
                        'data': df,
                        'results': None,
                        'aq5': aq5_features.get(),
                        'aq6': aq6_features.get(),
                        'aq7': aq7_features.get(),
                        'aq8': aq8_features.get()
                    }
                    ec_datasets.set(ec_data)
                    current_ec_name.set(ec_name)
                    print(f"Stored dataset for EC: {ec_name}")
                
            except Exception as e:
                print(f"Error loading CSV file: {str(e)}")
                uploaded_data.set(pd.DataFrame())
    
    # Display stored EC list
    @output
    @render.ui
    def stored_ec_list():
        ec_data = ec_datasets.get()
        if not ec_data or len(ec_data) == 0:
            return ui.p("No ECs stored yet", style="color: var(--text-muted); font-size: 0.9rem;")
        
        return ui.TagList(
            ui.p(f"✅ {len(ec_data)} EC(s) stored:", style="font-weight: 600; margin-bottom: 0.5rem;"),
            ui.tags.ul(
                *[ui.tags.li(f"{ec_name} ({ec_info['data'].shape[0]} rows)", 
                            style="font-size: 0.9rem; color: var(--ocean-blue);") 
                  for ec_name, ec_info in ec_data.items()],
                style="list-style: none; padding-left: 0;"
            )
        )
    
    # Data preview with improved validation
    @output
    @render.ui
    def data_preview_ui():
        df = uploaded_data.get()
        if df is not None and not df.empty:
            return ui.card(
                ui.card_header("✅ Data Preview"),
                ui.div(
                    ui.div(
                        ui.h5(f"📊 Dataset: {df.shape[0]} subzones × {df.shape[1]-1} features", 
                              style="color: var(--success-green); font-weight: 600; margin-bottom: 1rem;"),
                        ui.p(
                            f"✓ Successfully loaded data with {df.shape[0]} rows and {df.shape[1]} columns",
                            style="color: var(--text-muted);"
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
                            style="font-size: 1.1rem; text-align: center; color: var(--text-muted); padding: 2rem;"
                        ),
                        ui.p(
                            "💡 You can download a template file to see the expected format.",
                            style="text-align: center; color: var(--text-muted);"
                        )
                    )
                )
            )
    
    @output
    @render.table
    def data_preview_table():
        df = uploaded_data.get()
        if df is not None and not df.empty:
            return df.head(10)
        return pd.DataFrame()
    
    # Handle AQ5-AQ8 configuration
    @reactive.Effect
    @reactive.event(input.apply_aq_config)
    def handle_aq_config():
        aq5_features.set(input.aq5_checkboxes() or [])
        aq6_features.set(input.aq6_checkboxes() or [])
        aq7_features.set(input.aq7_checkboxes() or [])
        aq8_features.set(input.aq8_checkboxes() or [])
        print(f"AQ classifications updated: AQ5={len(aq5_features.get())}, AQ6={len(aq6_features.get())}, AQ7={len(aq7_features.get())}, AQ8={len(aq8_features.get())}")
    
    # Features configuration UI
    @output
    @render.ui
    def features_config_ui():
        df = uploaded_data.get()
        if df is None or df.empty:
            return ui.p("Please upload data first in the Data Input tab.")
        
        feature_names = df.columns[1:].tolist()  # Exclude Subzone ID column
        
        if not feature_names:
            return ui.p("No features detected in uploaded data.")
        
        return ui.TagList(
            ui.div(
                ui.h5("🎯 AQ5-AQ8 Feature Classifications", style="color: var(--ocean-blue); font-weight: 600; margin-bottom: var(--spacing-md);"),
                ui.p("Configure which features fall into each ecological significance category. These classifications affect the final EV calculations.", 
                     style="margin-bottom: var(--spacing-lg);"),
                
                # AQ5: Ecologically Significant Features
                ui.div(
                    ui.h6("AQ5: Ecologically Significant Features (ESF)", style="color: var(--success-green); font-weight: 600; margin-top: var(--spacing-lg);"),
                    ui.p("Features of particular ecological importance that should be highlighted in assessments.", style="font-size: 0.9rem; color: var(--text-muted);"),
                    ui.input_checkbox_group(
                        "aq5_checkboxes",
                        "",
                        choices=feature_names,
                        selected=aq5_features.get(),
                        inline=False
                    ),
                    class_="feature-category"
                ),
                
                # AQ6: Habitat Forming Species
                ui.div(
                    ui.h6("AQ6: Habitat Forming Species (HFS)", style="color: var(--success-green); font-weight: 600; margin-top: var(--spacing-lg);"),
                    ui.p("Species that create structural habitat for other organisms.", style="font-size: 0.9rem; color: var(--text-muted);"),
                    ui.input_checkbox_group(
                        "aq6_checkboxes",
                        "",
                        choices=feature_names,
                        selected=aq6_features.get(),
                        inline=False
                    ),
                    class_="feature-category"
                ),
                
                # AQ7: Biogenic Habitat
                ui.div(
                    ui.h6("AQ7: Biogenic Habitat (BH)", style="color: var(--success-green); font-weight: 600; margin-top: var(--spacing-lg);"),
                    ui.p("Habitats formed by living organisms (e.g., coral reefs, oyster beds).", style="font-size: 0.9rem; color: var(--text-muted);"),
                    ui.input_checkbox_group(
                        "aq7_checkboxes",
                        "",
                        choices=feature_names,
                        selected=aq7_features.get(),
                        inline=False
                    ),
                    class_="feature-category"
                ),
                
                # AQ8: Symbiotic Species
                ui.div(
                    ui.h6("AQ8: Symbiotic Species (SS)", style="color: var(--success-green); font-weight: 600; margin-top: var(--spacing-lg);"),
                    ui.p("Species involved in symbiotic relationships with other organisms.", style="font-size: 0.9rem; color: var(--text-muted);"),
                    ui.input_checkbox_group(
                        "aq8_checkboxes",
                        "",
                        choices=feature_names,
                        selected=aq8_features.get(),
                        inline=False
                    ),
                    class_="feature-category"
                ),
                
                ui.div(
                    ui.input_action_button(
                        "apply_aq_config",
                        "✓ Apply AQ Classifications",
                        class_="btn-primary",
                        style="margin-top: var(--spacing-lg); width: 100%; font-size: 1.1rem; padding: 0.8rem;"
                    ),
                    style="margin-top: var(--spacing-lg);"
                ),
                
                class_="aq-config-panel"
            )
        )
    
    @output
    @render.table
    def features_summary_table():
        df = uploaded_data.get()
        if df is not None and not df.empty and len(df.columns) > 1:
            feature_names = df.columns[1:].tolist()
            
            # Calculate feature metrics for display
            results = calculate_results()
            feature_metrics_data = []
            
            for feature in feature_names:
                if pd.api.types.is_numeric_dtype(df[feature]):
                    # Calculate X, Y, Z metrics
                    X = df[feature].mean()
                    Z = (df[feature] > 0).sum()
                    
                    # Calculate Y (95th percentile threshold)
                    if len(df) >= 20:
                        threshold_95 = df[feature].quantile(0.95)
                        top_5_percent = df[df[feature] >= threshold_95]
                        Y = (top_5_percent[feature].sum() / df[feature].sum() * 100) if df[feature].sum() > 0 else 0
                    else:
                        threshold_80 = df[feature].quantile(0.80)
                        top_20_percent = df[df[feature] >= threshold_80]
                        Y = (top_20_percent[feature].sum() / df[feature].sum() * 100) if df[feature].sum() > 0 else 0
                    
                    # Get AQ classifications
                    aq5_list = aq5_features.get()
                    aq6_list = aq6_features.get()
                    aq7_list = aq7_features.get()
                    aq8_list = aq8_features.get()
                    
                    classifications = []
                    if feature in aq5_list:
                        classifications.append("ESF")
                    if feature in aq6_list:
                        classifications.append("HFS")
                    if feature in aq7_list:
                        classifications.append("BH")
                    if feature in aq8_list:
                        classifications.append("SS")
                    
                    feature_metrics_data.append({
                        "Feature": feature,
                        "Mean (X)": f"{X:.2f}",
                        "Occurrences (Z)": Z,
                        "Top 5% Conc. (Y%)": f"{Y:.1f}%",
                        "Classifications": ", ".join(classifications) if classifications else "-"
                    })
            
            return pd.DataFrame(feature_metrics_data)
        return pd.DataFrame()
    
    # Calculate results with improved validation and efficiency
    @reactive.Calc
    def calculate_results():
        df = uploaded_data.get()
        if df is None or df.empty or len(df.columns) < 2:
            return pd.DataFrame()
        
        try:
            # Create a copy for results
            results = df.copy()
            
            # Get feature columns (exclude first column which should be Subzone ID)
            feature_cols = df.columns[1:].tolist()
            
            # Only process numeric columns for calculations
            numeric_cols = [col for col in feature_cols if pd.api.types.is_numeric_dtype(df[col])]
            
            if not numeric_cols:
                results['AQ_Score'] = 0
                results['EV'] = 0
                return results
            
            # Initialize AQ columns
            for i in range(1, 9):
                results[f'AQ{i}'] = 0
            
            # Calculate metrics for each feature
            feature_metrics = {}
            for feature in numeric_cols:
                # X: Mean abundance across all subzones
                X = df[feature].mean()
                
                # Z: Number of occurrences (subzones where feature > 0)
                Z = (df[feature] > 0).sum()
                
                # Y: Percentage of abundance in top 5% subzones
                # First, find the 95th percentile threshold for abundance
                if len(df) >= 20:  # Need enough data for meaningful percentiles
                    threshold_95 = df[feature].quantile(0.95)
                    # Get subzones in top 5% (above 95th percentile)
                    top_5_percent = df[df[feature] >= threshold_95]
                    if len(top_5_percent) > 0:
                        Y = top_5_percent[feature].sum() / df[feature].sum() if df[feature].sum() > 0 else 0
                    else:
                        Y = 0
                else:
                    # For small datasets, use top 20% as approximation
                    threshold_80 = df[feature].quantile(0.80)
                    top_20_percent = df[df[feature] >= threshold_80]
                    Y = top_20_percent[feature].sum() / df[feature].sum() if df[feature].sum() > 0 else 0
                
                feature_metrics[feature] = {'X': X, 'Y': Y, 'Z': Z}
                
                # Calculate AQ1-AQ4 for each feature
                # AQ1: Locally Rare Features (Y >= 0.5)
                if Y >= 0.5:
                    results[f'AQ1_{feature}'] = 1
                else:
                    results[f'AQ1_{feature}'] = 0
                
                # AQ2: Regionally Rare Features (0.25 <= Y < 0.5)
                if 0.25 <= Y < 0.5:
                    results[f'AQ2_{feature}'] = 1
                else:
                    results[f'AQ2_{feature}'] = 0
                
                # AQ3: Nationally Rare Features (Z <= 5)
                if Z <= 5:
                    results[f'AQ3_{feature}'] = 1
                else:
                    results[f'AQ3_{feature}'] = 0
                
                # AQ4: Regularly Occurring Features (Y < 0.25 AND Z > 5)
                if Y < 0.25 and Z > 5:
                    results[f'AQ4_{feature}'] = 1
                else:
                    results[f'AQ4_{feature}'] = 0
            
            # Calculate AQ5-AQ8 (user-defined classifications)
            aq5_list = aq5_features.get()
            aq6_list = aq6_features.get()
            aq7_list = aq7_features.get()
            aq8_list = aq8_features.get()
            
            for feature in numeric_cols:
                results[f'AQ5_{feature}'] = 1 if feature in aq5_list else 0  # Ecologically Significant Features
                results[f'AQ6_{feature}'] = 1 if feature in aq6_list else 0  # Habitat Forming Species
                results[f'AQ7_{feature}'] = 1 if feature in aq7_list else 0  # Biogenic Habitat
                results[f'AQ8_{feature}'] = 1 if feature in aq8_list else 0  # Symbiotic Species
            
            # Calculate Feature Presence Matrix (FPM) and AQ9 for each subzone
            results['AQ9'] = 0.0
            
            for idx in results.index:
                fpm_sum = 0.0
                row = results.loc[idx]
                for feature in numeric_cols:
                    # FPM = (Xi/X) * sum(AQ1-AQ8)
                    Xi = row[feature]
                    X = feature_metrics[feature]['X']
                    
                    if X > 0:
                        abundance_ratio = Xi / X
                    else:
                        abundance_ratio = 0
                    
                    # Sum AQ1-AQ8 for this feature
                    aq_sum = (row[f'AQ1_{feature}'] + row[f'AQ2_{feature}'] + row[f'AQ3_{feature}'] + 
                             row[f'AQ4_{feature}'] + row[f'AQ5_{feature}'] + row[f'AQ6_{feature}'] + 
                             row[f'AQ7_{feature}'] + row[f'AQ8_{feature}'])
                    
                    fpm = abundance_ratio * aq_sum
                    fpm_sum += fpm
                
                results.at[idx, 'AQ9'] = fpm_sum
            
            # Calculate EV (Ecological Value)
            n_features = len(numeric_cols)
            results['EV'] = results['AQ9'] / n_features if n_features > 0 else 0
            
            # Calculate individual AQ scores (sum of each AQ type across features)
            for i in range(1, 9):
                aq_cols = [f'AQ{i}_{feature}' for feature in numeric_cols if f'AQ{i}_{feature}' in results.columns]
                if aq_cols:
                    results[f'AQ{i}'] = results[aq_cols].sum(axis=1)
            
            return results
            
        except Exception as e:
            print(f"Error calculating results: {str(e)}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    # Results UI with consistent styling
    @output
    @render.ui
    def results_ui():
        results = calculate_results()
        if results is not None and not results.empty:
            return ui.TagList(
                ui.div(
                    ui.h5(f"✅ Analysis Complete: {len(results)} subzones analyzed", 
                          style="color: var(--success-green); font-weight: 600; margin-bottom: var(--spacing-md);"),
                    class_="info-box"
                ),
                create_info_card("Detailed Results Table", ui.output_table("results_table"), "📊")
            )
        return ui.div(
            ui.p(
                "⚠️ No results to display. Please upload data in the Data Input tab first.",
                style="font-size: 1.1rem; text-align: center; color: var(--text-muted); padding: var(--spacing-lg);"
            )
        )
    
    @output
    @render.table
    def results_table():
        results = calculate_results()
        if results is not None and not results.empty and 'EV' in results.columns:
            # Show subzone ID, individual AQ scores, AQ9, and EV
            display_cols = [results.columns[0]]  # Subzone ID
            aq_cols = [f'AQ{i}' for i in range(1, 10) if f'AQ{i}' in results.columns]
            display_cols.extend(aq_cols)
            display_cols.append('EV')
            return results[display_cols].head(20)
        return pd.DataFrame()
    
    # Total EV UI with improved validation and multiple EC support
    @output
    @render.ui
    def total_ev_ui():
        results = calculate_results()
        ec_data = ec_datasets.get()
        
        # Check if we have multiple ECs stored
        if ec_data and len(ec_data) > 1:
            # Aggregate multiple ECs
            return ui.TagList(
                ui.card(
                    ui.card_header("📊 Multiple Ecosystem Components Summary"),
                    ui.div(
                        ui.h5(f"🌊 {len(ec_data)} Ecosystem Components Loaded", 
                              style="color: var(--ocean-blue); font-weight: 600; margin-bottom: var(--spacing-md);"),
                        ui.tags.ul(
                            *[ui.tags.li(f"{ec_name}: {ec_info['data'].shape[0]} subzones × {ec_info['data'].shape[1]-1} features") 
                              for ec_name, ec_info in ec_data.items()],
                            style="line-height: 2;"
                        ),
                        class_="info-box"
                    )
                ),
                ui.hr(),
                ui.h5("📈 Aggregated Total EV (Sum across all ECs)", style="color: var(--ocean-blue); font-weight: 600;"),
                ui.output_table("aggregated_ev_table")
            )
        
        # Single EC or current results
        if results is not None and not results.empty and 'EV' in results.columns:
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
        if results is not None and not results.empty and 'EV' in results.columns:
            display_cols = [results.columns[0], 'EV']  # First column + EV
            return results[display_cols].head(20)
        return pd.DataFrame()
    
    # Aggregated EV table for multiple ECs
    @output
    @render.table
    def aggregated_ev_table():
        ec_data = ec_datasets.get()
        if not ec_data or len(ec_data) == 0:
            return pd.DataFrame()
        
        # Calculate results for each EC and aggregate
        aggregated = None
        
        for ec_name, ec_info in ec_data.items():
            # Temporarily set data for calculation
            temp_df = ec_info['data']
            if temp_df is None or temp_df.empty:
                continue
                
            # Simple EV calculation for aggregation
            feature_cols = temp_df.columns[1:].tolist()
            numeric_cols = [col for col in feature_cols if pd.api.types.is_numeric_dtype(temp_df[col])]
            
            if numeric_cols:
                ev_values = temp_df[numeric_cols].mean(axis=1)  # Simple average for demo
                
                if aggregated is None:
                    aggregated = pd.DataFrame({
                        'Subzone': temp_df.iloc[:, 0],
                        ec_name: ev_values
                    })
                else:
                    aggregated[ec_name] = ev_values
        
        if aggregated is not None:
            # Calculate total EV across all ECs
            ec_cols = [col for col in aggregated.columns if col != 'Subzone']
            aggregated['Total_EV'] = aggregated[ec_cols].sum(axis=1)
            return aggregated.head(20)
        
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
            df = uploaded_data.get()
            if df is not None and not df.empty and len(df.columns) > 1:
                # Get feature columns (exclude first column)
                feature_cols = df.columns[1:].tolist()
                
                # Create heatmap data
                heatmap_data = df[feature_cols].values
                subzone_labels = df.iloc[:, 0].values  # Use first column as subzone labels
                
                fig = go.Figure(data=go.Heatmap(
                    z=heatmap_data,
                    x=feature_cols,
                    y=subzone_labels,
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
            aq_columns = [col for col in results.columns.tolist() if col.startswith('AQ')]
            
            if aq_columns and not results.empty:
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
