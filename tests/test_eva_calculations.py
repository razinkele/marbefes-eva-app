"""
Comprehensive test suite for eva_calculations.py

Tests cover: detect_data_type, rescale_qualitative, rescale_quantitative,
classify_features, calculate_aq9_special, calculate_all_aqs, calculate_ev,
and get_aq_status.
"""

import sys
import os
import numpy as np
import pandas as pd
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from eva_calculations import (
    detect_data_type,
    rescale_qualitative,
    rescale_quantitative,
    classify_features,
    calculate_aq9_special,
    calculate_all_aqs,
    calculate_ev,
    get_aq_status,
)
from eva_config import MAX_EV_SCALE


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_test_df(n_subzones, n_features, data_type="qualitative", seed=42):
    """Generate a test DataFrame with Subzone ID and feature columns."""
    rng = np.random.RandomState(seed)
    data = {"Subzone ID": [f"SZ_{i+1}" for i in range(n_subzones)]}
    for j in range(n_features):
        if data_type == "qualitative":
            data[f"Feature_{j+1}"] = rng.choice([0, 1], size=n_subzones)
        else:
            data[f"Feature_{j+1}"] = rng.uniform(0, 100, size=n_subzones).round(2)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# TestDetectDataType
# ---------------------------------------------------------------------------

class TestDetectDataType:

    def test_binary_data(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [0, 1, 1],
            "Sp2": [1, 0, 0],
        })
        assert detect_data_type(df) == "qualitative"

    def test_continuous_data(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [0.5, 2.3, 10.7],
            "Sp2": [100.1, 0.0, 55.5],
        })
        assert detect_data_type(df) == "quantitative"

    def test_empty_features(self):
        df = pd.DataFrame({"Subzone ID": ["A", "B"]})
        assert detect_data_type(df) == "qualitative"

    def test_mixed_mostly_binary(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C", "D"],
            "Sp1": [0, 1, 1, 0],
            "Sp2": [1, 0, 0, 1],
            "Sp3": [1, 1, 0, 0],
            "Sp4": [0.5, 2.3, 10.7, 50.0],
        })
        assert detect_data_type(df) == "qualitative"


# ---------------------------------------------------------------------------
# TestRescaleQualitative
# ---------------------------------------------------------------------------

class TestRescaleQualitative:

    def test_basic(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B"],
            "Sp1": [1, 0],
        })
        result = rescale_qualitative(df)
        assert result["Sp1"].iloc[0] == MAX_EV_SCALE
        assert result["Sp1"].iloc[1] == 0

    def test_nan_handling(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [1, np.nan, 0],
        })
        result = rescale_qualitative(df)
        assert result["Sp1"].iloc[1] == 0  # NaN → 0
        assert not result["Sp1"].isna().any()

    def test_all_zeros(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B"],
            "Sp1": [0, 0],
        })
        result = rescale_qualitative(df)
        assert (result["Sp1"] == 0).all()


# ---------------------------------------------------------------------------
# TestRescaleQuantitative
# ---------------------------------------------------------------------------

class TestRescaleQuantitative:

    def test_basic_minmax(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [0, 5, 10],
        })
        result = rescale_quantitative(df)
        assert result["Sp1"].iloc[0] == pytest.approx(0.0)
        assert result["Sp1"].iloc[1] == pytest.approx(2.5)
        assert result["Sp1"].iloc[2] == pytest.approx(5.0)

    def test_nan_not_bias_min(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [10.0, 20.0, np.nan],
        })
        result = rescale_quantitative(df)
        # min should be 10, max 20 → 10→0, 20→5
        assert result["Sp1"].iloc[0] == pytest.approx(0.0)
        assert result["Sp1"].iloc[1] == pytest.approx(5.0)
        # NaN filled with 0 then rescaled: (0-10)/(20-10)*5 = -5
        # The implementation fills NaN with 0 *before* rescaling from true range
        # so the NaN slot gets (0-10)/(20-10)*5 = -5
        # This is the actual behavior — document it.
        assert pd.notna(result["Sp1"].iloc[2])

    def test_constant_column(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [7.0, 7.0, 7.0],
        })
        result = rescale_quantitative(df)
        assert (result["Sp1"] == 0).all()

    def test_all_nan_column(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B"],
            "Sp1": [np.nan, np.nan],
        })
        result = rescale_quantitative(df)
        assert (result["Sp1"] == 0).all()


# ---------------------------------------------------------------------------
# TestClassifyFeatures
# ---------------------------------------------------------------------------

class TestClassifyFeatures:

    def test_lrf_threshold(self):
        """Feature in 1 of 100 subzones (1%) → LRF=1."""
        n = 100
        data = {"Subzone ID": [f"SZ_{i}" for i in range(n)]}
        vals = [0] * n
        vals[0] = 1  # only 1 positive
        data["Sp1"] = vals
        df = pd.DataFrame(data)
        cls = classify_features(df, {})
        assert cls["LRF"]["Sp1"] == 1
        assert cls["ROF"]["Sp1"] == 0

    def test_rof_common(self):
        """Feature in 50 of 100 subzones (50%) → ROF=1."""
        n = 100
        vals = [1] * 50 + [0] * 50
        df = pd.DataFrame({"Subzone ID": [f"SZ_{i}" for i in range(n)], "Sp1": vals})
        cls = classify_features(df, {})
        assert cls["LRF"]["Sp1"] == 0
        assert cls["ROF"]["Sp1"] == 1

    def test_absent_feature_neither(self):
        """All-zero column → LRF=0, ROF=0 (critical bug fix)."""
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [0, 0, 0],
        })
        cls = classify_features(df, {})
        assert cls["LRF"]["Sp1"] == 0
        assert cls["ROF"]["Sp1"] == 0

    def test_user_classifications(self):
        """User marks feature as RRF."""
        df = pd.DataFrame({
            "Subzone ID": ["A", "B"],
            "Sp1": [1, 0],
        })
        user = {"Sp1": ["RRF"]}
        cls = classify_features(df, user)
        assert cls["RRF"]["Sp1"] == 1


# ---------------------------------------------------------------------------
# TestCalculateEV
# ---------------------------------------------------------------------------

class TestCalculateEV:

    def test_qualitative_max(self):
        aq_results = pd.DataFrame({
            "Subzone ID": ["A"],
            "AQ1": [2.0],
            "AQ3": [4.0],
            "AQ5": [1.0],
            "AQ7": [3.0],
            "AQ10": [0.0],
            "AQ12": [0.0],
            "AQ14": [0.0],
        })
        ev = calculate_ev(aq_results, "qualitative")
        assert ev[0] == pytest.approx(4.0)

    def test_quantitative_max(self):
        aq_results = pd.DataFrame({
            "Subzone ID": ["A"],
            "AQ2": [1.0],
            "AQ4": [0.0],
            "AQ6": [0.0],
            "AQ8": [3.5],
            "AQ9": [2.0],
            "AQ11": [0.0],
            "AQ13": [0.0],
            "AQ15": [0.0],
        })
        ev = calculate_ev(aq_results, "quantitative")
        assert ev[0] == pytest.approx(3.5)

    def test_all_nan_gives_zero(self):
        aq_results = pd.DataFrame({
            "Subzone ID": ["A"],
            "AQ1": [np.nan],
            "AQ3": [np.nan],
            "AQ5": [np.nan],
            "AQ7": [np.nan],
            "AQ10": [np.nan],
            "AQ12": [np.nan],
            "AQ14": [np.nan],
        })
        ev = calculate_ev(aq_results, "qualitative")
        assert ev[0] == pytest.approx(0.0)

    def test_unknown_datatype(self):
        aq_results = pd.DataFrame({
            "Subzone ID": ["A", "B"],
            "AQ1": [1.0, 2.0],
        })
        ev = calculate_ev(aq_results, "unknown")
        assert ev == [0, 0]


# ---------------------------------------------------------------------------
# TestGetAqStatus
# ---------------------------------------------------------------------------

class TestGetAqStatus:

    def _base_classifications(self):
        """Return a classifications dict where every feature has no special tags."""
        return {"Feature_1": []}

    def test_qualitative_aqs_active(self):
        cls = {"Feature_1": ["ROF"]}
        statuses = get_aq_status("qualitative", cls, {})
        # Qualitative AQs that need no special classification should be active
        assert statuses["AQ7"][0] == "active"
        # Quantitative AQs should be inactive
        assert statuses["AQ8"][0] == "inactive"

    def test_aq7_always_active(self):
        """AQ7 should be active for qualitative data even with no NRF features."""
        cls = {"Feature_1": []}
        statuses = get_aq_status("qualitative", cls, {})
        assert statuses["AQ7"][0] == "active"

    def test_aq3_inactive_without_rrf(self):
        cls = {"Feature_1": []}
        statuses = get_aq_status("qualitative", cls, {})
        assert statuses["AQ3"][0] == "inactive"
        assert "RRF" in statuses["AQ3"][1]

    def test_aq5_inactive_without_nrf(self):
        cls = {"Feature_1": []}
        statuses = get_aq_status("qualitative", cls, {})
        assert statuses["AQ5"][0] == "inactive"
        assert "NRF" in statuses["AQ5"][1]


# ---------------------------------------------------------------------------
# TestCalculateAllAqs
# ---------------------------------------------------------------------------

class TestCalculateAllAqs:

    def test_qualitative_basic(self):
        """Simple qualitative data → AQ7 (all features) should have non-zero values."""
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [1, 0, 1],
            "Sp2": [0, 1, 1],
        })
        rescaled_qual = rescale_qualitative(df)
        rescaled_quant = rescale_quantitative(df)
        cls = classify_features(df, {})
        aq9 = calculate_aq9_special(df, cls)

        results = calculate_all_aqs(df, "qualitative", rescaled_qual, rescaled_quant, aq9, cls)

        assert "AQ7" in results.columns
        # Row 2 (index 2) has both features present → AQ7 should be 5.0
        assert results["AQ7"].iloc[2] == pytest.approx(MAX_EV_SCALE)
        # Quantitative AQs should be NaN
        assert pd.isna(results["AQ8"].iloc[0])

    def test_quantitative_basic(self):
        """Simple quantitative data → AQ8 should have values for ROF features."""
        n = 20
        df = _make_test_df(n, 3, data_type="quantitative")
        rescaled_qual = rescale_qualitative(df)
        rescaled_quant = rescale_quantitative(df)
        cls = classify_features(df, {})
        aq9 = calculate_aq9_special(df, cls)

        results = calculate_all_aqs(df, "quantitative", rescaled_qual, rescaled_quant, aq9, cls)

        assert "AQ8" in results.columns
        # With 20 subzones and random data, features should be ROF (>5% present)
        # so AQ8 should have non-NaN values
        rof_count = sum(cls["ROF"][c] for c in cls["ROF"])
        if rof_count > 0:
            assert results["AQ8"].notna().any()
        # Qualitative AQs should be NaN
        assert pd.isna(results["AQ7"].iloc[0])
