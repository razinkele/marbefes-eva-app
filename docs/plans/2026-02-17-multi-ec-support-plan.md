# Multi-EC Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable multiple Ecosystem Components in a single session with aggregated Total EV.

**Architecture:** Add `ec_store` and `current_ec` reactive values. Build EC management UI in the Data Input sidebar. Update Total EV tab to aggregate across saved ECs. Existing single-EC workflow stays unchanged; multi-EC wraps around it via save/restore.

**Tech Stack:** Python Shiny, pandas, reactive values

---

### Task 1: Add EC store reactive values and save/restore logic

**Files:**
- Modify: `app.py:924-935` (add new reactive values after existing ones)
- Modify: `app.py` server function (add save/restore/delete/new handler functions)

**Step 1: Add reactive values**

After line 935 (`validation_report = reactive.Value(None)`), add:

```python
    # Multi-EC support
    ec_store = reactive.Value({})      # {ec_name: {data, data_type, classifications, results}}
    current_ec = reactive.Value(None)  # Name of the active EC
```

**Step 2: Add save EC handler**

Add a reactive effect that fires when a "save_ec" action button is clicked. Place this in the server function near the other button handlers:

```python
    @reactive.Effect
    @reactive.event(input.save_ec)
    def _save_current_ec():
        ec_name = input.ec_name().strip()
        if not ec_name:
            ui.notification_show("Please enter an EC Name before saving.", type="warning")
            return

        df = uploaded_data.get()
        if df is None:
            ui.notification_show("No data uploaded. Upload a CSV first.", type="warning")
            return

        results = calculate_results()
        store = ec_store.get().copy()
        store[ec_name] = {
            'data': df.copy(),
            'data_type': input.data_type(),
            'classifications': feature_classifications.get().copy(),
            'results': results.copy() if results is not None else None,
            'feature_count': len([c for c in df.columns if c != 'Subzone ID']),
        }
        ec_store.set(store)
        current_ec.set(ec_name)
        ui.notification_show(f"EC '{ec_name}' saved successfully.", type="message")
```

**Step 3: Add restore EC handler**

Add a handler that restores a saved EC when the user selects it from a dropdown:

```python
    @reactive.Effect
    @reactive.event(input.select_ec)
    def _restore_ec():
        ec_name = input.select_ec()
        if not ec_name or ec_name == "":
            return
        store = ec_store.get()
        if ec_name not in store:
            return

        ec = store[ec_name]
        uploaded_data.set(ec['data'].copy())
        feature_classifications.set(ec['classifications'].copy())
        detected_data_type.set(ec['data_type'])
        current_ec.set(ec_name)

        # Update the data type dropdown to match
        ui.update_select("data_type", selected=ec['data_type'])
        # Update EC name field
        ui.update_text("ec_name", value=ec_name)

        ui.notification_show(f"Switched to EC '{ec_name}'.", type="message")
```

**Step 4: Add new EC handler**

```python
    @reactive.Effect
    @reactive.event(input.new_ec)
    def _new_ec():
        uploaded_data.set(None)
        feature_classifications.set({})
        detected_data_type.set(None)
        current_ec.set(None)
        ui.update_text("ec_name", value="")
        ui.update_select("data_type", selected="TO SPECIFY")
        ui.notification_show("Ready for a new EC. Upload a CSV file.", type="message")
```

**Step 5: Add delete EC handler**

```python
    @reactive.Effect
    @reactive.event(input.delete_ec)
    def _delete_ec():
        ec_name = input.select_ec()
        if not ec_name:
            return
        store = ec_store.get().copy()
        if ec_name in store:
            del store[ec_name]
            ec_store.set(store)
            if current_ec.get() == ec_name:
                current_ec.set(None)
            ui.notification_show(f"EC '{ec_name}' removed.", type="message")
            # Update the select dropdown
            ui.update_select("select_ec", choices=[""] + list(store.keys()), selected="")
```

**Step 6: Commit**

```bash
git add app.py
git commit -m "feat: add EC store reactive values and save/restore/delete handlers"
```

---

### Task 2: Add EC management UI to Data Input sidebar

**Files:**
- Modify: `app.py:544-568` (add EC management section above metadata)

**Step 1: Add EC management panel**

In the Data Input sidebar, BEFORE the metadata section (before line 545 `ui.div(` that contains the metadata heading), insert a new EC management section:

```python
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
```

**Step 2: Add EC list summary renderer**

In the server function, add a renderer that shows the saved EC count and details:

```python
    @output
    @render.ui
    def ec_list_summary():
        store = ec_store.get()
        if not store:
            return ui.p("No ECs saved yet.", style="color: #999; font-size: 0.85rem; margin-top: 0.5rem;")

        active = current_ec.get()
        items = []
        for name, ec in store.items():
            badge_color = "#28a745" if name == active else "#6c757d"
            dt_badge = "Q" if ec['data_type'] == 'qualitative' else "QN"
            items.append(ui.div(
                ui.span(f"● {name}", style=f"font-weight: {'600' if name == active else '400'}; color: {badge_color};"),
                ui.span(f" ({dt_badge}, {ec['feature_count']} features)", style="color: #999; font-size: 0.8rem;"),
                style="margin: 0.2rem 0;"
            ))
        return ui.div(
            ui.p(f"📋 {len(store)} EC(s) saved:", style="font-weight: 600; margin: 0.5rem 0 0.3rem 0; font-size: 0.9rem;"),
            *items
        )
```

**Step 3: Add effect to update select_ec choices when store changes**

```python
    @reactive.Effect
    @reactive.event(ec_store)
    def _update_ec_selector():
        store = ec_store.get()
        choices = [""] + list(store.keys())
        current = current_ec.get() or ""
        ui.update_select("select_ec", choices=choices, selected=current)
```

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add EC management UI with save/restore/delete controls"
```

---

### Task 3: Update Total EV tab for multi-EC aggregation

**Files:**
- Modify: `app.py:2370-2421` (rewrite total_ev_ui and total_ev_table)

**Step 1: Rewrite total_ev_ui**

Replace the existing `total_ev_ui()` function with a version that aggregates across all saved ECs:

```python
    @output
    @render.ui
    def total_ev_ui():
        store = ec_store.get()

        # If multiple ECs saved, aggregate across them
        if len(store) >= 2:
            # Build aggregation DataFrame
            ev_frames = {}
            for ec_name, ec in store.items():
                if ec['results'] is not None:
                    ev_frames[ec_name] = ec['results'][['Subzone ID', 'EV']].rename(columns={'EV': ec_name})

            if not ev_frames:
                return ui.p("No ECs have computed results. Configure and save ECs first.")

            # Merge all EV columns on Subzone ID
            merged = None
            for ec_name, df in ev_frames.items():
                if merged is None:
                    merged = df
                else:
                    merged = merged.merge(df, on='Subzone ID', how='outer')

            # Fill NaN with 0 and compute Total EV
            ec_names = list(ev_frames.keys())
            merged[ec_names] = merged[ec_names].fillna(0)
            merged['Total EV'] = merged[ec_names].sum(axis=1)

            total_ev = merged['Total EV'].sum()
            avg_ev = merged['Total EV'].mean()
            max_ev = merged['Total EV'].max()
            min_ev = merged['Total EV'].min()

            # Per-EC summary
            ec_summary_rows = []
            for ec_name in ec_names:
                ec = store[ec_name]
                ec_summary_rows.append({
                    'EC Name': ec_name,
                    'Data Type': ec['data_type'],
                    'Features': ec['feature_count'],
                    'Mean EV': f"{merged[ec_name].mean():.2f}"
                })
            ec_summary_df = pd.DataFrame(ec_summary_rows)

            return ui.TagList(
                ui.card(
                    ui.card_header(f"🏆 Aggregated Total EV ({len(ec_names)} ECs)"),
                    ui.layout_column_wrap(
                        ui.value_box("Total EV (Sum)", f"{total_ev:.2f}", theme="primary"),
                        ui.value_box("Average Total EV", f"{avg_ev:.2f}", theme="info"),
                        ui.value_box("Max Total EV", f"{max_ev:.2f}", theme="success"),
                        ui.value_box("Min Total EV", f"{min_ev:.2f}", theme="warning"),
                        width=1/4
                    )
                ),
                ui.hr(),
                ui.h5("📋 Per-EC Summary"),
                ui.output_table("ec_summary_table"),
                ui.hr(),
                ui.h5("📊 Aggregated EV by Subzone"),
                ui.output_table("total_ev_table")
            )

        # Single EC or no ECs: use existing behavior
        results = calculate_results()
        if results is not None:
            total_ev = results['EV'].sum()
            avg_ev = results['EV'].mean()
            max_ev = results['EV'].max()
            min_ev = results['EV'].min()

            return ui.TagList(
                ui.card(
                    ui.card_header("Summary Statistics"),
                    ui.layout_column_wrap(
                        ui.value_box("Total EV", f"{total_ev:.2f}", theme="primary"),
                        ui.value_box("Average EV", f"{avg_ev:.2f}", theme="info"),
                        ui.value_box("Max EV", f"{max_ev:.2f}", theme="success"),
                        ui.value_box("Min EV", f"{min_ev:.2f}", theme="warning"),
                        width=1/4
                    )
                ),
                ui.hr(),
                ui.h5("Detailed EV by Subzone"),
                ui.output_table("total_ev_table")
            )
        return ui.p("No data available. Please upload data and calculate results.")
```

**Step 2: Update total_ev_table to handle multi-EC**

Replace the existing `total_ev_table()`:

```python
    @output
    @render.table
    def total_ev_table():
        store = ec_store.get()
        display_limit = int(input.results_display_limit())

        if len(store) >= 2:
            ev_frames = {}
            for ec_name, ec in store.items():
                if ec['results'] is not None:
                    ev_frames[ec_name] = ec['results'][['Subzone ID', 'EV']].rename(columns={'EV': ec_name})

            if not ev_frames:
                return pd.DataFrame()

            merged = None
            for ec_name, df in ev_frames.items():
                if merged is None:
                    merged = df
                else:
                    merged = merged.merge(df, on='Subzone ID', how='outer')

            ec_names = list(ev_frames.keys())
            merged[ec_names] = merged[ec_names].fillna(0)
            merged['Total EV'] = merged[ec_names].sum(axis=1)
            merged = merged.sort_values('Total EV', ascending=False)

            return merged.head(display_limit) if display_limit > 0 else merged

        results = calculate_results()
        if results is not None:
            df = results[['Subzone ID', 'EV']]
            return df.head(display_limit) if display_limit > 0 else df
        return pd.DataFrame()
```

**Step 3: Add ec_summary_table renderer**

```python
    @output
    @render.table
    def ec_summary_table():
        store = ec_store.get()
        if len(store) < 2:
            return pd.DataFrame()

        rows = []
        for ec_name, ec in store.items():
            mean_ev = ec['results']['EV'].mean() if ec['results'] is not None else 0
            rows.append({
                'EC Name': ec_name,
                'Data Type': ec['data_type'],
                'Features': ec['feature_count'],
                'Mean EV': round(mean_ev, 2)
            })
        return pd.DataFrame(rows)
```

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: update Total EV tab with multi-EC aggregation"
```

---

### Task 4: Update Excel export for multi-EC

**Files:**
- Modify: `app.py` download_results function (~line 2424)

**Step 1: Add multi-EC sheets to export**

At the beginning of `download_results()`, check if multiple ECs exist. If so, add per-EC sheets and an aggregation sheet. Wrap the existing export logic in an `if/else`:

After the existing single-EC export writes its sheets, add:

```python
        # If multiple ECs, add per-EC sheets and aggregation
        store = ec_store.get()
        if len(store) >= 2:
            # Aggregation sheet
            ev_frames = {}
            for ec_name, ec in store.items():
                if ec['results'] is not None:
                    ev_frames[ec_name] = ec['results'][['Subzone ID', 'EV']].rename(columns={'EV': ec_name})

            if ev_frames:
                merged = None
                for ec_name, df_ev in ev_frames.items():
                    if merged is None:
                        merged = df_ev
                    else:
                        merged = merged.merge(df_ev, on='Subzone ID', how='outer')
                ec_names = list(ev_frames.keys())
                merged[ec_names] = merged[ec_names].fillna(0)
                merged['Total EV'] = merged[ec_names].sum(axis=1)
                merged = merged.sort_values('Total EV', ascending=False)
                merged.to_excel(writer, sheet_name='Aggregated EV', index=False, startrow=2)
                ws = writer.sheets['Aggregated EV']
                ws.cell(row=1, column=1, value='Aggregated Ecological Value Across All ECs')

            # Per-EC result sheets
            for ec_name, ec in store.items():
                if ec['results'] is not None:
                    sheet_name = f"EC - {ec_name}"[:31]  # Excel 31-char limit
                    ec['results'].to_excel(writer, sheet_name=sheet_name, index=False, startrow=2)
                    ws = writer.sheets[sheet_name]
                    ws.cell(row=1, column=1, value=f"Results for EC: {ec_name} ({ec['data_type']})")
```

This code must be placed inside the `with pd.ExcelWriter(...)` block, after the existing sheets are written.

**Step 2: Commit**

```bash
git add app.py
git commit -m "feat: add multi-EC sheets and aggregation to Excel export"
```

---

### Task 5: Auto-save current EC results on calculation

**Files:**
- Modify: `app.py` (add effect near calculate_results)

**Step 1: Add auto-update of stored EC results**

When the user recalculates (changes classifications, thresholds, etc.), auto-update the stored EC if it's already saved:

```python
    @reactive.Effect
    @reactive.event(calculate_results)
    def _auto_update_stored_ec():
        ec_name = current_ec.get()
        if ec_name is None:
            return
        store = ec_store.get()
        if ec_name not in store:
            return
        results = calculate_results()
        df = uploaded_data.get()
        if results is not None and df is not None:
            updated = store.copy()
            updated[ec_name]['results'] = results.copy()
            updated[ec_name]['classifications'] = feature_classifications.get().copy()
            updated[ec_name]['data_type'] = input.data_type()
            ec_store.set(updated)
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "feat: auto-update stored EC results when recalculated"
```

---

### Task 6: Integration test

**Files:**
- No file changes — browser-based testing only

**Step 1: Start app and test single-EC workflow**

Upload `sample_data.csv`, enter EC Name "Fish", save it. Verify EC appears in the list and selector.

**Step 2: Test adding a second EC**

Click "New EC", upload `sample_data_with_rare_features.csv` (or reuse sample_data.csv), enter EC Name "Habitats", configure some features differently, save it. Verify both ECs in the list.

**Step 3: Test Total EV aggregation**

Go to Total EV tab. Verify:
- Per-EC summary table shows 2 rows (Fish, Habitats)
- Aggregated table shows Subzone ID | Fish | Habitats | Total EV
- Value boxes show aggregated statistics

**Step 4: Test EC switching**

Select "Fish" from the dropdown. Verify data and classifications restore correctly. Switch to "Habitats". Verify it switches.

**Step 5: Test delete**

Delete "Habitats". Verify only "Fish" remains. Total EV reverts to single-EC view.

**Step 6: Test export**

Download Excel with 2 ECs saved. Verify it contains per-EC sheets and Aggregated EV sheet.

**Step 7: Commit any fixes**

```bash
git add app.py
git commit -m "fix: address integration test issues in multi-EC support"
```
