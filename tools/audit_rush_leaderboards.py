#!/usr/bin/env python3
"""
tools/audit_rush_leaderboards.py — brute-force discover the Steam leaderboard
stat-codes for the 10 Rush boards (White/Red/Violet/Yellow/Mikey × Heaven/Hell).

Steam's client API has no "list all leaderboards" call, and Neon White's boards
are not published as community boards, so the only client-side discovery channel
is to guess a name and ask FindLeaderboard: a resolved handle means the board
exists, None means it doesn't. This generates a ranked candidate list from the
known level-code conventions (ALL_CAPS, underscore-separated) and probes each.

Run from the repo root with Steam running and logged in:
    python tools/audit_rush_leaderboards.py [--dll PATH\\to\\steam_api64.dll]

Optional:
    --extra FILE   newline-separated extra candidate names to probe first
    --limit N      probe only the first N candidates (smoke test)
    --out FILE     report path (default: 00_Inbox/rush_leaderboard_probe.md)

Any hit is the authoritative internal name — drop it into a RUSH_LEADERBOARDS
map in rush_data.py. If nothing hits, the convention is unguessable from here;
fall back to decompiling LevelRushStats / LeaderboardIntegrationSteam, or ask
the NeonLite / NeonNetwork modders for the exact strings.
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

# Character tokens for the 5 rushes. White is the main game; red/violet/yellow
# match the colored side-chapter keys already in rush_data.RUSH_LEVELS; mikey is
# the 5th. Extra aliases hedge against the game using a different internal token.
CHARS = ["WHITE", "RED", "VIOLET", "YELLOW", "MIKEY"]
CHAR_ALIASES = {
    "WHITE":  ["WHITE", "NEON", "MAIN", "96"],
    "RED":    ["RED"],
    "VIOLET": ["VIOLET", "PURPLE"],
    "YELLOW": ["YELLOW"],
    "MIKEY":  ["MIKEY", "MIKE"],
}
DIFFS = ["HEAVEN", "HELL"]

# Name templates. {C} = character token, {D} = difficulty token. Ordered most-
# to least-likely given the GRID_/TUT_ scene-style convention of level codes.
TEMPLATES = [
    "RUSH_{C}_{D}",
    "{C}_RUSH_{D}",
    "{C}_{D}_RUSH",
    "LEVELRUSH_{C}_{D}",
    "LEVEL_RUSH_{C}_{D}",
    "{C}_{D}",
    "{D}_RUSH_{C}",
    "RUSH_{D}_{C}",
    "{C}_{D}_LEVELRUSH",
    "{D}_{C}_RUSH",
    "{D}_{C}",
    "RUSH_{C}{D}",
    "{C}RUSH_{D}",
]

# Whole-game candidates where "White" may not appear as a token at all (the main
# rush might just be the bare difficulty).
GENERIC = [
    "RUSH_{D}", "{D}_RUSH", "LEVELRUSH_{D}", "LEVEL_RUSH_{D}",
    "{D}_RUSH_WHITE", "RUSH", "LEVELRUSH", "LEVEL_RUSH",
]


def _expand(template: str, char: str | None, diff: str) -> list[str]:
    """Render a template into ALL_CAPS, lowercase, and no-underscore variants."""
    base = template.replace("{C}", char or "").replace("{D}", diff)
    base = base.strip("_").replace("__", "_")
    out = [base, base.lower(), base.replace("_", "")]
    return out


def build_candidates(extra: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(name: str) -> None:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)

    for name in extra:
        add(name.strip())

    # Per-character × difficulty, walking templates outer so the most-likely
    # shape is tried for every rush before moving to the next shape.
    for template in TEMPLATES:
        for diff in DIFFS:
            for char in CHARS:
                for alias in CHAR_ALIASES[char]:
                    for variant in _expand(template, alias, diff):
                        add(variant)

    for template in GENERIC:
        for diff in DIFFS:
            for variant in _expand(template, None, diff):
                add(variant)

    return ordered


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe for Rush Steam leaderboard names.")
    parser.add_argument("--dll", default=str(_STEAMSCRAPER / "steam_api64.dll"),
                        help="Path to steam_api64.dll (default: SteamScraper/steam_api64.dll)")
    parser.add_argument("--out", default=str(_REPO / "00_Inbox" / "rush_leaderboard_probe.md"),
                        help="Output markdown path (default: 00_Inbox/rush_leaderboard_probe.md)")
    parser.add_argument("--extra", default=None,
                        help="File of newline-separated candidate names to probe first")
    parser.add_argument("--limit", type=int, default=0,
                        help="Probe only the first N candidates (0 = all)")
    args = parser.parse_args()

    dll_path = Path(args.dll)
    if not dll_path.exists():
        print(f"ERROR: DLL not found at {dll_path}", file=sys.stderr)
        return 2

    extra: list[str] = []
    if args.extra:
        extra_path = Path(args.extra)
        if not extra_path.exists():
            print(f"ERROR: --extra file not found at {extra_path}", file=sys.stderr)
            return 2
        extra = [ln for ln in extra_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    candidates = build_candidates(extra)
    if args.limit > 0:
        candidates = candidates[:args.limit]

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

    # Sanity-check the oracle: a known level code must resolve, a junk one must not.
    sane_hit = steam_api.find_leaderboard("GRID_PORT")
    sane_miss = steam_api.find_leaderboard("ZZ_DEFINITELY_NOT_A_BOARD_ZZ")
    if not (sane_hit and not sane_miss):
        print(f"WARNING: oracle sanity check looks off "
              f"(GRID_PORT->{sane_hit!r}, junk->{sane_miss!r}). "
              f"Results may be unreliable.", file=sys.stderr)

    print(f"Probing {len(candidates)} candidate names …", file=sys.stderr)
    hits: list[str] = []
    for i, name in enumerate(candidates, 1):
        handle = steam_api.find_leaderboard(name)
        found = handle is not None and handle != 0
        if found:
            hits.append(name)
        marker = "✓ HIT" if found else "·"
        print(f"  [{i:4d}/{len(candidates)}] {marker:6s} {name}", file=sys.stderr)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Rush leaderboard probe — Neon White",
        "",
        f"Brute-forced via `tools/audit_rush_leaderboards.py`. "
        f"Probed {len(candidates)} candidate names.",
        "",
        f"- **Hits:** {len(hits)}",
        "",
    ]
    if hits:
        lines.append("These resolved to a live Steam leaderboard handle — authoritative names:")
        lines.append("")
        lines.append("| Internal name |")
        lines.append("|---|")
        for name in hits:
            lines.append(f"| `{name}` |")
    else:
        lines.append("_No candidate resolved._ The naming convention isn't guessable from "
                     "the level-code pattern. Next: decompile `LevelRushStats` / "
                     "`LeaderboardIntegrationSteam`, or ask the NeonLite / NeonNetwork "
                     "modders for the exact strings, then re-run with `--extra`.")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {out_path.relative_to(_REPO)} — {len(hits)} hit(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
