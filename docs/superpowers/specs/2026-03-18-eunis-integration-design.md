# EMODnet EUNIS L3 Integration — Design Spec

**Date:** 2026-03-18
**Status:** Approved (post-review, all issues addressed)

## Goal

Integrate EUSeaMap EUNIS Level 3 habitat data into the EVA Shiny app's Physical Accounts module, enabling standardized BBT8-format PA reports with real habitat classification.

## Architecture

A one-time extraction script clips the EUSeaMap GDB to a BBT study area and overlays it onto the hexagonal grid. The app loads the pre-extracted EUNIS GeoPackage, assigns dominant habitats to subzones, and computes extent/condition/supply accounts per EUNIS class. Export follows the BBT8 format (multi-sheet Excel + GeoPackage).

## EUNIS Code System Note

EUSeaMap uses **EUNIS 2007/2012** codes (e.g., `A5.25`, `A3.4`) in its `EUNIScomb` column. The existing `pa_config.py` uses **EUNIS 2022** codes (e.g., `MA12`, `MB62`). These are different systems.

**Resolution:** The overlay GeoPackage carries its own code→name mapping via `dominant_EUNIS` (code) and `dominant_EUNIS_name` (full description from `EUNIScombD`). When EUNIS overlay is loaded, the app uses overlay codes/names directly — it does NOT attempt to resolve against `pa_config.EUNIS_LOOKUP`. The habitat selector dropdowns are dynamically populated from the overlay data, not from the static `EUNIS_HABITATS` list.

## Data Sources

| Source | Path | Size | Contents |
|--------|------|------|----------|
| EUSeaMap 2023 GDB | `BBTs/EMODNET/EUSeaMap_2023.zip` | 1.5 GB | Pan-European EUNIS L3 habitat polygons |
| Lithuanian hex grid | `EVA_FINAL/EVA Grids/HexGrid3kmLithuanianBBT.gpkg` | 110 KB | 425 hexagonal cells, EPSG:3346 |
| Corrected EVA | `EVA_FINAL_corrected/ALL4EVA_2025_fixed_geometries.gpkg` | ~460 MB | EVA scores per grid cell |

EUSeaMap Lithuanian bbox (EPSG:4326): 1,145 EUNIS polygons, 20 unique habitat types (716 after excluding "Na").

## Deliverables

### 1. Extraction script: `scripts/extract_eunis_for_bbt.py`

**Input:** EUSeaMap GDB path + hex grid GeoPackage path + output path
**Output:** `tutorial/eunis_l3_lithuanian.gpkg` (~2 MB)

**Algorithm:**
1. Read hex grid, determine bbox in EPSG:4326 (reproject if grid CRS differs)
2. Read EUSeaMap GDB layer `EUSeaMap_2023` with bbox filter
3. Exit with clear message if bbox yields 0 features
4. Filter out features where `EUNIScomb == "Na"` (unclassified)
5. Reproject EUNIS polygons to hex grid CRS
6. For each hex cell (with progress logging):
   a. Compute intersection geometry with each overlapping EUNIS polygon
   b. Calculate intersection area in metric CRS
   c. Assign `dominant_EUNIS` = EUNIS code with largest intersection area
   d. Assign `dominant_EUNIS_name` = full name from `EUNIScombD`
   e. Assign `habitat_count` = number of distinct EUNIS types with >0 intersection area
   f. Assign `dominant_pct` = % of hex area covered by dominant type
   g. Assign `coverage_pct` = total EUNIS coverage as % of hex area (identifies hexes with poor EUSeaMap coverage)
7. Write output GeoPackage with columns:
   - `Subzone_ID` (R{row}_C{col} format)
   - `dominant_EUNIS` (e.g., "A5.25")
   - `dominant_EUNIS_name` (e.g., "Circalittoral fine sand")
   - `habitat_count` (integer)
   - `dominant_pct` (float, 0-100)
   - `coverage_pct` (float, 0-100)
   - `geometry` (hex polygon)

**Error handling:**
- Validate grid CRS; reproject to EPSG:4326 for bbox extraction if needed
- Exit with message if 0 features after Na filtering
- Log progress every 50 hex cells
- Skip hex cells with 0 EUNIS intersections (set all values to NaN)

**CLI usage:**
```bash
python scripts/extract_eunis_for_bbt.py \
  --euseamap "path/to/EUSeaMap_2023.zip" \
  --grid "path/to/HexGrid.gpkg" \
  --output "tutorial/eunis_l3_lithuanian.gpkg"
```

**Multi-code handling:** Compound entries like "A5.24 or A5.33 or A5.34" are kept as-is (single string). They represent areas where EUSeaMap could not distinguish between types. The BBT8 accounts table accepts these compound codes (other BBTs have them too).

### 2. New module: `eunis_data.py`

Pure functions for EUNIS data processing (no Shiny dependencies):

```python
def load_eunis_overlay(path: str) -> gpd.GeoDataFrame:
    """Load pre-extracted EUNIS overlay GeoPackage.
    Returns GeoDataFrame with Subzone_ID, dominant_EUNIS, dominant_EUNIS_name,
    habitat_count, dominant_pct, coverage_pct, geometry."""

def compute_eunis_extent(eunis_gdf: gpd.GeoDataFrame, unit: str = "Ha") -> pd.DataFrame:
    """Compute area per EUNIS class from dominant habitat assignments.
    Uses hex cell geometry area (not EUSeaMap polygon areas) for consistency.
    Returns: EUNIS_code, EUNIS_name, n_subzones, total_area, pct_of_total."""

def compute_eunis_condition(
    eunis_gdf: gpd.GeoDataFrame,
    eva_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Join EVA scores to EUNIS classes via Subzone_ID.
    For each EUNIS class, compute mean of per-subzone max(EC scores) as Habitat_EV.
    Confidence = mean of per-subzone confidence scores (from Confidence column if present).
    Returns: EUNIS_code, EUNIS_name, Habitat_EV, Habitat_confidence, n_subzones."""

def compute_eunis_supply(
    eunis_gdf: gpd.GeoDataFrame,
    eva_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Compute ecosystem service proxies per EUNIS class.
    Joins on Subzone_ID, groups by dominant_EUNIS.
    EVA column mapping:
      EVA_all_fish → Fisheries provisioning (proxy)
      ZooScore → Food web support (proxy)
      PhytoScore → Primary production (proxy)
    Aggregation: mean per EUNIS class.
    Returns: EUNIS_code, Fisheries_proxy, FoodWeb_proxy, PrimaryProd_proxy."""

def build_accounts_summary(
    extent: pd.DataFrame,
    condition: pd.DataFrame,
) -> pd.DataFrame:
    """Build BBT8-format accounts table.
    Returns: EUNIS_code, EUNIS_name, area_m2, Habitat_EV, Habitat_confidence.
    Area in m2 (BBT8 standard internal unit; displayed as km2 in reports)."""

def build_missing_values(
    eunis_gdf: gpd.GeoDataFrame,
    eva_gdf: gpd.GeoDataFrame,
    total_bbt_area_m2: float,
) -> pd.DataFrame:
    """Identify subzones with no EUNIS match or no EVA data.
    Returns: Subzone_ID, issue_type ('no_eunis' or 'no_eva'), notes."""
```

**Relationship to existing `pa_calculations.py`:** `compute_eunis_extent` is a parallel function to `pa_calculations.compute_extent`. When EUNIS overlay is present, the BBT8 export calls `eunis_data.compute_eunis_extent` (more accurate, uses standardized codes). The existing `compute_extent` remains for the manual habitat assignment flow.

### 3. Updated PA export: `pa_export.py`

New function:

```python
def generate_bbt8_workbook(
    accounts: pd.DataFrame,
    main_values: pd.DataFrame,
    extent: pd.DataFrame,
    condition: pd.DataFrame,
    supply: pd.DataFrame,
    metadata: dict,
    missing_values: pd.DataFrame | None = None,
) -> io.BytesIO:
```

**Sheet definitions (matching BBT8 Irish Sea format):**

| Sheet name | Columns | Source |
|------------|---------|--------|
| `ReadMe` | Parameter, Value (key-value pairs) | metadata dict |
| `main_values` | Subzone_ID, EUNIS_code, Habitat_EV, Habitat_confidence, area_m2 | Per-subzone from overlay + EVA join |
| `habitat_area_sum` | EUNIS_code, sum_area_m2 | Grouped from main_values |
| `accounts` | EUNIS_code, EUNIS_name, area_m2, Habitat_EV, Habitat_confidence | Summary per EUNIS class |
| `missing_values` | Subzone_ID, issue_type, notes | From build_missing_values |
| `condition` | EUNIS_code, EUNIS_name, + per-indicator mean/std/count | Detailed condition stats |
| `supply` | EUNIS_code, EUNIS_name, Fisheries_proxy, FoodWeb_proxy, PrimaryProd_proxy | Ecosystem service proxies |

### 4. App UI changes

**PA sidebar additions** (in `eva_ui.py`, PA section):
- New section "EUNIS Habitat Data" with file upload widget
- Status display after upload: "Loaded X EUNIS types covering Y% of subzones"
- Download button: "Download BBT8 Physical Accounts (Excel)"

**Server integration** (in `app.py`, PA section):
- New reactive: `eunis_overlay = reactive.Value(None)`
- Upload handler: reads GPKG, validates columns, stores in reactive
- When EUNIS overlay is loaded:
  - Dynamically populate `all_habitat_choices` from overlay's unique `dominant_EUNIS` + `dominant_EUNIS_name` (NOT from `pa_config.EUNIS_HABITATS`)
  - Auto-set `pa_habitat_assignments` from `{Subzone_ID: dominant_EUNIS}` via updating dropdown defaults (same pattern as existing auto-detect at app.py line ~1496)
  - User can still override any assignment via dropdowns
- New output renderers: `eunis_extent_table`, `eunis_condition_table`, `eunis_accounts_preview`
- BBT8 download handler: calls `eunis_data` functions → `generate_bbt8_workbook`

**Confidence join path:** Confidence is per-subzone (from `Confidence` column added by repair pipeline script 05). The EUNIS condition function joins EVA data to overlay on `Subzone_ID`, then groups by `dominant_EUNIS`, computing `mean(Confidence)` per EUNIS class → `Habitat_confidence`.

### 5. Integration with existing PA flow

- If EUNIS overlay loaded → auto-populates assignments, enables BBT8 export
- If no overlay → existing manual flow works unchanged
- Both flows can coexist: manual overrides apply on top of EUNIS auto-assignments
- Existing PA export (standalone + combined) still available alongside BBT8 export

## Testing

| Test file | Tests |
|-----------|-------|
| `tests/test_eunis_data.py` | load/extent/condition/supply/accounts/missing — synthetic GeoDataFrames |

## Constraints

- Pre-extracted EUNIS GeoPackage must be <10 MB for git
- Extraction script must handle any BBT (parameterized, not hardcoded)
- App must work without EUNIS overlay (backward compatible)
- EUSeaMap compound codes ("A5.24 or A5.33 or A5.34") treated as single type

## Success Criteria

1. Extraction script produces valid EUNIS overlay for Lithuanian BBT
2. App loads overlay and auto-populates habitat assignments
3. Extent table shows EUNIS L3 codes with correct areas
4. Condition table shows mean EVA scores per EUNIS class
5. BBT8-format Excel matches Irish Sea standard (sheet names, column layout)
6. Existing PA functionality works without EUNIS overlay
7. All tests pass
