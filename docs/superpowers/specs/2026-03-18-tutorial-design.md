# EVA Shiny App Tutorial — Design Spec

**Date:** 2026-03-18
**Status:** Approved (post-review)

## Goal

Create a step-by-step tutorial with real Lithuanian BBT5 data files that walks users through a complete EVA assessment of 5 ecosystem components using the Shiny app.

## Pre-requisite: Fix app Total EV aggregation

The app currently computes multi-EC Total EV as **SUM** (`app.py` lines ~1030, 1105). The EVA Guidance (Nov 2024) requires **MAX**. This must be fixed before the tutorial ships, otherwise users will see Total EV values >5, contradicting the 0-5 scale. The fix: change `merged[ec_names].sum(axis=1)` to `merged[ec_names].max(axis=1)` in both `total_ev_ui` and `total_ev_table`.

## Deliverables

### 1. Tutorial data files (`tutorial/`)

| File | EC | Data Type | Rows | Columns | Source |
|------|----|-----------|------|---------|--------|
| `benthos.csv` | Zoobenthos | Quantitative | ~308 subzones | 6 species: Macoma, Monoporeia, Mytilus, Furcellaria, AI, HForming | `Benthos_EVA/Benthos_Final.shp` |
| `fish.csv` | Fish | Quantitative | 425 subzones | 11 species: Bream, Zander, Perch, Roach, Burbot, Eel, Smelt, Whitefish, Vimba, Asp, TwaiteShad | Individual `Fish/*Score.gpkg` files |
| `habitats.csv` | Benthic Habitats | Qualitative | ~393 subzones | ~8-10 habitat types (presence/absence) | `habitats_EVA/habitats_final.shp` |
| `zooplankton.csv` | Zooplankton | Quantitative | 5 zones | 3 taxa: Copepoda, Cladocera, Rotifera | `zooplankton_stations/*.xlsx` |
| `phytoplankton.csv` | Phytoplankton | Quantitative | 5 zones | 3 groups: Diatoms, Chlorophytes, Dinoflagellates | `FItoplankon4EVA.xlsx` |
| `grid.geojson` | (spatial) | GeoJSON | 425 hexagons | Subzone ID, geometry (only these 2 columns) | `EVA Grids/HexGrid3kmLithuanianBBT.gpkg` |
| `README.txt` | (metadata) | Text | — | See README spec below | — |

**CSV format:** First column = `Subzone ID` (matching grid.geojson). Remaining columns = species/habitat features. Values = abundance (quantitative) or 0/1 (qualitative).

**Subzone ID format:** `R{row:03d}_C{col:03d}` matching the grid's row_index/col_index.

**README.txt required content:**
- Data description and purpose
- Source: Lithuanian EPA, ICES BITS, Klaipeda University
- Extraction date
- CRS: EPSG:3346 (source), EPSG:4326 (grid.geojson)
- Citation: Franco A. and Amorim E. (2025) EVA Guidance
- License: CC-BY-4.0 (derived from public monitoring data)
- Contact: MARBEFES project

### 2. Data preparation script (`scripts/prepare_tutorial_data.py`)

Reads EVA_FINAL GeoPackages/Shapefiles, extracts species-level data, joins to hexagonal grid, writes clean CSVs to `tutorial/`. One-time script, committed for reproducibility.

**Steps per EC:**

**Benthos:**
1. Read `Benthos_EVA/Benthos_Final.shp`
2. Extract columns: Monoporeia, Macoma, Mytilus, Furcellari(a), AI, HForming
3. Map to grid via row_index/col_index or spatial join
4. Generate `Subzone ID` = `R{row:03d}_C{col:03d}`
5. Write `tutorial/benthos.csv`

**Fish:**
1. Read each of 11 `Fish/*Score.gpkg` files
2. Extract `_mean` column from each (CPUE score)
3. Merge on row_index/col_index into single DataFrame
4. Generate `Subzone ID`
5. Write `tutorial/fish.csv`

**Habitats:**
1. Read `habitats_EVA/habitats_final.shp`
2. Extract habitat type column (MSFD_broad or equivalent)
3. Pivot to presence/absence matrix: one column per habitat type
4. Map to grid via spatial join (polygon centroid → nearest hexagon)
5. Generate `Subzone ID`
6. Write `tutorial/habitats.csv`

**Zooplankton:**
1. Read `zooplankton_stations/Zooplanktono gausumas_EVAI_ LRF_final.xlsx`
2. Extract Copepoda, Cladocera, Rotifera abundance per station
3. Average by zone (Curonian zonation: Estuarine, Riverine, Stagnant, Transitional, BalticSea)
4. Write `tutorial/zooplankton.csv` with Zone name as Subzone ID

**Phytoplankton:**
1. Read `FItoplankon4EVA.xlsx`
2. Extract Diatoms, Chlorophytes, Dinoflagellates biomass
3. Average by zone
4. Write `tutorial/phytoplankton.csv` with Zone name as Subzone ID

**Grid:**
1. Read `EVA Grids/HexGrid3kmLithuanianBBT.gpkg`
2. Reproject to WGS84 (EPSG:4326) for Leaflet compatibility
3. Add `Subzone ID` = `R{row:03d}_C{col:03d}`
4. Drop all columns except `Subzone ID` and `geometry`
5. Write `tutorial/grid.geojson`

**Validation step (at end of script):**
- For each CSV, verify that all Subzone IDs are a subset of grid.geojson IDs (for benthos, fish, habitats)
- For plankton CSVs, verify zone names are valid
- Log any ID mismatches as errors

### 3. Tutorial document (`docs/TUTORIAL.md`)

**Structure:**

```
# MARBEFES EVA Tutorial — Lithuanian BBT5

## Overview
- What you'll learn: complete EVA assessment of 5 ecosystem components
- What data you'll use: real Lithuanian monitoring data
- Expected time: ~30 minutes
- Important: plankton ECs use zone-level data (5 zones) while other ECs
  use hexagonal subzones (308-425 cells). These are assessed separately.

## Prerequisites
- App installed and running (shiny run app.py --port 8790)
- Tutorial data files in tutorial/ directory

## Part A: Grid-Based ECs (Benthos, Fish, Habitats)

### Step 1: Launch and Load Spatial Grid
- Start the app
- Upload tutorial/grid.geojson in Data Input tab
- Verify 425 hexagons loaded

### Step 2: Benthos EC (Quantitative)
- Enter EC name: "Zoobenthos"
- Set data type: quantitative (auto-detected)
- Upload tutorial/benthos.csv
- Verify: ~308 subzones × 6 features
- Configure classifications:
  - Monoporeia → NRF (nationally rare glacial relict)
  - Furcellaria, Mytilus, AI → HFS/BH (habitat-forming species)
- Review AQ results — expected active AQs for quantitative data:
  - AQ2 (LRF quant): locally rare species abundance — may be NaN
    if no species occurs in <=5% of subzones
  - AQ6 (NRF quant): Monoporeia abundance scores
  - AQ8 (ROF quant): regularly occurring species abundance
  - AQ9 (ROF concentration): spatial hotspots of concentrated abundance
  - AQ13 (HFS/BH quant): habitat-forming species abundance
  - Note: AQ4 (RRF), AQ11 (ESF), AQ15 (SS) will be NaN — no features
    classified as RRF/ESF/SS. This is expected.
  - Note: Odd-numbered AQs (AQ1, AQ3, AQ5, AQ7, AQ10, AQ12, AQ14)
    are qualitative-only and will show NaN for quantitative data.
- Save EC

### Step 3: Fish EC (Quantitative)
- New EC → "Fish"
- Upload tutorial/fish.csv
- Set data type: quantitative
- Classify rare species as RRF:
  - Eel, Whitefish, Asp, TwaiteShad, Burbot → RRF
- Review AQ results:
  - AQ2 (LRF quant): may show values if some species are locally rare
  - AQ4 (RRF quant): rare fish abundance — the 5 RRF species
  - AQ8 (ROF quant): common species abundance
  - AQ9 (ROF concentration): spatial hotspots
  - AQ6, AQ11, AQ13, AQ15: NaN (no NRF/ESF/HFS/SS classified)
- Save EC

### Step 4: Habitats EC (Qualitative)
- New EC → "Benthic Habitats"
- Upload tutorial/habitats.csv
- Set data type: qualitative
- No special classifications needed
- Review AQ results:
  - AQ1 (LRF qual): locally rare habitat types — will show values
    only if some habitat types occur in <=5% of subzones. If all
    habitats are widespread, AQ1 will be NaN.
  - AQ7 (all features qual): habitat diversity per subzone — ALWAYS
    active for qualitative data, this is the baseline AQ
  - AQ3, AQ5, AQ10, AQ12, AQ14: NaN (no special classifications)
- Save EC

### Step 5: Review Grid-Based Total EV
- Total EV tab: see aggregated results across Benthos + Fish + Habitats
- Total EV = MAX of the three EC EVs per subzone (not sum or average)
- Download Excel report
- Visualization tab: AQ Breakdown, Radar Comparison, Heatmap
- Map tab: display EV, switch between AQ layers

## Part B: Zone-Based ECs (Plankton — Standalone Demo)

### Step 6: Plankton Demonstration
- Important: plankton data uses 5 ecological zones as "subzones",
  not the 425 hexagonal cells. These cannot be combined with
  grid-based ECs for Total EV because Subzone IDs don't match.
- Delete all saved ECs (or start fresh)
- Do NOT load grid.geojson (no spatial grid for zone data)
- Upload zooplankton.csv as new EC "Zooplankton" (quantitative)
- Upload phytoplankton.csv as new EC "Phytoplankton" (quantitative)
- Review individual AQ results for each
- Note: this demonstrates the app works with any spatial resolution,
  including coarse ecological zones

## Part C: Wrap-Up

### Step 7: Physical Accounts (Optional)
- Reload grid.geojson and benthos/habitats ECs
- Physical Accounts tab: assign habitat types to subzones
- View extent table

### Interpreting Your Results
- What high/low EV means ecologically
- EV is relative to this study area — cannot compare between BBTs
- Confidence is low (few AQs answered per EC) — this is typical
  for first-pass assessments and highlights data gaps
- Comparison with the published Lithuanian BBT5 results:
  zooplankton dominated the Total EV in the original analysis too
```

## App Fix Required

**File:** `app.py`, functions `total_ev_ui` and `total_ev_table`

**Change:** Replace `merged[ec_names].sum(axis=1)` with `merged[ec_names].max(axis=1)` in both functions. This aligns the app with the EVA Guidance (Nov 2024 revision) and the data repair pipeline (script 04).

**Impact:** Total EV values will decrease (MAX <= SUM). Values will stay in [0, 5] range.

## Constraints

- Tutorial CSVs must work with the app after the SUM→MAX fix
- Data files should be small enough for git (<10MB each)
- Tutorial document references only files in `tutorial/` — no external dependencies
- Plankton zone-level data acknowledged as a limitation, not hidden
- All data attributed to original sources (EPA Lithuania, ICES BITS, etc.)
- Grid-based and zone-based ECs are assessed in separate tutorial parts to avoid ID mismatch confusion

## Success Criteria

1. A new user can follow the tutorial from start to finish in ~30 minutes
2. All 5 tutorial CSVs upload without errors in the Shiny app
3. Each EC produces expected AQ scores (non-zero for active AQs, NaN for inactive)
4. Grid-based Total EV (3 ECs) aggregates correctly with MAX, values in [0, 5]
5. Map visualization shows spatial patterns for grid-based ECs
6. Tutorial document is self-contained — no prior EVA knowledge needed
7. Preparation script validates Subzone ID consistency between CSVs and grid
