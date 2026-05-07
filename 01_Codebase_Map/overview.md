# Project Overview

**Neon White Leaderboard Tool** — a Windows desktop app (v1.10.5) for scraping, exploring, and analyzing leaderboards for the game [Neon White](https://store.steampowered.com/app/1533420/Neon_White/) via Steam's Steamworks API.

## What it does

- **Global Leaderboard Export** — download the top N entries for every level and save to CSV
- **Level Search** — look up the leaderboard for any individual level
- **Player Lookup** — find a specific player's times across all levels, chapters, or a custom subset
- **Google Sheets Push** — write player data to a Google Sheet (OAuth authenticated)
- **Rush Tools** — a suite of 5 speedrun-focused utilities:
  - *Seed Finder* — searches 2.1B+ seeds to find randomizer runs where your target levels appear early
  - *Seed Parser* — decode any seed number into its resulting level play order
  - *Splits Updater* — reorder your existing split times to match a given seed
  - *Standardize Splits* — convert splits recorded in seed order back to standard level order (sidebar label; internal key `rush_std`)
  - *Timer* — in-development speedrun timer (incomplete). Surfaces standard medal labels (DEV/ACE/GOLD/SILVER/BRONZE) and community medals (BLOOD DIAMOND/TOPAZ/SAPPHIRE/AMETHYST/EMERALD) per split via `_get_medal` (`neonwhite_app.py:1032`), backed by `STANDARD_MEDAL_DATA` (`rush_data.py:198`) and `COMMUNITY_MEDAL_DATA`.

## How to run

**New UI (pywebview — M1+ active development):**
```
cd frontend && npm run build
python -m SteamScraper.webview_app.main
```

**Legacy tkinter app (kept alive through M3):**
```
python SteamScraper/neonwhite_app.py
```

Or launch the compiled `NeonWhiteLeaderboardTool.exe` (built with PyInstaller from `SteamScraper/neonwhite.spec`).

Requires `steam_api64.dll` (from the Neon White game install) at the path set in `neonwhite_config.json`.

## Who it's for

Neon White speedrunners and competitive players who want to analyze leaderboard standings, plan randomizer runs, or push data to community spreadsheets.

## New UI layer (M4 complete — 2026-05-06)

| Path | Responsibility |
|---|---|
| `SteamScraper/webview_app/` | pywebview bridge package |
| `SteamScraper/webview_app/bridge.py` | `JsApi` — all bridge methods (Rush + Leaderboard + Steam + Config + Resources) |
| `SteamScraper/webview_app/hell_rush.py` | Hell Rush spacing scorer (`score_hell_rush`) |
| `SteamScraper/webview_app/resources.py` | Ghosts + Route Videos — fetches two published Google Sheets via GViz CSV (no auth, no API key); caches in-memory once at startup |
| `SteamScraper/webview_app/models/` | Pydantic request/response types for all endpoints |
| `frontend/src/` | JSX source — `shared.jsx`, `api.js`, `pages/` |
| `frontend/dist/` | esbuild output (gitignored) — `bundle.js`, `bundle.css`, `index.html` |
| `data/healthpacks.json` | Authoritative 11-level HP list for Hell Rush mode |

**`start_finder` params:** `rush_name, levels_str, depth, mode, max_seeds, hell_rush=False, hell_rush_min="70"`. When `hell_rush=True` (White/Mikey only), each surviving seed is scored via `score_hell_rush`; seeds below `hell_rush_min` are dropped. `result` events include `score: int|null` and each level cell includes `is_healthpack: bool` (True for White/Mikey rushes when the cell's level is one of the 11 HP levels; False otherwise).

**Bridge methods by group:**
- Rush tools: `ping`, `get_rushes`, `parse_seed`, `reorder_splits`, `standardize_splits`, `get_standard_order`, `start_finder`, `stop_finder`, `load_timer_seed`, `calculate_timer`
- Config: `get_config`, `save_config_field`
- Steam: `init_steam`, `get_steam_status`, `pick_dll_file`
- Leaderboard metadata: `get_levels`, `get_chapters`
- Leaderboard ops (streaming via `_nw<Page>Event`): `run_global_export`, `run_level_search`, `run_player_lookup`, `stop_leaderboard`
- Resources: `get_resources_status`, `get_ghosts`, `get_videos`, `open_external_url` (allow-listed to drive.google.com / docs.google.com / youtube.com / youtu.be)

**Event handlers (JS side):** `window._nwFinderEvent` (Seed Finder), `window._nwGlobalEvent` (Global Export), `window._nwLevelEvent` (Level Search), `window._nwPlayerEvent` (Player Lookup)

All 11 pages live: Seed Parser, Splits Updater, Standardize, Seed Finder, Run Timer, Global Export, Level Search, Player Lookup, Ghosts, Route Videos, Settings.

## Legacy tkinter module layout

`neonwhite_app.py` is the entry point and `NeonWhiteApp` class. UI is split into per-tab mixin modules, all combined into the MRO at class definition. Method bodies live in mixins; shared helpers (`_log`, `_clear_log`, `_clear_table`, `_add_row`, `_build_results_area`, `_section_header`, `_build_radio_group`, `_get_medal`, `_resolve_level_code`, theme/widget defaults, Steam connect, push-to-sheet) stay in core.

| Module | Responsibility |
|---|---|
| `neonwhite_app.py` | App init, theme, shared helpers, Steam connect, push-to-sheet, main loop |
| `tab_sidebar.py` | `SidebarTabMixin` — left nav (collapsible groups), bottom status panel, `_show_section` |
| `tab_global.py` | `GlobalTabMixin` — Global Export tab |
| `tab_level.py` | `LevelTabMixin` — Level Search tab |
| `tab_player.py` | `PlayerTabMixin` — Player Lookup tab (incl. mode-switching sub-frame) |
| `tab_settings.py` | `SettingsTabMixin` — Settings tab + Google Sheets auth/signout |
| `tab_rush_finder.py` | `RushFinderTabMixin` — Seed Finder |
| `tab_rush_parser.py` | `RushParserTabMixin` — Seed Parser |
| `tab_rush_splits.py` | `RushSplitsTabMixin` — Splits Updater |
| `tab_rush_std.py` | `RushStdTabMixin` — Standardize Splits |
| `tab_rush_timer.py` | `RushTimerTabMixin` — Run Timer |
| `fonts.py` | Gohu font load + `gohu()` / `gohu_mono()` factories |
| `rush_data.py` | `LEVELS`, `LEVEL_LOOKUP`, `WHOLE_GAME_LEVELS`, `CHAPTERS`, `STANDARD_MEDAL_DATA` |
| `steam_api.py` | Steamworks DLL bindings, `find_leaderboard`, `fetch_batch`, cheater list |
| `sheets.py` | Google Sheets OAuth + push (lazy-imported) |
| `seed_search.py` | `_seed_search_worker` (multiprocessing target), `_expected_match_count` |
| `shuffle_lib.py` | C shuffle DLL loader (no logger to keep workers light) |
| `logger.py` | `get_logger` — rotating file handler at `logs/app.log` |
