"""
avg_rankings — pure board-list + scoring logic for the Average Placement
Leaderboard page.

Ranks players by their AVERAGE per-level placement (consistency), the counterpart
to the GlobalNeonRankings sum-of-times board. Ported from the validated
`avg_rankings_beta/` (seed mode); see plans/2026-06-22-avg-rankings-in-app.md.

No Steam / webview imports on purpose — everything here is plain dicts/lists so
the scoring can be unit-checked on fixtures. bridge.run_avg_rankings does all the
Steamworks I/O and hands the collected ranks to compute_scores().

Data shapes
-----------
ranks        : {steam_id: {board_id: rank_int}}   # only boards the player appears on
entry_counts : {board_id: total_entries_int}      # percentile denominator per board
names        : {steam_id: display_name}
boards       : [board_id, ...]                     # the full in-scope set
"""

from statistics import median

from rush_data import LEVELS, RUSH_LEVELS

# Sidequest stages (Red/Violet/Yellow rush levels). "story" scope = LEVELS minus
# these. Derived from LEVELS (the authoritative full set) rather than the rush
# "96" union, which drops Sacrifice and would silently leave a stage out.
_SIDE_NAMES = (set(RUSH_LEVELS["red"]) | set(RUSH_LEVELS["violet"])
               | set(RUSH_LEVELS["yellow"]))


def board_list(scope="story+side"):
    """Return [(display, internal), ...] for the requested scope.

    "story+side" — every distinct leaderboard stage (LEVELS == 121).
    "story"      — main-game stages only (LEVELS minus sidequests == 97).
    "side"       — Red/Violet/Yellow sidequest stages only (== 24).
    """
    if scope == "story":
        return [(d, i) for d, i in LEVELS if d not in _SIDE_NAMES]
    if scope == "side":
        return [(d, i) for d, i in LEVELS if d in _SIDE_NAMES]
    return list(LEVELS)


def chunks(seq, n):
    """Yield successive n-sized chunks (Valve caps batched user lookups at 100)."""
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def compute_scores(ranks, entry_counts, names, boards, threshold=0.95):
    """Score every player; return (rows, dropped).

    Players below `threshold` board coverage are dropped (gate policy — the
    validated beta default). Each surviving row carries avg_rank / avg_pct /
    median_rank / coverage / boards_n. Caller sorts via sort_rows.
    """
    total = len(boards)
    rows = []
    dropped = 0

    for sid, cells in ranks.items():
        coverage = len(cells) / total if total else 0.0
        if coverage < threshold:
            dropped += 1
            continue

        rank_vals = list(cells.values())
        pct_vals = [r / entry_counts[b] for b, r in cells.items() if entry_counts.get(b)]
        if not rank_vals:
            continue

        rows.append({
            "steam_id": sid,
            "name": names.get(sid, str(sid)),
            "avg_pct": (sum(pct_vals) / len(pct_vals)) if pct_vals else None,
            "avg_rank": sum(rank_vals) / len(rank_vals),
            "median_rank": median(rank_vals),
            "coverage": coverage,
            "boards_n": len(cells),
        })

    return rows, dropped


# Canonical tiebreak chain — every sort runs primary-first then this order, so
# the dense mid-board clusters (many players within a few % of each other)
# always resolve to the same deterministic ordering regardless of the toggle.
_SORT_KEYS = {"rank": "avg_rank", "pct": "avg_pct", "median": "median_rank"}
_CANONICAL = ["avg_rank", "avg_pct", "median_rank"]


def sort_rows(rows, metric="rank"):
    """Sort ascending (lower placement / percentile is better).

    `metric` ("rank" | "pct" | "median") chooses the primary key; ties break by
    the remaining canonical keys then steam_id. None avg_pct sorts last.
    """
    primary = _SORT_KEYS.get(metric, "avg_rank")
    order = [primary] + [k for k in _CANONICAL if k != primary]

    def sk(r):
        parts = []
        for k in order:
            v = r.get(k)
            parts.append((v is None, v if v is not None else 0))
        parts.append(str(r["steam_id"]))
        return tuple(parts)

    return sorted(rows, key=sk)
