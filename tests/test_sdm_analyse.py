"""Tests for scripts/sdm_analyse.py — the script's testable functions."""
import numpy as np
import pandas as pd
import pytest

from scripts.sdm_analyse import analyse_collinearity


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
