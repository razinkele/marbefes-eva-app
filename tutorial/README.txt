MARBEFES EVA Tutorial Data — Lithuanian BBT5
=============================================

Description:
  Sample data files for the MARBEFES EVA Shiny App tutorial.
  Derived from the Lithuanian Broad Biotope Type 5 (BBT5) assessment
  covering the Curonian Lagoon and Baltic Sea coast.

Files:
  benthos.csv        - Zoobenthos species abundance (6 species, ~308 subzones)
  fish.csv           - Fish CPUE scores (11 species, 425 subzones)
  habitats.csv       - Benthic habitat presence/absence (~6 types, ~393 subzones)
  zooplankton.csv    - Zooplankton abundance (3 taxa, 4-5 ecological zones)
  phytoplankton.csv  - Phytoplankton biomass (2-3 groups, 4-5 ecological zones)
  grid.geojson       - Hexagonal 3km grid (425 cells, WGS84/EPSG:4326)
  eunis_l3_lithuanian.gpkg - EUNIS Level 3 habitat overlay for BBT8 accounts (EUSeaMap-derived, Lithuanian waters)

Data Sources:
  - Zoobenthos: Species distribution modelling (Siaulys & Bucas, 2012)
    and underwater video surveys (2021-2023). Klaipeda University.
  - Fish: Baltic International Trawl Surveys (BITS, 2004-2023, ICES DATRAS)
    and Lithuanian EPA commercial catch statistics (2000-2017).
  - Habitats: HELCOM HUB Level 3 / EUNIS Level 2 classification.
    Lithuanian EPA (2019).
  - Zooplankton: MRI research surveys (1996-2020) and BIO-C3/RETRO
    projects (2014-2016). Klaipeda University.
  - Phytoplankton: Environmental Protection Agency of Lithuania
    monthly monitoring (2017-2023).

Coordinate Reference Systems:
  - Source data: EPSG:3346 (LKS94 / Lithuania TM)
  - grid.geojson: EPSG:4326 (WGS84) for web map display

Extraction Date: 2026-03-18

Citation:
  Franco A. and Amorim E. (2025) Ecological Value Assessment (EVA) -
  Guidance including FAQs. MARBEFES WP4.1.

  Razinkovas-Baziukas A. et al. (2025) Curonian Lagoon and Baltic Sea
  coast Lithuanian BBT EVA report. Klaipeda University / MARBEFES.

License: CC-BY-4.0 (derived from public environmental monitoring data)

Project: MARBEFES - Marine Biodiversity and Ecosystem Functioning
  European Union Horizon Europe Research Programme
