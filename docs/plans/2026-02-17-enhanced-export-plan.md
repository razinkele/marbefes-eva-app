# Enhanced Excel Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add professional styling, embedded charts, and multi-EC summary upgrade to the Excel export.

**Architecture:** Add a reusable `style_worksheet()` helper inside `download_results()` to apply formatting consistently. Add chart generation using Plotly + kaleido for image export. Update the Summary sheet to include multi-EC metadata when applicable. All changes in `app.py`.

**Tech Stack:** Python Shiny, openpyxl (Font, PatternFill, Border, Alignment, Side, numbers), plotly.io, kaleido, pandas

---

### Task 1: Add openpyxl imports and kaleido dependency

**Files:**
- Modify: `app.py:11-24` (add openpyxl styling imports)
- Modify: `requirements.txt` (add kaleido)

**Step 1: Add openpyxl imports**

At the top of `app.py`, after `import json` (line 24), add:

```python
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment, numbers
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.drawing.image import Image as XlImage
import plotly.io as pio
```

**Step 2: Add kaleido to requirements.txt**

Append `kaleido>=0.2.1` to `requirements.txt`.

**Step 3: Install kaleido**

Run: `pip install kaleido`

**Step 4: Commit**

```bash
git add app.py requirements.txt
git commit -m "feat: add openpyxl styling imports and kaleido dependency"
```

---

### Task 2: Add style_worksheet helper and apply to all existing sheets

**Files:**
- Modify: `app.py:2746-2760` (replace formatting section inside download_results)

**Step 1: Add style_worksheet helper function**

Inside `download_results()`, REPLACE the existing formatting section (lines 2746-2760):

```python
            # Format worksheets
            workbook = writer.book

            # Format Summary sheet
            summary_sheet = workbook['Summary & Metadata']
            summary_sheet.column_dimensions['A'].width = 30
            summary_sheet.column_dimensions['B'].width = 60

            # Format methodology sheet
            methodology_sheet = workbook['AQ Methodology']
            methodology_sheet.column_dimensions['A'].width = 8
            methodology_sheet.column_dimensions['B'].width = 45
            methodology_sheet.column_dimensions['C'].width = 50
            methodology_sheet.column_dimensions['D'].width = 15
            methodology_sheet.column_dimensions['E'].width = 40
```

With the following (inside the `with pd.ExcelWriter` block, same indentation):

```python
            # --- Professional Styling ---
            workbook = writer.book

            # Style constants
            header_font = Font(bold=True, color="FFFFFF", size=11)
            header_fill = PatternFill(start_color="006994", end_color="006994", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            thin_border = Border(
                left=Side(style='thin', color='D0D0D0'),
                right=Side(style='thin', color='D0D0D0'),
                top=Side(style='thin', color='D0D0D0'),
                bottom=Side(style='thin', color='D0D0D0')
            )
            alt_row_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

            def style_worksheet(ws, has_data=True, freeze=True, autofilter=True, start_row=1):
                """Apply professional styling to a worksheet."""
                if ws.max_row < start_row or ws.max_column < 1:
                    return

                # Header row styling
                for cell in ws[start_row]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
                    cell.border = thin_border

                if has_data and ws.max_row > start_row:
                    # Autofilter
                    if autofilter:
                        ws.auto_filter.ref = f"A{start_row}:{get_column_letter(ws.max_column)}{ws.max_row}"

                    # Freeze panes below header
                    if freeze:
                        ws.freeze_panes = f"A{start_row + 1}"

                    # Data rows: borders + alternating fill
                    for row_idx in range(start_row + 1, ws.max_row + 1):
                        for cell in ws[row_idx]:
                            cell.border = thin_border
                            if (row_idx - start_row) % 2 == 0:
                                cell.fill = alt_row_fill

                # Auto-size columns (estimate from content)
                for col_idx in range(1, ws.max_column + 1):
                    max_len = 0
                    col_letter = get_column_letter(col_idx)
                    for row_idx in range(start_row, min(ws.max_row + 1, start_row + 50)):
                        cell = ws.cell(row=row_idx, column=col_idx)
                        if cell.value:
                            max_len = max(max_len, len(str(cell.value)))
                    ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 60)

            # Sheet tab colors
            tab_colors = {
                'Summary & Metadata': '006994',
                'Original Data': '28A745',
                'AQ & EV Results': 'FD7E14',
                'Feature Classifications': '28A745',
                'AQ Methodology': '6C757D',
                'EV Calculation': '6C757D',
                'Complete Results': 'FD7E14',
            }

            # Apply styling to standard sheets
            for sheet_name in workbook.sheetnames:
                ws = workbook[sheet_name]
                if sheet_name in tab_colors:
                    ws.sheet_properties.tabColor = tab_colors[sheet_name]

                # Multi-EC sheets have data starting at row 3 (title in row 1, header in row 3)
                if sheet_name.startswith('EC - ') or sheet_name == 'Aggregated EV':
                    ws.sheet_properties.tabColor = '6F42C1'
                    style_worksheet(ws, start_row=3)
                else:
                    style_worksheet(ws)
```

**Step 2: Restart app and test**

Run: `shiny run app.py --port 8790`

Upload data, set data type, go to Total EV tab, click download. Open the Excel file and verify:
- Headers are blue with white bold text
- Alternating row shading on data sheets
- Autofilter arrows on headers
- Freeze panes (scroll down, header stays)
- Tab colors match spec
- Column widths auto-sized

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add professional styling to all Excel export sheets"
```

---

### Task 3: Add conditional formatting on EV columns

**Files:**
- Modify: `app.py` (inside the styling section added in Task 2, after tab color application)

**Step 1: Add EV conditional formatting**

After the `for sheet_name in workbook.sheetnames:` loop (from Task 2), add:

```python
            # Conditional formatting: color scale on EV columns
            ev_color_rule = ColorScaleRule(
                start_type='num', start_value=0, start_color='F8696B',    # Red
                mid_type='num', mid_value=2.5, mid_color='FFEB84',        # Yellow
                end_type='num', end_value=5, end_color='63BE7B'           # Green
            )

            # Apply to sheets that have EV columns
            ev_sheets = ['AQ & EV Results', 'Complete Results']
            if 'Aggregated EV' in workbook.sheetnames:
                ev_sheets.append('Aggregated EV')

            for sheet_name in ev_sheets:
                if sheet_name not in workbook.sheetnames:
                    continue
                ws = workbook[sheet_name]
                start_row = 3 if sheet_name == 'Aggregated EV' else 1

                # Find EV column(s)
                for col_idx in range(1, ws.max_column + 1):
                    header_cell = ws.cell(row=start_row, column=col_idx)
                    if header_cell.value and ('EV' in str(header_cell.value)):
                        col_letter = get_column_letter(col_idx)
                        data_range = f"{col_letter}{start_row + 1}:{col_letter}{ws.max_row}"
                        ws.conditional_formatting.add(data_range, ev_color_rule)

                        # Also format as 2 decimal places
                        for row_idx in range(start_row + 1, ws.max_row + 1):
                            cell = ws.cell(row=row_idx, column=col_idx)
                            cell.number_format = '0.00'

            # Format AQ columns as 2 decimal places
            for sheet_name in ['AQ & EV Results', 'Complete Results']:
                if sheet_name not in workbook.sheetnames:
                    continue
                ws = workbook[sheet_name]
                for col_idx in range(1, ws.max_column + 1):
                    header_cell = ws.cell(row=1, column=col_idx)
                    if header_cell.value and str(header_cell.value).startswith('AQ'):
                        for row_idx in range(2, ws.max_row + 1):
                            ws.cell(row=row_idx, column=col_idx).number_format = '0.00'
```

**Step 2: Test**

Download Excel, open AQ & EV Results sheet. Verify:
- EV column has green-yellow-red gradient
- AQ and EV values show 2 decimal places

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add conditional formatting and number formats to EV/AQ columns"
```

---

### Task 4: Add embedded chart sheets

**Files:**
- Modify: `app.py` (inside download_results, after multi-EC sheets but before styling section)

**Step 1: Add chart generation code**

After the multi-EC sheets block (after line 2744) and BEFORE the styling section, insert:

```python
            # --- Embedded Chart Sheets ---
            try:
                # Chart 1: EV by Subzone bar chart
                store = ec_store.get()
                if len(store) >= 2:
                    # Multi-EC: show aggregated Total EV
                    ev_frames = {}
                    for ec_nm, ec_data in store.items():
                        if ec_data['results'] is not None:
                            ev_frames[ec_nm] = ec_data['results'][['Subzone ID', 'EV']].rename(columns={'EV': ec_nm})
                    if ev_frames:
                        merged_chart = None
                        for ec_nm, df_ev in ev_frames.items():
                            if merged_chart is None:
                                merged_chart = df_ev
                            else:
                                merged_chart = merged_chart.merge(df_ev, on='Subzone ID', how='outer')
                        ec_nm_list = list(ev_frames.keys())
                        merged_chart[ec_nm_list] = merged_chart[ec_nm_list].fillna(0)
                        merged_chart['Total EV'] = merged_chart[ec_nm_list].sum(axis=1)
                        chart_ev_x = merged_chart['Subzone ID']
                        chart_ev_y = merged_chart['Total EV']
                        chart_ev_title = "Total EV by Subzone (Aggregated)"
                    else:
                        chart_ev_x = results['Subzone ID']
                        chart_ev_y = results['EV']
                        chart_ev_title = "EV by Subzone"
                else:
                    chart_ev_x = results['Subzone ID']
                    chart_ev_y = results['EV']
                    chart_ev_title = "EV by Subzone"

                fig_ev = go.Figure(data=[go.Bar(
                    x=chart_ev_x, y=chart_ev_y,
                    marker=dict(color=chart_ev_y.tolist(), colorscale='Viridis', showscale=True)
                )])
                fig_ev.update_layout(
                    title=chart_ev_title, xaxis_title="Subzone ID", yaxis_title="EV Score",
                    height=500, width=800, plot_bgcolor='rgba(0,0,0,0)'
                )
                ev_img_bytes = pio.to_image(fig_ev, format='png', width=800, height=500, scale=2)
                ev_img_stream = io.BytesIO(ev_img_bytes)
                ws_chart1 = workbook.create_sheet('Chart - EV by Subzone')
                ws_chart1.sheet_properties.tabColor = 'FD7E14'
                img1 = XlImage(ev_img_stream)
                img1.width = 800
                img1.height = 500
                ws_chart1.add_image(img1, 'A1')

                # Chart 2: AQ Heatmap
                aq_columns = [col for col in results.columns if col.startswith('AQ')]
                if aq_columns:
                    display_cols = aq_columns + ['EV']
                    sorted_res = results.sort_values('EV', ascending=True)
                    z_data = sorted_res[display_cols].fillna(0).values

                    fig_heatmap = go.Figure(data=go.Heatmap(
                        z=z_data, x=display_cols, y=sorted_res['Subzone ID'].tolist(),
                        colorscale='Viridis', zmin=0, zmax=5,
                        text=np.round(z_data, 1), texttemplate="%{text}",
                        textfont={"size": 9}, colorbar=dict(title="Score")
                    ))
                    fig_heatmap.update_layout(
                        title="AQ Scores x Subzones (sorted by EV)",
                        xaxis_title="Assessment Questions", yaxis_title="Subzone ID",
                        height=max(450, len(sorted_res) * 25), width=800,
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    hm_height = max(450, len(sorted_res) * 25)
                    hm_img_bytes = pio.to_image(fig_heatmap, format='png', width=800, height=hm_height, scale=2)
                    hm_img_stream = io.BytesIO(hm_img_bytes)
                    ws_chart2 = workbook.create_sheet('Chart - AQ Heatmap')
                    ws_chart2.sheet_properties.tabColor = 'FD7E14'
                    img2 = XlImage(hm_img_stream)
                    img2.width = 800
                    img2.height = hm_height
                    ws_chart2.add_image(img2, 'A1')

                # Chart 3: EV Distribution histogram
                fig_hist = go.Figure(data=[go.Histogram(
                    x=results['EV'], nbinsx=20,
                    marker=dict(color='#006994', line=dict(color='white', width=1))
                )])
                fig_hist.update_layout(
                    title="EV Score Distribution", xaxis_title="EV Score", yaxis_title="Count",
                    height=500, width=800, plot_bgcolor='rgba(0,0,0,0)',
                    bargap=0.05
                )
                hist_img_bytes = pio.to_image(fig_hist, format='png', width=800, height=500, scale=2)
                hist_img_stream = io.BytesIO(hist_img_bytes)
                ws_chart3 = workbook.create_sheet('Chart - EV Distribution')
                ws_chart3.sheet_properties.tabColor = 'FD7E14'
                img3 = XlImage(hist_img_stream)
                img3.width = 800
                img3.height = 500
                ws_chart3.add_image(img3, 'A1')

            except Exception as e:
                # If chart generation fails (e.g., kaleido not available), skip charts
                logging.warning(f"Chart generation failed: {e}")
```

**Step 2: Test**

Download Excel. Verify 3 new chart sheets appear:
- "Chart - EV by Subzone" — color bar chart
- "Chart - AQ Heatmap" — heatmap image
- "Chart - EV Distribution" — histogram

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add embedded Plotly chart sheets to Excel export"
```

---

### Task 5: Upgrade Summary sheet for multi-EC

**Files:**
- Modify: `app.py:2544-2588` (replace summary sheet generation in download_results)

**Step 1: Replace summary sheet generation**

Replace the Summary & Metadata sheet creation (lines 2544-2588) with a version that handles multi-EC:

```python
            # Sheet 1: Summary & Metadata
            store = ec_store.get()
            if len(store) >= 2:
                # Multi-EC summary
                summary_rows = [
                    ('Analysis Date', pd.Timestamp.now().strftime('%Y-%m-%d')),
                    ('Analysis Time', pd.Timestamp.now().strftime('%H:%M:%S')),
                    ('Application Version', '2.1.2'),
                    ('Study Area', input.study_area() if input.study_area() else 'Not specified'),
                    ('Data Description', input.data_description() if input.data_description() else 'Not specified'),
                    ('', ''),
                    ('Multi-EC Analysis', ''),
                    ('Number of ECs', len(store)),
                    ('Total Features (all ECs)', sum(ec['feature_count'] for ec in store.values())),
                ]

                # Build aggregated stats
                ev_vals = []
                for ec in store.values():
                    if ec['results'] is not None:
                        ev_vals.extend(ec['results']['EV'].tolist())
                if ev_vals:
                    total_ev_sum = sum(ev_vals)
                    summary_rows.extend([
                        ('Total EV (Sum, all ECs)', f"{total_ev_sum:.4f}"),
                        ('Average EV (across all subzones)', f"{np.mean(ev_vals):.4f}"),
                        ('Maximum EV', f"{max(ev_vals):.4f}"),
                        ('Minimum EV', f"{min(ev_vals):.4f}"),
                    ])

                summary_rows.extend([
                    ('', ''),
                    ('Per-EC Details', ''),
                ])

                for ec_name_s, ec in store.items():
                    mean_ev = ec['results']['EV'].mean() if ec['results'] is not None else 0
                    max_ev = ec['results']['EV'].max() if ec['results'] is not None else 0
                    summary_rows.append((f"  EC: {ec_name_s}", f"{ec['data_type']}, {ec['feature_count']} features, Mean EV={mean_ev:.2f}, Max EV={max_ev:.2f}"))

                summary_rows.extend([
                    ('', ''),
                    ('Reference', 'Franco A. and Amorim E. (2025) Ecological Value Assessment (EVA)'),
                    ('Funding', 'European Union Horizon Europe Research Programme - MARBEFES Project'),
                ])

                summary_df = pd.DataFrame(summary_rows, columns=['Parameter', 'Value'])
            else:
                # Single-EC summary (existing behavior)
                summary_data = {
                    'Parameter': [
                        'Analysis Date', 'Analysis Time', 'Application Version',
                        'EC Name', 'Study Area', 'Data Type', 'Data Description',
                        '', 'Dataset Statistics', 'Number of Subzones', 'Number of Features',
                        'Total EV (Sum)', 'Average EV', 'Maximum EV', 'Minimum EV',
                        '', 'Reference', 'Funding',
                    ],
                    'Value': [
                        pd.Timestamp.now().strftime('%Y-%m-%d'),
                        pd.Timestamp.now().strftime('%H:%M:%S'),
                        '2.1.2',
                        input.ec_name() if input.ec_name() else 'Not specified',
                        input.study_area() if input.study_area() else 'Not specified',
                        data_type if data_type else 'Not specified',
                        input.data_description() if input.data_description() else 'Not specified',
                        '', '',
                        len(results),
                        len([col for col in df.columns if col != 'Subzone ID']),
                        f"{results['EV'].sum():.4f}",
                        f"{results['EV'].mean():.4f}",
                        f"{results['EV'].max():.4f}",
                        f"{results['EV'].min():.4f}",
                        '',
                        'Franco A. and Amorim E. (2025) Ecological Value Assessment (EVA)',
                        'European Union Horizon Europe Research Programme - MARBEFES Project',
                    ]
                }
                summary_df = pd.DataFrame(summary_data)

            summary_df.to_excel(writer, sheet_name='Summary & Metadata', index=False)
```

**Step 2: Test with multi-EC**

Save 2 ECs, download Excel. Open Summary & Metadata sheet. Verify:
- Multi-EC header info (Number of ECs, Total Features)
- Aggregated EV statistics
- Per-EC detail lines

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: upgrade Summary sheet with multi-EC metadata"
```

---

### Task 6: Integration test

**Files:**
- No file changes — browser-based testing

**Step 1: Test single-EC export**

Upload data, set data type, download Excel. Verify:
- All 7 standard sheets present with professional styling
- Headers are blue/white/bold on every sheet
- Autofilters and freeze panes work
- Tab colors visible
- EV conditional formatting (green-yellow-red) in AQ & EV Results
- 3 chart sheets present with embedded images
- Summary sheet has single-EC metadata

**Step 2: Test multi-EC export**

Save 2 ECs, download Excel. Verify:
- All standard sheets + Aggregated EV + Per-EC sheets
- Multi-EC sheets have purple tabs
- Aggregated EV has conditional formatting on Total EV column
- Summary sheet has multi-EC metadata with per-EC details
- Chart - EV by Subzone shows "Total EV (Aggregated)"

**Step 3: Commit any fixes**

```bash
git add app.py
git commit -m "fix: address integration test issues in enhanced export"
```
