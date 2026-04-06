"""
MARBEFES EVA - UI Definition Module

Extracted from app.py: contains custom_css, get_aq_guide_html(), and app_ui.
"""

from shiny import ui
from eva_config import MAX_FEATURES, HEX_PRESETS
from version import __version__ as APP_VERSION_STR, get_version_info
import pa_config

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


# App UI
app_ui = ui.page_navbar(
    ui.nav_panel(
        "🔷 Grid Setup",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div(
                    ui.h5("1. Define Study Area", style="color: #006994; font-weight: 600; margin-bottom: 0.5rem;"),
                    ui.p(
                        "The study area is the marine polygon within which the hexagonal grid will be generated. "
                        "Land areas are automatically removed from the grid.",
                        style="font-size: 0.8rem; color: #6c757d; margin-bottom: 0.75rem;",
                    ),
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
                            "Supported: GeoJSON (.geojson/.json), Zipped Shapefile (.zip), GeoPackage (.gpkg). "
                            "Files must be in WGS84 (EPSG:4326) or will be reprojected automatically.",
                            style="font-size: 0.8rem; color: #6c757d; margin-top: 0.3rem;",
                        ),
                    ),
                    ui.panel_conditional(
                        "input.polygon_source === 'draw'",
                        ui.p(
                            "Use the ◻ rectangle or ⬠ polygon draw tools on the map to outline your study area. "
                            "You can edit or delete shapes after drawing. "
                            "Only the last drawn shape is used.",
                            style="font-size: 0.8rem; color: #6c757d; margin-top: 0.5rem;",
                        ),
                    ),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("2. Grid Parameters", style="color: #006994; font-weight: 600; margin-bottom: 0.5rem;"),
                    ui.p(
                        "Select the hexagon size based on the Ecosystem Component (EC) you are assessing. "
                        "Smaller cells capture fine-scale benthic patterns; larger cells suit mobile species.",
                        style="font-size: 0.8rem; color: #6c757d; margin-bottom: 0.75rem;",
                    ),
                    ui.tooltip(
                        ui.input_select(
                            "hex_preset",
                            "Hexagon size:",
                            choices={k: v["label"] for k, v in HEX_PRESETS.items()},
                            selected="mobile",
                        ),
                        "Inner diameter (flat-to-flat width) of each hexagon, "
                        "measured as twice the apothem per EVA guidance FAQ.",
                        placement="right",
                    ),
                    ui.div(
                        ui.HTML(
                            "<b>📖 EVA Guidance Table 2.1</b><br>"
                            "<b>~250 m</b> → Benthic ECs: macrobenthos, epibenthos, benthic habitats (fine-scale)<br>"
                            "<b>~3 km</b> → Mobile ECs: seabirds, fish, marine mammals, plankton<br>"
                            "<i>Nest smaller grids inside larger ones when combining ECs.</i>"
                        ),
                        style=(
                            "font-size: 0.78rem; color: #555; background: #f0f7ff; "
                            "border-left: 3px solid #006994; border-radius: 4px; "
                            "padding: 0.5rem 0.6rem; margin-top: 0.5rem;"
                        ),
                    ),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("3. Generate", style="color: #006994; font-weight: 600; margin-bottom: 0.5rem;"),
                    ui.tooltip(
                        ui.input_action_button(
                            "generate_grid",
                            "Generate Grid",
                            class_="btn-primary",
                            style="width: 100%; margin-bottom: 0.5rem;",
                        ),
                        "Creates a hexagonal H3 grid covering your study area. "
                        "Land cells are automatically clipped using Natural Earth 10m coastlines.",
                        placement="right",
                    ),
                    ui.tooltip(
                        ui.download_button(
                            "download_grid",
                            "Download GeoJSON",
                            class_="btn-outline-secondary",
                            style="width: 100%; margin-bottom: 0.5rem;",
                        ),
                        "Download the generated grid as a GeoJSON file for use in GIS software (QGIS, ArcGIS, etc.).",
                        placement="right",
                    ),
                    ui.tooltip(
                        ui.input_action_button(
                            "use_grid",
                            "Use This Grid →",
                            class_="btn-success",
                            style="width: 100%;",
                        ),
                        "Load this grid into the EVA pipeline as your spatial assessment units (subzones). "
                        "Proceed to the Data Input tab to upload EC data matched to the Subzone IDs.",
                        placement="right",
                    ),
                    ui.p(
                        "💡 After clicking 'Use This Grid', go to the Data Input tab and upload a CSV "
                        "with a 'Subzone ID' column matching the grid cell IDs (HEX_001, HEX_002, …).",
                        style="font-size: 0.78rem; color: #6c757d; margin-top: 0.6rem;",
                    ),
                ),
                width=380,
            ),
            ui.div(
                ui.output_ui("grid_status_output"),
                ui.output_ui("unified_map_output"),
                class_="main-content",
            ),
        ),
    ),
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
                        "Choose CSV or DwC-A File",
                        accept=[".csv", ".zip"],
                        multiple=False,
                        button_label="Browse...",
                    ),
                    ui.p(
                        "Supported: CSV (.csv) or Darwin Core Archive (.zip)",
                        style="font-size: 0.85rem; color: #6c757d; margin-top: 0.3rem;"
                    ),
                    ui.panel_conditional(
                        "input.upload_data !== null && input.upload_data !== undefined",
                        ui.output_ui("dwca_options_ui"),
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
                                    ui.tags.li(
                                        ui.strong("CSV: "),
                                        "Upload a CSV file with first row as feature names, "
                                        "first column as Subzone IDs, remaining columns as feature data"
                                    ),
                                    ui.tags.li(
                                        ui.strong("Darwin Core Archive (.zip): "),
                                        "Upload a DwC-A zip containing Event core + Occurrence extension. "
                                        "Events become subzones, species become features. "
                                        "Choose abundance (counts) or presence/absence mode."
                                    ),
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
        "📋 Physical Accounts",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div(
                    ui.h5("🏛️ Study Area", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_text("pa_eaa_name", "EAA Name:", placeholder="e.g. Lithuanian Coast MPA"),
                    ui.input_text("pa_boundary_desc", "Boundary Description:", placeholder="Describe the study area boundary"),
                    ui.input_numeric("pa_accounting_year", "Accounting Year:", value=2024, min=1990, max=2100),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("🌿 EUNIS Habitats", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_selectize(
                        "pa_habitat_select",
                        "Select Habitat Types:",
                        choices={h["code"]: f"{h['code']} - {h['name']}" for h in pa_config.EUNIS_HABITATS},
                        multiple=True,
                        options={"placeholder": "Search and select habitats..."}
                    ),
                    ui.input_text("pa_custom_habitat_code", "Custom Code:", placeholder="e.g. MB999"),
                    ui.input_text("pa_custom_habitat_name", "Custom Name:", placeholder="e.g. Local reef habitat"),
                    ui.input_action_button("pa_add_custom_habitat", "Add Custom Habitat", class_="btn-outline-secondary btn-sm", style="margin-top: 0.5rem;"),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("📊 Benefits", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_checkbox_group(
                        "pa_benefits_select",
                        "Active Benefits:",
                        choices={b["name"]: f"{b['name']} ({b['unit']})" for b in pa_config.DEFAULT_BENEFITS},
                        selected=[b["name"] for b in pa_config.DEFAULT_BENEFITS],
                    ),
                    ui.input_text("pa_custom_benefit_name", "Custom Benefit Name:", placeholder="e.g. Aquaculture"),
                    ui.input_text("pa_custom_benefit_unit", "Unit:", placeholder="e.g. tonnes"),
                    ui.input_action_button("pa_add_custom_benefit", "Add Custom Benefit", class_="btn-outline-secondary btn-sm", style="margin-top: 0.5rem;"),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("🗺️ EUNIS Overlay (EUSeaMap)", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.p("Upload a pre-extracted EUNIS Level 3 overlay GeoPackage.",
                         style="font-size: 0.9rem; color: #6c757d;"),
                    ui.input_file(
                        "upload_eunis_overlay",
                        "Choose EUNIS Overlay (.gpkg)",
                        accept=[".gpkg"],
                        multiple=False,
                        button_label="Browse...",
                    ),
                    ui.output_ui("eunis_status_ui"),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("⚙️ Settings", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_select("pa_area_unit", "Area Unit:", choices={"Ha": "Hectares (Ha)", "km2": "Square kilometres (km²)"}, selected="Ha"),
                    ui.download_button("pa_download_standalone", "📊 Download PA Report (Excel)", class_="btn-primary", style="width: 100%; margin-top: 1rem;"),
                    ui.download_button("pa_download_combined", "📊 Download Combined EVA+PA (Excel)", class_="btn-secondary", style="width: 100%; margin-top: 0.5rem;"),
                    ui.download_button("pa_download_bbt8", "📋 Download BBT8 Accounts (Excel)", class_="btn-outline-primary", style="width: 100%; margin-top: 0.5rem;"),
                ),
                width=380
            ),
            ui.div(
                ui.card(
                    ui.card_header("🗺️ Habitat Assignment"),
                    ui.div(ui.output_ui("pa_habitat_assignment_ui"), style="padding: 1rem;")
                ),
                ui.card(
                    ui.card_header("📐 Ecosystem Extent Account"),
                    ui.div(ui.output_ui("pa_extent_ui"), style="padding: 1rem;")
                ),
                ui.card(
                    ui.card_header("📊 Supply Table"),
                    ui.div(ui.output_ui("pa_supply_ui"), style="padding: 1rem;")
                ),
                ui.card(
                    ui.card_header("📋 BBT8 Accounts Summary (EUNIS L3)"),
                    ui.div(ui.output_ui("eunis_accounts_ui"), style="padding: 1rem;")
                ),
            )
        )
    ),

    ui.nav_panel(
        "📖 Help & Method",
        ui.div(
            ui.div(
                ui.h2("📖 Help & Methodology Reference", style="color: #006994; font-weight: 700; margin-bottom: 1.5rem;"),
                ui.p(
                    "Comprehensive guide, user manual, and methodology reference for the MARBEFES EVA application.",
                    style="font-size: 1.1rem; color: #6c757d; margin-bottom: 2rem;"
                )
            ),

            # Version and User Manual card
            ui.card(
                ui.card_header("📚 User Manual & Version Info"),
                ui.div(
                    ui.layout_column_wrap(
                        ui.div(
                            ui.h4("📖 User Manual", style="color: #006994; font-weight: 700; margin-bottom: 0.5rem;"),
                            ui.p("Complete guide covering all features of the application:", style="margin-bottom: 0.5rem;"),
                            ui.tags.ul(
                                ui.tags.li("Data Input and CSV format requirements"),
                                ui.tags.li("EC Features configuration and classification guide"),
                                ui.tags.li("Understanding AQ scores and EV calculation"),
                                ui.tags.li("Physical Accounts (SEEA EA) — extent and supply tables"),
                                ui.tags.li("Visualization and Map features"),
                                ui.tags.li("Excel export formats and contents"),
                                ui.tags.li("Troubleshooting common issues"),
                                ui.tags.li("Complete glossary of terms"),
                                style="line-height: 2; color: #495057;"
                            ),
                            ui.p(
                                "The full user manual is available at: ",
                                ui.code("docs/USER_MANUAL.md"),
                                style="margin-top: 1rem; color: #6c757d; font-size: 0.95rem;"
                            ),
                            style="padding: 1rem;"
                        ),
                        ui.div(
                            ui.h4("⚙️ Version Information", style="color: #006994; font-weight: 700; margin-bottom: 0.5rem;"),
                            ui.p(f"Application Version: ", ui.strong(f"v{APP_VERSION_STR}"), style="margin: 0.3rem 0;"),
                            ui.p(f"EVA Module: v{get_version_info()['eva_module']}", style="margin: 0.3rem 0; color: #6c757d;"),
                            ui.p(f"PA Module: v{get_version_info()['pa_module']}", style="margin: 0.3rem 0; color: #6c757d;"),
                            ui.p(f"Build Date: {get_version_info()['build_date']}", style="margin: 0.3rem 0; color: #6c757d;"),
                            ui.hr(),
                            ui.h5("📋 Recent Changes", style="color: #006994; font-weight: 600; margin-top: 1rem;"),
                            ui.tags.ul(
                                ui.tags.li("Physical Accounts module (SEEA EA)"),
                                ui.tags.li("Critical bug fixes in AQ mapping"),
                                ui.tags.li("XSS security fix"),
                                ui.tags.li("Vectorized EV calculation"),
                                ui.tags.li("Centralized version management"),
                                style="line-height: 1.8; color: #495057; font-size: 0.9rem;"
                            ),
                            ui.p(
                                "Full changelog: ",
                                ui.code("CHANGELOG.md"),
                                style="margin-top: 0.5rem; color: #6c757d; font-size: 0.9rem;"
                            ),
                            style="padding: 1rem; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 8px;"
                        ),
                        width=1/2
                    ),
                    style="padding: 1rem;"
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
        ui.span(f"MARBEFES EVA v{APP_VERSION_STR}", style="font-weight: 700;"),
        style="display: flex; align-items: center;",
        class_="logo-container"
    ),
    id="navbar",
    header=ui.tags.head(
        ui.HTML(custom_css)
    )
)
