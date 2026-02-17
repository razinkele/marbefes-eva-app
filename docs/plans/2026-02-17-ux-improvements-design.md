# UX Improvements Design for MARBEFES EVA Application

**Date:** 2026-02-17
**Status:** Approved
**Approach:** Incremental in-place improvements to app.py
**Scope:** Data validation, error handling, feature classification UI, configurable thresholds, AQ explanations

---

## 1. Data Validation & Error Handling

### 1.1 CSV Upload Validation Report

On CSV upload, display a validation report card in the Data Input main panel:

- Row/column counts, detected data type (qualitative/quantitative)
- Missing value count per column (with percentage)
- Warning if any feature columns are non-numeric
- Warning if Subzone IDs have duplicates
- Notification that NaN values will be treated as 0 (with option to keep as NaN)
- File size and format confirmation

### 1.2 Spatial Upload Feedback

Improve existing spatial preview:

- Clear error messages if file can't be read (user-facing, not just logged)
- Colour-coded match status: green = full match, yellow = partial, red = no match
- Collapsible list of unmatched Subzone IDs

### 1.3 Global Error Handling

- Wrap calculation functions in try-except blocks
- Show user-facing notifications via `ui.notification_show()` instead of silent logging
- Provide actionable error messages (e.g., "Feature column X contains non-numeric values")

## 2. Feature Classification UI

### 2.1 Grouped Layout

Replace flat checkbox grid with categorised sections:

- **Rarity group**: RRF (Regionally Rare), NRF (Nationally Rare), LRF (auto-detected, read-only badge)
- **Ecological role group**: ESF (Ecologically Significant), HFS_BH (Habitat Forming/Biogenic), SS (Symbiotic)

### 2.2 Inline Help

- Info icons next to each classification type with tooltip showing EVA guidance definition
- Show which AQs each classification activates (e.g., "RRF enables AQ5/AQ6")

### 2.3 Live Summary & Feedback

- Live count summary: "3 features classified as RRF, 2 as ESF, ..."
- "Reset All" button to clear all classifications
- Classified features get a coloured tag/badge in the feature list

## 3. Configurable Thresholds

### 3.1 Advanced Settings Panel

Collapsible panel in Data Input sidebar (collapsed by default):

| Setting | Default | Control | Range |
|---------|---------|---------|-------|
| Locally Rare threshold | 5% | Slider | 1-20% |
| Concentration percentile | 95th | Dropdown | 90th, 95th, 99th |
| Results display limit | 20 rows | Dropdown | 10, 20, 50, All |
| Max EV scale | 5 | Read-only | Fixed per guidance |

### 3.2 Behaviour

- Changes take effect immediately via reactive values
- Summary text when collapsed: "Thresholds: LRF 5%, P95, 20 rows"
- Calculation functions use reactive threshold values instead of constants

## 4. Clearer AQ Explanations

### 4.1 Status Badges

Replace "Active"/"Inactive" labels with descriptive badges:

- **"Active"** (green) — AQ applies to current data type
- **"N/A - Quantitative data required"** (grey) — data type mismatch
- **"N/A - No features classified as RRF"** (grey) — missing classification

### 4.2 EV Calculation Info Box

Collapsible info box at top of AQ + EV Results tab:

- "EV = MAX of all active AQ scores for each subzone"
- List of active AQs for current data
- Explanation of which classifications are needed to activate remaining AQs

### 4.3 Results Table Enhancements

- Highlight the AQ column that determines EV for each row (the max value)
- Feature contribution summary: which features/AQs drive high or low EV scores

## 5. Implementation Notes

- All changes in `app.py` (single-file architecture maintained)
- No new dependencies required
- Reactive values replace hardcoded constants for thresholds
- CSS additions for new UI components (badges, grouped sections, info boxes)
