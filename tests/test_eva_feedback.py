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


def test_validate_feedback_accepts_good_input():
    assert eva_feedback.validate_feedback("Title", "Desc", "bug", "steps") is None


def test_validate_feedback_rejects_empty_title():
    assert eva_feedback.validate_feedback("  ", "Desc") == "Please enter a title."


def test_validate_feedback_rejects_empty_description():
    assert eva_feedback.validate_feedback("Title", "") == "Please enter a description."


def test_validate_feedback_rejects_overlong_title():
    msg = eva_feedback.validate_feedback("x" * 201, "Desc")
    assert "200" in msg


def test_validate_feedback_rejects_overlong_description():
    msg = eva_feedback.validate_feedback("Title", "x" * 5001)
    assert "5000" in msg


def test_validate_feedback_rejects_bad_type():
    assert eva_feedback.validate_feedback("Title", "Desc", "nonsense") == "Invalid report type."


def test_validate_feedback_rejects_overlong_steps():
    msg = eva_feedback.validate_feedback("Title", "Desc", steps="x" * 2001)
    assert "2000" in msg


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


class _FakeInput:
    """Mimics Shiny inputs: input.navigation() etc. are callables."""
    def __init__(self, **values):
        for name, val in values.items():
            setattr(self, name, val)


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
    # Log should have two entries: the initial save (github_url=None) and
    # the audit-completion line with the resolved URL.
    entries = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 2
    assert entries[0]["github_url"] is None
    assert entries[1]["github_url"] == "https://gh/9"


def test_build_issue_body_includes_steps_only_when_present():
    bug = eva_feedback._build_issue_body("Desc", "1. do x", {"app_version": "3.8.0"})
    assert "## Description" in bug
    assert "## Steps to Reproduce" in bug
    assert "app_version" in bug          # context embedded in the <details> JSON
    gen = eva_feedback._build_issue_body("Desc", "", {})
    assert "## Steps to Reproduce" not in gen


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
    # Shiny escapes single quotes in data-display-if; check structure + value separately
    assert "data-display-if" in html
    assert "feedback_type" in html and "'bug'" in html.replace("&apos;", "'")


def test_validate_feedback_reports_bad_type_before_length():
    msg = eva_feedback.validate_feedback("x" * 250, "Desc", "nonsense")
    assert msg == "Invalid report type."
