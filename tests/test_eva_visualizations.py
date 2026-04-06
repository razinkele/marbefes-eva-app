"""Tests for eva_visualizations.py — all 6 chart functions."""

import pandas as pd
import pytest

from eva_visualizations import (
    create_aq_breakdown_chart,
    create_aq_heatmap,
    create_aq_histogram,
    create_aq_radar_chart,
    create_ev_bar_chart,
    create_feature_heatmap,
)


# ── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def results_df():
    return pd.DataFrame(
        {
            "Subzone ID": ["A", "B", "C"],
            "AQ1": [1.0, 2.0, 3.0],
            "AQ7": [2.0, 3.0, 4.0],
            "EV": [2.0, 3.0, 4.0],
        }
    )


@pytest.fixture()
def raw_df():
    return pd.DataFrame(
        {
            "Subzone ID": ["A", "B", "C"],
            "Sp1": [1, 0, 1],
            "Sp2": [0, 1, 1],
        }
    )


@pytest.fixture()
def no_aq_df():
    """DataFrame with no AQ columns."""
    return pd.DataFrame(
        {
            "Subzone ID": ["A", "B"],
            "EV": [1.0, 2.0],
        }
    )


@pytest.fixture()
def zero_aq_df():
    """DataFrame where all AQ columns are zero (inactive)."""
    return pd.DataFrame(
        {
            "Subzone ID": ["A", "B"],
            "AQ1": [0.0, 0.0],
            "AQ7": [0.0, 0.0],
            "EV": [1.0, 2.0],
        }
    )


# ── create_ev_bar_chart ────────────────────────────────────────────────


class TestCreateEvBarChart:
    def test_returns_html_with_div_id(self, results_df):
        html = create_ev_bar_chart(results_df)
        assert isinstance(html, str)
        assert 'id="ev_plot"' in html

    def test_contains_plotly_cdn(self, results_df):
        html = create_ev_bar_chart(results_df)
        assert "plotly" in html.lower()


# ── create_feature_heatmap ─────────────────────────────────────────────


class TestCreateFeatureHeatmap:
    def test_returns_html_with_div_id(self, raw_df):
        html = create_feature_heatmap(raw_df)
        assert isinstance(html, str)
        assert 'id="feature_plot"' in html

    def test_contains_plotly_cdn(self, raw_df):
        html = create_feature_heatmap(raw_df)
        assert "plotly" in html.lower()


# ── create_aq_breakdown_chart ──────────────────────────────────────────


class TestCreateAqBreakdownChart:
    def test_returns_html_with_div_id(self, results_df):
        html = create_aq_breakdown_chart(results_df)
        assert isinstance(html, str)
        assert 'id="aq_breakdown_plot"' in html

    def test_returns_none_when_no_aq_columns(self, no_aq_df):
        assert create_aq_breakdown_chart(no_aq_df) is None

    def test_returns_none_when_all_aq_zero(self, zero_aq_df):
        assert create_aq_breakdown_chart(zero_aq_df) is None


# ── create_aq_radar_chart ──────────────────────────────────────────────


class TestCreateAqRadarChart:
    def test_returns_html_with_div_id(self, results_df):
        html = create_aq_radar_chart(results_df, ["A", "B"])
        assert isinstance(html, str)
        assert 'id="radar_plot"' in html

    def test_returns_none_when_empty_selection(self, results_df):
        assert create_aq_radar_chart(results_df, []) is None

    def test_returns_none_when_no_aq_columns(self, no_aq_df):
        assert create_aq_radar_chart(no_aq_df, ["A"]) is None


# ── create_aq_heatmap ─────────────────────────────────────────────────


class TestCreateAqHeatmap:
    def test_returns_html_with_div_id(self, results_df):
        html = create_aq_heatmap(results_df, "Viridis")
        assert isinstance(html, str)
        assert 'id="aq_heatmap_plot"' in html

    def test_returns_none_when_no_aq_columns(self, no_aq_df):
        assert create_aq_heatmap(no_aq_df, "Viridis") is None


# ── create_aq_histogram ───────────────────────────────────────────────


class TestCreateAqHistogram:
    def test_returns_html_with_div_id(self, results_df):
        html = create_aq_histogram(results_df)
        assert isinstance(html, str)
        assert 'id="aq_plot"' in html

    def test_returns_none_when_no_aq_columns(self, no_aq_df):
        assert create_aq_histogram(no_aq_df) is None
