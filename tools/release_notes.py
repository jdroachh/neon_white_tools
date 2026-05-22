"""Generate release notes and a CHANGELOG section from git log.

Reads commits between two refs (default: most-recent tag .. HEAD), groups them
by conventional commit prefix, and writes two files at the repo root:

- ``release-notes.md``     PR-style draft for ``gh release create --notes-file``
- ``CHANGELOG-draft.md``   Keep-a-Changelog section block to paste into
                            ``CHANGELOG.md`` above the previous version

Usage:
    python tools/release_notes.py --version 1.1.0
    python tools/release_notes.py --version 1.1.0 --from v1.0.0
    python tools/release_notes.py --version 1.1.0 --from v1.0.0 --to HEAD

Commits with unrecognized prefixes are placed under "Other" in both outputs
and a warning is printed to stderr so they can be rewritten before publishing.

Convention (see RELEASING.md):
    Feat:      added feature              -> CHANGELOG Added,     notes "What's new"
    Fix:       bug fix                    -> CHANGELOG Fixed,     notes "What's fixed"
    Docs:      docs-only change           -> CHANGELOG Docs,      notes "What's fixed"
    Refactor:  code refactor              -> CHANGELOG Internal,  notes omitted
    Perf:      performance work           -> CHANGELOG Internal,  notes omitted
    Chore:     tooling / build / deps     -> omitted from both
    Release:   version bump commits       -> omitted from both
"""

from __future__ import annotations

import argparse
import datetime
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Prefix -> (CHANGELOG section, release-notes section or None to omit)
# None for the CHANGELOG section means "omit from CHANGELOG entirely".
PREFIX_MAP: dict[str, tuple[str | None, str | None]] = {
    "feat":     ("Added",    "What's new"),
    "fix":      ("Fixed",    "What's fixed"),
    "docs":     ("Docs",     "What's fixed"),
    "refactor": ("Internal", None),
    "perf":     ("Internal", None),
    "chore":    (None,       None),
    "release":  (None,       None),
}

# Order sections appear in the output.
CHANGELOG_ORDER = ["Added", "Fixed", "Docs", "Internal", "Other"]
NOTES_ORDER     = ["What's new", "What's fixed", "Other"]


def run(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def latest_tag() -> str | None:
    try:
        return run("describe", "--tags", "--abbrev=0")
    except subprocess.CalledProcessError:
        return None


def parse_commits(from_ref: str, to_ref: str) -> list[tuple[str, str]]:
    """Return a list of (short_hash, subject) tuples between from_ref..to_ref."""
    raw = run("log", f"{from_ref}..{to_ref}", "--pretty=%h%x09%s", "--no-merges")
    if not raw:
        return []
    out = []
    for line in raw.splitlines():
        sha, _, subject = line.partition("\t")
        out.append((sha.strip(), subject.strip()))
    return out


def classify(subject: str) -> tuple[str, str | None, str]:
    """Return (prefix_lower, body, changelog_section).

    If the subject doesn't match a known prefix, prefix_lower is "" and
    changelog_section is "Other".
    """
    prefix_token, sep, body = subject.partition(":")
    if not sep:
        return ("", None, "Other")
    p = prefix_token.strip().lower()
    # Strip optional (scope) so "feat(bingo-proto)" matches "feat".
    if "(" in p:
        p = p.split("(", 1)[0].strip()
    if p in PREFIX_MAP:
        section, _ = PREFIX_MAP[p]
        return (p, body.strip(), section if section is not None else "")
    return ("", None, "Other")


def build_buckets(commits: list[tuple[str, str]]) -> tuple[
    dict[str, list[tuple[str, str]]],  # changelog buckets
    dict[str, list[tuple[str, str]]],  # release-notes buckets
    list[tuple[str, str]],             # unknown-prefix commits (for stderr warning)
]:
    changelog: dict[str, list[tuple[str, str]]] = {k: [] for k in CHANGELOG_ORDER}
    notes:     dict[str, list[tuple[str, str]]] = {k: [] for k in NOTES_ORDER}
    unknown:   list[tuple[str, str]] = []

    for sha, subject in commits:
        prefix, body, cl_section = classify(subject)
        display = body if body else subject

        if cl_section == "Other":
            changelog["Other"].append((sha, subject))
            notes["Other"].append((sha, subject))
            unknown.append((sha, subject))
            continue

        if cl_section:  # not omitted from changelog
            changelog[cl_section].append((sha, display))

        _, notes_section = PREFIX_MAP[prefix]
        if notes_section:
            notes[notes_section].append((sha, display))

    return changelog, notes, unknown


def render_changelog(version: str, buckets: dict[str, list[tuple[str, str]]]) -> str:
    today = datetime.date.today().isoformat()
    lines = [f"## [{version}] — {today}", ""]
    any_section = False
    for section in CHANGELOG_ORDER:
        entries = buckets.get(section, [])
        if not entries:
            continue
        any_section = True
        lines.append(f"### {section}")
        for sha, text in entries:
            lines.append(f"- {text} ({sha})")
        lines.append("")
    if not any_section:
        lines.append("_No commits classified — check the git range._")
        lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def render_notes(version: str, buckets: dict[str, list[tuple[str, str]]]) -> str:
    lines = [
        f"**v{version} — <subtitle>**",
        "",
        "## What's new",
        "",
    ]
    new_entries = buckets.get("What's new", [])
    if new_entries:
        for sha, text in new_entries:
            lines.append(f"- {text}")
    else:
        lines.append("_No new features in this release._")
    lines.append("")

    fixed_entries = buckets.get("What's fixed", [])
    if fixed_entries:
        lines.append("## What's fixed")
        lines.append("")
        for sha, text in fixed_entries:
            lines.append(f"- {text}")
        lines.append("")

    other_entries = buckets.get("Other", [])
    if other_entries:
        lines.append("## Other")
        lines.append("")
        for sha, text in other_entries:
            lines.append(f"- {text} ({sha})")
        lines.append("")
        lines.append("_Review the Other section — these commits had no recognized prefix._")
        lines.append("")

    lines.extend([
        "## Installation",
        "",
        f"1. Download `NeonWhiteLeaderboardTool-{version}.zip` below",
        "2. **Before extracting** — right-click the zip → Properties → check **Unblock** → OK.",
        "   Windows flags files downloaded from the internet; skipping this step may block the app from running.",
        "3. Extract the zip and run `NeonWhiteLeaderboardTool.exe`",
        "4. On first launch, the Welcome page will guide you through locating `steam_api64.dll` from your Neon White install",
        "",
        "Requires Neon White on Steam (game must be installed). Steam must be running.",
        "",
        "See [docs/USAGE.md](https://github.com/jdroachh/neon_white_tools/blob/main/docs/USAGE.md) for a per-page walkthrough.",
        "",
        "**Bug reports** → [Issues tab](https://github.com/jdroachh/neon_white_tools/issues)",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release notes and CHANGELOG draft from git log.")
    parser.add_argument("--version", required=True, help="Version being released (e.g. 1.1.0)")
    parser.add_argument("--from", dest="from_ref", default=None,
                        help="Starting ref (exclusive). Defaults to the most recent tag.")
    parser.add_argument("--to", dest="to_ref", default="HEAD",
                        help="Ending ref (inclusive). Defaults to HEAD.")
    args = parser.parse_args()

    from_ref = args.from_ref or latest_tag()
    if not from_ref:
        print("ERROR: No --from ref given and no tags found. Pass --from explicitly.",
              file=sys.stderr)
        return 2

    print(f"Compiling notes for v{args.version} from {from_ref}..{args.to_ref}",
          file=sys.stderr)

    commits = parse_commits(from_ref, args.to_ref)
    if not commits:
        print("No commits in range. Nothing to write.", file=sys.stderr)
        return 1

    changelog_buckets, notes_buckets, unknown = build_buckets(commits)

    changelog_path = REPO_ROOT / "CHANGELOG-draft.md"
    notes_path     = REPO_ROOT / "release-notes.md"

    changelog_path.write_text(render_changelog(args.version, changelog_buckets), encoding="utf-8")
    notes_path.write_text(render_notes(args.version, notes_buckets), encoding="utf-8")

    print(f"  wrote {changelog_path.relative_to(REPO_ROOT)}", file=sys.stderr)
    print(f"  wrote {notes_path.relative_to(REPO_ROOT)}", file=sys.stderr)

    if unknown:
        print("", file=sys.stderr)
        print(f"WARNING: {len(unknown)} commit(s) had no recognized prefix and were dropped into 'Other':",
              file=sys.stderr)
        for sha, subject in unknown:
            print(f"  {sha} {subject}", file=sys.stderr)
        print("Rewrite these subjects before publishing, or edit the drafts manually.",
              file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
