# Modularization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract pure (non-reactive) logic from the 3,600-line `app.py` into 3 standalone modules: `eva_config.py`, `eva_calculations.py`, and `eva_export.py`.

**Architecture:** Move constants, calculation functions, and export logic into importable modules. The Shiny reactive layer stays in `app.py`. Each extracted function is replaced by an import + call. No behavioral changes — the app works identically after extraction.

**Tech Stack:** Python, pandas, numpy, openpyxl, plotly.io

---

### Task 1: Create `eva_config.py` with all constants and metadata

**Files:**
- Create: `eva_config.py`
- Modify: `app.py`

**Step 1: Create `eva_config.py`**

Create the file with all constants currently scattered across `app.py`:

```python
"""
MARBEFES EVA Configuration — constants, metadata, and reference data.
"""

# === Calculation Constants ===
MAX_FEATURES = 100
LOCALLY_RARE_THRESHOLD = 0.05  # 5% threshold for locally rare features
PERCENTILE_95 = 95  # 95th percentile for concentration calculations
MAX_EV_SCALE = 5  # Maximum value on the EV scale (0-5)

# === UI Constants ===
PREVIEW_ROWS_LIMIT = 10
RESULTS_DISPLAY_LIMIT = 20
MAX_FILE_SIZE_MB = 50

# === AQ Metadata ===
QUALITATIVE_AQS = ['AQ1', 'AQ3', 'AQ5', 'AQ7', 'AQ10', 'AQ12', 'AQ14']
QUANTITATIVE_AQS = ['AQ2', 'AQ4', 'AQ6', 'AQ8', 'AQ9', 'AQ11', 'AQ13', 'AQ15']
ALL_AQS = [f'AQ{i}' for i in range(1, 16)]

# === AQ Tooltips ===
AQ_TOOLTIPS = {
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
    "EV": "Ecological Value | MAX of applicable AQs (not average!) | Qualitative: MAX(AQ1,3,5,7,10,12,14) | Quantitative: MAX(AQ2,4,6,8,9,11,13,15)",
}

# === AQ Methodology Reference Data ===
AQ_METHODOLOGY = {
    'AQ': ALL_AQS,
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

# === Acronyms Reference ===
ACRONYMS = {
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
        "Symbiotic species",
    ],
}

# === Classification Badge Colors ===
CLASSIFICATION_COLORS = {
    'RRF': '#e91e63',
    'NRF': '#9c27b0',
    'ESF': '#2196F3',
    'HFS_BH': '#4caf50',
    'SS': '#ff9800',
}

# === Map Constants ===
EVA_5CLASS_BINS = [0, 1, 2, 3, 4, 5]
EVA_5CLASS_COLORS = ['#3288bd', '#99d594', '#e6f598', '#fc8d59', '#d53e4f']
EVA_5CLASS_LABELS = ['Very Low (0-1)', 'Low (1-2)', 'Medium (2-3)', 'High (3-4)', 'Very High (4-5)']

BASEMAP_TILES = {
    "CartoDB Positron": "cartodbpositron",
    "OpenStreetMap": "openstreetmap",
    "CartoDB Dark Matter": "cartodbdark_matter",
}

# === Export Styling Constants ===
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

# === EV Calculation Reference ===
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

APP_VERSION = '2.1.2'
```

**Step 2: Update `app.py` imports**

At the top of `app.py`, replace the inline constants block (lines 38–45) with:

```python
from eva_config import (
    MAX_FEATURES, LOCALLY_RARE_THRESHOLD, PERCENTILE_95, MAX_EV_SCALE,
    PREVIEW_ROWS_LIMIT, RESULTS_DISPLAY_LIMIT, MAX_FILE_SIZE_MB,
    QUALITATIVE_AQS, QUANTITATIVE_AQS, ALL_AQS, AQ_TOOLTIPS, AQ_METHODOLOGY,
    ACRONYMS, CLASSIFICATION_COLORS, EVA_5CLASS_BINS, EVA_5CLASS_COLORS,
    EVA_5CLASS_LABELS, BASEMAP_TILES, EXPORT_TAB_COLORS, EXPORT_HEADER_COLOR,
    EXPORT_ALT_ROW_COLOR, EXPORT_MULTI_EC_TAB_COLOR, EXPORT_CHART_TAB_COLOR,
    EV_EXPLANATION, APP_VERSION,
)
```

Then delete the inline constant definitions (lines 38–45) and update all references:
- `acronyms_table()` (line 1021): replace inline dict with `return pd.DataFrame(ACRONYMS)`
- `get_aq_tooltip()` (line 2256): replace inline dict with `return AQ_TOOLTIPS.get(aq_name, "")`
- Methodology sheet in export (~line 2658): replace inline dict with `pd.DataFrame(AQ_METHODOLOGY)`
- EV explanation sheet (~line 2722): replace inline dict with `pd.DataFrame(EV_EXPLANATION)`
- Map constants (lines 3414–3422): delete, already imported
- Classification colors (in `features_config_ui`): replace inline dict with `CLASSIFICATION_COLORS`
- Version string '2.1.2' in export: replace with `APP_VERSION`

**Step 3: Verify app still works**

Run: `python -c "from eva_config import MAX_EV_SCALE; print(MAX_EV_SCALE)"`
Expected: `5`

Run: `python -c "import app"` (basic import check)

**Step 4: Commit**

```bash
git add eva_config.py app.py
git commit -m "refactor: extract constants and metadata to eva_config.py"
```

---

### Task 2: Create `eva_calculations.py` with core EVA math

**Files:**
- Create: `eva_calculations.py`
- Modify: `app.py`

**Step 1: Create `eva_calculations.py`**

Extract the 9 pure functions from inside `server()`:

```python
"""
MARBEFES EVA Calculations — pure functions for EVA assessment.

All functions are stateless and have no Shiny dependencies.
"""

import pandas as pd
import numpy as np
import logging

from eva_config import (
    MAX_EV_SCALE, LOCALLY_RARE_THRESHOLD, PERCENTILE_95,
    QUALITATIVE_AQS, QUANTITATIVE_AQS, AQ_TOOLTIPS,
)

logger = logging.getLogger(__name__)


def detect_data_type(df):
    """
    Automatically detect if data is qualitative or quantitative.

    Logic:
    - Qualitative: Binary data (only 0 and 1 values, or very few unique values)
    - Quantitative: Continuous data (many unique values, decimals, or range > 1)
    """
    # ... (exact code from app.py lines 963-1015, with MAX_EV_SCALE already imported)


def rescale_qualitative(df):
    """
    Rescale qualitative (binary) data to 0-MAX_EV_SCALE scale.
    For presence/absence data: presence (1) = MAX_EV_SCALE, absence (0) = 0.
    """
    # ... (exact code from app.py lines 1768-1787)


def rescale_quantitative(df):
    """
    Rescale quantitative data to 0-MAX_EV_SCALE scale using min-max normalization.
    Formula: MAX_EV_SCALE * (value - min) / (max - min)
    """
    # ... (exact code from app.py lines 1789-1820)


def classify_features(df, user_classifications, lrf_threshold=LOCALLY_RARE_THRESHOLD):
    """
    Classify features based on intrinsic properties (LRF, ROF) and user input.
    """
    # ... (exact code from app.py lines 1822-1855)


def calculate_aq9_special(df, classifications, percentile=PERCENTILE_95):
    """
    Calculate AQ9 special 3-step concentration-weighted values.
    """
    # ... (exact code from app.py lines 1857-1928)


def calculate_all_aqs(df, data_type, rescaled_qual, rescaled_quant, aq9_rescaled, classifications):
    """Calculate all 15 Assessment Questions (AQ1-AQ15)."""
    # ... (exact code from app.py lines 1930-1992)


def calculate_ev(aq_results, data_type):
    """Calculate EV as MAX of appropriate AQs based on data type."""
    # ... (exact code from app.py lines 1994-2019)
    # Replace inline AQ lists with QUALITATIVE_AQS and QUANTITATIVE_AQS


def get_aq_status(data_type, classifications, results):
    """Analyze each AQ and return status with explanation."""
    # ... (exact code from app.py lines 2090-2122)
    # Replace inline qual_aqs/quant_aqs lists with QUALITATIVE_AQS/QUANTITATIVE_AQS


def get_aq_tooltip(aq_name):
    """Return tooltip text for a given AQ name."""
    return AQ_TOOLTIPS.get(aq_name, "")
```

Each function is copied verbatim from `app.py` with these changes:
- Remove one level of indentation (they were inside `server()`)
- Replace `LOCALLY_RARE_THRESHOLD`, `MAX_EV_SCALE`, `PERCENTILE_95` references with imports from `eva_config`
- In `calculate_ev()`: use `QUALITATIVE_AQS` and `QUANTITATIVE_AQS` instead of inline lists
- In `get_aq_status()`: use `QUALITATIVE_AQS` and `QUANTITATIVE_AQS` instead of inline lists
- `get_aq_tooltip()`: simplified to delegate to `AQ_TOOLTIPS` dict

**Step 2: Update `app.py`**

Add import at top of `app.py`:

```python
import eva_calculations
```

Inside `server()`:
- Delete the function definitions: `detect_data_type` (lines 963-1015), `rescale_qualitative` (1768-1787), `rescale_quantitative` (1789-1820), `classify_features` (1822-1855), `calculate_aq9_special` (1857-1928), `calculate_all_aqs` (1930-1992), `calculate_ev` (1994-2019), `get_aq_status` (2090-2122), `get_aq_tooltip` (2255-2275)
- Update call sites to use module prefix:
  - `detect_data_type(df)` → `eva_calculations.detect_data_type(df)` (in `handle_upload`)
  - `rescale_qualitative(df)` → `eva_calculations.rescale_qualitative(df)` (in `calculate_results`)
  - `rescale_quantitative(df)` → `eva_calculations.rescale_quantitative(df)` (in `calculate_results`)
  - `classify_features(...)` → `eva_calculations.classify_features(...)` (in `calculate_results`)
  - `calculate_aq9_special(...)` → `eva_calculations.calculate_aq9_special(...)` (in `calculate_results`)
  - `calculate_all_aqs(...)` → `eva_calculations.calculate_all_aqs(...)` (in `calculate_results`)
  - `calculate_ev(...)` → `eva_calculations.calculate_ev(...)` (in `calculate_results`)
  - `get_aq_status(...)` → `eva_calculations.get_aq_status(...)` (in `results_ui`)
  - `get_aq_tooltip(...)` → `eva_calculations.get_aq_tooltip(...)` (in `results_table_with_tooltips`)

**Step 3: Verify**

Run: `python -c "from eva_calculations import calculate_ev; print('OK')"`
Expected: `OK`

Run: `python -c "import app"` (basic import check)

**Step 4: Commit**

```bash
git add eva_calculations.py app.py
git commit -m "refactor: extract calculation functions to eva_calculations.py"
```

---

### Task 3: Create `eva_export.py` with Excel workbook generation

**Files:**
- Create: `eva_export.py`
- Modify: `app.py`

**Step 1: Create `eva_export.py`**

Extract the Excel generation logic from `download_results()` (lines 2530–3006):

```python
"""
MARBEFES EVA Excel Export — workbook generation and styling.

All functions accept plain data (DataFrames, dicts) — no Shiny dependencies.
"""

import io
import logging
import tempfile

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment, numbers
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.drawing.image import Image as XlImage

from eva_config import (
    AQ_METHODOLOGY, EV_EXPLANATION, APP_VERSION,
    EXPORT_TAB_COLORS, EXPORT_HEADER_COLOR, EXPORT_ALT_ROW_COLOR,
    EXPORT_MULTI_EC_TAB_COLOR, EXPORT_CHART_TAB_COLOR,
)

logger = logging.getLogger(__name__)

# Style constants
_HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
_HEADER_FILL = PatternFill(start_color=EXPORT_HEADER_COLOR, end_color=EXPORT_HEADER_COLOR, fill_type="solid")
_HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
_THIN_BORDER = Border(
    left=Side(style='thin', color='D0D0D0'),
    right=Side(style='thin', color='D0D0D0'),
    top=Side(style='thin', color='D0D0D0'),
    bottom=Side(style='thin', color='D0D0D0'),
)
_ALT_ROW_FILL = PatternFill(start_color=EXPORT_ALT_ROW_COLOR, end_color=EXPORT_ALT_ROW_COLOR, fill_type="solid")


def style_worksheet(ws, has_data=True, freeze=True, autofilter=True, start_row=1):
    """Apply professional styling to a worksheet."""
    # ... (exact code from app.py lines 2900-2936, using module-level style constants)


def _build_summary_sheet(writer, metadata, ec_store, results, uploaded_data, data_type):
    """Write the Summary & Metadata sheet."""
    # ... (extract logic from app.py lines 2549-2626)


def _build_data_sheets(writer, results, uploaded_data, user_classifications):
    """Write Original Data, AQ & EV Results, Feature Classifications, Methodology, EV Calc, Complete Results sheets."""
    # ... (extract logic from app.py lines 2628-2750)


def _build_multi_ec_sheets(writer, ec_store):
    """Write Aggregated EV and per-EC result sheets when multiple ECs saved."""
    # ... (extract logic from app.py lines 2752-2783)


def _build_chart_sheets(writer, results, ec_store):
    """Generate and embed Plotly chart images as worksheet sheets."""
    # ... (extract logic from app.py lines 2784-2883)


def _apply_styling(writer, ec_store):
    """Apply tab colors, professional styling, conditional formatting, and number formats to all sheets."""
    # ... (extract logic from app.py lines 2885-3003)


def generate_workbook(results, uploaded_data, user_classifications, data_type, metadata, ec_store):
    """
    Generate a complete Excel workbook with all analysis results.

    Args:
        results: DataFrame with AQ scores and EV values
        uploaded_data: Original uploaded DataFrame
        user_classifications: Dict of {feature: [classification_list]}
        data_type: "qualitative" or "quantitative"
        metadata: Dict with keys: ec_name, study_area, data_description
        ec_store: Dict of {ec_name: {data, data_type, classifications, results, feature_count}}

    Returns:
        io.BytesIO buffer containing the Excel workbook
    """
    if results is None or uploaded_data is None:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            pd.DataFrame({"Message": ["No data available"]}).to_excel(writer, sheet_name='Info', index=False)
        buffer.seek(0)
        return buffer

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        _build_summary_sheet(writer, metadata, ec_store, results, uploaded_data, data_type)
        _build_data_sheets(writer, results, uploaded_data, user_classifications)
        if len(ec_store) >= 2:
            _build_multi_ec_sheets(writer, ec_store)
        _build_chart_sheets(writer, results, ec_store)
        _apply_styling(writer, ec_store)

    buffer.seek(0)
    return buffer
```

The key design: `generate_workbook()` accepts plain Python objects (DataFrames, dicts, strings) — no reactive values or `input.*` references. The `download_results()` handler in `app.py` is responsible for extracting values from reactives and passing them in.

**Step 2: Update `app.py`**

Add import at top of `app.py`:

```python
import eva_export
```

Replace the entire `download_results()` body (lines 2530–3006) with:

```python
    @render.download(filename=lambda: f"MARBEFES_EVA_Results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    def download_results():
        """Export comprehensive analysis results to Excel."""
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
        )
```

Also delete the openpyxl styling imports from `app.py` (lines 25–29) since they're now only used in `eva_export.py`:
- `from openpyxl.styles import Font, PatternFill, Border, Side, Alignment, numbers`
- `from openpyxl.utils import get_column_letter`
- `from openpyxl.formatting.rule import ColorScaleRule`
- `from openpyxl.drawing.image import Image as XlImage`
- `import plotly.io as pio`

**Step 3: Verify**

Run: `python -c "from eva_export import generate_workbook; print('OK')"`
Expected: `OK`

Run: `python -c "import app"` (basic import check)

**Step 4: Commit**

```bash
git add eva_export.py app.py
git commit -m "refactor: extract Excel export logic to eva_export.py"
```

---

### Task 4: Update `app.py` map section to use config imports

**Files:**
- Modify: `app.py`

This task cleans up remaining inline references in `app.py` that should use `eva_config` imports.

**Step 1: Update map functions**

In `app.py`, the map section (around lines 3396–3523 post-extraction) still has inline constant definitions. After Task 1 moved the constants to `eva_config`, delete these lines from inside `server()`:

- `EVA_5CLASS_BINS = [0, 1, 2, 3, 4, 5]` (line 3414)
- `EVA_5CLASS_COLORS = [...]` (line 3415)
- `EVA_5CLASS_LABELS = [...]` (line 3416)
- `BASEMAP_TILES = {...}` (lines 3418–3422)

The functions `auto_zoom_level()` and `create_ev_map()` stay in `app.py` for now (they reference map constants via import and are called only by the reactive `map_output()` renderer).

**Step 2: Verify**

Run: `python -c "import app"` (basic import check)

**Step 3: Commit**

```bash
git add app.py
git commit -m "refactor: remove inline map constants, use eva_config imports"
```

---

### Task 5: Integration test — run the app and verify all features work

**Files:** None (testing only)

**Step 1: Start the application**

```bash
python -m shiny run app.py --port 8790
```

**Step 2: Verify core workflow**

Using Playwright or manual testing:
1. Navigate to `http://localhost:8790`
2. Go to Data Input tab
3. Upload `sample_data_with_rare_features.csv` as qualitative
4. Check that AQ + EV Results tab shows scores
5. Check that Visualization tab renders charts
6. Click "Download Complete Analysis (Excel)" on Total EV tab
7. Verify the downloaded Excel file has all sheets, styling, and charts

**Step 3: Verify multi-EC workflow**

1. Save current EC as "Fish"
2. Click "New EC", upload `sample_data.csv`, save as "Habitats"
3. Check Total EV tab shows aggregated view
4. Download Excel — verify multi-EC sheets present

**Step 4: Verify no import errors**

```bash
python -c "import eva_config; import eva_calculations; import eva_export; import app; print('All imports OK')"
```

**Step 5: Commit (if any fixes needed)**

```bash
git commit -m "fix: address integration test findings"
```

---

### Task 6: Push to GitHub

**Step 1: Push all commits**

```bash
git push origin main
```
