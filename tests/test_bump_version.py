"""Tests for scripts/bump_version.py.

Pure-function tests (no file IO) for version math + rewriters.
Integration tests use tmp_path fixtures to exercise the full CLI.
"""
from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

import pytest

from scripts.bump_version import (
    VersionInfo,
    ChangelogEntries,
    bump,
    build_changelog_entry,
    prepend_changelog,
    read_version_py,
    rewrite_readme,
    rewrite_tutorial,
    rewrite_user_manual,
    rewrite_version_py,
    run,
)


# ---------------------------------------------------------------------------
# Version math
# ---------------------------------------------------------------------------
class TestBump:
    def _v(self, major=3, minor=7, patch=0, codename="SDM Intelligence"):
        return VersionInfo(major, minor, patch, codename)

    def test_patch_increments_patch_only(self):
        assert bump(self._v(3, 7, 0), "patch") == self._v(3, 7, 1)

    def test_minor_resets_patch(self):
        assert bump(self._v(3, 7, 5), "minor") == self._v(3, 8, 0)

    def test_major_resets_minor_and_patch(self):
        assert bump(self._v(3, 7, 5), "major") == self._v(4, 0, 0)

    def test_codename_unchanged_by_bump(self):
        assert bump(self._v(3, 7, 0), "patch").codename == "SDM Intelligence"

    def test_invalid_part(self):
        with pytest.raises(ValueError):
            bump(self._v(), "beta")


# ---------------------------------------------------------------------------
# read_version_py
# ---------------------------------------------------------------------------
class TestReadVersionPy:
    def test_extracts_all_fields(self):
        text = dedent('''\
            __version__ = "1.2.3"
            VERSION_MAJOR = 1
            VERSION_MINOR = 2
            VERSION_PATCH = 3
            VERSION_LABEL = ""
            BUILD_DATE = "2026-01-01"
            CODENAME = "Test"
        ''')
        info = read_version_py(text)
        assert info == VersionInfo(1, 2, 3, "Test")

    def test_missing_field_raises(self):
        text = '__version__ = "1.2.3"\n'  # missing MAJOR/MINOR/PATCH/CODENAME
        with pytest.raises(RuntimeError, match="missing required fields"):
            read_version_py(text)


# ---------------------------------------------------------------------------
# rewrite_version_py
# ---------------------------------------------------------------------------
class TestRewriteVersionPy:
    TEMPLATE = dedent('''\
        """Doc."""
        __version__ = "1.2.3"
        VERSION_MAJOR = 1
        VERSION_MINOR = 2
        VERSION_PATCH = 3
        BUILD_DATE = "2026-01-01"
        CODENAME = "OLD"
    ''')

    def test_patch_bump_touches_version_and_date(self):
        new_info = VersionInfo(1, 2, 4, "OLD")
        out = rewrite_version_py(self.TEMPLATE, new_info, "2026-04-23", new_codename=None)
        assert '__version__ = "1.2.4"' in out
        assert "VERSION_PATCH = 4" in out
        assert 'BUILD_DATE = "2026-04-23"' in out
        assert 'CODENAME = "OLD"' in out  # untouched

    def test_codename_override(self):
        new_info = VersionInfo(2, 0, 0, "OLD")  # codename in info is ignored
        out = rewrite_version_py(self.TEMPLATE, new_info, "2026-04-23", new_codename="NEW")
        assert 'CODENAME = "NEW"' in out

    def test_preserves_docstring_and_comments(self):
        new_info = VersionInfo(1, 2, 4, "OLD")
        out = rewrite_version_py(self.TEMPLATE, new_info, "2026-04-23", new_codename=None)
        assert out.startswith('"""Doc."""')


# ---------------------------------------------------------------------------
# Changelog entry building
# ---------------------------------------------------------------------------
class TestChangelogEntry:
    def test_header_includes_codename(self):
        entry = build_changelog_entry(
            "1.2.3", "2026-04-23", "My Codename",
            ChangelogEntries(added=["a"]), notes_md=None,
        )
        assert entry.startswith('## [1.2.3] - 2026-04-23 "My Codename"\n')

    def test_header_without_codename(self):
        entry = build_changelog_entry(
            "1.2.3", "2026-04-23", "",
            ChangelogEntries(fixed=["bug"]), notes_md=None,
        )
        assert entry.startswith("## [1.2.3] - 2026-04-23\n")
        assert "### Fixed" in entry
        assert "- bug" in entry

    def test_grouped_sections(self):
        entry = build_changelog_entry(
            "1.0.0", "2026-04-23", "Init",
            ChangelogEntries(added=["a1", "a2"], fixed=["f1"], removed=["r1"]),
            notes_md=None,
        )
        assert "### Added" in entry
        assert "- a1\n- a2" in entry
        assert "### Fixed" in entry
        assert "- f1" in entry
        assert "### Removed" in entry
        assert "- r1" in entry
        # Changed absent because no items
        assert "### Changed" not in entry

    def test_notes_file_overrides_entries(self):
        entry = build_changelog_entry(
            "1.0.0", "2026-04-23", "",
            ChangelogEntries(added=["ignored"]),
            notes_md="Free-form notes.\n",
        )
        assert "Free-form notes." in entry
        assert "ignored" not in entry

    def test_empty_entries_gets_placeholder(self):
        entry = build_changelog_entry(
            "1.0.0", "2026-04-23", "", ChangelogEntries(), notes_md=None,
        )
        assert "_No release notes provided._" in entry


class TestPrependChangelog:
    def test_inserts_above_first_section(self):
        existing = dedent('''\
            # Changelog

            All notable changes here.

            ## [1.0.0] - 2026-01-01 "Init"

            ### Added
            - first release
        ''')
        entry = '## [1.1.0] - 2026-04-23 "Next"\n\n### Added\n- new thing\n\n'
        result = prepend_changelog(existing, entry)
        i_11 = result.index("## [1.1.0]")
        i_10 = result.index("## [1.0.0]")
        assert i_11 < i_10
        # Preamble above untouched
        assert result.startswith("# Changelog\n\nAll notable changes here.\n\n")

    def test_raises_when_no_sections(self):
        with pytest.raises(RuntimeError, match="no existing"):
            prepend_changelog("# Changelog\n\nnothing yet\n", "## [1.0.0] ...\n")


# ---------------------------------------------------------------------------
# README / USER_MANUAL / TUTORIAL rewrites
# ---------------------------------------------------------------------------
class TestReadmeRewrite:
    TEMPLATE = dedent('''\
        # MARBEFES EVA v3.7.0

        Ecological Value Assessment.

        **Current version:** 3.7.0 "Old Codename" (2026-04-06) | [CHANGELOG](CHANGELOG.md)

        More body.
    ''')

    def test_title_and_current_version_line_updated(self):
        out = rewrite_readme(self.TEMPLATE, "3.8.0", "New Name", "2026-04-23")
        assert out.startswith("# MARBEFES EVA v3.8.0\n")
        assert '**Current version:** 3.8.0 "New Name" (2026-04-23)' in out
        assert "Ecological Value Assessment." in out  # body preserved

    def test_empty_codename_is_no_suffix(self):
        out = rewrite_readme(self.TEMPLATE, "3.8.0", "", "2026-04-23")
        assert "**Current version:** 3.8.0 (2026-04-23)" in out

    def test_preserves_blank_line_after_title(self):
        """Regression: earlier ``\\s*$`` greedily ate the line after the title
        because ``\\s`` matches ``\\n`` in MULTILINE mode. Line 2 must stay."""
        out = rewrite_readme(self.TEMPLATE, "3.8.0", "New", "2026-04-23")
        lines = out.splitlines()
        assert lines[0] == "# MARBEFES EVA v3.8.0"
        assert lines[1] == "", f"blank line after title removed; lines[1]={lines[1]!r}"
        assert lines[2] == "Ecological Value Assessment."


class TestUserManualRewrite:
    def test_updates_version_header(self):
        text = "# Manual\n\n**Version 3.5.1** | Last updated: 2026-03-18\n\nBody."
        out = rewrite_user_manual(text, "3.8.0", "2026-04-23")
        assert "**Version 3.8.0** | Last updated: 2026-04-23" in out


class TestTutorialRewrite:
    def test_updates_footer_version(self):
        text = "Body.\n\n*Tutorial created for MARBEFES EVA v3.5.1 | Data: LT BBT5*\n"
        out = rewrite_tutorial(text, "3.9.0")
        assert "MARBEFES EVA v3.9.0 | Data: LT BBT5" in out
        assert "v3.5.1" not in out


# ---------------------------------------------------------------------------
# Integration: full CLI run on a tmp-populated tree
# ---------------------------------------------------------------------------
class TestRunCli:
    @pytest.fixture
    def fake_tree(self, tmp_path, monkeypatch):
        """Create a tmp project mirroring the paths bump_version.py expects."""
        root = tmp_path
        (root / "docs").mkdir()

        (root / "version.py").write_text(dedent('''\
            """v"""
            __version__ = "1.0.0"
            VERSION_MAJOR = 1
            VERSION_MINOR = 0
            VERSION_PATCH = 0
            VERSION_LABEL = ""
            BUILD_DATE = "2026-01-01"
            CODENAME = "Init"
        '''), encoding="utf-8")

        (root / "CHANGELOG.md").write_text(dedent('''\
            # Changelog

            ## [1.0.0] - 2026-01-01 "Init"

            ### Added
            - first
        '''), encoding="utf-8")

        (root / "README.md").write_text(dedent('''\
            # MARBEFES EVA v1.0.0

            **Current version:** 1.0.0 "Init" (2026-01-01) | [CHANGELOG](CHANGELOG.md)
        '''), encoding="utf-8")

        (root / "docs" / "USER_MANUAL.md").write_text(
            "# Manual\n\n**Version 1.0.0** | Last updated: 2026-01-01\n", encoding="utf-8",
        )
        (root / "docs" / "TUTORIAL.md").write_text(
            "*Tutorial created for MARBEFES EVA v1.0.0 | Data: demo*\n", encoding="utf-8",
        )

        # Monkey-patch bump_version's module-level paths to point at tmp
        import scripts.bump_version as bv
        monkeypatch.setattr(bv, "PROJECT_ROOT", root)
        monkeypatch.setattr(bv, "VERSION_PY", root / "version.py")
        monkeypatch.setattr(bv, "CHANGELOG", root / "CHANGELOG.md")
        monkeypatch.setattr(bv, "README", root / "README.md")
        monkeypatch.setattr(bv, "USER_MANUAL", root / "docs" / "USER_MANUAL.md")
        monkeypatch.setattr(bv, "TUTORIAL", root / "docs" / "TUTORIAL.md")
        return root

    def test_patch_end_to_end(self, fake_tree, capsys):
        rc = run(["patch", "--fixed", "bug one", "--fixed", "bug two"])
        assert rc == 0

        v = (fake_tree / "version.py").read_text(encoding="utf-8")
        assert '__version__ = "1.0.1"' in v
        assert "VERSION_PATCH = 1" in v
        # BUILD_DATE bumped to today — presence of a 10-char date is enough
        import re as _re
        assert _re.search(r'BUILD_DATE = "20\d{2}-\d{2}-\d{2}"', v)

        cl = (fake_tree / "CHANGELOG.md").read_text(encoding="utf-8")
        assert cl.index("## [1.0.1]") < cl.index("## [1.0.0]")
        assert "- bug one" in cl
        assert "- bug two" in cl

        readme = (fake_tree / "README.md").read_text(encoding="utf-8")
        assert readme.startswith("# MARBEFES EVA v1.0.1\n")

    def test_minor_updates_codename(self, fake_tree, capsys):
        rc = run(["minor", "--codename", "Next", "--added", "feature"])
        assert rc == 0
        v = (fake_tree / "version.py").read_text(encoding="utf-8")
        assert '__version__ = "1.1.0"' in v
        assert 'CODENAME = "Next"' in v
        cl = (fake_tree / "CHANGELOG.md").read_text(encoding="utf-8")
        assert '## [1.1.0] - ' in cl and '"Next"' in cl
        readme = (fake_tree / "README.md").read_text(encoding="utf-8")
        assert '**Current version:** 1.1.0 "Next" (' in readme

    def test_dry_run_writes_nothing(self, fake_tree, capsys):
        before = {
            p: p.read_text(encoding="utf-8") for p in [
                fake_tree / "version.py",
                fake_tree / "CHANGELOG.md",
                fake_tree / "README.md",
                fake_tree / "docs" / "USER_MANUAL.md",
                fake_tree / "docs" / "TUTORIAL.md",
            ]
        }
        rc = run(["patch", "--fixed", "x", "--dry-run"])
        assert rc == 0
        for p, text in before.items():
            assert p.read_text(encoding="utf-8") == text, f"{p} changed in dry-run"
        out = capsys.readouterr().out
        assert "Dry-run: no files written." in out

    def test_major_bump_resets_minor_and_patch(self, fake_tree):
        # Start from 1.0.0; bump patch to get to 1.0.1, then major — that would
        # give 2.0.0. But we only run once per test. Fake from 1.3.5 -> 2.0.0.
        (fake_tree / "version.py").write_text(dedent('''\
            """v"""
            __version__ = "1.3.5"
            VERSION_MAJOR = 1
            VERSION_MINOR = 3
            VERSION_PATCH = 5
            VERSION_LABEL = ""
            BUILD_DATE = "2026-01-01"
            CODENAME = "X"
        '''), encoding="utf-8")
        rc = run(["major", "--codename", "Two", "--added", "breaking"])
        assert rc == 0
        v = (fake_tree / "version.py").read_text(encoding="utf-8")
        assert '__version__ = "2.0.0"' in v
        assert "VERSION_MAJOR = 2" in v
        assert "VERSION_MINOR = 0" in v
        assert "VERSION_PATCH = 0" in v

    def test_unknown_cli_arg_exits_nonzero(self, fake_tree):
        with pytest.raises(SystemExit) as ei:
            run(["weird-part", "--fixed", "x"])
        assert ei.value.code != 0
