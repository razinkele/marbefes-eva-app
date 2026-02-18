# Modularization Design for MARBEFES EVA Application

**Date:** 2026-02-18
**Status:** Approved
**Approach:** Extract pure logic into 3 modules (Approach A)
**Scope:** Constants, calculation functions, and export logic extracted from app.py

---

## Current State

All application code lives in a single `app.py` file (~3,600 lines). Pure computation logic, export formatting, and constants are interleaved with Shiny reactive/UI code. This makes the file hard to navigate and the pure logic impossible to unit test in isolation.

## Goal

Split `app.py` into 3 new modules containing only pure (non-reactive) code. The Shiny reactive layer, UI definitions, and CSS remain in `app.py`. After extraction, `app.py` drops from ~3,600 to ~2,600 lines.

## 1. `eva_config.py` — Constants & Metadata

Shared constants and reference data used across the application. No external dependencies.

**Contents:**
- Calculation constants: `MAX_FEATURES`, `MAX_EV_SCALE`, `LOCALLY_RARE_THRESHOLD`, `PERCENTILE_95`, `MAX_FILE_SIZE_MB`, `PREVIEW_ROWS_LIMIT`, `RESULTS_DISPLAY_LIMIT`
- AQ metadata: qualitative AQ list, quantitative AQ list, AQ-to-feature-type mapping, AQ descriptions and tooltips
- Acronyms dictionary
- Classification badge colors
- Map constants: `EVA_5CLASS_BINS`, `EVA_5CLASS_COLORS`, `EVA_5CLASS_LABELS`, `BASEMAP_TILES`
- Export styling constants: header font/fill colors, tab colors by sheet category

**Not moved:** CSS string (embedded in UI definition), UI text content.

## 2. `eva_calculations.py` — Core EVA Math

Pure computation functions. Dependencies: `pandas`, `numpy`, `eva_config`.

**Functions:**
- `detect_data_type(df)` — Returns "qualitative", "quantitative", or "TO SPECIFY"
- `rescale_qualitative(df)` — Binary 0/1 → 0–5 scale
- `rescale_quantitative(df)` — Min-max normalization to 0–5
- `classify_features(df, user_classifications, lrf_threshold)` — LRF/ROF detection + user-assigned types
- `calculate_aq9_special(df, classifications, percentile)` — Concentration-weighted AQ9
- `calculate_all_aqs(df, data_type, rescaled_qual, rescaled_quant, aq9_rescaled, classifications)` — All 15 AQ scores
- `calculate_ev(aq_results, data_type)` — EV = MAX of applicable AQs
- `get_aq_status(data_type, classifications, results)` — Which AQs are active and why
- `get_aq_tooltip(aq_name)` — Tooltip text per AQ

The `calculate_results()` reactive in `app.py` becomes a thin orchestrator that calls these functions.

## 3. `eva_export.py` — Excel Export & Charts

Excel workbook generation. Dependencies: `pandas`, `openpyxl`, `plotly.io`, `io`, `tempfile`, `eva_config`.

**Functions:**
- `style_worksheet(ws, has_data, freeze, autofilter, start_row)` — Headers, borders, alternating rows, freeze panes, autofilter, column widths
- `apply_conditional_formatting(ws, columns_config)` — Color scale rules and number formats on EV/AQ columns
- `create_chart_sheets(wb, results_df, data_type, ec_store)` — 3 Plotly chart PNGs as image sheets
- `build_summary_sheet(ws, metadata, ec_store)` — Summary with single-EC or multi-EC metadata
- `generate_workbook(results, uploaded_data, classifications, data_type, metadata, ec_store)` — Orchestrates full workbook creation, returns BytesIO buffer

The `download_results()` handler in `app.py` calls `generate_workbook()` with reactive values passed as plain arguments.

## 4. What Stays in `app.py`

- All imports and the Shiny `App()` entry point
- Custom CSS string
- UI layout definition (all 8 tabs)
- Server function with reactive values
- All `@reactive.Effect`, `@reactive.Calc`, `@render.*` functions
- Multi-EC management (save/restore/delete) — tightly coupled to reactive state
- Visualization rendering — reads `input.*` controls directly
- Map rendering — reads `input.*` controls directly
- Data upload handlers — set reactive values

## 5. File Layout After Extraction

```
EVA Algorithms/
  app.py              # ~2,600 lines — Shiny UI + reactive layer
  eva_config.py       # ~200 lines — constants, metadata, reference data
  eva_calculations.py # ~300 lines — pure EVA math functions
  eva_export.py       # ~500 lines — Excel workbook generation
  requirements.txt
  docs/
  data/
  ...
```

## 6. Implementation Notes

- All new modules placed in the project root alongside `app.py`
- Imports in `app.py` change from inline definitions to `from eva_config import ...` etc.
- No behavioral changes — the app works identically after extraction
- Each module is independently importable and testable without Shiny
- Constants that are only used in one place still move to `eva_config.py` for single-source-of-truth
