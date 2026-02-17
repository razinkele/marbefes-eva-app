# UX Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the EVA app's usability with data validation feedback, better error handling, an enhanced feature classification UI, configurable thresholds, and clearer AQ explanations.

**Architecture:** All changes are incremental modifications to `app.py`. Hardcoded constants become reactive values driven by new UI controls. Error handling uses `ui.notification_show()` for user-facing feedback. No new files or dependencies.

**Tech Stack:** Python Shiny, pandas, numpy (all existing)

**Design doc:** `docs/plans/2026-02-17-ux-improvements-design.md`

---

### Task 1: Add CSV Validation Report on Upload

**Files:**
- Modify: `app.py:1103-1165` (handle_upload function)
- Modify: `app.py:570-621` (Data Input main panel)

**Context:** Currently `handle_upload()` at line 1103 reads the CSV, cleans data, and silently sets `uploaded_data`. Errors are only logged. The main panel shows a static instructions card or a basic data preview. We need a validation report card showing data quality info.

**Step 1: Add a reactive value for validation info**

In the server function, after `geo_match_info = reactive.Value(None)` (around line 1078), add:

```python
validation_report = reactive.Value(None)
```

**Step 2: Build validation report in handle_upload**

At the end of `handle_upload()` (after line 1157 `uploaded_data.set(df)`), before the auto-detection block, add validation logic:

```python
# Build validation report
feature_cols = [col for col in df.columns if col != 'Subzone ID']
report = {
    'rows': len(df),
    'columns': len(feature_cols),
    'features': feature_cols,
    'missing': {col: int(df[col].isna().sum()) for col in feature_cols},
    'missing_pct': {col: round(df[col].isna().sum() / len(df) * 100, 1) for col in feature_cols},
    'non_numeric': [col for col in feature_cols if not pd.api.types.is_numeric_dtype(df[col])],
    'duplicate_ids': int(df.duplicated(subset=['Subzone ID']).sum()),
    'file_size_mb': round(file_size_mb, 2),
}
validation_report.set(report)
```

Also add user-facing notifications for errors. Replace the `logger.error` calls with:

```python
# Line 1119 - file too large
ui.notification_show(
    f"File too large ({file_size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB.",
    type="error", duration=8
)

# Line 1130 - CSV read error
ui.notification_show(
    f"Could not read CSV file: {e}",
    type="error", duration=8
)
```

**Step 3: Add validation report UI renderer**

Add a new `@output @render.ui` function called `validation_report_ui` that reads `validation_report.get()` and renders a card with:
- Row/column counts and file size
- Detected data type badge
- Missing values per column (only show columns with missing values)
- Warnings for non-numeric columns or duplicate IDs
- Green checkmark if no issues found

```python
@output
@render.ui
def validation_report_ui():
    report = validation_report.get()
    if report is None:
        return ui.TagList()

    items = []
    items.append(ui.p(
        f"✅ Loaded {report['rows']} subzones × {report['columns']} features ({report['file_size_mb']} MB)",
        style="color: #28a745; font-weight: 600; margin-bottom: 0.5rem;"
    ))

    # Warnings
    if report['duplicate_ids'] > 0:
        items.append(ui.p(
            f"⚠️ {report['duplicate_ids']} duplicate Subzone IDs were removed",
            style="color: #ff9800;"
        ))
    if report['non_numeric']:
        items.append(ui.p(
            f"⚠️ Non-numeric columns: {', '.join(report['non_numeric'])}",
            style="color: #ff9800;"
        ))

    # Missing values summary
    cols_with_missing = {k: v for k, v in report['missing'].items() if v > 0}
    if cols_with_missing:
        items.append(ui.p(
            f"ℹ️ {len(cols_with_missing)} columns have missing values (treated as 0):",
            style="color: #2196F3; margin-top: 0.5rem;"
        ))
        for col, count in list(cols_with_missing.items())[:5]:
            pct = report['missing_pct'][col]
            items.append(ui.p(
                f"  • {col}: {count} missing ({pct}%)",
                style="color: #6c757d; margin-left: 1rem; margin-bottom: 0.2rem;"
            ))
        if len(cols_with_missing) > 5:
            items.append(ui.p(
                f"  ... and {len(cols_with_missing) - 5} more",
                style="color: #6c757d; margin-left: 1rem;"
            ))
    else:
        items.append(ui.p("✅ No missing values detected", style="color: #28a745;"))

    return ui.card(
        ui.card_header("📋 Data Validation Report"),
        ui.div(*items, style="padding: 1rem;")
    )
```

**Step 4: Add the output placeholder in the Data Input main panel**

In the Data Input tab main panel area (around line 619-620), add `ui.output_ui("validation_report_ui")` between the existing data preview and geo preview outputs.

**Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add CSV validation report with user-facing error notifications"
```

---

### Task 2: Improve Spatial Upload Error Feedback

**Files:**
- Modify: `app.py:1166-1246` (handle_geojson_upload function)
- Modify: `app.py:1248-1290` (geo_preview_ui function)

**Context:** The spatial upload handler at line 1166 catches errors but only logs them. The geo preview at line 1248 shows basic match info but doesn't colour-code results or list unmatched IDs.

**Step 1: Add user-facing notifications to spatial handler**

In `handle_geojson_upload()`, replace `logger.error(...)` calls with `ui.notification_show(...)`:

```python
# Around line 1186 - file read error
ui.notification_show(
    f"Could not read spatial file: {e}",
    type="error", duration=8
)

# Around line 1201 - CRS error
ui.notification_show(
    f"CRS reprojection failed: {e}. File will be used without reprojection.",
    type="warning", duration=8
)
```

**Step 2: Enhance geo_preview_ui with colour-coded match status**

In `geo_preview_ui()`, update the match info section. Store unmatched IDs in `geo_match_info` so the preview can show them. Update the match info reactive value to include unmatched ID lists:

```python
# In handle_geojson_upload, update the match_info dict (around line 1230):
match_info = {
    'matched': len(matched),
    'csv_only': len(csv_only),
    'geo_only': len(geo_only),
    'csv_only_ids': sorted(list(csv_only))[:20],  # cap at 20 for display
    'geo_only_ids': sorted(list(geo_only))[:20],
}
```

In `geo_preview_ui()`, replace the plain text match display with colour-coded badges:

```python
# Full match = green, partial = yellow, no match = red
if info['csv_only'] == 0 and info['geo_only'] == 0:
    match_color = "#28a745"
    match_icon = "✅"
    match_text = f"{info['matched']} subzones fully matched"
elif info['matched'] > 0:
    match_color = "#ff9800"
    match_icon = "⚠️"
    match_text = f"{info['matched']} matched, {info['csv_only']} CSV-only, {info['geo_only']} GeoJSON-only"
else:
    match_color = "#d32f2f"
    match_icon = "🔴"
    match_text = "No matching Subzone IDs found"
```

Show unmatched IDs in a collapsible details element if there are any.

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: improve spatial upload error feedback with colour-coded match status"
```

---

### Task 3: Add Configurable Thresholds Panel

**Files:**
- Modify: `app.py:33-40` (constants block)
- Modify: `app.py:503-568` (Data Input sidebar UI)
- Modify: `app.py:1592` (classify_features - LOCALLY_RARE_THRESHOLD usage)
- Modify: `app.py:1641` (calculate_aq9_special - PERCENTILE_95 usage)
- Modify: `app.py:1977,2122` (RESULTS_DISPLAY_LIMIT usage)

**Context:** Currently `LOCALLY_RARE_THRESHOLD`, `PERCENTILE_95`, and `RESULTS_DISPLAY_LIMIT` are module-level constants. They need to become reactive values driven by UI controls.

**Step 1: Add threshold UI controls to the Data Input sidebar**

After the spatial grid upload section (after line 567), add a collapsible Advanced Settings panel:

```python
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
```

**Step 2: Update calculation functions to use reactive inputs**

Replace constant references with `input.xxx()` calls:

- Line 1592: Replace `LOCALLY_RARE_THRESHOLD` with `input.lrf_threshold() / 100`
- Line 1641: Replace `PERCENTILE_95` with `int(input.concentration_percentile())`
- Lines 1977, 2122: Replace `RESULTS_DISPLAY_LIMIT` with:
  ```python
  limit = int(input.results_display_limit())
  display_df = results[display_cols].head(limit) if limit > 0 else results[display_cols]
  ```

Note: The `classify_features` and `calculate_aq9_special` functions are called from within the server, so they need to accept the threshold as a parameter rather than reading `input` directly. Pass the values through `calculate_results()`:

```python
# In calculate_results():
lrf_threshold = input.lrf_threshold() / 100
concentration_pct = int(input.concentration_percentile())

classifications = classify_features(df, user_classifications, lrf_threshold=lrf_threshold)
aq9_rescaled = calculate_aq9_special(df, classifications, percentile=concentration_pct)
```

Update the function signatures accordingly, keeping the constants as default values for backward compatibility.

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add configurable thresholds for LRF, percentile, and display limit"
```

---

### Task 4: Redesign Feature Classification UI

**Files:**
- Modify: `app.py:1394-1433` (features_config_ui function)
- Modify: `app.py:625-665` (EC Features tab UI)

**Context:** The current feature classification UI at line 1394 renders a flat grid of checkbox groups per feature. It needs to be reorganised with category groupings, help text, live summary, and reset button.

**Step 1: Add CSS for classification UI components**

Add to the `custom_css` string:

```css
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
```

**Step 2: Rewrite features_config_ui with grouped layout**

Replace the `features_config_ui()` function (lines 1394-1433) with a version that groups checkboxes by category and adds help text:

```python
@output
@render.ui
def features_config_ui():
    df = uploaded_data.get()
    if df is None:
        return ui.p("Please upload data first in the Data Input tab.")

    feature_names = df.columns[1:].tolist()
    classifications = feature_classifications.get() or {}

    feature_rows = []
    for feature in feature_names:
        # Get current classifications for badge display
        current = classifications.get(feature, [])
        badges = []
        badge_colors = {'RRF': '#e91e63', 'NRF': '#9c27b0', 'ESF': '#2196F3', 'HFS_BH': '#4caf50', 'SS': '#ff9800'}
        for cls in current:
            badges.append(ui.span(
                cls, class_="feature-badge",
                style=f"background: {badge_colors.get(cls, '#999')}; color: white;"
            ))

        feature_rows.append(
            ui.div(
                ui.div(
                    ui.strong(feature),
                    *badges,
                    style="margin-bottom: 0.3rem;"
                ),
                ui.div(
                    ui.div(
                        ui.div("Rarity", class_="classification-group-header"),
                        ui.p("Features rare at regional or national level", class_="classification-help"),
                        ui.input_checkbox_group(
                            f"class_rarity_{feature}", "",
                            choices={"RRF": "RRF (Regionally Rare) → AQ5/AQ6", "NRF": "NRF (Nationally Rare) → AQ7/AQ8"},
                            selected=[c for c in current if c in ['RRF', 'NRF']],
                            inline=True
                        ),
                        class_="classification-group"
                    ),
                    ui.div(
                        ui.div("Ecological Role", class_="classification-group-header"),
                        ui.p("Functional importance in the ecosystem", class_="classification-help"),
                        ui.input_checkbox_group(
                            f"class_role_{feature}", "",
                            choices={
                                "ESF": "ESF (Ecologically Significant) → AQ10/AQ11",
                                "HFS_BH": "HFS/BH (Habitat Forming) → AQ12/AQ13",
                                "SS": "SS (Symbiotic) → AQ14/AQ15"
                            },
                            selected=[c for c in current if c in ['ESF', 'HFS_BH', 'SS']],
                            inline=True
                        ),
                        class_="classification-group"
                    ),
                ),
                style="padding: 0.8rem; border-bottom: 1px solid #e0e0e0; margin-bottom: 0.5rem;"
            )
        )

    # Live summary
    summary_counts = {}
    for feature, classes in classifications.items():
        for cls in classes:
            summary_counts[cls] = summary_counts.get(cls, 0) + 1
    summary_text = ", ".join([f"{count} {cls}" for cls, count in sorted(summary_counts.items())]) if summary_counts else "No features classified yet"

    return ui.TagList(
        ui.div(
            ui.p(f"📋 {len(feature_names)} features detected. Classify each feature below."),
            ui.p(f"📊 Summary: {summary_text}", style="font-weight: 600; color: #006994;"),
            class_="classification-summary"
        ),
        ui.input_action_button("reset_classifications", "🔄 Reset All Classifications", class_="btn-outline-secondary btn-sm", style="margin: 1rem 0;"),
        ui.div(*feature_rows, style="margin-top: 1rem;")
    )
```

**Step 3: Update _update_feature_classifications to read from new checkbox IDs**

Update the effect at line 1435 to collect from both `class_rarity_{feature}` and `class_role_{feature}` groups:

```python
@reactive.Effect
def _update_feature_classifications():
    df = uploaded_data.get()
    if df is None:
        if feature_classifications.get() != {}:
            feature_classifications.set({})
        return

    feature_names = df.columns[1:].tolist()
    if not feature_names:
        feature_classifications.set({})
        return

    new_classifications = {}
    for feature in feature_names:
        rarity = list(input[f"class_rarity_{feature}"]() or [])
        role = list(input[f"class_role_{feature}"]() or [])
        combined = rarity + role
        if combined:
            new_classifications[feature] = combined

    feature_classifications.set(new_classifications)
```

**Step 4: Add reset button handler**

```python
@reactive.Effect
@reactive.event(input.reset_classifications)
def _reset_classifications():
    feature_classifications.set({})
    ui.notification_show("All classifications cleared.", type="message", duration=3)
```

**Step 5: Commit**

```bash
git add app.py
git commit -m "feat: redesign feature classification UI with grouped layout, help text, and badges"
```

---

### Task 5: Add Descriptive AQ Status Badges

**Files:**
- Modify: `app.py:1835-1941` (results_ui function)

**Context:** Currently the AQ + EV Results tab at line 1907 shows "Active AQs" and "Inactive AQs" as plain comma-separated lists. Users don't know WHY an AQ is inactive. We need descriptive status badges that explain the reason.

**Step 1: Create AQ status analysis function**

Add a helper function before `results_ui()`:

```python
def get_aq_status(data_type, classifications, results):
    """Analyze each AQ and return status with explanation."""
    qual_aqs = ['AQ1', 'AQ3', 'AQ5', 'AQ7', 'AQ10', 'AQ12', 'AQ14']
    quant_aqs = ['AQ2', 'AQ4', 'AQ6', 'AQ8', 'AQ9', 'AQ11', 'AQ13', 'AQ15']

    has_rrf = any('RRF' in cls for cls in classifications.values())
    has_nrf = any('NRF' in cls for cls in classifications.values())
    has_esf = any('ESF' in cls for cls in classifications.values())
    has_hfs = any('HFS_BH' in cls for cls in classifications.values())
    has_ss = any('SS' in cls for cls in classifications.values())

    statuses = {}
    for aq in qual_aqs + quant_aqs:
        aq_num = int(aq[2:])
        has_data = aq in results.columns and not results[aq].isna().all()

        if data_type == 'qualitative' and aq in quant_aqs:
            statuses[aq] = ('inactive', 'Quantitative data required')
        elif data_type == 'quantitative' and aq in qual_aqs:
            statuses[aq] = ('inactive', 'Qualitative data required')
        elif aq_num in [5, 6] and not has_rrf:
            statuses[aq] = ('inactive', 'No features classified as RRF')
        elif aq_num in [7, 8] and not has_nrf:
            statuses[aq] = ('inactive', 'No features classified as NRF')
        elif aq_num in [10, 11] and not has_esf:
            statuses[aq] = ('inactive', 'No features classified as ESF')
        elif aq_num in [12, 13] and not has_hfs:
            statuses[aq] = ('inactive', 'No features classified as HFS/BH')
        elif aq_num in [14, 15] and not has_ss:
            statuses[aq] = ('inactive', 'No features classified as SS')
        elif has_data:
            statuses[aq] = ('active', 'Active')
        else:
            statuses[aq] = ('inactive', 'No data')

    return statuses
```

**Step 2: Replace the Active/Inactive section in results_ui**

Replace lines 1913-1929 with the new badge-based display:

```python
user_classifications = feature_classifications.get() or {}
aq_statuses = get_aq_status(data_type, user_classifications, results)

active_badges = []
inactive_badges = []
for aq, (status, reason) in sorted(aq_statuses.items(), key=lambda x: int(x[0][2:])):
    if status == 'active':
        active_badges.append(ui.span(
            aq, style="display: inline-block; padding: 4px 10px; margin: 2px; border-radius: 12px; "
            "background: #28a745; color: white; font-size: 0.85rem; font-weight: 600;"
        ))
    else:
        inactive_badges.append(ui.span(
            f"{aq}: {reason}",
            style="display: inline-block; padding: 4px 10px; margin: 2px; border-radius: 12px; "
            "background: #e0e0e0; color: #666; font-size: 0.8rem;"
        ))
```

Render them in a summary card with "Active" and "Inactive (with reasons)" sections.

**Step 3: Add EV calculation info box**

Add a collapsible info box above the results table:

```python
ui.div(
    ui.details(
        ui.summary(ui.strong("ℹ️ How is EV calculated?")),
        ui.p("EV = MAX of all active AQ scores for each subzone. "
             "Each AQ evaluates a different aspect of ecological value. "
             "The highest-scoring AQ determines the EV for that subzone."),
        ui.p(f"Active AQs for your data: {', '.join(aq for aq, (s, _) in aq_statuses.items() if s == 'active')}"),
        ui.p("To activate more AQs, classify features in the EC Features tab "
             "(e.g., mark features as RRF to enable AQ5/AQ6)."),
    ),
    style="margin-bottom: 1.5rem; padding: 1rem; background: #f5f5f5; border-radius: 8px;"
)
```

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add descriptive AQ status badges with explanations and EV info box"
```

---

### Task 6: Highlight Max AQ in Results Table

**Files:**
- Modify: `app.py:1965-2050` (results_table_with_tooltips function)

**Context:** The results table at line 1965 shows AQ scores and EV per subzone. Users can't easily see which AQ determines the EV (max value). We need to highlight the max AQ cell in each row.

**Step 1: Add highlight CSS**

Add to `custom_css`:

```css
.aq-max-cell {
    background-color: #c8e6c9 !important;
    font-weight: 700;
    border: 2px solid #4caf50;
}
```

**Step 2: Update results_table_with_tooltips to mark max AQ cells**

In the HTML table generation logic, for each row identify which AQ column has the maximum value (matching EV), and add the `aq-max-cell` class to that `<td>`:

```python
# For each row, find the AQ that equals EV
aq_cols = [col for col in display_df.columns if col.startswith('AQ')]
for _, row in display_df.iterrows():
    aq_values = {col: row[col] for col in aq_cols if pd.notna(row[col]) and row[col] > 0}
    max_aq = max(aq_values, key=aq_values.get) if aq_values else None
    # When rendering the cell for max_aq, add class="aq-max-cell"
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: highlight max AQ cell that determines EV in results table"
```

---

### Task 7: Integration Test

**Files:**
- Modify: none (manual testing)

**Step 1: Run the app**

```bash
shiny run app.py --port 8790
```

**Step 2: Test validation report**

1. Upload `sample_data.csv`
2. Verify validation report card appears with row/column counts, no warnings
3. Try uploading a malformed file and verify error notification appears

**Step 3: Test configurable thresholds**

1. Change LRF threshold slider from 5% to 10%
2. Verify AQ results recalculate
3. Change percentile to 90th, verify AQ9 values change
4. Change display limit to "All rows", verify full table shown

**Step 4: Test feature classification UI**

1. Go to EC Features tab
2. Verify grouped layout with Rarity and Ecological Role sections
3. Classify a feature as RRF, verify badge appears
4. Verify live summary updates
5. Click Reset All, verify all cleared
6. Verify AQ5/AQ6 activate after classifying a feature as RRF

**Step 5: Test AQ status badges**

1. Go to AQ + EV Results tab
2. Verify active AQs shown as green badges
3. Verify inactive AQs show reason (e.g., "No features classified as RRF")
4. Verify "How is EV calculated?" info box is collapsible
5. Verify max AQ is highlighted green in results table

**Step 6: Test spatial upload feedback**

1. Upload test_grid.geojson
2. Verify colour-coded match status (green for full match)
3. Verify error notification if uploading an invalid file

**Step 7: Commit any fixes**

```bash
git add app.py
git commit -m "fix: integration test fixes for UX improvements"
```
