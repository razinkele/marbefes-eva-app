# Local env repair: pykrige, pygam, gstools missing from `shiny` micromamba env

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking. This is an **environment-maintenance plan**, not a code plan — no files under version control are modified. The test suite itself is the spec.

**Goal:** Resolve all 14 pre-existing failures in `tests/test_eva_sdm.py` by installing three packages (`pygam`, `pykrige`, `gstools`) that are declared in `requirements.txt` but missing from the local `shiny` micromamba environment. Outcome: full test suite runs without any `ImportError`, and the `pytest.importorskip("pykrige")` gate in `tests/test_sdm_analyse.py::TestCompareMethodsCoordCols::test_kriging_method_accepts_aliased_coord_cols` flips from **skip** to **pass**.

**Architecture:** Single operation — `micromamba install -n shiny -c conda-forge <pkgs>`. No code changes. No file edits. Per `~/.claude/CLAUDE.md`, this project uses micromamba exclusively (never `pip install` unless a package is unavailable on conda-forge). Conda-forge availability pre-checked: `pykrige 1.7.3`, `pygam 0.12.0`, `gstools 1.7.0` — all at or above the floors in `requirements.txt`.

**Tech Stack:** micromamba (Mamba 2.x), conda-forge channel, Python 3.13.12 inside the `shiny` env, pytest.

---

## Scope Check

Single subsystem: the local developer micromamba env. Server-side `/opt/micromamba/envs/shiny/` on laguna is a separate environment and is out of scope — production doesn't run the pytest suite.

## What this plan does NOT do

- It does **not** modify `requirements.txt` — the entries are already correct.
- It does **not** fix the **server-side** micromamba env on `laguna.ku.lt`. If the production server ever runs into the same missing-deps issue, the fix is analogous but needs sudo or the vendored-to-app-dir workaround documented in memory note `project_laguna_deploy_runtime_env.md`.
- It does **not** touch the 14 failing tests themselves — they are correct; the env is broken.
- It does **not** add new tests. The existing test suite is the full specification.

## Pre-flight — confirm symptom shape

Before installing anything, verify the failure shape matches this plan's diagnosis. If the failures look different (e.g., new assertion errors, different exception classes), STOP and re-investigate — the env may have a secondary issue beyond missing packages.

- [ ] **Step 0.1: Capture baseline failure summary**

```bash
cd "C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/MARBEFES/EVA Algorithms"
micromamba run -n shiny python -m pytest tests/test_eva_sdm.py --tb=no -q 2>&1 | tail -20
```

Expected tail of output:
```
14 failed, 25 passed, 8 skipped, 470 warnings in Ns
FAILED tests/test_eva_sdm.py::TestGAM::test_fit_linear_gam - ImportError: pyg...
FAILED tests/test_eva_sdm.py::TestGAM::test_fit_logistic_gam - ImportError: p...
FAILED tests/test_eva_sdm.py::TestPredictGrid::test_gam_prediction_shape - Im...
FAILED tests/test_eva_sdm.py::TestPredictGrid::test_ensemble_no_nan_where_both_valid
FAILED tests/test_eva_sdm.py::TestOrdinaryKriging::test_fit_returns_model - I...
FAILED tests/test_eva_sdm.py::TestOrdinaryKriging::test_variogram_models[spherical]
FAILED tests/test_eva_sdm.py::TestOrdinaryKriging::test_variogram_models[gaussian]
FAILED tests/test_eva_sdm.py::TestOrdinaryKriging::test_variogram_models[exponential]
FAILED tests/test_eva_sdm.py::TestOrdinaryKriging::test_predict_grid_returns_uncertainty
FAILED tests/test_eva_sdm.py::TestOrdinaryKriging::test_kriging_uncertainty_higher_away_from_sites
FAILED tests/test_eva_sdm.py::TestRegressionKriging::test_fit_and_predict - I...
FAILED tests/test_eva_sdm.py::TestRegressionKriging::test_regression_kriging_valid_range
FAILED tests/test_eva_sdm.py::TestVariogramPlot::test_returns_html_string - I...
FAILED tests/test_eva_sdm.py::TestVariogramPlot::test_contains_variogram_model_name
```

If the count is not exactly `14 failed, 25 passed, 8 skipped`, or if any of those 14 are NOT `ImportError`, STOP and re-diagnose. The plan assumes the textbook failure shape.

- [ ] **Step 0.2: Confirm the three packages are truly missing**

```bash
micromamba run -n shiny python -c "import pygam"   2>&1 | tail -3
micromamba run -n shiny python -c "import pykrige" 2>&1 | tail -3
micromamba run -n shiny python -c "import gstools" 2>&1 | tail -3
```

Expected: all three print `ModuleNotFoundError: No module named '<name>'`. If any succeed, the env has a partial install — STOP and investigate why the tests still fail with that module present.

- [ ] **Step 0.3: Confirm conda-forge has each package at ≥ requirements.txt floor**

`requirements.txt` floors: `pygam>=0.9.0`, `pykrige>=1.7.0`, `gstools>=1.5.0`. Pre-verified at plan-write time: `pygam 0.12.0`, `pykrige 1.7.3`, `gstools 1.7.0` are all on conda-forge. Skip this step unless the install in Task 1 errors on availability.

## Task 1: Install the three missing packages from conda-forge

**Command format:** `micromamba install -n shiny -c conda-forge <pkg1> <pkg2> <pkg3>` — one transaction so the dependency solver picks a mutually-compatible set.

**Files:** none changed (env mutation only).

**Rationale:** `~/.claude/CLAUDE.md` is explicit: "Install new packages with: `micromamba install -n shiny <package>`. Never use `pip install` unless a package is unavailable on conda-forge." Conda-forge availability confirmed in Step 0.3.

- [ ] **Step 1.1: Install in one transaction**

```bash
micromamba install -n shiny -c conda-forge pygam pykrige gstools -y
```

Expected: solver completes, downloads the three packages + any transitive deps (`networkx` for pygam, `meshio`/`emcee` for gstools), transaction reports `Installed <N> packages`. Exit code 0.

**If the solver reports a conflict** (e.g., with an existing pinned version of `scipy` or `numpy`), STOP — do not pass `--force-reinstall`. Report the conflict and re-plan. Likely cause: a stricter pin elsewhere in the env that conda-forge's latest versions incompatible with. Downgrade the `--channel` to `conda-forge/label/main` or pin `<pkg>=<older-version>` explicitly.

**If conda-forge times out or returns a 404**, fall back to pip per-package — see "Fallback: pip install" section below.

- [ ] **Step 1.2: Confirm the installs stuck**

```bash
micromamba run -n shiny python -c "import pygam;   print('pygam',   pygam.__version__)"
micromamba run -n shiny python -c "import pykrige; print('pykrige', pykrige.__version__)"
micromamba run -n shiny python -c "import gstools; print('gstools', gstools.__version__)"
```

Expected (version numbers may be newer than pre-checked — that's fine, floors are met):
```
pygam   0.12.0
pykrige 1.7.3
gstools 1.7.0
```

If any still raises `ModuleNotFoundError`, the transaction reported success but the env didn't actually gain the module — run `micromamba list -n shiny | grep -iE "pygam|pykrige|gstools"` to diagnose and STOP.

## Task 2: Verify the 14 failures resolve

**Files:** none changed. Running the tests only.

- [ ] **Step 2.1: Re-run `test_eva_sdm.py` alone**

```bash
micromamba run -n shiny python -m pytest tests/test_eva_sdm.py --tb=line -q 2>&1 | tail -20
```

**Expected — full success shape:**
```
39 passed, 8 skipped, N warnings in Ns
```

(Total 47 items: 39 pass, 8 skip. The 8 skips are NOT stable platform skips — they are `pytest.importorskip("xgboost")` at test_eva_sdm.py:427 and `pytest.importorskip("lightgbm")` at test_eva_sdm.py:476. Both `xgboost` and `lightgbm` are also in `requirements.txt` but missing from the env — same drift class as pygam/pykrige, excluded from this plan's scope by intent. See "Not fixing here" for the separate deliverable that would flip those 8 skips to passes.)

If any tests still fail, drill into them with:
```bash
micromamba run -n shiny python -m pytest tests/test_eva_sdm.py -x --tb=short 2>&1 | tail -40
```

A residual failure would most likely be:
- A test that depended on a specific `pykrige` API shape that changed between 1.7.0 and 1.7.3. Triage: is the test's assertion out of date, or does `eva_sdm.py` use a deprecated API? Either way, that's a separate bug outside this env-repair plan's scope — STOP and report.
- A transitive-dep conflict (e.g., `scipy` version mismatch manifesting at runtime). Rerun `Step 0.1` and compare tracebacks.

- [ ] **Step 2.2: Confirm kriging test in `test_sdm_analyse.py` flips skip → pass**

This is a downstream side-effect of the fix, not a regression. The test `tests/test_sdm_analyse.py::TestCompareMethodsCoordCols::test_kriging_method_accepts_aliased_coord_cols` is gated by `pytest.importorskip("pykrige")`. With pykrige now importable, it will execute instead of skip.

```bash
micromamba run -n shiny python -m pytest tests/test_sdm_analyse.py --tb=line -q 2>&1 | tail -10
```

**Expected (after the fix):**
```
18 passed in Ns
```

(Previously: 17 passed, 1 skipped. Now: 18 passed, 0 skipped. The kriging test should pass under real pykrige because the fix from PR #2 threaded `lat_col`/`lon_col` into both `_sites_to_metric` and `fit_kriging`.)

**If the newly-un-skipped test FAILS**, that's a genuine bug in the PR #2 fix — triage: read the actual error, check whether `fit_kriging` received the right kwargs. It would mean my Task 3 + `eef53c2` fix wasn't sufficient for the real kriging path. Unlikely given the combined threading is complete, but possible.

## Task 3: Run the full test suite (per-file due to Windows segfault)

**Files:** none changed.

**Context:** Windows Python + openpyxl has a documented C-extension segfault when pytest collects multiple test modules in one run (see `C:\Users\arturas.baziukas\.claude\projects\…\memory\project_test_suite_collection_failures.md`). The workaround is per-file invocation.

- [ ] **Step 3.1: Per-file sweep**

```bash
for f in tests/test_*.py; do
    echo "=== $f ==="
    micromamba run -n shiny python -m pytest "$f" --tb=line -q 2>&1 | tail -3
done
```

**Expected:**
- Every file reports all-passed or passed-with-skipped — no failures anywhere.
- `tests/test_eva_sdm.py` → 39 passed, 8 skipped.
- `tests/test_sdm_analyse.py` → 18 passed.
- All other test files unchanged (PA tests, EVA tests, etc.).

**If a test file that was green before this plan turns red**, it means `pygam`/`pykrige`/`gstools` installed a conflicting version of a shared dep (most likely `scipy` or `numpy`). Diagnose with `micromamba list -n shiny | grep -iE "scipy|numpy"` and compare against what the failing test imports. If confirmed, downgrade the conflicting dep or pin it in requirements.

## Fallback: pip install (only if conda-forge unavailable/failed at Task 1)

Per `~/.claude/CLAUDE.md`: "Never use `pip install` unless a package is unavailable on conda-forge." All three are available, so this section is only invoked if Task 1.1 fails for a package-specific reason.

- [ ] **Step F.1: Install the failing package(s) via pip inside the env**

```bash
micromamba run -n shiny python -m pip install 'pygam>=0.9.0'   # example for one package
```

(Using `python -m pip` instead of plain `pip` guarantees the pip binary matches the Python binary being invoked — eliminates any PATH-shadowing risk on Windows.)

(Repeat per missing package — same version floors as `requirements.txt`.)

- [ ] **Step F.2: Verify importability** — same as Step 1.2 above.

- [ ] **Step F.3: Continue from Task 2**.

**Risk of pip fallback:** pip may install wheels compiled against a different `numpy` / `scipy` ABI than the conda-forge builds in the rest of the env. If runtime errors appear in Task 2 (e.g., `RuntimeError: numpy ABI mismatch`), the package needs a conda-forge build — re-try Task 1 with a specific pinned version, or accept the ABI mismatch as a blocker and re-plan.

## Not fixing here (explicitly out of scope)

- **The server-side env on `laguna.ku.lt`** — verified during plan review (2026-04-23): `/opt/micromamba/envs/shiny/` has `pygam`, `pykrige`, `gstools`, and `xgboost` all importing cleanly. The production app's SDM features (GAM fitting, kriging, method comparison) are NOT affected by the drift that broke the local env — the two envs share a name but have evolved independently. No server-side action needed for this plan.

  One unrelated finding surfaced during that same check: `import lightgbm` fails on the server with `AttributeError: module 'cupy' has no attribute 'ndarray'` coming from `dask.array.chunk_types`. That's a pre-existing server-env bug in a different code path (not triggered by any of the 14 failing tests here) — likely caused by the `zarr<3.0` pin's ripple effect on `dask`/`cupy`. Surfacing it here for the record; fixing it is a separate deliverable.
- **Upgrading Python minor version in the env** — the env runs 3.13.12, which is fine for all three packages at their latest conda-forge builds.
- **Adding an env-drift check to the deploy script** — would catch this class of issue automatically but is a separate deliverable.
- **Removing `pygam`/`pykrige`/`gstools` from `requirements.txt`** — they are genuinely used by `eva_sdm.py`; the bug was the env, not the requirements.

## Self-review checklist

- [x] **Placeholder scan** — every step has an exact command, an exact expected output, and a specific STOP condition for unexpected results.
- [x] **Command correctness** — every `micromamba run -n shiny` invocation has a valid python -c body; every `micromamba install` specifies the `-n shiny` and `-c conda-forge` flags; `-y` avoids interactive confirmation.
- [x] **Test-counts are concrete** — baseline `14 failed / 25 passed / 8 skipped` and target `39 passed / 8 skipped` are pinned; `test_sdm_analyse.py` target `18 passed / 0 skipped` accounts for the importorskip flip.
- [x] **Downstream side-effect acknowledged** — the `test_sdm_analyse.py` kriging test change from skip-to-pass is documented as expected, not a regression.
- [x] **Fallback path defined** — pip-install fallback exists but is gated on conda-forge availability failing first.
- [x] **Out-of-scope boundary** — server-side, requirements.txt edits, deploy script hardening all explicitly excluded.

## Execution handoff

This plan has a single non-trivial step (the `micromamba install`) and a verification cascade. It can be executed inline in the current session — no need for subagent dispatching. The install itself is a one-shot command; everything else is verification.

If anything unexpected happens at Step 0, 1.1, 1.2, 2.1, 2.2, or 3.1, the plan's STOP conditions trigger and the operator must re-diagnose before continuing.
