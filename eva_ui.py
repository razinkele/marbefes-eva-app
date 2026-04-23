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

    /* ── Left-sidebar navigation layout ────────────────────── */
    html, body { height: 100%; margin: 0; }

    .app-wrapper {
        display: flex;
        flex-direction: column;
        height: 100vh;
        overflow: hidden;
    }

    .app-header {
        background: linear-gradient(135deg, var(--ocean-blue) 0%, var(--accent-teal) 100%);
        color: white;
        padding: 0.3rem 1rem;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        flex-shrink: 0;
        z-index: 100;
    }

    .app-header .app-logo img { height: 28px; }
    .app-header .app-title-group {
        display: flex;
        align-items: baseline;
        gap: 8px;
        flex: 1;
    }
    .app-header .app-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: white;
        margin: 0;
        line-height: 1;
    }
    .app-header .app-subtitle {
        font-size: 0.75rem;
        opacity: 0.85;
        margin: 0;
        font-weight: 400;
        line-height: 1;
    }
    .app-header-actions {
        display: flex;
        align-items: center;
        gap: 4px;
        margin-left: auto;
    }
    .app-header-actions .header-btn {
        background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.25);
        color: white;
        border-radius: 5px;
        padding: 3px 9px;
        font-size: 0.78rem;
        cursor: pointer;
        transition: background 0.2s;
        display: flex;
        align-items: center;
        gap: 4px;
        text-decoration: none;
    }
    .app-header-actions .header-btn:hover {
        background: rgba(255,255,255,0.28);
        color: white;
    }
    /* Help / About / Options modal panels */
    .header-panel-backdrop {
        display: none;
        position: fixed; inset: 0;
        background: rgba(0,0,0,0.35);
        z-index: 1200;
    }
    .header-panel-backdrop.open { display: block; }
    .header-panel {
        position: fixed;
        top: 0; right: 0;
        width: 380px; height: 100%;
        background: #fff;
        box-shadow: -4px 0 20px rgba(0,0,0,0.2);
        z-index: 1201;
        display: flex; flex-direction: column;
        transform: translateX(110%);
        transition: transform 0.25s ease;
    }
    .header-panel.open { transform: translateX(0); }
    .header-panel-title {
        background: linear-gradient(135deg, #004d7a, #006994);
        color: white;
        padding: 12px 16px;
        font-weight: 600;
        font-size: 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .header-panel-close {
        background: none; border: none; color: white;
        font-size: 1.3rem; cursor: pointer; line-height: 1;
    }
    .header-panel-body {
        padding: 16px;
        overflow-y: auto;
        flex: 1;
        font-size: 0.87rem;
        line-height: 1.6;
    }

    .app-body {
        display: flex;
        flex: 1;
        overflow: hidden;
    }

    /* Sidebar */
    .custom-sidebar {
        width: 220px;
        min-width: 220px;
        background: linear-gradient(180deg, #004d7a 0%, #006994 60%, #008b9e 100%);
        display: flex;
        flex-direction: column;
        overflow-y: auto;
        transition: width 0.25s ease, min-width 0.25s ease;
        flex-shrink: 0;
        z-index: 90;
    }

    .custom-sidebar.collapsed {
        width: 52px;
        min-width: 52px;
    }

    .sidebar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.8rem 0.8rem 0.6rem;
        border-bottom: 1px solid rgba(255,255,255,0.15);
    }

    .sidebar-title {
        color: white;
        font-weight: 700;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        opacity: 0.9;
        white-space: nowrap;
        overflow: hidden;
        transition: opacity 0.2s;
    }

    .custom-sidebar.collapsed .sidebar-title { opacity: 0; width: 0; }

    .sidebar-toggle {
        background: transparent;
        border: 1px solid rgba(255,255,255,0.3);
        color: white;
        border-radius: 5px;
        padding: 2px 6px;
        cursor: pointer;
        flex-shrink: 0;
        font-size: 1rem;
        line-height: 1.4;
    }
    .sidebar-toggle:hover { background: rgba(255,255,255,0.15); }

    .sidebar-nav {
        padding: 0.4rem 0;
        flex: 1;
    }

    .custom-sidebar .nav-link {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 0.55rem 0.85rem;
        color: rgba(255,255,255,0.82) !important;
        font-size: 0.88rem;
        font-weight: 500;
        border-radius: 0;
        text-decoration: none;
        white-space: nowrap;
        overflow: hidden;
        transition: background 0.18s, color 0.18s;
    }

    .custom-sidebar .nav-link i {
        font-size: 1.1rem;
        flex-shrink: 0;
        width: 22px;
        text-align: center;
    }

    .custom-sidebar .nav-link span {
        transition: opacity 0.2s;
    }

    .custom-sidebar.collapsed .nav-link span { opacity: 0; width: 0; overflow: hidden; }

    .custom-sidebar .nav-link:hover {
        background: rgba(255,255,255,0.12);
        color: white !important;
    }

    .custom-sidebar .nav-link.active {
        background: rgba(255,255,255,0.22) !important;
        color: white !important;
        font-weight: 600;
        border-left: 3px solid rgba(255,255,255,0.8);
    }

    .sidebar-footer {
        padding: 0.6rem 0.85rem;
        border-top: 1px solid rgba(255,255,255,0.15);
        font-size: 0.72rem;
        color: rgba(255,255,255,0.5);
        white-space: nowrap;
        overflow: hidden;
    }
    .custom-sidebar.collapsed .sidebar-footer { display: none; }

    /* Main content pane */
    .main-content-area {
        flex: 1;
        overflow-y: auto;
        padding: 0;
        background: #f4f6f9;
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
_sidebar_js = """
function initSidebar() {
    const toggleBtn = document.getElementById('sidebar-collapse-btn');
    const sidebar = document.getElementById('custom-sidebar');
    const navLinks = document.querySelectorAll('#custom-sidebar .nav-link[data-nav-id]');

    if (toggleBtn && sidebar) {
        toggleBtn.onclick = function(e) {
            e.stopPropagation();
            sidebar.classList.toggle('collapsed');
        };
    }

    navLinks.forEach(function(link) {
        link.onclick = function(e) {
            e.preventDefault();
            navLinks.forEach(function(l) { l.classList.remove('active'); });
            link.classList.add('active');
            var navId = link.getAttribute('data-nav-id');
            Shiny.setInputValue('navigation', navId, {priority: 'event'});
        };
    });
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSidebar);
} else { initSidebar(); }
setTimeout(initSidebar, 500);
setTimeout(initSidebar, 1500);
"""

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.HTML(custom_css),
        ui.HTML('<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">'),
    ),
    ui.tags.script(_sidebar_js),
    # Hidden navigation state input
    ui.div(
        ui.input_text("navigation", None, value="nav_home"),
        style="display:none;"
    ),
    # Full-page wrapper
    ui.div(
        # ── App header ──────────────────────────────────────────
        ui.div(
            ui.div(
                ui.HTML('<img src="marbefes.png" alt="MARBEFES Logo" style="height: 28px; margin-right: 6px;">'),
                class_="app-logo"
            ),
            ui.div(
                ui.tags.span("MARBEFES EVA", class_="app-title"),
                ui.tags.span(" — Ecological Value Assessment", class_="app-subtitle"),
                class_="app-title-group"
            ),
            # Right-side action buttons
            ui.div(
                ui.HTML('''
                <button class="header-btn" onclick="openPanel('help-panel')">
                  <i class="bi bi-question-circle"></i> Help
                </button>
                <button class="header-btn" onclick="openPanel('about-panel')">
                  <i class="bi bi-info-circle"></i> About
                </button>
                <button class="header-btn" onclick="openPanel('options-panel')">
                  <i class="bi bi-gear"></i> Options
                </button>
                '''),
                class_="app-header-actions"
            ),
            class_="app-header"
        ),
        # ── Help / About / Options slide-in panels ───────────────
        ui.HTML('''
        <div class="header-panel-backdrop" id="panel-backdrop" onclick="closeAllPanels()"></div>

        <div class="header-panel" id="help-panel">
          <div class="header-panel-title">
            <span><i class="bi bi-question-circle"></i> Help</span>
            <button class="header-panel-close" onclick="closeAllPanels()">&times;</button>
          </div>
          <div class="header-panel-body">
            <h5>Getting Started</h5>
            <ol>
              <li><strong>Data Input</strong> — upload a CSV with species occurrence records.</li>
              <li><strong>Grid Setup</strong> — draw or upload a boundary polygon, choose a hex grid resolution, and generate the grid.</li>
              <li><strong>Environmental Covariates</strong> — fetch depth, EUNIS habitat, and substrate data for each cell.</li>
              <li><strong>Copernicus Marine</strong> — fetch SST, salinity, chlorophyll and other physical/biogeochemical variables.</li>
              <li><strong>EVA Calculations</strong> — compute Ecological Value scores per grid cell.</li>
              <li><strong>Physical Accounts</strong> — generate habitat physical accounts and SEEA tables.</li>
              <li><strong>Results &amp; Export</strong> — view maps, charts, and download results as Excel or CSV.</li>
            </ol>
            <h5>Tips</h5>
            <ul>
              <li>Use the <em>Grid Setup</em> map to visually verify your study area before fetching data.</li>
              <li>EUNIS and CMEMS data fetching can take several minutes for large areas.</li>
              <li>All downloaded results include metadata columns for reproducibility.</li>
            </ul>
          </div>
        </div>

        <div class="header-panel" id="about-panel">
          <div class="header-panel-title">
            <span><i class="bi bi-info-circle"></i> About</span>
            <button class="header-panel-close" onclick="closeAllPanels()">&times;</button>
          </div>
          <div class="header-panel-body">
            <p><strong>MARBEFES EVA</strong> is an open-source tool for Ecological Value Assessment of marine areas, developed within the <strong>MARBEFES</strong> Horizon Europe project (Grant No. 101059877).</p>
            <p>It combines species occurrence data with environmental covariates (bathymetry, EUNIS habitat classification, Copernicus Marine physical and biogeochemical variables) on a hexagonal grid to produce spatially explicit ecological value scores and habitat physical accounts.</p>
            <hr>
            <p><strong>Developed by:</strong></p>
            <p style="margin-bottom:4px;">
              Marine Research Institute, Klaipėda University<br>
              <a href="mailto:arturas.razinkovas-baziukas@ku.lt">arturas.razinkovas-baziukas@ku.lt</a>
            </p>
            <p style="margin-bottom:4px;">
              International Estuarine &amp; Coastal Specialists Ltd. (IECS)<br>
              Anita Franco, PhD AFHEA — Director<br>
              <a href="mailto:Anita.Franco@iecs.ltd">Anita.Franco@iecs.ltd</a>
            </p>
            <p><strong>Source code:</strong><br><a href="https://github.com/razinkele/EVA-Algorithms" target="_blank">github.com/razinkele/EVA-Algorithms</a></p>
            <hr>
            <p style="font-size:0.8rem; color:#666;">MARBEFES is funded by the European Union under Horizon Europe. Views and opinions expressed are those of the authors only and do not necessarily reflect those of the European Union.</p>
          </div>
        </div>

        <div class="header-panel" id="options-panel">
          <div class="header-panel-title">
            <span><i class="bi bi-gear"></i> Options</span>
            <button class="header-panel-close" onclick="closeAllPanels()">&times;</button>
          </div>
          <div class="header-panel-body">
            <h5>Display</h5>
            <div style="margin-bottom:12px;">
              <label style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                <input type="checkbox" id="opt-dark-mode" onchange="toggleDarkMode(this.checked)">
                Dark sidebar
              </label>
            </div>
            <h5>Data Sources</h5>
            <p style="color:#555;">EMODnet WMS endpoint:<br>
              <code style="font-size:0.75rem;">emodnet-seabedhabitats.eu</code>
            </p>
            <p style="color:#555;">Copernicus Marine Service:<br>
              <code style="font-size:0.75rem;">marine.copernicus.eu</code>
            </p>
            <h5>Cache</h5>
            <p style="color:#555; font-size:0.82rem;">WMS tile responses are cached in memory for the current session. Restart the app to clear the cache.</p>
          </div>
        </div>

        <script>
        function openPanel(id) {
          document.getElementById("panel-backdrop").classList.add("open");
          document.getElementById(id).classList.add("open");
        }
        function closeAllPanels() {
          document.getElementById("panel-backdrop").classList.remove("open");
          document.querySelectorAll(".header-panel").forEach(function(p){ p.classList.remove("open"); });
        }
        function toggleDarkMode(on) {
          document.getElementById("custom-sidebar").style.filter = on ? "brightness(0.75)" : "";
        }
        </script>
        '''),
        # ── Body: sidebar + main ────────────────────────────────
        ui.div(
            # Left sidebar navigation
            ui.div(
                {"id": "custom-sidebar"},
                ui.div(
                    ui.tags.span("Navigation", class_="sidebar-title"),
                    ui.tags.button(
                        ui.tags.i(class_="bi bi-list"),
                        id="sidebar-collapse-btn",
                        class_="sidebar-toggle",
                        type="button",
                    ),
                    class_="sidebar-header"
                ),
                ui.div(
                    ui.tags.a(
                        {"class": "nav-link active",
                         "href": "#",
                         "data-nav-id": "nav_home"},
                        ui.tags.i(class_="bi bi-house-fill"),
                        ui.tags.span("Home")
                    ),
                    ui.tags.a(
                        {"class": "nav-link",
                         "href": "#",
                         "data-nav-id": "nav_grid"},
                        ui.tags.i(class_="bi bi-grid-3x3"),
                        ui.tags.span("Grid Setup")
                    ),
                    ui.tags.a(
                        {"class": "nav-link",
                         "href": "#",
                         "data-nav-id": "nav_sdm"},
                        ui.tags.i(class_="bi bi-graph-up-arrow"),
                        ui.tags.span("Species Distribution")
                    ),
                    ui.tags.a(
                        {"class": "nav-link",
                         "href": "#",
                         "data-nav-id": "nav_data"},
                        ui.tags.i(class_="bi bi-upload"),
                        ui.tags.span("Data Input")
                    ),
                    ui.tags.a(
                        {"class": "nav-link",
                         "href": "#",
                         "data-nav-id": "nav_features"},
                        ui.tags.i(class_="bi bi-sliders"),
                        ui.tags.span("EC Features")
                    ),
                    ui.tags.a(
                        {"class": "nav-link",
                         "href": "#",
                         "data-nav-id": "nav_results"},
                        ui.tags.i(class_="bi bi-bar-chart-fill"),
                        ui.tags.span("AQ + EV Results")
                    ),
                    ui.tags.a(
                        {"class": "nav-link",
                         "href": "#",
                         "data-nav-id": "nav_ev"},
                        ui.tags.i(class_="bi bi-trophy-fill"),
                        ui.tags.span("Total EV")
                    ),
                    ui.tags.a(
                        {"class": "nav-link",
                         "href": "#",
                         "data-nav-id": "nav_viz"},
                        ui.tags.i(class_="bi bi-graph-up"),
                        ui.tags.span("Visualization")
                    ),
                    ui.tags.a(
                        {"class": "nav-link",
                         "href": "#",
                         "data-nav-id": "nav_map"},
                        ui.tags.i(class_="bi bi-map-fill"),
                        ui.tags.span("Map")
                    ),
                    ui.tags.a(
                        {"class": "nav-link",
                         "href": "#",
                         "data-nav-id": "nav_pa"},
                        ui.tags.i(class_="bi bi-receipt"),
                        ui.tags.span("Physical Accounts")
                    ),
                    ui.tags.a(
                        {"class": "nav-link",
                         "href": "#",
                         "data-nav-id": "nav_help"},
                        ui.tags.i(class_="bi bi-question-circle-fill"),
                        ui.tags.span("Help & Method")
                    ),
                    class_="sidebar-nav"
                ),
                ui.div(f"v{APP_VERSION_STR}", class_="sidebar-footer"),
                class_="custom-sidebar"
            ),
            # Main content area with conditional panels
            ui.div(
                ui.panel_conditional(
                    "input.navigation === 'nav_home'",
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
        ),
                ),
                ui.panel_conditional(
                    "input.navigation === 'nav_grid'",
        ui.layout_sidebar(
            ui.sidebar(
                ui.output_ui("grid_status_output"),
                ui.accordion(
                    ui.accordion_panel(
                        "1. Define Study Area",
                        ui.tooltip(
                            ui.input_select(
                                "bbt_coverage",
                                "BBT Coverage:",
                                choices={"": "— Custom (upload / draw) —",
                                    "Archipelago":    "Archipelago Sea (Finland)",
                                    "Balearic":       "Balearic Sea (Spain)",
                                    "Bay_of_Gdansk":  "Bay of Gdańsk (Poland)",
                                    "BayOfBiscay":    "Bay of Biscay (Spain)",
                                    "Heraklion":      "Heraklion (Greece / Crete)",
                                    "Hornsund":       "Hornsund (Svalbard, Norway)",
                                    "Irish_sea":      "Irish Sea (UK/Ireland)",
                                    "Kongsfiord":     "Kongsfjord (Svalbard, Norway)",
                                    "Lithuanian":     "Lithuanian Coast (Baltic Sea)",
                                    "North_Sea":      "North Sea (Belgium/Netherlands)",
                                    "Porsangerfjord": "Porsangerfjord (Norway)",
                                    "Sardinia":       "Sardinia / Gulf of Oristano (Italy)",
                                },
                                selected="",
                            ),
                            "Select a MARBEFES Biodiversity Benchmark Territory (BBT) to use as the study area boundary, "
                            "or choose Custom to upload your own polygon or draw it on the map.",
                            placement="right",
                        ),
                        ui.panel_conditional(
                            "input.bbt_coverage === ''",
                            ui.tooltip(
                                ui.input_radio_buttons(
                                    "polygon_source",
                                    "Polygon source:",
                                    choices={"upload": "Upload boundary file", "draw": "Draw on map"},
                                    selected="upload",
                                ),
                                "Upload a polygon file or draw a shape on the map to define the study area.",
                                placement="right",
                            ),
                            ui.panel_conditional(
                                "input.polygon_source === 'upload'",
                                ui.tooltip(
                                    ui.input_file(
                                        "upload_boundary",
                                        "Choose Boundary File",
                                        accept=[".geojson", ".json", ".zip", ".gpkg"],
                                        multiple=False,
                                        button_label="Browse...",
                                    ),
                                    "Supported formats: GeoJSON (.geojson/.json), Zipped Shapefile (.zip), "
                                    "GeoPackage (.gpkg). Any CRS is accepted — files are reprojected to WGS84 automatically.",
                                    placement="right",
                                ),
                            ),
                            ui.panel_conditional(
                                "input.polygon_source === 'draw'",
                                ui.p(
                                    "Use the ◻ rectangle or ⬠ polygon draw tools on the map.",
                                    style="font-size: 0.8rem; color: #6c757d; margin-top: 0.4rem;",
                                ),
                            ),
                        ),
                    ),
                    ui.accordion_panel(
                        "2. Grid Parameters",
                        ui.tooltip(
                            ui.input_select(
                                "hex_preset",
                                "Hexagon size:",
                                choices={k: v["label"] for k, v in HEX_PRESETS.items()},
                                selected="mobile",
                            ),
                            "EVA Guidance Table 2.1 — ~250 m: benthic ECs (macrobenthos, epibenthos, habitats); "
                            "~3 km: mobile ECs (seabirds, fish, mammals, plankton). "
                            "Nest smaller grids inside larger ones when combining ECs.",
                            placement="right",
                        ),
                    ),
                    ui.accordion_panel(
                        "3. Generate",
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
                            "Load this grid into the EVA pipeline as spatial assessment units (subzones). "
                            "Then go to Data Input and upload a CSV with a 'Subzone ID' column matching the grid cell IDs (HEX_001, HEX_002, …).",
                            placement="right",
                        ),
                    ),
                    ui.accordion_panel(
                        "4. Environmental Covariates",
                        ui.p(
                            "Enrich each hexagon with habitat and environmental data for "
                            "Physical Accounts and Species Distribution Modelling (SDM). "
                            "EUNIS L3 is required for Physical Accounts.",
                            style="font-size: 0.8rem; color: #6c757d; margin-bottom: 0.75rem;",
                        ),
                        ui.input_radio_buttons(
                            "eunis_source",
                            "Data source:",
                            choices={
                                "auto": "EMODnet online services (automatic)",
                                "upload": "Upload custom habitat map",
                            },
                            selected="auto",
                        ),
                        ui.panel_conditional(
                            "input.eunis_source === 'auto'",
                            ui.div(
                                ui.HTML("<b>📡 Select layers to fetch:</b>"),
                                style="font-size: 0.82rem; font-weight: 600; margin-bottom: 0.4rem;",
                            ),
                            ui.input_checkbox_group(
                                "sdm_layers",
                                None,
                                choices={
                                    "eunis2007": "🌿 EUNIS 2007 L3 habitat (EuSEAMAP 2025) — for PA",
                                    "eunis2019": "🌿 EUNIS 2019 L3 habitat (EuSEAMAP 2025)",
                                    "substrate": "🪨 Seabed substrate type (rock/sand/mud/gravel)",
                                    "energy":    "🌊 Energy class (wave/current exposure)",
                                    "biozone":   "🔵 Biological zone (infralittoral/circalittoral/…)",
                                    "helcom":    "🇸🇪 HELCOM HUB class (Baltic Sea)",
                                    "depth":     "📏 Water depth — EMODnet Bathymetry WCS",
                                },
                                selected=["eunis2007", "substrate", "energy", "depth"],
                            ),
                            ui.div(
                                ui.HTML(
                                    "All EuSEAMAP layers share one WMS on "
                                    "<em>emodnet-seabedhabitats.eu</em>. Depth uses the "
                                    "EMODnet Bathymetry WCS (~1 MB download). "
                                    "Requires internet access. Near-shore hexagons may lack data."
                                ),
                                style=(
                                    "font-size: 0.75rem; color: #555; background: #f0f7ff; "
                                    "border-left: 3px solid #006994; border-radius: 4px; "
                                    "padding: 0.4rem 0.6rem; margin-bottom: 0.5rem;"
                                ),
                            ),
                            ui.tooltip(
                                ui.input_action_button(
                                    "fetch_eunis",
                                    "🌊 Fetch Selected Layers",
                                    class_="btn-info",
                                    style="width: 100%; margin-bottom: 0.4rem; color: white;",
                                ),
                                "Downloads the selected EMODnet layers and annotates each hexagon "
                                "by sampling at the centroid. EUNIS L3 result is automatically "
                                "loaded into Physical Accounts. A grid must be generated first.",
                                placement="right",
                            ),
                        ),
                        ui.panel_conditional(
                            "input.eunis_source === 'upload'",
                            ui.input_file(
                                "upload_habitat_source",
                                "Upload habitat polygon layer:",
                                accept=[".gpkg", ".geojson", ".json", ".zip"],
                                multiple=False,
                                button_label="Browse...",
                            ),
                            ui.p(
                                "GeoPackage (.gpkg), GeoJSON, or zipped Shapefile/FileGDB. "
                                "Must contain an 'EUNIScomb' column. Any CRS is auto-reprojected.",
                                style="font-size: 0.78rem; color: #6c757d; margin-top: 0.3rem;",
                            ),
                        ),
                        ui.output_ui("eunis_grid_status"),
                        ui.tooltip(
                            ui.download_button(
                                "download_eunis_overlay",
                                "Download EUNIS Overlay (.gpkg)",
                                class_="btn-outline-secondary",
                                style="width: 100%; margin-top: 0.3rem;",
                            ),
                            "Download EUNIS L3 annotation as GeoPackage for Physical Accounts.",
                            placement="right",
                        ),
                        ui.tooltip(
                            ui.download_button(
                                "download_sdm_covariates",
                                "Download SDM Covariates (.csv)",
                                class_="btn-outline-secondary",
                                style="width: 100%; margin-top: 0.3rem;",
                            ),
                            "Download all fetched environmental covariates as CSV for use in "
                            "species distribution models (MaxEnt, BRT, Random Forest, etc.).",
                            placement="right",
                        ),
                    ),
                    ui.accordion_panel(
                        "5. Copernicus Marine",
                        ui.p(
                            "Fetch climatological oceanographic variables for each hexagon "
                            "from the Copernicus Marine Service (CMEMS). Requires a free "
                            "account at ",
                            ui.tags.a(
                                "marine.copernicus.eu",
                                href="https://marine.copernicus.eu",
                                target="_blank",
                            ),
                            ".",
                            style="font-size: 0.8rem; color: #6c757d; margin-bottom: 0.75rem;",
                        ),
                        ui.div(
                            ui.HTML("<b>🔑 Credentials</b>"),
                            style="font-size: 0.82rem; font-weight: 600; margin-bottom: 0.3rem;",
                        ),
                        ui.input_text(
                            "cmems_username",
                            None,
                            placeholder="Username (or set env var COPERNICUSMARINE_SERVICE_USERNAME)",
                            width="100%",
                        ),
                        ui.input_password(
                            "cmems_password",
                            None,
                            placeholder="Password (or set env var COPERNICUSMARINE_SERVICE_PASSWORD)",
                            width="100%",
                        ),
                        ui.div(
                            ui.HTML("<b>📅 BGC averaging period</b>"),
                            style="font-size: 0.82rem; font-weight: 600; margin: 0.5rem 0 0.3rem;",
                        ),
                        ui.layout_columns(
                            ui.input_numeric("cmems_start_year", "From", value=2016, min=1993, max=2023, step=1),
                            ui.input_numeric("cmems_end_year",   "To",   value=2020, min=1993, max=2023, step=1),
                            col_widths=[6, 6],
                        ),
                        ui.div(
                            ui.HTML("<b>📡 Select variables to fetch:</b>"),
                            style="font-size: 0.82rem; font-weight: 600; margin: 0.5rem 0 0.3rem;",
                        ),
                        ui.input_checkbox_group(
                            "cmems_layers",
                            None,
                            choices={
                                "sst":           "🌡️ Sea Surface Temperature (SST)",
                                "bottom_temp":   "🌡️ Bottom Temperature",
                                "salinity":      "🧂 Sea Surface Salinity (SSS)",
                                "mld":           "📏 Mixed Layer Depth (MLD)",
                                "current_speed": "🌊 Surface Current Speed",
                                "chlorophyll":   "🟢 Chlorophyll-a (Chl-a)",
                                "oxygen":        "💧 Dissolved Oxygen (O₂)",
                                "nitrate":       "⚗️ Nitrate (NO₃)",
                                "ph":            "🧪 Sea Water pH",
                                "npp":           "🌱 Net Primary Production",
                            },
                            selected=["sst", "salinity", "chlorophyll"],
                        ),
                        ui.div(
                            ui.HTML(
                                "Physics variables (SST, salinity, MLD, currents, bottom temp) use the "
                                "<em>GLORYS12V1 monthly climatology</em> (1993–2020 baseline). "
                                "Biogeochemistry variables (Chl-a, O₂, NO₃, pH, NPP) use the "
                                "<em>PISCES monthly hindcast</em> averaged over the selected period."
                            ),
                            style=(
                                "font-size: 0.75rem; color: #555; background: #f0f7ff; "
                                "border-left: 3px solid #006994; border-radius: 4px; "
                                "padding: 0.4rem 0.6rem; margin-bottom: 0.5rem;"
                            ),
                        ),
                        ui.tooltip(
                            ui.input_action_button(
                                "fetch_cmems",
                                "🛰️ Fetch CMEMS Variables",
                                class_="btn-primary",
                                style="width: 100%; margin-bottom: 0.3rem; color: white;",
                            ),
                            "Downloads selected Copernicus Marine variables and annotates each "
                            "hexagon by sampling at the centroid. Data is added to the SDM "
                            "covariates table and can be exported with the button above.",
                            placement="right",
                        ),
                        ui.output_ui("cmems_status"),
                    ),
                    id="grid_setup_accordion",
                    open=["1. Define Study Area", "2. Grid Parameters", "3. Generate"],
                    multiple=True,
                ),
                width=380,
            ),
            ui.div(
                ui.output_ui("map_layer_selector_ui"),
                ui.output_ui("unified_map_output"),
                class_="main-content",
            ),
        ),
                ),
                ui.panel_conditional(
                    "input.navigation === 'nav_data'",
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
                                    "Subzone ID, Habitat1, Habitat2, Habitat3, ...\n"
                                    "A0, 1, 0, 1, ...\n"
                                    "A1, 0, 1, 0, ...\n"
                                    "A2, 1, 1, 0, ...",
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
        ),
                ),
                ui.panel_conditional(
                    "input.navigation === 'nav_features'",
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
        ),
                ),
                ui.panel_conditional(
                    "input.navigation === 'nav_results'",
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
        ),
                ),
                ui.panel_conditional(
                    "input.navigation === 'nav_ev'",
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
        ),
                ),
                ui.panel_conditional(
                    "input.navigation === 'nav_viz'",
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
        ),
                ),
                ui.panel_conditional(
                    "input.navigation === 'nav_map'",
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
        ),
                ),
                ui.panel_conditional(
                    "input.navigation === 'nav_pa'",
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
                    ui.download_button("pa_download_bbt8_docx", "📝 Download BBT8 Report (Word)", class_="btn-outline-primary", style="width: 100%; margin-top: 0.5rem;"),
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
        ),
                ),
                ui.panel_conditional(
                    "input.navigation === 'nav_sdm'",
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5("Species Distribution Modelling", style="color:#006994;font-weight:700;margin-bottom:1rem;"),

                # Prerequisites status
                ui.output_ui("sdm_prereq_status"),

                ui.hr(),

                # ── Sampling Data Source ─────────────────────────────────────
                ui.h6("Sampling Data", style="font-weight:600;"),
                ui.input_radio_buttons(
                    "sdm_data_source", None,
                    choices={
                        "csv":   "📊 Use uploaded CSV",
                        "dwca":  "🦋 Upload Darwin Core Archive",
                    },
                    selected="csv",
                ),
                ui.panel_conditional(
                    "input.sdm_data_source === 'dwca'",
                    ui.input_file(
                        "sdm_dwca_file",
                        "DwC-A zip file (.zip)",
                        accept=[".zip"],
                        multiple=False,
                        width="100%",
                    ),
                    ui.input_radio_buttons(
                        "sdm_dwca_value", "Values to extract",
                        choices={
                            "auto":      "Auto (abundance if available)",
                            "abundance": "Abundance (individualCount)",
                            "presence":  "Presence/Absence (0/1)",
                        },
                        selected="auto",
                    ),
                    ui.output_ui("sdm_dwca_status"),
                ),

                ui.hr(),

                # Response variable
                ui.h6("Response Variable", style="font-weight:600;"),
                ui.input_select("sdm_response_col", "Column with species data",
                                choices=[], width="100%"),
                ui.input_radio_buttons("sdm_response_type", "Response type",
                    choices={"continuous": "Abundance / continuous",
                             "binary":     "Presence/Absence (0/1)",
                             "count":      "Count"},
                    selected="continuous"),

                ui.hr(),

                # Predictor variables
                ui.h6("Environmental Predictors", style="font-weight:600;"),
                ui.p("Select covariates fetched in Grid Setup:",
                     style="font-size:0.8rem;color:#666;margin-bottom:4px;"),
                ui.output_ui("sdm_predictor_checkboxes"),

                ui.hr(),

                # Method
                ui.h6("Modelling Method", style="font-weight:600;"),
                ui.input_radio_buttons("sdm_method", None,
                    choices={
                        "ensemble":          "🔀 Ensemble (recommended)",
                        "regression_kriging":"⭐ Regression Kriging (RF + OK)",
                        "xgboost":           "⚡ XGBoost",
                        "lightgbm":          "💡 LightGBM",
                        "rf":                "🌲 Random Forest",
                        "kriging":           "🌐 Ordinary Kriging",
                        "gp":                "🔮 Gaussian Process",
                        "gam":               "📈 GAM only",
                        "idw":               "📍 IDW only",
                    },
                    selected="ensemble"),

                # Kriging options (shown for kriging/regression_kriging)
                ui.panel_conditional(
                    "['kriging','regression_kriging','ensemble'].includes(input.sdm_method)",
                    ui.tags.details(
                        ui.tags.summary("Kriging options",
                                        style="font-size:0.82rem;cursor:pointer;color:#006994;margin-top:4px;"),
                        ui.input_select("sdm_variogram_model", "Variogram model",
                            choices={"spherical": "Spherical", "gaussian": "Gaussian",
                                     "exponential": "Exponential",
                                     "linear": "Linear", "power": "Power"},
                            selected="spherical", width="100%"),
                        ui.input_checkbox("sdm_show_uncertainty",
                                          "Show uncertainty map", value=True),
                    ),
                ),

                # Advanced options (collapsible)
                ui.tags.details(
                    ui.tags.summary("Advanced options",
                                    style="font-size:0.82rem;cursor:pointer;color:#006994;"),
                    ui.input_numeric("sdm_idw_power", "IDW power", value=2.0,
                                     min=0.5, max=5.0, step=0.5, width="100%"),
                    ui.input_numeric("sdm_gam_splines", "GAM splines per term", value=10,
                                     min=4, max=20, step=1, width="100%"),
                    ui.input_numeric("sdm_rf_trees", "RF: number of trees", value=200,
                                     min=50, max=1000, step=50, width="100%"),
                    ui.input_slider("sdm_ensemble_weight", "GAM weight in ensemble",
                                    min=0.0, max=1.0, value=0.5, step=0.1, width="100%"),
                ),

                ui.hr(),

                # Column lat/lon overrides
                ui.h6("Sampling site columns", style="font-weight:600;"),
                ui.input_text("sdm_lat_col", "Latitude column", value="lat", width="100%"),
                ui.input_text("sdm_lon_col", "Longitude column", value="lon", width="100%"),

                ui.hr(),
                ui.input_action_button("sdm_analyse_btn", "🔬 Analyse Predictors",
                                       class_="btn btn-info w-100 mb-2",
                                       icon=ui.tags.i(class_="bi bi-bar-chart-line")),
                ui.input_action_button("sdm_fit_btn", "Fit & Predict",
                                       class_="btn btn-success w-100",
                                       icon=ui.tags.i(class_="bi bi-play-fill")),
                ui.br(),
                ui.output_ui("sdm_fit_status"),
                ui.output_ui("sdm_analyse_status"),

                width=310,
            ),
            # Main content — map + diagnostics
            ui.div(
                # CSS for compact SDM tabs
                ui.tags.style("""
                    #sdm_tabs .nav-tabs { flex-wrap: wrap; gap: 2px 0; }
                    #sdm_tabs .nav-tabs .nav-link {
                        font-size: 0.78rem; padding: 0.35rem 0.6rem;
                        white-space: nowrap;
                    }
                    #sdm_tabs .nav-tabs .nav-link.active {
                        font-weight: 600; border-bottom: 2px solid #006994;
                        color: #006994;
                    }
                """),
                ui.div(
                    ui.navset_tab(
                        ui.nav_panel("📋 Data",
                            ui.div(
                                ui.output_ui("sdm_data_analysis"),
                                style="padding:0.5rem;max-height:calc(100vh - 200px);overflow-y:auto;"
                            ),
                        ),
                        ui.nav_panel("🔬 Predictors",
                            ui.div(
                                ui.output_ui("sdm_predictor_analysis"),
                                style="padding:0.5rem;max-height:calc(100vh - 200px);overflow-y:auto;"
                            ),
                        ),
                        ui.nav_panel("🗺️ Map",
                            ui.output_ui("sdm_map_output"),
                        ),
                        ui.nav_panel("🎯 Uncertainty",
                            ui.div(
                                ui.p("Kriging variance or GP standard deviation — "
                                     "lower values indicate more confident predictions.",
                                     style="font-size:0.82rem;color:#666;padding:0.5rem 1rem 0;"),
                                ui.output_ui("sdm_uncertainty_map_output"),
                            ),
                        ),
                        ui.nav_panel("📊 Diagnostics",
                            ui.div(
                                ui.output_ui("sdm_diagnostics_output"),
                                style="padding:1rem;"
                            ),
                        ),
                        ui.nav_panel("📉 Variogram",
                            ui.div(
                                ui.p("Empirical and fitted variogram for Kriging-based methods.",
                                     style="font-size:0.82rem;color:#666;padding:0.5rem 1rem 0;"),
                                ui.output_ui("sdm_variogram_output"),
                                style="padding:0.5rem;"
                            ),
                        ),
                        ui.nav_panel("📋 GAM Effects",
                            ui.div(
                                ui.output_ui("sdm_partial_effects_output"),
                                style="padding:1rem;"
                            ),
                        ),
                        id="sdm_tabs",
                    ),
                    style="height:100%;"
                ),
                style="height:100%;"
            ),
        )
                ),
                ui.panel_conditional(
                    "input.navigation === 'nav_help'",
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
        ),
                ),
                class_="main-content-area"
            ),
            class_="app-body"
        ),
        class_="app-wrapper"
    ),
    title=f"MARBEFES EVA v{APP_VERSION_STR}",
)
