# EVA Feedback Reporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-app feedback reporter to the MARBEFES EVA Python-Shiny app — a header button opening a modal (bug / suggestion / general) that appends every submission to a local NDJSON log and optionally opens a GitHub Issue.

**Architecture:** One standalone module `eva_feedback.py` holds all pure logic (validate, save-local, GitHub POST, orchestrate, context) plus UI builders and a reactive `register_feedback_handlers()`. `app.py` imports it and calls the registrar inside `server`; `eva_ui.py` adds the header button. Pure functions are unit-tested with pytest; the reactive handler is verified by running the app.

**Tech Stack:** Python 3, Shiny for Python (`shiny.ui`, `shiny.reactive`), `requests` (already a dependency), `pytest` + `monkeypatch`/`tmp_path`.

**Spec:** `docs/superpowers/specs/2026-05-27-eva-feedback-reporter-design.md`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `eva_feedback.py` (create) | Constants, `validate_feedback`, `save_feedback_local`, `create_github_issue`, `collect_system_context`, `submit_feedback`, `feedback_button`, `feedback_modal`, `register_feedback_handlers` |
| `tests/test_eva_feedback.py` (create) | Unit tests for the pure functions |
| `eva_ui.py` (modify) | Add the `💬 Feedback` HTML button to the header actions (around line 766–779) |
| `app.py` (modify) | `import eva_feedback` (~line 30); call `eva_feedback.register_feedback_handlers(input, output, session)` near the top of `server` (line 136) |
| `.gitignore` (modify) | Ignore `feedback/` |

Conventions confirmed in-repo: `tests/conftest.py` puts the project root on `sys.path`, so tests `import eva_feedback` directly. `app.py` imports modules as bare `import eva_*`. The app version comes from `version.get_version()`.

---

## Task 1: `save_feedback_local()` — append-only NDJSON

**Files:**
- Create: `eva_feedback.py`
- Test: `tests/test_eva_feedback.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_eva_feedback.py
import json
import eva_feedback


def test_save_feedback_local_writes_valid_ndjson(tmp_path):
    log = tmp_path / "fb.ndjson"
    ok = eva_feedback.save_feedback_local({"title": "x", "n": 1}, path=str(log))
    assert ok is True
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"title": "x", "n": 1}


def test_save_feedback_local_appends_without_corruption(tmp_path):
    log = tmp_path / "fb.ndjson"
    eva_feedback.save_feedback_local({"a": 1}, path=str(log))
    eva_feedback.save_feedback_local({"b": 2}, path=str(log))
    lines = log.read_text(encoding="utf-8").splitlines()
    assert [json.loads(x) for x in lines] == [{"a": 1}, {"b": 2}]


def test_save_feedback_local_creates_missing_dir(tmp_path):
    log = tmp_path / "nested" / "deep" / "fb.ndjson"
    assert eva_feedback.save_feedback_local({"a": 1}, path=str(log)) is True
    assert log.exists()


def test_save_feedback_local_returns_false_on_error(tmp_path):
    # Point at a path whose parent is a file, so mkdir/open fails.
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    bad = blocker / "sub" / "fb.ndjson"
    assert eva_feedback.save_feedback_local({"a": 1}, path=str(bad)) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -v`
Expected: FAIL — `AttributeError: module 'eva_feedback' has no attribute 'save_feedback_local'` (or ModuleNotFoundError until the file exists).

- [ ] **Step 3: Create `eva_feedback.py` with the module preamble + `save_feedback_local`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add eva_feedback.py tests/test_eva_feedback.py
git commit -m "feat(feedback): add save_feedback_local NDJSON logger"
```

---

## Task 2: `validate_feedback()` — pure input validation

**Files:**
- Modify: `eva_feedback.py`
- Test: `tests/test_eva_feedback.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_eva_feedback.py
def test_validate_feedback_accepts_good_input():
    assert eva_feedback.validate_feedback("Title", "Desc", "bug", "steps") is None


def test_validate_feedback_rejects_empty_title():
    assert eva_feedback.validate_feedback("  ", "Desc") == "Please enter a title."


def test_validate_feedback_rejects_empty_description():
    assert eva_feedback.validate_feedback("Title", "") == "Please enter a description."


def test_validate_feedback_rejects_overlong_title():
    msg = eva_feedback.validate_feedback("x" * 201, "Desc")
    assert "200" in msg


def test_validate_feedback_rejects_bad_type():
    assert eva_feedback.validate_feedback("Title", "Desc", "nonsense") == "Invalid report type."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -k validate -v`
Expected: FAIL — `AttributeError: ... has no attribute 'validate_feedback'`.

- [ ] **Step 3: Add `validate_feedback` to `eva_feedback.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -k validate -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add eva_feedback.py tests/test_eva_feedback.py
git commit -m "feat(feedback): add validate_feedback"
```

---

## Task 3: `create_github_issue()` — GitHub Issues POST

**Files:**
- Modify: `eva_feedback.py`
- Test: `tests/test_eva_feedback.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_eva_feedback.py
class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_create_github_issue_returns_none_without_token(monkeypatch):
    monkeypatch.delenv("MARBEFES_EVA_GITHUB_TOKEN", raising=False)
    assert eva_feedback.create_github_issue("t", "b", ["bug"]) is None


def test_create_github_issue_posts_correct_request(monkeypatch):
    monkeypatch.setenv("MARBEFES_EVA_GITHUB_TOKEN", "tok123")
    monkeypatch.setenv("MARBEFES_EVA_GITHUB_REPO", "owner/repo")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResp(201, {"html_url": "https://gh/issues/7", "number": 7})

    monkeypatch.setattr(eva_feedback.requests, "post", fake_post)
    result = eva_feedback.create_github_issue("Title", "Body", ["bug", "user-reported"])

    assert result == {"url": "https://gh/issues/7", "number": 7}
    assert captured["url"] == "https://api.github.com/repos/owner/repo/issues"
    assert captured["headers"]["Authorization"] == "Bearer tok123"
    assert captured["headers"]["Accept"] == "application/vnd.github+json"
    assert captured["json"] == {"title": "Title", "body": "Body",
                                "labels": ["bug", "user-reported"]}
    assert captured["timeout"] == 10


def test_create_github_issue_returns_none_on_http_error(monkeypatch):
    monkeypatch.setenv("MARBEFES_EVA_GITHUB_TOKEN", "tok")
    monkeypatch.setattr(eva_feedback.requests, "post",
                        lambda *a, **k: _FakeResp(422, {}))
    assert eva_feedback.create_github_issue("t", "b", []) is None


def test_create_github_issue_returns_none_on_exception(monkeypatch):
    import requests as _rq
    monkeypatch.setenv("MARBEFES_EVA_GITHUB_TOKEN", "tok")

    def boom(*a, **k):
        raise _rq.exceptions.ConnectionError("down")

    monkeypatch.setattr(eva_feedback.requests, "post", boom)
    assert eva_feedback.create_github_issue("t", "b", []) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -k github -v`
Expected: FAIL — `AttributeError: ... has no attribute 'create_github_issue'`.

- [ ] **Step 3: Add `create_github_issue` to `eva_feedback.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -k github -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add eva_feedback.py tests/test_eva_feedback.py
git commit -m "feat(feedback): add create_github_issue"
```

---

## Task 4: `collect_system_context()` — defensive context snapshot

**Files:**
- Modify: `eva_feedback.py`
- Test: `tests/test_eva_feedback.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_eva_feedback.py
class _FakeInput:
    """Mimics Shiny inputs: input.navigation() etc. are callables."""
    def __init__(self, **values):
        for name, val in values.items():
            setattr(self, name, (lambda v=val: v))


def test_collect_system_context_has_core_keys():
    inp = _FakeInput(navigation=lambda: "nav_eva", fb_browser_info=lambda: "UA/1.0")
    ctx = eva_feedback.collect_system_context(inp)
    assert ctx["current_tab"] == "nav_eva"
    assert ctx["browser_info"] == "UA/1.0"
    assert "app_version" in ctx
    assert ctx["timestamp"].endswith("Z")


def test_collect_system_context_defaults_when_inputs_missing():
    inp = _FakeInput()  # no navigation / fb_browser_info attributes
    ctx = eva_feedback.collect_system_context(inp)
    assert ctx["current_tab"] == "unknown"
    assert ctx["browser_info"] == "unknown"


def test_collect_system_context_merges_extra():
    inp = _FakeInput(navigation=lambda: "nav_home")
    ctx = eva_feedback.collect_system_context(inp, extra={"feature_count": 42})
    assert ctx["feature_count"] == 42
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -k context -v`
Expected: FAIL — `AttributeError: ... has no attribute 'collect_system_context'`.

- [ ] **Step 3: Add `collect_system_context` to `eva_feedback.py`**

```python
def collect_system_context(input, session=None, extra: dict | None = None) -> dict:
    """Snapshot non-PII technical context for a feedback submission.

    Every field is gathered defensively: a missing input or any error yields
    "unknown" rather than raising. `extra` lets the caller inject app-specific
    fields (e.g. dataset_loaded, feature_count, selected_area).
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -k context -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add eva_feedback.py tests/test_eva_feedback.py
git commit -m "feat(feedback): add collect_system_context"
```

---

## Task 5: `submit_feedback()` — orchestrate local save + GitHub

**Files:**
- Modify: `eva_feedback.py`
- Test: `tests/test_eva_feedback.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_eva_feedback.py
def test_submit_feedback_local_only_without_token(tmp_path, monkeypatch):
    monkeypatch.delenv("MARBEFES_EVA_GITHUB_TOKEN", raising=False)
    log = tmp_path / "fb.ndjson"
    result = eva_feedback.submit_feedback(
        "Title", "Desc", type_="bug", steps="do x",
        context={"app_version": "3.8.0"}, log_path=str(log))
    assert result["local_success"] is True
    assert result["github_success"] is False
    assert result["github_url"] is None
    entry = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert entry["title"] == "Title"
    assert entry["type"] == "bug"
    assert entry["labels"] == ["bug", "user-reported"]
    assert entry["app_version"] == "3.8.0"


def test_submit_feedback_creates_issue_when_token_present(tmp_path, monkeypatch):
    monkeypatch.setenv("MARBEFES_EVA_GITHUB_TOKEN", "tok")
    monkeypatch.setattr(
        eva_feedback, "create_github_issue",
        lambda title, body, labels: {"url": "https://gh/9", "number": 9})
    log = tmp_path / "fb.ndjson"
    result = eva_feedback.submit_feedback(
        "T", "D", type_="general", context={}, log_path=str(log))
    assert result["github_success"] is True
    assert result["github_url"] == "https://gh/9"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -k submit -v`
Expected: FAIL — `AttributeError: ... has no attribute 'submit_feedback'`.

- [ ] **Step 3: Add `submit_feedback` to `eva_feedback.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -k submit -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add eva_feedback.py tests/test_eva_feedback.py
git commit -m "feat(feedback): add submit_feedback orchestration"
```

---

## Task 6: UI builders — `feedback_button()` and `feedback_modal()`

**Files:**
- Modify: `eva_feedback.py`
- Test: `tests/test_eva_feedback.py`

- [ ] **Step 1: Write the failing tests** (render the UI to HTML and assert key markers)

```python
# append to tests/test_eva_feedback.py
def test_feedback_button_html_sets_input():
    html = str(eva_feedback.feedback_button())
    assert "show_feedback_modal" in html
    assert "Feedback" in html


def test_feedback_modal_contains_field_ids():
    html = str(eva_feedback.feedback_modal())
    for marker in ("feedback_type", "feedback_title", "feedback_description",
                   "feedback_steps", "feedback_submit", "fb_browser_info"):
        assert marker in html
    # bug-only steps field is gated client-side on the radio value
    assert "feedback_type === 'bug'" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -k "button or modal" -v`
Expected: FAIL — `AttributeError: ... has no attribute 'feedback_button'`.

- [ ] **Step 3: Add the UI builders to `eva_feedback.py`**

```python
def feedback_button():
    """HTML header button matching EVA's existing header-btn style.

    Sets the Shiny input `show_feedback_modal` so the server can open the modal.
    """
    return ui.HTML(
        '<button class="header-btn" '
        "onclick=\"Shiny.setInputValue('show_feedback_modal', Math.random()); return false;\">"
        '<i class="bi bi-chat-dots"></i> Feedback</button>'
    )


def feedback_modal():
    """Build the feedback modal dialog."""
    return ui.modal(
        ui.input_radio_buttons(
            "feedback_type", "Report type",
            {"bug": "Bug Report", "suggestion": "Improvement Suggestion",
             "general": "General Feedback"},
            selected="bug",
        ),
        ui.input_text("feedback_title", "Title",
                      placeholder="Brief summary of your feedback"),
        ui.tags.script("document.getElementById('feedback_title')"
                       "?.setAttribute('maxlength', '200');"),
        ui.input_text_area("feedback_description", "Description",
                            rows=5, placeholder="Please describe in detail..."),
        ui.tags.script("document.getElementById('feedback_description')"
                       "?.setAttribute('maxlength', '5000');"),
        ui.panel_conditional(
            "input.feedback_type === 'bug'",
            ui.input_text_area("feedback_steps", "Steps to reproduce",
                               rows=3, placeholder="1. Go to...\n2. Click...\n3. See error"),
        ),
        ui.tags.details(
            ui.tags.summary("System information"),
            ui.tags.small("Version, current tab, browser, and timestamp are "
                          "attached automatically. No personal data is collected."),
        ),
        ui.tags.script(
            "Shiny.setInputValue('fb_browser_info', navigator.userAgent);"
        ),
        title="Send Feedback",
        easy_close=False,
        footer=ui.TagList(
            ui.input_action_button("feedback_submit", "Submit Feedback",
                                   class_="btn-primary"),
            ui.modal_button("Cancel"),
        ),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -k "button or modal" -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add eva_feedback.py tests/test_eva_feedback.py
git commit -m "feat(feedback): add feedback_button and feedback_modal UI builders"
```

---

## Task 7: `register_feedback_handlers()` — reactive wiring

**Files:**
- Modify: `eva_feedback.py`

No unit test (Shiny reactives need a running session); verified by the run in Task 9. Run the **full** existing test file after to confirm no import/syntax regressions.

- [ ] **Step 1: Add `register_feedback_handlers` to `eva_feedback.py`**

```python
def register_feedback_handlers(input, output, session) -> None:
    """Wire the feedback modal: open, submit (validate + rate-limit), notify."""
    last_submit = reactive.value(0.0)

    @reactive.effect
    @reactive.event(input.show_feedback_modal)
    def _open_feedback_modal():
        ui.modal_show(feedback_modal())

    @reactive.effect
    @reactive.event(input.feedback_submit)
    def _on_feedback_submit():
        import time
        title = input.feedback_title()
        description = input.feedback_description()
        type_ = input.feedback_type()
        # feedback_steps only exists in the DOM for bug reports
        try:
            steps = input.feedback_steps() or ""
        except Exception:
            steps = ""

        err = validate_feedback(title, description, type_, steps)
        if err:
            ui.notification_show(err, type="warning", duration=5)
            return

        now = time.time()
        if now - last_submit() < RATE_LIMIT_SECONDS:
            ui.notification_show("Please wait a moment before submitting again.",
                                 type="warning", duration=4)
            return

        context = collect_system_context(input, session)
        result = submit_feedback(title, description, type_=type_,
                                 steps=steps, context=context)
        last_submit.set(now)

        if result["github_success"]:
            ui.notification_show("Thank you! Your feedback has been submitted.",
                                 type="message", duration=5)
        elif result["local_success"]:
            ui.notification_show("Thank you! Your feedback has been saved.",
                                 type="message", duration=5)
        else:
            ui.notification_show("Sorry — your feedback could not be saved.",
                                 type="error", duration=6)
        ui.modal_remove()
```

- [ ] **Step 2: Verify the module imports and all tests still pass**

Run: `micromamba run -n shiny python -c "import eva_feedback; print('ok')"`
Expected: `ok`
Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -v`
Expected: PASS (all prior tests still pass).

- [ ] **Step 3: Commit**

```bash
git add eva_feedback.py
git commit -m "feat(feedback): add register_feedback_handlers reactive wiring"
```

---

## Task 8: Wire into the app + gitignore

**Files:**
- Modify: `app.py` (import ~line 30; register call near top of `server`, line 136)
- Modify: `eva_ui.py` (header actions block, lines 766–779)
- Modify: `.gitignore`

- [ ] **Step 1: Add the import to `app.py`**

Find the import block (after `import eva_visualizations`, line 30) and add:

```python
import eva_feedback
```

- [ ] **Step 2: Register the handlers in `server`**

Immediately after `def server(input, output, session):` (line 136), add as the first body line:

```python
    eva_feedback.register_feedback_handlers(input, output, session)
```

- [ ] **Step 3: Add the Feedback button to the header**

In `eva_ui.py`, the header actions block (≈ lines 766–779) currently holds a single `ui.HTML('''...''')` with Help/About/Options buttons. Add a Feedback button as the first button inside that HTML string, so the block reads:

```python
            # Right-side action buttons
            ui.div(
                ui.HTML('''
                <button class="header-btn" onclick="Shiny.setInputValue('show_feedback_modal', Math.random()); return false;">
                  <i class="bi bi-chat-dots"></i> Feedback
                </button>
                <button class="header-btn" onclick="openPanel('help-panel')">
                  <i class="bi bi-question-circle"></i> Help
                </button>
                <button class="header-btn" onclick="openPanel('about-panel')">
                  <i class="bi bi-info-circle"></i> About
                </button>
                <button class="header-btn" onclick="openPanel('options-panel')">
                  <i class="bi bi-gear"></i> Options
                </button>
                '''),
                class_="app-header-actions"
            ),
```

(The button is plain HTML to match the existing ones; `feedback_button()` in the module is the reusable equivalent for any future non-header placement.)

- [ ] **Step 4: Gitignore the local log**

Add to `.gitignore`:

```
# User feedback log (runtime-generated, may contain submissions)
feedback/
```

- [ ] **Step 5: Verify the app imports cleanly**

Run: `micromamba run -n shiny python -c "import app; print('app import ok')"`
Expected: `app import ok` (no exceptions).

- [ ] **Step 6: Commit**

```bash
git add app.py eva_ui.py .gitignore
git commit -m "feat(feedback): wire feedback reporter into app header and server"
```

---

## Task 9: Manual / integration verification

**Files:** none (runtime check)

- [ ] **Step 1: Launch the app locally**

Run: `micromamba run -n shiny shiny run --port 8000 app.py`
(Or the project's usual run command.) Open `http://localhost:8000`.

- [ ] **Step 2: Exercise the reporter (no token set → local-only path)**

  - Click **💬 Feedback** in the header → modal opens.
  - Select **Bug Report** → "Steps to reproduce" field appears; switch to **General** → it disappears.
  - Submit with an empty title → warning notification "Please enter a title.", modal stays open.
  - Fill title + description, Submit → "Thank you! Your feedback has been saved.", modal closes.
  - Click Submit twice quickly (reopen) within 30 s → "Please wait a moment..." rate-limit notification.

- [ ] **Step 3: Confirm the local log**

Run: `micromamba run -n shiny python -c "import pathlib,eva_feedback; print(pathlib.Path(eva_feedback._feedback_log_path()).read_text())"`
Expected: one NDJSON line per saved submission, each valid JSON with `title`, `type`, `labels`, and the context keys.

- [ ] **Step 4 (optional): Verify GitHub path**

Set a token in the shell and repeat one submission, then confirm an issue appears:
```bash
$env:MARBEFES_EVA_GITHUB_TOKEN = "<a PAT with issues:write>"
```
Expected: notification "...has been submitted." and a new labeled issue in `razinkele/marbefes-eva-app` (or the repo set via `MARBEFES_EVA_GITHUB_REPO`).

- [ ] **Step 5: Final full test run**

Run: `micromamba run -n shiny python -m pytest tests/test_eva_feedback.py -v`
Expected: all green.

---

## Notes for the implementer

- **DRY/YAGNI:** No admin panel, analyzer, or i18n — out of scope per the spec.
- **Rate limit** is per-session (`reactive.value`); good enough here. The server-side check is the real guard; the client can't bypass it.
- **No PII** in `collect_system_context` — never add uploaded file names or data content to `extra`.
- **Deployment:** set `MARBEFES_EVA_GITHUB_TOKEN` (and optionally `MARBEFES_EVA_GITHUB_REPO`) in the laguna shiny-server environment, beside `MARBEFES_EVA_DATA_PATH`. Without it the feature is silently local-only. The `feedback/` dir is created at runtime and untouched by the deploy script.
- **`feature_count`/`selected_area`:** the `extra` dict in `collect_system_context` is the injection point if you later want EVA's loaded-dataset feature count or selected BBT in the context — pass them from a reactive in `register_feedback_handlers`. Not required for the core feature.
