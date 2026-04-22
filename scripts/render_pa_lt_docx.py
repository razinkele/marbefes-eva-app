"""Render the Lithuanian BBT5 Physical Accounts report as a styled .docx.

Thin CLI wrapper around :mod:`pa_docx`. Reads the bundle produced by
``generate_pa_lt_report.py``:

  * ``accounts_lithuania/PA_report.md``                              narrative
  * ``accounts_lithuania/PhysicalAccounts_BBT8_LithuanianBBT5.xlsx`` data
  * ``accounts_lithuania/maps/*.png``                                figures

Writes ``accounts_lithuania/PA_report.docx``.

Run:
    micromamba run -n shiny python scripts/render_pa_lt_docx.py
"""
from __future__ import annotations

import io
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pa_docx  # noqa: E402  — after sys.path fix-up

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BUNDLE_DIR = PROJECT_ROOT / "accounts_lithuania"
MD_PATH = BUNDLE_DIR / "PA_report.md"
XLSX_PATH = BUNDLE_DIR / "PhysicalAccounts_BBT8_LithuanianBBT5.xlsx"
MAPS_DIR = BUNDLE_DIR / "maps"
OUT_PATH = BUNDLE_DIR / "PA_report.docx"

# Bundle-specific mapping between the DOCX figure keys and the PNG files
# on disk (produced by generate_pa_lt_report.py).
MAP_FILES = {
    "EUNIS_classes":     "EUNIS_classes.png",
    "habEV_classes":     "habEV_classes.png",
    "TotalEV_MAX":       "TotalEV_MAX.png",
    "AQ7_Habitats":      "AQ7_Habitats.png",
    "Benthos_MAX":       "Benthos_MAX.png",
    "AQ_Zooplankton":    "AQ_Zooplankton.png",
    "AQ_Phytoplankton":  "AQ_Phytoplankton.png",
}


def _load_maps(maps_dir: Path) -> dict[str, io.BytesIO]:
    """Read PNGs from the bundle into BytesIO buffers."""
    out: dict[str, io.BytesIO] = {}
    for key, fname in MAP_FILES.items():
        p = maps_dir / fname
        if p.exists():
            out[key] = io.BytesIO(p.read_bytes())
        else:
            logger.warning("Missing map: %s", p.name)
    return out


def main() -> None:
    if not MD_PATH.exists():
        raise FileNotFoundError(f"Missing {MD_PATH}")
    if not XLSX_PATH.exists():
        raise FileNotFoundError(f"Missing {XLSX_PATH}")

    logger.info("Reading %s", MD_PATH)
    md = MD_PATH.read_text(encoding="utf-8")

    logger.info("Reading %s", XLSX_PATH.name)
    extent = pd.read_excel(XLSX_PATH, sheet_name="extent")
    condition = pd.read_excel(XLSX_PATH, sheet_name="condition")
    supply = pd.read_excel(XLSX_PATH, sheet_name="supply")
    missing = pd.read_excel(XLSX_PATH, sheet_name="missing_values")
    readme = pd.read_excel(XLSX_PATH, sheet_name="ReadMe")

    # Normalize column names that differ between the LT pipeline and the
    # generic BBT8 schema used by pa_docx's detail tables.
    condition = condition.rename(columns={"habEV": "Habitat_EV"})

    generated = str(readme.loc[readme["Parameter"] == "Generated", "Value"].iloc[0])
    metadata = {
        "bbt_name": "Lithuanian BBT5 — Curonian Lagoon & Baltic Sea Coast",
        "generated": generated,
    }

    maps = _load_maps(MAPS_DIR)

    logger.info("Building DOCX")
    buf = pa_docx.build_docx_bytes(md, extent, condition, supply, missing, maps, metadata)

    OUT_PATH.write_bytes(buf.getvalue())
    logger.info("Saved %s", OUT_PATH)


if __name__ == "__main__":
    main()
