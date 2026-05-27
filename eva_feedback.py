# eva_feedback.py
"""In-app user feedback reporter for the MARBEFES EVA application.

Collects bug reports / suggestions / general feedback from a modal, appends
each submission to a local NDJSON log, and optionally opens a GitHub Issue.
Ported from the Marine-SABRES SES Toolbox feedback_reporter (R/Shiny).
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path

import requests
from shiny import reactive, ui

logger = logging.getLogger(__name__)

# --- limits & config -------------------------------------------------------
TITLE_MAX = 200
DESC_MAX = 5000
STEPS_MAX = 2000
RATE_LIMIT_SECONDS = 30
DEFAULT_REPO = "razinkele/marbefes-eva-app"

LABELS_BY_TYPE = {
    "bug": ["bug", "user-reported"],
    "suggestion": ["enhancement", "user-reported"],
    "general": ["feedback", "user-reported"],
}


def _feedback_log_path() -> str:
    """Resolve the NDJSON log path (env override, else <app>/feedback/...)."""
    env = os.environ.get("MARBEFES_EVA_FEEDBACK_LOG", "").strip()
    if env:
        return env
    return str(Path(__file__).resolve().parent / "feedback" / "user_feedback_log.ndjson")


def save_feedback_local(payload: dict, path: str | None = None) -> bool:
    """Append one feedback payload as an NDJSON line. Returns False on error."""
    target = path or _feedback_log_path()
    try:
        p = Path(target)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True
    except Exception as e:  # disk full, permission, parent-is-a-file, etc.
        logger.error("save_feedback_local failed: %s", e)
        return False
