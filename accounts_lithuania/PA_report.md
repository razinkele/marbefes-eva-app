# Physical Accounts - Lithuanian BBT5 (Curonian Lagoon & Baltic Sea coast)

*MARBEFES WP4 | SEEA EA Framework | Generated 2026-04-22*

## 1. Overview

This report presents ecosystem **extent**, **condition**, and **supply**
accounts for the Lithuanian BBT5, following the SEEA Ecosystem Accounting
framework and the MARBEFES WP4 guidance (Luisetti & Burdon, 2023). Habitat
classification is **EUNIS Level 3**, derived from EMODnet EUSeaMap 2023
and pre-joined to a 3 km hexagonal grid covering the LT BBT
(`tutorial/eunis_l3_lithuanian.gpkg`, 425 hexes). Ecological Value scores
come from the MARBEFES EVA pipeline (`ALL4EVA_2025_fixed_geometries`,
sentinel-corrected Sept 2025, 721,900 features on a finer native grid).

**Note on join method.** The EUNIS overlay and the EVA pipeline use two
different Subzone_ID schemes (`R###_C###` vs `I######`). This report
therefore uses a **spatial join** (representative points of EVA polygons
into the EUNIS hexes) with area-weighted per-hex aggregation - see
`Join_Method` in the ReadMe sheet.

**Headline figures**

| Metric | Value |
|---|---:|
| EUNIS L3 classes identified | 9 |
| Hexagonal subzones total | 425 |
| Subzones with EUNIS attribution | 391 |
| Habitats with habEV computed | 9 / 9 |
| Total mapped extent | 260,327 Ha |
| EVA source features | 721,900 |

**Top three habitats by area**

| Rank | EUNIS | Name | Area (Ha) | % | habEV |
|---:|---|---|---:|---:|---:|
| 1 | A5.26 or A5.35 or A5.36 | A5.26 or A5.35 or A5.36: Circalittoral muddy sand or Circalittoral sandy mud or Circalittoral fine mud | 131,732 | 50.6 | 4.27 |
| 2 | A5.23 | A5.23: Infralittoral fine sand | 49,241 | 18.9 | 4.12 |
| 3 | A5.25 | A5.25: Circalittoral fine sand | 32,413 | 12.4 | 4.28 |

## 2. Extent Account

See `PhysicalAccounts_BBT8_LithuanianBBT5.xlsx` -> *extent*, *habitat_area_sum*
and *accounts* sheets, plus `habs_ev_lt.gpkg` for per-habitat geometries
(dissolved from hexagonal subzones).

## 3. Condition Account

Condition is expressed through per-habitat **habEV**, an area-weighted mean
of the MARBEFES EVA TotalEV_MAX aggregated score (0-5 scale). The companion
`habs_ev_lt.gpkg` encodes this as the `habEV` field plus a `habEV_class`
categorical bin (Very Low -> Very High), visualized in `maps/habEV_classes.png`.

All EVA Confidence scores in the LT pipeline are Low - each ecosystem
component answered only 1-4 of 7-8 possible Assessment Questions (see
`EVA_FINAL_corrected/validation_report.md`).

## 4. Supply Account (Proxy)

Three ecosystem-service proxies derived from EVA scores, per EUNIS class:

- **Fisheries_proxy** - EVA_all_fish (0-5 scale)
- **FoodWeb_proxy** - ZooScore (0-5 scale)
- **PrimaryProd_proxy** - PhytoScore (0-5 scale)

Full SEEA EA supply accounting in physical units (tonnes of fish, tCO2eq,
visitor-days, tonnes N removed, Ha protected) is not yet available for the
LT BBT and is flagged as *future work* per the DOCX methodology.

## 5. Data Quality

The *missing_values* sheet lists hexes with no EUNIS attribution (outside
EMODnet EUSeaMap 2023 coverage) or partial coverage (<50% EMODnet overlap).

## Methodology

- **Framework:** SEEA Ecosystem Accounting (UN, 2021).
- **Guidance:** MARBEFES WP4.3 Deliverable D4.2 (Luisetti & Burdon, 2023).
- **Habitat classification:** EUNIS Level 3 (EMODnet EUSeaMap 2023).
- **Spatial unit:** 3 km hexagonal grid (EPSG:3346 / LKS94).
- **EVA reconciliation:** representative-point spatial join + area-weighted
  per-hex aggregation.
- **Ecological Value:** MARBEFES EVA aggregated score (0-5), area-weighted
  to habitat level as *habEV*.

## Files in this bundle

| File | Role | Analogue in accounts_crete/ |
|---|---|---|
| `PhysicalAccounts_BBT8_LithuanianBBT5.xlsx` | SEEA EA tables (BBT8 format) | - |
| `eunis_aq_lt.gpkg` | Per-hex EUNIS + AQ | `euniGRaq.shp` |
| `habs_ev_lt.gpkg` | Per-habitat rollup with habEV | `habsev.shp` |
| `bbtland_lt.gpkg` | Coastal land context | `bbtland.shp` |
| `maps/EUNIS_classes.png` | Habitat classification map | - |
| `maps/habEV_classes.png` | habEV class map | `habsEVclasses.JPG` |
| `maps/TotalEV_MAX.png`, `maps/AQ_*.png`, etc. | Indicator maps | `aq1_2_7_8.JPG`, `aq9.JPG` |
| `PA_report.md` | This narrative | - |

## References

- Luisetti T., Burdon D. et al. (2023). *Draft Guidance on Socio-Economic
  Frameworks and Methods - Physical Accounts Section.* MARBEFES D4.2.
- UN (2021). *System of Environmental-Economic Accounting - Ecosystem
  Accounting (SEEA EA).*
- EMODnet (2023). *EUSeaMap 2023.*
- Razinkovas-Baziukas A. et al. (2025). *Lithuanian BBT5 EVA report.* KU/MARBEFES.
- Franco A. & Amorim E. (2025). *EVA guidance.* MARBEFES WP4.1.
