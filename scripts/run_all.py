"""Master script: run all data repair steps in sequence."""
import importlib
import logging
import os
import sys
import time

# Ensure project root is on sys.path so 'scripts' package is importable
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

STEPS = [
    ("01 -- Clean sentinels",       "scripts.s01_clean_sentinels"),
    ("02 -- Standardize CRS",       "scripts.s02_standardize_crs"),
    ("03 -- Add Subzone IDs",       "scripts.s03_add_subzone_ids"),
    ("04 -- Recompute Total EV",    "scripts.s04_recompute_total_ev"),
    ("05 -- Compute confidence",    "scripts.s05_compute_confidence"),
    ("06 -- Validate and report",   "scripts.s06_validate_and_report"),
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
            mod = importlib.import_module(module_name)
            mod.run()
            elapsed = time.time() - step_start
            logger.info("  Completed in %.1fs", elapsed)
        except Exception as e:
            logger.error("  FAILED: %s", e, exc_info=True)
            logger.error("  Pipeline stopped. Fix the issue and re-run.")
            sys.exit(1)

    total = time.time() - start
    logger.info("")
    logger.info("=" * 60)
    logger.info("  Pipeline complete in %.1fs", total)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
