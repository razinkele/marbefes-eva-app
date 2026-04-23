"""Tests for scripts/sdm_analyse.py — the script's testable functions."""
import numpy as np
import pandas as pd
import pytest

from scripts.sdm_analyse import analyse_collinearity, _align_valid_for_residuals


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


class TestAlignValidForResiduals:
    """Helper extraction: the DataFrame rebuild that must align with what
    eva_sdm.prepare_features kept, so residual-kriging can safely assign
    a residual Series onto the surviving rows."""

    def test_helper_drops_species_nan(self):
        sites = pd.DataFrame({
            "sp": [1.0, 2.0, np.nan, 4.0],     # row index 2 has NaN response
            "depth_m": [10.0, 20.0, 30.0, 40.0],
            "slope": [0.1, 0.2, 0.3, 0.4],
        })
        valid = _align_valid_for_residuals(sites, ["depth_m", "slope"], "sp")
        assert len(valid) == 3                  # row 2 dropped
        assert valid["sp"].isna().sum() == 0

    def test_helper_drops_feature_nan(self):
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
        sites = pd.DataFrame({
            "sp": [1.0, np.nan, 3.0],
            "x": [1.0, 2.0, 3.0],
        })
        valid = _align_valid_for_residuals(sites, ["x"], "sp")
        assert list(valid.index) == [0, 1]

    def test_helper_ignores_all_nan_columns(self):
        """Mirror prepare_features: a column that is 100% NaN must not drop all rows."""
        sites = pd.DataFrame({
            "sp": [1.0, 2.0, 3.0],
            "depth_m": [10.0, 20.0, 30.0],
            "all_nan_feature": [np.nan, np.nan, np.nan],  # column fully NaN
        })
        valid = _align_valid_for_residuals(
            sites, ["depth_m", "all_nan_feature"], "sp"
        )
        assert len(valid) == 3, f"expected all 3 rows kept, got {len(valid)}"
