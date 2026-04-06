# EMODnet EUNIS L3 Integration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add EUSeaMap EUNIS Level 3 habitat data to the EVA app, enabling BBT8-format Physical Accounts with standardized habitat classification.

**Architecture:** Extraction script clips EUSeaMap GDB to BBT area and overlays onto hex grid. New `eunis_data.py` module computes extent/condition/supply per EUNIS class. App UI adds EUNIS upload + BBT8 export. All backward-compatible with existing manual PA flow.

**Tech Stack:** Python 3.11, geopandas, fiona, openpyxl, shiny (conda env: `shiny`)

**Run tests:** `conda run -n shiny python -m pytest tests/ -v`

**Spec:** `docs/superpowers/specs/2026-03-18-eunis-integration-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `eunis_data.py` | Create | Pure functions: load overlay, compute extent/condition/supply/accounts |
| `tests/test_eunis_data.py` | Create | Unit tests for eunis_data functions |
| `scripts/extract_eunis_for_bbt.py` | Create | One-time: clip EUSeaMap GDB → hex grid overlay GeoPackage |
| `pa_export.py` | Modify | Add `generate_bbt8_workbook()` |
| `eva_ui.py` | Modify | Add EUNIS upload widget + BBT8 download button in PA sidebar |
| `app.py` | Modify | Add EUNIS upload handler + BBT8 export handler + EUNIS-aware PA renderers |
| `tutorial/eunis_l3_lithuanian.gpkg` | Generate | Pre-extracted EUNIS overlay for Lithuanian BBT5 |

---

### Task 1: Create eunis_data.py module with tests

**Files:**
- Create: `eunis_data.py`
- Create: `tests/test_eunis_data.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_eunis_data.py
"""Tests for eunis_data module."""
import numpy as np
import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import Point, box


def _make_eunis_gdf():
    """Synthetic EUNIS overlay: 4 subzones, 3 habitat types."""
    return gpd.GeoDataFrame({
        "Subzone_ID": ["R001_C001", "R001_C002", "R002_C001", "R002_C002"],
        "dominant_EUNIS": ["A5.25", "A5.25", "A4.4", "A5.23"],
        "dominant_EUNIS_name": [
            "Circalittoral fine sand", "Circalittoral fine sand",
            "Baltic exposed circalittoral rock", "Infralittoral fine sand",
        ],
        "habitat_count": [2, 1, 3, 1],
        "dominant_pct": [75.0, 100.0, 60.0, 90.0],
        "coverage_pct": [95.0, 100.0, 85.0, 90.0],
    }, geometry=[box(0,0,1,1), box(1,0,2,1), box(0,1,1,2), box(1,1,2,2)],
       crs="EPSG:3346")


def _make_eva_gdf():
    """Synthetic EVA scores matching the EUNIS overlay subzones."""
    return gpd.GeoDataFrame({
        "Subzone_ID": ["R001_C001", "R001_C002", "R002_C001", "R002_C002"],
        "AQ7_HABITATS": [1.5, 2.0, 3.0, 1.0],
        "ZooScore": [4.0, 3.5, 4.5, 3.0],
        "PhytoScore": [2.0, 2.5, 1.5, 3.0],
        "MaxBenthos": [3.0, 2.0, 4.0, 1.5],
        "EVA_all_fish": [np.nan, 1.0, np.nan, 2.0],
        "TotalEV_MAX": [4.0, 3.5, 4.5, 3.0],
        "Confidence": [0.3, 0.3, 0.3, 0.3],
    }, geometry=[box(0,0,1,1), box(1,0,2,1), box(0,1,1,2), box(1,1,2,2)],
       crs="EPSG:3346")


class TestComputeEunisExtent:
    def test_basic_extent(self):
        from eunis_data import compute_eunis_extent
        result = compute_eunis_extent(_make_eunis_gdf(), unit="Ha")
        assert len(result) == 3  # 3 unique habitat types
        assert "EUNIS_code" in result.columns
        assert "EUNIS_name" in result.columns
        assert "n_subzones" in result.columns
        # A5.25 has 2 subzones
        a525 = result[result["EUNIS_code"] == "A5.25"]
        assert a525["n_subzones"].iloc[0] == 2

    def test_pct_sums_to_100(self):
        from eunis_data import compute_eunis_extent
        result = compute_eunis_extent(_make_eunis_gdf())
        assert result["pct_of_total"].sum() == pytest.approx(100.0, abs=0.5)


class TestComputeEunisCondition:
    def test_basic_condition(self):
        from eunis_data import compute_eunis_condition
        result = compute_eunis_condition(_make_eunis_gdf(), _make_eva_gdf())
        assert "Habitat_EV" in result.columns
        assert "Habitat_confidence" in result.columns
        # A5.25 has 2 subzones with TotalEV_MAX 4.0 and 3.5 → mean = 3.75
        a525 = result[result["EUNIS_code"] == "A5.25"]
        assert a525["Habitat_EV"].iloc[0] == pytest.approx(3.75)

    def test_no_eva_match_gives_nan(self):
        from eunis_data import compute_eunis_condition
        eunis = _make_eunis_gdf()
        eva = _make_eva_gdf()
        eva["Subzone_ID"] = ["X1", "X2", "X3", "X4"]  # no match
        result = compute_eunis_condition(eunis, eva)
        assert result["Habitat_EV"].isna().all()


class TestComputeEunisSupply:
    def test_basic_supply(self):
        from eunis_data import compute_eunis_supply
        result = compute_eunis_supply(_make_eunis_gdf(), _make_eva_gdf())
        assert "Fisheries_proxy" in result.columns
        assert "FoodWeb_proxy" in result.columns
        assert "PrimaryProd_proxy" in result.columns


class TestBuildAccountsSummary:
    def test_merges_extent_and_condition(self):
        from eunis_data import compute_eunis_extent, compute_eunis_condition, build_accounts_summary
        extent = compute_eunis_extent(_make_eunis_gdf())
        condition = compute_eunis_condition(_make_eunis_gdf(), _make_eva_gdf())
        accounts = build_accounts_summary(extent, condition)
        assert "area_m2" in accounts.columns
        assert "Habitat_EV" in accounts.columns
        assert len(accounts) == 3


class TestBuildMissingValues:
    def test_detects_no_eva(self):
        from eunis_data import build_missing_values
        eunis = _make_eunis_gdf()
        eva = _make_eva_gdf()
        eva = eva[eva["Subzone_ID"] != "R002_C002"]  # remove one
        missing = build_missing_values(eunis, eva, total_bbt_area_m2=1e9)
        assert len(missing) >= 1
        assert "no_eva" in missing["issue_type"].values
```

- [ ] **Step 2: Run tests — expect FAIL (no module)**

Run: `conda run -n shiny python -m pytest tests/test_eunis_data.py -v`

- [ ] **Step 3: Implement eunis_data.py**

```python
# eunis_data.py
"""EUNIS Level 3 habitat data processing for Physical Accounts.

Pure functions operating on GeoDataFrames. No Shiny dependencies.
Handles EUSeaMap 2007/2012 codes (A5.25 format) — does NOT use
pa_config.EUNIS_LOOKUP (which uses 2022 codes like MA12).
"""
import logging

import geopandas as gpd
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_eunis_overlay(path: str) -> gpd.GeoDataFrame:
    """Load pre-extracted EUNIS overlay GeoPackage."""
    gdf = gpd.read_file(path)
    required = {"Subzone_ID", "dominant_EUNIS", "dominant_EUNIS_name"}
    missing = required - set(gdf.columns)
    if missing:
        raise ValueError(f"EUNIS overlay missing columns: {missing}")
    return gdf


def compute_eunis_extent(eunis_gdf: gpd.GeoDataFrame, unit: str = "Ha") -> pd.DataFrame:
    """Compute area per EUNIS class from dominant habitat assignments."""
    from pa_config import AREA_CONVERSIONS
    gdf = eunis_gdf.copy()
    # Reproject to metric CRS for area calculation
    if gdf.crs is not None and gdf.crs.is_projected:
        metric = gdf  # already metric (e.g., EPSG:3346)
    else:
        from pa_calculations import _reproject_to_metric
        metric = _reproject_to_metric(gdf, original_crs=gdf.crs)
    conversion = AREA_CONVERSIONS.get(unit, 10_000)
    metric["_area"] = metric.geometry.area / conversion

    agg = metric.groupby("dominant_EUNIS").agg(
        EUNIS_name=("dominant_EUNIS_name", "first"),
        n_subzones=("Subzone_ID", "count"),
        total_area=("_area", "sum"),
    ).reset_index().rename(columns={"dominant_EUNIS": "EUNIS_code"})

    total = agg["total_area"].sum()
    agg["pct_of_total"] = (agg["total_area"] / total * 100).round(1) if total > 0 else 0.0
    agg["total_area"] = agg["total_area"].round(2)
    agg["area_m2"] = (agg["total_area"] * AREA_CONVERSIONS.get(unit, 10_000)).round(0)

    return agg.sort_values("total_area", ascending=False).reset_index(drop=True)


def compute_eunis_condition(
    eunis_gdf: gpd.GeoDataFrame, eva_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Compute mean EVA scores per EUNIS class via Subzone_ID join."""
    # Join on Subzone_ID
    eunis_ids = eunis_gdf[["Subzone_ID", "dominant_EUNIS", "dominant_EUNIS_name"]].copy()

    eva_cols = ["Subzone_ID"]
    if "TotalEV_MAX" in eva_gdf.columns:
        eva_cols.append("TotalEV_MAX")
    elif "TotalEV" in eva_gdf.columns:
        eva_cols.append("TotalEV")
    if "Confidence" in eva_gdf.columns:
        eva_cols.append("Confidence")

    # Fallback: compute max of EC scores as Habitat_EV
    ec_score_cols = [c for c in ["AQ7_HABITATS", "ZooScore", "PhytoScore", "MaxBenthos", "EVA_all_fish"]
                     if c in eva_gdf.columns]
    eva_cols.extend(ec_score_cols)

    eva_subset = eva_gdf[eva_cols].drop(columns="geometry", errors="ignore") if "geometry" in eva_gdf.columns else eva_gdf[eva_cols]

    merged = eunis_ids.merge(eva_subset, on="Subzone_ID", how="left")

    # Habitat_EV = TotalEV_MAX if available, else max of EC scores
    if "TotalEV_MAX" in merged.columns:
        merged["_ev"] = merged["TotalEV_MAX"]
    elif ec_score_cols:
        merged["_ev"] = merged[ec_score_cols].max(axis=1, skipna=True)
    else:
        merged["_ev"] = np.nan

    merged["_conf"] = merged.get("Confidence", pd.Series(np.nan, index=merged.index))

    cond = merged.groupby("dominant_EUNIS").agg(
        EUNIS_name=("dominant_EUNIS_name", "first"),
        Habitat_EV=("_ev", "mean"),
        Habitat_confidence=("_conf", "mean"),
        n_subzones=("Subzone_ID", "count"),
    ).reset_index().rename(columns={"dominant_EUNIS": "EUNIS_code"})

    cond["Habitat_EV"] = cond["Habitat_EV"].round(3)
    cond["Habitat_confidence"] = cond["Habitat_confidence"].round(3)
    return cond


def compute_eunis_supply(
    eunis_gdf: gpd.GeoDataFrame, eva_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Compute ecosystem service proxies per EUNIS class."""
    eunis_ids = eunis_gdf[["Subzone_ID", "dominant_EUNIS", "dominant_EUNIS_name"]].copy()

    supply_map = {
        "EVA_all_fish": "Fisheries_proxy",
        "ZooScore": "FoodWeb_proxy",
        "PhytoScore": "PrimaryProd_proxy",
    }
    available = {k: v for k, v in supply_map.items() if k in eva_gdf.columns}

    eva_cols = ["Subzone_ID"] + list(available.keys())
    eva_subset = eva_gdf[eva_cols].drop(columns="geometry", errors="ignore") if "geometry" in eva_gdf.columns else eva_gdf[eva_cols]

    merged = eunis_ids.merge(eva_subset, on="Subzone_ID", how="left")

    supply = merged.groupby("dominant_EUNIS")[list(available.keys())].mean().round(3)
    supply = supply.reset_index().rename(columns={"dominant_EUNIS": "EUNIS_code", **available})

    # Add name
    name_map = eunis_gdf.drop_duplicates("dominant_EUNIS").set_index("dominant_EUNIS")["dominant_EUNIS_name"]
    supply["EUNIS_name"] = supply["EUNIS_code"].map(name_map)

    return supply


def build_accounts_summary(extent: pd.DataFrame, condition: pd.DataFrame) -> pd.DataFrame:
    """Build BBT8-format accounts table."""
    accounts = extent[["EUNIS_code", "EUNIS_name", "area_m2"]].merge(
        condition[["EUNIS_code", "Habitat_EV", "Habitat_confidence"]],
        on="EUNIS_code", how="left",
    )
    return accounts


def build_missing_values(
    eunis_gdf: gpd.GeoDataFrame, eva_gdf: gpd.GeoDataFrame,
    total_bbt_area_m2: float,
) -> pd.DataFrame:
    """Identify subzones with no EUNIS match or no EVA data."""
    rows = []
    eunis_ids = set(eunis_gdf["Subzone_ID"])
    eva_ids = set(eva_gdf["Subzone_ID"]) if "Subzone_ID" in eva_gdf.columns else set()

    # Subzones in EUNIS but not in EVA
    for sid in eunis_ids - eva_ids:
        rows.append({"Subzone_ID": sid, "issue_type": "no_eva", "notes": "No EVA score data"})

    # Subzones with low EUNIS coverage
    if "coverage_pct" in eunis_gdf.columns:
        low_cov = eunis_gdf[eunis_gdf["coverage_pct"] < 50]
        for _, row in low_cov.iterrows():
            rows.append({
                "Subzone_ID": row["Subzone_ID"],
                "issue_type": "low_coverage",
                "notes": f"EUNIS coverage only {row['coverage_pct']:.0f}%",
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Subzone_ID", "issue_type", "notes"])
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_eunis_data.py -v`

- [ ] **Step 5: Commit**

```bash
git add eunis_data.py tests/test_eunis_data.py
git commit -m "feat: add eunis_data module with extent/condition/supply/accounts functions"
```

---

### Task 2: Create extraction script and generate Lithuanian overlay

**Files:**
- Create: `scripts/extract_eunis_for_bbt.py`
- Generate: `tutorial/eunis_l3_lithuanian.gpkg`

- [ ] **Step 1: Write the extraction script**

The script must:
1. Accept `--euseamap`, `--grid`, `--output` CLI args
2. Extract GDB from zip to temp dir
3. Read EUSeaMap with bbox from grid bounds
4. Filter out Na EUNIScomb
5. Reproject to grid CRS
6. For each hex cell: intersect with EUNIS polygons, find dominant type
7. Write output GeoPackage

```python
# scripts/extract_eunis_for_bbt.py
"""Extract EUSeaMap EUNIS L3 overlay for a BBT hexagonal grid.

Usage:
    python scripts/extract_eunis_for_bbt.py \
        --euseamap path/to/EUSeaMap_2023.zip \
        --grid path/to/HexGrid.gpkg \
        --output tutorial/eunis_l3_lithuanian.gpkg
"""
import argparse
import logging
import os
import shutil
import sys
import tempfile
import zipfile

import fiona
import geopandas as gpd
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_gdb_from_zip(zip_path):
    """Extract FileGDB from zip to a temp directory. Returns (tmpdir, gdb_path)."""
    tmpdir = tempfile.mkdtemp()
    logger.info("Extracting %s to %s...", zip_path, tmpdir)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmpdir)
    # Find .gdb directory
    for item in os.listdir(tmpdir):
        if item.endswith(".gdb"):
            return tmpdir, os.path.join(tmpdir, item)
    raise FileNotFoundError("No .gdb found in zip")


def compute_overlay(grid_gdf, eunis_gdf):
    """For each hex cell, compute dominant EUNIS type by intersection area."""
    results = []
    total = len(grid_gdf)

    for i, (idx, hex_row) in enumerate(grid_gdf.iterrows()):
        if (i + 1) % 50 == 0 or i == 0:
            logger.info("  Processing hex %d/%d...", i + 1, total)

        hex_geom = hex_row.geometry
        hex_area = hex_geom.area

        # Find intersecting EUNIS polygons
        candidates = eunis_gdf[eunis_gdf.intersects(hex_geom)]
        if candidates.empty:
            results.append({
                "Subzone_ID": hex_row["Subzone_ID"],
                "dominant_EUNIS": np.nan,
                "dominant_EUNIS_name": np.nan,
                "habitat_count": 0,
                "dominant_pct": 0.0,
                "coverage_pct": 0.0,
                "geometry": hex_geom,
            })
            continue

        # Compute intersection areas
        intersections = []
        for _, eunis_row in candidates.iterrows():
            try:
                inter = hex_geom.intersection(eunis_row.geometry)
                if not inter.is_empty:
                    intersections.append({
                        "code": eunis_row["EUNIScomb"],
                        "name": eunis_row["EUNIScombD"],
                        "area": inter.area,
                    })
            except Exception:
                continue

        if not intersections:
            results.append({
                "Subzone_ID": hex_row["Subzone_ID"],
                "dominant_EUNIS": np.nan,
                "dominant_EUNIS_name": np.nan,
                "habitat_count": 0,
                "dominant_pct": 0.0,
                "coverage_pct": 0.0,
                "geometry": hex_geom,
            })
            continue

        inter_df = pd.DataFrame(intersections)
        # Group by code (same code may appear from multiple polygons)
        by_code = inter_df.groupby("code").agg(
            name=("name", "first"),
            total_area=("area", "sum"),
        ).sort_values("total_area", ascending=False)

        dominant_code = by_code.index[0]
        dominant_name = by_code.iloc[0]["name"]
        dominant_area = by_code.iloc[0]["total_area"]
        total_eunis_area = by_code["total_area"].sum()

        results.append({
            "Subzone_ID": hex_row["Subzone_ID"],
            "dominant_EUNIS": dominant_code,
            "dominant_EUNIS_name": dominant_name,
            "habitat_count": len(by_code),
            "dominant_pct": round(dominant_area / hex_area * 100, 1) if hex_area > 0 else 0,
            "coverage_pct": round(total_eunis_area / hex_area * 100, 1) if hex_area > 0 else 0,
            "geometry": hex_geom,
        })

    return gpd.GeoDataFrame(results, crs=grid_gdf.crs)


def main():
    parser = argparse.ArgumentParser(description="Extract EUSeaMap EUNIS overlay for a BBT grid")
    parser.add_argument("--euseamap", required=True, help="Path to EUSeaMap_2023.zip")
    parser.add_argument("--grid", required=True, help="Path to hex grid GeoPackage")
    parser.add_argument("--output", required=True, help="Output GeoPackage path")
    args = parser.parse_args()

    # Read grid
    logger.info("Reading grid: %s", args.grid)
    grid = gpd.read_file(args.grid)
    grid["Subzone_ID"] = [f"R{int(r):03d}_C{int(c):03d}"
                          for r, c in zip(grid["row_index"], grid["col_index"])]
    logger.info("  %d hexagons, CRS: %s", len(grid), grid.crs)

    # Get bbox in WGS84 for EUSeaMap query
    grid_4326 = grid.to_crs(epsg=4326)
    bbox = tuple(grid_4326.total_bounds)  # minx, miny, maxx, maxy
    logger.info("  BBox (WGS84): %s", bbox)

    # Extract and read EUSeaMap
    tmpdir, gdb_path = extract_gdb_from_zip(args.euseamap)
    try:
        layers = fiona.listlayers(gdb_path)
        # Prefer named layer; fall back to first
        layer = "EUSeaMap_2023" if "EUSeaMap_2023" in layers else layers[0]
        logger.info("Reading EUSeaMap layer '%s' with bbox filter...", layer)
        eunis = gpd.read_file(gdb_path, layer=layer, bbox=bbox)
        logger.info("  %d features in bbox", len(eunis))

        # Filter Na
        eunis = eunis[eunis["EUNIScomb"] != "Na"].copy()
        logger.info("  %d features after removing Na", len(eunis))

        if len(eunis) == 0:
            logger.error("No EUNIS features found in study area. Check bbox.")
            sys.exit(1)

        # Reproject to grid CRS
        eunis = eunis.to_crs(grid.crs)

        # Compute overlay
        logger.info("Computing spatial overlay...")
        result = compute_overlay(grid, eunis)

        # Write output
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        result.to_file(args.output, driver="GPKG")
        logger.info("Written %d hexagons to %s", len(result), args.output)

        # Summary
        valid = result["dominant_EUNIS"].notna()
        logger.info("  %d with EUNIS data, %d without", valid.sum(), (~valid).sum())
        logger.info("  Unique EUNIS types: %d", result["dominant_EUNIS"].nunique())
        logger.info("  Types: %s", result["dominant_EUNIS"].value_counts().to_dict())

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the extraction for Lithuanian BBT**

```bash
conda run -n shiny python scripts/extract_eunis_for_bbt.py \
  --euseamap "C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\BBTs\EMODNET\EUSeaMap_2023.zip" \
  --grid "C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\EVA_FINAL\EVA Grids\HexGrid3kmLithuanianBBT.gpkg" \
  --output tutorial/eunis_l3_lithuanian.gpkg
```

Expected: 425 hexagons output, ~300-400 with EUNIS data, ~15-20 unique types.

- [ ] **Step 3: Verify output**

```bash
conda run -n shiny python -c "import geopandas as gpd; g=gpd.read_file('tutorial/eunis_l3_lithuanian.gpkg'); print(f'Features: {len(g)}, EUNIS types: {g.dominant_EUNIS.nunique()}, With data: {g.dominant_EUNIS.notna().sum()}')"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/extract_eunis_for_bbt.py tutorial/eunis_l3_lithuanian.gpkg
git commit -m "feat: add EUSeaMap extraction script and Lithuanian EUNIS overlay"
```

---

### Task 3: Add BBT8-format export to pa_export.py

**Files:**
- Modify: `pa_export.py`

- [ ] **Step 1: Add generate_bbt8_workbook function**

Append to `pa_export.py`:

```python
def generate_bbt8_workbook(accounts, main_values, extent, condition,
                           supply, metadata, missing_values=None):
    """Generate BBT8-format Excel workbook for Physical Accounts.

    Follows the Irish Sea BBT8 standard with sheets:
    ReadMe, main_values, habitat_area_sum, accounts, missing_values,
    condition, supply.
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # ReadMe
        readme_rows = [(k, v) for k, v in metadata.items()]
        pd.DataFrame(readme_rows, columns=["Parameter", "Value"]).to_excel(
            writer, sheet_name="ReadMe", index=False)

        # main_values (per-subzone)
        main_values.to_excel(writer, sheet_name="main_values", index=False)

        # habitat_area_sum
        if "area_m2" in extent.columns:
            area_sum = extent[["EUNIS_code", "area_m2"]].copy()
            area_sum.columns = ["EUNIS2019C", "Sum of area_m2"]
        else:
            area_sum = extent[["EUNIS_code", "total_area"]].copy()
            area_sum.columns = ["EUNIS2019C", "Sum of area"]
        area_sum.to_excel(writer, sheet_name="habitat_area_sum", index=False)

        # accounts (main summary)
        acct = accounts.copy()
        acct.columns = [c.replace("EUNIS_code", "EUNIS2019C").replace("EUNIS_name", "Habitat")
                        for c in acct.columns]
        acct.to_excel(writer, sheet_name="accounts", index=False)

        # missing_values
        if missing_values is not None and not missing_values.empty:
            missing_values.to_excel(writer, sheet_name="missing_values", index=False)

        # condition
        condition.to_excel(writer, sheet_name="condition", index=False)

        # supply
        supply.to_excel(writer, sheet_name="supply", index=False)

    # Apply styling
    buffer.seek(0)
    wb = openpyxl.load_workbook(buffer)
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        style_worksheet(ws)
        ws.sheet_properties.tabColor = "006994"
    styled_buffer = io.BytesIO()
    wb.save(styled_buffer)
    styled_buffer.seek(0)
    return styled_buffer
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `conda run -n shiny python -m pytest tests/ -v`

- [ ] **Step 3: Commit**

```bash
git add pa_export.py
git commit -m "feat: add BBT8-format Excel export to pa_export"
```

---

### Task 4: Add EUNIS upload and BBT8 export to app UI

**Files:**
- Modify: `eva_ui.py:1005-1060` (PA sidebar)
- Modify: `app.py:1440-1500` (PA server section)

- [ ] **Step 1: Add EUNIS upload widget to PA sidebar**

In `eva_ui.py`, after the Study Area section (line ~1011) and before the EUNIS Habitats section (line ~1013), add a new section:

```python
ui.hr(),
ui.div(
    ui.h5("🗺️ EUNIS Overlay (EUSeaMap)", style="color: #006994; font-weight: 600; margin-bottom: 1rem;"),
    ui.p("Upload a pre-extracted EUNIS Level 3 overlay GeoPackage.",
         style="font-size: 0.9rem; color: #6c757d;"),
    ui.input_file(
        "upload_eunis_overlay",
        "Choose EUNIS Overlay (.gpkg)",
        accept=[".gpkg"],
        multiple=False,
        button_label="Browse...",
    ),
    ui.output_ui("eunis_status_ui"),
),
```

Also add a BBT8 download button in the Settings section (after line ~1044):

```python
ui.download_button("pa_download_bbt8", "📋 Download BBT8 Accounts (Excel)",
                   class_="btn-outline-primary", style="width: 100%; margin-top: 0.5rem;"),
```

And add a new card in the main panel (after the Supply Table card, line ~1057):

```python
ui.card(
    ui.card_header("📋 BBT8 Accounts Summary"),
    ui.div(ui.output_ui("eunis_accounts_ui"), style="padding: 1rem;")
),
```

- [ ] **Step 2: Add EUNIS server logic to app.py**

In the PA server section of `app.py` (after line ~1450), add:

```python
# EUNIS overlay reactive
eunis_overlay = reactive.Value(None)

# Cached EVA data loader (avoids re-reading 460MB file on every render)
@reactive.Calc
def cached_eva_data():
    from scripts.config import OUTPUT_DIR, COMBINED_LAYER
    path = os.path.join(OUTPUT_DIR, COMBINED_LAYER)
    if not os.path.exists(path):
        return None
    logger.info("Loading EVA data from %s (cached)", path)
    return gpd.read_file(path)

@reactive.Effect
@reactive.event(input.upload_eunis_overlay)
def _handle_eunis_upload():
    file_info = input.upload_eunis_overlay()
    if file_info is None or len(file_info) == 0:
        return
    try:
        import eunis_data
        gdf = eunis_data.load_eunis_overlay(file_info[0]["datapath"])
        eunis_overlay.set(gdf)
        # Auto-populate habitat assignments from overlay
        assignments = {row["Subzone_ID"]: row["dominant_EUNIS"]
                       for _, row in gdf.iterrows()
                       if pd.notna(row["dominant_EUNIS"])}
        pa_habitat_assignments.set(assignments)
        ui.notification_show(
            f"EUNIS overlay loaded: {gdf['dominant_EUNIS'].nunique()} habitat types, "
            f"{gdf['dominant_EUNIS'].notna().sum()} subzones with data.",
            type="message", duration=5)
    except Exception as e:
        ui.notification_show(f"Error loading EUNIS overlay: {e}", type="error")

@output
@render.ui
def eunis_status_ui():
    overlay = eunis_overlay.get()
    if overlay is None:
        return ui.div()
    n_types = overlay["dominant_EUNIS"].nunique()
    n_with = overlay["dominant_EUNIS"].notna().sum()
    n_total = len(overlay)
    return ui.div(
        ui.p(f"✅ {n_types} EUNIS types loaded, {n_with}/{n_total} subzones matched",
             style="color: #28a745; font-weight: 600; margin-top: 0.5rem;"),
        class_="info-box"
    )

@output
@render.ui
def eunis_accounts_ui():
    overlay = eunis_overlay.get()
    if overlay is None:
        return ui.p("Upload a EUNIS overlay to see BBT8 accounts.",
                    style="color: #6c757d; text-align: center; padding: 2rem;")
    import eunis_data
    # Get EVA data
    eva = cached_eva_data()
    if eva is None:
        return ui.p("Corrected EVA data not found.", style="color: #d32f2f;")
    if "Subzone_ID" not in eva.columns:
        return ui.p("EVA data missing Subzone_ID column.", style="color: #d32f2f;")

    extent = eunis_data.compute_eunis_extent(overlay, unit=input.pa_area_unit())
    condition = eunis_data.compute_eunis_condition(overlay, eva)
    accounts = eunis_data.build_accounts_summary(extent, condition)

    # Render table
    display = accounts.copy()
    display["area_m2"] = display["area_m2"].apply(lambda x: f"{x:,.0f}")
    display["Habitat_EV"] = display["Habitat_EV"].round(2)
    display["Habitat_confidence"] = display["Habitat_confidence"].round(2)
    return ui.TagList(
        ui.output_table("eunis_accounts_table"),
    )

@output
@render.table
def eunis_accounts_table():
    overlay = eunis_overlay.get()
    if overlay is None:
        return pd.DataFrame()
    import eunis_data
    eva = cached_eva_data()
    if eva is None:
        return pd.DataFrame()
    extent = eunis_data.compute_eunis_extent(overlay, unit=input.pa_area_unit())
    condition = eunis_data.compute_eunis_condition(overlay, eva)
    accounts = eunis_data.build_accounts_summary(extent, condition)
    accounts.columns = ["EUNIS Code", "Habitat", "Area (m2)", "Habitat EV", "Confidence"]
    return accounts

@render.download(filename=lambda: f"MARBEFES_BBT8_PhysicalAccounts_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx")
def pa_download_bbt8():
    overlay = eunis_overlay.get()
    if overlay is None:
        return None
    import eunis_data
    from pa_export import generate_bbt8_workbook

    eva = cached_eva_data()
    if eva is None:
        return pd.DataFrame()

    unit = input.pa_area_unit()
    extent = eunis_data.compute_eunis_extent(overlay, unit=unit)
    condition = eunis_data.compute_eunis_condition(overlay, eva)
    supply = eunis_data.compute_eunis_supply(overlay, eva)
    accounts = eunis_data.build_accounts_summary(extent, condition)
    missing = eunis_data.build_missing_values(overlay, eva, total_bbt_area_m2=0)

    # main_values: per-subzone
    mv = overlay[["Subzone_ID", "dominant_EUNIS"]].merge(
        eva[["Subzone_ID", "TotalEV_MAX", "Confidence"]].drop(columns="geometry", errors="ignore"),
        on="Subzone_ID", how="left")
    mv.columns = ["Subzone_ID", "EUNIS_code", "Habitat_EV", "Habitat_confidence"]

    metadata = {
        "Report": "SEEA EA Physical Accounts",
        "BBT": input.pa_eaa_name() or "Not specified",
        "Boundary": input.pa_boundary_desc() or "Not specified",
        "Year": str(input.pa_accounting_year()),
        "Framework": "SEEA EA / MARBEFES WP4",
        "Generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "EUNIS Source": "EMODnet EUSeaMap 2023",
        "EVA Version": "MARBEFES EVA v3.3",
    }

    return generate_bbt8_workbook(
        accounts=accounts, main_values=mv, extent=extent,
        condition=condition, supply=supply, metadata=metadata,
        missing_values=missing)
```

- [ ] **Step 3: Add geopandas import to app.py** (if not already present)

Check that `import geopandas as gpd` is in app.py imports. It should be (line 18).

- [ ] **Step 4: Run full test suite**

Run: `conda run -n shiny python -m pytest tests/ -v`
Expected: All tests pass (116 existing + new eunis_data tests).

- [ ] **Step 5: Commit**

```bash
git add eva_ui.py app.py pa_export.py
git commit -m "feat: add EUNIS overlay upload, BBT8 accounts display, and BBT8 Excel export to PA tab"
```

---

### Task 5: End-to-end verification

- [ ] **Step 1: Launch the app**

Run: `conda run -n shiny python -m shiny run app.py --port 8792`

- [ ] **Step 2: Test EUNIS flow**

1. Go to Physical Accounts tab
2. Upload `tutorial/eunis_l3_lithuanian.gpkg` in the EUNIS Overlay section
3. Verify status shows habitat types and subzone count
4. Verify BBT8 Accounts Summary card shows EUNIS codes with EV and confidence
5. Click "Download BBT8 Accounts (Excel)"
6. Open the Excel — verify sheets: ReadMe, main_values, habitat_area_sum, accounts, condition, supply

- [ ] **Step 3: Verify backward compatibility**

1. Restart app without EUNIS overlay
2. Verify existing PA flow still works (manual habitat assignment, extent, supply)
3. Upload GeoJSON grid → upload CSV → save EC → manual PA → download PA report

- [ ] **Step 4: Bump version**

In `version.py`: change to `3.4.0`, codename `"EUNIS Integration"`.

- [ ] **Step 5: Final commit**

```bash
git add version.py
git commit -m "feat: EUNIS L3 integration complete (v3.4.0)"
```
