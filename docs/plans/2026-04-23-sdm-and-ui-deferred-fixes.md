# SDM & UI Deferred Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve 6 latent bugs deferred from PR #1's CodeRabbit review — 5 in the SDM analysis code path (coord-alias handling, residual/response alignment, NaN iteration, silent loop failure, coord-column filter) and 1 UI cleanup (duplicate HTML `id`).

**Architecture:** Two sequential PRs. PR #2 (`fix/sdm-hardening`) bundles all SDM fixes behind a shared constraint: `tests/test_eva_sdm.py` has 14 pre-existing failures caused by a broken `pykrige` in the environment. New tests must either avoid the kriging path or be skipped via `pytest.importorskip("pykrige")`. PR #3 (`fix/ui-duplicate-id`) is a single-line HTML fix with no tests.

**Tech Stack:** Python 3.13, pandas, geopandas, pykrige (optional — gated in tests), pytest, Shiny for Python. Run under the `shiny` micromamba environment.

---

## Scope Check

Two subsystems touched (SDM analysis, Shiny UI). The UI fix is trivial and separable, so it gets its own PR. All five SDM fixes share code in `scripts/sdm_analyse.py` and a common test-baseline constraint, so they cluster into PR #2.

## File Structure

**Files created:**
- `tests/test_sdm_analyse.py` — new test module for functions in `scripts/sdm_analyse.py`. The existing `tests/test_eva_sdm.py` covers the library (`eva_sdm.py`); the script's `compare_methods` / `analyse_collinearity` are testable but not currently covered anywhere.

**Files modified:**
- `scripts/sdm_analyse.py` — three separate patches: Task 1 (`.dropna` in `analyse_collinearity`), Task 2 (align `valid` with `residuals`), Task 3 (add `lat_col`/`lon_col` params to `compare_methods`), Task 4 (extract `filter_species_columns`). Task 3 also touches the second caller at line 927.
- `app.py` — two patches: Task 4 (call `filter_species_columns`), Task 5 (empty-`species_results` guard with stale-state reset).
- `eva_ui.py` — Task 6 (remove duplicate `id="sdm_tabs"`).

**Files NOT modified:**
- `eva_sdm.py` — `_sites_to_metric` already accepts `lat_col`/`lon_col` kwargs with defaults; no library change required.
- `tests/test_eva_sdm.py` — library tests unchanged; the 14 pykrige-dependent failures stay as-is.

---

## Pre-flight — baseline capture

Before any code change, capture the test baseline for later diff:

```bash
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/MARBEFES/EVA Algorithms"
micromamba run -n shiny python -m pytest tests/test_eva_sdm.py --tb=no -q 2>&1 | tail -3 > /tmp/sdm_baseline.txt
cat /tmp/sdm_baseline.txt
```

Expected output (record exact numbers):
```
14 failed, 25 passed, 8 skipped, N warnings in Ns
```

Any rerun must match `N_failed` to within ±0 and `N_passed` to at least the baseline (+ newly-added passing tests). If `N_failed` rises, a new regression was introduced.

---

# PR #2 — SDM hardening (`fix/sdm-hardening`)

## Task 1: Drop NaN before iterating EUNIS habitats (Finding 2.3)

**Files:**
- Create: `tests/test_sdm_analyse.py`
- Modify: `scripts/sdm_analyse.py:489-495`

### Context

In `analyse_collinearity`, the EUNIS column may contain `NaN` for subzones with no habitat attribution. The current code does `for h in sorted(sites_cov[eunis_col].unique()):` which raises `TypeError: '<' not supported between instances of 'str' and 'float'` on Python 3.13 / pandas 2.x when `NaN` and strings mix.

- [ ] **Step 1: Create `tests/test_sdm_analyse.py` with the failing test**

```python
"""Tests for scripts/sdm_analyse.py — the script's testable functions."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# scripts/ is a package via its __init__.py — add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sdm_analyse import analyse_collinearity


class TestAnalyseCollinearityNaN:
    def test_nan_in_eunis_does_not_raise(self):
        """Regression: sorted() on a series with NaN + strings used to raise TypeError."""
        sites = pd.DataFrame({
            "dominant_EUNIS2019": ["A5.25", "A5.25", np.nan, "A4.4"],
            "depth_m": [10.0, 20.0, 30.0, 40.0],
        })
        out = analyse_collinearity(sites, env_cols=["depth_m"])
        assert "habitat_counts" in out

    def test_nan_not_present_as_habitat_key(self):
        """NaN must not appear as a key in habitat_counts or depth_by_habitat."""
        sites = pd.DataFrame({
            "dominant_EUNIS2019": ["A5.25", np.nan, "A4.4", "A5.25"],
            "depth_m": [10.0, 20.0, 30.0, 40.0],
        })
        out = analyse_collinearity(sites, env_cols=["depth_m"])
        assert not any(pd.isna(k) for k in out["habitat_counts"])
        assert not any(pd.isna(k) for k in out["depth_by_habitat"])
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
micromamba run -n shiny python -m pytest tests/test_sdm_analyse.py::TestAnalyseCollinearityNaN -v 2>&1 | tail -10
```

Expected: both tests fail with `TypeError: '<' not supported between instances of 'float' and 'str'` (or the pandas variant).

- [ ] **Step 3: Apply the fix**

In `scripts/sdm_analyse.py`, replace lines 489–495:

```python
# Habitat distribution
hab_counts = sites_cov[eunis_col].value_counts().to_dict()

# Depth by habitat
depth_by_hab = {}
if "depth_m" in sites_cov.columns:
    for h in sorted(sites_cov[eunis_col].unique()):
```

with:

```python
# Habitat distribution — drop NaN habitats so iteration and value_counts
# do not surface NaN keys to downstream formatters.
eunis_series = sites_cov[eunis_col].dropna()
hab_counts = eunis_series.value_counts().to_dict()

# Depth by habitat
depth_by_hab = {}
if "depth_m" in sites_cov.columns:
    for h in sorted(eunis_series.unique()):
```

- [ ] **Step 4: Run test, confirm it passes**

```bash
micromamba run -n shiny python -m pytest tests/test_sdm_analyse.py::TestAnalyseCollinearityNaN -v 2>&1 | tail -5
```

Expected: `2 passed`.

- [ ] **Step 5: Run baseline check**

```bash
micromamba run -n shiny python -m pytest tests/test_eva_sdm.py --tb=no -q 2>&1 | tail -3
```

Expected: `14 failed, 25 passed, 8 skipped` (unchanged from baseline).

- [ ] **Step 6: Commit**

```bash
git add tests/test_sdm_analyse.py scripts/sdm_analyse.py
git commit -m "fix(sdm): drop NaN EUNIS rows before iteration in analyse_collinearity"
```

---

## Task 2: Align `valid` with `residuals` in regression_kriging (Finding 2.2)

**Files:**
- Modify: `scripts/sdm_analyse.py:436-444`
- Modify: `tests/test_sdm_analyse.py` (append)

### Context

`eva_sdm.prepare_features` drops rows where `response_col` OR any feature column is NaN (line 183 of `eva_sdm.py`). The reconstructed `valid` at lines 440–442 only drops on feature cols, so when any row has NaN response, `len(valid) > len(residuals)` and `valid["__resid__"] = residuals` raises `ValueError: Length mismatch`. Fix: add `species` to the `dropna` subset.

This task extracts an inline helper so the alignment can be unit-tested without invoking `pykrige` (which is broken in the current env and would otherwise skip-via-importorskip).

- [ ] **Step 1: Append the failing test to `tests/test_sdm_analyse.py`**

```python
class TestAlignValidForResiduals:
    """Extract-to-helper target: the alignment logic between
    prepare_features' kept-row count and the subset of sites_cov used
    for residual kriging."""

    def test_helper_drops_species_nan(self):
        from scripts.sdm_analyse import _align_valid_for_residuals
        sites = pd.DataFrame({
            "sp": [1.0, 2.0, np.nan, 4.0],     # row index 2 has NaN response
            "depth_m": [10.0, 20.0, 30.0, 40.0],
            "slope": [0.1, 0.2, 0.3, 0.4],
        })
        valid = _align_valid_for_residuals(sites, ["depth_m", "slope"], "sp")
        assert len(valid) == 3                  # row 2 dropped
        assert valid["sp"].isna().sum() == 0

    def test_helper_drops_feature_nan(self):
        from scripts.sdm_analyse import _align_valid_for_residuals
        sites = pd.DataFrame({
            "sp": [1.0, 2.0, 3.0, 4.0],
            "depth_m": [10.0, np.nan, 30.0, 40.0],   # row 1 has NaN feature
            "slope": [0.1, 0.2, 0.3, 0.4],
        })
        valid = _align_valid_for_residuals(sites, ["depth_m", "slope"], "sp")
        assert len(valid) == 3
        assert valid["depth_m"].isna().sum() == 0

    def test_helper_reset_index(self):
        """valid must have a contiguous RangeIndex starting at 0 so residual assignment by position is safe."""
        from scripts.sdm_analyse import _align_valid_for_residuals
        sites = pd.DataFrame({
            "sp": [1.0, np.nan, 3.0],
            "x": [1.0, 2.0, 3.0],
        })
        valid = _align_valid_for_residuals(sites, ["x"], "sp")
        assert list(valid.index) == [0, 1]
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
micromamba run -n shiny python -m pytest tests/test_sdm_analyse.py::TestAlignValidForResiduals -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name '_align_valid_for_residuals' from 'scripts.sdm_analyse'` for all three tests.

- [ ] **Step 3: Apply the fix**

In `scripts/sdm_analyse.py`, add this helper near the top of the file (after the `import` block, above the first function):

```python
def _align_valid_for_residuals(
    sites_cov: pd.DataFrame, cols: list[str], species_col: str
) -> pd.DataFrame:
    """Return rows of ``sites_cov`` that survive NaN-dropping on both the
    response column (``species_col``) and the numeric predictor columns.

    Matches the row set that ``eva_sdm.prepare_features`` would keep,
    so a residual vector built from those rows aligns index-by-index.
    """
    numeric = [c for c in cols if pd.api.types.is_numeric_dtype(sites_cov[c])]
    return sites_cov.dropna(subset=numeric + [species_col]).reset_index(drop=True)
```

Then replace lines 440–442 (the existing `valid = sites_cov.dropna(...)` block) with a call to the helper:

```python
valid = _align_valid_for_residuals(sites_cov, cols, species)
valid["__resid__"] = residuals
```

- [ ] **Step 4: Run test, confirm it passes**

```bash
micromamba run -n shiny python -m pytest tests/test_sdm_analyse.py::TestAlignValidForResiduals -v 2>&1 | tail -5
```

Expected: `3 passed`.

- [ ] **Step 5: Run baseline check**

```bash
micromamba run -n shiny python -m pytest tests/test_eva_sdm.py --tb=no -q 2>&1 | tail -3
```

Expected: `14 failed, 25 passed, 8 skipped` (unchanged).

- [ ] **Step 6: Commit**

```bash
git add tests/test_sdm_analyse.py scripts/sdm_analyse.py
git commit -m "fix(sdm): align valid DataFrame with prepare_features residual length"
```

---

## Task 3: Thread `lat_col`/`lon_col` through `compare_methods` (Finding 2.1)

**Files:**
- Modify: `scripts/sdm_analyse.py:360-395` (signature and one call)
- Modify: `scripts/sdm_analyse.py:927` (second caller, unchanged by virtue of default values)
- Modify: `app.py:3509-3512` (primary caller — thread detected names when available)
- Modify: `tests/test_sdm_analyse.py` (append)

### Context

`compare_methods` hardcodes `"lat"`/`"lon"` at line 395 when calling `eva_sdm._sites_to_metric`. The library function `_sites_to_metric` already accepts `lat_col`/`lon_col` kwargs with defaults (confirmed at `eva_sdm.py:1050-1052`) — no library change needed. Both callers (`app.py:3509` and `scripts/sdm_analyse.py:927`) can remain unchanged if defaults stay `"lat"/"lon"`, but the signature expansion is required so a caller holding aliased coordinate columns (DwC-A: `decimalLatitude`/`decimalLongitude`) can pass them through without raising `KeyError`.

The test for the "rf" branch of `compare_methods` can verify col-name acceptance **without requiring pykrige** by asking only for `methods=["rf"]`. The kriging branch test requires `pytest.importorskip("pykrige")` and will SKIP (not fail) in the current env.

- [ ] **Step 1: Append the failing tests to `tests/test_sdm_analyse.py`**

```python
class TestCompareMethodsCoordCols:
    """Ensure compare_methods accepts aliased lat/lon column names."""

    def _sites(self, lat_name="latitude", lon_name="longitude"):
        import geopandas as gpd
        from shapely.geometry import Point
        # 12 sites with varied response + one covariate
        coords = [(20 + i * 0.1, 55 + i * 0.1) for i in range(12)]
        return pd.DataFrame({
            lat_name: [c[1] for c in coords],
            lon_name: [c[0] for c in coords],
            "depth_m": [10.0 + i for i in range(12)],
            "sp": [0.1 * i + 0.5 for i in range(12)],
        })

    def _cov_grid(self):
        import geopandas as gpd
        from shapely.geometry import Point
        return gpd.GeoDataFrame(
            {"depth_m": [10.0, 20.0, 30.0]},
            geometry=[Point(20.1, 55.1), Point(20.2, 55.2), Point(20.3, 55.3)],
            crs="EPSG:4326",
        )

    def test_rf_method_accepts_aliased_coord_cols(self):
        """rf branch does not touch _sites_to_metric, but the signature must accept the kwargs."""
        from scripts.sdm_analyse import compare_methods
        sites = self._sites()
        cov = self._cov_grid()
        results = compare_methods(
            sites, "sp", cov,
            methods=["rf"],
            env_cols=["depth_m"],
            eunis_cols=[],
            lat_col="latitude", lon_col="longitude",
        )
        # rf does not error on the renamed coord cols (since it doesn't use them)
        assert any(k.startswith("RF") or k == "rf" or "RF" in k for k in results)

    def test_kriging_method_accepts_aliased_coord_cols(self):
        """kriging branch passes lat_col/lon_col to _sites_to_metric — no KeyError on aliases."""
        pytest.importorskip("pykrige")
        from scripts.sdm_analyse import compare_methods
        sites = self._sites()
        cov = self._cov_grid()
        results = compare_methods(
            sites, "sp", cov,
            methods=["kriging"],
            env_cols=["depth_m"],
            eunis_cols=[],
            lat_col="latitude", lon_col="longitude",
        )
        # Either the branch succeeded or errored, but not on the lat/lon key
        err = results.get("Ordinary Kriging", {}).get("error", "")
        assert "lat" not in err and "lon" not in err, \
            f"coord-name KeyError suggests threading failed: {err!r}"
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
micromamba run -n shiny python -m pytest tests/test_sdm_analyse.py::TestCompareMethodsCoordCols -v 2>&1 | tail -12
```

Expected: `test_rf_method_accepts_aliased_coord_cols` fails with `TypeError: compare_methods() got an unexpected keyword argument 'lat_col'`. `test_kriging_method_accepts_aliased_coord_cols` either skips (pykrige missing) or fails with the same TypeError.

- [ ] **Step 3: Apply the fix in `scripts/sdm_analyse.py`**

Change the signature (lines 360-367):

```python
def compare_methods(
    sites_cov: pd.DataFrame,
    species: str,
    covariates: gpd.GeoDataFrame,
    methods: list[str] = None,
    env_cols: list[str] | None = None,
    eunis_cols: list[str] | None = None,
    lat_col: str = "lat",
    lon_col: str = "lon",
) -> dict[str, Any]:
```

Change line 395:

```python
coords_m = eva_sdm._sites_to_metric(sites_cov, lat_col, lon_col)
```

The second caller at `scripts/sdm_analyse.py:927` requires no change — defaults preserve current behaviour.

- [ ] **Step 4: Update the primary caller in `app.py:3509-3512`**

```python
# Detect lat/lon column names from the upload (falls back to defaults).
lat_col = next((c for c in ("lat", "latitude", "decimalLatitude", "decimallatitude") if c in sites_cov.columns), "lat")
lon_col = next((c for c in ("lon", "longitude", "decimalLongitude", "decimallongitude") if c in sites_cov.columns), "lon")

method_results = _sdm_mod.compare_methods(
    sites_cov, selected[0][0], cov,
    methods=["rf", "kriging"],
    lat_col=lat_col, lon_col=lon_col,
)
```

- [ ] **Step 5: Run tests, confirm they pass**

```bash
micromamba run -n shiny python -m pytest tests/test_sdm_analyse.py::TestCompareMethodsCoordCols -v 2>&1 | tail -6
```

Expected: 1 passed, 1 skipped (pykrige missing) — or 2 passed if pykrige is available. Zero failures.

- [ ] **Step 6: Run baseline check**

```bash
micromamba run -n shiny python -m pytest tests/test_eva_sdm.py --tb=no -q 2>&1 | tail -3
```

Expected: baseline unchanged.

- [ ] **Step 7: Commit**

```bash
git add tests/test_sdm_analyse.py scripts/sdm_analyse.py app.py
git commit -m "fix(sdm): accept lat_col/lon_col kwargs in compare_methods for coord aliases"
```

---

## Task 4: Extract `filter_species_columns` helper and expand coord aliases (Finding 2.5)

**Files:**
- Modify: `scripts/sdm_analyse.py` (append new helper)
- Modify: `app.py:3472-3477` (call helper)
- Modify: `tests/test_sdm_analyse.py` (append)

### Context

App-side species detection at `app.py:3473-3477` uses a small `meta_cols` set that excludes only `lat`, `lon`, `depth`, etc. — not the common DwC-A aliases `decimalLatitude`, `decimalLongitude`, `x`, `y`. Any such alias that is numeric gets treated as a species column, producing nonsensical prevalence analysis. This task extracts the filter into a pure testable helper.

- [ ] **Step 1: Append the failing test**

```python
class TestFilterSpeciesColumns:
    def test_excludes_dwca_coord_aliases(self):
        from scripts.sdm_analyse import filter_species_columns
        df = pd.DataFrame({
            "decimalLatitude":  [55.1, 55.2],
            "decimalLongitude": [20.1, 20.2],
            "eventID":          ["e1", "e2"],
            "depth_m":          [10.0, 20.0],
            "Sprattus sprattus": [0.5, 0.8],
            "Clupea harengus":   [0.1, 0.2],
        })
        cols = filter_species_columns(df)
        assert set(cols) == {"Sprattus sprattus", "Clupea harengus"}

    def test_case_insensitive(self):
        from scripts.sdm_analyse import filter_species_columns
        df = pd.DataFrame({
            "LATITUDE":  [55.1, 55.2],
            "longitude": [20.1, 20.2],
            "species_A": [1.0, 2.0],
        })
        assert filter_species_columns(df) == ["species_A"]

    def test_keeps_numeric_only(self):
        from scripts.sdm_analyse import filter_species_columns
        df = pd.DataFrame({
            "lat":      [55.1],
            "notes":    ["a text field"],           # non-numeric excluded
            "species":  [1.0],
        })
        assert filter_species_columns(df) == ["species"]
```

- [ ] **Step 2: Run tests, confirm failure**

```bash
micromamba run -n shiny python -m pytest tests/test_sdm_analyse.py::TestFilterSpeciesColumns -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name 'filter_species_columns'` for all three.

- [ ] **Step 3: Apply the fix — add helper to `scripts/sdm_analyse.py`**

Append (near the top of the file, after the imports):

```python
# Columns that should never be classified as a species response.
# Lower-cased; the filter compares via str.lower().
_SDM_META_COLUMNS = frozenset({
    "lat", "lon", "latitude", "longitude",
    "decimallatitude", "decimallongitude",
    "x", "y", "coord_x", "coord_y",
    "eventid", "occurrenceid", "locationid", "site_id", "station",
    "date", "datetime", "eventdate",
    "depth", "depth_m", "elevation",
    "geometry",
})


def filter_species_columns(data: pd.DataFrame) -> list[str]:
    """Return numeric columns of ``data`` that are not metadata/coord/id columns.

    Case-insensitive against a curated exclusion list. Non-numeric columns
    are always dropped regardless of name.
    """
    return [
        c for c in data.columns
        if c.lower() not in _SDM_META_COLUMNS
        and pd.api.types.is_numeric_dtype(data[c])
    ]
```

- [ ] **Step 4: Replace the inline filter in `app.py:3472-3477`**

Current:

```python
else:
    meta_cols = {"lat", "lon", "eventid", "locationid", "site_id",
                 "station", "date", "depth", "geometry"}
    species_list = [c for c in data.columns
                    if c.lower() not in meta_cols
                    and pd.api.types.is_numeric_dtype(data[c])]
```

Replace with:

```python
else:
    species_list = _sdm_mod.filter_species_columns(data)
```

- [ ] **Step 5: Run tests, confirm pass**

```bash
micromamba run -n shiny python -m pytest tests/test_sdm_analyse.py::TestFilterSpeciesColumns -v 2>&1 | tail -6
```

Expected: `3 passed`.

- [ ] **Step 6: Baseline check**

```bash
micromamba run -n shiny python -m pytest tests/test_eva_sdm.py --tb=no -q 2>&1 | tail -3
```

Unchanged.

- [ ] **Step 7: Commit**

```bash
git add tests/test_sdm_analyse.py scripts/sdm_analyse.py app.py
git commit -m "fix(sdm): exclude DwC-A coord aliases from species auto-select"
```

---

## Task 5: Guard empty `species_results` in app.py (Finding 2.4)

**Files:**
- Modify: `app.py:3490-3499`

### Context

If every species iteration in the loop raises (data issues in `compare_predictor_sets`), `species_results` ends up empty but the app proceeds to store it as a successful analysis. The reactive `sdm_analysis_results` either keeps a stale value from a previous successful run or shows an empty analysis to the user. This is a Shiny-side UI reactive and is not unit-testable in isolation; manual QA is the accept gate. The fix is defensive — it does not change a successful-case code path.

Note: CodeRabbit's original comment mentioned "two identical blocks" but there is only one such loop in `app.py`. The sister loop at `scripts/sdm_analyse.py:906` has no try/except and already fails loud.

- [ ] **Step 1: Apply the fix in `app.py`**

Current (lines 3490-3499):

```python
# Run predictor comparison for each species
sdm_analysis_message.set(f"⏳ Comparing predictors for {len(selected)} species…")
species_results = {}
for sp, prev, n_pres in selected:
    try:
        species_results[sp] = _sdm_mod.compare_predictor_sets(
            sites_cov, sp, do_cv=False
        )
    except Exception as exc:
        logger.warning("Predictor analysis failed for %s: %s", sp, exc)
```

Replace with:

```python
# Run predictor comparison for each species
sdm_analysis_message.set(f"⏳ Comparing predictors for {len(selected)} species…")
species_results = {}
for sp, prev, n_pres in selected:
    try:
        species_results[sp] = _sdm_mod.compare_predictor_sets(
            sites_cov, sp, do_cv=False
        )
    except Exception as exc:
        logger.warning("Predictor analysis failed for %s: %s", sp, exc)

if not species_results:
    msg = (
        f"SDM predictor analysis failed for all {len(selected)} species — "
        "see the server log for per-species errors."
    )
    logger.error(msg)
    ui.notification_show(msg, type="error", duration=15)
    sdm_analysis_message.set(f"❌ {msg}")
    # Clear any stale successful-run state so the UI does not show mixed data.
    sdm_analysis_results.set(None)
    return
```

- [ ] **Step 2: Manual verification (no unit test possible)**

Start the app locally:

```bash
micromamba run -n shiny shiny run app.py
```

Open http://localhost:8000/, upload a site-covariates CSV that has at least one species column but insufficient non-NaN observations to fit any model (e.g., 4 rows). Click through to the SDM tab and trigger Predictor Analysis. Expect: a red notification "SDM predictor analysis failed for all N species — see the server log for per-species errors." AND the SDM results area either shows the previous analysis cleared or an empty state — not stale content.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "fix(sdm-ui): surface empty species_results as error, reset stale state"
```

---

## Final PR #2 verification

- [ ] **Step 1: Full SDM-scope test sweep**

```bash
micromamba run -n shiny python -m pytest tests/test_sdm_analyse.py tests/test_eva_sdm.py --tb=line -q 2>&1 | tail -5
```

Expected: all new `test_sdm_analyse.py` tests pass; `test_eva_sdm.py` unchanged at 14 failed / 25 passed / 8 skipped (or 1 more skip if the kriging test skipped).

- [ ] **Step 2: App import check**

```bash
micromamba run -n shiny python -c "import app; print('app OK')"
```

Expected: `app OK`.

- [ ] **Step 3: Push branch and open PR**

```bash
git push -u origin fix/sdm-hardening
gh pr create --title "SDM hardening: coord aliases, residual alignment, NaN handling, empty-results guard" \
  --body "$(cat <<'EOF'
## Summary
- Five CodeRabbit findings from PR #1 addressed, all in the SDM analysis path.
- Respects the pre-existing 14 pykrige-related failures in tests/test_eva_sdm.py — baseline unchanged.

## Test plan
- [x] tests/test_sdm_analyse.py: 8 new unit tests, all passing (1 auto-skips without pykrige)
- [x] tests/test_eva_sdm.py baseline: 14 failed / 25 passed / 8 skipped (unchanged)
- [x] app.py imports clean
- [ ] Manual QA: trigger SDM with a broken response column, verify the empty-results notification fires
EOF
)"
```

- [ ] **Step 4: Address any CodeRabbit re-review findings, then merge**

---

# PR #3 — UI duplicate `id` cleanup (`fix/ui-duplicate-id`)

## Task 6: Remove outer `id="sdm_tabs"` on wrapper div

**Files:**
- Modify: `eva_ui.py:2097`

### Context

`ui.navset_tab(..., id="sdm_tabs")` at line 2095 sets the id on the proper tab control. The surrounding `ui.div(..., id="sdm_tabs")` at line 2097 creates a duplicate element id. Pre-flight grep (below) confirms no other file references `sdm_tabs`.

- [ ] **Step 1: Pre-flight grep — confirm no hidden coupling**

```bash
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/MARBEFES/EVA Algorithms"
grep -rn "sdm_tabs" --include="*.py" --include="*.js" --include="*.css" --include="*.html" .
```

Expected: three hits, all in `eva_ui.py` (the CSS block at 2040-2048, the navset `id` at 2095, the duplicate `id` at 2097). No hits in `app.py` or anywhere else. If anything unexpected appears, STOP and investigate.

- [ ] **Step 2: Apply the fix in `eva_ui.py`**

Change lines 2095-2099 from:

```python
                        id="sdm_tabs",
                    ),
                    id="sdm_tabs",
                    style="height:100%;"
                ),
```

to:

```python
                        id="sdm_tabs",
                    ),
                    style="height:100%;"
                ),
```

- [ ] **Step 3: Verify exactly one `id="sdm_tabs"` remains**

```bash
grep -c 'id="sdm_tabs"' eva_ui.py
```

Expected: `1`.

- [ ] **Step 4: App import check**

```bash
micromamba run -n shiny python -c "import eva_ui; print('eva_ui OK')"
```

Expected: `eva_ui OK`.

- [ ] **Step 5: Manual UI smoke test**

Start the app and navigate to the SDM section:

```bash
micromamba run -n shiny shiny run app.py
```

In the browser, click through all seven SDM sub-tabs (Data, Predictors, Map, Uncertainty, Diagnostics, Variogram, GAM Effects). All should render and switch correctly. CSS under `#sdm_tabs .nav-tabs` still applies because the selector targets descendants of the surviving (inner) `id`.

- [ ] **Step 6: Commit, push, PR, merge**

```bash
git add eva_ui.py
git commit -m "chore(ui): remove duplicate id='sdm_tabs' on wrapper div"
git push -u origin fix/ui-duplicate-id
gh pr create --title "UI: remove duplicate id=sdm_tabs" \
  --body "$(cat <<'EOF'
## Summary
CodeRabbit finding from PR #1 review. The wrapper ui.div duplicated the id of its child ui.navset_tab. Removed from the outer wrapper; inner navset keeps it. CSS selectors (#sdm_tabs .nav-tabs) still match.

## Test plan
- [x] grep confirms exactly one id="sdm_tabs" remains
- [x] eva_ui imports clean
- [ ] Manual: SDM sub-tabs still switch correctly
EOF
)"
```

---

## Self-review checklist

- [x] **Spec coverage** — each of CodeRabbit's 6 deferred findings mapped to exactly one task (2.1→Task 3, 2.2→Task 2, 2.3→Task 1, 2.4→Task 5, 2.5→Task 4, 3.1→Task 6).
- [x] **Placeholders** — none remain. Each task shows test code, implementation code, commands, expected output.
- [x] **Type consistency** — `filter_species_columns` referenced in Task 4 is defined in Task 4. `_align_valid_for_residuals` defined in Task 2 is only used in Task 2. No forward dangling references.
- [x] **Test file placement** — all new tests go to `tests/test_sdm_analyse.py` (matching the code under test's location in `scripts/`). Existing `tests/test_eva_sdm.py` stays untouched to preserve the baseline.
- [x] **pykrige-broken-env handling** — Task 3's kriging test uses `pytest.importorskip("pykrige")`; Tasks 1/2/4/5 do not hit pykrige.
- [x] **Baseline check** — every task runs `tests/test_eva_sdm.py` afterwards and compares against the recorded baseline.
- [x] **Second caller for Task 3** — explicitly mentioned `scripts/sdm_analyse.py:927` needing no change because defaults preserve behaviour.
- [x] **Finding 2.4 stale-state** — the empty-results guard also resets `sdm_analysis_results.set(None)` so stale UI from a prior success does not leak through.

## Not in scope

- Fixing the 14 pre-existing `test_eva_sdm.py` failures (pykrige environment issue) — own plan.
- Refactoring `eva_sdm.prepare_features` to return row indices — an API change that would enable a cleaner Task 2 but is not required by the bug fix.
- Any changes to the `cov` covariate grid preparation or the CMEMS data path.
- PR #1's follow-ups that don't appear in CodeRabbit's review (e.g., matplotlib font choice, cache eviction policy).
