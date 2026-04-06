# EVA_FINAL Data Repair Pipeline — Design Spec

**Date:** 2026-03-18
**Author:** Claude (with user direction)
**Status:** Draft

## Goal

Fix all correctable data quality issues in the Lithuanian BBT5 EVA_FINAL dataset by producing a set of corrected spatial layers and a validation report, using standalone Python scripts that are reproducible and versionable.

## Context

Analysis of `EVA_FINAL/` against the MARBEFES WP4.1 EVA Guidance (Franco & Amorim, June 2025) identified critical issues: -9999 sentinel values in AQ13, MEAN aggregation instead of MAX for Total EV, CRS inconsistencies, missing Subzone IDs, and no confidence index. All fixes use only data already present in EVA_FINAL.

## Input Data

| File | Contents | Issues |
|------|----------|--------|
| `ALL4EVA_2025_fixed_geometries.gpkg` | Combined EVA (721,900 features) | AQ13=-9999, no Subzone ID, MEAN aggregation |
| `All4EVA_2025.gpkg` | Combined EVA with FinalTotalEVAmax | Same issues + has MAX column |
| `NewBenthos.shp` | Benthos AQ6/AQ7/AQ9/AQ13 (41,061 features) | AQ13=-9999 |
| `All_EVA_Sept_2025.shp` | Final EVA shapefile (721,900 features) | AQ13=-9999, truncated column names |
| `final_EVA_without_Fish.gpkg` | EVA sans fish (274,985 features) | AQ13=-9999 |
| `OLD_EVA_PLUS_NEW_AQ7.shp` | Older EVA + new AQ7 (57,334 features) | Has MaxEVA column (MAX aggregation) |
| `chrophyta_score.gpkg`, `copepoda_score.gpkg`, `cladocera_score.gpkg` | Plankton scores | CRS EPSG:3035 (should be 3346) |
| `AllFishAQ.gpkg` | Fish AQ scores (850 features) | 94% null in combined layer |

## Architecture

```
EVA Algorithms/
  scripts/                          # NEW — data repair pipeline
    01_clean_sentinels.py
    02_standardize_crs.py
    03_add_subzone_ids.py
    04_recompute_total_ev.py
    05_compute_confidence.py
    06_validate_and_report.py
    run_all.py                      # Master script
    config.py                       # Shared paths and constants
  tests/
    test_repair_scripts.py          # Unit tests for repair logic
```

Output written to `EVA_FINAL_corrected/` (sibling of `EVA_FINAL/`).

## Script Specifications

### config.py — Shared Configuration

```python
EVA_FINAL_DIR = r"C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\EVA_FINAL"
OUTPUT_DIR = r"C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\EVA_FINAL_corrected"
TARGET_CRS = "EPSG:3346"  # LKS94 / Lithuania TM
SENTINEL_VALUE = -9999
EVA_SCALE_MAX = 5
EVA_SCALE_MIN = 0
```

Datasets dict mapping logical names to file paths and which columns need fixing.

### 01_clean_sentinels.py

**Purpose:** Replace -9999 sentinel values with NaN/NULL in all AQ columns.

**Files processed:**
- `ALL4EVA_2025_fixed_geometries.gpkg` → column `AQ13_benthos`
- `All4EVA_2025.gpkg` → column `AQ13_benthos`
- `NewBenthos.shp` → column `AQ13`
- `All_EVA_Sept_2025.shp` → column `AQ13_benth`
- `final_EVA_without_Fish.gpkg` → column `AQ13_benthos`

**Logic:**
1. Read each file with geopandas
2. Find AQ columns by pattern matching (`AQ*` prefix) — do not hardcode truncated shapefile names. Log warning if expected column not found but similar one is.
3. For each AQ column: replace values <= -9998 with NaN
4. Log: file, column, count replaced, new min/max/mean
5. Write to OUTPUT_DIR preserving original filename

**Validation:** After fix, all AQ columns must have values in [0, 5] or NaN.

### 02_standardize_crs.py

**Purpose:** Reproject layers in EPSG:3035 to EPSG:3346.

**Files processed:**
- `chrophyta_score.gpkg` (EPSG:3035 → 3346)
- `copepoda_score.gpkg` (EPSG:3035 → 3346)
- `cladocera_score.gpkg` (EPSG:3035 → 3346)

**Logic:**
1. Read with geopandas
2. If CRS != TARGET_CRS, reproject with `to_crs(TARGET_CRS)`
3. Write to OUTPUT_DIR
4. Log: file, original CRS, new CRS, feature count preserved

**Validation:** All output files have CRS EPSG:3346. Feature count unchanged.

### 03_add_subzone_ids.py

**Purpose:** Generate consistent `Subzone_ID` column across all layers.

**Logic:**
1. For datasets with `row_index`/`col_index`: generate `Subzone_ID = f"R{row_index:03d}_C{col_index:03d}"`
2. For datasets with `fid` only: use `Subzone_ID = f"F{fid:06d}"`
3. Fallback: if neither column exists, use GeoDataFrame integer index as `Subzone_ID = f"I{idx:06d}"` and log a warning
4. Add column to all corrected outputs
5. Log: file, ID generation method, unique ID count

**Validation:** No duplicate Subzone_IDs within any single layer. IDs are consistent between layers sharing the same grid.

### 04_recompute_total_ev.py

**Purpose:** Recompute Total EV using MAX aggregation (per guidance, Nov 2024 revision).

**Input:** Corrected `ALL4EVA_2025_fixed_geometries.gpkg` (after sentinel cleanup).

**EC score columns:**
- `AQ7_HABITATS` — Habitat diversity (qualitative)
- `ZooScore` — Zooplankton EV
- `PhytoScore` — Phytoplankton EV
- `MaxBenthos` — Benthos EV (max of AQ6, AQ7_benthos, AQ9, AQ13)
- `EVA_all_fish` — Fish EV

**Logic:**
1. Read corrected combined layer
2. **Verification step:** For benthos, check that `MaxBenthos == max(AQ6_benthos, AQ9_benthos, AQ13_benthos)` (post-sentinel cleanup). If any EC score was computed with MEAN instead of MAX, use the individual AQ columns to recompute the EC-level EV as MAX. Log any discrepancies found.
3. For each row: `TotalEV_MAX = max(AQ7_HABITATS, ZooScore, PhytoScore, MaxBenthos, EVA_all_fish)` treating NaN as absent (skip in max). All-NaN rows produce NaN.
4. Add `TotalEV_MAX` column
5. Also compute `TotalEV_MEAN` for comparison (mean of non-null scores, using identical NaN-exclusion as MAX)
6. Add `EC_count` column — number of non-null EC scores per subzone
7. Add `Dominant_EC` column — which EC determined the MAX
8. Log: value range, histogram of 5-class distribution (VL/L/M/H/VH), comparison with original

**Validation:** All TotalEV_MAX values in [0, 5] or NaN (when all EC scores are absent). TotalEV_MAX >= TotalEV_MEAN for every non-NaN row.

### 05_compute_confidence.py

**Purpose:** Calculate confidence index per subzone following Equation 1 from guidance.

**Formula (per EC):** `Confidence_EC = sum(AQi * wi) / (N * 5)`

Where:
- `AQi` = 1 if the i-th AQ was computed for this EC, 0 if not
- `N` = max applicable AQs for this EC type (8 for benthic species groups, 7 for all others)
- `wi` = weight (1-5) based on evidence quality. All AQs within the same EC share the same `wi` (evidence quality is an EC-level property).

Total confidence for a subzone = confidence of the **dominant EC** (the one that set TotalEV_MAX).

**Worked example — Benthos:** 4 AQs answered (AQ6, AQ7, AQ9, AQ13), N=8, wi=3.
`Confidence = (4 * 3) / (8 * 5) = 12/40 = 0.30` → **Low** (<=1.67). Expected: 50% AQ coverage with medium evidence.

**Worked example — Habitats:** 1 AQ answered (AQ7), N=7, wi=3.
`Confidence = (1 * 3) / (7 * 5) = 3/35 = 0.09` → **Low**.

**Weight assignment (per BBT5 report data sources):**

| EC | Evidence Base | Data Use | Data Availability | wi |
|----|--------------|----------|-------------------|-----|
| Habitats | Data-based | Model/map products | Medium-High | 3 |
| Zooplankton | Data-based | Direct monitoring | Low (n=12 BS, ~78 CL) | 2 |
| Phytoplankton | Data-based | Direct monitoring | Medium (5-6 stations, monthly) | 3 |
| Benthos soft | Data-based | Model products (SDM) | Medium-High (640 samples) | 3 |
| Benthos hard | Data-based | Direct monitoring (video) | High (1923+822 transects) | 4 |
| Fish CL | Data-based | Indirect (commercial catch) | Medium | 2 |
| Fish BS | Data-based | Direct monitoring (BITS) | Medium (2004-2023) | 3 |

**AQs answered per EC:**

| EC | AQs answered | N | Notes |
|----|-------------|---|-------|
| Habitats | AQ7 | 7 | Only 1 of 7 |
| Zooplankton | AQ8 (as ZooScore) | 7 | Aggregate score, ~1 AQ |
| Phytoplankton | AQ8 (as PhytoScore) | 7 | Aggregate score, ~1 AQ |
| Benthos | AQ6, AQ7, AQ9, AQ13 | 8 | 4 of 8 |
| Fish CL | AQ4 | 7 | Rare fish only |
| Fish BS | AQ4, AQ8 | 7 | Rare + commercial |

**Logic:**
1. For each subzone, determine which EC has data (non-null score)
2. For each EC present, compute confidence using its AQ count and weight
3. Total confidence = confidence of the dominant EC (the one that set TotalEV_MAX)
4. Write as separate GeoPackage with Subzone_ID, per-EC confidence, total confidence
5. Classify: Low (<=1.67), Medium (1.67-3.33), High (>3.33)

### 06_validate_and_report.py

**Purpose:** Run comprehensive quality checks and produce a comparison report.

**Checks:**
1. All AQ values in [0, 5] or NaN (no sentinels)
2. All CRS are EPSG:3346
3. All layers have Subzone_ID column
4. TotalEV_MAX computed correctly
5. Confidence index present
6. Feature counts match originals
7. No geometry corruption (valid geometries)

**Report outputs:**
- `validation_report.md` — human-readable Markdown with tables and statistics
- `validation_summary.xlsx` — Excel with before/after comparison per layer

**Report contents:**
- Executive summary (pass/fail per check)
- Per-layer: feature count, CRS, column list, AQ value ranges (before/after)
- Total EV comparison: MEAN vs MAX distribution, histogram of 5-class changes
- Confidence index distribution
- Data completeness matrix (ECs x subzones)
- List of remaining known limitations

### run_all.py — Master Script

Runs all 6 scripts in sequence. Stops on error. Prints summary at end.

```
python scripts/run_all.py
```

## Testing

`tests/test_repair_scripts.py` — unit tests for the pure logic functions:
- Sentinel replacement: -9999 → NaN, valid values unchanged
- CRS check/reproject logic
- Subzone ID generation: format, uniqueness
- MAX aggregation: correct with NaN, correct dominant EC selection
- Confidence calculation: formula matches guidance Equation 1
- Validation checks: detect out-of-range, detect sentinel, detect wrong CRS

Tests use small synthetic DataFrames, no dependency on EVA_FINAL files.

## Constraints

- Original EVA_FINAL files are NEVER modified
- All outputs go to EVA_FINAL_corrected/
- Scripts must run in the `shiny` conda environment (geopandas, pandas, numpy available)
- Large files (721K features, ~500MB-1GB in memory) fit in 64GB RAM — no chunking needed
- Plankton scores remain as zone-level aggregates (no per-subzone AQ disaggregation possible)
- Missing ECs (birds, macrophytes, CL benthos) cannot be added — data doesn't exist

## Success Criteria

1. Zero -9999 sentinel values in any corrected output
2. All layers in EPSG:3346
3. All layers have consistent Subzone_ID
4. TotalEV_MAX correctly computed using MAX aggregation
5. Confidence index present for every subzone with data
6. Validation report shows all checks passing
7. All unit tests passing
