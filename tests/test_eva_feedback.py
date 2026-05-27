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
