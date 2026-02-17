# Enhanced Excel Export Design for MARBEFES EVA Application

**Date:** 2026-02-17
**Status:** Approved
**Approach:** Professional styling, embedded charts, multi-EC summary upgrade
**Scope:** All Excel export sheets in download_results()

---

## Current State

The export creates 7 standard sheets plus multi-EC sheets (when 2+ ECs saved). Formatting is minimal — only column widths on 2 sheets. No header styling, conditional formatting, or embedded charts.

## 1. Professional Styling

Applied to all sheets using openpyxl:

- **Header row:** Bold white text on dark blue background (#006994), matching app theme
- **Autofilter:** Enabled on all data sheet headers
- **Freeze panes:** Below header row so headers stay visible when scrolling
- **Data formatting:** EV and AQ score columns formatted to 2 decimal places
- **Alternating rows:** Light grey (#F2F2F2) every other row for readability
- **Column widths:** Auto-sized to content width (replacing hardcoded widths)
- **Conditional formatting:** Color scale on EV columns — Green (5.0) to Yellow (2.5) to Red (0.0). Applied to AQ & EV Results, Complete Results, and Aggregated EV sheets
- **Sheet tab colors:**
  - Summary: blue (#006994)
  - Data sheets: green (#28A745)
  - Results sheets: orange (#FD7E14)
  - Reference sheets: grey (#6C757D)
  - Multi-EC sheets: purple (#6F42C1)
- **Borders:** Thin borders around all data cells

## 2. Embedded Charts

Three chart sheets added using Plotly figure export via kaleido:

- **"Chart - EV by Subzone"** — Bar chart of EV scores per subzone (current EC or aggregated Total EV if multi-EC)
- **"Chart - AQ Heatmap"** — AQ scores × Subzones heatmap with cell annotations
- **"Chart - EV Distribution"** — Histogram of EV value distribution

Each chart rendered as PNG (~800x500px) via `fig.write_image()`, inserted into a dedicated sheet using `openpyxl.drawing.image.Image` at cell A1.

**New dependency:** `kaleido` package added to requirements.txt.

## 3. Summary Sheet Upgrade

**Single EC (unchanged):** Same metadata and statistics as current.

**Multiple ECs (new sections):**
- Header: "Multi-EC Analysis Summary"
- General metadata: Analysis Date, Time, Version, Study Area
- Per-EC summary table: EC Name | Data Type | Features | Mean EV | Max EV
- Aggregated statistics: Total EV sum, Average Total EV per subzone, Number of ECs, Total features across all ECs

## 4. Implementation Notes

- All changes in `app.py` (single-file architecture maintained)
- New dependency: `kaleido` for Plotly image export
- Styling applied via a reusable helper function to avoid duplication across sheets
- Existing sheet content unchanged — only formatting and new sheets added
- Charts use same visual style as app Visualization tab
