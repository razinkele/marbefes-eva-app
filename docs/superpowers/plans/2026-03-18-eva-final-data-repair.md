# EVA_FINAL Data Repair Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all correctable data quality issues in the Lithuanian BBT5 EVA_FINAL dataset by producing corrected spatial layers and a validation report.

**Architecture:** 6 sequential Python scripts in `scripts/` sharing a `config.py`. Each script reads from `EVA_FINAL/`, writes corrected outputs to `EVA_FINAL_corrected/`. Pure logic functions are tested with synthetic DataFrames in `tests/test_repair_scripts.py`. A master `run_all.py` executes the full pipeline.

**Tech Stack:** Python 3.11, geopandas, pandas, numpy, fiona, openpyxl (all in `shiny` conda env)

**Run tests with:** `conda run -n shiny python -m pytest tests/test_repair_scripts.py -v`

**Spec:** `docs/superpowers/specs/2026-03-18-eva-final-data-repair-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/__init__.py` | Create | Makes scripts a Python package |
| `scripts/config.py` | Create | Shared paths, constants, dataset registry |
| `scripts/s01_clean_sentinels.py` | Create | Replace -9999 with NaN in AQ columns |
| `scripts/s02_standardize_crs.py` | Create | Reproject EPSG:3035 → EPSG:3346 |
| `scripts/s03_add_subzone_ids.py` | Create | Generate Subzone_ID from row/col indices |
| `scripts/s04_recompute_total_ev.py` | Create | MAX aggregation for Total EV |
| `scripts/s05_compute_confidence.py` | Create | Confidence index per EC per subzone |
| `scripts/s06_validate_and_report.py` | Create | Quality checks + Markdown/Excel report |
| `scripts/run_all.py` | Create | Master pipeline runner |
| `tests/test_repair_scripts.py` | Create | Unit tests for all pure logic |

---

### Task 1: Create config.py and test scaffolding

**Files:**
- Create: `scripts/config.py`
- Create: `tests/test_repair_scripts.py`

- [ ] **Step 1: Create scripts package**

Run: `mkdir -p scripts && touch scripts/__init__.py`

- [ ] **Step 2: Write config.py**

```python
# scripts/config.py
"""Shared configuration for EVA_FINAL data repair pipeline."""
import os

EVA_FINAL_DIR = os.path.normpath(
    r"C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\EVA_FINAL"
)
OUTPUT_DIR = os.path.normpath(
    r"C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\EVA_FINAL_corrected"
)
TARGET_CRS = "EPSG:3346"
SENTINEL_THRESHOLD = -9998  # values <= this are sentinels
EVA_SCALE_MIN = 0
EVA_SCALE_MAX = 5

# EC score columns in the combined layer
EC_SCORE_COLUMNS = {
    "Habitats": "AQ7_HABITATS",
    "Zooplankton": "ZooScore",
    "Phytoplankton": "PhytoScore",
    "Benthos": "MaxBenthos",
    "Fish": "EVA_all_fish",
}

# Benthos individual AQ columns (for MAX verification)
# Note: AQ7 in NewBenthos.shp but named differently in combined layer
BENTHOS_AQ_COLUMNS = ["AQ6_benthos", "AQ9_benthos", "AQ13_benthos"]
# Also check for AQ7 variants in benthos-specific files
BENTHOS_AQ_COLUMNS_ALT = ["AQ6", "AQ7", "AQ9", "AQ13"]  # NewBenthos.shp names

# Confidence parameters per EC
# (n_aqs_answered, max_possible_aqs, evidence_weight)
EC_CONFIDENCE = {
    "Habitats":      (1, 7, 3),
    "Zooplankton":   (1, 7, 2),
    "Phytoplankton": (1, 7, 3),
    "Benthos":       (4, 8, 3),
    "Fish_CL":       (1, 7, 2),  # Curonian Lagoon: AQ4 only, commercial catch
    "Fish_BS":       (2, 7, 3),  # Baltic Sea: AQ4+AQ8, BITS surveys
    "Fish":          (2, 7, 3),  # Fallback when CL/BS not distinguishable
}

# EVA 5-class bins
EVA_CLASS_BINS = [0, 1, 2, 3, 4, 5]
EVA_CLASS_LABELS = ["Very Low", "Low", "Medium", "High", "Very High"]

# Files that need sentinel cleanup (all files with AQ columns)
SENTINEL_FILES = [
    "ALL4EVA_2025_fixed_geometries.gpkg",
    "All4EVA_2025.gpkg",
    "NewBenthos.shp",
    "All_EVA_Sept_2025.shp",
    "final_EVA_without_Fish.gpkg",
]

# Files that need CRS reprojection
CRS_FILES = [
    "chrophyta_score.gpkg",
    "copepoda_score.gpkg",
    "cladocera_score.gpkg",
]

# Primary combined layer (used for Total EV recomputation)
COMBINED_LAYER = "ALL4EVA_2025_fixed_geometries.gpkg"
```

- [ ] **Step 3: Write test file skeleton**

```python
# tests/test_repair_scripts.py
"""Unit tests for EVA_FINAL data repair pipeline.

Tests use synthetic DataFrames — no dependency on EVA_FINAL files.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import Point
```

- [ ] **Step 4: Verify imports work**

Run: `conda run -n shiny python -c "import scripts.config; print('OK')"` (from project root)

- [ ] **Step 5: Commit**

```bash
git add scripts/config.py tests/test_repair_scripts.py
git commit -m "feat: add data repair pipeline config and test scaffolding"
```

---

### Task 2: Implement sentinel cleanup (01_clean_sentinels.py)

**Files:**
- Modify: `tests/test_repair_scripts.py`
- Create: `scripts/01_clean_sentinels.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_repair_scripts.py`:

```python
from scripts.config import SENTINEL_THRESHOLD, EVA_SCALE_MIN, EVA_SCALE_MAX


def _make_geo_df(data_dict):
    """Helper: create a GeoDataFrame with point geometries."""
    n = len(next(iter(data_dict.values())))
    gdf = gpd.GeoDataFrame(
        data_dict,
        geometry=[Point(i, i) for i in range(n)],
        crs="EPSG:3346",
    )
    return gdf


class TestCleanSentinels:

    def test_replaces_minus_9999_with_nan(self):
        from scripts.s01_clean_sentinels import clean_sentinels
        gdf = _make_geo_df({"AQ13": [1.5, -9999.0, 3.0, -9999.0]})
        result = clean_sentinels(gdf)
        assert result["AQ13"].isna().sum() == 2
        assert result["AQ13"].iloc[0] == pytest.approx(1.5)
        assert result["AQ13"].iloc[2] == pytest.approx(3.0)

    def test_preserves_valid_values(self):
        from scripts.s01_clean_sentinels import clean_sentinels
        gdf = _make_geo_df({"AQ6": [0.0, 2.5, 5.0], "AQ9": [1.0, 3.0, 4.0]})
        result = clean_sentinels(gdf)
        assert (result["AQ6"] == gdf["AQ6"]).all()
        assert (result["AQ9"] == gdf["AQ9"]).all()

    def test_finds_aq_columns_by_prefix(self):
        from scripts.s01_clean_sentinels import find_aq_columns
        cols = ["fid", "AQ6_benthos", "AQ13_benth", "ZooScore", "geometry"]
        result = find_aq_columns(cols)
        assert "AQ6_benthos" in result
        assert "AQ13_benth" in result
        assert "ZooScore" not in result
        assert "geometry" not in result

    def test_all_values_in_valid_range_after_cleanup(self):
        from scripts.s01_clean_sentinels import clean_sentinels
        gdf = _make_geo_df({"AQ13": [-9999.0, 0.5, 5.0, -9999.0, 3.0]})
        result = clean_sentinels(gdf)
        valid = result["AQ13"].dropna()
        assert (valid >= EVA_SCALE_MIN).all()
        assert (valid <= EVA_SCALE_MAX).all()
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `conda run -n shiny python -m pytest tests/test_repair_scripts.py::TestCleanSentinels -v`
Expected: ImportError (module not found)

- [ ] **Step 3: Implement 01_clean_sentinels.py**

```python
# scripts/s01_clean_sentinels.py
"""Step 1: Replace -9999 sentinel values with NaN in all AQ columns."""
import logging
import os

import geopandas as gpd
import numpy as np

from scripts.config import (
    EVA_FINAL_DIR, OUTPUT_DIR, SENTINEL_THRESHOLD,
    EVA_SCALE_MIN, EVA_SCALE_MAX, SENTINEL_FILES,
)

logger = logging.getLogger(__name__)


def find_aq_columns(columns):
    """Return column names that start with 'AQ' (case-sensitive)."""
    return [c for c in columns if c.startswith("AQ") and c != "geometry"]


def clean_sentinels(gdf):
    """Replace sentinel values (<= SENTINEL_THRESHOLD) with NaN in AQ columns.

    Returns a copy; does not modify the input.
    """
    gdf = gdf.copy()
    aq_cols = find_aq_columns(gdf.columns)
    for col in aq_cols:
        mask = gdf[col] <= SENTINEL_THRESHOLD
        count = mask.sum()
        if count > 0:
            gdf.loc[mask, col] = np.nan
            logger.info(
                "  %s: replaced %d sentinel values. "
                "New range: %.4f - %.4f (mean %.4f, %d null)",
                col, count,
                gdf[col].min(), gdf[col].max(), gdf[col].mean(),
                gdf[col].isna().sum(),
            )
    return gdf


def run():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for fname in SENTINEL_FILES:
        src = os.path.join(EVA_FINAL_DIR, fname)
        dst = os.path.join(OUTPUT_DIR, fname)
        logger.info("Processing %s", fname)
        gdf = gpd.read_file(src)
        gdf = clean_sentinels(gdf)
        # Validate
        for col in find_aq_columns(gdf.columns):
            valid = gdf[col].dropna()
            if len(valid) > 0:
                assert valid.min() >= EVA_SCALE_MIN, f"{col} has values below {EVA_SCALE_MIN}"
                assert valid.max() <= EVA_SCALE_MAX, f"{col} has values above {EVA_SCALE_MAX}"
        gdf.to_file(dst, driver="GPKG" if fname.endswith(".gpkg") else None)
        logger.info("  Written to %s (%d features)", dst, len(gdf))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_repair_scripts.py::TestCleanSentinels -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/s01_clean_sentinels.py tests/test_repair_scripts.py
git commit -m "feat: add sentinel cleanup script with tests"
```

---

### Task 3: Implement CRS standardization (02_standardize_crs.py)

**Files:**
- Modify: `tests/test_repair_scripts.py`
- Create: `scripts/s02_standardize_crs.py`

- [ ] **Step 1: Write failing tests**

```python
class TestStandardizeCrs:

    def test_reprojects_from_3035_to_3346(self):
        from scripts.s02_standardize_crs import standardize_crs
        gdf = gpd.GeoDataFrame(
            {"val": [1.0]},
            geometry=[Point(2332000, 7530000)],
            crs="EPSG:3035",
        )
        result = standardize_crs(gdf, "EPSG:3346")
        assert result.crs.to_epsg() == 3346
        assert len(result) == 1

    def test_already_correct_crs_unchanged(self):
        from scripts.s02_standardize_crs import standardize_crs
        gdf = gpd.GeoDataFrame(
            {"val": [1.0]},
            geometry=[Point(500000, 6100000)],
            crs="EPSG:3346",
        )
        result = standardize_crs(gdf, "EPSG:3346")
        assert result.crs.to_epsg() == 3346
        assert result.geometry.iloc[0].equals(gdf.geometry.iloc[0])

    def test_preserves_feature_count(self):
        from scripts.s02_standardize_crs import standardize_crs
        gdf = gpd.GeoDataFrame(
            {"val": [1.0, 2.0, 3.0]},
            geometry=[Point(2332000 + i * 100, 7530000) for i in range(3)],
            crs="EPSG:3035",
        )
        result = standardize_crs(gdf, "EPSG:3346")
        assert len(result) == 3
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement s02_standardize_crs.py**

```python
# scripts/s02_standardize_crs.py
"""Step 2: Reproject layers to TARGET_CRS."""
import logging
import os

import geopandas as gpd

from scripts.config import EVA_FINAL_DIR, OUTPUT_DIR, TARGET_CRS, CRS_FILES

logger = logging.getLogger(__name__)


def standardize_crs(gdf, target_crs):
    """Reproject GeoDataFrame to target CRS if needed. Returns a copy."""
    if gdf.crs is None:
        logger.warning("  No CRS defined — setting to %s", target_crs)
        return gdf.set_crs(target_crs)
    if str(gdf.crs) != target_crs and gdf.crs.to_epsg() != int(target_crs.split(":")[1]):
        original = str(gdf.crs)
        gdf = gdf.to_crs(target_crs)
        logger.info("  Reprojected from %s to %s", original, target_crs)
    return gdf


def run():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for fname in CRS_FILES:
        src = os.path.join(EVA_FINAL_DIR, fname)
        dst = os.path.join(OUTPUT_DIR, fname)
        logger.info("Processing %s", fname)
        gdf = gpd.read_file(src)
        original_count = len(gdf)
        gdf = standardize_crs(gdf, TARGET_CRS)
        assert len(gdf) == original_count, "Feature count changed during reprojection"
        gdf.to_file(dst, driver="GPKG")
        logger.info("  Written %d features to %s", len(gdf), dst)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_repair_scripts.py::TestStandardizeCrs -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/s02_standardize_crs.py tests/test_repair_scripts.py
git commit -m "feat: add CRS standardization script with tests"
```

---

### Task 4: Implement Subzone ID generation (03_add_subzone_ids.py)

**Files:**
- Modify: `tests/test_repair_scripts.py`
- Create: `scripts/s03_add_subzone_ids.py`

- [ ] **Step 1: Write failing tests**

```python
class TestAddSubzoneIds:

    def test_generates_from_row_col(self):
        from scripts.s03_add_subzone_ids import generate_subzone_ids
        gdf = _make_geo_df({"row_index": [12, 28, 30], "col_index": [17, 21, 20]})
        result = generate_subzone_ids(gdf)
        assert result["Subzone_ID"].tolist() == ["R012_C017", "R028_C021", "R030_C020"]

    def test_generates_from_fid(self):
        from scripts.s03_add_subzone_ids import generate_subzone_ids
        gdf = _make_geo_df({"fid": [1, 42, 999]})
        result = generate_subzone_ids(gdf)
        assert result["Subzone_ID"].tolist() == ["F000001", "F000042", "F000999"]

    def test_fallback_to_index(self):
        from scripts.s03_add_subzone_ids import generate_subzone_ids
        gdf = _make_geo_df({"value": [1.0, 2.0]})
        result = generate_subzone_ids(gdf)
        assert result["Subzone_ID"].tolist() == ["I000000", "I000001"]

    def test_no_duplicates(self):
        from scripts.s03_add_subzone_ids import generate_subzone_ids
        gdf = _make_geo_df({"row_index": [1, 2, 3, 4, 5], "col_index": [1, 1, 2, 2, 3]})
        result = generate_subzone_ids(gdf)
        assert result["Subzone_ID"].nunique() == 5
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement s03_add_subzone_ids.py**

```python
# scripts/s03_add_subzone_ids.py
"""Step 3: Generate consistent Subzone_ID column across all layers."""
import logging
import os
import glob

import geopandas as gpd

from scripts.config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def generate_subzone_ids(gdf):
    """Add Subzone_ID column based on available columns. Returns a copy."""
    gdf = gdf.copy()
    if "row_index" in gdf.columns and "col_index" in gdf.columns:
        gdf["Subzone_ID"] = [
            f"R{int(r):03d}_C{int(c):03d}"
            for r, c in zip(gdf["row_index"], gdf["col_index"])
        ]
        method = "row_index/col_index"
    elif "fid" in gdf.columns:
        gdf["Subzone_ID"] = [f"F{int(f):06d}" for f in gdf["fid"]]
        method = "fid"
    else:
        gdf["Subzone_ID"] = [f"I{i:06d}" for i in range(len(gdf))]
        method = "integer index (fallback)"
        logger.warning("  No row_index/col_index or fid — using integer index")
    logger.info("  Generated %d IDs using %s", gdf["Subzone_ID"].nunique(), method)
    return gdf


def run():
    """Add Subzone_ID to all files in OUTPUT_DIR."""
    patterns = [os.path.join(OUTPUT_DIR, "*.gpkg"), os.path.join(OUTPUT_DIR, "*.shp")]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    for fpath in sorted(files):
        fname = os.path.basename(fpath)
        logger.info("Processing %s", fname)
        gdf = gpd.read_file(fpath)
        if "Subzone_ID" in gdf.columns:
            logger.info("  Subzone_ID already exists — skipping")
            continue
        gdf = generate_subzone_ids(gdf)
        driver = "GPKG" if fpath.endswith(".gpkg") else None
        gdf.to_file(fpath, driver=driver)
        logger.info("  Updated %s (%d features, %d unique IDs)",
                     fname, len(gdf), gdf["Subzone_ID"].nunique())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_repair_scripts.py::TestAddSubzoneIds -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/s03_add_subzone_ids.py tests/test_repair_scripts.py
git commit -m "feat: add Subzone ID generation script with tests"
```

---

### Task 5: Implement Total EV recomputation (04_recompute_total_ev.py)

**Files:**
- Modify: `tests/test_repair_scripts.py`
- Create: `scripts/s04_recompute_total_ev.py`

- [ ] **Step 1: Write failing tests**

```python
class TestRecomputeTotalEv:

    def test_max_aggregation(self):
        from scripts.s04_recompute_total_ev import compute_total_ev
        gdf = _make_geo_df({
            "AQ7_HABITATS": [1.0, 3.0, 2.0],
            "ZooScore": [2.0, 1.0, 4.0],
            "PhytoScore": [3.0, 2.0, 1.0],
            "MaxBenthos": [0.5, 5.0, 3.0],
            "EVA_all_fish": [np.nan, np.nan, 2.0],
        })
        result = compute_total_ev(gdf)
        assert result["TotalEV_MAX"].iloc[0] == pytest.approx(3.0)  # max(1,2,3,0.5,nan)
        assert result["TotalEV_MAX"].iloc[1] == pytest.approx(5.0)  # max(3,1,2,5,nan)
        assert result["TotalEV_MAX"].iloc[2] == pytest.approx(4.0)  # max(2,4,1,3,2)

    def test_all_nan_gives_nan(self):
        from scripts.s04_recompute_total_ev import compute_total_ev
        gdf = _make_geo_df({
            "AQ7_HABITATS": [np.nan],
            "ZooScore": [np.nan],
            "PhytoScore": [np.nan],
            "MaxBenthos": [np.nan],
            "EVA_all_fish": [np.nan],
        })
        result = compute_total_ev(gdf)
        assert pd.isna(result["TotalEV_MAX"].iloc[0])
        assert pd.isna(result["TotalEV_MEAN"].iloc[0])
        assert result["EC_count"].iloc[0] == 0
        assert result["Dominant_EC"].iloc[0] is None

    def test_dominant_ec_identified(self):
        from scripts.s04_recompute_total_ev import compute_total_ev
        gdf = _make_geo_df({
            "AQ7_HABITATS": [1.0],
            "ZooScore": [4.0],
            "PhytoScore": [2.0],
            "MaxBenthos": [3.0],
            "EVA_all_fish": [np.nan],
        })
        result = compute_total_ev(gdf)
        assert result["Dominant_EC"].iloc[0] == "Zooplankton"

    def test_ec_count(self):
        from scripts.s04_recompute_total_ev import compute_total_ev
        gdf = _make_geo_df({
            "AQ7_HABITATS": [1.0],
            "ZooScore": [np.nan],
            "PhytoScore": [2.0],
            "MaxBenthos": [np.nan],
            "EVA_all_fish": [np.nan],
        })
        result = compute_total_ev(gdf)
        assert result["EC_count"].iloc[0] == 2

    def test_max_gte_mean(self):
        from scripts.s04_recompute_total_ev import compute_total_ev
        gdf = _make_geo_df({
            "AQ7_HABITATS": [1.0, 2.0, 3.0],
            "ZooScore": [3.0, 1.0, 2.0],
            "PhytoScore": [2.0, 3.0, 1.0],
            "MaxBenthos": [4.0, 0.5, 5.0],
            "EVA_all_fish": [np.nan, 2.0, np.nan],
        })
        result = compute_total_ev(gdf)
        for i in range(len(result)):
            if pd.notna(result["TotalEV_MAX"].iloc[i]):
                assert result["TotalEV_MAX"].iloc[i] >= result["TotalEV_MEAN"].iloc[i]

    def test_verify_benthos_max(self):
        from scripts.s04_recompute_total_ev import verify_benthos_max
        gdf = _make_geo_df({
            "MaxBenthos": [3.0, 5.0],
            "AQ6_benthos": [1.0, 5.0],
            "AQ9_benthos": [3.0, 2.0],
            "AQ13_benthos": [2.0, 4.0],
        })
        issues = verify_benthos_max(gdf)
        assert len(issues) == 0  # max(1,3,2)=3 ✓, max(5,2,4)=5 ✓

    def test_verify_benthos_max_detects_mean(self):
        from scripts.s04_recompute_total_ev import verify_benthos_max
        gdf = _make_geo_df({
            "MaxBenthos": [2.0],  # mean(1,3,2)=2, but max should be 3
            "AQ6_benthos": [1.0],
            "AQ9_benthos": [3.0],
            "AQ13_benthos": [2.0],
        })
        issues = verify_benthos_max(gdf)
        assert len(issues) > 0
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement s04_recompute_total_ev.py**

```python
# scripts/s04_recompute_total_ev.py
"""Step 4: Recompute Total EV using MAX aggregation."""
import logging
import os

import geopandas as gpd
import numpy as np
import pandas as pd

from scripts.config import (
    OUTPUT_DIR, COMBINED_LAYER, EC_SCORE_COLUMNS,
    BENTHOS_AQ_COLUMNS, EVA_SCALE_MAX,
    EVA_CLASS_BINS, EVA_CLASS_LABELS,
)

logger = logging.getLogger(__name__)

EC_COL_TO_NAME = {v: k for k, v in EC_SCORE_COLUMNS.items()}


def verify_benthos_max(gdf):
    """Check that MaxBenthos == max(AQ6, AQ9, AQ13). Return list of issue descriptions."""
    issues = []
    aq_cols = [c for c in BENTHOS_AQ_COLUMNS if c in gdf.columns]
    if "MaxBenthos" not in gdf.columns or not aq_cols:
        return issues
    expected_max = gdf[aq_cols].max(axis=1, skipna=True)
    actual = gdf["MaxBenthos"]
    # Compare where both are non-null
    mask = actual.notna() & expected_max.notna()
    diff = (actual[mask] - expected_max[mask]).abs()
    bad = diff[diff > 0.01]
    if len(bad) > 0:
        issues.append(
            f"MaxBenthos != max({', '.join(aq_cols)}) in {len(bad)} rows "
            f"(max diff: {bad.max():.4f}). Will recompute."
        )
    return issues


def compute_total_ev(gdf):
    """Compute TotalEV_MAX, TotalEV_MEAN, EC_count, Dominant_EC. Returns a copy."""
    gdf = gdf.copy()
    ec_cols = [c for c in EC_SCORE_COLUMNS.values() if c in gdf.columns]
    ec_df = gdf[ec_cols].copy()

    gdf["TotalEV_MAX"] = ec_df.max(axis=1, skipna=True)
    gdf["TotalEV_MEAN"] = ec_df.mean(axis=1, skipna=True)
    gdf["EC_count"] = ec_df.notna().sum(axis=1)

    # Dominant EC
    dominant = []
    for idx in range(len(ec_df)):
        row = ec_df.iloc[idx]
        non_null = row.dropna()
        if len(non_null) == 0:
            dominant.append(None)
        else:
            max_col = non_null.idxmax()
            dominant.append(EC_COL_TO_NAME.get(max_col, max_col))
    gdf["Dominant_EC"] = dominant

    return gdf


def run():
    src = os.path.join(OUTPUT_DIR, COMBINED_LAYER)
    logger.info("Reading %s", src)
    gdf = gpd.read_file(src)

    # Verify benthos MAX
    issues = verify_benthos_max(gdf)
    for issue in issues:
        logger.warning(issue)
    if issues:
        aq_cols = [c for c in BENTHOS_AQ_COLUMNS if c in gdf.columns]
        gdf["MaxBenthos"] = gdf[aq_cols].max(axis=1, skipna=True)
        logger.info("  Recomputed MaxBenthos from individual AQ columns")

    # Compute Total EV
    gdf = compute_total_ev(gdf)

    # Log statistics
    ev = gdf["TotalEV_MAX"].dropna()
    logger.info("TotalEV_MAX: min=%.2f, max=%.2f, mean=%.2f, null=%d",
                ev.min(), ev.max(), ev.mean(), gdf["TotalEV_MAX"].isna().sum())
    bins = pd.cut(ev, bins=EVA_CLASS_BINS, labels=EVA_CLASS_LABELS, include_lowest=True)
    logger.info("5-class distribution:\n%s", bins.value_counts().sort_index().to_string())

    # Dominant EC distribution
    logger.info("Dominant EC:\n%s", gdf["Dominant_EC"].value_counts().to_string())

    gdf.to_file(src, driver="GPKG")
    logger.info("Updated %s", src)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_repair_scripts.py::TestRecomputeTotalEv -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/s04_recompute_total_ev.py tests/test_repair_scripts.py
git commit -m "feat: add Total EV MAX recomputation script with tests"
```

---

### Task 6: Implement confidence index (05_compute_confidence.py)

**Files:**
- Modify: `tests/test_repair_scripts.py`
- Create: `scripts/s05_compute_confidence.py`

- [ ] **Step 1: Write failing tests**

```python
class TestComputeConfidence:

    def test_benthos_confidence(self):
        from scripts.s05_compute_confidence import compute_ec_confidence
        # 4 AQs answered, N=8, wi=3 → (4*3)/8 = 1.5
        result = compute_ec_confidence(n_answered=4, n_max=8, weight=3)
        assert result == pytest.approx(1.5)

    def test_habitats_confidence(self):
        from scripts.s05_compute_confidence import compute_ec_confidence
        # 1 AQ answered, N=7, wi=3 → (1*3)/7 ≈ 0.43
        result = compute_ec_confidence(n_answered=1, n_max=7, weight=3)
        assert result == pytest.approx(3 / 7)

    def test_max_confidence(self):
        from scripts.s05_compute_confidence import compute_ec_confidence
        # All 7 AQs answered with wi=5 → (7*5)/7 = 5.0
        result = compute_ec_confidence(n_answered=7, n_max=7, weight=5)
        assert result == pytest.approx(5.0)

    def test_zero_aqs_gives_zero(self):
        from scripts.s05_compute_confidence import compute_ec_confidence
        result = compute_ec_confidence(n_answered=0, n_max=7, weight=3)
        assert result == pytest.approx(0.0)

    def test_missing_dominant_ec_gives_nan(self):
        from scripts.s05_compute_confidence import assign_confidence
        gdf = _make_geo_df({
            "AQ7_HABITATS": [np.nan],
            "ZooScore": [np.nan],
            "PhytoScore": [np.nan],
            "MaxBenthos": [np.nan],
            "EVA_all_fish": [np.nan],
            "Dominant_EC": [None],
        })
        result = assign_confidence(gdf)
        assert pd.isna(result["Confidence"].iloc[0])

    def test_classify_low(self):
        from scripts.s05_compute_confidence import classify_confidence
        assert classify_confidence(0.30) == "Low"
        assert classify_confidence(1.67) == "Low"

    def test_classify_medium(self):
        from scripts.s05_compute_confidence import classify_confidence
        assert classify_confidence(1.68) == "Medium"
        assert classify_confidence(3.33) == "Medium"

    def test_classify_high(self):
        from scripts.s05_compute_confidence import classify_confidence
        assert classify_confidence(3.34) == "High"
        assert classify_confidence(5.0) == "High"

    def test_assign_confidence_to_gdf(self):
        from scripts.s05_compute_confidence import assign_confidence
        gdf = _make_geo_df({
            "AQ7_HABITATS": [1.0, np.nan],
            "ZooScore": [np.nan, 3.0],
            "PhytoScore": [np.nan, np.nan],
            "MaxBenthos": [np.nan, np.nan],
            "EVA_all_fish": [np.nan, np.nan],
            "Dominant_EC": ["Habitats", "Zooplankton"],
        })
        result = assign_confidence(gdf)
        assert "Confidence" in result.columns
        assert "Confidence_Class" in result.columns
        assert result["Confidence_Class"].iloc[0] == "Low"  # Habitats: (1*3)/7=0.43
        assert result["Confidence_Class"].iloc[1] == "Low"  # Zoo: (1*2)/7=0.29
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement s05_compute_confidence.py**

```python
# scripts/s05_compute_confidence.py
"""Step 5: Compute confidence index per EC per subzone."""
import logging
import os

import geopandas as gpd
import numpy as np

from scripts.config import OUTPUT_DIR, COMBINED_LAYER, EC_CONFIDENCE, EC_SCORE_COLUMNS

logger = logging.getLogger(__name__)


def compute_ec_confidence(n_answered, n_max, weight):
    """Confidence = sum(AQi * wi) / N. Result range: 0-5."""
    if n_max == 0:
        return 0.0
    return (n_answered * weight) / n_max


def classify_confidence(score):
    """Classify confidence score into Low/Medium/High."""
    if score <= 1.67:
        return "Low"
    elif score <= 3.33:
        return "Medium"
    else:
        return "High"


def assign_confidence(gdf):
    """Add per-subzone confidence based on dominant EC. Returns a copy."""
    gdf = gdf.copy()

    # Pre-compute confidence per EC
    ec_conf = {}
    for ec_name, (n_ans, n_max, wi) in EC_CONFIDENCE.items():
        ec_conf[ec_name] = compute_ec_confidence(n_ans, n_max, wi)

    # Assign based on Dominant_EC
    confidences = []
    for _, row in gdf.iterrows():
        dom = row.get("Dominant_EC")
        if dom and dom in ec_conf:
            confidences.append(ec_conf[dom])
        else:
            confidences.append(np.nan)

    gdf["Confidence"] = confidences
    gdf["Confidence_Class"] = [
        classify_confidence(c) if not np.isnan(c) else None
        for c in confidences
    ]
    return gdf


def run():
    src = os.path.join(OUTPUT_DIR, COMBINED_LAYER)
    logger.info("Reading %s", src)
    gdf = gpd.read_file(src)

    if "Dominant_EC" not in gdf.columns:
        logger.error("Dominant_EC column missing — run 04_recompute_total_ev.py first")
        return

    gdf = assign_confidence(gdf)

    # Log distribution
    logger.info("Confidence distribution:\n%s",
                gdf["Confidence_Class"].value_counts().to_string())
    logger.info("Per-EC confidence values:")
    for ec_name, (n_ans, n_max, wi) in EC_CONFIDENCE.items():
        logger.info("  %s: %.4f (%s)", ec_name,
                     compute_ec_confidence(n_ans, n_max, wi),
                     classify_confidence(compute_ec_confidence(n_ans, n_max, wi)))

    gdf.to_file(src, driver="GPKG")
    logger.info("Updated %s", src)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_repair_scripts.py::TestComputeConfidence -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/s05_compute_confidence.py tests/test_repair_scripts.py
git commit -m "feat: add confidence index computation script with tests"
```

---

### Task 7: Implement validation and report (06_validate_and_report.py)

**Files:**
- Modify: `tests/test_repair_scripts.py`
- Create: `scripts/s06_validate_and_report.py`

- [ ] **Step 1: Write failing tests**

```python
class TestValidation:

    def test_check_no_sentinels_pass(self):
        from scripts.s06_validate_and_report import check_no_sentinels
        gdf = _make_geo_df({"AQ13": [1.0, np.nan, 3.0]})
        assert check_no_sentinels(gdf) is True

    def test_check_no_sentinels_fail(self):
        from scripts.s06_validate_and_report import check_no_sentinels
        gdf = _make_geo_df({"AQ13": [1.0, -9999.0, 3.0]})
        assert check_no_sentinels(gdf) is False

    def test_check_aq_range_pass(self):
        from scripts.s06_validate_and_report import check_aq_range
        gdf = _make_geo_df({"AQ6": [0.0, 2.5, 5.0], "AQ9": [np.nan, 1.0, 4.0]})
        assert check_aq_range(gdf) is True

    def test_check_aq_range_fail(self):
        from scripts.s06_validate_and_report import check_aq_range
        gdf = _make_geo_df({"AQ6": [0.0, 6.0, 5.0]})
        assert check_aq_range(gdf) is False

    def test_check_crs(self):
        from scripts.s06_validate_and_report import check_crs
        gdf = _make_geo_df({"val": [1.0]})  # created with EPSG:3346
        assert check_crs(gdf, "EPSG:3346") is True

    def test_check_has_subzone_id(self):
        from scripts.s06_validate_and_report import check_has_subzone_id
        gdf = _make_geo_df({"Subzone_ID": ["R001_C001"], "val": [1.0]})
        assert check_has_subzone_id(gdf) is True
        gdf2 = _make_geo_df({"val": [1.0]})
        assert check_has_subzone_id(gdf2) is False

    def test_check_total_ev_correct(self):
        from scripts.s06_validate_and_report import check_total_ev
        gdf = _make_geo_df({
            "AQ7_HABITATS": [1.0], "ZooScore": [3.0],
            "PhytoScore": [2.0], "MaxBenthos": [4.0],
            "EVA_all_fish": [np.nan], "TotalEV_MAX": [4.0],
        })
        assert check_total_ev(gdf) is True

    def test_check_total_ev_wrong(self):
        from scripts.s06_validate_and_report import check_total_ev
        gdf = _make_geo_df({
            "AQ7_HABITATS": [1.0], "ZooScore": [3.0],
            "PhytoScore": [2.0], "MaxBenthos": [4.0],
            "EVA_all_fish": [np.nan], "TotalEV_MAX": [2.5],  # wrong: should be 4.0
        })
        assert check_total_ev(gdf) is False

    def test_check_confidence_present(self):
        from scripts.s06_validate_and_report import check_confidence_present
        gdf = _make_geo_df({"Confidence": [1.5], "Confidence_Class": ["Low"]})
        assert check_confidence_present(gdf) is True
        gdf2 = _make_geo_df({"val": [1.0]})
        assert check_confidence_present(gdf2) is False
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement s06_validate_and_report.py**

```python
# scripts/s06_validate_and_report.py
"""Step 6: Run quality checks and produce validation report."""
import logging
import os
import glob
from datetime import datetime

import geopandas as gpd
import numpy as np
import pandas as pd

from scripts.config import (
    OUTPUT_DIR, TARGET_CRS, SENTINEL_THRESHOLD,
    EVA_SCALE_MIN, EVA_SCALE_MAX,
    EVA_CLASS_BINS, EVA_CLASS_LABELS,
)
from scripts.s01_clean_sentinels import find_aq_columns

logger = logging.getLogger(__name__)


def check_no_sentinels(gdf):
    for col in find_aq_columns(gdf.columns):
        vals = gdf[col].dropna()
        if (vals <= SENTINEL_THRESHOLD).any():
            return False
    return True


def check_aq_range(gdf):
    for col in find_aq_columns(gdf.columns):
        vals = gdf[col].dropna()
        if len(vals) > 0 and (vals.min() < EVA_SCALE_MIN or vals.max() > EVA_SCALE_MAX):
            return False
    return True


def check_crs(gdf, target_crs):
    if gdf.crs is None:
        return False
    target_epsg = int(target_crs.split(":")[1])
    return gdf.crs.to_epsg() == target_epsg


def check_has_subzone_id(gdf):
    return "Subzone_ID" in gdf.columns


def check_total_ev(gdf):
    """Verify TotalEV_MAX == max of EC score columns."""
    if "TotalEV_MAX" not in gdf.columns:
        return False
    from scripts.config import EC_SCORE_COLUMNS
    ec_cols = [c for c in EC_SCORE_COLUMNS.values() if c in gdf.columns]
    if not ec_cols:
        return True
    expected = gdf[ec_cols].max(axis=1, skipna=True)
    mask = gdf["TotalEV_MAX"].notna() & expected.notna()
    diff = (gdf.loc[mask, "TotalEV_MAX"] - expected[mask]).abs()
    return (diff < 0.01).all()


def check_confidence_present(gdf):
    return "Confidence" in gdf.columns and "Confidence_Class" in gdf.columns


def run():
    report_lines = [
        f"# EVA_FINAL Validation Report",
        f"",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Source:** `{OUTPUT_DIR}`",
        f"",
        f"## Check Results",
        f"",
        f"| File | Features | CRS | No Sentinels | AQ Range [0,5] | Subzone_ID |",
        f"|------|----------|-----|-------------|----------------|------------|",
    ]

    patterns = [os.path.join(OUTPUT_DIR, "*.gpkg"), os.path.join(OUTPUT_DIR, "*.shp")]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat))

    all_pass = True
    for fpath in sorted(files):
        fname = os.path.basename(fpath)
        try:
            gdf = gpd.read_file(fpath)
        except Exception as e:
            report_lines.append(f"| {fname} | ERROR | {e} | - | - | - |")
            all_pass = False
            continue

        crs_ok = check_crs(gdf, TARGET_CRS)
        sent_ok = check_no_sentinels(gdf)
        range_ok = check_aq_range(gdf)
        id_ok = check_has_subzone_id(gdf)

        p = lambda ok: "PASS" if ok else "**FAIL**"
        crs_str = f"EPSG:{gdf.crs.to_epsg()}" if gdf.crs else "None"

        report_lines.append(
            f"| {fname} | {len(gdf)} | {crs_str} {p(crs_ok)} | "
            f"{p(sent_ok)} | {p(range_ok)} | {p(id_ok)} |"
        )
        if not (crs_ok and sent_ok and range_ok):
            all_pass = False

    # Total EV section
    combined = os.path.join(OUTPUT_DIR, "ALL4EVA_2025_fixed_geometries.gpkg")
    if os.path.exists(combined):
        gdf = gpd.read_file(combined)
        report_lines.extend(["", "## Total EV Distribution", ""])
        if "TotalEV_MAX" in gdf.columns:
            ev = gdf["TotalEV_MAX"].dropna()
            report_lines.append(f"- Range: {ev.min():.2f} - {ev.max():.2f}")
            report_lines.append(f"- Mean: {ev.mean():.2f}")
            report_lines.append(f"- Null: {gdf['TotalEV_MAX'].isna().sum()}")
            bins = pd.cut(ev, bins=EVA_CLASS_BINS, labels=EVA_CLASS_LABELS,
                         include_lowest=True)
            report_lines.append(f"")
            report_lines.append(f"| Class | Count | % |")
            report_lines.append(f"|-------|-------|---|")
            for label in EVA_CLASS_LABELS:
                count = (bins == label).sum()
                pct = count / len(ev) * 100
                report_lines.append(f"| {label} | {count} | {pct:.1f}% |")

        if "Dominant_EC" in gdf.columns:
            report_lines.extend(["", "## Dominant EC Distribution", ""])
            report_lines.append(f"| EC | Count | % |")
            report_lines.append(f"|-----|-------|---|")
            for ec, count in gdf["Dominant_EC"].value_counts().items():
                pct = count / len(gdf) * 100
                report_lines.append(f"| {ec} | {count} | {pct:.1f}% |")

        if "Confidence_Class" in gdf.columns:
            report_lines.extend(["", "## Confidence Distribution", ""])
            report_lines.append(f"| Class | Count | % |")
            report_lines.append(f"|-------|-------|---|")
            for cls in ["Low", "Medium", "High"]:
                count = (gdf["Confidence_Class"] == cls).sum()
                pct = count / len(gdf) * 100
                report_lines.append(f"| {cls} | {count} | {pct:.1f}% |")

    # Summary
    status = "ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED"
    report_lines.extend(["", f"## Summary: {status}", ""])

    report_text = "\n".join(report_lines)
    report_path = os.path.join(OUTPUT_DIR, "validation_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info("Report written to %s", report_path)
    print(report_text)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `conda run -n shiny python -m pytest tests/test_repair_scripts.py::TestValidation -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/s06_validate_and_report.py tests/test_repair_scripts.py
git commit -m "feat: add validation and report generation script with tests"
```

---

### Task 8: Implement master runner (run_all.py)

**Files:**
- Create: `scripts/run_all.py`

- [ ] **Step 1: Write run_all.py**

```python
# scripts/run_all.py
"""Master script: run all data repair steps in sequence."""
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

STEPS = [
    ("01 — Clean sentinels",       "scripts.s01_clean_sentinels"),
    ("02 — Standardize CRS",       "scripts.s02_standardize_crs"),
    ("03 — Add Subzone IDs",       "scripts.s03_add_subzone_ids"),
    ("04 — Recompute Total EV",    "scripts.s04_recompute_total_ev"),
    ("05 — Compute confidence",    "scripts.s05_compute_confidence"),
    ("06 — Validate and report",   "scripts.s06_validate_and_report"),
]


def main():
    start = time.time()
    logger.info("=" * 60)
    logger.info("  EVA_FINAL Data Repair Pipeline")
    logger.info("=" * 60)

    for label, module_name in STEPS:
        logger.info("")
        logger.info("--- %s ---", label)
        step_start = time.time()
        try:
            import importlib
            mod = importlib.import_module(module_name)
            mod.run()
            elapsed = time.time() - step_start
            logger.info("  Completed in %.1fs", elapsed)
        except Exception as e:
            logger.error("  FAILED: %s", e)
            logger.error("  Pipeline stopped. Fix the issue and re-run.")
            sys.exit(1)

    total = time.time() - start
    logger.info("")
    logger.info("=" * 60)
    logger.info("  Pipeline complete in %.1fs", total)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite to verify all tests pass**

Run: `conda run -n shiny python -m pytest tests/test_repair_scripts.py -v`
Expected: All tests pass (4+3+4+7+7+6 = ~31 tests)

- [ ] **Step 3: Commit**

```bash
git add scripts/run_all.py
git commit -m "feat: add master pipeline runner"
```

---

### Task 9: Run the pipeline on real data

- [ ] **Step 1: Execute the full pipeline**

Run: `conda run -n shiny python scripts/run_all.py`

Expected: All 6 steps complete without error. Outputs written to `EVA_FINAL_corrected/`.

- [ ] **Step 2: Review the validation report**

Read: `EVA_FINAL_corrected/validation_report.md`

All checks should show PASS. Review the Total EV distribution and confidence breakdown.

- [ ] **Step 3: Spot-check a corrected file**

Run a quick Python check: read the corrected combined layer, verify AQ13 has no -9999, TotalEV_MAX is present, Confidence_Class is present.

- [ ] **Step 4: Commit the pipeline and bump version**

In `version.py`: bump `VERSION_PATCH` to 1 (→ 3.2.1).

```bash
git add scripts/ tests/test_repair_scripts.py version.py
git commit -m "feat: complete EVA_FINAL data repair pipeline (v3.2.1)"
```
