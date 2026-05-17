# Changelog

All notable changes to Neon White Tools are documented here.

---

## [Unreleased]

### Added
- **Compare Players & Player Lookup — medal count breakdown**: when the Medals toggle is on, a row of colored MedalBadge pills with per-tier counts appears in the footer (Player Lookup) and in the stats strip (Compare Players, one row per player). Only tiers with at least one entry are shown, ordered rarest → most common. Hidden when Medals is off.
- **Compare Players — sort & filter dropdowns**: available in chapter and game modes. Sort options: Level (default), P1 Rank, P2 Rank, P1 Lead, P2 Lead, Closest Gap, Medal Tier. Filter options: All (default), P1 Leads, P2 Leads, Gap > 1s, Medal Mismatch, Missing. Rows with a missing player always fall to the bottom under non-level sorts. Sort and filter reset to defaults on each new Compare run.
- **Compare Players — summary stats strip**: two-line panel shown above the table in chapter and game modes. Line 1: win record (`P1 X–Y P2`), signed total delta, tie count, missing count. Line 2: biggest lead (player + level + delta), closest gap (level + ±delta), best rank for each player. Hides when no rows are loaded.

---

## [1.0.0-beta.2] — 2026-05-14

### Fixed
- **Medal thresholds corrected for 33 levels** — chapters 7–12 and 5 violet sidequests had thresholds significantly tighter than in-game values, causing late-game levels to show BRONZE instead of the correct medal (DEV, ACE, etc.)

---

## [1.0.0-beta.1] — 2026-05-12

### Added
- **Ghosts library wired**: 472 ghost replays across 121 levels now load in-app from the published Google Sheet
- **`tools/build_ghosts_sheet.py`**: one-shot dev script to walk the Drive tree (`Ghosts/<Chapter>/<Level>/<Medal>/<Player> - <Time>/`) and write the Ghosts index sheet; handles `1-1 `/ `V-1 `/ `R-1 `/ `Y-1 ` folder prefixes automatically; re-running is idempotent

---

## Resources (M4 cont.) — 2026-05-07

### Added
- **Route Videos page**: stage × medal picker showing YouTube route videos; primary + alternate per medal tier; iframe embed with fallback to "Open in YouTube" on load error
- **Ghosts page**: stage × medal picker; "Open in browser" links to Drive ghost replays; empty-state message when no ghosts indexed for a combination
- Both resource sheets fetched anonymously via GViz CSV endpoint (no OAuth, no API key required at runtime)

### Fixed
- YouTube embeds failing with error 153: app now serves frontend over a local `127.0.0.1` HTTP server instead of `file://`, giving the page a real origin
- Medal target time display: cutoff was showing the exclusive boundary; display now shows `cutoff − 1ms` (the max qualifying time)
- `pick_folder` updated to `webview.FileDialog.FOLDER` API

---

## Leaderboard Tools — 2026-05-07

### Added
- **Compare Players page**: side-by-side time comparison for two Steam IDs across a level / chapter / whole game; faster time highlighted; Δ column with signed seconds; medals toggle; Normal / Large text; Copy to clipboard
- **Compare Players CSV export**: `display / csv / both` output mode matching Player Lookup; filename `P1_vs_P2_context.csv`
- **Player Lookup — Avg Placement toggle**: opt-in footer showing average rank across queried levels post-run; denominator reflects chapter or whole-game scope
- **Player Lookup — Medals toggle**: color-coded medal badge next to each time (community tiers included: Blood Diamond, Topaz, Sapphire, Amethyst, Emerald)
- **Player Lookup — Text size toggle**: Normal / Large, also extended to Level Search and Global Export
- **Output mode (display / csv / both)** on all three leaderboard pages (Global Export, Level Search, Player Lookup)
- Button placement standardized: Run / Stop moved to bottom of parameters panel on all leaderboard pages to match Rush Tools pattern

### Fixed
- Player Lookup CSV filename now uses the player's Steam display name instead of the literal string "player"
- Steam ID returned as string to prevent JavaScript precision loss on 64-bit IDs

---

## Seed Finder — 2026-05-07

### Added
- **Hell Rush Mode**: White / Mikey only; filters seeds by minimum healthpack-spacing score (0–100); results sorted best-first on completion; score badge on each seed card; ♥ glyph on healthpack levels in the expanded grid
- **Force First Level**: White / Mikey only; constrains the first shuffled position to a specific level
- **Excluded Levels**: White / Mikey only; drops seeds where any listed level appears in the first N positions; amber cell tint in results; stacks with Force First and Hell Rush
- **Order Matters? toggle**: Violet / Red / Yellow only; requires target levels to appear in exact user-specified positions ("No - Any Order" / "Yes - Exact Order")
- Rush-aware placeholder text on the desired-starting-levels field

### Fixed
- Healthpack heart glyph moved inline with level name (was trailing at far right in fullscreen)
- Heart glyph size increased 9 → 12 px and color slightly saturated

---

## M3 — Leaderboard + Steam (2026-05-06 / 2026-05-07)

### Added
- Global Export, Level Search, and Player Lookup pages fully wired to live Steam leaderboard data
- Steamworks polling moved from tkinter `root.after` loop to a daemon thread (pywebview-compatible)
- Settings page: Steam DLL path picker, Google Sheets config, theme toggle, log pane
- Medal tier resolution for community medals (Blood Diamond / Topaz / Sapphire / Amethyst / Emerald) checked first, then standard tiers (DEV / ACE / GOLD / SILVER / BRONZE)

---

## M2 — Seed Finder + Run Timer (2026-05-06)

### Added
- Seed Finder fully wired: live seed search with progress streaming, Stop button, result cards with expanded level grid
- Run Timer wired: splits input, cumulative time calculation, medal column, copy in three formats (times / splits / medals)
- Blood Diamond and Topaz community medal tiers added to Run Timer
- Medal toggle on Run Timer results

### Fixed
- Seed Finder stop / done state race conditions
- Stop status bleeding into subsequent runs
- Medal check order (community tiers evaluated before standard tiers)
- Reorder / Standardize NameError; splits copy format split into three distinct outputs

---

## M1 — Core scaffold + Rush parsing (2026-05-06)

### Added
- pywebview + React frontend scaffold: esbuild pipeline, `JsApi` bridge, Pydantic request/response models
- Seed Parser, Splits Updater, and Standardize Splits pages fully wired (offline — no Steam required)
- Hell Rush scoring formula and authoritative 11-level healthpack list

---

## Infrastructure

### Added
- **shuffle.dll: `find_seeds_batch`** (~12× seed-search speedup; 89k → 1.1M seeds/sec); two `uint64_t` masks for 96-level support; `arr[128]` buffer; 250k slab size
- **Logging**: rotating file handler (`logs/app.log`, 5 MB × 3); silent error sites replaced with structured log calls across load_config, Steam init, Sheets auth, Google libs import, font load
- Module extraction: `steam_api.py`, `sheets.py`, `rush_data.py`, `shuffle_lib.py`, `seed_search.py`, tab mixins — all separated from the monolithic entry point
- Seed-finder subset check: removed redundant `set()` allocation (~1.8× faster check)

### Fixed
- int32 overflow in `System.Random` warmup wrapping for high seed values
- Shuffle output mapping formula (`r%N` → `Random.Next(N)` multiply)
- Seed finder access violation in worker processes
