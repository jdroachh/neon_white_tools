# Changelog

All notable changes to Neon White Tools are documented here.

---

## [Unreleased]

---

## [1.3.0] — 2026-05-23

### Added
- **Multi Compare drill panel** — click any cell in Chapter or Whole Game mode to open a 520px breakdown rail showing winner, winning time, lead Δ vs 2nd, top medal, top global rank, and the full 7-column rank table. Replaces the previous side drawer.
- **Multi Compare medals** — medal column in the drill panel + "Top medal" item in the meta strip, gated on the existing **Settings → Show medals** toggle. Same medal labels Compare Players and Player Lookup use (community tiers from NeonLite's `communitymedals.json`).
- **Filter-by-player chips** — `Show only` chip row above the result grid dims all cells whose winner isn't the chosen player to 12% opacity. Click `all` or re-click the active chip to clear.
- **Sort modes** — `chapter / most contested / biggest Δ` segmented control. "Most contested" surfaces chapters where the leading player has the lowest share of wins; "biggest Δ" sorts by the largest winner-to-2nd gap per chapter.
- **`link` icon** — new icon glyph in the shared `Icon` component, now used by Helpful Links in the sidebar (was a placeholder `copy` glyph).

### Changed
- **Multi Compare visual redesign (V2 Balanced)** — page header matches the rest of the app (shared `PageHead` with totals subtitle), all buttons swapped to the shared `<Btn>` component, search-mode + sort use the shared `<Seg>` control, roster pills rendered above an expand-to-edit inline editor.
- **Level mode** now shows the rank table inline instead of a 1-cell grid + drill drawer. No drill panel in Level mode — the whole page is the level detail.
- **Chapter mode** shows only the chosen chapter's row (10 cells) instead of the full whole-game grid. Sort segment hidden in this mode (nothing to reorder); filter chips still work.
- **Standings strip** above the grid is now scope-aware — `/N` reflects the actual run scope (chapter level count, 1 in level mode, 121 in game mode), not always 121.
- **Multi Compare Run button** uses the multicompare 3-silhouette icon to match the sidebar nav.

### Internal
- `MultiCompareRowEvent` gained a `medal: Optional[str]` field populated via `_get_medal(display, time_seconds)` in `run_multi_compare`. Same helper Compare Players + Player Lookup use.
- New `frontend/src/mc-styles.css` — design-handoff tokens + component CSS scoped under `.mc-scope` so the design's `nwt-*` classes can't leak into the rest of the app. `--mc-accent` aliases `var(--accent)` so the user's accent picker still drives the page.
- Extracted `<MetaStrip>` and `<RankTable>` shared by the drill panel and the Level-mode result.
- Per-row "▾ Saved" picker now uses the shared `<SavedProfilesDropdown>` (right-anchored — no more viewport clipping at 10 players in fullscreen).
- Dropped the unused `lastRunAt` / `lastEntryCount` state + `formatRelativeTime` helper that powered the "last run Xm ago" hint (cut from the design).

---

## [1.2.0] — 2026-05-22

### Added
- **Multi Compare page** — new leaderboard tool that compares up to 10 players' Neon White times side-by-side. Roster supports 1–10 players (each with a color, name, initial, and 17-digit Steam ID). Three render modes: **Level** (rank table with rolling and total gaps), **Chapter** (10-cell color-coded strip showing who has the fastest time on each level), **Whole Game** (15 stacked chapter rows across all 121 levels). Clicking any cell in Chapter or Whole Game mode opens a side drawer with that level's full rank breakdown. Per-session in-memory cache means mode-switching after a run is instant. Saved profiles dropdown on each roster row pulls from the existing `saved_profiles` config and greys out players already in the roster.
- **Saved rosters** for Multi Compare — `saved_rosters` config key (cap 25). New "★ save roster" button on Multi Compare opens an inline name prompt; saved rosters surface via the `▾ saved rosters` button at the top of the roster section and fill all rows in one click. Manage saved rosters from Settings via the new third tab on the `profiles | seeds | rosters` toggle (rename, reorder, delete). Loading a saved roster replaces the current roster contents entirely.
- **Shared `SavedProfilesDropdown` component** in `frontend/src/components/` (first component in that directory). Used by Player Lookup, Compare Players, and Multi Compare. Multi Compare additionally uses the `disabledIds` prop to grey out profiles already in the roster.

### Changed
- **Player Lookup and Compare Players use the shared `SavedProfilesDropdown`** instead of their own inlined versions. Visual behavior is identical; ~130 LOC of duplicated dropdown code removed across the two pages.
- **Multi Compare uses batched `DownloadLeaderboardEntriesForUsers`** via the new `steam_api.get_player_entries(lb_handle, [steam_ids])` helper — one Steam round-trip per level instead of one per (level, player). For a 10-player Whole Game compare this cuts round-trips from ~1,331 to ~242. Falls back to per-Steam-ID calls if the batched call returns 0 entries (handles the case where one invalid Steam ID poisons the batch — verified via smoke test).

### Fixed
- **Compare Players also uses batched fetches now** — a single `get_player_entries(lb, [sid1, sid2])` call replaces the previous two `get_player_entry` calls per level. Whole Game compare drops from ~363 to ~242 Steam round-trips (~33% reduction). No behavior change visible to users; just faster.

### Internal
- New `steam_api.get_player_entries(lb_handle, steam_ids)` helper. Accepts up to 100 Steam IDs per call (Valve's documented cap on `DownloadLeaderboardEntriesForUsers`). Returns `{sid: entry_or_None}` keyed by every requested Steam ID. Fall-back per-Steam-ID retry on empty batch result.
- `webview_app/models/multi_compare.py` — Pydantic request + event types (`MultiCompareRequest`, `MultiCompareRowEvent`, `MultiCompareProgressEvent`, `MultiCompareDoneEvent`). Frozen wire shapes; events stream to `window._nwMultiCompareEvent`.
- `webview_app/multi_compare_cache.py` — thread-safe in-memory `(steam_id, level_code) → entry` cache. Lifetime is the pywebview window. Designed to be swapped to a disk-backed implementation later without changing callers.
- `frontend/src/lib/playerColors.js` — neutrally-named 10-color palette (red, orange, yellow, green, blue, navy, violet, pink, cyan, white). Replaces the Tailwind 500-shade indigo with a darker navy `#1e3a8a` so it pairs with blue by lightness rather than competing on hue. Bingo Mode (Phase 2) will reuse this palette for team colors.
- `frontend/src/lib/savedRosters.js` — load/save/add/remove/move/rename helpers for `saved_rosters`. Mirrors `savedProfiles.js` / `savedSeeds.js` patterns.
- `heatmap_prototype/` directory deleted. All functional code graduated into the main app.

---

## [1.1.0] — 2026-05-22

### Added
- Save/favorite seeds in Seed Finder + Seed Parser. Star button on each result card opens a save prompt; saved-seeds dropdown surfaces on both Seed Finder (View / Use-as-search / Delete) and Seed Parser (auto-parse on click); Settings page got a `profiles | seeds` toggle for managing both lists. Cap raised to 50 for each. (dbb27bf)
- Name filter on Global Export results — case-insensitive live filter; counter and Copy button reflect the filtered subset. (724ea22)
- Resources pages (Route Videos, WR VODs, Community Guides, Ghosts, Helpful Links) consolidated into the left-pane layout. (aa8c227)

### Changed
- `open_external_url` allow-list expanded to include `github.com` and `discord.com` (plus `www` and `raw.githubusercontent.com`), so deep-link Discord channels and GitHub repo links from Helpful Links resolve. (c522279)

### Fixed
- Medal gradient text (BLOOD DIAMOND, TOPAZ, etc) no longer disappears after sort/filter changes on Player Lookup, Compare Players, Level Search, and Global Export. Root cause was WebView2 failing to repaint `background-clip: text` on recycled DOM nodes; fixed with stable keys. (df25ce0)

### Internal
- Bingo Mode Phase 0 Steam Lobbies smoke-test sandbox under `SteamScraper/bingo_proto/`. Not bundled in the shipping EXE. (0f0cc5d)
- `tools/audit_leaderboards.py` — one-shot script to audit which `rush_data.LEVELS` have Steam leaderboards (used for Bingo Mode pool sizing). (5d3e942)
- `tools/release_notes.py` — `classify()` now strips a trailing `(scope)` from commit prefixes, so `Feat(bingo-proto):` and similar bucket correctly. (cf159a0)

---

## [1.0.1] — 2026-05-19

### Added
- Saved profiles dropdown on Player Lookup (87cdb17)

### Fixed
- Resource pages (Route Videos, WR VODs, Guides, Ghosts, Helpful Links) no longer stay stuck on "Resources not loaded" / "No guides match" when the background fetch takes longer than 1 s (f53341a)
- Player Lookup and Compare Players Level dropdowns no longer appear empty on first boot due to a `getLevels()` race (f53341a)

### Internal
- tools/release_notes.py + commit-prefix convention (a417593) — was committed after v1.0.0 was published; listed here for completeness

---

## [1.0.0] — 2026-05-18

First public stable release. All beta features carry forward; this entry covers what landed since `1.0.0-beta.3`.

### Changed
- **Auto-connect to Steam on launch.** When `dll_path` is configured and Steam isn't already up, the app initializes Steam in the background during startup. No more clicking Settings → Connect on every launch. If init fails, the app falls through to Settings for manual recovery.

### Docs
- Added `docs/USAGE.md` — a per-page walkthrough of every tab in the app.
- Trimmed stale beta-era Known Issues from `README.md`; the three items listed there were legacy tkinter bugs that don't exist in the shipping pywebview app.
- Removed Gohu font credit; the shipping UI uses Anton-NWT, not Gohu.

---

## [1.0.0-beta.3] — 2026-05-17

### Added
- **Player Lookup — sort & filter dropdowns**: available in chapter and game modes. Sort options: Level (default), Rank, Time, Percentile, Medal Tier. Filter options: All (default), Top 10, Top 100, Top 500, Community Medal (Emerald+). Both reset to defaults on each new Look Up.
- **Player Lookup — expanded stats strip**: two-line panel above the table in chapter and game modes. Line 1: avg rank, median rank, best rank (+ level), worst rank (+ level). Line 2: Top 10 / Top 100 / Top 500 finish counts and total time across played levels. Existing "Average Placement" footer + medal-count pills row remain in place below the table.
- **Compare Players & Player Lookup — medal count breakdown**: when the Medals toggle is on, a row of colored MedalBadge pills with per-tier counts appears in the footer (Player Lookup) and in the stats strip (Compare Players, one row per player). Only tiers with at least one entry are shown, ordered rarest → most common. Hidden when Medals is off.
- **Compare Players — sort & filter dropdowns**: available in chapter and game modes. Sort options: Level (default), P1 Rank, P2 Rank, P1 Lead, P2 Lead, Closest Gap, Medal Tier. Filter options: All (default), P1 Leads, P2 Leads, Gap > 1s, Medal Mismatch, Missing. Rows with a missing player always fall to the bottom under non-level sorts. Sort and filter reset to defaults on each new Compare run.
- **Compare Players — summary stats strip**: two-line panel shown above the table in chapter and game modes. Line 1: win record (`P1 X–Y P2`), signed total delta, tie count, missing count. Line 2: biggest lead (player + level + delta), closest gap (level + ±delta), best rank for each player. Hides when no rows are loaded.

### Fixed
- **Sidebar version label** now sourced from `APP_VERSION` in `bridge.py` via `get_app_version` instead of a hardcoded string, so the sidebar can no longer drift out of sync with the canonical version (was showing `v1.11.0-beta.1` while the app shipped `1.0.0-beta.2`).

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
