"""
MARBEFES EVA Application — Centralized Version Management

Single source of truth for all version information.
Import from here in all modules that need version data.
"""

# ---------------------------------------------------------------------------
# Semantic Versioning: MAJOR.MINOR.PATCH
#   MAJOR: Breaking changes to data formats or calculation methodology
#   MINOR: New features (e.g., new modules, new tabs, new export formats)
#   PATCH: Bug fixes, UI tweaks, documentation updates
# ---------------------------------------------------------------------------

__version__ = "3.7.0"

# Structured version info
VERSION_MAJOR = 3
VERSION_MINOR = 7
VERSION_PATCH = 0
VERSION_LABEL = ""  # e.g., "beta", "rc1", or "" for release

# Module versions (track independently for SEEA EA compliance reporting)
EVA_MODULE_VERSION = "2.2.0"       # EVA assessment engine (AQ1-15, EV calculation)
PA_MODULE_VERSION = "1.0.0"        # Physical Accounts (Extent, Supply)

# Build metadata
BUILD_DATE = "2026-04-06"
CODENAME = "SDM Intelligence"      # Release codename

# ---------------------------------------------------------------------------
# Computed version strings
# ---------------------------------------------------------------------------

def get_version() -> str:
    """Return the full version string."""
    v = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
    if VERSION_LABEL:
        v += f"-{VERSION_LABEL}"
    return v


def get_version_info() -> dict:
    """Return structured version information for export/display."""
    return {
        "app_version": get_version(),
        "eva_module": EVA_MODULE_VERSION,
        "pa_module": PA_MODULE_VERSION,
        "build_date": BUILD_DATE,
        "codename": CODENAME,
    }
