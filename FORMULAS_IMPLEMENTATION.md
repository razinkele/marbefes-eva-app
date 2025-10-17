# EVA Formulas & Calculation Methods - Implementation Guide

**Date:** October 17, 2025  
**Status:** ✅ Complete - Formulas Tab Added  
**Location:** Tab "📐 Formulas & Methods" in MARBEFES EVA Application

---

## Overview

A comprehensive **Formulas & Methods** tab has been added to the MARBEFES EVA application, providing complete documentation of all calculation methodologies used in the Ecological Value Assessment framework.

---

## What's Included in the Formulas Tab

### 1. **Assessment Framework Overview**
- Key metrics definitions (X, Xi, Y, Z, EV)
- Explanation of the spatial assessment approach
- Overview of the 9 Assessment Questions (AQ1-AQ9)

### 2. **Assessment Question Calculations**

#### **Rarity Assessments (AQ1-AQ3)**

**AQ1: Locally Rare Features (LRF)**
```
if Y >= 0.5 then LRF = 1 else LRF = 0
```
- Features with ≥50% of total abundance in top 5% subzones

**AQ2: Regionally Rare Features (RRF)**
```
if 0.25 <= Y < 0.5 then RRF = 1 else RRF = 0
```
- Features with 25-50% abundance in top 5% subzones

**AQ3: Nationally Rare Features (NRF)**
```
if Z <= 5 then NRF = 1 else NRF = 0
```
- Features present in ≤5 subzones

#### **Regular Occurrence (AQ4)**

**AQ4: Regularly Occurring Features (ROF)**
```
if Y < 0.25 AND Z > 5 then ROF = 1 else ROF = 0
```
- Features widespread but not concentrated

#### **Ecological Significance (AQ5-AQ8)**

These are user-defined binary flags:
- **AQ5: Ecologically Significant Features (ESF)** - User designated
- **AQ6: Habitat Forming Species (HFS)** - Species creating structural habitat
- **AQ7: Biogenic Habitat (BH)** - Habitats formed by living organisms
- **AQ8: Symbiotic Species (SS)** - Species in symbiotic relationships

### 3. **Ecological Value (EV) Calculation**

#### **Step 1: Feature Presence Matrix (FPM)**
```
FPM[i,j] = (Xi[j] / X[j]) × (AQ1 + AQ2 + AQ3 + AQ4 + AQ5 + AQ6 + AQ7 + AQ8)
```

Where:
- i = subzone index
- j = feature index
- Xi[j] = abundance of feature j in subzone i
- X[j] = mean abundance of feature j across all subzones

#### **Step 2: Combined Assessment Score (AQ9)**
```
AQ9[i] = Σ[j] FPM[i,j]
```
Sum across all features for each subzone

#### **Step 3: Ecological Value**
```
EV[i] = AQ9[i] / n
```
Where n = number of features being assessed

#### **Step 4: Total EV (Multiple Components)**
```
Total_EV[i] = Σ[k] EV[i,k]
```
Where k = ecosystem component index

### 4. **Detailed Calculation Workflow**

The tab provides a complete 6-step workflow:

1. **Data Preparation**
   - Load gridded data
   - Calculate total means (X)
   - Identify 95th percentiles

2. **Rarity Assessment (AQ1-AQ3)**
   - Calculate Y (abundance percentage in top 5%)
   - Calculate Z (occurrence count)
   - Apply threshold criteria

3. **Regular Occurrence (AQ4)**
   - Apply combined Y and Z criteria

4. **Ecological Significance (AQ5-AQ8)**
   - Apply user-defined classifications

5. **Feature Presence Matrix (AQ9)**
   - Calculate weighted presence
   - Sum across features

6. **Final EV**
   - Normalize and aggregate

### 5. **Implementation Status**

**Currently Implemented:**
- ✅ Basic data loading and validation
- ✅ Feature identification
- ✅ Simple AQ score (sum of features)
- ✅ Normalized EV calculation
- ✅ Data export

**Planned Enhancements:**
- 🚧 Full AQ1-AQ8 calculations with proper thresholds
- 🚧 95th percentile detection
- 🚧 Y/Z ratio calculations
- 🚧 Feature configuration for AQ5-AQ8 flags
- 🚧 Complete FPM calculation
- 🚧 Multiple EC support

---

## Key Formulas Quick Reference

| Metric | Formula | Description |
|--------|---------|-------------|
| **X** | mean(Xi) | Total mean abundance across all subzones |
| **Y** | Σ(top 5% Xi) / Σ(all Xi) | % abundance in top 5% subzones |
| **Z** | count(Xi > 0) | Number of occurrences |
| **FPM** | (Xi/X) × Σ(AQ1-8) | Feature presence matrix |
| **AQ9** | Σ(FPM) | Combined assessment score |
| **EV** | AQ9 / n | Ecological value (normalized) |

---

## Formula Interpretation

### Understanding Y (Abundance Concentration)
- **Y ≥ 50%**: Locally rare (concentrated in few subzones)
- **25% ≤ Y < 50%**: Regionally rare (moderately concentrated)
- **Y < 25%**: Widespread distribution

### Understanding Z (Spatial Occurrence)
- **Z ≤ 5**: Nationally rare (very limited occurrence)
- **Z > 5**: More widespread occurrence

### Understanding EV (Ecological Value)
- **Higher EV**: Subzone has greater ecological value
- **EV considers**: Both abundance (Xi/X) and assessment criteria (AQ1-AQ8)
- **Normalized**: Divided by number of features for comparability

---

## Visual Elements in the Tab

The formulas tab includes:

1. **Color-Coded Sections**
   - Blue boxes: Main formulas and definitions
   - Green boxes: Final EV calculations
   - Orange boxes: Implementation notes

2. **Mathematical Notation**
   - HTML formatted equations with subscripts/superscripts
   - Code blocks for easy copying
   - Clear variable definitions

3. **Organized Layout**
   - Two-column layout for easy comparison
   - Hierarchical organization (Overview → Details → Implementation)
   - Clear section headers with icons

4. **Interactive Elements**
   - Expandable descriptions
   - Linked cross-references
   - Styled for readability

---

## Usage Guide

### For Researchers
1. Navigate to "📐 Formulas & Methods" tab
2. Review the Assessment Framework Overview
3. Understand each AQ calculation
4. Follow the detailed workflow for implementation

### For Developers
1. Use formulas as implementation specification
2. Check Implementation Status for current state
3. Reference Quick Reference table for coding
4. Plan enhancements based on Planned section

### For Reviewers
1. Verify calculations against Franco & Amorim (2025)
2. Check formula consistency across sections
3. Validate threshold values (Y percentages, Z counts)
4. Review workflow completeness

---

## Benefits of the Formulas Tab

### ✅ **Transparency**
- All calculations are explicitly documented
- Users understand how results are derived
- Reproducible research supported

### ✅ **Educational**
- Clear explanations of each metric
- Step-by-step workflow
- Mathematical notation with plain language

### ✅ **Reference**
- Quick lookup for formula details
- Implementation checklist
- Status tracking

### ✅ **Quality Assurance**
- Enables validation of calculations
- Provides testing criteria
- Documents expected behavior

---

## Integration with Application

The formulas tab integrates seamlessly with:

1. **Acronyms Tab**: References same terminology
2. **Data Input Tab**: Explains required data structure
3. **EC Features Tab**: Documents feature configuration
4. **AQ + EV Results Tab**: Shows output of these formulas
5. **Total EV Tab**: Demonstrates aggregation formula

---

## Next Steps for Full Implementation

To implement complete EVA methodology:

### Phase 1: Rarity Calculations
```python
def calculate_Y(df, feature_col):
    """Calculate Y: % abundance in top 5% subzones"""
    percentile_95 = df[feature_col].quantile(0.95)
    top_5_sum = df[df[feature_col] >= percentile_95][feature_col].sum()
    total_sum = df[feature_col].sum()
    return top_5_sum / total_sum if total_sum > 0 else 0

def calculate_Z(df, feature_col):
    """Calculate Z: number of occurrences"""
    return (df[feature_col] > 0).sum()
```

### Phase 2: AQ Calculations
```python
def calculate_AQ1_to_AQ4(df, feature_cols):
    """Calculate AQ1-AQ4 for all features"""
    results = pd.DataFrame()
    for col in feature_cols:
        Y = calculate_Y(df, col)
        Z = calculate_Z(df, col)
        results[f'{col}_LRF'] = 1 if Y >= 0.5 else 0
        results[f'{col}_RRF'] = 1 if 0.25 <= Y < 0.5 else 0
        results[f'{col}_NRF'] = 1 if Z <= 5 else 0
        results[f'{col}_ROF'] = 1 if Y < 0.25 and Z > 5 else 0
    return results
```

### Phase 3: EV Calculation
```python
def calculate_EV(df, feature_cols, AQ_flags):
    """Calculate complete EV using FPM approach"""
    X = df[feature_cols].mean()  # Mean abundance
    FPM = pd.DataFrame()
    
    for i, row in df.iterrows():
        for col in feature_cols:
            Xi = row[col]
            aq_sum = sum([AQ_flags[col][aq] for aq in ['LRF', 'RRF', 'NRF', 'ROF', 'ESF', 'HFS', 'BH', 'SS']])
            FPM.loc[i, col] = (Xi / X[col]) * aq_sum if X[col] > 0 else 0
    
    df['AQ9'] = FPM.sum(axis=1)
    df['EV'] = df['AQ9'] / len(feature_cols)
    return df
```

---

## References

1. **Franco A. and Amorim E. (2025)** - Ecological Value Assessment (EVA) - Phase 2 Methodology
2. **MARBEFES_EVA-Phase2_template.xlsx** - Original Excel implementation with formulas
3. **MARBEFES Project** - Horizon Europe Research Programme

---

## Changelog

**Version 1.0 - October 17, 2025**
- ✅ Initial formulas tab created
- ✅ Complete AQ1-AQ9 documentation
- ✅ EV calculation workflow documented
- ✅ Implementation status tracking added
- ✅ Visual styling applied
- ✅ Mathematical notation formatted

---

**For Questions:**
- Review the Franco & Amorim (2025) reference
- Check the Excel template calculation sheets
- Consult the MARBEFES project documentation

**Application Status:** Ready for review and full implementation planning
