"""Step 05: Compute confidence scores for each feature based on its Dominant EC."""
import os

import geopandas as gpd
import numpy as np

from scripts.config import EC_CONFIDENCE, OUTPUT_DIR, COMBINED_LAYER


def compute_ec_confidence(n_answered: int, n_max: int, weight: int) -> float:
    """Compute confidence score: (n_answered * weight) / n_max, range 0-5.

    Returns 0.0 when n_max is zero.
    """
    if n_max == 0:
        return 0.0
    return min((n_answered * weight) / n_max, 5.0)


def classify_confidence(score: float) -> str:
    """Classify a confidence score into Low / Medium / High.

    Thresholds are calibrated for the current EC_CONFIDENCE weights (max weight=3):
      - Maximum achievable score (when n_answered == n_max) = weight = 3.0
      - Low:    score <= 1.0  (≤ 33% of max)
      - Medium: 1.0 < score <= 2.0  (33–67% of max)
      - High:   score > 2.0  (> 67% of max)
    """
    if score <= 1.0:
        return "Low"
    elif score <= 2.0:
        return "Medium"
    else:
        return "High"


def assign_confidence(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add Confidence and Confidence_Class columns based on Dominant_EC.

    Looks up each feature's Dominant_EC in EC_CONFIDENCE to obtain
    (n_answered, n_max, weight) and computes the score.  If Dominant_EC is
    None/NaN or not found in EC_CONFIDENCE the result is NaN.
    """
    gdf = gdf.copy()

    confidence = []
    conf_class = []

    for ec in gdf["Dominant_EC"]:
        if ec is None or (isinstance(ec, float) and np.isnan(ec)) or ec not in EC_CONFIDENCE:
            confidence.append(np.nan)
            conf_class.append(np.nan)
        else:
            n_answered, n_max, weight = EC_CONFIDENCE[ec]
            score = compute_ec_confidence(n_answered, n_max, weight)
            confidence.append(score)
            conf_class.append(classify_confidence(score))

    gdf["Confidence"] = confidence
    gdf["Confidence_Class"] = conf_class
    return gdf


def run():
    """Read combined layer from OUTPUT_DIR, assign confidence, write back."""
    src = os.path.join(OUTPUT_DIR, COMBINED_LAYER)
    if not os.path.exists(src):
        print(f"  SKIP (not found): {src}")
        return

    print(f"  Processing: {COMBINED_LAYER}")
    gdf = gpd.read_file(src)
    gdf = assign_confidence(gdf)
    gdf.to_file(src, driver="GPKG")
    print(f"  Written: {src}")


if __name__ == "__main__":
    run()
