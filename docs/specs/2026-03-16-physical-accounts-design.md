# Physical Accounts Module — Design Specification

**Date:** 2026-03-16
**Status:** Draft
**Reference:** Draft Guidance on Socio-Economic Frameworks and Methods, Physical Accounts Section (MARBEFES D4.2, 2023)

## Overview

A new module for the MARBEFES EVA application that implements Physical Natural Capital Accounts following the SEEA EA framework and the MARBEFES 7-step process (Steps 1-6). The module produces Ecosystem Extent and Supply tables aligned with the MARBEFES guidance document (Tables 2A.1-2A.4).

**Initial scope (v1):** Extent Account + Supply Table for a single accounting period.
**Future scope (stubs):** Use Table, Condition Account, multi-year time series.

## Architecture

### New Files

| File | Responsibility |
|------|---------------|
| `pa_config.py` | Constants: EUNIS Level 3 reference table (~40-60 marine codes), default benefits list (5 core + extensible), units, methodology text, export styling |
| `pa_calculations.py` | Pure functions: extent aggregation from spatial grid, supply table assembly, validation, CRS handling |
| `pa_export.py` | Excel workbook generation (standalone + combined with EVA) |

### Integration with Existing Code

- **`app.py`** gains a new "Physical Accounts" nav tab with sidebar + 3 content cards
- **Shared GIS infrastructure**: reuses the existing spatial grid upload flow, CRS reprojection, and Folium map rendering. However, a new `geo_data_full` reactive is introduced (see GIS Data Strategy below) to preserve attribute columns stripped by the current handler.
- **Shared export infrastructure**: `eva_export.py` is refactored to expose a `build_workbook() -> Workbook` function alongside the existing `generate_workbook() -> BytesIO` (which becomes a thin wrapper). This allows `pa_export.py` to extend the EVA workbook directly for combined export.
- **Map tab** extended with "Habitat Type" categorical choropleth option

### GIS Data Strategy

The current `handle_geojson_upload()` in `app.py:1351` strips the GeoDataFrame to `['Subzone ID', 'geometry']` before storing in `geo_data`. The Physical Accounts module needs additional attribute columns (e.g., EUNIS habitat type) from the spatial file.

**Solution:** Introduce a new `geo_data_full` reactive that stores the complete GeoDataFrame (all columns preserved, reprojected to WGS84). The existing `geo_data` reactive continues unchanged for backward compatibility with EVA. The PA module reads `geo_data_full` for habitat auto-detection, and `geo_data` for geometry/area calculations.

Change to `handle_geojson_upload()`:
```python
# After reprojection, before stripping columns:
geo_data_full.set(gdf.copy())           # NEW: preserve all columns
gdf = gdf[['Subzone ID', 'geometry']]   # existing behavior
geo_data.set(gdf)
```

### CRS & Area Unit Handling

GeoPandas `.area` returns values in the CRS's native units. To produce correct km²/Ha values:

1. `pa_calculations.py:compute_extent()` receives the GeoDataFrame in WGS84 (EPSG:4326) from `geo_data` and an optional `original_crs` string parameter
2. Before computing areas, it reprojects to a metric CRS:
   - Parse `original_crs` string via `pyproj.CRS.from_user_input()` and check `.is_projected` — if True, reproject to that CRS
   - Otherwise, use UTM zone auto-detected from the centroid of the bounding box (`int((lon + 180) / 6) + 1`)
   - Fallback: EPSG:3857 (Web Mercator) with a logged warning about area distortion at high latitudes
3. `.area` returns m². Conversion factors applied: `1 Ha = 10,000 m²`, `1 km² = 1,000,000 m²`
4. The area unit (km² or Ha) is user-configurable via the sidebar toggle

Function signature:
```python
def compute_extent(
    gdf: gpd.GeoDataFrame,          # WGS84, with 'Subzone ID' and 'geometry'
    habitat_assignments: dict,       # {subzone_id: eunis_code}
    unit: str = "Ha",               # "Ha" or "km2"
    original_crs: str | None = None # Original CRS string for metric reprojection
) -> pd.DataFrame:                  # Columns: eunis_code, habitat_name, area, pct_total
```

### Pattern

Follows the existing EVA modularization: stateless config, calculations, and export modules. No Shiny dependencies in `pa_calculations.py` or `pa_export.py`.

## Data Flow

```
1. User uploads spatial grid (shared with EVA, via Data Input tab)
   └─► Polygons loaded into geo_data (stripped) and geo_data_full (all columns)

2. User selects EUNIS habitat types (from built-in reference or custom)
   └─► pa_habitat_selection reactive

3. User assigns habitats to subzones
   a) Auto-detect: check geo_data_full for habitat column → pre-populate
   b) Manual: user assigns via per-subzone dropdowns
   └─► pa_habitat_assignments reactive: {subzone_id: eunis_code}

4. Module computes Extent Account from spatial grid polygon areas
   └─► Reproject to metric CRS → .area → aggregate by EUNIS type → convert units

5. User configures benefits (select defaults or add custom with unique name + unit)
   └─► pa_benefits_config reactive

6. User enters quantities per benefit × habitat type via numeric input grid
   └─► pa_supply_data reactive → Supply Table

7. Export to Excel (standalone PA workbook or combined with EVA)
```

## EUNIS Reference Data & Habitat Configuration

### Built-in EUNIS Level 3 Reference

Stored in `pa_config.py` as a list of dicts. Initial curated list of ~40-60 marine EUNIS Level 3 codes covering Mediterranean, Baltic, and Atlantic habitats relevant to MARBEFES BBTs:

```python
EUNIS_HABITATS = [
    {"code": "MA12", "name": "Littoral coarse sediment", "level": 3, "parent": "MA1"},
    {"code": "MB252", "name": "Posidonia oceanica meadows", "level": 3, "parent": "MB25"},
    {"code": "MC352", "name": "Mediterranean coastal detritic bottoms", "level": 3, "parent": "MC35"},
    {"code": "MC3521", "name": "Association with rhodolithes", "level": 3, "parent": "MC352"},
    ...
]
```

Users select from a searchable multi-select dropdown (using `ui.input_selectize` with search enabled). Custom entries can be added with code + name. The dropdown handles up to ~60 items well with the selectize search widget.

### Habitat-to-Grid Mapping

**Auto-detect from spatial file:**
The module checks `geo_data_full` for habitat columns using an ordered candidate list:
```python
HABITAT_COLUMN_CANDIDATES = [
    "EUNIS", "eunis", "EUNIS_code", "eunis_code",
    "Habitat", "habitat", "habitat_type", "Habitat_type",
    "EUNIS_Level3", "eunis_level3",
]
```
First match wins. If multiple candidates exist, the first in the list takes priority. Values not found in `EUNIS_HABITATS` are treated as custom habitat codes with a warning notification. If no candidate column is found, manual assignment is required.

**Manual assignment:**
UI table with each Subzone ID paired with a dropdown to select a EUNIS habitat type. Pre-populated from auto-detect if available.

**Constraints (v1):** One subzone = one habitat type. Unassigned subzones are excluded from extent calculations with a warning.

### TODO: Mixed-Habitat Subzones

Future versions may support fractional habitat assignment (e.g., subzone A1 = 60% seagrass, 40% detritic) with proportional area splitting.

## Benefits Configuration & Supply Table

### Default Benefits Reference

From the 5 MARBEFES logic chain benefits, stored in `pa_config.py`:

```python
DEFAULT_BENEFITS = [
    {"name": "Wild food (finfish)", "unit": "tonnes", "ecosystem_service": "Wild fish"},
    {"name": "Healthy climate", "unit": "tCO2eq", "ecosystem_service": "Carbon sequestration & storage"},
    {"name": "Recreation & nature watching", "unit": "visitor-days", "ecosystem_service": "Places and seascapes"},
    {"name": "Erosion/flood prevention", "unit": "Ha protected", "ecosystem_service": "Natural hazard protection"},
    {"name": "Clean water", "unit": "tonnes N removed", "ecosystem_service": "Waste remediation"},
]
```

### User Workflow

1. Select which benefits apply (checkboxes from reference list)
2. Add custom benefits with unique name + unit (name uniqueness enforced — duplicate names rejected with notification)
3. Enter physical quantities per benefit × habitat type via a grid of `ui.input_numeric` widgets
4. Empty cells tracked as data gaps (the guidance expects partial data)

### Supply Table Input Widget

Python Shiny does not have a built-in editable data grid. The supply table is implemented as a dynamically generated matrix of `ui.input_numeric` inputs:

- Input IDs follow the pattern: `supply_{benefit_slug}_{eunis_code}` where `benefit_slug` is computed as `re.sub(r'\W+', '_', name.lower()).strip('_')` — this function is used consistently both when rendering the grid and when reading input values back into `pa_supply_data`
- Grid is rendered via `@render.ui` and regenerated when benefits or habitats change
- Row headers = benefit names with units; column headers = EUNIS codes with habitat names
- For up to ~5 benefits × ~10 habitats (50 inputs), this scales well within Shiny's reactive framework
- If the matrix exceeds 100 inputs, a warning suggests using fewer habitat types or benefits

### Validation

Validation runs on every input change (reactive) and is advisory (does not block export):

- **Warning:** Benefit with no quantities for any habitat (0% filled for that row)
- **Warning:** Habitat with no benefits assigned (0% filled for that column)
- **Info:** Data completeness percentage displayed as "X of Y cells filled (Z%)"

Follows the existing EVA pattern of inline advisory warnings (colored text, not modal dialogs).

### TODO: Use Table

Disaggregate the same supply quantities by beneficiary sector:

```python
pa_use_data = {benefit_name: {sector_name: quantity}}
# Sectors: society (households/government), fishing, tourism, cosmetics, etc.
```

### TODO: Condition Account

SEEA condition typology with opening/closing values:

```python
pa_condition_data = {
    eunis_code: {
        variable_name: {
            "descriptor": str,
            "unit": str,
            "typology_class": "compositional|structural|functional|landscape",
            "opening_value": float,
            "closing_value": float,
        }
    }
}
```

### TODO: Multi-Year Time Series

```python
pa_years = [2019, 2020, 2021, 2022, 2023]
# Supply data indexed by year
# Extent with opening/closing stocks per year
# Net change tracking: managed/unmanaged expansions and reductions
```

## UI Layout

### New Nav Tab: "Physical Accounts"

**Sidebar:**
- Study area metadata (EAA name, boundary description, accounting year)
- EUNIS habitat selector (searchable multi-select via `ui.input_selectize` + "Add custom" button)
- Benefits configurator (checkboxes for 5 defaults + "Add custom" with name/unit fields, name uniqueness enforced)
- Area units toggle (km² / Ha)
- Export buttons (standalone / combined with EVA)

**Main Content — 3 Cards:**

1. **Habitat Assignment Card**
   - Auto-detect status: shows which column was matched (or "No habitat column found — manual assignment required")
   - Table of Subzone IDs with dropdown to assign/override habitat type
   - Summary: "X of Y subzones assigned (Z unassigned)"

2. **Habitat Extent Card**
   - Computed extent table: EUNIS code | Habitat name | Area | % of total
   - Derived from spatial grid polygon areas aggregated by habitat type
   - If no spatial grid uploaded: prompt card linking to Data Input tab
   - Future scope info box (muted blue `info-box` style, not error): "Opening/closing stock tracking and change analysis will be available in a future version."

3. **Supply Table Card**
   - Dynamic grid of `ui.input_numeric` widgets (rows = benefits, columns = habitats)
   - Row headers show benefit name + unit; column headers show EUNIS code + short name
   - Data completeness indicator: "X of Y cells filled (Z%)"
   - Future scope info box: "Use Table (sector disaggregation) and Condition Account will be available in a future version."

### Map Integration

The existing Map tab's `map_variable` dropdown gains a new option: **"Habitat Type (PA)"**.

The option is added/removed dynamically via `ui.update_select("map_variable", choices=updated_list)` called from a reactive observer watching `pa_habitat_assignments`. When no habitat assignments exist, the option is simply absent from the choices list (not greyed out, as Shiny selects don't support per-option disabling).

When selected, the map renders a **categorical choropleth** instead of the continuous color scale:
- Each EUNIS habitat type gets a distinct color from a qualitative palette (Plotly `Plotly` or `Set3` palette, up to 12 colors; habitats beyond 12 cycle with pattern fills)
- Legend shows EUNIS code + name → color mapping
- Tooltips show: Subzone ID, EUNIS code, habitat name, area
- This option is only enabled when `pa_habitat_assignments` has data; otherwise greyed out with tooltip "Assign habitats in Physical Accounts tab first"
- Implementation: separate code path in `create_ev_map()` triggered by `variable == "Habitat Type (PA)"`, using `folium.GeoJson` with a `style_function` keyed on EUNIS code

### Known v1 Limitation: Session Persistence

Custom benefits, habitat assignments, and supply data persist only within the Shiny session (via reactive values). Data is lost on page refresh. Users should export their work before closing. A future version may add session serialization (save/load JSON).

## Reactive Data Model

### New Reactive Values

| Reactive Value | Type | Description |
|---|---|---|
| `geo_data_full` | `GeoDataFrame or None` | Full spatial data with all attribute columns preserved |
| `pa_habitat_selection` | `list[str]` | Selected EUNIS codes |
| `pa_habitat_assignments` | `dict[str, str]` | `{subzone_id: eunis_code}` |
| `pa_benefits_config` | `list[dict]` | `[{"name": str, "unit": str, "active": bool, "custom": bool}]` — benefit names must be unique |
| `pa_supply_data` | `dict[str, dict[str, float]]` | `{benefit_name: {eunis_code: quantity}}` — keyed by unique benefit name |
| `pa_metadata` | `dict` | Schema below |

### `pa_metadata` Schema

```python
pa_metadata = {
    "eaa_name": str,               # Ecosystem Accounting Area name
    "boundary_description": str,    # Text description of EAA boundary
    "accounting_year": int,         # e.g. 2023
}
# The following are auto-populated at export time, not stored in reactive:
# export_date, app_version (from pa_config.APP_VERSION), data_completeness_pct
```

### TODO: Future Reactive Values

| Reactive Value | Type | Description |
|---|---|---|
| `pa_use_data` | `dict[str, dict[str, float]]` | `{benefit_name: {sector_name: quantity}}` |
| `pa_condition_data` | `dict[str, dict]` | Condition variables per habitat |
| `pa_years` | `list[int]` | Accounting periods |
| `pa_extent_changes` | `dict[str, dict[str, float]]` | Managed/unmanaged expansion/reduction per habitat |

## Export

### Export Architecture

To support combined export, `eva_export.py` is refactored:

```python
# eva_export.py — refactored public API:

def build_workbook(...) -> openpyxl.Workbook:
    """Build and return the styled EVA workbook object (not serialized)."""
    # Contains the existing logic from generate_workbook, minus the BytesIO wrapping

def generate_workbook(...) -> io.BytesIO:
    """Build workbook and serialize to BytesIO. Backward-compatible entry point."""
    wb = build_workbook(...)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
```

`pa_export.py` can then:
- **Standalone:** Build its own workbook from scratch
- **Combined:** Call `eva_export.build_workbook()` to get the EVA workbook, then append PA sheets to it before serializing

### Standalone Physical Accounts Workbook

| Sheet | Content |
|-------|---------|
| Summary & Metadata | EAA name, accounting year, boundary description, app version, export date, data completeness % |
| Ecosystem Extent Account | Table 2A.1 format: EUNIS habitats × area (with unit) with totals row |
| Supply Table | Table 2A.2 format: benefits (with units) × habitat types with quantities |
| Habitat Assignments | Subzone ID → EUNIS code → habitat name mapping |
| EUNIS Reference | All EUNIS codes and names used in this analysis |
| Methodology | SEEA EA framework description, data sources note, completeness gaps listed |

### Methodology Sheet Content

Defined in `pa_config.py`:

```python
PA_METHODOLOGY = {
    "Topic": [
        "Framework", "Standard", "Habitat Classification",
        "Extent Method", "Supply Method", "Data Completeness",
    ],
    "Description": [
        "MARBEFES 7-step Natural Capital Accounting process (Steps 1-6: Physical Accounts)",
        "System of Environmental-Economic Accounting — Ecosystem Accounting (SEEA EA, UN 2021)",
        "EUNIS Level 3 habitat classification system",
        "Polygon area aggregation from spatial grid, reprojected to metric CRS",
        "User-entered physical quantities per societal benefit per habitat type",
        "Computed at export: X of Y supply cells populated",
    ],
}
```

### Combined Workbook (EVA + Physical Accounts)

- EVA workbook built via `eva_export.build_workbook()` which accepts an optional `pa_summary_data: dict | None = None` parameter
- When `pa_summary_data` is provided, `_build_summary_sheet()` appends a "Physical Accounts" section (EAA name, accounting year, extent summary) during construction — keeping row layout knowledge inside `eva_export.py`
- PA sheets appended to the returned workbook with distinct tab color (`#009688` teal)

### TODO: Future Export Sheets

- Use Table sheet (benefits × sectors)
- Condition Account sheet (per ecosystem type, SEEA typology classes)
- Multi-year comparison sheets (time series across accounting periods)

## Testing Strategy

`pa_calculations.py` is pure and stateless — all functions are unit-testable:

| Test | Input | Expected Output |
|------|-------|-----------------|
| `test_compute_extent_basic` | GeoDataFrame with 3 polygons, 2 habitat types | Correct aggregated areas in Ha and km² |
| `test_compute_extent_unassigned` | GeoDataFrame with unassigned subzones | Unassigned excluded, warning returned |
| `test_compute_extent_metric_crs` | GeoDataFrame in UTM vs WGS84 | Same area results after reprojection |
| `test_assemble_supply_table` | Supply data dict + habitat list | Correct DataFrame matching Table 2A.2 format |
| `test_validate_completeness` | Partial supply data | Correct completeness percentage |
| `test_benefit_name_uniqueness` | Duplicate benefit names | Validation error returned |

Tests should use small synthetic GeoDataFrames (3-5 polygons) with known areas.

## SEEA EA Alignment

The module aligns with the SEEA EA framework as follows:

| SEEA EA Concept | Module Implementation |
|---|---|
| Ecosystem Accounting Area (EAA) | Study area defined by spatial grid boundary |
| Ecosystem Type | EUNIS Level 3 habitat classification |
| Ecosystem Extent | Polygon area aggregated by habitat type |
| Ecosystem Services (physical) | Supply table quantities per benefit per habitat |
| Accounting Period | Single year (v1); multi-year TODO |
| Opening/Closing Stock | TODO: extent changes with managed/unmanaged tracking |
| Condition Assessment | TODO: SEEA typology (compositional, structural, functional, landscape) |
| Use Table | TODO: sector disaggregation of supply quantities |
