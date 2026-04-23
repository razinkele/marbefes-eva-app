"""Bump the MARBEFES EVA version across every file that carries a version string.

Single source of truth is ``version.py``. This script updates that file plus
the documentation and changelog entries that reference the version number,
then prints a suggested git commit + tag command.

Usage
-----
    python scripts/bump_version.py <patch|minor|major> [options]

Options
-------
    --codename "Name"         Update release codename in version.py.
    --added "text"            Changelog entry under Added. Repeatable.
    --changed "text"          Changelog entry under Changed. Repeatable.
    --fixed "text"            Changelog entry under Fixed. Repeatable.
    --removed "text"          Changelog entry under Removed. Repeatable.
    --notes-file PATH         Read a prepared Markdown block for the changelog
                              entry body (replaces --added/--changed/etc).
    --dry-run                 Print the diffs without writing anything.

Examples
--------
    # Patch release with two bug fixes
    python scripts/bump_version.py patch \\
        --fixed "DOCX download hangs when EVA permissions block shiny user" \\
        --fixed "scripts/ directory not uploaded by deploy_to_laguna_razinka.sh"

    # Minor release with a codename
    python scripts/bump_version.py minor --codename "Timeouts Tamed" \\
        --added "Module-level EVA cache with prewarm thread" \\
        --changed "@render.download handlers raise instead of return None"

    # See what would change without touching disk
    python scripts/bump_version.py patch --fixed "foo" --dry-run
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERSION_PY = PROJECT_ROOT / "version.py"
CHANGELOG = PROJECT_ROOT / "CHANGELOG.md"
README = PROJECT_ROOT / "README.md"
USER_MANUAL = PROJECT_ROOT / "docs" / "USER_MANUAL.md"
TUTORIAL = PROJECT_ROOT / "docs" / "TUTORIAL.md"


# ---------------------------------------------------------------------------
# Parse version.py
# ---------------------------------------------------------------------------
@dataclass
class VersionInfo:
    major: int
    minor: int
    patch: int
    codename: str


def read_version_py(text: str) -> VersionInfo:
    m_major = re.search(r"^VERSION_MAJOR\s*=\s*(\d+)", text, flags=re.MULTILINE)
    m_minor = re.search(r"^VERSION_MINOR\s*=\s*(\d+)", text, flags=re.MULTILINE)
    m_patch = re.search(r"^VERSION_PATCH\s*=\s*(\d+)", text, flags=re.MULTILINE)
    m_code = re.search(r'^CODENAME\s*=\s*"([^"]*)"', text, flags=re.MULTILINE)
    if not all((m_major, m_minor, m_patch, m_code)):
        raise RuntimeError("version.py missing required fields (VERSION_MAJOR/MINOR/PATCH/CODENAME)")
    return VersionInfo(
        major=int(m_major.group(1)),
        minor=int(m_minor.group(1)),
        patch=int(m_patch.group(1)),
        codename=m_code.group(1),
    )


def bump(info: VersionInfo, part: str) -> VersionInfo:
    if part == "major":
        return VersionInfo(info.major + 1, 0, 0, info.codename)
    if part == "minor":
        return VersionInfo(info.major, info.minor + 1, 0, info.codename)
    if part == "patch":
        return VersionInfo(info.major, info.minor, info.patch + 1, info.codename)
    raise ValueError(f"unknown part {part!r}")


# ---------------------------------------------------------------------------
# Rewriters
# ---------------------------------------------------------------------------
def rewrite_version_py(
    text: str, new: VersionInfo, build_date: str, new_codename: str | None
) -> str:
    vstring = f"{new.major}.{new.minor}.{new.patch}"
    out = re.sub(
        r'^__version__\s*=\s*"[^"]*"',
        f'__version__ = "{vstring}"',
        text, count=1, flags=re.MULTILINE,
    )
    out = re.sub(r"^VERSION_MAJOR\s*=\s*\d+", f"VERSION_MAJOR = {new.major}", out, count=1, flags=re.MULTILINE)
    out = re.sub(r"^VERSION_MINOR\s*=\s*\d+", f"VERSION_MINOR = {new.minor}", out, count=1, flags=re.MULTILINE)
    out = re.sub(r"^VERSION_PATCH\s*=\s*\d+", f"VERSION_PATCH = {new.patch}", out, count=1, flags=re.MULTILINE)
    out = re.sub(
        r'^BUILD_DATE\s*=\s*"[^"]*"',
        f'BUILD_DATE = "{build_date}"',
        out, count=1, flags=re.MULTILINE,
    )
    if new_codename is not None:
        out = re.sub(
            r'^CODENAME\s*=\s*"[^"]*"',
            f'CODENAME = "{new_codename}"',
            out, count=1, flags=re.MULTILINE,
        )
    return out


@dataclass
class ChangelogEntries:
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.added or self.changed or self.fixed or self.removed)

    def render_body(self) -> str:
        sections: list[str] = []
        for label, items in (
            ("Added", self.added),
            ("Changed", self.changed),
            ("Fixed", self.fixed),
            ("Removed", self.removed),
        ):
            if items:
                sections.append(f"### {label}")
                sections.extend(f"- {item}" for item in items)
                sections.append("")
        return "\n".join(sections).rstrip() + "\n"


def build_changelog_entry(
    version_str: str, release_date: str, codename: str,
    entries: ChangelogEntries | None, notes_md: str | None,
) -> str:
    header_codename = f' "{codename}"' if codename else ""
    header = f"## [{version_str}] - {release_date}{header_codename}\n\n"
    if notes_md:
        body = notes_md.strip() + "\n\n"
    elif entries and not entries.is_empty():
        body = entries.render_body() + "\n"
    else:
        body = "_No release notes provided._\n\n"
    return header + body


def prepend_changelog(text: str, entry: str) -> str:
    # Insert just above the first `## [` heading.
    m = re.search(r"^## \[", text, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("CHANGELOG.md: no existing `## [x.y.z]` sections found")
    idx = m.start()
    return text[:idx] + entry + text[idx:]


def rewrite_readme(text: str, new_version: str, codename: str, build_date: str) -> str:
    # Line 1: `# MARBEFES EVA vX.Y.Z` — match trailing spaces/tabs only,
    # NOT the newline. (`\s*$` would greedily eat the following blank
    # line because `\s` includes `\n` in multiline mode.)
    out = re.sub(
        r"^# MARBEFES EVA v[\d.]+[ \t]*$",
        f"# MARBEFES EVA v{new_version}",
        text, count=1, flags=re.MULTILINE,
    )
    # Any line that matches "**Current version:** X.Y.Z "Codename" (YYYY-MM-DD)..."
    cname_chunk = f' "{codename}"' if codename else ""
    out = re.sub(
        r'\*\*Current version:\*\*\s*[\d.]+(?:\s+"[^"]*")?\s*\([\d-]+\)',
        f'**Current version:** {new_version}{cname_chunk} ({build_date})',
        out, count=1,
    )
    return out


def rewrite_user_manual(text: str, new_version: str, build_date: str) -> str:
    return re.sub(
        r"\*\*Version\s+[\d.]+\*\*\s*\|\s*Last updated:\s*[\d-]+",
        f"**Version {new_version}** | Last updated: {build_date}",
        text, count=1,
    )


def rewrite_tutorial(text: str, new_version: str) -> str:
    return re.sub(
        r"MARBEFES EVA v[\d.]+(?= \| Data:)",
        f"MARBEFES EVA v{new_version}",
        text, count=1,
    )


# ---------------------------------------------------------------------------
# CLI / orchestration
# ---------------------------------------------------------------------------
def show_diff(path: Path, old: str, new: str) -> None:
    if old == new:
        print(f"  [unchanged]  {path.relative_to(PROJECT_ROOT)}")
        return
    print(f"  [modified]   {path.relative_to(PROJECT_ROOT)}")
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{path.relative_to(PROJECT_ROOT)}",
        tofile=f"b/{path.relative_to(PROJECT_ROOT)}",
        n=2,
    )
    for line in diff:
        print(f"    {line.rstrip()}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="bump_version", description=__doc__.split("\n\n")[0])
    ap.add_argument("part", choices=("major", "minor", "patch"))
    ap.add_argument("--codename", default=None, help="New release codename (kept if omitted)")
    ap.add_argument("--added", action="append", default=[], help="Changelog Added entry. Repeatable.")
    ap.add_argument("--changed", action="append", default=[], help="Changelog Changed entry. Repeatable.")
    ap.add_argument("--fixed", action="append", default=[], help="Changelog Fixed entry. Repeatable.")
    ap.add_argument("--removed", action="append", default=[], help="Changelog Removed entry. Repeatable.")
    ap.add_argument("--notes-file", type=Path, default=None,
                    help="Pre-written Markdown body for the CHANGELOG section (overrides per-section flags).")
    ap.add_argument("--dry-run", action="store_true", help="Show the diffs; do not write files.")
    return ap.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    release_date = date.today().isoformat()

    if not VERSION_PY.exists():
        print(f"ERROR: {VERSION_PY} not found", file=sys.stderr)
        return 2
    vpy_old = VERSION_PY.read_text(encoding="utf-8")
    info = read_version_py(vpy_old)
    new = bump(info, args.part)
    new_codename = args.codename if args.codename is not None else info.codename
    vstring = f"{new.major}.{new.minor}.{new.patch}"
    print(f"Bumping: {info.major}.{info.minor}.{info.patch} '{info.codename}'  ->  "
          f"{vstring} '{new_codename}'  (date: {release_date})")

    # Changelog entries
    notes_md = args.notes_file.read_text(encoding="utf-8") if args.notes_file else None
    entries = ChangelogEntries(
        added=args.added, changed=args.changed, fixed=args.fixed, removed=args.removed,
    )
    if entries.is_empty() and not notes_md:
        print("WARN: No --added/--changed/--fixed/--removed/--notes-file given. "
              "The CHANGELOG entry will be empty.", file=sys.stderr)

    # Compute each file's new content
    vpy_new = rewrite_version_py(vpy_old, new, release_date, args.codename)

    if not CHANGELOG.exists():
        print(f"ERROR: {CHANGELOG} not found", file=sys.stderr)
        return 2
    changelog_old = CHANGELOG.read_text(encoding="utf-8")
    entry_block = build_changelog_entry(vstring, release_date, new_codename, entries, notes_md)
    changelog_new = prepend_changelog(changelog_old, entry_block)

    readme_old = README.read_text(encoding="utf-8") if README.exists() else None
    readme_new = (
        rewrite_readme(readme_old, vstring, new_codename, release_date) if readme_old is not None else None
    )

    manual_old = USER_MANUAL.read_text(encoding="utf-8") if USER_MANUAL.exists() else None
    manual_new = (
        rewrite_user_manual(manual_old, vstring, release_date) if manual_old is not None else None
    )

    tutorial_old = TUTORIAL.read_text(encoding="utf-8") if TUTORIAL.exists() else None
    tutorial_new = (
        rewrite_tutorial(tutorial_old, vstring) if tutorial_old is not None else None
    )

    plan = [
        (VERSION_PY, vpy_old, vpy_new),
        (CHANGELOG, changelog_old, changelog_new),
    ]
    if readme_old is not None:
        plan.append((README, readme_old, readme_new))
    if manual_old is not None:
        plan.append((USER_MANUAL, manual_old, manual_new))
    if tutorial_old is not None:
        plan.append((TUTORIAL, tutorial_old, tutorial_new))

    print()
    print(f"{'-' * 70}")
    print(f"Proposed changes (dry-run={args.dry_run}):")
    print(f"{'-' * 70}")
    for path, old, new_text in plan:
        show_diff(path, old, new_text)

    if args.dry_run:
        print()
        print("Dry-run: no files written.")
        return 0

    for path, old, new_text in plan:
        if old != new_text:
            path.write_text(new_text, encoding="utf-8")
    print()
    print("Files updated.")
    print()
    print("Suggested git commit:")
    print(f'    git add -- {" ".join(str(p.relative_to(PROJECT_ROOT)) for p, _, _ in plan)}')
    notes_summary = (
        (args.added + args.changed + args.fixed + args.removed)
        or ([notes_md.strip().splitlines()[0]] if notes_md else ["version bump"])
    )
    summary_line = notes_summary[0][:80]
    print(f'    git commit -m "chore(version): bump to v{vstring} — {summary_line}"')
    print(f'    git tag v{vstring}')
    print(f'    git push && git push --tags')
    return 0


if __name__ == "__main__":
    sys.exit(run())
