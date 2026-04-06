"""Unit tests for EVA_FINAL data repair pipeline."""
import numpy as np
import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import Point


def _make_geo_df(data_dict):
    """Helper: create a GeoDataFrame with point geometries."""
    n = len(next(iter(data_dict.values())))
    return gpd.GeoDataFrame(
        data_dict,
        geometry=[Point(i, i) for i in range(n)],
        crs="EPSG:3346",
    )


# ---------------------------------------------------------------------------
# s01_clean_sentinels
# ---------------------------------------------------------------------------
from scripts.s01_clean_sentinels import find_aq_columns, clean_sentinels


class TestCleanSentinels:
    def test_replaces_minus_9999_with_nan(self):
        gdf = _make_geo_df({"AQ1_test": [1.5, -9999, 3.0, -9999]})
        result = clean_sentinels(gdf)
        assert result["AQ1_test"].isna().sum() == 2

    def test_preserves_valid_values(self):
        gdf = _make_geo_df({"AQ1_test": [0.0, 2.5, 5.0]})
        result = clean_sentinels(gdf)
        expected = [0.0, 2.5, 5.0]
        assert result["AQ1_test"].tolist() == expected

    def test_finds_aq_columns_by_prefix(self):
        cols = ["AQ6_benthos", "AQ13_benth", "ZooScore", "geometry"]
        result = find_aq_columns(cols)
        assert result == ["AQ6_benthos", "AQ13_benth"]

    def test_all_values_in_valid_range_after_cleanup(self):
        gdf = _make_geo_df({"AQ1_x": [1.0, -9999, 3.5, 5.0, -10000]})
        result = clean_sentinels(gdf)
        valid = result["AQ1_x"].dropna()
        assert (valid >= 0).all() and (valid <= 5).all()


# ---------------------------------------------------------------------------
# s02_standardize_crs
# ---------------------------------------------------------------------------
from scripts.s02_standardize_crs import standardize_crs


class TestStandardizeCrs:
    def test_reprojects_from_3035_to_3346(self):
        """A point in EPSG:3035 should be reprojected to EPSG:3346."""
        gdf = gpd.GeoDataFrame(
            {"val": [1]},
            geometry=[Point(3500000, 3500000)],
            crs="EPSG:3035",
        )
        result = standardize_crs(gdf, "EPSG:3346")
        assert result.crs.to_epsg() == 3346
        # Coordinates must have changed
        orig_x = gdf.geometry.iloc[0].x
        new_x = result.geometry.iloc[0].x
        assert orig_x != new_x

    def test_already_correct_crs_unchanged(self):
        """If already EPSG:3346, geometry should stay identical."""
        gdf = gpd.GeoDataFrame(
            {"val": [1]},
            geometry=[Point(500000, 6100000)],
            crs="EPSG:3346",
        )
        result = standardize_crs(gdf, "EPSG:3346")
        assert result.crs.to_epsg() == 3346
        assert result.geometry.iloc[0].equals(gdf.geometry.iloc[0])

    def test_preserves_feature_count(self):
        """Number of features must remain the same after reprojection."""
        gdf = gpd.GeoDataFrame(
            {"val": [1, 2, 3]},
            geometry=[Point(i * 100000, i * 100000) for i in range(3)],
            crs="EPSG:3035",
        )
        result = standardize_crs(gdf, "EPSG:3346")
        assert len(result) == 3


# ---------------------------------------------------------------------------
# s03_add_subzone_ids
# ---------------------------------------------------------------------------
from scripts.s03_add_subzone_ids import generate_subzone_ids


class TestAddSubzoneIds:
    def test_generates_from_row_col(self):
        gdf = _make_geo_df({
            "row_index": [12, 28, 30],
            "col_index": [17, 21, 20],
        })
        result = generate_subzone_ids(gdf)
        assert list(result["Subzone_ID"]) == [
            "R012_C017",
            "R028_C021",
            "R030_C020",
        ]

    def test_generates_from_fid(self):
        gdf = _make_geo_df({"fid": [1, 42, 999]})
        result = generate_subzone_ids(gdf)
        assert list(result["Subzone_ID"]) == [
            "F000001",
            "F000042",
            "F000999",
        ]

    def test_fallback_to_index(self):
        gdf = _make_geo_df({"val": [10, 20]})
        with pytest.warns(UserWarning, match="falling back"):
            result = generate_subzone_ids(gdf)
        assert list(result["Subzone_ID"]) == ["I000000", "I000001"]

    def test_no_duplicates(self):
        gdf = _make_geo_df({
            "row_index": [1, 2, 3, 4, 5],
            "col_index": [10, 20, 30, 40, 50],
        })
        result = generate_subzone_ids(gdf)
        ids = result["Subzone_ID"].tolist()
        assert len(ids) == len(set(ids)) == 5


# ---------------------------------------------------------------------------
# s04_recompute_total_ev
# ---------------------------------------------------------------------------
from scripts.s04_recompute_total_ev import compute_total_ev, verify_benthos_max


class TestRecomputeTotalEv:
    def test_max_aggregation(self):
        """3 rows with known EC scores -- verify MAX picks correctly."""
        gdf = _make_geo_df({
            "AQ7_HABITATS": [1.0, 3.0, 2.0],
            "ZooScore":     [2.0, 1.0, 4.0],
            "PhytoScore":   [3.0, 2.0, 1.0],
            "MaxBenthos":   [0.5, 5.0, 3.0],
            "EVA_all_fish": [np.nan, np.nan, 2.0],
        })
        result = compute_total_ev(gdf)
        assert result["TotalEV_MAX"].iloc[0] == pytest.approx(3.0)
        assert result["TotalEV_MAX"].iloc[1] == pytest.approx(5.0)
        assert result["TotalEV_MAX"].iloc[2] == pytest.approx(4.0)

    def test_all_nan_gives_nan(self):
        """All 5 EC scores NaN -> NaN outputs, EC_count=0, Dominant_EC=None."""
        gdf = _make_geo_df({
            "AQ7_HABITATS": [np.nan],
            "ZooScore":     [np.nan],
            "PhytoScore":   [np.nan],
            "MaxBenthos":   [np.nan],
            "EVA_all_fish": [np.nan],
        })
        result = compute_total_ev(gdf)
        assert pd.isna(result["TotalEV_MAX"].iloc[0])
        assert pd.isna(result["TotalEV_MEAN"].iloc[0])
        assert result["EC_count"].iloc[0] == 0
        assert result["Dominant_EC"].iloc[0] is None or pd.isna(result["Dominant_EC"].iloc[0])

    def test_dominant_ec_identified(self):
        """ZooScore=4 is highest -> Dominant_EC='Zooplankton'."""
        gdf = _make_geo_df({
            "AQ7_HABITATS": [1.0],
            "ZooScore":     [4.0],
            "PhytoScore":   [2.0],
            "MaxBenthos":   [3.0],
            "EVA_all_fish": [0.5],
        })
        result = compute_total_ev(gdf)
        assert result["Dominant_EC"].iloc[0] == "Zooplankton"

    def test_ec_count(self):
        """2 non-null ECs -> EC_count=2."""
        gdf = _make_geo_df({
            "AQ7_HABITATS": [np.nan],
            "ZooScore":     [2.0],
            "PhytoScore":   [np.nan],
            "MaxBenthos":   [3.0],
            "EVA_all_fish": [np.nan],
        })
        result = compute_total_ev(gdf)
        assert result["EC_count"].iloc[0] == 2

    def test_max_gte_mean(self):
        """For all non-NaN rows: TotalEV_MAX >= TotalEV_MEAN."""
        gdf = _make_geo_df({
            "AQ7_HABITATS": [1.0, 3.0, 2.0, np.nan],
            "ZooScore":     [2.0, 1.0, 4.0, np.nan],
            "PhytoScore":   [3.0, 2.0, 1.0, np.nan],
            "MaxBenthos":   [0.5, 5.0, 3.0, np.nan],
            "EVA_all_fish": [4.0, 0.5, 2.0, np.nan],
        })
        result = compute_total_ev(gdf)
        valid = result[result["TotalEV_MAX"].notna()]
        assert (valid["TotalEV_MAX"] >= valid["TotalEV_MEAN"]).all()

    def test_verify_benthos_max_correct(self):
        """MaxBenthos matches max(AQ6, AQ9, AQ13) -> empty issues."""
        gdf = _make_geo_df({
            "AQ6_benthos":  [1.0, 2.0],
            "AQ9_benthos":  [3.0, 1.0],
            "AQ13_benthos": [2.0, 2.0],
            "MaxBenthos":   [3.0, 2.0],
        })
        issues = verify_benthos_max(gdf)
        assert issues == []

    def test_verify_benthos_max_detects_mean(self):
        """MaxBenthos=2 but max(1,3,2)=3 -> non-empty issues."""
        gdf = _make_geo_df({
            "AQ6_benthos":  [1.0],
            "AQ9_benthos":  [3.0],
            "AQ13_benthos": [2.0],
            "MaxBenthos":   [2.0],
        })
        issues = verify_benthos_max(gdf)
        assert len(issues) > 0


# ---------------------------------------------------------------------------
# s05_compute_confidence
# ---------------------------------------------------------------------------
from scripts.s05_compute_confidence import (
    compute_ec_confidence,
    classify_confidence,
    assign_confidence,
)


class TestComputeConfidence:
    def test_benthos_confidence(self):
        # Benthos: (4, 8, 3) → (4*3)/8 = 1.5
        assert compute_ec_confidence(4, 8, 3) == pytest.approx(1.5)

    def test_habitats_confidence(self):
        # Habitats: (1, 7, 3) → (1*3)/7 ≈ 0.4286
        assert compute_ec_confidence(1, 7, 3) == pytest.approx(3 / 7)

    def test_max_confidence(self):
        # (7*5)/7 = 5.0
        assert compute_ec_confidence(7, 7, 5) == pytest.approx(5.0)

    def test_zero_aqs_gives_zero(self):
        assert compute_ec_confidence(0, 7, 3) == 0.0

    def test_zero_nmax_gives_zero(self):
        assert compute_ec_confidence(5, 0, 3) == 0.0

    def test_classify_low(self):
        assert classify_confidence(0.30) == "Low"
        assert classify_confidence(1.0) == "Low"

    def test_classify_medium(self):
        assert classify_confidence(1.01) == "Medium"
        assert classify_confidence(2.0) == "Medium"

    def test_classify_high(self):
        assert classify_confidence(2.01) == "High"
        assert classify_confidence(5.0) == "High"

    def test_assign_confidence_to_gdf(self):
        gdf = _make_geo_df({"Dominant_EC": ["Benthos", "Habitats"]})
        result = assign_confidence(gdf)
        assert "Confidence" in result.columns
        assert "Confidence_Class" in result.columns
        # Benthos: (4*3)/8 = 1.5 → Medium (between 1.0 and 2.0)
        assert result["Confidence"].iloc[0] == pytest.approx(1.5)
        assert result["Confidence_Class"].iloc[0] == "Medium"
        # Habitats: (1*3)/7 ≈ 0.4286 → Low (≤ 1.0)
        assert result["Confidence"].iloc[1] == pytest.approx(3 / 7)
        assert result["Confidence_Class"].iloc[1] == "Low"

    def test_missing_dominant_ec_gives_nan(self):
        gdf = _make_geo_df({"Dominant_EC": [None, "UnknownEC"]})
        result = assign_confidence(gdf)
        assert np.isnan(result["Confidence"].iloc[0])
        assert np.isnan(result["Confidence"].iloc[1])


# ---------------------------------------------------------------------------
# s06_validate_and_report
# ---------------------------------------------------------------------------
from scripts.s06_validate_and_report import (
    check_no_sentinels,
    check_aq_range,
    check_crs,
    check_has_subzone_id,
    check_total_ev,
    check_confidence_present,
)


class TestValidation:
    def test_check_no_sentinels_pass(self):
        gdf = _make_geo_df({"AQ1_x": [1.0, 2.0, np.nan]})
        assert check_no_sentinels(gdf) is True

    def test_check_no_sentinels_fail(self):
        gdf = _make_geo_df({"AQ1_x": [1.0, -9999.0, 3.0]})
        assert check_no_sentinels(gdf) is False

    def test_check_aq_range_pass(self):
        gdf = _make_geo_df({"AQ1_x": [0.0, 2.5, 5.0, np.nan]})
        assert check_aq_range(gdf) is True

    def test_check_aq_range_fail(self):
        gdf = _make_geo_df({"AQ1_x": [0.0, 6.0]})
        assert check_aq_range(gdf) is False

    def test_check_crs(self):
        gdf = _make_geo_df({"val": [1]})  # crs="EPSG:3346"
        assert check_crs(gdf, "EPSG:3346") is True
        assert check_crs(gdf, "EPSG:4326") is False

    def test_check_has_subzone_id(self):
        gdf = _make_geo_df({"Subzone_ID": ["R001_C002"]})
        assert check_has_subzone_id(gdf) is True
        gdf2 = _make_geo_df({"val": [1]})
        assert check_has_subzone_id(gdf2) is False

    def test_check_total_ev_correct(self):
        gdf = _make_geo_df({
            "TotalEV_MAX": [3.0, 5.0],
            "AQ7_HABITATS": [3.0, 4.0],
            "EVA_all_fish": [2.0, 5.0],
        })
        assert check_total_ev(gdf) is True

    def test_check_total_ev_wrong(self):
        gdf = _make_geo_df({
            "TotalEV_MAX": [3.0, 5.0],
            "AQ7_HABITATS": [3.0, 4.0],
            "EVA_all_fish": [2.0, 4.0],  # max is 4, but TotalEV_MAX says 5
        })
        assert check_total_ev(gdf) is False

    def test_check_confidence_present(self):
        gdf = _make_geo_df({
            "Confidence": [1.5],
            "Confidence_Class": ["Low"],
        })
        assert check_confidence_present(gdf) is True
        gdf2 = _make_geo_df({"val": [1]})
        assert check_confidence_present(gdf2) is False
