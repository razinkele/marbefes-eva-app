# Physical Accounts Module Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Physical Natural Capital Accounts module (Extent Account + Supply Table) to the MARBEFES EVA Shiny application, following the SEEA EA framework.

**Architecture:** Three new stateless modules (`pa_config.py`, `pa_calculations.py`, `pa_export.py`) following the existing EVA pattern. A new "Physical Accounts" tab in `app.py` with habitat assignment, extent computation, and supply table entry. Shared GIS infrastructure for spatial data; refactored EVA export for combined workbook support.

**Tech Stack:** Python Shiny, GeoPandas, pyproj, openpyxl, Folium, Plotly, pandas, numpy

**Spec:** `docs/specs/2026-03-16-physical-accounts-design.md`

---

## Chunk 1: Core Config and Calculations

### Task 1: Create `pa_config.py` — constants, EUNIS reference, benefits

**Files:**
- Create: `pa_config.py`

- [ ] **Step 1: Create `pa_config.py` with all constants**

```python
"""
MARBEFES Physical Accounts Configuration Module

All constants, reference data, and metadata for the Physical Accounts module.
"""

import re

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------
PA_MODULE_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Area unit conversion from m²
# ---------------------------------------------------------------------------
AREA_CONVERSIONS = {
    "Ha": 10_000,       # 1 Ha = 10,000 m²
    "km2": 1_000_000,   # 1 km² = 1,000,000 m²
}

AREA_UNIT_LABELS = {
    "Ha": "Hectares (Ha)",
    "km2": "Square kilometres (km²)",
}

# ---------------------------------------------------------------------------
# EUNIS Level 3 Marine Habitat Reference (curated for MARBEFES BBTs)
# Covers Mediterranean, Baltic, and Atlantic habitats
# ---------------------------------------------------------------------------
EUNIS_HABITATS = [
    # Littoral rock and biogenic reef
    {"code": "MA1", "name": "Atlantic and Mediterranean high energy littoral rock", "level": 2, "parent": "MA"},
    {"code": "MA12", "name": "Littoral coarse sediment", "level": 3, "parent": "MA1"},
    {"code": "MA13", "name": "Littoral sand", "level": 3, "parent": "MA1"},
    {"code": "MA14", "name": "Littoral muddy sand", "level": 3, "parent": "MA1"},
    {"code": "MA15", "name": "Littoral mud", "level": 3, "parent": "MA1"},
    # Infralittoral rock and biogenic reef
    {"code": "MB1", "name": "Atlantic and Mediterranean infralittoral rock", "level": 2, "parent": "MB"},
    {"code": "MB12", "name": "Infralittoral coarse sediment", "level": 3, "parent": "MB1"},
    {"code": "MB13", "name": "Infralittoral sand", "level": 3, "parent": "MB1"},
    {"code": "MB14", "name": "Infralittoral muddy sand", "level": 3, "parent": "MB1"},
    {"code": "MB15", "name": "Infralittoral mud", "level": 3, "parent": "MB1"},
    {"code": "MB25", "name": "Mediterranean infralittoral biogenic habitat", "level": 3, "parent": "MB2"},
    {"code": "MB252", "name": "Posidonia oceanica meadows", "level": 3, "parent": "MB25"},
    # Circalittoral rock and biogenic reef
    {"code": "MC1", "name": "Atlantic and Mediterranean circalittoral rock", "level": 2, "parent": "MC"},
    {"code": "MC12", "name": "Circalittoral coarse sediment", "level": 3, "parent": "MC1"},
    {"code": "MC13", "name": "Circalittoral sand", "level": 3, "parent": "MC1"},
    {"code": "MC14", "name": "Circalittoral muddy sand", "level": 3, "parent": "MC1"},
    {"code": "MC15", "name": "Circalittoral mud", "level": 3, "parent": "MC1"},
    {"code": "MC35", "name": "Mediterranean circalittoral biogenic habitat", "level": 3, "parent": "MC3"},
    {"code": "MC352", "name": "Mediterranean coastal detritic bottoms", "level": 3, "parent": "MC35"},
    {"code": "MC3521", "name": "Association with rhodolithes", "level": 3, "parent": "MC352"},
    {"code": "MC3517", "name": "Association with Laminaria rodriguezii", "level": 3, "parent": "MC352"},
    # Offshore circalittoral
    {"code": "MD1", "name": "Atlantic and Mediterranean offshore circalittoral rock", "level": 2, "parent": "MD"},
    {"code": "MD12", "name": "Offshore circalittoral coarse sediment", "level": 3, "parent": "MD1"},
    {"code": "MD13", "name": "Offshore circalittoral sand", "level": 3, "parent": "MD1"},
    {"code": "MD14", "name": "Offshore circalittoral muddy sand", "level": 3, "parent": "MD1"},
    {"code": "MD15", "name": "Offshore circalittoral mud", "level": 3, "parent": "MD1"},
    # Baltic specific
    {"code": "MA6", "name": "Baltic littoral rock and biogenic reef", "level": 2, "parent": "MA"},
    {"code": "MB6", "name": "Baltic infralittoral rock and biogenic reef", "level": 2, "parent": "MB"},
    {"code": "MC6", "name": "Baltic circalittoral rock and biogenic reef", "level": 2, "parent": "MC"},
    {"code": "MA62", "name": "Baltic littoral sand", "level": 3, "parent": "MA6"},
    {"code": "MA63", "name": "Baltic littoral mud", "level": 3, "parent": "MA6"},
    {"code": "MB62", "name": "Baltic infralittoral sand", "level": 3, "parent": "MB6"},
    {"code": "MB63", "name": "Baltic infralittoral mud", "level": 3, "parent": "MB6"},
    {"code": "MC62", "name": "Baltic circalittoral sand", "level": 3, "parent": "MC6"},
    {"code": "MC63", "name": "Baltic circalittoral mud", "level": 3, "parent": "MC6"},
    # Coastal habitats
    {"code": "N1", "name": "Coastal dunes and sandy shores", "level": 2, "parent": "N"},
    {"code": "N2", "name": "Coastal shingle", "level": 2, "parent": "N"},
    {"code": "N3", "name": "Rock cliffs, ledges and shores", "level": 2, "parent": "N"},
    # Saltmarshes and reedbeds
    {"code": "MA22", "name": "Atlantic saltmarshes and salt meadows", "level": 3, "parent": "MA2"},
    {"code": "MA23", "name": "Mediterranean saltmarshes and salt meadows", "level": 3, "parent": "MA2"},
]

# Lookup dict for quick access: {code: name}
EUNIS_LOOKUP = {h["code"]: h["name"] for h in EUNIS_HABITATS}

# ---------------------------------------------------------------------------
# Habitat column auto-detection candidates (ordered, first match wins)
# ---------------------------------------------------------------------------
HABITAT_COLUMN_CANDIDATES = [
    "EUNIS", "eunis", "EUNIS_code", "eunis_code",
    "Habitat", "habitat", "habitat_type", "Habitat_type",
    "EUNIS_Level3", "eunis_level3",
]

# ---------------------------------------------------------------------------
# Default societal benefits (from MARBEFES 5 logic chain benefits)
# ---------------------------------------------------------------------------
DEFAULT_BENEFITS = [
    {"name": "Wild food (finfish)", "unit": "tonnes", "ecosystem_service": "Wild fish"},
    {"name": "Healthy climate", "unit": "tCO2eq", "ecosystem_service": "Carbon sequestration & storage"},
    {"name": "Recreation & nature watching", "unit": "visitor-days", "ecosystem_service": "Places and seascapes"},
    {"name": "Erosion/flood prevention", "unit": "Ha protected", "ecosystem_service": "Natural hazard protection"},
    {"name": "Clean water", "unit": "tonnes N removed", "ecosystem_service": "Waste remediation"},
]

# ---------------------------------------------------------------------------
# Slug function (used for input IDs — must be consistent everywhere)
# ---------------------------------------------------------------------------
def benefit_slug(name: str) -> str:
    """Convert benefit name to a safe input ID component."""
    return re.sub(r'\W+', '_', name.lower()).strip('_')

# ---------------------------------------------------------------------------
# Export styling
# ---------------------------------------------------------------------------
EXPORT_PA_TAB_COLOR = "009688"  # Teal

# ---------------------------------------------------------------------------
# Methodology reference (exported to Excel "Methodology" sheet)
# ---------------------------------------------------------------------------
PA_METHODOLOGY = {
    "Topic": [
        "Framework", "Standard", "Habitat Classification",
        "Extent Method", "Supply Method", "Data Completeness",
    ],
    "Description": [
        "MARBEFES 7-step Natural Capital Accounting process (Steps 1-6: Physical Accounts)",
        "System of Environmental-Economic Accounting - Ecosystem Accounting (SEEA EA, UN 2021)",
        "EUNIS Level 3 habitat classification system",
        "Polygon area aggregation from spatial grid, reprojected to metric CRS",
        "User-entered physical quantities per societal benefit per habitat type",
        "Computed at export: see Summary sheet for completeness percentage",
    ],
}

# ---------------------------------------------------------------------------
# Map styling for habitat categorical choropleth
# ---------------------------------------------------------------------------
HABITAT_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#aec7e8", "#ffbb78",
]

# ---------------------------------------------------------------------------
# TODO stubs — future scope constants
# ---------------------------------------------------------------------------
# TODO: Use Table sector categories
# DEFAULT_SECTORS = ["Households and government", "Fish sector", "Tourism sector",
#                    "Cosmetic sector", "Other sector"]

# TODO: Condition typology classes (SEEA EA)
# CONDITION_TYPOLOGY_CLASSES = ["Compositional state", "Structural state",
#                               "Functional state", "Landscape/seascape"]
```

- [ ] **Step 2: Verify module imports**

Run: `python -c "import pa_config; print(len(pa_config.EUNIS_HABITATS), 'habitats'); print(len(pa_config.DEFAULT_BENEFITS), 'benefits'); print(pa_config.benefit_slug('Wild food (finfish)'))"`

Expected: `40 habitats`, `5 benefits`, `wild_food_finfish`

- [ ] **Step 3: Commit**

```bash
git add pa_config.py
git commit -m "feat(pa): add pa_config.py with EUNIS reference, benefits, and constants"
```

---

### Task 2: Create `pa_calculations.py` — extent and supply computations

**Files:**
- Create: `pa_calculations.py`
- Create: `tests/test_pa_calculations.py`

- [ ] **Step 1: Write failing tests for `compute_extent`**

```python
"""Tests for pa_calculations module."""

import pytest
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import box

import pa_calculations as pac


def _make_test_gdf():
    """Create a small GeoDataFrame with 3 known-area polygons in UTM33N."""
    # 3 boxes: each 1000m x 1000m = 1,000,000 m² = 100 Ha = 1 km²
    polys = [
        box(500000, 6100000, 501000, 6101000),  # Subzone A
        box(501000, 6100000, 502000, 6101000),  # Subzone B
        box(502000, 6100000, 503000, 6101000),  # Subzone C
    ]
    gdf = gpd.GeoDataFrame(
        {"Subzone ID": ["A", "B", "C"]},
        geometry=polys,
        crs="EPSG:32633",  # UTM zone 33N (metric)
    )
    # Convert to WGS84 as the app stores it
    return gdf.to_crs(epsg=4326)


class TestComputeExtent:
    def test_basic_two_habitats(self):
        gdf = _make_test_gdf()
        assignments = {"A": "MB252", "B": "MB252", "C": "MC352"}
        result = pac.compute_extent(gdf, assignments, unit="Ha", original_crs="EPSG:32633")
        # MB252: 2 polygons x 100 Ha = 200 Ha
        # MC352: 1 polygon x 100 Ha = 100 Ha
        mb = result[result["eunis_code"] == "MB252"]
        mc = result[result["eunis_code"] == "MC352"]
        assert len(result) == 2
        assert abs(mb["area"].values[0] - 200.0) < 5  # allow small reprojection error
        assert abs(mc["area"].values[0] - 100.0) < 5
        assert abs(result["pct_total"].sum() - 100.0) < 0.1

    def test_unassigned_excluded(self):
        gdf = _make_test_gdf()
        assignments = {"A": "MB252"}  # B and C unassigned
        result = pac.compute_extent(gdf, assignments, unit="Ha", original_crs="EPSG:32633")
        assert len(result) == 1
        assert result["eunis_code"].values[0] == "MB252"

    def test_km2_unit(self):
        gdf = _make_test_gdf()
        assignments = {"A": "MB252", "B": "MB252", "C": "MC352"}
        result = pac.compute_extent(gdf, assignments, unit="km2", original_crs="EPSG:32633")
        mb = result[result["eunis_code"] == "MB252"]
        assert abs(mb["area"].values[0] - 2.0) < 0.05  # 2 km²

    def test_empty_assignments(self):
        gdf = _make_test_gdf()
        result = pac.compute_extent(gdf, {}, unit="Ha", original_crs="EPSG:32633")
        assert len(result) == 0


class TestAssembleSupplyTable:
    def test_basic(self):
        supply_data = {
            "Wild food (finfish)": {"MB252": 100.5, "MC352": 50.0},
            "Healthy climate": {"MB252": 200.0},
        }
        habitat_codes = ["MB252", "MC352"]
        result = pac.assemble_supply_table(supply_data, habitat_codes)
        assert list(result.columns) == ["Benefit", "Unit", "MB252", "MC352"]
        assert len(result) == 2
        # Check NaN for missing cell
        row_climate = result[result["Benefit"] == "Healthy climate"]
        assert pd.isna(row_climate["MC352"].values[0])

    def test_empty(self):
        result = pac.assemble_supply_table({}, [])
        assert len(result) == 0


class TestValidateCompleteness:
    def test_partial(self):
        supply_data = {
            "Benefit A": {"H1": 10.0},
        }
        habitat_codes = ["H1", "H2"]
        benefit_names = ["Benefit A", "Benefit B"]
        result = pac.validate_completeness(supply_data, habitat_codes, benefit_names)
        assert result["filled"] == 1
        assert result["total"] == 4
        assert result["pct"] == 25.0

    def test_full(self):
        supply_data = {
            "B1": {"H1": 1.0, "H2": 2.0},
        }
        result = pac.validate_completeness(supply_data, ["H1", "H2"], ["B1"])
        assert result["pct"] == 100.0


class TestDetectHabitatColumn:
    def test_finds_eunis(self):
        columns = ["Subzone ID", "EUNIS", "geometry", "area"]
        assert pac.detect_habitat_column(columns) == "EUNIS"

    def test_finds_habitat(self):
        columns = ["Subzone ID", "habitat_type", "geometry"]
        assert pac.detect_habitat_column(columns) == "habitat_type"

    def test_none_found(self):
        columns = ["Subzone ID", "geometry", "population"]
        assert pac.detect_habitat_column(columns) is None

    def test_priority_order(self):
        columns = ["Subzone ID", "habitat", "EUNIS", "geometry"]
        assert pac.detect_habitat_column(columns) == "EUNIS"  # EUNIS comes first in candidate list


class TestBenefitNameValidation:
    def test_unique_names(self):
        names = ["Food", "Climate", "Recreation"]
        assert pac.validate_benefit_names(names) is True

    def test_duplicate_names(self):
        names = ["Food", "Climate", "Food"]
        assert pac.validate_benefit_names(names) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pa_calculations.py -v`

Expected: All tests FAIL (module not found)

- [ ] **Step 3: Implement `pa_calculations.py`**

```python
"""
MARBEFES Physical Accounts Calculations — pure functions.

All functions are stateless and have no Shiny dependencies.
"""

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj

from pa_config import (
    AREA_CONVERSIONS, EUNIS_LOOKUP, HABITAT_COLUMN_CANDIDATES,
    DEFAULT_BENEFITS, benefit_slug,
)

logger = logging.getLogger(__name__)


def compute_extent(
    gdf: gpd.GeoDataFrame,
    habitat_assignments: dict,
    unit: str = "Ha",
    original_crs: str | None = None,
) -> pd.DataFrame:
    """
    Compute ecosystem extent by habitat type from spatial grid.

    Parameters
    ----------
    gdf : GeoDataFrame
        Spatial grid in WGS84 with 'Subzone ID' and 'geometry' columns.
    habitat_assignments : dict
        Mapping of {subzone_id: eunis_code}.
    unit : str
        'Ha' or 'km2'.
    original_crs : str or None
        Original CRS string for metric reprojection.

    Returns
    -------
    pd.DataFrame
        Columns: eunis_code, habitat_name, area, pct_total
    """
    if not habitat_assignments:
        return pd.DataFrame(columns=["eunis_code", "habitat_name", "area", "pct_total"])

    # Filter to assigned subzones only
    assigned_ids = set(habitat_assignments.keys())
    gdf_assigned = gdf[gdf["Subzone ID"].isin(assigned_ids)].copy()

    if gdf_assigned.empty:
        return pd.DataFrame(columns=["eunis_code", "habitat_name", "area", "pct_total"])

    # Reproject to metric CRS for accurate area calculation
    metric_gdf = _reproject_to_metric(gdf_assigned, original_crs)

    # Compute areas in m²
    metric_gdf["area_m2"] = metric_gdf.geometry.area

    # Map subzone to habitat
    metric_gdf["eunis_code"] = metric_gdf["Subzone ID"].map(habitat_assignments)

    # Aggregate by habitat type
    conversion = AREA_CONVERSIONS.get(unit, AREA_CONVERSIONS["Ha"])
    grouped = metric_gdf.groupby("eunis_code")["area_m2"].sum().reset_index()
    grouped["area"] = grouped["area_m2"] / conversion
    total_area = grouped["area"].sum()
    grouped["pct_total"] = (grouped["area"] / total_area * 100) if total_area > 0 else 0
    grouped["habitat_name"] = grouped["eunis_code"].map(
        lambda c: EUNIS_LOOKUP.get(c, c)
    )

    return grouped[["eunis_code", "habitat_name", "area", "pct_total"]].reset_index(drop=True)


def _reproject_to_metric(gdf: gpd.GeoDataFrame, original_crs: str | None) -> gpd.GeoDataFrame:
    """Reproject GeoDataFrame to a metric CRS for area calculations."""
    # Try using original CRS if it was projected and metric
    if original_crs:
        try:
            crs_obj = pyproj.CRS.from_user_input(original_crs)
            if crs_obj.is_projected:
                return gdf.to_crs(crs_obj)
        except Exception:
            pass  # Fall through to auto-detection

    # Auto-detect UTM zone from centroid
    try:
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        utm_zone = int((center_lon + 180) / 6) + 1
        hemisphere = "north" if center_lat >= 0 else "south"
        epsg = 32600 + utm_zone if hemisphere == "north" else 32700 + utm_zone
        return gdf.to_crs(epsg=epsg)
    except Exception as e:
        logger.warning("UTM auto-detection failed (%s), falling back to EPSG:3857", e)

    # Fallback: Web Mercator (area distortion at high latitudes)
    logger.warning("Using EPSG:3857 — area values may be distorted at high latitudes")
    return gdf.to_crs(epsg=3857)


def detect_habitat_column(columns: list[str]) -> str | None:
    """Check column list for a habitat type column using the candidate list."""
    for candidate in HABITAT_COLUMN_CANDIDATES:
        if candidate in columns:
            return candidate
    return None


def assemble_supply_table(
    supply_data: dict[str, dict[str, float]],
    habitat_codes: list[str],
) -> pd.DataFrame:
    """
    Assemble supply data into a SEEA EA Table 2A.2-style DataFrame.

    Parameters
    ----------
    supply_data : dict
        {benefit_name: {eunis_code: quantity}}
    habitat_codes : list
        Ordered list of EUNIS codes for columns.

    Returns
    -------
    pd.DataFrame
        Columns: Benefit, Unit, <eunis_code_1>, <eunis_code_2>, ...
    """
    if not supply_data or not habitat_codes:
        return pd.DataFrame(columns=["Benefit", "Unit"] + list(habitat_codes))

    rows = []
    for benefit in DEFAULT_BENEFITS:
        name = benefit["name"]
        if name in supply_data:
            row = {"Benefit": name, "Unit": benefit["unit"]}
            for code in habitat_codes:
                row[code] = supply_data[name].get(code, np.nan)
            rows.append(row)

    # Custom benefits (not in DEFAULT_BENEFITS)
    default_names = {b["name"] for b in DEFAULT_BENEFITS}
    for name, quantities in supply_data.items():
        if name not in default_names:
            row = {"Benefit": name, "Unit": "units"}
            for code in habitat_codes:
                row[code] = quantities.get(code, np.nan)
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["Benefit", "Unit"] + list(habitat_codes))

    return pd.DataFrame(rows)


def validate_completeness(
    supply_data: dict[str, dict[str, float]],
    habitat_codes: list[str],
    benefit_names: list[str],
) -> dict:
    """
    Calculate data completeness for the supply table.

    Returns dict with keys: filled, total, pct, empty_benefits, empty_habitats
    """
    total = len(habitat_codes) * len(benefit_names)
    if total == 0:
        return {"filled": 0, "total": 0, "pct": 0.0,
                "empty_benefits": [], "empty_habitats": []}

    filled = 0
    empty_benefits = []
    habitat_fill_count = {code: 0 for code in habitat_codes}

    for name in benefit_names:
        benefit_filled = 0
        for code in habitat_codes:
            val = supply_data.get(name, {}).get(code)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                filled += 1
                benefit_filled += 1
                habitat_fill_count[code] += 1
        if benefit_filled == 0:
            empty_benefits.append(name)

    empty_habitats = [code for code, count in habitat_fill_count.items() if count == 0]

    return {
        "filled": filled,
        "total": total,
        "pct": round(filled / total * 100, 1),
        "empty_benefits": empty_benefits,
        "empty_habitats": empty_habitats,
    }


def validate_benefit_names(names: list[str]) -> bool:
    """Check that all benefit names are unique."""
    return len(names) == len(set(names))


# ---------------------------------------------------------------------------
# TODO stubs — future scope
# ---------------------------------------------------------------------------

def compute_use_table(supply_data, sector_allocations):
    """TODO: Disaggregate supply by beneficiary sector."""
    raise NotImplementedError("Use Table: planned for future version")


def compute_condition_account(condition_data):
    """TODO: Compute condition indices per ecosystem type."""
    raise NotImplementedError("Condition Account: planned for future version")


def compute_extent_changes(opening_extent, closing_extent):
    """TODO: Compute managed/unmanaged extent changes between periods."""
    raise NotImplementedError("Multi-year extent changes: planned for future version")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pa_calculations.py -v`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add pa_calculations.py tests/test_pa_calculations.py
git commit -m "feat(pa): add pa_calculations.py with extent, supply, and validation functions"
```

---

### Task 3: Refactor `eva_export.py` — expose `build_workbook()`

**Files:**
- Modify: `eva_export.py:477-534`

- [ ] **Step 1: Refactor `generate_workbook` into `build_workbook` + wrapper**

In `eva_export.py`, replace the `generate_workbook` function (lines 477-534) with:

```python
def build_workbook(results, uploaded_data, user_classifications,
                   data_type, metadata, ec_store, pa_summary_data=None):
    """
    Build a complete Excel workbook with all analysis results.

    Returns an openpyxl Workbook object (not serialized).
    """
    import openpyxl

    # Handle null case
    if results is None or uploaded_data is None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Info"
        ws.cell(row=1, column=1, value="Message")
        ws.cell(row=2, column=1, value="No data available")
        return wb

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _build_summary_sheet(writer, results, uploaded_data, data_type,
                             metadata, ec_store)
        _build_data_sheets(writer, results, uploaded_data, user_classifications)
        _build_multi_ec_sheets(writer, results, ec_store)
        _build_chart_sheets(writer.book, results, ec_store)
        _apply_styling(writer.book)
        workbook = writer.book

    # Re-load from buffer to get a clean Workbook object
    buffer.seek(0)
    workbook = openpyxl.load_workbook(buffer)
    return workbook


def generate_workbook(results, uploaded_data, user_classifications,
                      data_type, metadata, ec_store):
    """
    Generate a complete Excel workbook with all analysis results.

    Backward-compatible entry point — returns io.BytesIO buffer.
    """
    wb = build_workbook(results, uploaded_data, user_classifications,
                        data_type, metadata, ec_store)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
```

- [ ] **Step 2: Add `import openpyxl` at top of eva_export.py if not present**

Check imports — `openpyxl` is already used via `from openpyxl.styles import ...` etc., but `import openpyxl` directly is needed for `openpyxl.load_workbook`. Add at the top if missing.

- [ ] **Step 3: Verify existing EVA export still works**

Run: `python -c "import eva_export; print('eva_export imports OK')"` and `python -c "import eva_config; import eva_export; print(type(eva_export.build_workbook)); print(type(eva_export.generate_workbook))"`

Expected: Both functions exist and are callable.

- [ ] **Step 4: Commit**

```bash
git add eva_export.py
git commit -m "refactor(export): expose build_workbook() for combined PA export support"
```

---

### Task 4: Create `pa_export.py` — Physical Accounts Excel export

**Files:**
- Create: `pa_export.py`

- [ ] **Step 1: Create `pa_export.py`**

```python
"""
MARBEFES Physical Accounts Excel Export.

Generates standalone or combined (EVA + PA) Excel workbooks.
All functions are stateless and have no Shiny dependencies.
"""

import io
import logging

import numpy as np
import pandas as pd
from openpyxl.utils import get_column_letter

import eva_export
from eva_export import style_worksheet
from pa_config import (
    PA_MODULE_VERSION, PA_METHODOLOGY, EXPORT_PA_TAB_COLOR,
    EUNIS_LOOKUP,
)

logger = logging.getLogger(__name__)


def _build_pa_summary_sheet(ws, metadata, extent_df, completeness):
    """Write PA Summary & Metadata to worksheet."""
    rows = [
        ("Parameter", "Value"),
        ("Module", "Physical Accounts"),
        ("Module Version", PA_MODULE_VERSION),
        ("Export Date", pd.Timestamp.now().strftime("%Y-%m-%d")),
        ("Export Time", pd.Timestamp.now().strftime("%H:%M:%S")),
        ("", ""),
        ("Ecosystem Accounting Area (EAA)", metadata.get("eaa_name", "Not specified")),
        ("Boundary Description", metadata.get("boundary_description", "Not specified")),
        ("Accounting Year", str(metadata.get("accounting_year", "Not specified"))),
        ("", ""),
        ("Data Completeness", f"{completeness.get('pct', 0):.1f}% ({completeness.get('filled', 0)} of {completeness.get('total', 0)} cells)"),
        ("Number of Habitat Types", str(len(extent_df)) if extent_df is not None else "0"),
        ("Total Extent", f"{extent_df['area'].sum():.2f}" if extent_df is not None and len(extent_df) > 0 else "0"),
        ("", ""),
        ("Reference", "Franco A. and Amorim E. (2025) Ecological Value Assessment (EVA)"),
        ("Framework", "SEEA EA (United Nations, 2021)"),
        ("Funding", "European Union Horizon Europe Research Programme - MARBEFES Project"),
    ]

    for row_idx, (param, value) in enumerate(rows, start=1):
        ws.cell(row=row_idx, column=1, value=param)
        ws.cell(row=row_idx, column=2, value=value)


def _build_extent_sheet(ws, extent_df, unit):
    """Write Ecosystem Extent Account to worksheet."""
    headers = ["EUNIS Code", "Habitat Name", f"Area ({unit})", "% of Total"]
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col_idx, value=header)

    if extent_df is not None and len(extent_df) > 0:
        for row_idx, row in enumerate(extent_df.itertuples(), start=2):
            ws.cell(row=row_idx, column=1, value=row.eunis_code)
            ws.cell(row=row_idx, column=2, value=row.habitat_name)
            ws.cell(row=row_idx, column=3, value=round(row.area, 2))
            ws.cell(row=row_idx, column=4, value=round(row.pct_total, 1))

        # Totals row
        total_row = len(extent_df) + 2
        ws.cell(row=total_row, column=1, value="TOTAL")
        ws.cell(row=total_row, column=3, value=round(extent_df["area"].sum(), 2))
        ws.cell(row=total_row, column=4, value=100.0)


def _build_supply_sheet(ws, supply_df):
    """Write Supply Table to worksheet."""
    if supply_df is None or supply_df.empty:
        ws.cell(row=1, column=1, value="No supply data available")
        return

    # Write headers
    for col_idx, col_name in enumerate(supply_df.columns, start=1):
        ws.cell(row=1, column=col_idx, value=col_name)

    # Write data
    for row_idx, row in enumerate(supply_df.itertuples(index=False), start=2):
        for col_idx, value in enumerate(row, start=1):
            if pd.notna(value):
                ws.cell(row=row_idx, column=col_idx, value=value)


def _build_assignments_sheet(ws, assignments):
    """Write habitat assignments to worksheet."""
    headers = ["Subzone ID", "EUNIS Code", "Habitat Name"]
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col_idx, value=header)

    for row_idx, (subzone, code) in enumerate(sorted(assignments.items()), start=2):
        ws.cell(row=row_idx, column=1, value=subzone)
        ws.cell(row=row_idx, column=2, value=code)
        ws.cell(row=row_idx, column=3, value=EUNIS_LOOKUP.get(code, code))


def _build_methodology_sheet(ws):
    """Write SEEA EA methodology reference to worksheet."""
    methodology_df = pd.DataFrame(PA_METHODOLOGY)
    headers = list(methodology_df.columns)
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col_idx, value=header)
    for row_idx, row in enumerate(methodology_df.itertuples(index=False), start=2):
        for col_idx, value in enumerate(row, start=1):
            ws.cell(row=row_idx, column=col_idx, value=value)


def generate_pa_workbook(extent_df, supply_df, assignments, metadata,
                         completeness, unit="Ha"):
    """
    Generate a standalone Physical Accounts Excel workbook.

    Returns io.BytesIO buffer.
    """
    import openpyxl

    wb = openpyxl.Workbook()

    # Sheet 1: Summary
    ws_summary = wb.active
    ws_summary.title = "Summary & Metadata"
    ws_summary.sheet_properties.tabColor = EXPORT_PA_TAB_COLOR
    _build_pa_summary_sheet(ws_summary, metadata, extent_df, completeness)
    style_worksheet(ws_summary)

    # Sheet 2: Extent
    ws_extent = wb.create_sheet("Ecosystem Extent Account")
    ws_extent.sheet_properties.tabColor = EXPORT_PA_TAB_COLOR
    _build_extent_sheet(ws_extent, extent_df, unit)
    style_worksheet(ws_extent)

    # Sheet 3: Supply
    ws_supply = wb.create_sheet("Supply Table")
    ws_supply.sheet_properties.tabColor = EXPORT_PA_TAB_COLOR
    _build_supply_sheet(ws_supply, supply_df)
    style_worksheet(ws_supply)

    # Sheet 4: Assignments
    ws_assign = wb.create_sheet("Habitat Assignments")
    ws_assign.sheet_properties.tabColor = EXPORT_PA_TAB_COLOR
    _build_assignments_sheet(ws_assign, assignments)
    style_worksheet(ws_assign)

    # Sheet 5: Methodology
    ws_method = wb.create_sheet("Methodology")
    ws_method.sheet_properties.tabColor = EXPORT_PA_TAB_COLOR
    _build_methodology_sheet(ws_method)
    style_worksheet(ws_method)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_combined_workbook(eva_args, pa_extent_df, pa_supply_df,
                               pa_assignments, pa_metadata, pa_completeness,
                               pa_unit="Ha"):
    """
    Generate a combined EVA + Physical Accounts workbook.

    Parameters
    ----------
    eva_args : dict
        Arguments to pass to eva_export.build_workbook().
    pa_* : various
        Physical Accounts data.

    Returns io.BytesIO buffer.
    """
    import openpyxl

    # Build EVA workbook
    wb = eva_export.build_workbook(**eva_args)

    # Append PA sheets
    ws_extent = wb.create_sheet("PA - Extent Account")
    ws_extent.sheet_properties.tabColor = EXPORT_PA_TAB_COLOR
    _build_extent_sheet(ws_extent, pa_extent_df, pa_unit)
    style_worksheet(ws_extent)

    ws_supply = wb.create_sheet("PA - Supply Table")
    ws_supply.sheet_properties.tabColor = EXPORT_PA_TAB_COLOR
    _build_supply_sheet(ws_supply, pa_supply_df)
    style_worksheet(ws_supply)

    ws_assign = wb.create_sheet("PA - Habitat Assignments")
    ws_assign.sheet_properties.tabColor = EXPORT_PA_TAB_COLOR
    _build_assignments_sheet(ws_assign, pa_assignments)
    style_worksheet(ws_assign)

    ws_method = wb.create_sheet("PA - Methodology")
    ws_method.sheet_properties.tabColor = EXPORT_PA_TAB_COLOR
    _build_methodology_sheet(ws_method)
    style_worksheet(ws_method)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
```

- [ ] **Step 2: Verify module imports**

Run: `python -c "import pa_export; print('pa_export imports OK')"`

Expected: OK (may need plotly/kaleido installed)

- [ ] **Step 3: Commit**

```bash
git add pa_export.py
git commit -m "feat(pa): add pa_export.py with standalone and combined Excel export"
```

---

## Chunk 2: App Integration — GIS, UI Tab, and Map

### Task 5: Modify `app.py` — add `geo_data_full` reactive and update GIS handler

**Files:**
- Modify: `app.py:948-955` (reactive values)
- Modify: `app.py:1347-1352` (handle_geojson_upload)

- [ ] **Step 1: Add `geo_data_full` reactive value**

After `geo_match_info = reactive.Value(None)` (~line 952), add:

```python
    geo_data_full = reactive.Value(None)  # Full GeoDataFrame with all attributes (for PA module)
```

- [ ] **Step 2: Update `handle_geojson_upload` to store full GDF**

Find the line `gdf = gdf[['Subzone ID', 'geometry']]` (~line 1351 after previous edits) and insert before it:

```python
        # Store full GeoDataFrame for Physical Accounts habitat auto-detection
        geo_data_full.set(gdf.copy())
```

- [ ] **Step 3: Verify app.py syntax**

Run: `python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(pa): add geo_data_full reactive for PA habitat auto-detection"
```

---

### Task 6: Add Physical Accounts tab UI to `app.py`

**Files:**
- Modify: `app.py` — add new `ui.nav_panel` before the Method tab
- Modify: `app.py` — add PA imports at top

This is a large UI addition. Add the following new nav_panel in the `app_ui` definition, just before the `"📖 Method"` nav_panel (~line 888):

- [ ] **Step 1: Add PA imports at top of `app.py`**

After `import eva_export`, add:

```python
import pa_config
import pa_calculations
import pa_export
```

- [ ] **Step 2: Add the Physical Accounts nav_panel UI**

Insert before the Method tab panel (`ui.nav_panel("📖 Method", ...)`):

```python
    ui.nav_panel(
        "📋 Physical Accounts",
        ui.layout_sidebar(
            ui.sidebar(
                ui.div(
                    ui.h5("🏛️ Study Area", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_text("pa_eaa_name", "EAA Name:", placeholder="e.g. Lithuanian Coast MPA"),
                    ui.input_text("pa_boundary_desc", "Boundary Description:", placeholder="Describe the study area boundary"),
                    ui.input_numeric("pa_accounting_year", "Accounting Year:", value=2024, min=1990, max=2100),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("🌿 EUNIS Habitats", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_selectize(
                        "pa_habitat_select",
                        "Select Habitat Types:",
                        choices={h["code"]: f"{h['code']} - {h['name']}" for h in pa_config.EUNIS_HABITATS},
                        multiple=True,
                        options={"placeholder": "Search and select habitats..."}
                    ),
                    ui.input_text("pa_custom_habitat_code", "Custom Code:", placeholder="e.g. MB999"),
                    ui.input_text("pa_custom_habitat_name", "Custom Name:", placeholder="e.g. Local reef habitat"),
                    ui.input_action_button("pa_add_custom_habitat", "Add Custom Habitat", class_="btn-outline-secondary btn-sm", style="margin-top: 0.5rem;"),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("📊 Benefits", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_checkbox_group(
                        "pa_benefits_select",
                        "Active Benefits:",
                        choices={b["name"]: f"{b['name']} ({b['unit']})" for b in pa_config.DEFAULT_BENEFITS},
                        selected=[b["name"] for b in pa_config.DEFAULT_BENEFITS],
                    ),
                    ui.input_text("pa_custom_benefit_name", "Custom Benefit Name:", placeholder="e.g. Aquaculture"),
                    ui.input_text("pa_custom_benefit_unit", "Unit:", placeholder="e.g. tonnes"),
                    ui.input_action_button("pa_add_custom_benefit", "Add Custom Benefit", class_="btn-outline-secondary btn-sm", style="margin-top: 0.5rem;"),
                ),
                ui.hr(),
                ui.div(
                    ui.h5("⚙️ Settings", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
                    ui.input_select("pa_area_unit", "Area Unit:", choices={"Ha": "Hectares (Ha)", "km2": "Square kilometres (km²)"}, selected="Ha"),
                    ui.download_button("pa_download_standalone", "📊 Download PA Report (Excel)", class_="btn-primary", style="width: 100%; margin-top: 1rem;"),
                    ui.download_button("pa_download_combined", "📊 Download Combined EVA+PA (Excel)", class_="btn-secondary", style="width: 100%; margin-top: 0.5rem;"),
                ),
                width=380
            ),
            ui.div(
                # Card 1: Habitat Assignment
                ui.card(
                    ui.card_header("🗺️ Habitat Assignment"),
                    ui.div(
                        ui.output_ui("pa_habitat_assignment_ui"),
                        style="padding: 1rem;"
                    )
                ),
                # Card 2: Extent Account
                ui.card(
                    ui.card_header("📐 Ecosystem Extent Account"),
                    ui.div(
                        ui.output_ui("pa_extent_ui"),
                        style="padding: 1rem;"
                    )
                ),
                # Card 3: Supply Table
                ui.card(
                    ui.card_header("📊 Supply Table"),
                    ui.div(
                        ui.output_ui("pa_supply_ui"),
                        style="padding: 1rem;"
                    )
                ),
            )
        )
    ),
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(pa): add Physical Accounts tab UI with sidebar and 3 content cards"
```

---

### Task 7: Add Physical Accounts server logic to `app.py`

**Files:**
- Modify: `app.py` — add server-side reactive values, outputs, and handlers inside `server()` function

- [ ] **Step 1: Add PA reactive values inside `server()` function**

After the existing multi-EC reactive values (~line 956), add:

```python
    # Physical Accounts reactive values
    pa_habitat_assignments = reactive.Value({})
    pa_custom_habitats = reactive.Value([])  # list of {code, name} dicts
    pa_custom_benefits = reactive.Value([])  # list of {name, unit} dicts
```

- [ ] **Step 2: Add habitat assignment UI output**

Add after the existing EC management server code (before visualizations section):

```python
    # === PHYSICAL ACCOUNTS SERVER LOGIC ===

    @output
    @render.ui
    def pa_habitat_assignment_ui():
        gdf = geo_data.get()
        gdf_full = geo_data_full.get()
        if gdf is None:
            return ui.div(
                ui.p("⬆️ Upload a spatial grid file in the Data Input tab to begin habitat assignment.",
                     style="text-align: center; color: #6c757d; padding: 2rem; font-size: 1.1rem;")
            )

        subzone_ids = gdf["Subzone ID"].tolist()
        selected_habitats = list(input.pa_habitat_select() or [])
        custom_habs = pa_custom_habitats.get()
        all_habitat_choices = {h["code"]: f"{h['code']} - {h['name']}" for h in pa_config.EUNIS_HABITATS if h["code"] in selected_habitats}
        for ch in custom_habs:
            all_habitat_choices[ch["code"]] = f"{ch['code']} - {ch['name']}"

        # Auto-detect
        auto_col = None
        auto_assignments = {}
        if gdf_full is not None:
            auto_col = pa_calculations.detect_habitat_column(list(gdf_full.columns))
            if auto_col:
                for _, row in gdf_full.iterrows():
                    sid = str(row.get("Subzone ID", ""))
                    val = str(row.get(auto_col, ""))
                    if sid and val:
                        auto_assignments[sid] = val

        items = []
        if auto_col:
            items.append(ui.p(f"✅ Auto-detected habitat column: '{auto_col}'",
                             style="color: #28a745; font-weight: 600; margin-bottom: 1rem;"))
        else:
            items.append(ui.p("ℹ️ No habitat column detected — assign habitats manually below.",
                             style="color: #ff9800; margin-bottom: 1rem;"))

        # Per-subzone dropdowns
        if not all_habitat_choices:
            items.append(ui.p("👈 Select habitat types in the sidebar first.", style="color: #6c757d;"))
        else:
            assignment_rows = []
            for sid in subzone_ids:
                default = auto_assignments.get(sid, "")
                assignment_rows.append(
                    ui.div(
                        ui.div(ui.strong(sid), style="width: 120px; display: inline-block;"),
                        ui.input_select(
                            f"pa_assign_{sid}", "",
                            choices={"": "(unassigned)", **all_habitat_choices},
                            selected=default if default in all_habitat_choices else "",
                            width="300px"
                        ),
                        style="display: flex; align-items: center; gap: 1rem; margin-bottom: 0.3rem;"
                    )
                )
            items.append(ui.div(*assignment_rows))

        # Summary
        assigned_count = sum(1 for sid in subzone_ids
                           if input.get(f"pa_assign_{sid}", lambda: "")() != "")
        items.append(ui.p(
            f"📋 {assigned_count} of {len(subzone_ids)} subzones assigned",
            style=f"font-weight: 600; color: {'#28a745' if assigned_count == len(subzone_ids) else '#ff9800'}; margin-top: 1rem;"
        ))

        return ui.div(*items)

    @reactive.Effect
    def _update_pa_assignments():
        """Collect habitat assignments from per-subzone dropdowns."""
        gdf = geo_data.get()
        if gdf is None:
            pa_habitat_assignments.set({})
            return
        assignments = {}
        for sid in gdf["Subzone ID"].tolist():
            try:
                val = input[f"pa_assign_{sid}"]()
                if val:
                    assignments[sid] = val
            except Exception:
                pass
        pa_habitat_assignments.set(assignments)
```

- [ ] **Step 3: Add extent UI output**

```python
    @output
    @render.ui
    def pa_extent_ui():
        gdf = geo_data.get()
        assignments = pa_habitat_assignments.get()
        if gdf is None:
            return ui.p("Upload a spatial grid to compute extent.", style="color: #6c757d; text-align: center; padding: 2rem;")
        if not assignments:
            return ui.p("Assign habitats to subzones above to compute extent.", style="color: #6c757d; text-align: center; padding: 2rem;")

        unit = input.pa_area_unit()
        crs = original_crs.get()
        extent_df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs)

        if extent_df.empty:
            return ui.p("No extent data computed.", style="color: #6c757d;")

        return ui.TagList(
            ui.output_table("pa_extent_table"),
            ui.div(
                ui.p("ℹ️ Opening/closing stock tracking and change analysis will be available in a future version.",
                     style="color: #6c757d; font-size: 0.9rem; margin-top: 1rem;"),
                class_="info-box"
            )
        )

    @output
    @render.table
    def pa_extent_table():
        gdf = geo_data.get()
        assignments = pa_habitat_assignments.get()
        if gdf is None or not assignments:
            return pd.DataFrame()
        unit = input.pa_area_unit()
        crs = original_crs.get()
        df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs)
        df["area"] = df["area"].round(2)
        df["pct_total"] = df["pct_total"].round(1)
        df.columns = ["EUNIS Code", "Habitat Name", f"Area ({unit})", "% of Total"]
        return df
```

- [ ] **Step 4: Add supply table UI output**

```python
    @output
    @render.ui
    def pa_supply_ui():
        assignments = pa_habitat_assignments.get()
        selected_benefits = list(input.pa_benefits_select() or [])
        custom_bens = pa_custom_benefits.get()
        all_benefits = selected_benefits + [b["name"] for b in custom_bens]

        if not assignments:
            return ui.p("Assign habitats first to enter supply data.", style="color: #6c757d; text-align: center; padding: 2rem;")
        if not all_benefits:
            return ui.p("Select at least one benefit in the sidebar.", style="color: #6c757d; text-align: center; padding: 2rem;")

        habitat_codes = sorted(set(assignments.values()))

        # Check grid size
        grid_size = len(all_benefits) * len(habitat_codes)
        items = []
        if grid_size > 100:
            items.append(ui.p(f"⚠️ Large grid ({grid_size} cells). Consider reducing habitats or benefits for performance.",
                             style="color: #ff9800; font-weight: 600;"))

        # Build grid header
        header_cells = [ui.tags.th("Benefit"), ui.tags.th("Unit")]
        for code in habitat_codes:
            name = pa_config.EUNIS_LOOKUP.get(code, code)
            short = name[:20] + "..." if len(name) > 20 else name
            header_cells.append(ui.tags.th(f"{code}", title=name, style="cursor: help;"))

        # Build grid rows
        body_rows = []
        for ben_name in all_benefits:
            slug = pa_config.benefit_slug(ben_name)
            # Find unit
            ben_unit = "units"
            for b in pa_config.DEFAULT_BENEFITS:
                if b["name"] == ben_name:
                    ben_unit = b["unit"]
                    break
            for cb in custom_bens:
                if cb["name"] == ben_name:
                    ben_unit = cb["unit"]
                    break

            cells = [ui.tags.td(ui.strong(ben_name)), ui.tags.td(ben_unit)]
            for code in habitat_codes:
                input_id = f"supply_{slug}_{code}"
                cells.append(ui.tags.td(
                    ui.input_numeric(input_id, "", value=None, width="100px"),
                    style="padding: 2px;"
                ))
            body_rows.append(ui.tags.tr(*cells))

        items.append(ui.tags.table(
            ui.tags.thead(ui.tags.tr(*header_cells)),
            ui.tags.tbody(*body_rows),
            class_="table table-sm table-bordered",
            style="font-size: 0.9rem;"
        ))

        # Completeness
        supply_data = _collect_pa_supply_data(all_benefits, habitat_codes)
        completeness = pa_calculations.validate_completeness(supply_data, habitat_codes, all_benefits)
        items.append(ui.p(
            f"📊 Data completeness: {completeness['filled']} of {completeness['total']} cells filled ({completeness['pct']}%)",
            style=f"font-weight: 600; color: {'#28a745' if completeness['pct'] == 100 else '#ff9800'}; margin-top: 1rem;"
        ))

        items.append(ui.div(
            ui.p("ℹ️ Use Table (sector disaggregation) and Condition Account will be available in a future version.",
                 style="color: #6c757d; font-size: 0.9rem; margin-top: 1rem;"),
            class_="info-box"
        ))

        return ui.div(*items)

    def _collect_pa_supply_data(benefit_names, habitat_codes):
        """Read supply quantities from dynamic input widgets."""
        supply_data = {}
        for name in benefit_names:
            slug = pa_config.benefit_slug(name)
            quantities = {}
            for code in habitat_codes:
                try:
                    val = input[f"supply_{slug}_{code}"]()
                    if val is not None:
                        quantities[code] = float(val)
                except Exception:
                    pass
            if quantities:
                supply_data[name] = quantities
        return supply_data
```

- [ ] **Step 5: Add custom habitat/benefit handlers and export handlers**

```python
    @reactive.Effect
    @reactive.event(input.pa_add_custom_habitat)
    def _add_custom_habitat():
        code = input.pa_custom_habitat_code().strip()
        name = input.pa_custom_habitat_name().strip()
        if not code or not name:
            ui.notification_show("Please enter both code and name.", type="warning")
            return
        current = pa_custom_habitats.get().copy()
        if any(h["code"] == code for h in current):
            ui.notification_show(f"Habitat code '{code}' already exists.", type="warning")
            return
        current.append({"code": code, "name": name})
        pa_custom_habitats.set(current)
        # Add to lookup for display
        pa_config.EUNIS_LOOKUP[code] = name
        ui.notification_show(f"Added custom habitat: {code} - {name}", type="message")

    @reactive.Effect
    @reactive.event(input.pa_add_custom_benefit)
    def _add_custom_benefit():
        name = input.pa_custom_benefit_name().strip()
        unit = input.pa_custom_benefit_unit().strip()
        if not name or not unit:
            ui.notification_show("Please enter both name and unit.", type="warning")
            return
        current = pa_custom_benefits.get().copy()
        all_names = list(input.pa_benefits_select() or []) + [b["name"] for b in current]
        if name in all_names:
            ui.notification_show(f"Benefit '{name}' already exists.", type="warning")
            return
        current.append({"name": name, "unit": unit})
        pa_custom_benefits.set(current)
        ui.notification_show(f"Added custom benefit: {name} ({unit})", type="message")

    # PA Export handlers
    @render.download(filename=lambda: f"MARBEFES_PhysicalAccounts_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    def pa_download_standalone():
        gdf = geo_data.get()
        assignments = pa_habitat_assignments.get()
        unit = input.pa_area_unit()
        crs = original_crs.get()

        extent_df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs) if gdf is not None and assignments else pd.DataFrame()

        selected_benefits = list(input.pa_benefits_select() or [])
        custom_bens = pa_custom_benefits.get()
        all_benefits = selected_benefits + [b["name"] for b in custom_bens]
        habitat_codes = sorted(set(assignments.values())) if assignments else []

        supply_data = _collect_pa_supply_data(all_benefits, habitat_codes)
        supply_df = pa_calculations.assemble_supply_table(supply_data, habitat_codes)
        completeness = pa_calculations.validate_completeness(supply_data, habitat_codes, all_benefits)

        metadata = {
            "eaa_name": input.pa_eaa_name() or "Not specified",
            "boundary_description": input.pa_boundary_desc() or "Not specified",
            "accounting_year": input.pa_accounting_year() or 2024,
        }

        return pa_export.generate_pa_workbook(
            extent_df=extent_df, supply_df=supply_df,
            assignments=assignments, metadata=metadata,
            completeness=completeness, unit=unit,
        )

    @render.download(filename=lambda: f"MARBEFES_EVA_PA_Combined_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    def pa_download_combined():
        # Collect PA data
        gdf = geo_data.get()
        assignments = pa_habitat_assignments.get()
        unit = input.pa_area_unit()
        crs = original_crs.get()

        extent_df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs) if gdf is not None and assignments else pd.DataFrame()

        selected_benefits = list(input.pa_benefits_select() or [])
        custom_bens = pa_custom_benefits.get()
        all_benefits = selected_benefits + [b["name"] for b in custom_bens]
        habitat_codes = sorted(set(assignments.values())) if assignments else []

        supply_data = _collect_pa_supply_data(all_benefits, habitat_codes)
        supply_df = pa_calculations.assemble_supply_table(supply_data, habitat_codes)
        completeness = pa_calculations.validate_completeness(supply_data, habitat_codes, all_benefits)

        pa_metadata = {
            "eaa_name": input.pa_eaa_name() or "Not specified",
            "boundary_description": input.pa_boundary_desc() or "Not specified",
            "accounting_year": input.pa_accounting_year() or 2024,
        }

        eva_args = {
            "results": calculate_results(),
            "uploaded_data": uploaded_data.get(),
            "user_classifications": feature_classifications.get(),
            "data_type": input.data_type(),
            "metadata": {
                "ec_name": input.ec_name() if input.ec_name() else "Not specified",
                "study_area": input.study_area() if input.study_area() else "Not specified",
                "data_description": input.data_description() if input.data_description() else "Not specified",
            },
            "ec_store": ec_store.get(),
        }

        return pa_export.generate_combined_workbook(
            eva_args=eva_args,
            pa_extent_df=extent_df, pa_supply_df=supply_df,
            pa_assignments=assignments, pa_metadata=pa_metadata,
            pa_completeness=completeness, pa_unit=unit,
        )
```

- [ ] **Step 6: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('OK')"`

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "feat(pa): add Physical Accounts server logic — assignments, extent, supply, export"
```

---

### Task 8: Add habitat type option to Map tab

**Files:**
- Modify: `app.py` — map_variable update observer + categorical map code path

- [ ] **Step 1: Add reactive observer to update map_variable choices**

Add after the PA server logic:

```python
    @reactive.Effect
    @reactive.event(pa_habitat_assignments)
    def _update_map_variable_for_pa():
        assignments = pa_habitat_assignments.get()
        base_choices = ["EV", "AQ1", "AQ2", "AQ3", "AQ4", "AQ5", "AQ6", "AQ7",
                        "AQ8", "AQ9", "AQ10", "AQ11", "AQ12", "AQ13", "AQ14", "AQ15"]
        if assignments:
            base_choices.append("Habitat Type (PA)")
        ui.update_select("map_variable", choices=base_choices)
```

- [ ] **Step 2: Add categorical choropleth code path in the map rendering function**

In the `map_output` function, add a check at the beginning for the PA habitat type variable. Find the section where `create_ev_map` is called and add before it:

```python
        # Handle PA Habitat Type categorical map
        if input.map_variable() == "Habitat Type (PA)":
            assignments = pa_habitat_assignments.get()
            if not assignments:
                return ui.p("No habitat assignments available.", style="color: #6c757d; text-align: center; padding: 2rem;")

            map_gdf = gdf.merge(
                pd.DataFrame(list(assignments.items()), columns=["Subzone ID", "habitat_code"]),
                on="Subzone ID", how="inner"
            )
            map_gdf["habitat_name"] = map_gdf["habitat_code"].map(lambda c: pa_config.EUNIS_LOOKUP.get(c, c))

            # Build categorical color map
            unique_habitats = map_gdf["habitat_code"].unique().tolist()
            color_map = {h: pa_config.HABITAT_PALETTE[i % len(pa_config.HABITAT_PALETTE)]
                        for i, h in enumerate(unique_habitats)}

            bounds = map_gdf.total_bounds
            center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
            zoom = auto_zoom_level(bounds)
            tiles = BASEMAP_TILES.get(input.map_basemap(), "cartodbpositron")
            m = folium.Map(location=center, zoom_start=zoom, tiles=tiles)

            def habitat_style(feature):
                code = feature["properties"].get("habitat_code", "")
                return {
                    "fillColor": color_map.get(code, "#999999"),
                    "color": "#333333",
                    "weight": 0.5,
                    "fillOpacity": float(input.map_opacity()),
                }

            folium.GeoJson(
                map_gdf.to_json(),
                style_function=habitat_style,
                tooltip=folium.GeoJsonTooltip(
                    fields=["Subzone ID", "habitat_code", "habitat_name"],
                    aliases=["Subzone:", "EUNIS Code:", "Habitat:"],
                )
            ).add_to(m)

            # Legend
            legend_html = '<div style="position: fixed; bottom: 30px; left: 30px; background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.2); z-index: 1000; font-size: 0.85rem;">'
            legend_html += '<strong>Habitat Types</strong><br>'
            for code in unique_habitats:
                name = pa_config.EUNIS_LOOKUP.get(code, code)
                color = color_map[code]
                legend_html += f'<span style="background:{color}; width:12px; height:12px; display:inline-block; margin-right:5px; border-radius:2px;"></span>{code} - {name}<br>'
            legend_html += '</div>'
            m.get_root().html.add_child(folium.Element(legend_html))

            return ui.HTML(m._repr_html_())
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(pa): add Habitat Type categorical choropleth to Map tab"
```

---

## Chunk 3: Testing and Final Integration

### Task 9: Run full test suite and integration check

**Files:**
- Existing: `tests/test_pa_calculations.py`

- [ ] **Step 1: Run all PA calculation tests**

Run: `python -m pytest tests/test_pa_calculations.py -v`

Expected: All tests PASS

- [ ] **Step 2: Run import checks for all modules**

Run: `python -c "import pa_config; import pa_calculations; import pa_export; import eva_config; import eva_calculations; import eva_export; print('All modules import OK')"`

- [ ] **Step 3: Verify app.py compiles**

Run: `python -c "import py_compile; py_compile.compile('app.py', doraise=True); print('app.py OK')"`

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "test(pa): verify all PA modules and tests pass"
```

---

### Task 10: Update requirements.txt and README

**Files:**
- Modify: `requirements.txt`
- Modify: `README.md`

- [ ] **Step 1: Add pyproj to requirements.txt if not already present**

Check if `pyproj` is listed (it's a dependency of geopandas but should be explicit):

```
pyproj>=3.6.0
```

- [ ] **Step 2: Update README.md project structure and features**

Add to the Features section:
```markdown
- **Physical Accounts** - SEEA EA physical natural capital accounting
  - Ecosystem Extent Account from spatial grid (EUNIS Level 3 habitats)
  - Supply Table for societal benefits (configurable, 5 defaults)
  - Habitat type categorical map visualization
  - Excel export (standalone or combined with EVA)
```

Add to Project Structure:
```markdown
pa_config.py            # Physical Accounts constants and EUNIS reference
pa_calculations.py      # Physical Accounts calculation functions
pa_export.py            # Physical Accounts Excel export
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt README.md
git commit -m "docs: update requirements and README for Physical Accounts module"
```
