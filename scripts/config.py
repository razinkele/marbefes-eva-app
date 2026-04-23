"""Shared configuration for EVA_FINAL data repair pipeline.

Paths resolve in this order:
  1. Environment variable (``EVA_FINAL_DIR`` / ``EVA_FINAL_CORRECTED_DIR``)
  2. A sibling of the project root (``<repo>/../EVA_FINAL`` and
     ``<repo>/../EVA_FINAL_corrected``), matching the layout used by
     ``scripts/generate_pa_lt_report.py``.
"""
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(env_var: str, sibling_name: str) -> str:
    override = os.environ.get(env_var)
    if override:
        return os.path.normpath(override)
    return os.path.normpath(str(_PROJECT_ROOT.parent / sibling_name))


EVA_FINAL_DIR = _resolve("EVA_FINAL_DIR", "EVA_FINAL")
OUTPUT_DIR = _resolve("EVA_FINAL_CORRECTED_DIR", "EVA_FINAL_corrected")
TARGET_CRS = "EPSG:3346"
SENTINEL_THRESHOLD = -9998
EVA_SCALE_MIN = 0
EVA_SCALE_MAX = 5

EC_SCORE_COLUMNS = {
    "Habitats": "AQ7_HABITATS",
    "Zooplankton": "ZooScore",
    "Phytoplankton": "PhytoScore",
    "Benthos": "MaxBenthos",
    "Fish": "EVA_all_fish",
}

BENTHOS_AQ_COLUMNS = ["AQ6_benthos", "AQ8_benthos", "AQ9_benthos", "AQ13_benthos"]

EC_CONFIDENCE = {
    "Habitats":      (1, 7, 3),
    "Zooplankton":   (1, 7, 2),
    "Phytoplankton": (1, 7, 3),
    "Benthos":       (4, 8, 3),
    # "Fish_CL" and "Fish_BS" removed — these keys can never appear as
    # Dominant_EC because only EC_SCORE_COLUMNS keys ("Fish") are used.
    "Fish":          (2, 7, 3),
}

EVA_CLASS_BINS = [0, 1, 2, 3, 4, 5]
EVA_CLASS_LABELS = ["Very Low", "Low", "Medium", "High", "Very High"]

SENTINEL_FILES = [
    "ALL4EVA_2025_fixed_geometries.gpkg",
    "All4EVA_2025.gpkg",
    "NewBenthos.shp",
    "All_EVA_Sept_2025.shp",
    "final_EVA_without_Fish.gpkg",
]

CRS_FILES = [
    "chrophyta_score.gpkg",
    "copepoda_score.gpkg",
    "cladocera_score.gpkg",
]

COMBINED_LAYER = "ALL4EVA_2025_fixed_geometries.gpkg"
