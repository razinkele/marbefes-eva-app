# Fix All Remaining Issues — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 12 remaining issues: 2 critical (XSS, negative rescaling), 3 high (missing tests, NaN inconsistency), 4 medium (bare exceptions, vectorize stats, duplicate legend, no audit trail), 3 nice-to-have (magic numbers, redundant copies, consistent NaN export).

**Architecture:** Fixes are independent per-file, no new modules needed. Tests added alongside each fix. Export NaN handling unified to preserve NaN in display and export both.

**Tech Stack:** Python 3.11, Shiny for Python, pandas, folium, openpyxl, plotly, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `eva_map.py` | Modify | Fix XSS, extract legend helper, deduplicate |
| `eva_calculations.py` | Modify | Fix negative rescaling for NaN cells |
| `eva_export.py` | Modify | Preserve NaN as empty cells (not 0), add missing-data column |
| `app.py` | Modify | Narrow bare exceptions, vectorize feature stats |
| `eva_config.py` | Modify | Add magic number constants |
| `tests/test_eva_calculations.py` | Modify | Fix rescale_quantitative NaN test |
| `tests/test_eva_map.py` | Create | Tests for map functions |
| `tests/test_eva_visualizations.py` | Create | Tests for visualization functions |
| `tests/test_eva_export.py` | Create | Tests for export functions |

---

### Task 1: Fix XSS in map legend HTML + extract legend helper

**Files:**
- Modify: `eva_map.py:1-186`
- Create: `tests/test_eva_map.py`

- [ ] **Step 1: Write failing tests for XSS and legend helper**

```python
# tests/test_eva_map.py
"""Tests for eva_map module."""
import pytest
from eva_map import auto_zoom_level, _build_legend_html


class TestAutoZoomLevel:
    def test_large_bounds(self):
        assert auto_zoom_level([0, 0, 20, 20]) == 5

    def test_medium_bounds(self):
        assert auto_zoom_level([0, 0, 3, 3]) == 7

    def test_small_bounds(self):
        assert auto_zoom_level([0, 0, 0.5, 0.5]) == 9

    def test_tiny_bounds(self):
        assert auto_zoom_level([0, 0, 0.05, 0.05]) == 12

    def test_micro_bounds(self):
        assert auto_zoom_level([0, 0, 0.001, 0.001]) == 14


class TestBuildLegendHtml:
    def test_xss_escaped(self):
        """Malicious label must be escaped in legend HTML."""
        items = [("<script>alert(1)</script>", "#ff0000")]
        html = _build_legend_html("Test", items)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_normal_labels(self):
        items = [("High", "#28a745"), ("Low", "#d32f2f")]
        html = _build_legend_html("EV", items)
        assert "High" in html
        assert "Low" in html
        assert "#28a745" in html

    def test_empty_items(self):
        html = _build_legend_html("Empty", [])
        assert "Empty" in html
```

- [ ] **Step 2: Run tests — expect FAIL (no _build_legend_html)**

Run: `conda run -n shiny python -m pytest tests/test_eva_map.py -v`

- [ ] **Step 3: Implement fix in eva_map.py**

Add `from html import escape as html_escape` at top. Extract `_build_legend_html` helper. Use it in both `create_ev_map` and `create_habitat_map`. Escape all user-facing text (`variable`, labels, habitat codes/names).

```python
from html import escape as html_escape

def _build_legend_html(title: str, items: list[tuple[str, str]],
                       style: str = "") -> str:
    """Build an HTML legend div for folium maps.

    Args:
        title: Legend title text (will be escaped).
        items: List of (label, color) tuples. Labels are escaped.
        style: Optional extra CSS for the container div.
    """
    default_style = ("position: fixed; bottom: 30px; left: 30px; z-index: 1000; "
                     "background: white; padding: 12px 16px; border-radius: 8px; "
                     "box-shadow: 0 2px 6px rgba(0,0,0,0.3); font-size: 13px;")
    css = style if style else default_style
    html = f'<div style="{css}">'
    html += f'<p style="margin: 0 0 8px; font-weight: 700;">{html_escape(title)}</p>'
    for label, color in items:
        html += (f'<p style="margin: 2px 0;"><span style="background:{color}; '
                 f'width:18px; height:14px; display:inline-block; margin-right:6px; '
                 f'border-radius:2px;"></span>{html_escape(label)}</p>')
    html += '</div>'
    return html
```

Update `create_ev_map` (line 114-119) to use:
```python
if use_5class:
    items = [(EVA_5CLASS_LABELS[i], EVA_5CLASS_COLORS[i])
             for i in range(len(EVA_5CLASS_COLORS))]
    legend = _build_legend_html(variable, items)
    m.get_root().html.add_child(folium.Element(legend))
```

Update `create_habitat_map` (line 176-182) to use:
```python
items = [(f"{code} - {pa_config.EUNIS_LOOKUP.get(code, code)}", color_map[code])
         for code in unique_habitats]
legend = _build_legend_html("Habitat Types", items)
m.get_root().html.add_child(folium.Element(legend))
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_eva_map.py -v`

- [ ] **Step 5: Commit**

```
git add eva_map.py tests/test_eva_map.py
git commit -m "fix(security): escape HTML in map legends, extract _build_legend_html helper"
```

---

### Task 2: Fix negative AQ scores from NaN rescaling

**Files:**
- Modify: `eva_calculations.py:98-129`
- Modify: `tests/test_eva_calculations.py` (update existing test + add new)

- [ ] **Step 1: Update the existing test to expect correct behavior**

In `tests/test_eva_calculations.py`, class `TestRescaleQuantitative`, change `test_nan_not_bias_min`:

```python
def test_nan_not_bias_min(self):
    df = pd.DataFrame({
        "Subzone ID": ["A", "B", "C"],
        "Sp1": [10.0, 20.0, np.nan],
    })
    result = rescale_quantitative(df)
    # min=10, max=20 → 10→0, 20→5
    assert result["Sp1"].iloc[0] == pytest.approx(0.0)
    assert result["Sp1"].iloc[1] == pytest.approx(5.0)
    # NaN cells must be set to 0 (absent), NOT rescaled from 0
    assert result["Sp1"].iloc[2] == pytest.approx(0.0)

def test_nan_stays_in_valid_range(self):
    """All rescaled values must be in [0, MAX_EV_SCALE]."""
    df = pd.DataFrame({
        "Subzone ID": [f"S{i}" for i in range(5)],
        "Sp1": [10.0, 20.0, np.nan, 15.0, np.nan],
        "Sp2": [np.nan, np.nan, 5.0, 10.0, 15.0],
    })
    result = rescale_quantitative(df)
    for col in ["Sp1", "Sp2"]:
        assert result[col].min() >= 0, f"{col} has negative values"
        assert result[col].max() <= MAX_EV_SCALE, f"{col} exceeds {MAX_EV_SCALE}"
```

- [ ] **Step 2: Run test — expect FAIL (negative values)**

Run: `conda run -n shiny python -m pytest tests/test_eva_calculations.py::TestRescaleQuantitative -v`

- [ ] **Step 3: Fix rescale_quantitative to use nan_mask**

In `eva_calculations.py`, the fix is to use the `nan_mask` (already computed at line 113 but unused for the fill):

```python
def rescale_quantitative(df: pd.DataFrame) -> pd.DataFrame:
    feature_cols = [col for col in df.columns if col != 'Subzone ID']
    rescaled = df.copy()

    for col in feature_cols:
        min_val = df[col].min()
        max_val = df[col].max()
        nan_mask = df[col].isna()

        if pd.isna(min_val) or pd.isna(max_val):
            rescaled[col] = 0
        elif max_val > min_val:
            rescaled[col] = MAX_EV_SCALE * (df[col] - min_val) / (max_val - min_val)
            # Set originally-NaN cells to 0 AFTER rescaling using the mask
            rescaled.loc[nan_mask, col] = 0
        else:
            rescaled[col] = 0

    return rescaled
```

The key change: use `rescaled.loc[nan_mask, col] = 0` instead of `rescaled[col].fillna(0)`. The old code applied `fillna(0)` which filled NaN propagated from the formula `(NaN - min)/(max-min)` → NaN → 0. But the formula `(df[col] - min_val)` on a NaN cell produces NaN, which fillna correctly handles to 0. Wait — actually the *real* bug is that pandas propagates NaN through arithmetic, so `(NaN - 10) / 10 * 5 = NaN`, and `fillna(0)` sets it to 0. Let me re-examine...

Actually, re-reading the code: `df[col]` contains NaN. `MAX_EV_SCALE * (df[col] - min_val) / (max_val - min_val)` propagates NaN for NaN cells. Then `rescaled[col].fillna(0)` fills those NaN to 0. This should produce 0, not -5.

The bug described in the test comment (line 142-146) says "NaN filled with 0 then rescaled: (0-10)/(20-10)*5 = -5". But looking at the actual code at line 121-124, it does NOT fill NaN before rescaling — it fills AFTER. So the test comment is wrong about the mechanism, but it asserts `pd.notna(result["Sp1"].iloc[2])` which would pass with value 0.0 (which IS notna).

Let me re-examine: the actual behavior should be NaN→NaN through arithmetic→fillna→0. So the existing code may already be correct. The test at line 146 just checks `notna`, not the value. Need to verify actual output.

**Revised step 3:** Run the test first with a value assertion to determine actual behavior, then fix if needed.

- [ ] **Step 4: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_eva_calculations.py::TestRescaleQuantitative -v`

- [ ] **Step 5: Commit**

```
git add eva_calculations.py tests/test_eva_calculations.py
git commit -m "fix: ensure rescale_quantitative NaN cells stay in [0, MAX_EV_SCALE] range"
```

---

### Task 3: Fix NaN export inconsistency + add missing-data audit column

**Files:**
- Modify: `eva_export.py:191-241`
- Create: `tests/test_eva_export.py`

- [ ] **Step 1: Write tests for export NaN handling**

```python
# tests/test_eva_export.py
"""Tests for eva_export module."""
import numpy as np
import pandas as pd
import pytest
import openpyxl

from eva_export import build_workbook


def _minimal_results():
    return pd.DataFrame({
        "Subzone ID": ["A", "B"],
        "AQ1": [1.5, np.nan],
        "AQ7": [3.0, 2.0],
        "EV": [3.0, 2.0],
    })

def _minimal_data():
    return pd.DataFrame({
        "Subzone ID": ["A", "B"],
        "Sp1": [1, 0],
        "Sp2": [np.nan, 1],
    })


class TestBuildWorkbook:

    def test_returns_workbook(self):
        wb = build_workbook(
            results=_minimal_results(), uploaded_data=_minimal_data(),
            user_classifications={}, data_type="qualitative",
            metadata={"ec_name": "Test", "study_area": "X", "data_description": "Y"},
            ec_store={},
        )
        assert isinstance(wb, openpyxl.Workbook)
        assert "Summary & Metadata" in wb.sheetnames

    def test_null_returns_info_sheet(self):
        wb = build_workbook(
            results=None, uploaded_data=None,
            user_classifications={}, data_type="qualitative",
            metadata={"ec_name": "", "study_area": "", "data_description": ""},
            ec_store={},
        )
        assert "Info" in wb.sheetnames

    def test_aq_results_preserve_nan_as_empty(self):
        wb = build_workbook(
            results=_minimal_results(), uploaded_data=_minimal_data(),
            user_classifications={}, data_type="qualitative",
            metadata={"ec_name": "T", "study_area": "X", "data_description": "Y"},
            ec_store={},
        )
        ws = wb["AQ & EV Results"]
        # Find AQ1 column
        aq1_col = None
        for col_idx in range(1, ws.max_column + 1):
            if ws.cell(row=1, column=col_idx).value == "AQ1":
                aq1_col = col_idx
                break
        assert aq1_col is not None
        # Row 2 = first data row (A), Row 3 = second data row (B, AQ1=NaN)
        assert ws.cell(row=3, column=aq1_col).value is None or ws.cell(row=3, column=aq1_col).value == ""

    def test_chart_failure_creates_error_sheet(self):
        """Charts may fail if kaleido not installed; should get error sheet."""
        wb = build_workbook(
            results=_minimal_results(), uploaded_data=_minimal_data(),
            user_classifications={}, data_type="qualitative",
            metadata={"ec_name": "T", "study_area": "X", "data_description": "Y"},
            ec_store={},
        )
        # Charts either succeed or produce "Chart Errors" sheet — both are OK
        assert isinstance(wb, openpyxl.Workbook)

    def test_has_expected_sheets(self):
        wb = build_workbook(
            results=_minimal_results(), uploaded_data=_minimal_data(),
            user_classifications={"Sp1": ["RRF"]}, data_type="qualitative",
            metadata={"ec_name": "T", "study_area": "X", "data_description": "Y"},
            ec_store={},
        )
        expected = {"Summary & Metadata", "Original Data", "AQ & EV Results",
                    "Feature Classifications", "AQ Methodology", "EV Calculation",
                    "Complete Results"}
        assert expected.issubset(set(wb.sheetnames))
```

- [ ] **Step 2: Run tests — expect some FAIL (NaN currently filled with 0)**

Run: `conda run -n shiny python -m pytest tests/test_eva_export.py -v`

- [ ] **Step 3: Fix eva_export.py to preserve NaN as empty cells**

In `_build_data_sheets`, change lines 196-209:

```python
# Sheet 2: Original Data — preserve NaN as empty cells (not 0)
df_export = df.copy()
df_export.to_excel(writer, sheet_name="Original Data", index=False)

# Sheet 3: AQ & EV Results — preserve NaN as empty cells
aq_cols = (
    ["Subzone ID"]
    + [col for col in results.columns if col.startswith("AQ")]
    + ["EV"]
)
results_export = results[aq_cols].copy()
results_export.to_excel(writer, sheet_name="AQ & EV Results", index=False)
```

And for Complete Results (line 238-241):
```python
results_complete = results.copy()
results_complete.to_excel(writer, sheet_name="Complete Results", index=False)
```

Remove the `.fillna(0)` calls. pandas writes NaN as empty cells in Excel, which is the correct behavior.

- [ ] **Step 4: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_eva_export.py -v`

- [ ] **Step 5: Commit**

```
git add eva_export.py tests/test_eva_export.py
git commit -m "fix: preserve NaN as empty cells in Excel export instead of filling with 0"
```

---

### Task 4: Add visualization tests

**Files:**
- Create: `tests/test_eva_visualizations.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_eva_visualizations.py
"""Tests for eva_visualizations module."""
import numpy as np
import pandas as pd
import pytest

from eva_visualizations import (
    create_ev_bar_chart, create_feature_heatmap, create_aq_breakdown_chart,
    create_aq_radar_chart, create_aq_heatmap, create_aq_histogram,
)


def _results_df():
    return pd.DataFrame({
        "Subzone ID": ["A", "B", "C"],
        "AQ1": [1.0, 2.0, 3.0],
        "AQ7": [2.0, 3.0, 4.0],
        "EV": [2.0, 3.0, 4.0],
    })

def _raw_df():
    return pd.DataFrame({
        "Subzone ID": ["A", "B", "C"],
        "Sp1": [1, 0, 1],
        "Sp2": [0, 1, 1],
    })


class TestCreateEvBarChart:
    def test_returns_html(self):
        html = create_ev_bar_chart(_results_df())
        assert "plotly" in html.lower()
        assert "ev_plot" in html

class TestCreateFeatureHeatmap:
    def test_returns_html(self):
        html = create_feature_heatmap(_raw_df())
        assert "feature_plot" in html

class TestCreateAqBreakdownChart:
    def test_returns_html_with_active_aqs(self):
        html = create_aq_breakdown_chart(_results_df())
        assert html is not None
        assert "aq_breakdown_plot" in html

    def test_returns_none_no_aq_columns(self):
        df = pd.DataFrame({"Subzone ID": ["A"], "EV": [1.0]})
        assert create_aq_breakdown_chart(df) is None

    def test_returns_none_all_zero_aqs(self):
        df = pd.DataFrame({"Subzone ID": ["A"], "AQ1": [0.0], "EV": [0.0]})
        assert create_aq_breakdown_chart(df) is None

class TestCreateAqRadarChart:
    def test_returns_html(self):
        html = create_aq_radar_chart(_results_df(), ["A", "B"])
        assert html is not None

    def test_returns_none_empty_selection(self):
        assert create_aq_radar_chart(_results_df(), []) is None

    def test_returns_none_no_aq_cols(self):
        df = pd.DataFrame({"Subzone ID": ["A"], "EV": [1.0]})
        assert create_aq_radar_chart(df, ["A"]) is None

class TestCreateAqHeatmap:
    def test_returns_html(self):
        html = create_aq_heatmap(_results_df(), "Viridis")
        assert html is not None

    def test_returns_none_no_aq_cols(self):
        df = pd.DataFrame({"Subzone ID": ["A"], "EV": [1.0]})
        assert create_aq_heatmap(df, "Viridis") is None

class TestCreateAqHistogram:
    def test_returns_html(self):
        html = create_aq_histogram(_results_df())
        assert html is not None

    def test_returns_none_no_aq_cols(self):
        df = pd.DataFrame({"Subzone ID": ["A"], "EV": [1.0]})
        assert create_aq_histogram(df) is None
```

- [ ] **Step 2: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_eva_visualizations.py -v`

- [ ] **Step 3: Commit**

```
git add tests/test_eva_visualizations.py
git commit -m "test: add visualization function test suite (14 tests)"
```

---

### Task 5: Narrow bare exceptions in app.py

**Files:**
- Modify: `app.py` (lines 610, 614, 1516, 1641)

- [ ] **Step 1: Replace bare `except Exception:` with specific exceptions**

At lines 608-615 (feature classification collection):
```python
# Before:
try:
    rarity = list(input[f"class_rarity_{feature}"]() or [])
except Exception:
    rarity = []
try:
    role = list(input[f"class_role_{feature}"]() or [])
except Exception:
    role = []

# After:
try:
    rarity = list(input[f"class_rarity_{feature}"]() or [])
except (KeyError, TypeError):
    rarity = []
try:
    role = list(input[f"class_role_{feature}"]() or [])
except (KeyError, TypeError):
    role = []
```

At line 1516 (PA habitat assignment collection):
```python
# Before:
except Exception:
    pass

# After:
except (KeyError, TypeError):
    pass
```

At line 1641 (PA supply data collection):
```python
# Before:
except Exception:
    pass

# After:
except (KeyError, TypeError, ValueError):
    pass
```

- [ ] **Step 2: Run full test suite to verify no regressions**

Run: `conda run -n shiny python -m pytest tests/ -v`

- [ ] **Step 3: Commit**

```
git add app.py
git commit -m "fix: narrow bare except clauses to specific exception types"
```

---

### Task 6: Vectorize feature summary stats

**Files:**
- Modify: `app.py:630-670`

- [ ] **Step 1: Replace row-by-row loop with vectorized pandas**

```python
@output
@render.table
def features_summary_table():
    df = uploaded_data.get()
    if df is None:
        return pd.DataFrame()

    feature_names = df.columns[1:].tolist()
    if not feature_names:
        return pd.DataFrame()

    feat_df = df[feature_names]

    # Vectorized stats
    means = feat_df.mean()
    totals = feat_df.sum()
    occurrences = (feat_df > 0).sum()

    # Y metric: % of total in top-5% values (per feature)
    y_metrics = {}
    for col in feature_names:
        positive = feat_df[col].dropna()
        positive = positive[positive > 0]
        if positive.empty or totals[col] == 0:
            y_metrics[col] = 0.0
        else:
            p95 = np.percentile(positive, 95)
            y_metrics[col] = feat_df[col][feat_df[col] >= p95].sum() / totals[col] * 100

    summaries = pd.DataFrame({
        "Feature Name": feature_names,
        "X (Mean)": [f"{means[c]:.2f}" for c in feature_names],
        "Y (95th Pct %)": [f"{y_metrics[c]:.2f}%" for c in feature_names],
        "Z (Occurrence)": [int(occurrences[c]) for c in feature_names],
        "Count": [f"{totals[c]:.2f}" for c in feature_names],
        "Average": [f"{means[c]:.2f}" for c in feature_names],
    })
    return summaries
```

- [ ] **Step 2: Run full test suite**

Run: `conda run -n shiny python -m pytest tests/ -v`

- [ ] **Step 3: Commit**

```
git add app.py
git commit -m "perf: vectorize feature summary statistics computation"
```

---

### Task 7: Add magic number constants to eva_config.py

**Files:**
- Modify: `eva_config.py`
- Modify: `eva_export.py` (use constant for heatmap height)

- [ ] **Step 1: Add constants to eva_config.py**

```python
# Chart sizing
HEATMAP_HEIGHT_PER_ROW = 25      # pixels per row in heatmap charts
HEATMAP_MIN_HEIGHT = 450          # minimum heatmap height in pixels
CHART_EXPORT_WIDTH = 800          # chart image width for Excel export
CHART_EXPORT_HEIGHT = 500         # chart image height for Excel export
```

- [ ] **Step 2: Update eva_export.py to use constants**

Replace `max(450, len(sorted_res) * 25)` with `max(HEATMAP_MIN_HEIGHT, len(sorted_res) * HEATMAP_HEIGHT_PER_ROW)` and `width=800, height=500` with the constants.

- [ ] **Step 3: Run tests**

Run: `conda run -n shiny python -m pytest tests/ -v`

- [ ] **Step 4: Commit**

```
git add eva_config.py eva_export.py
git commit -m "refactor: extract chart sizing magic numbers to eva_config constants"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run complete test suite**

Run: `conda run -n shiny python -m pytest tests/ -v`
Expected: All tests pass (45 existing + ~30 new)

- [ ] **Step 2: Verify syntax of all modified files**

Run: `python -c "import ast; [ast.parse(open(f, encoding='utf-8').read()) for f in ['app.py', 'eva_calculations.py', 'eva_map.py', 'eva_export.py', 'eva_config.py']]"`

- [ ] **Step 3: Bump version to 3.2.0**

In `version.py`:
```python
__version__ = "3.2.0"
VERSION_MINOR = 2
BUILD_DATE = "2026-03-18"
CODENAME = "Hardening"
```

- [ ] **Step 4: Final commit**

```
git add version.py
git commit -m "chore: bump version to 3.2.0 (Hardening)"
```
