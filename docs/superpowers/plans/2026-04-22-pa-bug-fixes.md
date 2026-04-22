# Physical Accounts Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix seven concrete bugs in the Physical Accounts (PA) module surfaced by the 2026-04-22 code review: broken CRS string parsing, missing defensive guards, custom habitat name loss in exports, pct rounding drift, missing BBT8 schema validation, hardcoded BBT8 total-area argument, and silent supply-input validation.

**Architecture:** All fixes are localised to `pa_calculations.py`, `pa_export.py`, and the PA server section of `app.py` (~lines 2035-2373 and 2800-2870). No schema migrations. No UI changes. Each fix ships with a pytest test that demonstrates the bug before the fix and passes after. The deeper `"Subzone ID"` / `"Subzone_ID"` schema split is explicitly out of scope — it warrants its own plan.

**Tech Stack:** Python 3, pytest, geopandas, pyproj, pandas, openpyxl, Shiny for Python. Tests run under the `shiny` micromamba environment.

---

## File Structure

| File | Role | Touched by tasks |
|---|---|---|
| `pa_calculations.py` | Pure calc functions: extent, supply, validation | Tasks 1, 2, 3 |
| `pa_export.py` | Excel export: standalone/combined/BBT8 | Tasks 4, 5, 6 |
| `app.py` | Shiny server wiring for PA tab and BBT8 download | Tasks 1, 3, 7, 8 |
| `tests/test_pa_calculations.py` | Unit tests for pure calc layer | Tasks 1, 2, 3 |
| `tests/test_pa_export.py` | Unit tests for export layer | Tasks 4, 5, 6 |

No new files are created. Task 8 (supply validation) is the only one that mutates Shiny-reactive code and is therefore tested by extracting a pure helper and unit-testing that.

**Test invocation (used throughout):**
```
micromamba run -n shiny pytest tests/<file> -v
```

---

## Task 1: Make `reproject_to_metric` robust to decorated CRS strings

**Bug:** `app.py:265, 761, 815` set `original_crs` to `"EPSG:4326 (WGS84)"`. `pa_calculations.reproject_to_metric` feeds this to `pyproj.CRS.from_user_input`, which rejects the parenthetical suffix. The `except Exception` at `pa_calculations.py:41` silently swallows the error and the user-supplied CRS path becomes dead code whenever a decorated string is used.

**Fix:** If full parsing fails, fall back to extracting `EPSG:\d+` via regex and using `pyproj.CRS.from_epsg`. Also fix the three decorated-string call sites in `app.py` to store the clean `"EPSG:4326"`.

**Files:**
- Modify: `pa_calculations.py` (add `re` import, extend `reproject_to_metric` fallback)
- Modify: `app.py:265, 761, 815` (drop `" (WGS84)"` suffix)
- Test: `tests/test_pa_calculations.py` (new test class)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pa_calculations.py`:

```python
# ---------------------------------------------------------------------------
# TestReprojectToMetric
# ---------------------------------------------------------------------------

from pa_calculations import reproject_to_metric


class TestReprojectToMetric:
    def test_decorated_epsg_string_is_parsed(self):
        """Decorated `"EPSG:#### (description)"` must be parsed, not silently dropped.

        Fixture choice: `_make_test_gdf` is centered in UTM zone 33N, so the
        UTM auto-detect fallback returns EPSG:32633. We deliberately pass a
        DECORATED string for EPSG:3035 (ETRS89-LAEA Europe) which pyproj
        cannot parse raw. Before the fix: parse fails → UTM auto-detect →
        32633. After the fix: regex extracts 3035 → from_epsg → 3035.
        """
        gdf = _make_test_gdf()  # WGS-84 GeoDataFrame, centroid in UTM 33N
        decorated = "EPSG:3035 (ETRS89 / LAEA Europe)"
        out = reproject_to_metric(gdf, original_crs=decorated)
        assert out.crs.to_epsg() == 3035, (
            f"Expected EPSG:3035 (regex-extracted from decorated string), "
            f"got {out.crs.to_epsg()} — likely UTM auto-detect fallback, "
            "meaning the decorated CRS string was silently dropped."
        )
```

- [ ] **Step 2: Run test to verify it fails**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py::TestReprojectToMetric::test_decorated_epsg_string_is_parsed -v
```

Expected: FAIL. Before the fix, pyproj raises `CRSError` on the decorated string, `reproject_to_metric` falls through to UTM auto-detect, and the centroid resolves to EPSG:32633. The test asserts 3035, so it fails. Verified manually: `python -c "import pyproj; pyproj.CRS.from_user_input('EPSG:3035 (ETRS89 / LAEA Europe)')"` raises `CRSError: Invalid projection`.

- [ ] **Step 3: Implement the regex fallback**

Edit `pa_calculations.py`. First, add `import re` — change line 8:
```python
import logging
```
to:
```python
import logging
import re
```

Then replace the body of `reproject_to_metric` lines 36-42 with:

```python
    if original_crs is not None:
        crs_obj = None
        try:
            crs_obj = pyproj.CRS.from_user_input(original_crs)
        except Exception:
            # Extract EPSG:#### from decorated strings like "EPSG:32633 (UTM zone 33N)"
            match = re.search(r"EPSG:(\d+)", str(original_crs))
            if match:
                try:
                    crs_obj = pyproj.CRS.from_epsg(int(match.group(1)))
                except Exception:
                    logger.warning(
                        "Could not parse original_crs=%r; falling back to auto-detect.",
                        original_crs,
                    )
            else:
                logger.warning(
                    "Could not parse original_crs=%r; falling back to auto-detect.",
                    original_crs,
                )
        if crs_obj is not None and crs_obj.is_projected:
            return gdf.to_crs(crs_obj)
```

- [ ] **Step 4: Run test to verify it passes**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py::TestReprojectToMetric -v
```

Expected: PASS.

- [ ] **Step 5: Clean up call sites in `app.py`**

Apply these three edits:

`app.py:265` — change from:
```python
                    original_crs.set("EPSG:4326 (WGS84)")
```
to:
```python
                    original_crs.set("EPSG:4326")
```

`app.py:761` — change from:
```python
        original_crs.set("EPSG:4326 (WGS84)")
```
to:
```python
        original_crs.set("EPSG:4326")
```

`app.py:815` — change from:
```python
        original_crs.set("EPSG:4326 (WGS84)")
```
to:
```python
        original_crs.set("EPSG:4326")
```

`app.py:873` — fourth CRS-setting call site. The `"Unknown (no CRS defined)"` sentinel string does not round-trip through `reproject_to_metric` meaningfully (it has no EPSG code for the regex to extract). Normalise to `None` so downstream code can check `is None` rather than pattern-match a sentinel. Change from:
```python
            original_crs.set("Unknown (no CRS defined)")
```
to:
```python
            original_crs.set(None)
```

Note: `reproject_to_metric`'s existing guard `if original_crs is not None:` at line 36 already handles `None` gracefully (falls through to UTM auto-detect), so no calc-side change is needed.

(The four edits at lines 265, 761, 815, 873 — the first three share an identical `old_string` and are best handled with `replace_all=True` restricted via context, or three separate edits using surrounding context to disambiguate. Line 873 is distinct.)

- [ ] **Step 6: Run the full PA test file to confirm no regressions**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py -v
```

Expected: PASS on all tests including existing ones.

- [ ] **Step 7: Commit**

```
git add pa_calculations.py app.py tests/test_pa_calculations.py
git commit -m "fix(pa): parse decorated EPSG strings in reproject_to_metric"
```

---

## Task 2: Add defensive guards to `compute_extent`

**Bug:** `pa_calculations.compute_extent` raises `KeyError` when `"Subzone ID"` column is missing, and raises a `pyproj.exceptions.CRSError` when `gdf.crs is None`. Both cases propagate uncaught to the UI.

**Fix:** Add explicit guards at the top of `compute_extent` that raise clean `ValueError`s with user-friendly messages. The Shiny UI catches these via its existing error-rendering path.

**Files:**
- Modify: `pa_calculations.py:63-118` (add guards at top of `compute_extent`)
- Test: `tests/test_pa_calculations.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pa_calculations.py` inside `class TestComputeExtent`:

```python
    def test_missing_subzone_id_column_raises(self):
        """GDF without 'Subzone ID' column should raise a clear ValueError."""
        gdf = gpd.GeoDataFrame(
            {"wrong_col": ["A", "B"], "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1)]},
            crs="EPSG:4326",
        )
        with pytest.raises(ValueError, match="Subzone ID"):
            compute_extent(gdf, {"A": "MB252"}, unit="Ha")

    def test_missing_crs_raises(self):
        """GDF with crs=None should raise a clear ValueError, not CRSError."""
        gdf = gpd.GeoDataFrame(
            {"Subzone ID": ["A"], "geometry": [box(0, 0, 1, 1)]},
            crs=None,
        )
        with pytest.raises(ValueError, match="CRS"):
            compute_extent(gdf, {"A": "MB252"}, unit="Ha")
```

- [ ] **Step 2: Run tests to verify they fail**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py::TestComputeExtent::test_missing_subzone_id_column_raises tests/test_pa_calculations.py::TestComputeExtent::test_missing_crs_raises -v
```

Expected: FAIL. First test will raise `KeyError: 'Subzone ID'`; second will raise `pyproj.exceptions.CRSError` or similar — neither is `ValueError`.

- [ ] **Step 3: Add guards to `compute_extent`**

Edit `pa_calculations.py` — replace the body between the docstring and the existing `if not habitat_assignments:` check (around line 87) with:

```python
    if "Subzone ID" not in gdf.columns:
        raise ValueError(
            "GeoDataFrame is missing required 'Subzone ID' column. "
            "Available columns: " + ", ".join(map(str, gdf.columns))
        )
    if gdf.crs is None:
        raise ValueError(
            "GeoDataFrame has no CRS defined. Please upload a spatial file "
            "with a defined coordinate reference system."
        )
    if not habitat_assignments:
        return pd.DataFrame(columns=["eunis_code", "habitat_name", "area", "pct_total"])
```

(The original `if not habitat_assignments:` block stays in place — just precede it with the two new guards.)

- [ ] **Step 4: Run tests to verify they pass**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py::TestComputeExtent -v
```

Expected: PASS on all `TestComputeExtent` tests.

- [ ] **Step 5: Commit**

```
git add pa_calculations.py tests/test_pa_calculations.py
git commit -m "fix(pa): add defensive guards for missing column and CRS in compute_extent"
```

---

## Task 3: Thread custom habitats through `compute_extent`

**Bug:** `pa_calculations.compute_extent` resolves habitat names via `EUNIS_LOOKUP.map(...).fillna("Unknown")` (line 116). User-defined habitats (stored in `pa_custom_habitats` reactive — never mutated into `EUNIS_LOOKUP` per `app.py:2280-2281`) therefore appear as `"Unknown"` in both the UI table and every exported workbook.

**Fix:** Add an optional `custom_lookup: dict | None` parameter to `compute_extent` and merge it with `EUNIS_LOOKUP` before name resolution. Update the four call sites in `app.py` to pass the current custom-habitats mapping.

**Files:**
- Modify: `pa_calculations.py:63-118` (extend `compute_extent` signature)
- Modify: `app.py:2151, 2174, 2308, 2338` (four PA call sites)
- Test: `tests/test_pa_calculations.py`

- [ ] **Step 1: Write the failing test**

Append to `class TestComputeExtent`:

```python
    def test_custom_lookup_overrides_unknown(self):
        """Custom EUNIS codes not in EUNIS_LOOKUP must be named via custom_lookup."""
        gdf = _make_test_gdf()
        assignments = {"Z1": "X99", "Z2": "X99", "Z3": "MC352"}
        custom_lookup = {"X99": "Custom reef mosaic"}
        result = compute_extent(
            gdf, assignments, unit="Ha", custom_lookup=custom_lookup
        )
        x99_name = result.loc[result["eunis_code"] == "X99", "habitat_name"].iloc[0]
        assert x99_name == "Custom reef mosaic", (
            f"Expected custom name, got {x99_name!r}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py::TestComputeExtent::test_custom_lookup_overrides_unknown -v
```

Expected: FAIL with `TypeError: compute_extent() got an unexpected keyword argument 'custom_lookup'`.

- [ ] **Step 3: Extend `compute_extent` signature and body**

Edit `pa_calculations.py` — change the signature from:
```python
def compute_extent(
    gdf: gpd.GeoDataFrame,
    habitat_assignments: dict,
    unit: str = "Ha",
    original_crs=None,
) -> pd.DataFrame:
```
to:
```python
def compute_extent(
    gdf: gpd.GeoDataFrame,
    habitat_assignments: dict,
    unit: str = "Ha",
    original_crs=None,
    custom_lookup: dict | None = None,
) -> pd.DataFrame:
```

Then replace line 116:
```python
    agg["habitat_name"] = agg["eunis_code"].map(EUNIS_LOOKUP).fillna("Unknown")
```
with:
```python
    merged_lookup = dict(EUNIS_LOOKUP)
    if custom_lookup:
        merged_lookup.update(custom_lookup)
    agg["habitat_name"] = agg["eunis_code"].map(merged_lookup).fillna("Unknown")
```

- [ ] **Step 4: Run test to verify it passes**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py::TestComputeExtent::test_custom_lookup_overrides_unknown -v
```

Expected: PASS.

- [ ] **Step 5: Add a helper and thread the lookup through the four `app.py` call sites**

Edit `app.py`. Locate the `_lookup_habitat_name` helper at line 2043-2048 and add directly after it:

```python
    def _pa_custom_lookup():
        """Return {code: name} for all custom habitats currently defined."""
        return {h["code"]: h["name"] for h in pa_custom_habitats.get()}
```

Then update four call sites to pass `custom_lookup=_pa_custom_lookup()`:

`app.py:2151` — change from:
```python
        extent_df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs)
```
to:
```python
        extent_df = pa_calculations.compute_extent(
            gdf, assignments, unit=unit, original_crs=crs,
            custom_lookup=_pa_custom_lookup(),
        )
```

`app.py:2174` — change from:
```python
        df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs)
```
to:
```python
        df = pa_calculations.compute_extent(
            gdf, assignments, unit=unit, original_crs=crs,
            custom_lookup=_pa_custom_lookup(),
        )
```

`app.py:2308` — change from:
```python
        extent_df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs) if gdf is not None and assignments else pd.DataFrame()
```
to:
```python
        extent_df = pa_calculations.compute_extent(
            gdf, assignments, unit=unit, original_crs=crs,
            custom_lookup=_pa_custom_lookup(),
        ) if gdf is not None and assignments else pd.DataFrame()
```

`app.py:2338` — change from:
```python
        extent_df = pa_calculations.compute_extent(gdf, assignments, unit=unit, original_crs=crs) if gdf is not None and assignments else pd.DataFrame()
```
to:
```python
        extent_df = pa_calculations.compute_extent(
            gdf, assignments, unit=unit, original_crs=crs,
            custom_lookup=_pa_custom_lookup(),
        ) if gdf is not None and assignments else pd.DataFrame()
```

Note to the engineer: the `app.py:2308` and `app.py:2338` lines are textually identical before the change. The Edit tool's uniqueness rule means you must either (a) use `replace_all` after confirming only these two lines match, or (b) include a few lines of surrounding context (e.g. the enclosing `def pa_download_standalone` vs. `def pa_download_combined` signature) to disambiguate. Both call sites must end up with the same post-edit form shown above.

- [ ] **Step 6: Run the full PA test file**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py -v
```

Expected: PASS on all tests.

- [ ] **Step 7: Commit**

```
git add pa_calculations.py app.py tests/test_pa_calculations.py
git commit -m "fix(pa): thread custom habitats through compute_extent"
```

---

## Task 4: Trust `habitat_name` column in `_build_extent_sheet`

**Bug:** `pa_export.py:138` overwrites the `habitat_name` that `compute_extent` emits by re-looking up the code in `EUNIS_LOOKUP`. After Task 3, `compute_extent` produces correct custom-habitat names — but the exporter still discards them.

**Fix:** If the DataFrame has a `habitat_name` column, use it verbatim. Fall back to `EUNIS_LOOKUP` otherwise (for legacy callers passing frames without that column).

**Files:**
- Modify: `pa_export.py:95-144` (`_build_extent_sheet`)
- Test: `tests/test_pa_export.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pa_export.py` (if file imports differ, mirror existing import style from the top of that file):

```python
import openpyxl
import pandas as pd
from pa_export import _build_extent_sheet


class TestBuildExtentSheet:
    def test_custom_habitat_name_preserved(self):
        """Custom habitat names (not in EUNIS_LOOKUP) must survive export."""
        df = pd.DataFrame({
            "eunis_code":   ["X99"],
            "habitat_name": ["Custom reef mosaic"],
            "area":         [42.0],
            "pct_total":    [100.0],
        })
        wb = openpyxl.Workbook()
        ws = wb.active
        _build_extent_sheet(ws, df, unit="Ha")
        # Header row + one data row + TOTAL row
        data_row = list(ws.iter_rows(min_row=2, max_row=2, values_only=True))[0]
        # Columns: EUNIS Code, Habitat Name, Area (Ha), % of Total
        assert data_row[0] == "X99"
        assert data_row[1] == "Custom reef mosaic", (
            f"Expected custom name, got {data_row[1]!r}"
        )

    def test_empty_habitat_name_falls_back_to_lookup(self):
        """If habitat_name is empty/NaN for a real EUNIS code, fall back to lookup."""
        df = pd.DataFrame({
            "eunis_code":   ["MB252", "MB252"],
            "habitat_name": ["", None],  # both empty — CSV round-trip scenarios
            "area":         [10.0, 20.0],
            "pct_total":    [33.3, 66.7],
        })
        wb = openpyxl.Workbook()
        ws = wb.active
        _build_extent_sheet(ws, df, unit="Ha")
        rows = list(ws.iter_rows(min_row=2, max_row=3, values_only=True))
        # Both rows should show the real EUNIS_LOOKUP name, not empty string
        assert rows[0][1] == "Posidonia oceanica meadows", (
            f"Empty-string habitat_name should fall back to EUNIS_LOOKUP, got {rows[0][1]!r}"
        )
        assert rows[1][1] == "Posidonia oceanica meadows", (
            f"None habitat_name should fall back to EUNIS_LOOKUP, got {rows[1][1]!r}"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```
micromamba run -n shiny pytest tests/test_pa_export.py::TestBuildExtentSheet -v
```

Expected: FAIL on both. For `test_custom_habitat_name_preserved`, `data_row[1]` will be `""` (EUNIS_LOOKUP.get("X99", "") returns empty). For `test_empty_habitat_name_falls_back_to_lookup`, the current code already ignores `habitat_name` and uses `EUNIS_LOOKUP` — so it would accidentally pass. That means the empty-string test only meaningfully fails against the NAIVE fix (one that drops only NaN, not empty strings). This documents the stricter semantics we want.

- [ ] **Step 3: Prefer `habitat_name` column when present, with full NaN/empty guard**

Edit `pa_export.py` — replace line 138:
```python
        name = EUNIS_LOOKUP.get(code, "")
```
with:
```python
        if "habitat_name" in df.columns:
            name_raw = row["habitat_name"]
            if pd.isna(name_raw) or not str(name_raw).strip():
                name = EUNIS_LOOKUP.get(code, "")
            else:
                name = str(name_raw)
        else:
            name = EUNIS_LOOKUP.get(code, "")
```

(`pd.isna` handles `None`, `float NaN`, `pd.NA`, and `pd.NaT` uniformly. The `str(name_raw).strip()` check catches empty and whitespace-only strings from CSV round-trips. `pd` is already imported at `pa_export.py:14`.)

- [ ] **Step 4: Run both tests to verify they pass**

```
micromamba run -n shiny pytest tests/test_pa_export.py::TestBuildExtentSheet::test_custom_habitat_name_preserved tests/test_pa_export.py::TestBuildExtentSheet::test_empty_habitat_name_falls_back_to_lookup -v
```

Expected: PASS on both.

- [ ] **Step 5: Commit**

```
git add pa_export.py tests/test_pa_export.py
git commit -m "fix(pa): preserve custom habitat names and fall back on empty name"
```

---

## Task 5: Use `pct_total` from `compute_extent` instead of recomputing

**Bug:** `pa_export.py:140` recomputes `pct = area / total_area * 100` and rounds it to 2 decimals. `compute_extent` already emits `pct_total`. The UI (`app.py:2176`) rounds to 1 decimal. The exported value can drift from what the user sees, and the recompute itself risks rounding loops if `area_col` points at an already-rounded column.

**Fix:** Use `pct_total` from the DataFrame if present. Fall back to recomputation for legacy frames.

**Files:**
- Modify: `pa_export.py:127-144` (`_build_extent_sheet`)
- Test: `tests/test_pa_export.py`

- [ ] **Step 1: Write the failing test**

Append to `class TestBuildExtentSheet`:

```python
    def test_pct_total_from_dataframe_is_preserved(self):
        """If DataFrame carries pct_total, exporter must use it — not recompute.

        Fixture choice: areas 1.0 and 2.0 produce recomputed percentages of
        33.33 and 66.67. We deliberately set pct_total to 50.0 and 50.0 (an
        upstream override) so the test fails before the fix and passes after.
        """
        import pandas as pd
        df = pd.DataFrame({
            "eunis_code":   ["A",   "B"],
            "habitat_name": ["Alpha", "Beta"],
            "area":         [1.0,   2.0],
            "pct_total":    [50.0,  50.0],  # override, NOT matching area ratio
        })
        wb = openpyxl.Workbook()
        ws = wb.active
        _build_extent_sheet(ws, df, unit="Ha")
        rows = list(ws.iter_rows(min_row=2, max_row=3, values_only=True))
        # Row 0 is Alpha, row 1 is Beta — % column is index 3
        assert rows[0][3] == 50.0, f"Expected 50.0 (from pct_total), got {rows[0][3]}"
        assert rows[1][3] == 50.0, f"Expected 50.0 (from pct_total), got {rows[1][3]}"
```

- [ ] **Step 2: Run test to verify it fails**

```
micromamba run -n shiny pytest tests/test_pa_export.py::TestBuildExtentSheet::test_pct_total_from_dataframe_is_preserved -v
```

Expected: FAIL. Current code recomputes `pct` from area ratios → `33.33` and `66.67`, but the test expects the upstream `pct_total` values → `50.0` and `50.0`.

- [ ] **Step 3: Prefer `pct_total` column when present**

Edit `pa_export.py`. First, replace line 140:
```python
        pct = (area / total_area * 100) if total_area > 0 else 0.0
```
with:
```python
        if "pct_total" in df.columns:
            pct_raw = row["pct_total"]
            pct = float(pct_raw) if not pd.isna(pct_raw) else 0.0
        else:
            pct = (area / total_area * 100) if total_area > 0 else 0.0
```

Then fix the TOTAL row at line 144. The current `ws.append(["TOTAL", "", round(total_area, 4), 100.0])` hardcodes `100.0` as the total percentage — which lies whenever per-row `pct_total` values don't sum to exactly 100 (rounding drift, deliberate upstream override, or partial-coverage accounts). Replace line 144:
```python
    ws.append(["TOTAL", "", round(total_area, 4), 100.0])
```
with:
```python
    if "pct_total" in df.columns:
        total_pct = float(df["pct_total"].sum())
    else:
        total_pct = 100.0 if total_area > 0 else 0.0
    ws.append(["TOTAL", "", round(total_area, 4), round(total_pct, 2)])
```

- [ ] **Step 4: Add a test that the TOTAL row reflects the actual sum, not 100.0**

Append to `class TestBuildExtentSheet`:

```python
    def test_total_row_reflects_actual_pct_sum(self):
        """TOTAL row % must equal sum of pct_total, not the hardcoded 100.0."""
        df = pd.DataFrame({
            "eunis_code":   ["A",   "B"],
            "habitat_name": ["Alpha", "Beta"],
            "area":         [1.0,   1.0],
            "pct_total":    [40.0,  40.0],  # partial coverage — sums to 80, not 100
        })
        wb = openpyxl.Workbook()
        ws = wb.active
        _build_extent_sheet(ws, df, unit="Ha")
        # TOTAL row is row 4 (header=1, A=2, B=3, TOTAL=4)
        total_row = list(ws.iter_rows(min_row=4, max_row=4, values_only=True))[0]
        assert total_row[0] == "TOTAL"
        assert total_row[3] == 80.0, (
            f"Expected TOTAL row % = 80.0 (sum of pct_total), got {total_row[3]}"
        )
```

- [ ] **Step 5: Run test to verify it fails, then implement the fix, then passes**

Since Step 3 already bundles the TOTAL-row fix, run all `TestBuildExtentSheet` tests after applying Step 3:
```
micromamba run -n shiny pytest tests/test_pa_export.py::TestBuildExtentSheet -v
```

Expected: PASS on all three (`test_custom_habitat_name_preserved`, `test_pct_total_from_dataframe_is_preserved`, `test_total_row_reflects_actual_pct_sum`).

- [ ] **Step 6: Commit**

```
git add pa_export.py tests/test_pa_export.py
git commit -m "fix(pa): use pct_total from DataFrame in extent sheet and TOTAL row"
```

---

## Task 6: Add schema guards to `generate_bbt8_workbook`

**Bug:** `pa_export.py:457-468` does direct column-access (`extent["area_m2"]`, `extent["total_area"]`, `accounts.columns` contains `"EUNIS_code"` / `"EUNIS_name"`) with no protection. A rename anywhere upstream in `eunis_data.py` produces an opaque `KeyError` mid-export, often after some sheets have already been written.

**Fix:** Validate the required columns at the top of `generate_bbt8_workbook` and raise a `ValueError` listing the missing ones.

**Files:**
- Modify: `pa_export.py:415-491` (top of `generate_bbt8_workbook`)
- Test: `tests/test_pa_export.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pa_export.py`:

```python
from pa_export import generate_bbt8_workbook


class TestGenerateBbt8Workbook:
    def _valid_inputs(self):
        """Build a minimal set of valid inputs; individual tests mutate one."""
        extent = pd.DataFrame({"EUNIS_code": ["MB252"], "area_m2": [100.0]})
        accounts = pd.DataFrame({
            "EUNIS_code": ["MB252"], "EUNIS_name": ["Posidonia"],
            "area_m2": [100.0], "Habitat_EV": [0.5], "Confidence": [0.9],
        })
        main_values = pd.DataFrame({
            "Subzone_ID": ["A"], "EUNIS_code": ["MB252"],
            "Habitat_EV": [0.5], "Habitat_confidence": [0.9],
        })
        condition = pd.DataFrame({"EUNIS_code": ["MB252"]})
        supply = pd.DataFrame({"EUNIS_code": ["MB252"]})
        return extent, accounts, main_values, condition, supply

    def test_missing_extent_area_column_raises(self):
        """extent without area_m2 or total_area must raise ValueError listing both names."""
        extent, accounts, main_values, condition, supply = self._valid_inputs()
        extent = pd.DataFrame({"EUNIS_code": ["MB252"], "something_else": [1]})
        with pytest.raises(ValueError, match="area_m2"):
            generate_bbt8_workbook(
                accounts=accounts, main_values=main_values, extent=extent,
                condition=condition, supply=supply, metadata={"BBT": "test"},
            )

    def test_missing_main_values_subzone_id_raises(self):
        """main_values without Subzone_ID must raise ValueError."""
        extent, accounts, main_values, condition, supply = self._valid_inputs()
        main_values = main_values.drop(columns=["Subzone_ID"])
        with pytest.raises(ValueError, match="Subzone_ID"):
            generate_bbt8_workbook(
                accounts=accounts, main_values=main_values, extent=extent,
                condition=condition, supply=supply, metadata={"BBT": "test"},
            )

    def test_valid_inputs_do_not_raise(self):
        """Sanity: valid inputs must not trigger the schema guard."""
        extent, accounts, main_values, condition, supply = self._valid_inputs()
        # Should not raise; ignore the returned BytesIO
        generate_bbt8_workbook(
            accounts=accounts, main_values=main_values, extent=extent,
            condition=condition, supply=supply, metadata={"BBT": "test"},
        )
```

(Add `import pytest` at top of file if not already imported.)

- [ ] **Step 2: Run tests to verify they fail**

```
micromamba run -n shiny pytest tests/test_pa_export.py::TestGenerateBbt8Workbook -v
```

Expected: FAIL on `test_missing_extent_area_column_raises` (current code raises `KeyError: 'total_area'`) and `test_missing_main_values_subzone_id_raises` (raises `KeyError: 'Subzone_ID'`). The `test_valid_inputs_do_not_raise` sanity check should already pass.

- [ ] **Step 3: Add schema validation at top of `generate_bbt8_workbook`**

Edit `pa_export.py` — insert this block immediately after the docstring in `generate_bbt8_workbook` (i.e. right before `buffer = io.BytesIO()` near line 446):

```python
    # Schema validation — fail loudly with clear messages
    missing = []
    if "EUNIS_code" not in extent.columns:
        missing.append("extent: 'EUNIS_code'")
    if "area_m2" not in extent.columns and "total_area" not in extent.columns:
        missing.append("extent: one of 'area_m2' or 'total_area'")
    if "EUNIS_code" not in accounts.columns:
        missing.append("accounts: 'EUNIS_code'")
    if "Subzone_ID" not in main_values.columns:
        missing.append("main_values: 'Subzone_ID'")
    if "EUNIS_code" not in main_values.columns:
        missing.append("main_values: 'EUNIS_code'")
    if missing:
        raise ValueError(
            "generate_bbt8_workbook called with malformed inputs. Missing columns: "
            + "; ".join(missing)
        )
```

- [ ] **Step 4: Run test to verify it passes**

```
micromamba run -n shiny pytest tests/test_pa_export.py::TestGenerateBbt8Workbook -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add pa_export.py tests/test_pa_export.py
git commit -m "fix(pa): validate schema in generate_bbt8_workbook before writing"
```

---

## Task 7: Wire real `total_bbt_area_m2` into BBT8 download

**Bug:** `app.py:2837` passes `total_bbt_area_m2=0` to `build_missing_values`. The parameter is currently unused inside `build_missing_values` (`eunis_data.py:178-201`), so this is latent — but any future code that divides by the total will immediately produce infinities or NaN.

**Fix:** Compute the actual value from `extent["area_m2"].sum()` at the BBT8 download site.

**Files:**
- Modify: `app.py:2837` (one line in `pa_download_bbt8`)

No new test: the parameter is currently inert downstream. This is a preventative fix.

- [ ] **Step 1: Replace the hardcoded zero**

Edit `app.py` — around line 2836-2837, change from:
```python
        accounts = eunis_data.build_accounts_summary(extent, condition)
        missing = eunis_data.build_missing_values(overlay, eva, total_bbt_area_m2=0)
```
to:
```python
        accounts = eunis_data.build_accounts_summary(extent, condition)
        total_area_m2 = float(extent["area_m2"].sum()) if "area_m2" in extent.columns else 0.0
        missing = eunis_data.build_missing_values(overlay, eva, total_bbt_area_m2=total_area_m2)
```

- [ ] **Step 2: Sanity-check by starting the app and exporting a BBT8 workbook**

```
micromamba run -n shiny python app.py
```

In the browser, upload a EUNIS overlay (or use the BBT8 test fixture), then click the "Download BBT8" button. Expected: a non-zero total area flowing through (no crash). If no fixture is on hand, this step can be skipped — the change is a pure substitution and existing tests on `build_missing_values` cover correctness.

- [ ] **Step 3: Commit**

```
git add app.py
git commit -m "fix(pa): pass real total area to build_missing_values in BBT8 download"
```

---

## Task 8: Reject non-positive supply inputs

**Bug:** `app.py:2250-2264` (`_collect_pa_supply_data`) wraps `float(val)` in a broad `except (KeyError, TypeError, ValueError)`. Non-numeric strings are silently dropped (fine, since the input is `ui.input_numeric`). But **negative numbers** (which are physically meaningless for tonnes landed, visitor-days, hectares protected, tonnes N removed) are accepted and flow through to the supply table and Excel export.

**Fix:** Extract the filter logic into a pure helper and reject negatives. Log a single warning summary per render rather than spamming notifications.

**Files:**
- Modify: `pa_calculations.py` (add `clean_supply_value` helper)
- Modify: `app.py:2250-2264` (`_collect_pa_supply_data`)
- Test: `tests/test_pa_calculations.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pa_calculations.py`:

```python
from pa_calculations import clean_supply_value


class TestCleanSupplyValue:
    def test_positive_value_passes(self):
        assert clean_supply_value(42.0) == 42.0

    def test_zero_passes(self):
        assert clean_supply_value(0) == 0.0

    def test_negative_returns_none(self):
        assert clean_supply_value(-1.5) is None

    def test_none_returns_none(self):
        assert clean_supply_value(None) is None

    def test_non_numeric_returns_none(self):
        assert clean_supply_value("not a number") is None

    def test_nan_returns_none(self):
        assert clean_supply_value(float("nan")) is None
```

- [ ] **Step 2: Run test to verify it fails**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py::TestCleanSupplyValue -v
```

Expected: FAIL with `ImportError: cannot import name 'clean_supply_value'`.

- [ ] **Step 3: Add the helper to `pa_calculations.py`**

Append to `pa_calculations.py` (after `validate_benefit_names`, before the TODO stubs):

```python
def clean_supply_value(val) -> float | None:
    """Return ``val`` as a non-negative float, or None if invalid.

    Rejects: None, non-numeric strings, NaN, and negative values (a physical
    supply quantity — tonnes, visitor-days, etc. — cannot be negative).
    """
    if val is None:
        return None
    try:
        out = float(val)
    except (TypeError, ValueError):
        return None
    if np.isnan(out) or out < 0:
        return None
    return out
```

- [ ] **Step 4: Run test to verify it passes**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py::TestCleanSupplyValue -v
```

Expected: PASS on all six subtests.

- [ ] **Step 5: Use the helper in `_collect_pa_supply_data`**

Edit `app.py` — replace lines 2250-2264 (`_collect_pa_supply_data` function body) with:

```python
    def _collect_pa_supply_data(benefit_names, habitat_codes):
        supply_data = {}
        for name in benefit_names:
            slug = pa_config.benefit_slug(name)
            quantities = {}
            for code in habitat_codes:
                try:
                    raw = input[f"supply_{slug}_{code}"]()
                except (KeyError, TypeError):
                    continue
                cleaned = pa_calculations.clean_supply_value(raw)
                if cleaned is not None:
                    quantities[code] = cleaned
            if quantities:
                supply_data[name] = quantities
        return supply_data
```

- [ ] **Step 6: Run the full PA test file**

```
micromamba run -n shiny pytest tests/test_pa_calculations.py tests/test_pa_export.py -v
```

Expected: PASS on all tests.

- [ ] **Step 7: Commit**

```
git add pa_calculations.py app.py tests/test_pa_calculations.py
git commit -m "fix(pa): reject negative and invalid supply inputs via clean_supply_value"
```

---

## Final Verification

- [ ] **Run the full test suite**

```
micromamba run -n shiny pytest tests/ -v
```

Expected: PASS across all tests (existing + the ones added in Tasks 1-8).

- [ ] **Manual smoke test**

```
micromamba run -n shiny python app.py
```

In the browser:
1. Upload a CSV + GeoJSON (use `Test dataset EC1 for EVAapp.csv` and any BBT grid).
2. Open the Physical Accounts tab. Assign a few habitats. Confirm the extent table renders.
3. Add a custom habitat (e.g. `code=X99, name=Custom test reef`), assign it to a subzone, confirm the custom name appears in the table.
4. Click "Download Standalone PA Workbook". Open the `.xlsx` and confirm the custom habitat name is present in the `Ecosystem Extent Account` sheet (not blank, not "Unknown").
5. Try entering `-5` in a supply-table cell and confirm it is dropped rather than exported.

---

## Out of Scope

- **`"Subzone ID"` vs `"Subzone_ID"` unification.** The PA tab and the BBT8/`eunis_data.py` pipeline use different column names. Unifying requires touching many files (`app.py` in several places, `eunis_data.py`, `pa_calculations.py`, `pa_export.py`, fixtures in `tests/`) and should be its own plan with an explicit migration strategy.
- **BBT8 pipeline custom-habitat handling.** Task 3 threads `custom_lookup` through `pa_calculations.compute_extent`, which serves the PA tab. The BBT8 download path (`app.py:2821 pa_download_bbt8`) goes through `eunis_data.compute_eunis_extent` instead, and reads habitat names directly from `dominant_EUNIS_name` in the overlay GeoPackage — so it is immune to the custom-habitat `"Unknown"` bug by construction. If BBT8 ever needs custom-habitat support, it belongs in a separate plan alongside Subzone-ID unification.
- **Per-subzone reactive polling performance** in `_update_pa_assignments` (`app.py:2118-2137`). Acceptable at N ≈ 200 subzones; revisit if any BBT grid exceeds ~1000.
- **Stale-assignment cleanup** when a user deselects a habitat after assigning it to subzones (`app.py:2118-2137`). The assignment dict keeps orphaned EUNIS codes. Not a correctness bug — orphan codes still resolve via `EUNIS_LOOKUP` — but confusing UX.
- **`EUNIS_LOOKUP` mutation regression test.** The comment at `app.py:2280-2281` warns historical code mutated this global; no test currently guards against regression. Worth a module-level invariant check but not urgent.
- **SEEA EA use table / condition account / extent-change account.** These are NotImplementedError stubs in `pa_calculations.py:226-238`, surfaced as "coming in a future version" UI copy at `app.py:2159, 2243`. Their implementation is a separate feature, not a bug fix.
- **EUNIS 2007 / 2022 code mixing** in `EUNIS_HFS_BH_CODES` (`pa_config.py:198-209`). The prefix-match semantics are risky but unrelated to the bugs fixed here — warrants a dedicated EUNIS-version-awareness plan.
