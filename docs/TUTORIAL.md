# MARBEFES EVA Tutorial — Lithuanian BBT5

**Version 3.5.1** | Estimated time: ~30 minutes

This tutorial walks you through a complete Ecological Value Assessment using real data from the Lithuanian Baltic Sea coast and Curonian Lagoon (Broad Biotope Type 5). You will assess 5 ecosystem components, configure species classifications, review AQ scores and EV values, and visualize results on interactive maps.

---

## Overview

**What you'll do:**
1. Load a spatial hexagonal grid (425 cells)
2. Assess 3 grid-based ecosystem components: Benthos, Fish, Habitats
3. Assess 2 zone-based ecosystem components: Zooplankton, Phytoplankton
4. Review aggregated Total Ecological Value
5. Explore visualizations and maps

**What you'll learn:**
- How AQ1-AQ15 Assessment Questions work for different data types
- How to classify species as rare, habitat-forming, or ecologically significant
- How EV is computed as the MAX of applicable AQs
- How multiple ECs combine into Total EV

---

## Prerequisites

1. **App installed and running:**
   ```bash
   pip install -r requirements.txt
   shiny run app.py --port 8790
   ```
   Open `http://localhost:8790` in your browser.

2. **Tutorial data files** in the `tutorial/` directory:
   - `grid.geojson` — hexagonal 3km grid
   - `benthos.csv` — 6 benthic species
   - `fish.csv` — 11 fish species
   - `habitats.csv` — benthic habitat types
   - `zooplankton.csv` — 3 zooplankton taxa
   - `phytoplankton.csv` — phytoplankton groups

---

## Part A: Grid-Based Ecosystem Components

These 3 ECs use the hexagonal grid (308-425 subzones) and can be combined for a spatial Total EV.

### Step 1: Launch and Load the Spatial Grid

1. Open the app in your browser
2. Go to the **Data Input** tab
3. In the sidebar under "Upload Spatial Grid", click **Browse** and select `tutorial/grid.geojson`
4. You should see: "Grid: 425 features loaded" with a bounding box around the Lithuanian coast

This grid will be used for all map visualizations throughout the tutorial.

---

### Step 2: Benthos EC (Quantitative Data)

**Background:** The benthos dataset contains abundance scores for 6 species/groups in the Lithuanian Baltic Sea coastal zone, derived from species distribution modelling and underwater video surveys.

**Upload:**
1. In the sidebar, under "Metadata":
   - EC Name: `Zoobenthos`
   - Study Area: `Lithuanian Baltic Sea coast`
   - Data Type: leave as auto-detected (should detect **quantitative**)
2. Under "Upload Data", click Browse and select `tutorial/benthos.csv`
3. Verify the data preview shows ~308 subzones x 6 features

**Configure Feature Classifications:**

Go to the **EC Features** tab. For each species, set:

| Feature | Classification | Reason |
|---------|---------------|--------|
| Monoporeia | **NRF** (Nationally Rare) | Glacial relict amphipod, nationally rare in Lithuanian waters |
| Furcellaria | **HFS/BH** (Habitat Forming) | Red alga forming biogenic reef structures |
| Mytilus | **HFS/BH** (Habitat Forming) | Blue mussel beds create habitat for other species |
| AI | **HFS/BH** (Habitat Forming) | *Amphibalanus improvisus* — barnacle forming hard substrate |
| Macoma | (none) | Common bivalve, no special classification |
| HForming | (none) | Aggregate habitat-forming score, leave unclassified |

**Review Results:**

Go to the **AQ + EV Results** tab. For quantitative data with NRF and HFS/BH classifications, you should see:

| AQ | Status | What it measures |
|----|--------|-----------------|
| AQ2 | Active or NaN | Locally rare species abundance (auto-detected, depends on species occurrence rates) |
| AQ4 | NaN | No RRF classified |
| AQ6 | **Active** | Nationally rare — Monoporeia abundance per subzone |
| AQ8 | **Active** | Regularly occurring species — average abundance |
| AQ9 | **Active** | Concentration hotspots — where species abundance is spatially concentrated |
| AQ11 | NaN | No ESF classified |
| AQ13 | **Active** | Habitat-forming species — Furcellaria, Mytilus, AI |
| AQ15 | NaN | No SS classified |

Odd-numbered AQs (AQ1, AQ3, AQ5, AQ7, AQ10, AQ12, AQ14) will show **NaN** — these are qualitative-only AQs and do not apply to quantitative data.

**EV** = MAX of all active AQs for each subzone. A subzone with high Monoporeia abundance (AQ6=4.5) and moderate benthos diversity (AQ8=2.0) will get EV=4.5.

**Save the EC** by clicking "Save Current EC" in the Data Input sidebar.

---

### Step 3: Fish EC (Quantitative Data)

**Background:** Fish data comes from ICES Baltic International Trawl Surveys (sea fish) and Lithuanian EPA commercial catch statistics (lagoon fish). 11 species cover both rare and commercially important fish.

**Upload:**
1. Click **New EC** in the sidebar
2. EC Name: `Fish`
3. Upload `tutorial/fish.csv`
4. Data type: quantitative (auto-detected)
5. Verify: 425 subzones x 11 features

**Configure Classifications:**

In the **EC Features** tab, classify these 5 species as **RRF** (Regionally Rare Features):

| Feature | Classification | Reason |
|---------|---------------|--------|
| Eel | **RRF** | European eel — HELCOM Red List |
| Whitefish | **RRF** | Regionally declining species |
| Asp | **RRF** | Rare predatory cyprinid |
| TwaiteShad | **RRF** | Anadromous, regionally rare |
| Burbot | **RRF** | Cold-water species, declining |

Leave Bream, Zander, Perch, Roach, Smelt, Vimba unclassified (they are common/commercial species).

**Expected AQ Results:**

| AQ | Status | What it measures |
|----|--------|-----------------|
| AQ2 | Active or NaN | Locally rare fish (if any species occurs in <=5% of subzones) |
| AQ4 | **Active** | Regionally rare fish — the 5 RRF species |
| AQ6 | NaN | No NRF classified |
| AQ8 | **Active** | Common fish species abundance |
| AQ9 | **Active** | Fish concentration hotspots |
| AQ11-AQ15 | NaN | No ESF/HFS/SS classified |

**Save the EC.**

---

### Step 4: Habitats EC (Qualitative Data)

**Background:** Habitat data represents the presence/absence of broad benthic habitat types (HELCOM HUB Level 3 / EUNIS Level 2) across the study area.

**Upload:**
1. Click **New EC**
2. EC Name: `Benthic Habitats`
3. Upload `tutorial/habitats.csv`
4. Data type: should auto-detect as **qualitative** (presence/absence, 0/1 values)
5. Verify the data shows ~393 subzones with habitat type columns

**Classifications:** No special classifications needed for habitats in this tutorial. The AQ calculations will automatically determine which habitat types are locally rare.

**Expected AQ Results:**

| AQ | Status | What it measures |
|----|--------|-----------------|
| AQ1 | Active or NaN | Locally rare habitats — only if some habitat types occur in <=5% of subzones |
| AQ7 | **Always Active** | Habitat diversity — the number of different habitat types per subzone, rescaled to 0-5 |

All other AQs will be NaN: even-numbered AQs require quantitative data, and AQ3/5/10/12/14 require specific classifications.

AQ7 is the **baseline AQ** — it always works for qualitative data and requires no special classification. A subzone with 4 out of 6 habitat types present will score higher than one with only 1 type.

**Save the EC.**

---

### Step 5: Review Grid-Based Total EV

Go to the **Total EV** tab. With 3 saved ECs (Zoobenthos, Fish, Benthic Habitats), you should see:

- **Aggregated Total EV** = MAX of the three EC EVs per subzone
- Values range from 0 to 5
- Summary statistics: Total, Average, Maximum, Minimum across all subzones

**Understanding MAX aggregation:** If a subzone has Benthos EV=4.0, Fish EV=2.5, and Habitats EV=1.5, the Total EV = 4.0 (the maximum). This ensures that any significant ecological value is captured — a subzone important for benthos is still flagged even if fish and habitats score low there.

**Download the Excel report** by clicking "Download Complete Analysis (Excel)" — this contains all AQ scores, EV values, metadata, and methodology reference across multiple sheets.

---

### Step 6: Visualize and Map

**Visualization tab:**
- **EV by Subzone** — bar chart showing EV for each subzone
- **AQ Breakdown by Subzone** — grouped bars comparing active AQ scores
- **AQ Radar Comparison** — select 3-5 subzones to compare their AQ profiles
- **AQ Heatmap** — heatmap of all AQ scores sorted by EV

**Map tab:**
- Select **EV** as the display variable — see the spatial pattern of ecological value
- Switch to **AQ6** to see where Monoporeia (nationally rare) drives high scores
- Switch to **AQ13** to see habitat-forming species hotspots
- Try the **EVA 5-class** classification to see Very Low / Low / Medium / High / Very High categories
- Switch basemaps (CartoDB, OpenStreetMap) for different context

---

## Part B: Zone-Based Ecosystem Components (Standalone)

Zooplankton and phytoplankton data is only available at the ecological zone level (4-5 zones covering the Curonian Lagoon), not at the hexagonal grid level. Because the Subzone IDs are zone names (not grid cell IDs), these ECs must be assessed **separately** from the grid-based ECs.

### Step 7: Plankton Demonstration

1. **Delete all saved ECs** (click Delete for each in the Data Input sidebar) or restart the app
2. Do NOT load grid.geojson (zone data has no spatial geometry for hex mapping)

**Zooplankton:**
1. New EC, name: `Zooplankton`
2. Upload `tutorial/zooplankton.csv` — should show 4 zones x 3 taxa (Copepoda, Cladocera, Rotifera)
3. Data type: quantitative
4. No special classifications needed
5. Review AQ results — with only 4 subzones, most AQs will show unusual patterns:
   - AQ8 (ROF): active if species occur in >5% of zones (>0.2 zones, so essentially all)
   - AQ9 (concentration): may produce extreme values with so few subzones
   - This demonstrates that EVA works best with more subzones (>20 recommended)

**Phytoplankton:**
1. New EC, name: `Phytoplankton`
2. Upload `tutorial/phytoplankton.csv`
3. Same interpretation as zooplankton

**Key takeaway:** The plankton results illustrate a real-world limitation — when monitoring data is sparse, the EVA can still be applied but confidence is low and spatial resolution is coarse. The Lithuanian BBT5 report addressed this by producing both a "full EVA" (all 5 ECs) and an "EVA without plankton" map.

---

## Part C: Wrap-Up

### Step 8: Physical Accounts (Optional)

If you want to explore the Physical Accounts module:

1. Reload `tutorial/grid.geojson` and at least the Habitats EC
2. Go to the **Physical Accounts** tab
3. In the sidebar, select habitat types from the EUNIS list
4. Assign habitat types to subzones (or let auto-detection work)
5. View the **Extent Account** — area per habitat type
6. View the **Supply Table** — enter ecosystem service values per habitat

### Step 8.5: Upload EUNIS Overlay for BBT8 Accounts (Optional)

Since v3.4.0, the Physical Accounts module supports uploading a EUNIS habitat overlay to automatically assign EUNIS Level 3 habitat types via spatial intersection:

1. In the Physical Accounts sidebar, click **Browse** under "Upload EUNIS Overlay"
2. Select `tutorial/eunis_l3_lithuanian.gpkg`
3. The app intersects the EUNIS polygons with your spatial grid and assigns the dominant habitat type per subzone
4. HFS/BH classifications are auto-detected from EUNIS codes — habitat-forming species and biogenic habitats are flagged automatically
5. View the updated **Extent Account** with EUNIS-derived habitat assignments
6. Toggle the **EUNIS Habitat Base Layer** on the Map tab to see the overlay beneath your EVA results
7. Export includes a **BBT8 Export** option and an "EV by Habitat Type" sheet in the Excel output

> **Tip:** Set the environment variable `MARBEFES_EVA_DATA_PATH` to a directory containing EUNIS BBT8 data files to have them loaded automatically on startup.

---

## Interpreting Your Results

### What do the scores mean?

| EV Range | Class | Interpretation |
|----------|-------|----------------|
| 0-1 | Very Low | Minimal ecological value detected |
| 1-2 | Low | Some ecological features present |
| 2-3 | Medium | Moderate ecological importance |
| 3-4 | High | Significant ecological value |
| 4-5 | Very High | Critical ecological value — priority for conservation |

### Important caveats

- **EV is relative:** A score of 5 means "highest value within this study area" — it cannot be compared between different BBTs or countries
- **Confidence matters:** With only 2-4 AQs answered per EC, confidence is Low. This is typical for first-pass assessments and highlights where more data collection would improve the assessment
- **Data limitations:** The benthos data covers only the Baltic Sea coast (not the Curonian Lagoon), and plankton data has very coarse spatial resolution
- **Classification choices affect results:** Changing which species are classified as RRF/NRF/HFS changes which AQs are active, which changes EV

### Comparison with published results

The Lithuanian BBT5 assessment (Razinkovas-Baziukas et al., 2025) found that zooplankton dominated the Total EV in most subzones due to its broad spatial coverage and high scores. The dual-map approach (with and without plankton) was recommended to ensure that benthic patterns are not obscured. Your tutorial results should show similar patterns.

---

## Next Steps

- Try the assessment with your own data — prepare a CSV with your species/habitat features
- Experiment with different classification schemes to see how they affect EV
- Use the R script (in `EVA_R-script.zip`) for comparison with the GIS-based workflow
- Read the full methodology: Franco A. and Amorim E. (2025) EVA Guidance including FAQs

---

*Tutorial created for MARBEFES EVA v3.8.0 | Data: Lithuanian BBT5 (Klaipeda University) | Framework: Franco & Amorim (2025)*
