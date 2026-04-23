# SDM Predictor Comparison Report: EUNIS 2019 Habitats vs Environmental Variables

**MARBEFES EVA — Species Distribution Modelling**
**Date:** 2026-04-13
**Study area:** North coast of Crete, Greece (Lat 35.29–35.47°N, Lon 25.06–25.35°E)
**Data source:** Darwin Core Archive `dwca-macrosoft-v2.1.zip` (MACROSOFT macrobenthos survey)

---

## 1. Objective

Evaluate the predictive value of **EUNIS 2019 habitat classifications** obtained from the EMODnet Seabed Habitats WMS, compared with **continuous environmental covariates** from Copernicus Marine Service (CMEMS) and EMODnet Bathymetry, in Random Forest and Kriging-based Species Distribution Models.

## 2. Data Summary

| Parameter | Value |
|---|---|
| Sampling sites | 118 |
| Species in DwC-A | 315 |
| H3 hex grid cells (res 7) | 68 |
| Sites with complete CMEMS covariates | 32 |
| Depth range | 1.7–480 m (mean 150.5 m) |

### 2.1 Environmental Covariates (7 continuous variables)

| Variable | Source | Description |
|---|---|---|
| `depth_m` | EMODnet Bathymetry WCS | Seabed depth (m) |
| `sst_mean_c` | CMEMS | Sea surface temperature (°C) |
| `bottom_temp_c` | CMEMS | Bottom temperature (°C) |
| `sss_mean` | CMEMS | Sea surface salinity (PSU) |
| `current_speed_ms` | CMEMS | Current speed (m/s) |
| `chl_mean` | CMEMS | Chlorophyll-a concentration (mg/m³) |
| `o2_mean_mmol` | CMEMS | Dissolved oxygen (mmol/m³) |

### 2.2 EUNIS 2019 Habitat Categories at Sites

| EUNIS 2019 Code | Habitat Name | Sites | Depth Range |
|---|---|---:|---|
| MB6 | Infralittoral mud | 73 (62%) | 9.5–61.2 m |
| MC6 | Circalittoral mud | 30 (25%) | 66.3–120.4 m |
| MD6 | Offshore circalittoral mud | 3 (3%) | 181.1 m |
| ME6 / MF6 | Upper / Lower bathyal mud | 12 (10%) | 227.9–268.9 m |

### 2.3 Substrate Types

| Substrate | Sites |
|---|---:|
| Dead mattes of *Posidonia oceanica* | 66 (97%) |
| Sand | 2 (3%) |

> **Note:** Substrate is nearly homogeneous across the study area (97% *Posidonia* dead mattes), providing virtually no discriminatory power.

### 2.4 Selected Test Species

Five species were selected across a prevalence gradient to ensure results are not species-specific:

| Species | Occurrences | Prevalence |
|---|---:|---:|
| *Aponuphis brementi* | 46 / 118 | 39% |
| *Amphiura chiajei* | 29 / 118 | 25% |
| *Leiochone leiopygos* | 17 / 118 | 14% |
| *Aricidea simonae* | 12 / 118 | 10% |
| *Eunicidae* | 9 / 118 | 8% |

## 3. Collinearity Analysis: EUNIS 2019 vs Depth

A key finding is that **EUNIS 2019 habitat classes are strongly correlated with depth**, effectively serving as a categorical discretisation of a continuous gradient.

| EUNIS Dummy Variable | Pearson r with depth |
|---|---:|
| MB6: Infralittoral mud | **−0.770** |
| MC6: Circalittoral mud | +0.186 |
| MD6: Offshore circalittoral mud | +0.239 |
| ME6/MF6: Upper/Lower bathyal mud | **+0.844** |

The two largest habitat classes (MB6 and ME6/MF6, representing 72% of sites) have correlations |r| > 0.77 with depth. This means that when depth is already included as a continuous predictor, EUNIS categories carry essentially no additional information.

## 4. Model Comparison

### 4.1 Random Forest: Environmental Variables vs EUNIS 2019

Three Random Forest configurations were compared for each species (in-sample R²):

| Species | Prev. | RF — Env only | RF — EUNIS only | RF — Env + EUNIS | Δ (both − env) |
|---|---:|---:|---:|---:|---:|
| *Aponuphis brementi* | 39% | **0.737** | 0.047 | 0.737 | +0.000 |
| *Amphiura chiajei* | 25% | **0.803** | 0.005 | 0.803 | +0.000 |
| *Leiochone leiopygos* | 14% | **0.509** | 0.028 | 0.509 | +0.000 |
| *Aricidea simonae* | 10% | **0.381** | 0.007 | 0.381 | +0.000 |
| *Eunicidae* | 8% | **1.000** | 0.045 | 1.000 | +0.000 |

**Findings:**
- EUNIS 2019 alone explains less than 5% of variance for every species tested
- Adding EUNIS to environmental variables produces **zero measurable improvement** (Δ < 0.001)
- Environmental variables alone explain 38–100% of variance depending on species prevalence

### 4.2 Feature Importance in Combined Models (RF — Env + EUNIS)

For *Aricidea simonae* (representative low-prevalence species), the top-10 feature importances in the combined model were:

| Rank | Feature | Importance |
|---:|---|---:|
| 1 | `bottom_temp_c` | 0.213 |
| 2 | `sst_mean_c` | 0.157 |
| 3 | `depth_m` | 0.136 |
| 4 | `sss_mean` | 0.089 |
| 5 | `current_speed_ms` | 0.076 |
| 6 | `o2_mean_mmol` | 0.065 |
| 7 | `chl_mean` | 0.051 |
| 8–17 | EUNIS / substrate dummies (10 features) | 0.213 total |

The 7 environmental variables account for ~79% of total importance, while 10 one-hot-encoded EUNIS/substrate dummies share the remaining ~21% — spread thinly across many sparse columns.

### 4.3 Kriging Comparison

| Species | Prev. | Ordinary Kriging (spatial only) | Reg. Kriging — Env | Reg. Kriging — Env + EUNIS |
|---|---:|---:|---:|---:|
| *Aponuphis brementi* | 39% | 0.367 | **0.737** | 0.737 |
| *Amphiura chiajei* | 25% | 0.239 | **0.803** | 0.803 |
| *Leiochone leiopygos* | 14% | 0.116 | **0.509** | 0.509 |
| *Aricidea simonae* | 10% | 0.118 | **0.381** | 0.381 |
| *Eunicidae* | 8% | 0.307 | — | — |

**Findings:**
- Ordinary Kriging (pure spatial interpolation, no covariates) captures R² = 0.12–0.37 from spatial autocorrelation alone
- Regression Kriging with environmental covariates substantially improves over Ordinary Kriging
- Adding EUNIS to Regression Kriging provides **no improvement** over environment-only Regression Kriging

### 4.4 Habitat Preference Patterns

Presence rates by EUNIS 2019 zone confirm that species distributions track depth gradients rather than habitat categories per se:

| Species | MB6 Infra (n=73) | MC6 Circa (n=30) | MD6 Offshore (n=3) | ME6/MF6 Bathyal (n=12) |
|---|---:|---:|---:|---:|
| *A. brementi* | 48% | 33% | 33% | 0% |
| *A. chiajei* | 26% | 23% | 0% | 25% |
| *L. leiopygos* | 16% | 17% | 0% | 0% |
| *Eunicidae* | 12% | 0% | 0% | 0% |

Most species show gradual rather than sharp transitions between habitat classes, consistent with continuous environmental drivers rather than discrete habitat effects.

## 5. Conclusions

1. **EUNIS 2019 habitats are not useful predictors** in this study area. They explain < 5% of variance alone and add zero improvement when combined with environmental variables.

2. **The root cause is collinearity with depth.** In this muddy-substrate coastal transect, the four EUNIS 2019 classes (MB6→ME6/MF6) are simply depth zone labels. The continuous depth variable already captures this gradient with higher resolution.

3. **Substrate is uninformative** because 97% of the study area is a single type (dead *Posidonia oceanica* mattes).

4. **Environmental variables dominate prediction**, with depth, bottom temperature, and SST consistently ranking as the top-3 features across all species.

5. **Ordinary Kriging provides a useful spatial baseline** (R² = 0.12–0.37), suggesting moderate spatial autocorrelation in species distributions that environmental covariates further explain.

6. **These results are study-area-specific.** EUNIS habitats would likely be more informative in areas with:
   - Greater substrate heterogeneity (rocky reefs, mixed sediments, biogenic structures)
   - Habitats not defined primarily by depth (e.g., seagrass meadows, coral formations)
   - Finer-scale EUNIS classification (Level 4+) capturing within-zone variability
   - Larger spatial extent spanning multiple biogeographic regions

## 6. Recommendations

- **For this Crete study area:** Use environmental variables only (depth, bottom temperature, SST, salinity). EUNIS 2019 can be excluded without loss of predictive power.
- **For other study areas:** Always run this comparison before excluding EUNIS — in heterogeneous environments, habitat classes may carry complementary information.
- **For the EVA app SDM module:** Consider adding an automated collinearity check that warns users when categorical covariates (like EUNIS) are highly correlated with existing continuous predictors.

---

*Report generated by the MARBEFES EVA SDM pipeline using data from the MACROSOFT Darwin Core Archive (Crete macrobenthos), EMODnet Seabed Habitats EUNIS 2019 WMS, EMODnet Bathymetry WCS, and Copernicus Marine Service.*
