# tests/test_eunis_data.py
"""Tests for eunis_data module."""
import numpy as np
import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import Point, box


def _make_eunis_gdf():
    """Synthetic EUNIS overlay: 4 subzones, 3 habitat types."""
    return gpd.GeoDataFrame({
        "Subzone_ID": ["R001_C001", "R001_C002", "R002_C001", "R002_C002"],
        "dominant_EUNIS": ["A5.25", "A5.25", "A4.4", "A5.23"],
        "dominant_EUNIS_name": [
            "Circalittoral fine sand", "Circalittoral fine sand",
            "Baltic exposed circalittoral rock", "Infralittoral fine sand",
        ],
        "habitat_count": [2, 1, 3, 1],
        "dominant_pct": [75.0, 100.0, 60.0, 90.0],
        "coverage_pct": [95.0, 100.0, 85.0, 90.0],
    }, geometry=[box(0,0,1,1), box(1,0,2,1), box(0,1,1,2), box(1,1,2,2)],
       crs="EPSG:3346")


def _make_eva_gdf():
    """Synthetic EVA scores matching the EUNIS overlay subzones."""
    return gpd.GeoDataFrame({
        "Subzone_ID": ["R001_C001", "R001_C002", "R002_C001", "R002_C002"],
        "AQ7_HABITATS": [1.5, 2.0, 3.0, 1.0],
        "ZooScore": [4.0, 3.5, 4.5, 3.0],
        "PhytoScore": [2.0, 2.5, 1.5, 3.0],
        "MaxBenthos": [3.0, 2.0, 4.0, 1.5],
        "EVA_all_fish": [np.nan, 1.0, np.nan, 2.0],
        "TotalEV_MAX": [4.0, 3.5, 4.5, 3.0],
        "Confidence": [0.3, 0.3, 0.3, 0.3],
    }, geometry=[box(0,0,1,1), box(1,0,2,1), box(0,1,1,2), box(1,1,2,2)],
       crs="EPSG:3346")


class TestComputeEunisExtent:
    def test_basic_extent(self):
        from eunis_data import compute_eunis_extent
        result = compute_eunis_extent(_make_eunis_gdf(), unit="Ha")
        assert len(result) == 3  # 3 unique habitat types
        assert "EUNIS_code" in result.columns
        assert "EUNIS_name" in result.columns
        assert "n_subzones" in result.columns
        # A5.25 has 2 subzones
        a525 = result[result["EUNIS_code"] == "A5.25"]
        assert a525["n_subzones"].iloc[0] == 2

    def test_pct_sums_to_100(self):
        from eunis_data import compute_eunis_extent
        result = compute_eunis_extent(_make_eunis_gdf())
        assert result["pct_of_total"].sum() == pytest.approx(100.0, abs=0.5)


class TestComputeEunisCondition:
    def test_basic_condition(self):
        from eunis_data import compute_eunis_condition
        result = compute_eunis_condition(_make_eunis_gdf(), _make_eva_gdf())
        assert "Habitat_EV" in result.columns
        assert "Habitat_confidence" in result.columns
        # A5.25 has 2 subzones with TotalEV_MAX 4.0 and 3.5 → mean = 3.75
        a525 = result[result["EUNIS_code"] == "A5.25"]
        assert a525["Habitat_EV"].iloc[0] == pytest.approx(3.75)

    def test_no_eva_match_gives_nan(self):
        from eunis_data import compute_eunis_condition
        eunis = _make_eunis_gdf()
        eva = _make_eva_gdf()
        eva["Subzone_ID"] = ["X1", "X2", "X3", "X4"]  # no match
        result = compute_eunis_condition(eunis, eva)
        assert result["Habitat_EV"].isna().all()


class TestComputeEunisSupply:
    def test_basic_supply(self):
        from eunis_data import compute_eunis_supply
        result = compute_eunis_supply(_make_eunis_gdf(), _make_eva_gdf())
        assert "Fisheries_proxy" in result.columns
        assert "FoodWeb_proxy" in result.columns
        assert "PrimaryProd_proxy" in result.columns


class TestBuildAccountsSummary:
    def test_merges_extent_and_condition(self):
        from eunis_data import compute_eunis_extent, compute_eunis_condition, build_accounts_summary
        extent = compute_eunis_extent(_make_eunis_gdf())
        condition = compute_eunis_condition(_make_eunis_gdf(), _make_eva_gdf())
        accounts = build_accounts_summary(extent, condition)
        assert "area_m2" in accounts.columns
        assert "Habitat_EV" in accounts.columns
        assert len(accounts) == 3


class TestSuggestClassifications:
    def test_detects_hfs_subzones(self):
        from eunis_data import suggest_feature_classifications
        gdf = _make_eunis_gdf()  # has A4.4 in one subzone
        result = suggest_feature_classifications(gdf, ["species1"])
        assert result.get("_hfs_subzone_count", 0) > 0

    def test_no_hfs_when_only_sediment(self):
        from eunis_data import suggest_feature_classifications
        gdf = gpd.GeoDataFrame({
            "Subzone_ID": ["R001_C001"],
            "dominant_EUNIS": ["A5.25"],  # sand, not biogenic
            "dominant_EUNIS_name": ["Circalittoral fine sand"],
        }, geometry=[box(0,0,1,1)], crs="EPSG:3346")
        result = suggest_feature_classifications(gdf, ["species1"])
        assert result.get("_hfs_subzone_count", 0) == 0

    def test_detects_esf_subzones(self):
        from eunis_data import suggest_feature_classifications
        gdf = gpd.GeoDataFrame({
            "Subzone_ID": ["R001_C001"],
            "dominant_EUNIS": ["MB252"],  # Posidonia
            "dominant_EUNIS_name": ["Posidonia oceanica meadows"],
        }, geometry=[box(0,0,1,1)], crs="EPSG:3346")
        result = suggest_feature_classifications(gdf, [])
        assert result.get("_esf_subzone_count", 0) > 0
        # MB252 is also in HFS_BH set
        assert result.get("_hfs_subzone_count", 0) > 0

    def test_handles_nan_eunis_codes(self):
        from eunis_data import suggest_feature_classifications
        gdf = gpd.GeoDataFrame({
            "Subzone_ID": ["R001_C001", "R001_C002"],
            "dominant_EUNIS": [None, "A4.4"],
            "dominant_EUNIS_name": [None, "Baltic exposed circalittoral rock"],
        }, geometry=[box(0,0,1,1), box(1,0,2,1)], crs="EPSG:3346")
        result = suggest_feature_classifications(gdf, [])
        assert result.get("_hfs_subzone_count", 0) == 1


class TestBuildMissingValues:
    def test_detects_no_eva(self):
        from eunis_data import build_missing_values
        eunis = _make_eunis_gdf()
        eva = _make_eva_gdf()
        eva = eva[eva["Subzone_ID"] != "R002_C002"]  # remove one
        missing = build_missing_values(eunis, eva, total_bbt_area_m2=1e9)
        assert len(missing) >= 1
        assert "no_eva" in missing["issue_type"].values
