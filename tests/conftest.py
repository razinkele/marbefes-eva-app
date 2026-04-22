"""Pytest configuration — ensure project root is importable.

Individual test files import top-level modules like `eva_cmems`, `eva_hexgrid`,
`pa_calculations`, etc., directly. Most work when pytest is invoked from the
project root, but test files that do inline imports inside test methods
(e.g. `from eva_hexgrid import generate_h3_grid` inside a method body) can
still fail if the import path was set up only in a file-level sys.path hack.

Adding project root to sys.path here, before any test module is imported,
removes the need for per-file workarounds and makes the test suite
invocation-location-independent.
"""

import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
