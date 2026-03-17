# MARBEFES EVA — User Manual

**Version 3.0.0** | Last updated: 2026-03-16

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Data Input](#3-data-input)
4. [EC Features Configuration](#4-ec-features-configuration)
5. [AQ + EV Results](#5-aq--ev-results)
6. [Total EV](#6-total-ev)
7. [Physical Accounts](#7-physical-accounts)
8. [Visualization](#8-visualization)
9. [Map](#9-map)
10. [Export](#10-export)
11. [Methodology Reference](#11-methodology-reference)
12. [Troubleshooting](#12-troubleshooting)
13. [Glossary](#13-glossary)

---

## 1. Introduction

The MARBEFES Ecological Value Assessment (EVA) application is a web-based tool for evaluating the ecological value of marine areas. It implements Phase 2 of the EVA framework developed under the European Union's Horizon Europe MARBEFES project.

**What it does:**
- Scores ecosystem components (species or habitats) across spatial subzones using 15 standardised Assessment Questions (AQ1-AQ15)
- Produces Ecological Value (EV) scores on a 0-5 scale
- Supports multiple ecosystem components (ECs) with aggregation
- Generates SEEA EA-aligned Physical Natural Capital Accounts
- Produces professional Excel reports with charts and spatial maps

**Reference:** Franco A. and Amorim E. (2025) *Ecological Value Assessment (EVA) - Guidance including FAQs*. MARBEFES WP4.1.

---

## 2. Getting Started

### Installation

```bash
pip install -r requirements.txt
shiny run app.py --port 8790
```

Open `http://localhost:8790` in your browser.

### Recommended Workflow

1. **Home tab** — Read the overview and key concepts
2. **Data Input tab** — Upload your CSV data and optional spatial grid
3. **EC Features tab** — Configure feature classifications (RRF, NRF, ESF, etc.)
4. **AQ + EV Results tab** — Review calculated scores
5. **Total EV tab** — See aggregated results and download Excel reports
6. **Physical Accounts tab** — Create SEEA EA physical accounts (if needed)
7. **Visualization tab** — Explore interactive charts
8. **Map tab** — View spatial results on interactive maps
9. **Method tab** — Reference the EVA methodology

---

## 3. Data Input

### CSV File Format

Your CSV must follow this structure:

| Subzone ID | Feature1 | Feature2 | Feature3 |
|------------|----------|----------|----------|
| A0         | 1        | 0        | 1        |
| A1         | 0        | 1        | 0        |
| A2         | 1        | 1        | 0        |

- **First column:** Subzone identifiers (grid cell IDs)
- **Remaining columns:** Feature values (species or habitats)
- **Qualitative data:** Presence (1) / absence (0)
- **Quantitative data:** Continuous numerical values (counts, density, biomass)

### Data Type Detection

The application automatically detects whether your data is qualitative or quantitative:
- **Qualitative:** Binary data (only 0 and 1 values)
- **Quantitative:** Continuous data (many unique values, decimals, range > 1)

You can override the auto-detection using the "Data Type" dropdown in the sidebar.

### Missing Values

Missing values (NA, N/A, null, empty) are treated as 0 (absent). A validation report shows which columns have missing data and how much.

### Spatial Grid (Optional)

Upload a spatial polygon file to enable map visualization:
- **GeoJSON** (`.geojson`, `.json`)
- **Zipped Shapefile** (`.zip` containing `.shp`, `.dbf`, `.shx`, `.prj`)
- **GeoPackage** (`.gpkg`)

Each polygon must have a `Subzone ID` attribute matching the CSV data. The app automatically detects and reprojections the coordinate reference system (CRS) to WGS84.

### EC Management

Save multiple Ecosystem Components (ECs) for aggregation:
1. Upload data and configure for one EC
2. Enter an EC name in the sidebar
3. Click **Save Current EC**
4. Click **New EC** to start a fresh analysis
5. Repeat for additional ECs

Switch between saved ECs using the dropdown. The **Total EV** tab aggregates all saved ECs.

### Advanced Settings

- **Locally Rare Threshold (%):** Features occurring in this percentage or fewer subzones are classified as Locally Rare (default: 5%)
- **Concentration Percentile:** Used in AQ9 calculation (default: 95th)
- **Results Display Limit:** Number of rows shown in tables (10/20/50/All)

---

## 4. EC Features Configuration

### Feature Classifications

Each feature (column in your CSV) can be assigned one or more ecological classifications:

| Classification | Code | Description | Activates |
|---------------|------|-------------|-----------|
| Regionally Rare Feature | RRF | Rare at regional level (user-defined) | AQ3/AQ4 |
| Nationally Rare Feature | NRF | Rare at national level (user-defined) | AQ5/AQ6 |
| Ecologically Significant Feature | ESF | Keystone species, ecosystem engineers | AQ10/AQ11 |
| Habitat Forming Species / Biogenic Habitat | HFS/BH | Corals, seagrasses, habitat creators | AQ12/AQ13 |
| Symbiotic Species | SS | Species in symbiotic relationships | AQ14/AQ15 |

**Automatic classifications** (computed from data, not user-assigned):
- **Locally Rare Feature (LRF):** Present in <=5% of subzones → AQ1/AQ2
- **Regularly Occurring Feature (ROF):** Present in >5% of subzones → AQ8/AQ9

### How to Classify

1. Go to the **EC Features** tab
2. For each feature, check the relevant boxes under "Rarity" and "Ecological Role"
3. Click **Apply Configuration**
4. The feature summary table shows statistics (mean, 95th percentile, occurrence count)

### Tips
- You don't need to classify every feature — unclassified features still contribute to AQ7 (all features)
- Multiple classifications can be assigned to the same feature (e.g., a species can be both RRF and ESF)
- Use **Reset All Classifications** to start over

---

## 5. AQ + EV Results

### Assessment Questions (AQ1-AQ15)

The 15 AQs evaluate different aspects of ecological value:

| AQ | Name | Data Type | Filter |
|----|------|-----------|--------|
| AQ1 | Locally Rare Features | Qualitative | LRF only |
| AQ2 | Locally Rare Features | Quantitative | LRF only |
| AQ3 | Regionally Rare Features | Qualitative | RRF only |
| AQ4 | Regionally Rare Features | Quantitative | RRF only |
| AQ5 | Nationally Rare Features | Qualitative | NRF only |
| AQ6 | Nationally Rare Features | Quantitative | NRF only |
| AQ7 | All Features | Qualitative | No filter (always active) |
| AQ8 | Regularly Occurring Features | Quantitative | ROF only |
| AQ9 | ROF Concentration-Weighted | Quantitative | ROF only |
| AQ10 | Ecologically Significant Features | Qualitative | ESF only |
| AQ11 | Ecologically Significant Features | Quantitative | ESF only |
| AQ12 | Habitat Forming Species | Qualitative | HFS/BH only |
| AQ13 | Habitat Forming Species | Quantitative | HFS/BH only |
| AQ14 | Symbiotic Species | Qualitative | SS only |
| AQ15 | Symbiotic Species | Quantitative | SS only |

### Ecological Value (EV)

**EV = MAX of applicable AQ scores** (not average or sum)

- Qualitative: `EV = MAX(AQ1, AQ3, AQ5, AQ7, AQ10, AQ12, AQ14)`
- Quantitative: `EV = MAX(AQ2, AQ4, AQ6, AQ8, AQ9, AQ11, AQ13, AQ15)`

All scores are on a 0-5 scale. The MAX approach ensures that any significant ecological value is captured, even if only one criterion is met.

### Reading the Results Table

- **Green highlighted cells:** The AQ with the highest score for that subzone (determines EV)
- **NA values:** The AQ does not apply (wrong data type or no features classified)
- **Active/Inactive badges:** Show which AQs contribute to the analysis
- **Hover over column headers** for detailed AQ descriptions

---

## 6. Total EV

### Single EC

Shows summary statistics (Total, Average, Max, Min EV) and a per-subzone EV table.

### Multiple ECs

When 2+ ECs are saved, this tab aggregates:
- **Total EV** per subzone = Sum of EV values across all ECs
- Per-EC summary showing data type, feature count, and mean EV
- Aggregated EV table sorted by Total EV (highest first)

---

## 7. Physical Accounts

The Physical Accounts module implements SEEA EA physical natural capital accounting (Steps 1-6 of the MARBEFES 7-step process).

### Prerequisites

- A spatial grid file must be uploaded in the **Data Input** tab
- The spatial grid should contain polygon features with `Subzone ID` attributes

### Step 1: Configure Study Area

In the sidebar:
1. Enter the **EAA Name** (Ecosystem Accounting Area)
2. Enter a **Boundary Description**
3. Set the **Accounting Year**

### Step 2: Select Habitats

1. Use the **EUNIS Habitats** dropdown to search and select habitat types from the built-in EUNIS Level 3 reference (~40 marine codes)
2. To add a habitat not in the list, enter a custom code and name, then click **Add Custom Habitat**

### Step 3: Assign Habitats to Subzones

The **Habitat Assignment** card shows:
- **Auto-detection:** If your spatial file has a column named "EUNIS", "Habitat", or similar, habitats are pre-populated automatically
- **Manual assignment:** Use the dropdowns to assign a EUNIS habitat type to each subzone
- **Summary:** Shows how many subzones are assigned vs unassigned

### Step 4: Review Extent Account

The **Ecosystem Extent Account** card shows:
- EUNIS code and habitat name
- Area in your chosen unit (Ha or km²)
- Percentage of total extent
- Areas are computed from the spatial grid polygon geometries

### Step 5: Enter Supply Data

The **Supply Table** card shows an editable grid:
- **Rows:** Active societal benefits (5 defaults + any custom benefits you add)
- **Columns:** Habitat types present in your extent
- Enter physical quantities in the appropriate units (tonnes, tCO2eq, visitor-days, etc.)
- Empty cells are tracked as data gaps — partial data is expected and acceptable per the SEEA EA guidance
- The completeness indicator shows "X of Y cells filled (Z%)"

### Step 6: Export

Use the sidebar buttons:
- **Download PA Report (Excel):** Standalone Physical Accounts workbook with 5 sheets
- **Download Combined EVA+PA (Excel):** All EVA sheets plus PA sheets in one workbook

### Default Benefits

| Benefit | Unit | Ecosystem Service |
|---------|------|-------------------|
| Wild food (finfish) | tonnes | Wild fish |
| Healthy climate | tCO2eq | Carbon sequestration & storage |
| Recreation & nature watching | visitor-days | Places and seascapes |
| Erosion/flood prevention | Ha protected | Natural hazard protection |
| Clean water | tonnes N removed | Waste remediation |

### Future Features (Planned)

- **Use Table:** Disaggregation of supply by beneficiary sector (households, fishing industry, tourism, etc.)
- **Condition Account:** SEEA ecosystem condition assessment (compositional, structural, functional, landscape/seascape state)
- **Multi-year time series:** Opening/closing stock tracking across accounting periods

---

## 8. Visualization

### Available Chart Types

| Chart | Description |
|-------|-------------|
| **EV by Subzone** | Bar chart of EV scores per subzone with color scale |
| **Feature Distribution** | Heatmap of raw feature values across subzones |
| **AQ Scores** | Histogram of all AQ score distributions |
| **AQ Breakdown by Subzone** | Grouped bars showing active AQ scores per subzone with EV line |
| **AQ Radar Comparison** | Radar chart comparing AQ profiles for selected subzones (max 5) |
| **AQ Heatmap** | AQ scores x subzones matrix sorted by EV |

### Tips
- Use **Color Scheme** to change the palette (Viridis, Plasma, Blues, Greens)
- For **AQ Radar Comparison**, select 1-5 subzones from the sidebar dropdown
- All charts are interactive (zoom, pan, hover for details)

---

## 9. Map

### Requirements
- A spatial grid file must be uploaded in the **Data Input** tab
- EVA results must be calculated (or habitat assignments made for PA)

### Map Controls

| Control | Options |
|---------|---------|
| **Display Variable** | EV, AQ1-AQ15, Habitat Type (PA) |
| **Color Scheme** | YlOrRd, Viridis, Blues, RdYlGn, Plasma |
| **Classification** | Continuous, EVA 5-class (VL/L/M/H/VH) |
| **Basemap** | CartoDB Positron, OpenStreetMap, CartoDB Dark Matter |
| **Fill Opacity** | 0.3 to 1.0 |

### EVA 5-Class Classification

| Class | Range | Color |
|-------|-------|-------|
| Very Low | 0-1 | Blue |
| Low | 1-2 | Green |
| Medium | 2-3 | Yellow |
| High | 3-4 | Orange |
| Very High | 4-5 | Red |

### Habitat Type Map (Physical Accounts)

When "Habitat Type (PA)" is selected, the map shows a categorical choropleth:
- Each EUNIS habitat type gets a distinct color
- Legend shows code + name for each habitat
- Tooltips display Subzone ID, EUNIS code, and habitat name
- This option only appears after habitats are assigned in the Physical Accounts tab

---

## 10. Export

### Excel Export (EVA)

Downloaded from the **Total EV** tab. Contains:

| Sheet | Content |
|-------|---------|
| Summary & Metadata | Analysis date, version, EC name, study area, EV statistics |
| Original Data | Uploaded CSV data |
| AQ & EV Results | All AQ scores and EV per subzone |
| Feature Classifications | User-assigned classifications per feature |
| AQ Methodology | Reference table of all 15 AQs |
| EV Calculation | EV formula explanation |
| Complete Results | Full merged dataset |
| Chart - EV by Subzone | Embedded bar chart |
| Chart - AQ Heatmap | Embedded heatmap |
| Chart - EV Distribution | Embedded histogram |

With multiple ECs: adds Aggregated EV and per-EC result sheets.

### Excel Export (Physical Accounts)

Downloaded from the **Physical Accounts** tab sidebar.

**Standalone PA workbook:**

| Sheet | Content |
|-------|---------|
| Summary & Metadata | EAA name, accounting year, completeness, references |
| Ecosystem Extent Account | SEEA EA Table 2A.1 format |
| Supply Table | SEEA EA Table 2A.2 format |
| Habitat Assignments | Subzone-to-habitat mapping |
| Methodology | SEEA EA framework reference |

**Combined EVA+PA workbook:** All EVA sheets plus PA sheets (prefixed with "PA -") in one file.

---

## 11. Methodology Reference

### EVA Framework

The EVA framework evaluates marine ecosystem ecological value through:
1. **Data rescaling:** Raw values normalized to 0-5 scale
   - Qualitative: presence (1) -> 5, absence (0) -> 0
   - Quantitative: min-max normalization per feature
2. **Feature classification:** Automatic (LRF/ROF) and user-defined (RRF/NRF/ESF/HFS_BH/SS)
3. **AQ calculation:** 15 questions applied based on data type and classifications
4. **EV computation:** MAX of applicable AQs per subzone

### AQ9 Special Calculation

AQ9 uses a 3-step concentration-weighted calculation for Regularly Occurring Features:
1. **Normalize by mean:** `value / feature_mean`
2. **Weight by concentration:** `(% of total in top 5%) / occurrence_count * normalized_value`
3. **Rescale to 0-5:** `5 * weighted / MAX(all_weighted)`

This identifies spatial hotspots where regularly occurring features are concentrated.

### SEEA EA Alignment

The Physical Accounts module follows the System of Environmental-Economic Accounting - Ecosystem Accounting (SEEA EA) framework:

| SEEA EA Concept | Module Implementation |
|---|---|
| Ecosystem Accounting Area | Study area defined by spatial grid |
| Ecosystem Type | EUNIS Level 3 classification |
| Ecosystem Extent | Polygon area aggregated by habitat |
| Ecosystem Services (physical) | Supply table quantities |

---

## 12. Troubleshooting

### Common Issues

**"No data uploaded" message:**
- Go to the Data Input tab and upload a CSV file
- Check that the file is valid CSV with a "Subzone ID" column

**All AQ values are 0 or NA:**
- Verify the data type (qualitative vs quantitative) matches your data
- For qualitative: AQ7 should always have values; if not, check data contains 1s
- For quantitative: AQ8/AQ9 should have values for features in >5% of subzones

**Map shows "No spatial data":**
- Upload a GeoJSON/Shapefile/GeoPackage in the Data Input tab
- Ensure Subzone IDs in the spatial file match the CSV

**Physical Accounts extent shows 0:**
- Verify habitats are assigned to subzones (check assignment summary)
- Ensure the spatial file has valid polygon geometries

**Excel export has no charts:**
- Kaleido must be installed (`pip install kaleido`)
- Chart generation failures are logged but do not prevent export

### File Size Limits
- Maximum CSV/spatial file size: 50 MB
- For very large datasets (100k+ rows), consider using the "20 rows" display limit

---

## 13. Glossary

| Term | Definition |
|------|-----------|
| **AQ** | Assessment Question — one of 15 criteria for evaluating ecological value |
| **BH** | Biogenic Habitat — habitat created by living organisms |
| **EC** | Ecosystem Component — a group of species or habitats being assessed |
| **EAA** | Ecosystem Accounting Area — spatial boundary for SEEA EA accounts |
| **ESF** | Ecologically Significant Feature — keystone species, ecosystem engineers |
| **EUNIS** | European Nature Information System — standardised habitat classification |
| **EV** | Ecological Value — MAX of applicable AQ scores (0-5 scale) |
| **EVA** | Ecological Value Assessment — the overall framework |
| **HFS** | Habitat Forming Species — corals, seagrasses, habitat creators |
| **LRF** | Locally Rare Feature — present in <=5% of subzones |
| **NRF** | Nationally Rare Feature — user-defined national rarity |
| **ROF** | Regularly Occurring Feature — present in >5% of subzones |
| **RRF** | Regionally Rare Feature — user-defined regional rarity |
| **SEEA EA** | System of Environmental-Economic Accounting - Ecosystem Accounting |
| **SS** | Symbiotic Species — species in symbiotic relationships |
