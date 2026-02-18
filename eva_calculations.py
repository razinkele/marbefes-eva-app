"""
MARBEFES EVA Calculations — pure functions for EVA assessment.

All functions are stateless and have no Shiny dependencies.
"""

import pandas as pd
import numpy as np
import logging

from eva_config import (
    MAX_EV_SCALE, LOCALLY_RARE_THRESHOLD, PERCENTILE_95,
    QUALITATIVE_AQS, QUANTITATIVE_AQS, AQ_TOOLTIPS,
)

logger = logging.getLogger(__name__)


def detect_data_type(df):
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


def rescale_qualitative(df):
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

        # Simple rescaling: 1 -> MAX_EV_SCALE, 0 -> 0
        rescaled[col] = values * MAX_EV_SCALE

        # Ensure no NaN in output
        rescaled[col] = rescaled[col].fillna(0)

    return rescaled


def rescale_quantitative(df):
    """
    Rescale quantitative data to 0-MAX_EV_SCALE scale using min-max normalization
    Formula: MAX_EV_SCALE * (value - min) / (max - min)
    Handles NaN by replacing with 0
    """
    feature_cols = [col for col in df.columns if col != 'Subzone ID']
    rescaled = df.copy()

    for col in feature_cols:
        # Fill any NaN with 0 first
        values = df[col].fillna(0)

        # Calculate min and max (skipna=True by default, but we already filled NaN)
        min_val = values.min()
        max_val = values.max()

        # Check for division by zero and handle NaN
        if pd.isna(min_val) or pd.isna(max_val):
            # If still NaN, set to 0
            rescaled[col] = 0
        elif max_val > min_val:
            # Rescale to 0-MAX_EV_SCALE
            rescaled[col] = MAX_EV_SCALE * (values - min_val) / (max_val - min_val)

            # Ensure no NaN in output
            rescaled[col] = rescaled[col].fillna(0)
        else:
            # All values are the same
            rescaled[col] = 0

    return rescaled


def classify_features(df, user_classifications, lrf_threshold=LOCALLY_RARE_THRESHOLD):
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

        is_lrf = 1 if proportion > 0 and proportion <= lrf_threshold else 0
        classifications['LRF'][col] = is_lrf
        classifications['ROF'][col] = 1 - is_lrf

        # User-defined classifications
        user_settings = user_classifications.get(col, [])
        classifications['RRF'][col] = 1 if "RRF" in user_settings else 0
        classifications['NRF'][col] = 1 if "NRF" in user_settings else 0
        classifications['ESF'][col] = 1 if "ESF" in user_settings else 0
        classifications['HFS_BH'][col] = 1 if "HFS_BH" in user_settings else 0
        classifications['SS'][col] = 1 if "SS" in user_settings else 0

    return classifications


def calculate_aq9_special(df, classifications, percentile=PERCENTILE_95):
    """
    Calculate AQ9 special 3-step concentration-weighted values
    Step 1: Normalize by mean
    Step 2: Apply concentration ratio
    Step 3: Rescale to 0-MAX_EV_SCALE
    Handles NaN by replacing with 0
    """
    feature_cols = [col for col in df.columns if col != 'Subzone ID']
    aq9_rescaled = pd.DataFrame(index=df.index)
    aq9_rescaled['Subzone ID'] = df['Subzone ID']

    for col in feature_cols:
        if classifications['ROF'][col] == 1:
            # Step 1: Calculate concentration metrics
            # Fill NaN with 0 first
            values = df[col].fillna(0)
            mean_val = values.mean()

            if mean_val == 0 or pd.isna(mean_val):
                aq9_rescaled[col] = 0
                continue

            # Step 2: Normalize by mean (with safety check)
            try:
                normalized = values / mean_val
            except (ZeroDivisionError, FloatingPointError):
                aq9_rescaled[col] = 0
                continue

            # Step 3: Calculate concentration weighting
            # Find 95th percentile
            positive_values = values[values > 0]
            if len(positive_values) > 0:
                try:
                    percentile_val = np.percentile(positive_values, percentile)
                    sum_top_5_percent = values[values >= percentile_val].sum()
                    total_sum = values.sum()

                    # Y metric: percentage in top 5% (with division safety)
                    y_metric = (sum_top_5_percent / total_sum) if total_sum > 0 else 0

                    # Z metric: occurrence count
                    z_metric = (values > 0).sum()

                    # Concentration ratio (with division safety)
                    concentration_ratio = (y_metric / z_metric) if z_metric > 0 else 0

                    # Apply concentration weighting
                    weighted = normalized * concentration_ratio
                except (ZeroDivisionError, FloatingPointError, ValueError):
                    weighted = normalized * 0
            else:
                weighted = normalized * 0

            aq9_rescaled[col] = weighted
        else:
            aq9_rescaled[col] = 0

    # Step 4: Rescale all weighted values to 0-MAX_EV_SCALE range
    for col in feature_cols:
        if classifications['ROF'][col] == 1:
            max_weighted = aq9_rescaled[col].max()
            if max_weighted > 0 and not pd.isna(max_weighted):
                try:
                    aq9_rescaled[col] = MAX_EV_SCALE * aq9_rescaled[col] / max_weighted
                except (ZeroDivisionError, FloatingPointError):
                    aq9_rescaled[col] = 0
            else:
                aq9_rescaled[col] = 0

    return aq9_rescaled


def calculate_all_aqs(df, data_type, rescaled_qual, rescaled_quant, aq9_rescaled, classifications):
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
            except Exception as e:
                logger.error(f"Error calculating {aq}: {e}")
                results[aq] = 0
        else:
            results[aq] = np.nan

    return results


def calculate_ev(aq_results, data_type):
    """Calculate EV as MAX of appropriate AQs based on data type"""
    ev_values = []

    for idx in aq_results.index:
        if data_type == "qualitative":
            # EV = MAX(AQ1, AQ3, AQ5, AQ7, AQ10, AQ12, AQ14)
            aq_cols = QUALITATIVE_AQS
        elif data_type == "quantitative":
            # EV = MAX(AQ2, AQ4, AQ6, AQ8, AQ9, AQ11, AQ13, AQ15)
            aq_cols = QUANTITATIVE_AQS
        else:
            ev_values.append(0)
            continue

        # Get values, treating NaN as 0
        values = []
        for col in aq_cols:
            val = aq_results.loc[idx, col]
            if pd.notna(val) and val != 0:
                values.append(val)

        # Calculate max, defaulting to 0 if no valid values
        ev_values.append(np.max(values) if values else 0)

    return ev_values


def get_aq_status(data_type, classifications, results):
    """Analyze each AQ and return status with explanation."""
    qual_aqs = QUALITATIVE_AQS
    quant_aqs = QUANTITATIVE_AQS

    has_rrf = any('RRF' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
    has_nrf = any('NRF' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
    has_esf = any('ESF' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
    has_hfs = any('HFS_BH' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())
    has_ss = any('SS' in (cls if isinstance(cls, list) else [cls]) for cls in classifications.values())

    statuses = {}
    for aq in qual_aqs + quant_aqs:
        aq_num = int(aq[2:])

        if data_type == 'qualitative' and aq in quant_aqs:
            statuses[aq] = ('inactive', 'Quantitative data required')
        elif data_type == 'quantitative' and aq in qual_aqs:
            statuses[aq] = ('inactive', 'Qualitative data required')
        elif aq_num in [5, 6] and not has_rrf:
            statuses[aq] = ('inactive', 'No features classified as RRF')
        elif aq_num in [7, 8] and not has_nrf:
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


def get_aq_tooltip(aq_name):
    return AQ_TOOLTIPS.get(aq_name, "")
