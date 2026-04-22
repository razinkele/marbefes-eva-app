"""Tests for pa_calculations module."""

import sys
import os

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import geopandas as gpd

from pa_calculations import (
    assemble_supply_table,
    compute_extent,
    detect_habitat_column,
    reproject_to_metric,
    validate_benefit_names,
    validate_completeness,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_gdf() -> gpd.GeoDataFrame:
    """Create 3 boxes (1000 m x 1000 m each) in UTM 33N, then convert to WGS-84.

    Boxes sit at easting 500 000 – 503 000, northing 6 100 000 – 6 101 000.
    """
    boxes = [
        box(500_000 + i * 1000, 6_100_000, 500_000 + (i + 1) * 1000, 6_101_000)
        for i in range(3)
    ]
    gdf = gpd.GeoDataFrame(
        {"Subzone ID": ["Z1", "Z2", "Z3"], "geometry": boxes},
        crs="EPSG:32633",
    )
    return gdf.to_crs(epsg=4326)


# ---------------------------------------------------------------------------
# TestComputeExtent
# ---------------------------------------------------------------------------

class TestComputeExtent:
    def test_basic_two_habitats(self):
        gdf = _make_test_gdf()
        assignments = {"Z1": "MB252", "Z2": "MB252", "Z3": "MC352"}
        result = compute_extent(gdf, assignments, unit="Ha")

        assert set(result["eunis_code"]) == {"MB252", "MC352"}
        mb = result.loc[result["eunis_code"] == "MB252", "area"].iloc[0]
        mc = result.loc[result["eunis_code"] == "MC352", "area"].iloc[0]
        assert abs(mb - 200) < 5, f"MB252 area {mb} not ~200 Ha"
        assert abs(mc - 100) < 5, f"MC352 area {mc} not ~100 Ha"
        assert abs(result["pct_total"].sum() - 100) < 1

    def test_unassigned_excluded(self):
        gdf = _make_test_gdf()
        assignments = {"Z1": "MB252"}
        result = compute_extent(gdf, assignments, unit="Ha")
        assert len(result) == 1
        assert result["eunis_code"].iloc[0] == "MB252"

    def test_km2_unit(self):
        gdf = _make_test_gdf()
        assignments = {"Z1": "MB252", "Z2": "MB252", "Z3": "MC352"}
        result = compute_extent(gdf, assignments, unit="km2")
        mb = result.loc[result["eunis_code"] == "MB252", "area"].iloc[0]
        assert abs(mb - 2) < 0.1, f"MB252 area {mb} not ~2 km²"

    def test_empty_assignments(self):
        gdf = _make_test_gdf()
        result = compute_extent(gdf, {}, unit="Ha")
        assert result.empty
        assert list(result.columns) == ["eunis_code", "habitat_name", "area", "pct_total"]

    def test_missing_subzone_id_column_raises(self):
        """GDF without 'Subzone ID' column should raise a clear ValueError."""
        gdf = gpd.GeoDataFrame(
            {"wrong_col": ["A", "B"], "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1)]},
            crs="EPSG:4326",
        )
        with pytest.raises(ValueError, match="Subzone ID"):
            compute_extent(gdf, {"A": "MB252"}, unit="Ha")

    def test_missing_crs_raises(self):
        """GDF with crs=None should raise a clear ValueError, not CRSError."""
        gdf = gpd.GeoDataFrame(
            {"Subzone ID": ["A"], "geometry": [box(0, 0, 1, 1)]},
            crs=None,
        )
        with pytest.raises(ValueError, match="CRS"):
            compute_extent(gdf, {"A": "MB252"}, unit="Ha")


# ---------------------------------------------------------------------------
# TestAssembleSupplyTable
# ---------------------------------------------------------------------------

class TestAssembleSupplyTable:
    def test_basic(self):
        supply = {
            "Wild food (finfish)": {"MB252": 10, "MC352": 20},
            "Clean water": {"MB252": 5},
        }
        codes = ["MB252", "MC352"]
        result = assemble_supply_table(supply, codes)

        assert list(result.columns) == ["Benefit", "Unit", "MB252", "MC352"]
        assert len(result) == 2
        # Clean water / MC352 should be NaN
        cw_row = result.loc[result["Benefit"] == "Clean water"]
        assert np.isnan(cw_row["MC352"].iloc[0])

    def test_empty(self):
        result = assemble_supply_table({}, [])
        assert result.empty


# ---------------------------------------------------------------------------
# TestValidateCompleteness
# ---------------------------------------------------------------------------

class TestValidateCompleteness:
    def test_partial(self):
        supply = {"B1": {"H1": 10}}
        result = validate_completeness(supply, ["H1", "H2"], ["B1", "B2"])
        assert result["filled"] == 1
        assert result["total"] == 4
        assert result["pct"] == 25.0

    def test_full(self):
        supply = {
            "B1": {"H1": 10, "H2": 20},
            "B2": {"H1": 30, "H2": 40},
        }
        result = validate_completeness(supply, ["H1", "H2"], ["B1", "B2"])
        assert result["filled"] == 4
        assert result["total"] == 4
        assert result["pct"] == 100.0


# ---------------------------------------------------------------------------
# TestDetectHabitatColumn
# ---------------------------------------------------------------------------

class TestDetectHabitatColumn:
    def test_finds_eunis(self):
        assert detect_habitat_column(["id", "EUNIS", "area"]) == "EUNIS"

    def test_finds_habitat(self):
        assert detect_habitat_column(["id", "habitat_type", "area"]) == "habitat_type"

    def test_none_found(self):
        assert detect_habitat_column(["id", "name", "area"]) is None

    def test_priority_order(self):
        # EUNIS appears before habitat in HABITAT_COLUMN_CANDIDATES
        assert detect_habitat_column(["habitat", "EUNIS", "area"]) == "EUNIS"


# ---------------------------------------------------------------------------
# TestBenefitNameValidation
# ---------------------------------------------------------------------------

class TestBenefitNameValidation:
    def test_unique_names(self):
        assert validate_benefit_names(["A", "B", "C"]) is True

    def test_duplicate_names(self):
        assert validate_benefit_names(["A", "B", "A"]) is False


# ---------------------------------------------------------------------------
# TestReprojectToMetric
# ---------------------------------------------------------------------------

class TestReprojectToMetric:
    def test_decorated_epsg_string_is_parsed(self):
        """Decorated `"EPSG:#### (description)"` must be parsed, not silently dropped.

        Fixture choice: `_make_test_gdf` is centered in UTM zone 33N, so the
        UTM auto-detect fallback returns EPSG:32633. We deliberately pass a
        DECORATED string for EPSG:3035 (ETRS89-LAEA Europe) which pyproj
        cannot parse raw. Before the fix: parse fails → UTM auto-detect →
        32633. After the fix: regex extracts 3035 → from_epsg → 3035.
        """
        gdf = _make_test_gdf()  # WGS-84 GeoDataFrame, centroid in UTM 33N
        decorated = "EPSG:3035 (ETRS89 / LAEA Europe)"
        out = reproject_to_metric(gdf, original_crs=decorated)
        assert out.crs.to_epsg() == 3035, (
            f"Expected EPSG:3035 (regex-extracted from decorated string), "
            f"got {out.crs.to_epsg()} — likely UTM auto-detect fallback, "
            "meaning the decorated CRS string was silently dropped."
        )
