# Multi-EC Support Design for MARBEFES EVA Application

**Date:** 2026-02-17
**Status:** Approved
**Approach:** Dictionary-based EC store with save/restore into existing reactives
**Scope:** EC management UI, state persistence, Total EV aggregation, enhanced export

---

## Current State

The app processes one Ecosystem Component (EC) per session. There is no infrastructure for storing multiple ECs or aggregating Total EV across them. The Total EV tab currently summarises a single EC's EV values across subzones.

## 1. EC State Management

Two new reactive values:

```python
ec_store = reactive.Value({})    # {ec_name: {data, data_type, classifications, results}}
current_ec = reactive.Value(None)  # Name of the active EC
```

**Save operation:** When the user clicks "Save Current EC", a snapshot is stored:
- `data`: the uploaded DataFrame
- `data_type`: qualitative or quantitative
- `classifications`: the feature classification dict
- `results`: the calculated AQ + EV results DataFrame

**Restore operation:** When the user clicks a saved EC, the snapshot is loaded back into the existing reactive values (`uploaded_data`, `feature_classifications`, `detected_data_type`), so all existing rendering code works unchanged.

**EC name:** Taken from the existing `input.ec_name()` metadata field. Required before saving (validation).

## 2. EC Management UI

Added to the Data Input sidebar, above the metadata fields:

- **EC list** showing saved ECs with name, data type badge, and feature count
- **"Save Current EC" button** — saves current workspace under `input.ec_name()`
- **"New EC" button** — clears current state for a fresh upload
- **Click an EC name** — restores its data into the active workspace
- **Delete (×) button** on each EC to remove it from the store

All ECs must share the same Subzone IDs (same spatial grid).

## 3. Total EV Aggregation

The Total EV tab aggregates across all saved ECs:

- **Per-EC summary table:** EC name, data type, feature count, mean EV
- **Aggregated Total EV per subzone:** Total EV = sum of EV values from all ECs
- **Summary statistics:** sum, mean, max, min of the aggregated Total EV
- **Aggregated results table:** Subzone ID | EC1 EV | EC2 EV | ... | Total EV
- If only 1 EC saved, behaves exactly as current (single-EC summary)

## 4. Enhanced Export

Excel export updated when multiple ECs are saved:

- One sheet per EC with its AQ + EV results
- Aggregation sheet with per-EC EV columns and Total EV
- Summary sheet updated with multi-EC metadata

## 5. Implementation Notes

- All changes in `app.py` (single-file architecture maintained)
- No new dependencies required
- Existing single-EC workflow remains the primary interaction; multi-EC is additive
- The data type dropdown and feature classification UI operate on the current (active) EC
- Results are recalculated when switching ECs via the existing `calculate_results()` reactive
