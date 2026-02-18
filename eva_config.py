"""
MARBEFES EVA Configuration Module

All application constants, reference data, and metadata used across the
EVA application.  Extracted from app.py to keep a single source of truth.
"""

# ---------------------------------------------------------------------------
# Application version
# ---------------------------------------------------------------------------
APP_VERSION = '2.1.2'

# ---------------------------------------------------------------------------
# Calculation constants
# ---------------------------------------------------------------------------
MAX_FEATURES = 100                # Maximum number of features allowed
LOCALLY_RARE_THRESHOLD = 0.05     # 5% threshold for locally rare features
PERCENTILE_95 = 95                # 95th percentile for concentration calculations
MAX_EV_SCALE = 5                  # Maximum value on the EV scale (0-5)
PREVIEW_ROWS_LIMIT = 10           # Number of rows to show in data preview
RESULTS_DISPLAY_LIMIT = 20        # Number of results to display in tables
MAX_FILE_SIZE_MB = 50             # Maximum file size for uploads in MB

# ---------------------------------------------------------------------------
# Assessment Question (AQ) lists
# ---------------------------------------------------------------------------
QUALITATIVE_AQS = ['AQ1', 'AQ3', 'AQ5', 'AQ7', 'AQ10', 'AQ12', 'AQ14']
QUANTITATIVE_AQS = ['AQ2', 'AQ4', 'AQ6', 'AQ8', 'AQ9', 'AQ11', 'AQ13', 'AQ15']
ALL_AQS = [f'AQ{i}' for i in range(1, 16)]

# ---------------------------------------------------------------------------
# AQ tooltips  (used in results table headers)
# ---------------------------------------------------------------------------
AQ_TOOLTIPS = {
    "AQ1": "Locally Rare Features (LRF) - Qualitative | Average of rescaled values for features in \u22645% of subzones | Returns NaN when no features are locally rare",
    "AQ2": "Locally Rare Features (LRF) - Quantitative | Average abundance of locally rare features | Returns NaN for qualitative data or when no LRF exist",
    "AQ3": "Regionally Rare Features (RRF) - Qualitative | Average of rescaled values for RRF-classified features | Returns NaN when no RRF features defined",
    "AQ4": "Regionally Rare Features (RRF) - Quantitative | Average abundance of regionally rare features | Returns NaN for qualitative data or no RRF",
    "AQ5": "Nationally Rare Features (NRF) - Qualitative | Average of rescaled values for NRF features | Highest rarity classification",
    "AQ6": "Nationally Rare Features (NRF) - Quantitative | Average abundance of nationally rare features | Returns NaN for qualitative data or no NRF",
    "AQ7": "All Features - Qualitative \u2b50 | Average of ALL features (no filter) | ALWAYS ACTIVE for qualitative data",
    "AQ8": "Regularly Occurring Features (ROF) - Quantitative | Average abundance of features in >5% of subzones | Returns NaN for qualitative data",
    "AQ9": "ROF Concentration-Weighted - Quantitative \U0001f52c | Complex 3-step calculation considering spatial concentration | Identifies hotspots",
    "AQ10": "Ecologically Significant Features (ESF) - Qualitative | Keystone species, ecosystem engineers | Returns NaN when no ESF defined",
    "AQ11": "Ecologically Significant Features (ESF) - Quantitative | Abundance of ecologically significant features | Returns NaN for qualitative or no ESF",
    "AQ12": "Habitat Forming Species/Biogenic Habitat (HFS/BH) - Qualitative | Features creating habitat structure (corals, seagrasses, etc.) | Returns NaN when no HFS/BH defined",
    "AQ13": "Habitat Forming Species/Biogenic Habitat (HFS/BH) - Quantitative | Extent of habitat-forming features | Returns NaN for qualitative or no HFS/BH",
    "AQ14": "Symbiotic Species (SS) - Qualitative | Species in symbiotic relationships | Returns NaN when no SS defined",
    "AQ15": "Symbiotic Species (SS) - Quantitative | Abundance of symbiotic species | Returns NaN for qualitative or no SS",
    "EV": "Ecological Value | MAX of applicable AQs (not average!) | Qualitative: MAX(AQ1,3,5,7,10,12,14) | Quantitative: MAX(AQ2,4,6,8,9,11,13,15)",
}

# ---------------------------------------------------------------------------
# AQ methodology reference  (exported to the Excel "AQ Methodology" sheet)
# ---------------------------------------------------------------------------
AQ_METHODOLOGY = {
    'AQ': ['AQ1', 'AQ2', 'AQ3', 'AQ4', 'AQ5', 'AQ6', 'AQ7', 'AQ8', 'AQ9',
           'AQ10', 'AQ11', 'AQ12', 'AQ13', 'AQ14', 'AQ15'],
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
        'Symbiotic Species (SS) - Quantitative',
    ],
    'Description': [
        'Features present in \u22645% of subzones',
        'Abundance of features in \u22645% of subzones',
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
        'Abundance of symbiotic species',
    ],
    'Data Type': [
        'Qualitative', 'Quantitative', 'Qualitative', 'Quantitative',
        'Qualitative', 'Quantitative', 'Qualitative', 'Quantitative',
        'Quantitative', 'Qualitative', 'Quantitative', 'Qualitative',
        'Quantitative', 'Qualitative', 'Quantitative',
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
        'Qualitative data or no SS',
    ],
}

# ---------------------------------------------------------------------------
# EV calculation explanation  (exported to the Excel "EV Calculation" sheet)
# ---------------------------------------------------------------------------
EV_EXPLANATION = {
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
    ],
}

# ---------------------------------------------------------------------------
# Acronyms reference table
# ---------------------------------------------------------------------------
ACRONYMS = {
    "Acronym": [
        "EVA", "EV", "EC", "AQ", "LRF", "RRF",
        "NRF", "ROF", "ESF", "HFS", "BH", "SS",
    ],
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
        "Symbiotic species",
    ],
}

# ---------------------------------------------------------------------------
# Feature classification badge colours  (used in the features config UI)
# ---------------------------------------------------------------------------
CLASSIFICATION_BADGE_COLORS = {
    'RRF': '#e91e63',
    'NRF': '#9c27b0',
    'ESF': '#2196F3',
    'HFS_BH': '#4caf50',
    'SS': '#ff9800',
}

# ---------------------------------------------------------------------------
# Map constants
# ---------------------------------------------------------------------------
EVA_5CLASS_BINS = [0, 1, 2, 3, 4, 5]
EVA_5CLASS_COLORS = ['#3288bd', '#99d594', '#e6f598', '#fc8d59', '#d53e4f']
EVA_5CLASS_LABELS = [
    'Very Low (0-1)', 'Low (1-2)', 'Medium (2-3)',
    'High (3-4)', 'Very High (4-5)',
]

BASEMAP_TILES = {
    "CartoDB Positron": "cartodbpositron",
    "OpenStreetMap": "openstreetmap",
    "CartoDB Dark Matter": "cartodbdark_matter",
}

# ---------------------------------------------------------------------------
# Export styling constants
# ---------------------------------------------------------------------------
EXPORT_HEADER_COLOR = "006994"
EXPORT_ALT_ROW_COLOR = "F2F2F2"

EXPORT_TAB_COLORS = {
    'Summary & Metadata': '006994',
    'Original Data': '28A745',
    'AQ & EV Results': 'FD7E14',
    'Feature Classifications': '28A745',
    'AQ Methodology': '6C757D',
    'EV Calculation': '6C757D',
    'Complete Results': 'FD7E14',
}

EXPORT_MULTI_EC_TAB_COLOR = '6F42C1'
EXPORT_CHART_TAB_COLOR = 'FD7E14'
