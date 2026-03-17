"""
MARBEFES Physical Accounts (PA) Configuration Module

All constants, reference data, and metadata used by the Physical Accounts
module of the EVA application.  Follows the SEEA EA framework for ecosystem
extent accounts.  Extracted here to keep a single source of truth, mirroring
the structure of eva_config.py.
"""

import re

# ---------------------------------------------------------------------------
# Module version
# ---------------------------------------------------------------------------
PA_MODULE_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Area unit conversions  (factors to convert to square metres)
# ---------------------------------------------------------------------------
AREA_CONVERSIONS = {
    "Ha":  10_000,       # 1 hectare  = 10 000 m²
    "km2": 1_000_000,    # 1 km²      = 1 000 000 m²
}

AREA_UNIT_LABELS = {
    "Ha":  "Hectares (Ha)",
    "km2": "Square kilometres (km²)",
}

# ---------------------------------------------------------------------------
# EUNIS habitat reference list  (marine Level 3, plus selected parent nodes)
# Keys: code, name, level, parent
# Coverage: Mediterranean, Baltic, Atlantic coastal & subtidal habitats
# ---------------------------------------------------------------------------
EUNIS_HABITATS = [
    # --- Parent / Level-2 nodes (kept for hierarchy resolution) -------------
    {"code": "MA1",  "name": "Littoral rock and other hard substrata",          "level": 2, "parent": "MA"},
    {"code": "MB1",  "name": "Infralittoral rock and other hard substrata",     "level": 2, "parent": "MB"},
    {"code": "MC1",  "name": "Circalittoral rock and other hard substrata",     "level": 2, "parent": "MC"},
    {"code": "MD1",  "name": "Offshore circalittoral rock and hard substrata",  "level": 2, "parent": "MD"},
    {"code": "MA6",  "name": "Littoral sediment (Baltic)",                      "level": 2, "parent": "MA"},
    {"code": "MB6",  "name": "Infralittoral sediment (Baltic)",                 "level": 2, "parent": "MB"},
    {"code": "MC6",  "name": "Circalittoral sediment (Baltic)",                 "level": 2, "parent": "MC"},
    {"code": "MB25", "name": "Infralittoral seagrass beds",                     "level": 2, "parent": "MB"},
    {"code": "MC35", "name": "Circalittoral biogenic reefs",                    "level": 2, "parent": "MC"},

    # --- Littoral rock — Mediterranean / Atlantic (MA1x) --------------------
    {"code": "MA12", "name": "Mediterranean littoral rock: upper mediolittoral","level": 3, "parent": "MA1"},
    {"code": "MA13", "name": "Mediterranean littoral rock: lower mediolittoral","level": 3, "parent": "MA1"},
    {"code": "MA14", "name": "Atlantic littoral rock: upper mediolittoral",     "level": 3, "parent": "MA1"},
    {"code": "MA15", "name": "Atlantic littoral rock: lower mediolittoral",     "level": 3, "parent": "MA1"},

    # --- Infralittoral rock (MB1x) ------------------------------------------
    {"code": "MB12", "name": "Mediterranean infralittoral rock: photophilic algae",  "level": 3, "parent": "MB1"},
    {"code": "MB13", "name": "Mediterranean infralittoral rock: coralligenous",      "level": 3, "parent": "MB1"},
    {"code": "MB14", "name": "Atlantic infralittoral rock: kelp and large algae",    "level": 3, "parent": "MB1"},
    {"code": "MB15", "name": "Atlantic infralittoral rock: mixed faunal turf",       "level": 3, "parent": "MB1"},

    # --- Infralittoral seagrass — Posidonia (MB25x) -------------------------
    {"code": "MB252",
     "name": "Posidonia oceanica meadows",
     "level": 3, "parent": "MB25"},

    # --- Circalittoral rock (MC1x) ------------------------------------------
    {"code": "MC12", "name": "Mediterranean circalittoral rock: coralligenous assemblages","level": 3, "parent": "MC1"},
    {"code": "MC13", "name": "Mediterranean circalittoral rock: deep coralligenous",       "level": 3, "parent": "MC1"},
    {"code": "MC14", "name": "Atlantic circalittoral rock: faunal turf",                   "level": 3, "parent": "MC1"},
    {"code": "MC15", "name": "Atlantic circalittoral rock: mixed faunal communities",      "level": 3, "parent": "MC1"},

    # --- Circalittoral biogenic reefs (MC35x) --------------------------------
    {"code": "MC352",  "name": "Cold-water coral reefs",                        "level": 3, "parent": "MC35"},
    {"code": "MC3521", "name": "Lophelia pertusa reefs",                        "level": 4, "parent": "MC352"},
    {"code": "MC3517", "name": "Eunicella / gorgonian gardens",                 "level": 4, "parent": "MC352"},

    # --- Offshore circalittoral rock (MD1x) ----------------------------------
    {"code": "MD12", "name": "Offshore circalittoral rock: mixed fauna",        "level": 3, "parent": "MD1"},
    {"code": "MD13", "name": "Offshore circalittoral rock: sponge aggregations","level": 3, "parent": "MD1"},
    {"code": "MD14", "name": "Offshore circalittoral rock: coral communities",  "level": 3, "parent": "MD1"},
    {"code": "MD15", "name": "Offshore circalittoral rock: deep-sea assemblages","level": 3, "parent": "MD1"},

    # --- Baltic sediment (MA6x, MB6x, MC6x) ---------------------------------
    {"code": "MA62", "name": "Baltic littoral sediment: sandy shores",          "level": 3, "parent": "MA6"},
    {"code": "MA63", "name": "Baltic littoral sediment: muddy shores",          "level": 3, "parent": "MA6"},
    {"code": "MB62", "name": "Baltic infralittoral sediment: sandy",            "level": 3, "parent": "MB6"},
    {"code": "MB63", "name": "Baltic infralittoral sediment: muddy",            "level": 3, "parent": "MB6"},
    {"code": "MC62", "name": "Baltic circalittoral sediment: sandy",            "level": 3, "parent": "MC6"},
    {"code": "MC63", "name": "Baltic circalittoral sediment: muddy/clay",       "level": 3, "parent": "MC6"},

    # --- Coastal / transitional (N-level) ------------------------------------
    {"code": "N1",   "name": "Coastal lagoons",                                 "level": 3, "parent": "N"},
    {"code": "N2",   "name": "Estuaries",                                       "level": 3, "parent": "N"},
    {"code": "N3",   "name": "Shallow inlets and bays",                         "level": 3, "parent": "N"},

    # --- Saltmarshes / halophytic vegetation (MA2x) --------------------------
    {"code": "MA22", "name": "Mediterranean saltmarshes",                       "level": 3, "parent": "MA2"},
    {"code": "MA23", "name": "Atlantic / Baltic saltmarshes",                   "level": 3, "parent": "MA2"},
]

# Fast code → name lookup
EUNIS_LOOKUP = {h["code"]: h["name"] for h in EUNIS_HABITATS}

# ---------------------------------------------------------------------------
# Column name candidates for auto-detecting the habitat column in uploads
# ---------------------------------------------------------------------------
HABITAT_COLUMN_CANDIDATES = [
    "EUNIS", "eunis", "EUNIS_code", "eunis_code",
    "Habitat", "habitat", "habitat_type", "Habitat_type",
    "EUNIS_Level3", "eunis_level3",
]

# ---------------------------------------------------------------------------
# Default ecosystem benefits / services for the supply table
# Each entry: name, unit, ecosystem_service (SEEA EA supply category)
# ---------------------------------------------------------------------------
DEFAULT_BENEFITS = [
    {
        "name":               "Wild food (finfish)",
        "unit":               "tonnes",
        "ecosystem_service":  "Wild fish",
    },
    {
        "name":               "Healthy climate",
        "unit":               "tCO2eq",
        "ecosystem_service":  "Carbon sequestration & storage",
    },
    {
        "name":               "Recreation & nature watching",
        "unit":               "visitor-days",
        "ecosystem_service":  "Places and seascapes",
    },
    {
        "name":               "Erosion/flood prevention",
        "unit":               "Ha protected",
        "ecosystem_service":  "Natural hazard protection",
    },
    {
        "name":               "Clean water",
        "unit":               "tonnes N removed",
        "ecosystem_service":  "Waste remediation",
    },
]


def benefit_slug(name: str) -> str:
    """Return a filesystem-safe ASCII slug for a benefit name."""
    return re.sub(r'\W+', '_', name.lower()).strip('_')


# ---------------------------------------------------------------------------
# Export styling
# ---------------------------------------------------------------------------
EXPORT_PA_TAB_COLOR = "009688"   # teal — distinguishes PA sheets from EVA sheets

# ---------------------------------------------------------------------------
# PA methodology reference  (exported to the Excel "PA Methodology" sheet)
# ---------------------------------------------------------------------------
PA_METHODOLOGY = {
    "Topic": [
        "Framework",
        "Standard",
        "Habitat Classification",
        "Extent Method",
        "Supply Method",
        "Data Completeness",
    ],
    "Description": [
        "System of Environmental-Economic Accounting – Ecosystem Accounting (SEEA EA)",
        "UN Statistical Commission SEEA EA (2021); EU Biodiversity Strategy 2030",
        "EUNIS (European Nature Information System) marine habitat typology",
        "Habitat extent calculated from spatial polygon area in reported area units (Ha or km²)",
        "Ecosystem service supply estimated as benefit quantity per unit habitat extent per year",
        "Missing benefit values are left as NaN; partial accounts are flagged in the summary sheet",
    ],
}

# ---------------------------------------------------------------------------
# Colour palette for categorical habitat choropleth maps  (12 distinct hues)
# ---------------------------------------------------------------------------
HABITAT_PALETTE = [
    "#1f77b4",  # muted blue
    "#ff7f0e",  # safety orange
    "#2ca02c",  # cooked asparagus green
    "#d62728",  # brick red
    "#9467bd",  # muted purple
    "#8c564b",  # chestnut brown
    "#e377c2",  # raspberry yogurt pink
    "#7f7f7f",  # middle gray
    "#bcbd22",  # curry yellow-green
    "#17becf",  # blue-teal
    "#aec7e8",  # light blue
    "#ffbb78",  # light orange
]

# ---------------------------------------------------------------------------
# TODO stubs — reserved for future expansion
# ---------------------------------------------------------------------------
# DEFAULT_SECTORS  — economic sector classification for monetary accounts
#                    (e.g. fisheries, tourism, coastal protection, water treatment)
#
# CONDITION_TYPOLOGY_CLASSES  — habitat condition typology following SEEA EA
#                               (e.g. Good, Moderate, Poor, Unknown)
