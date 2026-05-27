# EVA Feedback Reporter — Design Spec

- **Date:** 2026-05-27
- **Status:** Design approved; implementation plan pending
- **Scope:** A core, in-app feedback reporter for the MARBEFES EVA Phase 2 application, ported from the Marine-SABRES SES Toolbox `feedback_reporter` (R/Shiny) to EVA's Python Shiny stack.

## Goal

Let users submit feedback from inside the running EVA app: **bug reports**, **improvement suggestions**, and **general feedback**. Each submission is created as a **GitHub Issue** (primary triage channel) and **always** appended to a local **NDJSON** log (fallback + audit). If no GitHub token is configured, the app silently runs local-only.

## Out of scope (deferred / dropped)

- In-app **admin panel** to browse/resolve feedback (the reference has one; deferred).
- **Feedback analyzer** / AI triage (deferred).
- **i18n** — EVA is English-only; single-language strings only.
- `user_level` and ISA element/connection counts from the reference (not applicable to EVA) — replaced by EVA-relevant context.
- File/screenshot attachments, email notifications, user authentication.

## Architecture

A single new module `eva_feedback.py`, following EVA's existing `eva_*.py` convention. It keeps all feedback logic, UI helpers, and the server-handler registrar out of the already-large `app.py` (~193 KB) and `eva_ui.py` (~105 KB), and is independently unit-testable (mock `requests`, no real network).

- `eva_ui.py` places a `💬 Feedback` button in the app header.
- `app.py` calls `eva_feedback.register_feedback_handlers(input, output, session)` inside its `server(input, output, session)` function.

### Module API (`eva_feedback.py`)

```python
def collect_system_context(input, session=None) -> dict
def save_feedback_local(payload: dict, path: str | None = None) -> bool
def create_github_issue(title: str, body: str, labels: list[str]) -> dict | None
def submit_feedback(title, description, type_, steps, context, log_path=None) -> dict
def feedback_button()  -> "ui element"        # header action button
def feedback_modal()   -> "ui.Modal"          # the form
def register_feedback_handlers(input, output, session) -> None
```

- `collect_system_context` — returns the auto-context dict (see *Auto-collected context*). Pure/defensive: every field wrapped so a failure yields `"unknown"`/`0`, never raises.
- `save_feedback_local` — append one JSON object + `\n` to the NDJSON log (append-only, no read-modify-write). Wrapped in `try/except`; returns `False` on error (disk/permission) after logging.
- `create_github_issue` — `requests.post` to the GitHub Issues REST API; returns `{"url", "number"}` on 200/201, else `None`. Returns `None` immediately if no token. 10-second timeout.
- `submit_feedback` — orchestrates: build payload → `save_feedback_local` (always, first) → `create_github_issue` (if token) → return `{"local_success", "github_success", "github_url"}`.
- `feedback_button` / `feedback_modal` — return Shiny UI objects (no side effects).
- `register_feedback_handlers` — registers the reactive effects: show modal, toggle steps field, validate + rate-limit + submit, notify, close.

### UI — button + modal

- **Button:** `ui.input_action_button("show_feedback_modal", "💬 Feedback", class_="btn-outline-secondary btn-sm")`, placed in the EVA header row (near the title/version).
- **Modal** (`ui.modal(..., easy_close=False, footer=[Submit, Cancel])`) — `easy_close=False` so an outside click can't discard a partially filled form. Fields:

  | Field | Control | Required | Visibility | Limit |
  |-------|---------|----------|------------|-------|
  | Report type | `ui.input_radio_buttons` — values `bug`/`suggestion`/`general`, labels "Bug Report"/"Improvement Suggestion"/"General Feedback" | Yes | Always | — |
  | Title | `ui.input_text` | Yes | Always | maxlength 200 |
  | Description | `ui.input_text_area` (5 rows) | Yes | Always | maxlength 5000 |
  | Steps to reproduce | `ui.input_text_area` (3 rows) | No | Bug only | maxlength 2000 |
  | System information | read-only collapsible block | n/a | Always (collapsed) | — |

- The **Steps to reproduce** field is wrapped in `ui.panel_conditional("input.feedback_type === 'bug'", …)` so it appears only for Bug reports — client-side, no server round-trip (Python-Shiny's equivalent of R's `conditionalPanel`).
- `browser_info` is captured by a small `ui.tags.script` in the modal body running `Shiny.setInputValue('fb_browser_info', navigator.userAgent)` on open.
- **Input ids:** `show_feedback_modal` (trigger), `feedback_type`, `feedback_title`, `feedback_description`, `feedback_steps`, `feedback_submit`, `fb_browser_info`. Cancel uses the modal's built-in dismiss.

### Submission flow

```
Submit clicked
  → disable Submit button
  → server-side rate-limit: reactive.value holds last-submit time; reject if < 30 s ago
  → validate: title and description non-empty, within length limits
  → build payload (form fields + auto-context)
  → save_feedback_local(payload)          # always, wrapped in try/except
  → if token configured: create_github_issue(...)
        success → notification "Thank you! Submitted." (+ issue URL)
        failure → notification "Thank you! Saved."
     else      → notification "Thank you! Saved."
  → ui.modal_remove()
  → record last-submit time
```

**Rate-limit scope:** the last-submit time is a per-session `reactive.value`. Each modal open builds a fresh `feedback_modal()`, so there is no need to re-enable a button across opens (the R reference's `shinyjs::delay` re-enable is dropped). The 30 s server-side check is the real guard; the client-side disable only prevents double-clicks within one open. Two browser tabs are separate sessions and each gets its own limiter — acceptable for this use case.

### Storage & configuration

- **Local log:** NDJSON, append-only. Path from env `MARBEFES_EVA_FEEDBACK_LOG`; default `<app_dir>/feedback/user_feedback_log.ndjson`. The directory is created if missing. It lives in a folder the deploy script never uploads or wipes, so it **persists across deploys**. Gitignored. **Concurrency:** one `json.dumps(payload) + "\n"` is a single append with no read-modify-write — safe for sequential/low-volume use; multi-worker deployments get best-effort safety from the append-only pattern.
- **GitHub:** token from env `MARBEFES_EVA_GITHUB_TOKEN`; target repo from env `MARBEFES_EVA_GITHUB_REPO`, default `razinkele/marbefes-eva-app`. (Configurable so issues can later be pointed at a **private** repo, since the default repo is public.) Labels by type:
  - Bug → `["bug", "user-reported"]`
  - Suggestion → `["enhancement", "user-reported"]`
  - General → `["feedback", "user-reported"]`
- **GitHub API:** `POST https://api.github.com/repos/{owner}/{repo}/issues`, headers `Authorization: Bearer <token>` and `Accept: application/vnd.github+json`; `{owner}`/`{repo}` parsed from `MARBEFES_EVA_GITHUB_REPO` (`owner/repo` form). Success = HTTP 201 (also accept 200); any other status or a request exception → return `None` and fall through to local-only.
- **Issue body:** Markdown — `## Description`, optional `## Steps to Reproduce`, and a collapsible `<details>` block holding the system-context JSON.

### Auto-collected context (EVA-adapted, no PII)

Gathered at submit time via `collect_system_context`:

- `app_version` — `version.get_version()` (e.g., `"3.8.0"`)
- `current_tab` — id of the active main navset panel, read defensively from the relevant `input.*` nav id (`"unknown"` if unavailable)
- `browser_info` — `navigator.userAgent` via `input.fb_browser_info`
- `selected_area` — selected BBT/study area if present in inputs, else `"unknown"`
- `dataset_loaded` — boolean; plus `feature_count` (integer only) when a dataset is loaded
- `timestamp` — ISO-8601 UTC

No personal data: no uploaded file names, no uploaded data content, no usernames.

### Security

- GitHub token is a **server-side env var**, never sent to the client.
- **30-second server-side rate limit** via `reactive.value` (not bypassable from the browser console); Submit button also disabled client-side for UX.
- Length limits enforced **server-side** in `validate_feedback`; placeholders state the limits as a client hint (Shiny for Python's `input_text`/`input_text_area` expose no native `maxlength`).
- No user content is ever `eval`'d — all values are treated as strings.
- Auto-context is aggregate/technical only (no PII).
- GitHub call has a 10-second timeout; any error falls through to local-only.

### Files to create / modify

| File | Action | Purpose |
|------|--------|---------|
| `eva_feedback.py` | create | Logic + UI helpers + `register_feedback_handlers` |
| `eva_ui.py` | modify | Add the `💬 Feedback` header button |
| `app.py` | modify | Call `register_feedback_handlers(input, output, session)` in `server` |
| `.gitignore` | modify | Ignore `feedback/` (the local log dir) |
| `tests/test_eva_feedback.py` | create | pytest unit tests |

`requests` is already in `requirements.txt` — no dependency change.

### Testing (pytest; mock `requests`, no real API calls)

- `save_feedback_local` writes valid NDJSON and appends without corrupting prior lines; returns `False` (no raise) on write error.
- `create_github_issue` builds the correct API payload + headers (monkeypatched `requests.post`); returns `None` when the token env var is unset.
- `submit_feedback` falls back to local-only when no token; rejects empty title/description; returns the expected result dict shape.
- `collect_system_context` returns all expected keys with safe defaults when inputs are missing.

## Deployment notes

- Set `MARBEFES_EVA_GITHUB_TOKEN` (and optionally `MARBEFES_EVA_GITHUB_REPO`) in the laguna shiny-server environment (same place as `MARBEFES_EVA_DATA_PATH`). Without it, the feature degrades gracefully to local-only.
- The deploy script uploads `*.py`, `scripts/`, `www/`, and select `data/*` files; `eva_feedback.py` ships as a normal module. The `feedback/` log directory is created at runtime and is not touched by deploys.
- **Local-log writability:** the worker runs as `shiny`, but the app dir is owned `razinka:shiny` mode 755, so `shiny` cannot create `feedback/` there. On laguna, set `MARBEFES_EVA_FEEDBACK_LOG` to a `shiny`-writable path **or** pre-create the dir: `sudo install -d -o shiny -g shiny -m 775 /srv/shiny-server/EVA/feedback`. GitHub Issue creation is unaffected; only the local audit log needs this.
