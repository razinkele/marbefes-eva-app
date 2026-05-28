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


def validate_feedback(title: str, description: str,
                      type_: str = "general", steps: str = "") -> str | None:
    """Return an error message string, or None if the input is valid."""
    if not title or not title.strip():
        return "Please enter a title."
    if not description or not description.strip():
        return "Please enter a description."
    if len(title) > TITLE_MAX:
        return f"Title must be {TITLE_MAX} characters or fewer."
    if len(description) > DESC_MAX:
        return f"Description must be {DESC_MAX} characters or fewer."
    if steps and len(steps) > STEPS_MAX:
        return f"Steps must be {STEPS_MAX} characters or fewer."
    if type_ not in LABELS_BY_TYPE:
        return "Invalid report type."
    return None


def create_github_issue(title: str, body: str,
                        labels: list[str] | None = None) -> dict | None:
    """POST a new GitHub Issue. Returns {'url','number'} or None.

    Returns None immediately if MARBEFES_EVA_GITHUB_TOKEN is unset, and on any
    non-2xx status or request exception (caller falls back to local-only).
    """
    token = os.environ.get("MARBEFES_EVA_GITHUB_TOKEN", "").strip()
    if not token:
        logger.info("create_github_issue: no token configured; skipping GitHub")
        return None

    repo = os.environ.get("MARBEFES_EVA_GITHUB_REPO", DEFAULT_REPO).strip() or DEFAULT_REPO
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {"title": title, "body": body, "labels": list(labels or [])}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code in (200, 201):
            data = resp.json()
            return {"url": data.get("html_url", ""), "number": data.get("number")}
        logger.error("create_github_issue: HTTP %s", resp.status_code)
        return None
    except Exception as e:
        logger.error("create_github_issue error: %s", e)
        return None


def collect_system_context(input, session=None, extra: dict | None = None) -> dict:
    """Snapshot non-PII technical context for a feedback submission.

    Every field is gathered defensively: a missing input or any error yields
    "unknown" rather than raising. `extra` lets the caller inject app-specific
    fields (e.g. dataset_loaded, feature_count, selected_area).

    `session` is reserved for future use (e.g. attaching session.id to
    diagnostic context) and is not read by the current implementation.
    """
    def safe(getter, default="unknown"):
        try:
            val = getter()
            return default if val in (None, "") else val
        except Exception:
            return default

    try:
        import version
        app_version = version.get_version()
    except Exception:
        app_version = "unknown"

    ctx = {
        "app_version": app_version,
        "current_tab": safe(lambda: str(input.navigation())),
        "browser_info": safe(lambda: str(input.fb_browser_info())),
        "timestamp": datetime.datetime.now(datetime.timezone.utc)
                            .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if extra:
        ctx.update(extra)
    return ctx


def _build_issue_body(description: str, steps: str, context: dict) -> str:
    parts = [f"## Description\n\n{description}"]
    if steps and steps.strip():
        parts.append(f"\n\n## Steps to Reproduce\n\n{steps}")
    ctx_json = json.dumps(context or {}, indent=2, ensure_ascii=False)
    parts.append("\n\n<details>\n<summary>System Context</summary>\n\n"
                 f"```json\n{ctx_json}\n```\n\n</details>")
    return "".join(parts)


def submit_feedback(title: str, description: str, type_: str = "general",
                    steps: str = "", context: dict | None = None,
                    log_path: str | None = None) -> dict:
    """Save locally (always) and attempt a GitHub Issue. Returns a result dict."""
    context = context or {}
    labels = LABELS_BY_TYPE.get(type_, LABELS_BY_TYPE["general"])

    payload = {
        "title": title,
        "description": description,
        "type": type_,
        "steps": steps,
        "labels": labels,
        "github_url": None,
        **context,
    }
    local_success = save_feedback_local(payload, path=log_path)

    gh = create_github_issue(title, _build_issue_body(description, steps, context), labels)
    github_success = gh is not None
    github_url = gh["url"] if gh else None

    return {
        "local_success": local_success,
        "github_success": github_success,
        "github_url": github_url,
    }
