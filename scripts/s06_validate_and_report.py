"""Step 06: Validate corrected layers and generate a Markdown report."""
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from scripts.config import (
    OUTPUT_DIR,
    TARGET_CRS,
    EVA_CLASS_BINS,
    EVA_CLASS_LABELS,
)
from scripts.s01_clean_sentinels import find_aq_columns


# ---------------------------------------------------------------------------
# Validation check functions — each takes a GeoDataFrame and returns bool
# ---------------------------------------------------------------------------

def check_no_sentinels(gdf: gpd.GeoDataFrame) -> bool:
    """Return True if no AQ column has values <= -9998."""
    aq_cols = find_aq_columns(gdf.columns)
    for col in aq_cols:
        vals = pd.to_numeric(gdf[col], errors="coerce")
        if (vals <= -9998).any():
            return False
    return True


def check_aq_range(gdf: gpd.GeoDataFrame) -> bool:
    """Return True if all AQ values are in [0, 5] or NaN."""
    aq_cols = find_aq_columns(gdf.columns)
    for col in aq_cols:
        vals = pd.to_numeric(gdf[col], errors="coerce").dropna()
        if len(vals) == 0:
            continue
        if (vals < 0).any() or (vals > 5).any():
            return False
    return True


def check_crs(gdf: gpd.GeoDataFrame, target_crs: str) -> bool:
    """Return True if the GeoDataFrame's CRS matches the target EPSG."""
    if gdf.crs is None:
        return False
    from pyproj import CRS
    return CRS(gdf.crs) == CRS(target_crs)


def check_has_subzone_id(gdf: gpd.GeoDataFrame) -> bool:
    """Return True if the Subzone_ID column exists."""
    return "Subzone_ID" in gdf.columns


def check_total_ev(gdf: gpd.GeoDataFrame) -> bool:
    """Return True if TotalEV_MAX equals max of EC score columns (tolerance 0.01).

    Skips rows where TotalEV_MAX is absent or NaN.
    """
    if "TotalEV_MAX" not in gdf.columns:
        return True  # nothing to validate

    from scripts.config import EC_SCORE_COLUMNS
    ec_cols = [c for c in EC_SCORE_COLUMNS.values() if c in gdf.columns]
    if not ec_cols:
        return True

    sub = gdf[["TotalEV_MAX"] + ec_cols].copy()
    sub = sub.dropna(subset=["TotalEV_MAX"])
    if len(sub) == 0:
        return True

    row_max = sub[ec_cols].max(axis=1)
    return bool((np.abs(sub["TotalEV_MAX"] - row_max) <= 0.01).all())


def check_confidence_present(gdf: gpd.GeoDataFrame) -> bool:
    """Return True if Confidence and Confidence_Class columns exist."""
    return "Confidence" in gdf.columns and "Confidence_Class" in gdf.columns


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

_CHECKS = [
    ("No sentinels (<= -9998)", check_no_sentinels),
    ("AQ values in [0, 5]", check_aq_range),
    ("CRS matches target", lambda gdf: check_crs(gdf, TARGET_CRS)),
    ("Subzone_ID present", check_has_subzone_id),
    ("TotalEV_MAX consistency", check_total_ev),
    ("Confidence columns present", check_confidence_present),
]


def _distribution_section(gdf: gpd.GeoDataFrame) -> str:
    """Build Markdown distribution sections for TotalEV, Dominant_EC, Confidence."""
    lines: list[str] = []

    # TotalEV 5-class distribution
    if "TotalEV_MAX" in gdf.columns:
        lines.append("\n### TotalEV 5-class distribution\n")
        classes = pd.cut(
            gdf["TotalEV_MAX"].dropna(),
            bins=EVA_CLASS_BINS,
            labels=EVA_CLASS_LABELS,
            include_lowest=True,
        )
        counts = classes.value_counts().sort_index()
        lines.append("| Class | Count |")
        lines.append("|-------|------:|")
        for label in EVA_CLASS_LABELS:
            lines.append(f"| {label} | {counts.get(label, 0)} |")

    # Dominant EC distribution
    if "Dominant_EC" in gdf.columns:
        lines.append("\n### Dominant EC distribution\n")
        counts = gdf["Dominant_EC"].value_counts().sort_index()
        lines.append("| EC | Count |")
        lines.append("|----|------:|")
        for ec, cnt in counts.items():
            lines.append(f"| {ec} | {cnt} |")

    # Confidence distribution
    if "Confidence_Class" in gdf.columns:
        lines.append("\n### Confidence distribution\n")
        counts = gdf["Confidence_Class"].value_counts()
        lines.append("| Class | Count |")
        lines.append("|-------|------:|")
        for cls in ["Low", "Medium", "High"]:
            lines.append(f"| {cls} | {counts.get(cls, 0)} |")

    return "\n".join(lines)


def run():
    """Read all files in OUTPUT_DIR, run checks, write validation_report.md."""
    out = Path(OUTPUT_DIR)
    if not out.exists():
        print(f"  OUTPUT_DIR not found: {OUTPUT_DIR}")
        return

    extensions = (".gpkg", ".shp")
    files = sorted(
        p for p in out.iterdir()
        if p.suffix in extensions and p.is_file()
    )
    if not files:
        print("  No spatial files found in OUTPUT_DIR.")
        return

    report_lines: list[str] = ["# EVA_FINAL Validation Report\n"]

    for fpath in files:
        fname = fpath.name
        print(f"  Validating: {fname}")
        gdf = gpd.read_file(str(fpath))

        report_lines.append(f"\n## {fname}\n")
        report_lines.append("| Check | Result |")
        report_lines.append("|-------|--------|")
        for name, fn in _CHECKS:
            try:
                passed = fn(gdf)
            except Exception as exc:
                passed = False
                name = f"{name} (error: {exc})"
            status = "PASS" if passed else "FAIL"
            report_lines.append(f"| {name} | {status} |")

        report_lines.append(_distribution_section(gdf))

    report_path = out / "validation_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"  Report written: {report_path}")


if __name__ == "__main__":
    run()
