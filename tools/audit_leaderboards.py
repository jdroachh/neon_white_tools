#!/usr/bin/env python3
"""
tools/audit_leaderboards.py — one-shot: probe each level in rush_data.LEVELS
for a Steam leaderboard and write coverage report to
00_Inbox/leaderboard_coverage.md.

Run from the repo root with Steam running and logged in:
    python tools/audit_leaderboards.py [--dll PATH\\to\\steam_api64.dll]

If --dll is omitted, defaults to SteamScraper/steam_api64.dll.

Determines the v1 Bingo Mode board pool: any level whose stat-code does NOT
have a Steam leaderboard becomes honor-only or excluded from the pool.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_REPO = _HERE.parent
_STEAMSCRAPER = _REPO / "SteamScraper"

sys.path.insert(0, str(_STEAMSCRAPER))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Steam-leaderboard coverage across LEVELS.")
    parser.add_argument(
        "--dll",
        default=str(_STEAMSCRAPER / "steam_api64.dll"),
        help="Path to steam_api64.dll (default: SteamScraper/steam_api64.dll)",
    )
    parser.add_argument(
        "--out",
        default=str(_REPO / "00_Inbox" / "leaderboard_coverage.md"),
        help="Output markdown path (default: 00_Inbox/leaderboard_coverage.md)",
    )
    args = parser.parse_args()

    dll_path = Path(args.dll)
    if not dll_path.exists():
        print(f"ERROR: DLL not found at {dll_path}", file=sys.stderr)
        return 2

    from rush_data import LEVELS
    import steam_api

    # init_steam writes steam_appid.txt to CWD — chdir to SteamScraper which
    # already has one, so we don't litter the repo root.
    prev_cwd = os.getcwd()
    os.chdir(_STEAMSCRAPER)
    try:
        ok, msg = steam_api.init_steam(str(dll_path))
    finally:
        os.chdir(prev_cwd)
    if not ok:
        print(f"ERROR: init_steam failed: {msg}", file=sys.stderr)
        return 3

    print(f"Probing {len(LEVELS)} levels …", file=sys.stderr)
    found: list[tuple[str, str]] = []
    missing: list[tuple[str, str]] = []
    for i, (display, stat_code) in enumerate(LEVELS, 1):
        handle = steam_api.find_leaderboard(stat_code)
        ok = handle is not None and handle != 0
        (found if ok else missing).append((display, stat_code))
        marker = "✓" if ok else "✗"
        print(f"  [{i:3d}/{len(LEVELS)}] {marker} {display:30s}  {stat_code}",
              file=sys.stderr)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Steam-leaderboard coverage — Neon White",
        "",
        f"Audit run via `tools/audit_leaderboards.py`. Probed {len(LEVELS)} levels.",
        "",
        f"- **With leaderboards:** {len(found)}",
        f"- **Without leaderboards:** {len(missing)}",
        "",
        "Determines the Bingo Mode v1 board pool. Levels in the 'without' list",
        "are honor-only or excluded.",
        "",
        "## Without leaderboards",
        "",
    ]
    if missing:
        lines.append("| Level | Stat code |")
        lines.append("|---|---|")
        for display, code in missing:
            lines.append(f"| {display} | `{code}` |")
    else:
        lines.append("_All probed levels returned a valid leaderboard handle._")
    lines.append("")
    lines.append("## With leaderboards")
    lines.append("")
    lines.append("<details><summary>Click to expand full list</summary>")
    lines.append("")
    lines.append("| Level | Stat code |")
    lines.append("|---|---|")
    for display, code in found:
        lines.append(f"| {display} | `{code}` |")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {out_path.relative_to(_REPO)} — {len(found)}/{len(LEVELS)} covered.",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
