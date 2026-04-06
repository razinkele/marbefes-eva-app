# Copilot Instructions — MARBEFES EVA

## What this project is

A Python Shiny web application implementing the **Ecological Value Assessment (EVA)** framework for the MARBEFES Horizon Europe project. It scores marine ecosystem components (species/habitats) across spatial subzones using 15 standardised Assessment Questions (AQ1–AQ15), producing Ecological Value (EV) scores on a 0–5 scale. It also includes a **Physical Accounts** module for SEEA EA natural capital accounting.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app locally (uses conda 'shiny' env, auto-reload on file changes)
conda run -n shiny python -m shiny run app.py --port 8000 --reload

# Run all tests
conda run -n shiny python -m pytest tests/ -v

# Run a single test file
conda run -n shiny python -m pytest tests/test_eva_calculations.py

# Run a single test by name
conda run -n shiny python -m pytest tests/test_eva_calculations.py::TestDetectDataType::test_binary_data
```

## Architecture

The app is split into **EVA** and **Physical Accounts (PA)** modules, each with a parallel set of files:

| Layer | EVA | Physical Accounts |
|---|---|---|
| Config / constants | `eva_config.py` | `pa_config.py` |
| Pure calculation functions | `eva_calculations.py` | `pa_calculations.py` |
| Excel export | `eva_export.py` | `pa_export.py` |

Additional modules:
- **`app.py`** — Shiny server logic; all `reactive.Value` state lives here
- **`eva_ui.py`** — All Shiny UI definitions (extracted from `app.py`)
- **`eva_map.py`** — Folium/Leaflet choropleth map rendering
- **`eva_hexgrid.py`** — Uber H3 hexagonal grid generation
- **`eva_visualizations.py`** — Plotly charts (bar, heatmap)
- **`eva_config.py`** — Single source of truth for all constants (AQ lists, thresholds, colours, export styles)
- **`version.py`** — Single source of truth for version strings; import `__version__` from here
- **`eunis_data.py`** — Pure functions for EUNIS L3 habitat overlay processing (EUSeaMap 2007/2012 codes like `A5.25`); note this uses **different codes** than `pa_config.EUNIS_LOOKUP` which uses 2022 codes like `MA12`
- **`dwca_reader.py`** — Darwin Core Archive parser: converts DwC-A zip (Event core + Occurrence extension) into the subzone × species matrix the app expects
- **`scripts/`** — Standalone data processing pipeline for EVA_FINAL results (not part of the web app)

## Key conventions

### Calculation modules are pure and stateless
`eva_calculations.py` and `pa_calculations.py` contain **only** pure functions with no Shiny imports or side effects. All reactive state stays in `app.py`.

### EV is MAX, not average
`EV = MAX(applicable AQs)` — never sum or average. Qualitative EV uses `MAX(AQ1,3,5,7,10,12,14)`; quantitative uses `MAX(AQ2,4,6,8,9,11,13,15)`.

### NaN semantics
AQs return `NaN` (not 0) when they don't apply (e.g., no LRF features defined → AQ1=NaN). NaN must propagate correctly — do **not** silently coerce to 0 in AQ calculations. The `rescale_*` functions fill NaN → 0 only at the rescaling stage.

### Data types
Input data is either `"qualitative"` (binary 0/1 presence-absence) or `"quantitative"` (continuous abundance). Auto-detection is in `detect_data_type()`. Each AQ number has a paired qualitative/quantitative version (odd = qualitative, even = quantitative, except AQ9 which is quantitative-only).

### Feature classification tags
User-defined classifications are stored as a `dict[str, list[str]]` mapping feature name → list of tags from `{'RRF', 'NRF', 'ESF', 'HFS_BH', 'SS'}`. LRF and ROF are auto-detected from data (threshold in `LOCALLY_RARE_THRESHOLD = 0.05`).

### Multi-EC support
Multiple Ecosystem Components can be loaded simultaneously. Active EC state is in `ec_store` (a `dict[ec_name, ECEntry]`) and `current_ec` reactive values in `app.py`. `ECEntry` is a dataclass defined in `eva_config.py` that also supports dict-like access for backward compatibility.

### XSS sanitisation
All user-supplied strings rendered in HTML must be passed through `html_escape` (imported from `html` in `app.py`).

### Versioning
`version.py` is the single source of truth. Semantic versioning: MAJOR = breaking data/methodology change, MINOR = new features, PATCH = bug fixes. EVA and PA modules have independent version numbers (`EVA_MODULE_VERSION`, `PA_MODULE_VERSION`).

### Spatial data
All spatial data is standardised to **WGS84 (EPSG:4326)** for display. For area calculations, `pa_calculations._reproject_to_metric()` auto-detects UTM zone from centroid, falling back to EPSG:3857.

## Known past issues to watch for

- **AQ7 score mapping** — was previously inverted; verify carefully after any AQ mapping changes
- **NaN in rescaling** — `rescale_quantitative` must exclude NaN from min/max (use pandas default `skipna=True`)
- **Total EV aggregation** — must use MAX across subzones, not SUM
- **Constant-value columns** — division-by-zero in `rescale_quantitative` when all values are identical; handled by the `max_val == min_val` branch

## DwC-A input

`dwca_reader.py` reads Darwin Core Archive zip files as an alternative to plain CSV upload. The archive must contain:
- `meta.xml` — describes the layout (detected via `is_dwca_zip()`)
- A core file (Event core, sampling events = subzones)
- An extension file (Occurrence, species linked via `eventID`)

The reader outputs the same subzone × species matrix format as the CSV path, so the rest of the app is unaware of the source format. The test archive `data/dwca-macrosoft-v2.1.zip` is used by `tests/test_dwca_reader.py`; tests are skipped if the file is absent.

## scripts/ data pipeline

Standalone scripts for post-processing exported EVA results — **not** loaded by the web app. Run from the project root:

```bash
python -m scripts.run_all          # run all 6 steps in sequence
python -m scripts.s04_recompute_total_ev  # run a single step
```

Steps (run in order, each calls `mod.run()`):
1. `s01_clean_sentinels` — remove sentinel/fill values
2. `s02_standardize_crs` — reproject to WGS84
3. `s03_add_subzone_ids` — ensure Subzone ID column present
4. `s04_recompute_total_ev` — recalculate Total EV using MAX aggregation
5. `s05_compute_confidence` — confidence scoring
6. `s06_validate_and_report` — validation and summary report

Scripts read from `EVA_FINAL` and `EVA_FINAL_corrected` directories configured inside each script (or via environment variables). Pipeline stops on first failure.

## Tutorial data

`tutorial/` contains the Lithuanian BBT5 sample dataset for the guided walkthrough (`docs/TUTORIAL.md`):

| File | Contents |
|---|---|
| `benthos.csv` | Zoobenthos abundance (quantitative) |
| `fish.csv` | Fish CPUE scores (quantitative) |
| `habitats.csv` | Benthic habitat presence/absence (qualitative) |
| `zooplankton.csv` | Zooplankton abundance (quantitative) |
| `phytoplankton.csv` | Phytoplankton biomass (quantitative) |
| `grid.geojson` | 425-cell hexagonal grid, EPSG:4326 |
| `eunis_l3_lithuanian.gpkg` | EUNIS L3 overlay for Physical Accounts BBT8 |

Source CRS for the raw data is EPSG:3346 (LKS94 Lithuania TM); `grid.geojson` is already in WGS84.

## Deployment — laguna.ku.lt (production)

**Live URL:** http://laguna.ku.lt:3838/sample-apps/EVA/  
**Server path:** `/srv/shiny-server/sample-apps/EVA/`  
**SSH user:** `razinka` (has sudo)  
**Runtime:** Python venv at `/srv/shiny-server/sample-apps/EVA/venv/`, served by `shiny-server` systemd service

### Pre-deployment checklist (do not skip)

1. All tests pass — `conda run -n shiny python -m pytest tests/ -v`
2. Required files present: `app.py`, `requirements.txt`, `www/marbefes.png`, `www/iecs.png`
3. No uncommitted changes to core files: `git status --short app.py eva_*.py pa_*.py requirements.txt`
4. Confirm with the user before running the script

### Deploy

```bash
bash deploy_to_laguna_razinka.sh
```

The script runs 10 steps: checks local files → tests SSH → creates remote dir → uploads files → creates venv → installs deps → sets permissions → verifies import → configures shiny-server → restarts service.

### Operational commands (run from local machine)

```bash
# Check server status
bash deploy_to_laguna_razinka.sh --status

# Restart without redeploying
bash deploy_to_laguna_razinka.sh --restart

# Tail live logs
bash deploy_to_laguna_razinka.sh --logs

# Or directly via SSH
ssh razinka@laguna.ku.lt 'sudo journalctl -u shiny-server -n 50'
ssh razinka@laguna.ku.lt 'sudo tail -f /var/log/shiny-server.log'
```

### Server-side details

- Systemd service name: `shiny-server`; unit file template: `marbefes-eva.service` in repo root
- App runs as user `shiny:shiny`
- Resource limits: 2 GB RAM, 200% CPU quota
- Logs: `/var/log/shiny-server/` and `journalctl -u shiny-server`
