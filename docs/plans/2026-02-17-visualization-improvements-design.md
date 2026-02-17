# Visualization Improvements Design for MARBEFES EVA Application

**Date:** 2026-02-17
**Status:** Approved
**Approach:** Add new chart types to existing Visualization tab dropdown
**Scope:** AQ Breakdown chart, Radar chart, AQ Heatmap

---

## Current State

The Visualization tab has 3 chart types in a dropdown:
- "EV by Subzone" — bar chart of EV scores
- "Feature Distribution" — heatmap of raw feature data (subzone × feature)
- "AQ Scores" — histogram of all AQ score values

All use Plotly. The Map tab (Folium choropleth) is out of scope.

## 1. AQ Breakdown by Subzone

New dropdown option: **"AQ Breakdown by Subzone"**

Grouped bar chart showing individual AQ contributions per subzone with EV as a line overlay.

- **X-axis:** Subzone IDs
- **Y-axis:** Score (0–5)
- **Bars:** One colour per active AQ, grouped side-by-side; inactive AQs hidden
- **Line overlay:** EV value per subzone
- **Hover:** AQ name, score, whether it determines EV (is the max)
- **Colour:** Uses the selected colour scheme

## 2. Radar/Spider Chart

New dropdown option: **"AQ Radar Comparison"**

Radar chart comparing AQ profiles across selected subzones.

- **Axes:** All 15 AQs (AQ1–AQ15), each scaled 0–5
- **Polygons:** One per selected subzone, with transparency (fill opacity ~0.2)
- **Subzone selector:** Multi-select dropdown, max 5 subzones to avoid clutter
- **Default:** First 3 subzones selected
- **Colour:** Distinct colours per subzone (Plotly default sequence)

Requires a new `ui.input_selectize()` control that appears when "AQ Radar Comparison" is selected.

## 3. AQ × Subzone Heatmap

New dropdown option: **"AQ Heatmap"**

Heatmap showing AQ scores across all subzones.

- **Rows:** Subzones, sorted by EV descending
- **Columns:** AQ1–AQ15 + EV
- **Colour intensity:** Score value (0–5), using selected colour scheme
- **Annotations:** Score values displayed in cells (rounded to 1 decimal)
- **Inactive AQs:** Shown in grey/muted
- **Height:** Dynamic based on number of subzones

The existing "Feature Distribution" heatmap remains unchanged.

## 4. Implementation Notes

- All changes in `app.py` (single-file architecture maintained)
- No new dependencies — Plotly already supports all chart types
- Add new options to the `plot_type` dropdown choices
- Add conditional `ui.input_selectize()` for radar chart subzone selection
- Reuse existing `calculate_results()` data and colour scheme selector
