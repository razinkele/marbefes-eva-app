"""
MARBEFES EVA Calculations — pure functions for EVA assessment.

All functions are stateless and have no Shiny dependencies.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import logging

from eva_config import (
    MAX_EV_SCALE, LOCALLY_RARE_THRESHOLD, PERCENTILE_95,
    QUALITATIVE_AQS, QUANTITATIVE_AQS, AQ_TOOLTIPS,
)

logger = logging.getLogger(__name__)


def detect_data_type(df: pd.DataFrame) -> str:
    """
    Automatically detect if data is qualitative or quantitative

    Logic:
    - Qualitative: Binary data (only 0 and 1 values, or very few unique values)
    - Quantitative: Continuous data (many unique values, decimals, or range > 1)
    """
    feature_cols = [col for col in df.columns if col != 'Subzone ID']

    # Analyze each feature column
    is_binary_count = 0
    is_continuous_count = 0

    for col in feature_cols:
        values = df[col].dropna()
        if len(values) == 0:
            continue

        unique_values = values.unique()
        num_unique = len(unique_values)

        # Check if binary (only 0 and 1)
        is_binary = set(unique_values).issubset({0, 1, 0.0, 1.0})

        # Check if has decimals
        try:
            has_decimals = any(
                isinstance(v, (int, float)) and v != int(v)
                for v in values if pd.notna(v) and v != 0
            )
        except (TypeError, ValueError):
            has_decimals = False

        # Check value range
        val_range = values.max() - values.min() if len(values) > 0 else 0

        # Decision logic
        if is_binary:
            is_binary_count += 1
        elif has_decimals or val_range > 1 or num_unique > 10:
            is_continuous_count += 1
        else:
            # Few unique values, likely categorical/qualitative
            is_binary_count += 1

    # Determine overall data type (default to qualitative if no data)
    if is_binary_count == 0 and is_continuous_count == 0:
        return "qualitative"
    elif is_binary_count > is_continuous_count:
        return "qualitative"
    else:
        return "quantitative"


def rescale_qualitative(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rescale qualitative (binary) data to 0-MAX_EV_SCALE scale
    For presence/absence data: presence (1) = MAX_EV_SCALE, absence (0) = 0
    Handles NaN by replacing with 0
    """
    feature_cols = [col for col in df.columns if col != 'Subzone ID']
    rescaled = df.copy()

    for col in feature_cols:
        # Fill any NaN with 0 first
        values = df[col].fillna(0)

        # Warn if non-binary values detected (would produce scores > MAX_EV_SCALE)
        max_val = values.max()
        if max_val > 1:
            logger.warning("Feature '%s' has non-binary values (max=%.2f) in qualitative mode. "
                           "Rescaled values will exceed 0-%d range.", col, max_val, MAX_EV_SCALE)

        # Simple rescaling: 1 -> MAX_EV_SCALE, 0 -> 0
        rescaled[col] = values * MAX_EV_SCALE

        # Ensure no NaN in output
        rescaled[col] = rescaled[col].fillna(0)

    return rescaled


def rescale_quantitative(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rescale quantitative data to 0-MAX_EV_SCALE scale using min-max normalization
    Formula: MAX_EV_SCALE * (value - min) / (max - min)
    Handles NaN by replacing with 0
    """
    feature_cols = [col for col in df.columns if col != 'Subzone ID']
    rescaled = df.copy()

    for col in feature_cols:
        # Compute min/max on original data (excluding NaN) to avoid bias
        min_val = df[col].min()   # skipna=True by default
        max_val = df[col].max()

        # Track which cells were originally NaN
        nan_mask = df[col].isna()

        # Check for division by zero and handle NaN
        if pd.isna(min_val) or pd.isna(max_val):
            # All values are NaN, set to 0
            rescaled[col] = 0
        elif max_val > min_val:
            # Rescale non-NaN values to 0-MAX_EV_SCALE using true data range
            rescaled[col] = MAX_EV_SCALE * (df[col] - min_val) / (max_val - min_val)

            # Set originally-NaN cells to 0 (not rescaled, just absent)
            rescaled[col] = rescaled[col].fillna(0)
        else:
            # All non-NaN values are the same — feature is uniformly present
            if min_val > 0:
                rescaled[col] = MAX_EV_SCALE  # uniform positive = max relative presence
            else:
                rescaled[col] = 0  # all zeros = absent

    return rescaled


def classify_features(
    df: pd.DataFrame,
    user_classifications: dict[str, list[str]],
    lrf_threshold: float = LOCALLY_RARE_THRESHOLD,
) -> dict[str, dict[str, int]]:
    """
    Classify features based on intrinsic properties (LRF, ROF) and user input.

    Args:
        df (pd.DataFrame): The input data.
        user_classifications (dict): A dictionary from the reactive value
                                     holding user-defined classifications.
    """
    feature_cols = [col for col in df.columns if col != 'Subzone ID']
    classifications = {
        'LRF': {}, 'ROF': {}, 'RRF': {}, 'NRF': {},
        'ESF': {}, 'HFS_BH': {}, 'SS': {}
    }

    for col in feature_cols:
        # Intrinsic classification based on data
        positive_count = (df[col] > 0).sum()
        total_count = df[col].notna().sum()
        proportion = positive_count / total_count if total_count > 0 else 0

        if proportion == 0:
            # Feature never appears — neither locally rare nor regularly occurring
            classifications['LRF'][col] = 0
            classifications['ROF'][col] = 0
        elif proportion <= lrf_threshold:
            classifications['LRF'][col] = 1
            classifications['ROF'][col] = 0
        else:
            classifications['LRF'][col] = 0
            classifications['ROF'][col] = 1

        # User-defined classifications
        user_settings = user_classifications.get(col, [])
        classifications['RRF'][col] = 1 if "RRF" in user_settings else 0
        classifications['NRF'][col] = 1 if "NRF" in user_settings else 0
        classifications['ESF'][col] = 1 if "ESF" in user_settings else 0
        classifications['HFS_BH'][col] = 1 if "HFS_BH" in user_settings else 0
        classifications['SS'][col] = 1 if "SS" in user_settings else 0

    return classifications


def calculate_aq9_special(
    df: pd.DataFrame,
    classifications: dict[str, dict[str, int]],
    percentile: int = PERCENTILE_95,
) -> pd.DataFrame:
    """
    Calculate AQ9 special 3-step concentration-weighted values.

    Step 1: Normalize each feature by its mean.
    Step 2: Weight by concentration ratio  CR = Y / Z_prop  where
            Y = proportion of total abundance in the top-percentile values,
            Z_prop = occurrence proportion (fraction of subzones occupied).
            Using proportion instead of absolute count makes CR
            scale-invariant across different grid resolutions.
    Step 3: Rescale to 0-MAX_EV_SCALE using a *global* maximum across all
            ROF features so that inter-feature concentration differences
            are preserved.  (Per-feature rescaling would cancel CR.)
    """
    feature_cols = [col for col in df.columns if col != 'Subzone ID']
    n_subzones = len(df)
    aq9_rescaled = pd.DataFrame(index=df.index)
    aq9_rescaled['Subzone ID'] = df['Subzone ID']

    for col in feature_cols:
        if classifications['ROF'][col] == 1:
            values = df[col].fillna(0)
            mean_val = values.mean()

            if mean_val == 0 or pd.isna(mean_val):
                aq9_rescaled[col] = 0
                continue

            # Step 1: Normalize by mean
            try:
                normalized = values / mean_val
            except (ZeroDivisionError, FloatingPointError):
                aq9_rescaled[col] = 0
                continue

            # Step 2: Concentration weighting
            positive_values = values[values > 0]
            if len(positive_values) > 0:
                try:
                    percentile_val = np.percentile(positive_values, percentile)
                    sum_top = values[values >= percentile_val].sum()
                    total_sum = values.sum()

                    # Y: proportion of total abundance in top-percentile
                    y_metric = (sum_top / total_sum) if total_sum > 0 else 0

                    # Z: occurrence proportion (scale-invariant)
                    z_prop = (values > 0).sum() / n_subzones if n_subzones > 0 else 0

                    # CR = Y / Z_prop  (high when concentrated + spatially restricted)
                    concentration_ratio = (y_metric / z_prop) if z_prop > 0 else 0

                    weighted = normalized * concentration_ratio
                except (ZeroDivisionError, FloatingPointError, ValueError):
                    weighted = normalized * 0
            else:
                weighted = normalized * 0

            aq9_rescaled[col] = weighted
        else:
            aq9_rescaled[col] = 0

    # Step 3: Rescale using GLOBAL max across all ROF features.
    # This preserves inter-feature concentration differences.
    rof_cols = [col for col in feature_cols if classifications['ROF'].get(col) == 1]
    if rof_cols:
        global_max = aq9_rescaled[rof_cols].values.max()
        if global_max > 0 and not pd.isna(global_max):
            for col in rof_cols:
                aq9_rescaled[col] = MAX_EV_SCALE * aq9_rescaled[col] / global_max
        else:
            for col in rof_cols:
                aq9_rescaled[col] = 0

    return aq9_rescaled


def calculate_all_aqs(
    df: pd.DataFrame,
    data_type: str,
    rescaled_qual: pd.DataFrame,
    rescaled_quant: pd.DataFrame,
    aq9_rescaled: pd.DataFrame,
    classifications: dict[str, dict[str, int]],
) -> pd.DataFrame:
    """Calculate all 15 Assessment Questions (AQ1-AQ15) in a refactored way."""
    results = pd.DataFrame(index=df.index)
    results['Subzone ID'] = df['Subzone ID']
    feature_cols = [col for col in df.columns if col != 'Subzone ID']

    # Define AQ properties
    aq_map = {
        'AQ1': {'type': 'qualitative', 'features': 'LRF', 'df': rescaled_qual},
        'AQ2': {'type': 'quantitative', 'features': 'LRF', 'df': rescaled_quant},
        'AQ3': {'type': 'qualitative', 'features': 'RRF', 'df': rescaled_qual},
        'AQ4': {'type': 'quantitative', 'features': 'RRF', 'df': rescaled_quant},
        'AQ5': {'type': 'qualitative', 'features': 'NRF', 'df': rescaled_qual},
        'AQ6': {'type': 'quantitative', 'features': 'NRF', 'df': rescaled_quant},
        'AQ7': {'type': 'qualitative', 'features': 'ALL', 'df': rescaled_qual},
        'AQ8': {'type': 'quantitative', 'features': 'ROF', 'df': rescaled_quant},
        'AQ9': {'type': 'quantitative', 'features': 'ROF', 'df': aq9_rescaled},
        'AQ10': {'type': 'qualitative', 'features': 'ESF', 'df': rescaled_qual},
        'AQ11': {'type': 'quantitative', 'features': 'ESF', 'df': rescaled_quant},
        'AQ12': {'type': 'qualitative', 'features': 'HFS_BH', 'df': rescaled_qual},
        'AQ13': {'type': 'quantitative', 'features': 'HFS_BH', 'df': rescaled_quant},
        'AQ14': {'type': 'qualitative', 'features': 'SS', 'df': rescaled_qual},
        'AQ15': {'type': 'quantitative', 'features': 'SS', 'df': rescaled_quant},
    }

    for aq, props in aq_map.items():
        if data_type == props['type']:
            rescaled_df = props['df']
            feature_type = props['features']

            # Get the list of features that match the classification for this AQ
            if feature_type == 'ALL':
                matching_features = feature_cols
            else:
                matching_features = [
                    col for col in feature_cols
                    if classifications[feature_type].get(col) == 1
                ]

            if not matching_features:
                results[aq] = np.nan
                continue

            # Select only the data for the matching features
            try:
                aq_data = rescaled_df[matching_features]

                # Calculate the mean across the row for the selected features
                # Replace any NaN values with 0 before calculating mean
                aq_data_clean = aq_data.fillna(0)

                # Calculate mean across columns (axis=1)
                results[aq] = aq_data_clean.mean(axis=1)

                # If all values in a row are 0, keep it as 0 (not NaN)
                results[aq] = results[aq].fillna(0)
            except KeyError as e:
                logger.error(f"Missing column while calculating {aq}: {e}")
                results[aq] = np.nan
        else:
            results[aq] = np.nan

    return results


def calculate_ev(aq_results: pd.DataFrame, data_type: str) -> list[float]:
    """Calculate EV as MAX of appropriate AQs based on data type (vectorized)."""
    if data_type == "qualitative":
        aq_cols = QUALITATIVE_AQS
    elif data_type == "quantitative":
        aq_cols = QUANTITATIVE_AQS
    else:
        return [0] * len(aq_results)

    cols_present = [c for c in aq_cols if c in aq_results.columns]
    if not cols_present:
        return [0] * len(aq_results)

    return aq_results[cols_present].fillna(0).max(axis=1).tolist()


def get_aq_status(
    data_type: str,
    classifications: dict[str, list[str]],
    results: pd.DataFrame,
) -> dict[str, tuple[str, str]]:
    """Analyze each AQ and return status with explanation."""
    qual_aqs = QUALITATIVE_AQS
    quant_aqs = QUANTITATIVE_AQS

    has_rrf = any('RRF' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
    has_nrf = any('NRF' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
    has_esf = any('ESF' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
    has_hfs = any('HFS_BH' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
    has_ss = any('SS' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())

    # LRF is auto-computed from data, not user-classified; check results for activity
    lrf_col = 'AQ1' if data_type == 'qualitative' else 'AQ2'
    if isinstance(results, pd.DataFrame) and not results.empty and lrf_col in results.columns:
        has_lrf = results[lrf_col].notna().any()
    else:
        has_lrf = False

    statuses = {}
    for aq in qual_aqs + quant_aqs:
        aq_num = int(aq[2:])

        if data_type == 'qualitative' and aq in quant_aqs:
            statuses[aq] = ('inactive', 'Quantitative data required')
        elif data_type == 'quantitative' and aq in qual_aqs:
            statuses[aq] = ('inactive', 'Qualitative data required')
        elif aq_num in [1, 2] and not has_lrf:
            statuses[aq] = ('inactive', 'No locally rare features in this dataset')
        elif aq_num in [3, 4] and not has_rrf:
            statuses[aq] = ('inactive', 'No features classified as RRF')
        elif aq_num in [5, 6] and not has_nrf:
            statuses[aq] = ('inactive', 'No features classified as NRF')
        elif aq_num in [10, 11] and not has_esf:
            statuses[aq] = ('inactive', 'No features classified as ESF')
        elif aq_num in [12, 13] and not has_hfs:
            statuses[aq] = ('inactive', 'No features classified as HFS/BH')
        elif aq_num in [14, 15] and not has_ss:
            statuses[aq] = ('inactive', 'No features classified as SS')
        else:
            statuses[aq] = ('active', 'Active')

    return statuses


def get_aq_tooltip(aq_name: str) -> str:
    return AQ_TOOLTIPS.get(aq_name, "")


def merge_multi_ec_ev(ec_store: dict) -> pd.DataFrame | None:
    """Merge EV scores from multiple ECs into a single DataFrame.

    Returns DataFrame with columns: Subzone ID, <ec_name1>, <ec_name2>, ..., Total EV
    Total EV = MAX across all EC EVs per subzone (per EVA guidance Nov 2024).
    Returns None if no ECs have results.
    """
    ev_frames = {}
    for ec_name, ec in ec_store.items():
        if ec["results"] is not None:
            ev_frames[ec_name] = ec["results"][["Subzone ID", "EV"]].rename(
                columns={"EV": ec_name}
            )
    if not ev_frames:
        return None

    merged = None
    for ec_name, df in ev_frames.items():
        if merged is None:
            merged = df
        else:
            merged = merged.merge(df, on="Subzone ID", how="outer")

    ec_names = list(ev_frames.keys())
    merged[ec_names] = merged[ec_names].fillna(0)
    merged["Total EV"] = merged[ec_names].max(axis=1)
    return merged
