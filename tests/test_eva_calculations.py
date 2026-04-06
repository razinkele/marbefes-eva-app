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
        # NaN is replaced with 0 after rescaling (not before), so it maps to 0.0.
        assert pd.notna(result["Sp1"].iloc[2])
        assert result["Sp1"].iloc[2] == pytest.approx(0.0)

    def test_nan_stays_in_valid_range(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C", "D", "E"],
            "Sp1": [5.0, np.nan, 15.0, np.nan, 25.0],
            "Sp2": [np.nan, 10.0, np.nan, 20.0, 30.0],
        })
        result = rescale_quantitative(df)
        for col in ["Sp1", "Sp2"]:
            vals = result[col]
            assert vals.min() >= 0.0, f"{col} has value below 0"
            assert vals.max() <= MAX_EV_SCALE, f"{col} has value above {MAX_EV_SCALE}"

    def test_constant_column(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [7.0, 7.0, 7.0],
        })
        result = rescale_quantitative(df)
        assert (result["Sp1"] == MAX_EV_SCALE).all()

    def test_constant_zero_column(self):
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [0.0, 0.0, 0.0],
        })
        result = rescale_quantitative(df)
        assert (result["Sp1"] == 0).all()

    def test_constant_positive_gets_max_scale(self):
        """Uniform positive values should get MAX_EV_SCALE, not zero."""
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [3.5, 3.5, 3.5],
        })
        result = rescale_quantitative(df)
        assert (result["Sp1"] == MAX_EV_SCALE).all()

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

    def test_all_nan_column(self):
        """All-NaN feature should be neither LRF nor ROF."""
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [np.nan, np.nan, np.nan],
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

    def test_qualitative_aq7_hand_verified(self):
        """Hand-verified: 3 subzones, 3 features, qualitative.
        AQ7 = mean of rescaled values for ALL features.
        Feature present = 5, absent = 0. Mean of row values.

        Subzone A: [1, 0, 1] → rescaled [5, 0, 5] → AQ7 = 10/3 = 3.333
        Subzone B: [0, 1, 0] → rescaled [0, 5, 0] → AQ7 = 5/3 = 1.667
        Subzone C: [1, 1, 1] → rescaled [5, 5, 5] → AQ7 = 5.0
        """
        df = pd.DataFrame({
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [1, 0, 1],
            "Sp2": [0, 1, 1],
            "Sp3": [1, 0, 1],
        })
        rescaled_qual = rescale_qualitative(df)
        rescaled_quant = rescale_quantitative(df)
        cls = classify_features(df, {})
        aq9 = calculate_aq9_special(df, cls)
        results = calculate_all_aqs(df, "qualitative", rescaled_qual, rescaled_quant, aq9, cls)

        assert results["AQ7"].iloc[0] == pytest.approx(10/3, abs=0.01)  # A
        assert results["AQ7"].iloc[1] == pytest.approx(5/3, abs=0.01)   # B
        assert results["AQ7"].iloc[2] == pytest.approx(5.0)              # C

    def test_quantitative_aq8_hand_verified(self):
        """Hand-verified: AQ8 = mean of rescaled ROF feature values.
        10 subzones, 2 features. Both occur in >5% → both ROF.
        Feature X: values [0,1,2,3,4,5,6,7,8,9] → min-max rescaled to [0, 0.556, ..., 5.0]
        Feature Y: values [9,8,7,6,5,4,3,2,1,0] → same rescaling reversed
        AQ8 per subzone = mean of rescaled X and Y.
        Since X+Y=9 for all rows, rescaled_X + rescaled_Y ≈ 5.0, so AQ8 ≈ 2.5 for all.
        """
        df = pd.DataFrame({
            "Subzone ID": [f"S{i}" for i in range(10)],
            "X": list(range(10)),
            "Y": list(range(9, -1, -1)),
        })
        rescaled_qual = rescale_qualitative(df)
        rescaled_quant = rescale_quantitative(df)
        cls = classify_features(df, {})
        aq9 = calculate_aq9_special(df, cls)
        results = calculate_all_aqs(df, "quantitative", rescaled_qual, rescaled_quant, aq9, cls)

        # All subzones should have AQ8 ≈ 2.5 (mean of complementary rescaled values)
        for i in range(10):
            assert results["AQ8"].iloc[i] == pytest.approx(2.5, abs=0.1)

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


# ---------------------------------------------------------------------------
# TestAQ9Concentration
# ---------------------------------------------------------------------------

class TestAQ9Concentration:
    """Tests for AQ9 concentration-weighted calculation."""

    def _make_concentrated_df(self):
        """Two ROF features: A concentrated in 2/10, B evenly spread."""
        return pd.DataFrame({
            'Subzone ID': [f'S{i}' for i in range(10)],
            'A': [0, 0, 0, 0, 0, 0, 0, 0, 50, 50],
            'B': [8, 9, 10, 11, 12, 8, 9, 10, 11, 12],
        })

    def test_concentrated_feature_dominates(self):
        """Feature concentrated in few subzones should score higher than spread feature."""
        df = self._make_concentrated_df()
        cls = classify_features(df, {})
        aq9 = calculate_aq9_special(df, cls)

        assert aq9['A'].max() > aq9['B'].max()
        assert aq9['A'].max() == pytest.approx(MAX_EV_SCALE)

    def test_concentration_weighting_has_effect(self):
        """AQ9 should differ from naive normalize-by-mean rescaling."""
        df = self._make_concentrated_df()
        cls = classify_features(df, {})
        aq9 = calculate_aq9_special(df, cls)

        # Naive: normalize by mean, rescale per-feature to 0-5
        values_b = df['B'].fillna(0)
        normalized_b = values_b / values_b.mean()
        naive_b = MAX_EV_SCALE * normalized_b / normalized_b.max()

        # AQ9 for B should NOT match naive (concentration ratio should change it)
        assert not np.allclose(aq9['B'].values, naive_b.values, atol=1e-6)

    def test_aq9_differs_from_aq8(self):
        """AQ9 (concentration-weighted) and AQ8 (plain quantitative) should differ."""
        df = self._make_concentrated_df()
        cls = classify_features(df, {})
        rescaled_qual = rescale_qualitative(df)
        rescaled_quant = rescale_quantitative(df)
        aq9 = calculate_aq9_special(df, cls)

        results = calculate_all_aqs(df, "quantitative", rescaled_qual, rescaled_quant, aq9, cls)
        assert not np.allclose(results['AQ8'].values, results['AQ9'].values, atol=1e-6)

    def test_scale_invariance(self):
        """Doubling subzones with same proportions should give same CR ratios."""
        df10 = self._make_concentrated_df()
        cls10 = classify_features(df10, {})
        aq9_10 = calculate_aq9_special(df10, cls10)

        # Same pattern doubled
        df20 = pd.DataFrame({
            'Subzone ID': [f'S{i}' for i in range(20)],
            'A': [0]*16 + [50]*4,
            'B': [8, 9, 10, 11, 12] * 4,
        })
        cls20 = classify_features(df20, {})
        aq9_20 = calculate_aq9_special(df20, cls20)

        ratio_10 = aq9_10['A'].max() / aq9_10['B'].max()
        ratio_20 = aq9_20['A'].max() / aq9_20['B'].max()

        # Ratios should be identical (0% difference) with occurrence proportion
        assert ratio_10 == pytest.approx(ratio_20, rel=1e-6)

    def test_all_zero_feature(self):
        """Feature with all zeros should produce all-zero AQ9."""
        df = pd.DataFrame({
            'Subzone ID': ['S0', 'S1', 'S2'],
            'A': [0, 0, 0],
            'B': [10, 20, 30],
        })
        cls = classify_features(df, {})
        aq9 = calculate_aq9_special(df, cls)
        # A has proportion 0, so not ROF → all zeros
        assert (aq9['A'] == 0).all()

    def test_single_rof_feature(self):
        """Single ROF feature should rescale to 0-5."""
        df = pd.DataFrame({
            'Subzone ID': [f'S{i}' for i in range(10)],
            'X': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        })
        cls = classify_features(df, {})
        aq9 = calculate_aq9_special(df, cls)
        assert aq9['X'].max() == pytest.approx(MAX_EV_SCALE)
        assert aq9['X'].min() >= 0
