# Usage

A page-by-page guide to Neon White Tools. Pages are listed in sidebar order.

For installation and build instructions, see the [README](../README.md).

---

## First launch

The **Welcome** page runs once. It tries to locate `steam_api64.dll` automatically
by reading the Steam registry, parsing `libraryfolders.vdf`, and walking your
Neon White install. Click **Find Steam DLL & Connect** to run the search and
connect Steam in one step. If it fails (uncommon Steam install layout, game
moved manually, etc.), use **I'll set it up later** and point the Settings page
at the DLL by hand.

Tick **Don't show again** before dismissing and the Welcome page won't reappear.
On every subsequent launch the app re-opens to whichever tab you used last
(`last_tab` in config), and — if `dll_path` is already set — auto-connects to
Steam in the background so you don't have to hit Connect manually.

---

## Rush Tools

### Seed Parser

Decode a Neon White seed number into its level play-order. Paste the
seed, pick the rush (White, Mikey, Violet, Red, Yellow), and the result grid
shows the levels in the order the game will serve them. Healthpack levels are
flagged with a ♥ on White / Mikey rushes.

### Splits Updater

Reorder an existing set of split times to match a given seed. Use this when you
have splits recorded in *standard* order (Movement, Pummel, Gunner…) and want
them rearranged into *seeded* order.

### Standardize Splits

The inverse of Splits Updater: takes splits recorded in seed order (the order
the game played them on a seeded run) and rearranges them back into
standard level order, so they line up with conventional any% comparisons.

### Seed Finder

Brute-force search for seeds matching a target ruleset.

- **Modes.** *Violet / Red / Yellow* support an **Order Matters?** toggle —
  *Yes* means the target levels must appear in the exact positions you typed;
  *No* means any order. *White / Mikey* always run in "any order" mode plus the
  bonus filters below.
- **Hell Rush** (White / Mikey only). Scores each candidate by healthpack
  spacing on a 0–100 scale; only seeds at or above the minimum survive.
  Results sort best-score-first when the search completes.
- **Force First Level** (White / Mikey only). Constrains the first shuffled
  position to a specific level.
- **Excluded Levels** (White / Mikey only). Drops seeds where any listed level
  appears in the first N positions. Levels matching the exclude rule render
  with an amber tint in the seed cards. Stacks with the other filters.
- **Stop** is non-destructive — it halts the C-side scan but leaves all matches
  already returned visible. Hitting **Find Seed** again starts a fresh range.

Typical scan rate is ~1.1M seeds/sec; the full 2.1B range completes in roughly
3 minutes if you ever need to exhaust it.

### Run Timer

Paste split times and get cumulative totals plus medal labels per split.

Three accepted formats per line:

- `Stomp Traversal 38.28` (trailing whitespace-separated time — what LiveSplit
  exports)
- `Stomp Traversal: 38.28` (colon-separated)
- `38.28` (bare time, no name)

The parser checks the trailing token first, so mixed lines from LiveSplit work
without manual reformatting. The Medals toggle adds standard tier labels
(DEV / ACE / GOLD / SILVER / BRONZE) and community tiers (BLOOD DIAMOND /
TOPAZ / SAPPHIRE / AMETHYST / EMERALD) per split. Use **Copy** to grab the
results in one of three layouts: times only, splits only, or medals only.

---

## Leaderboards

All four pages require Steam to be connected (status pill in the sidebar is
green). Output mode (`display` / `csv` / `both`) is per-page; CSVs land in your
configured `output_folder`.

### Global Export

Download the top N entries per level for every level in the game. `entry_count`
in Settings caps how deep each level pulls (default 200; max is whatever Steam
serves). A full 200-entry × 121-level export takes around 90 seconds.

### Level Search

Look up the leaderboard for any single level. Filter by player name (substring
match, case-insensitive) or by rank range. Toggle text size (Normal / Large)
for screen-share readability.

### Player Lookup

Find one player's times across all levels, a chapter, or an individual level.
Saved profiles dropdown remembers Steam IDs you've saved before.

In Chapter and Whole Game modes, the **Sort** and **Filter** dropdowns are
available: sort by Level (default), Rank, Time, or Medal Tier; filter to All,
Top 10, Top 100, Top 500, or Community Medal Emerald+. The two-line stats strip
above the table shows average / median / best / worst rank and Top 10 / 100 /
500 counts. The Medals toggle (when on) adds a colored pill row of per-tier
counts at the bottom.

### Compare Players

Side-by-side comparison of two Steam IDs across one level, a chapter, or the
whole game. The faster time per row is highlighted; the Δ column shows the
signed delta in seconds.

Sort options: Level, P1 Rank, P2 Rank, P1 Lead, P2 Lead, Closest Gap, Medal
Tier. Filter options: All, P1 Leads, P2 Leads, Gap > 1s, Medal Mismatch,
Missing. The summary stats strip shows the win record (`P1 X–Y P2`), total
delta, biggest lead, closest gap, and each player's best rank. Output mode and
medals toggle behave the same as Player Lookup.

---

## Resources

Ghosts, Route Videos, World Record VODs, Community Guides, and Helpful Links
all fetch from published Google Sheets at startup. No OAuth or API key
required — the sheets are publicly published as CSV. Empty pages on first
launch usually mean the resource load is still in flight; switch tabs and back.

### Community Guides

Tabs across the top filter by guide category (Route, Technical, Medal
Playlists). Each row has a cycling watch-state icon — click to cycle ○ →
✓ → ✗ (unmarked → watched → on watchlist). The Hide Watched and Watchlist
Only filter pills are persistent across sessions.

### Route Videos

Pick a level and medal tier to surface route videos for that combination.
Primary and alternate routes are listed when both exist. Embedded player falls
back to "Open in YouTube" if YouTube blocks the embed.

---

## Settings

- **DLL path.** Path to `steam_api64.dll` from your Neon White install.
  The picker walks you to it; the **Find DLL** button re-runs the auto-search.
- **Output folder.** Where exported CSVs land.
- **Entry count.** Top-N cap for leaderboard pulls (default 200).
- **Accent color.** 8 preset swatches; the chosen color drives most of the UI's
  accent variable. Status indicators (Steam connect light) stay green/red
  regardless.
- **Theme.** Light / dark.
- **Open log folder.** Opens `logs/` next to the EXE — useful if something
  goes wrong and you want to attach `app.log` to a bug report.
