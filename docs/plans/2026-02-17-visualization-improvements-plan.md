# Visualization Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add three new chart types (AQ Breakdown, Radar, AQ Heatmap) to the Visualization tab.

**Architecture:** Extend the existing `visualization_ui()` render function in `app.py` with new `elif` branches for each chart type. Add a conditional subzone selector for the radar chart. All charts use Plotly (`go` and `px`), which is already imported.

**Tech Stack:** Python Shiny, Plotly (`plotly.graph_objects`, `plotly.express`), pandas

---

### Task 1: Add AQ Breakdown by Subzone chart

**Files:**
- Modify: `app.py:798` (add dropdown option)
- Modify: `app.py:2697-2698` (add new elif branch before the `else`)

**Step 1: Add dropdown option**

In `app.py` line 798, change the choices list:

```python
# Before:
choices=["EV by Subzone", "Feature Distribution", "AQ Scores"]

# After:
choices=["EV by Subzone", "Feature Distribution", "AQ Scores",
         "AQ Breakdown by Subzone", "AQ Radar Comparison", "AQ Heatmap"]
```

**Step 2: Add AQ Breakdown chart**

In `app.py`, before the `else:  # AQ Scores` branch (line 2698), add a new `elif` block:

```python
        elif plot_type == "AQ Breakdown by Subzone":
            # Grouped bar chart showing active AQ scores per subzone with EV line
            aq_columns = [col for col in results.columns if col.startswith('AQ')]
            if not aq_columns:
                return ui.p("No AQ scores available")

            # Filter to active AQs (those with at least one non-zero value)
            active_aqs = [col for col in aq_columns if results[col].abs().sum() > 0]
            if not active_aqs:
                return ui.p("No active AQ scores to display. All AQ values are zero.")

            color_scheme = input.color_scheme().lower()

            fig = go.Figure()

            # Add bars for each active AQ
            colors = px.colors.qualitative.Plotly
            for i, aq in enumerate(active_aqs):
                fig.add_trace(go.Bar(
                    name=aq,
                    x=results['Subzone ID'],
                    y=results[aq],
                    marker_color=colors[i % len(colors)],
                    hovertemplate=f'{aq}: %{{y:.2f}}<extra></extra>'
                ))

            # Add EV line overlay
            fig.add_trace(go.Scatter(
                name='EV',
                x=results['Subzone ID'],
                y=results['EV'],
                mode='lines+markers',
                line=dict(color='black', width=2, dash='dot'),
                marker=dict(size=6, color='black'),
                hovertemplate='EV: %{y:.2f}<extra></extra>'
            ))

            fig.update_layout(
                title="AQ Score Breakdown by Subzone",
                xaxis_title="Subzone ID",
                yaxis_title="Score (0-5)",
                yaxis=dict(range=[0, 5.5]),
                barmode='group',
                height=550,
                hovermode='x unified',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )

            return ui.HTML(fig.to_html(include_plotlyjs="cdn", div_id="aq_breakdown_plot"))
```

**Step 3: Restart app and test**

Run: `shiny run app.py --port 8790`

- Upload `sample_data.csv`
- Go to Visualization tab
- Select "AQ Breakdown by Subzone"
- Verify grouped bars appear with EV dotted line overlay
- Verify hover shows AQ name and score

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add AQ Breakdown by Subzone grouped bar chart with EV line"
```

---

### Task 2: Add Radar/Spider Chart

**Files:**
- Modify: `app.py:793-805` (add conditional subzone selector in sidebar)
- Modify: `app.py` visualization_ui function (add new elif branch)

**Step 1: Add subzone selector to sidebar**

In `app.py`, inside the Visualization tab sidebar (after the color_scheme select, around line 804), add a conditional subzone selector. Replace the sidebar section:

```python
# Before (lines 793-805):
                ui.sidebar(
                    ui.h5("🎨 Chart Options", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_select(
                        "plot_type",
                        "Visualization Type:",
                        choices=["EV by Subzone", "Feature Distribution", "AQ Scores",
                                 "AQ Breakdown by Subzone", "AQ Radar Comparison", "AQ Heatmap"]
                    ),
                    ui.input_select(
                        "color_scheme",
                        "Color Scheme:",
                        choices=["Viridis", "Plasma", "Blues", "Greens"]
                    ),
                    width=280
                ),

# After:
                ui.sidebar(
                    ui.h5("🎨 Chart Options", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_select(
                        "plot_type",
                        "Visualization Type:",
                        choices=["EV by Subzone", "Feature Distribution", "AQ Scores",
                                 "AQ Breakdown by Subzone", "AQ Radar Comparison", "AQ Heatmap"]
                    ),
                    ui.input_select(
                        "color_scheme",
                        "Color Scheme:",
                        choices=["Viridis", "Plasma", "Blues", "Greens"]
                    ),
                    ui.panel_conditional(
                        "input.plot_type === 'AQ Radar Comparison'",
                        ui.input_selectize(
                            "radar_subzones",
                            "Select Subzones to Compare (max 5):",
                            choices=[],
                            multiple=True,
                            options={"maxItems": 5, "placeholder": "Upload data first..."}
                        )
                    ),
                    width=280
                ),
```

**Step 2: Add server-side logic to populate radar subzone choices**

In the server function, add an effect to update the radar subzone selector when data is uploaded. Place this near the other `@reactive.Effect` handlers (around the visualization section):

```python
    @reactive.Effect
    @reactive.event(uploaded_data)
    def _update_radar_choices():
        df = uploaded_data.get()
        if df is not None and 'Subzone ID' in df.columns:
            subzone_ids = df['Subzone ID'].tolist()
            ui.update_selectize(
                "radar_subzones",
                choices=subzone_ids,
                selected=subzone_ids[:3]  # Default: first 3
            )
```

**Step 3: Add radar chart rendering**

In the `visualization_ui()` function, add the radar chart elif branch (after the AQ Breakdown branch):

```python
        elif plot_type == "AQ Radar Comparison":
            # Radar chart comparing AQ profiles across selected subzones
            selected = list(input.radar_subzones()) if input.radar_subzones() else []
            if not selected:
                return ui.div(
                    ui.p("👈 Select 1-5 subzones from the sidebar to compare their AQ profiles.",
                         style="font-size: 1.1rem; text-align: center; color: #6c757d; padding: 2rem;")
                )

            aq_columns = [col for col in results.columns if col.startswith('AQ')]
            if not aq_columns:
                return ui.p("No AQ scores available")

            fig = go.Figure()

            colors = px.colors.qualitative.Plotly
            for i, subzone in enumerate(selected):
                row = results[results['Subzone ID'] == subzone]
                if row.empty:
                    continue
                values = row[aq_columns].values.flatten().tolist()
                values.append(values[0])  # Close the polygon
                categories = aq_columns + [aq_columns[0]]

                fig.add_trace(go.Scatterpolar(
                    r=values,
                    theta=categories,
                    fill='toself',
                    fillcolor=f'rgba({",".join(str(int(c*255)) for c in px.colors.convert_colors_to_same_type(colors[i % len(colors)])[0][0][:3])},0.15)',
                    name=str(subzone),
                    line=dict(color=colors[i % len(colors)], width=2),
                    hovertemplate='%{theta}: %{r:.2f}<extra>' + str(subzone) + '</extra>'
                ))

            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 5]),
                    angularaxis=dict(direction="clockwise")
                ),
                title="AQ Profile Comparison by Subzone",
                height=600,
                showlegend=True,
                legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
                paper_bgcolor='rgba(0,0,0,0)'
            )

            return ui.HTML(fig.to_html(include_plotlyjs="cdn", div_id="radar_plot"))
```

Note: The `fillcolor` rgba conversion above may be complex. A simpler approach is to use a predefined list of rgba fill colors:

```python
            fill_colors = [
                'rgba(99,110,250,0.15)', 'rgba(239,85,59,0.15)', 'rgba(0,204,150,0.15)',
                'rgba(171,99,250,0.15)', 'rgba(255,161,90,0.15)'
            ]
```

And use `fillcolor=fill_colors[i % len(fill_colors)]` instead.

**Step 4: Restart app and test**

- Select "AQ Radar Comparison" from dropdown
- Verify subzone selector appears
- Select 2-3 subzones
- Verify radar chart renders with polygons

**Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add AQ Radar Comparison chart with subzone selector"
```

---

### Task 3: Add AQ × Subzone Heatmap

**Files:**
- Modify: `app.py` visualization_ui function (add new elif branch)

**Step 1: Add AQ Heatmap rendering**

In the `visualization_ui()` function, add an elif branch (after the radar branch, before the `else: # AQ Scores`):

```python
        elif plot_type == "AQ Heatmap":
            # Heatmap of AQ scores across subzones, sorted by EV descending
            aq_columns = [col for col in results.columns if col.startswith('AQ')]
            if not aq_columns:
                return ui.p("No AQ scores available")

            display_cols = aq_columns + ['EV']
            sorted_results = results.sort_values('EV', ascending=True)

            z_data = sorted_results[display_cols].values
            x_labels = display_cols
            y_labels = sorted_results['Subzone ID'].tolist()

            color_scheme = input.color_scheme()

            fig = go.Figure(data=go.Heatmap(
                z=z_data,
                x=x_labels,
                y=y_labels,
                colorscale=color_scheme,
                zmin=0,
                zmax=5,
                text=np.round(z_data, 1),
                texttemplate="%{text}",
                textfont={"size": 10},
                hoverongaps=False,
                colorbar=dict(title="Score")
            ))

            fig.update_layout(
                title="AQ Scores × Subzones (sorted by EV)",
                xaxis_title="Assessment Questions",
                yaxis_title="Subzone ID",
                height=max(450, len(sorted_results) * 25),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )

            return ui.HTML(fig.to_html(include_plotlyjs="cdn", div_id="aq_heatmap_plot"))
```

**Step 2: Restart app and test**

- Select "AQ Heatmap" from dropdown
- Verify heatmap renders with AQ1-AQ15 + EV columns
- Verify subzones sorted by EV descending (highest at top visually)
- Verify cell annotations show score values
- Verify colour scheme selector changes heatmap colours

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add AQ × Subzone heatmap with score annotations"
```

---

### Task 4: Integration test

**Files:**
- No file changes — browser-based testing only

**Step 1: Start app and upload data**

```bash
shiny run app.py --port 8790
```

Upload `sample_data.csv`, verify data loads.

**Step 2: Test each chart type**

Cycle through all 6 dropdown options:
1. "EV by Subzone" — bar chart renders
2. "Feature Distribution" — heatmap renders
3. "AQ Scores" — histogram renders
4. "AQ Breakdown by Subzone" — grouped bars + EV line
5. "AQ Radar Comparison" — subzone selector appears, radar renders
6. "AQ Heatmap" — scored heatmap renders

**Step 3: Test colour scheme**

Switch colour scheme for each chart type and verify it updates.

**Step 4: Test radar subzone selection**

- Select 1 subzone → single polygon
- Select 5 subzones → 5 overlapping polygons
- Deselect all → "Select subzones" message shown

**Step 5: Verify no console errors**

Check browser console for JavaScript errors.

**Step 6: Commit any fixes**

```bash
git add app.py
git commit -m "fix: address integration test issues in visualization charts"
```
