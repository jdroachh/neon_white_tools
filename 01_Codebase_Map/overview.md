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

```
python SteamScraper/neonwhite_app.py
```

Or launch the compiled `NeonWhiteLeaderboardTool.exe` (built with PyInstaller from `SteamScraper/neonwhite.spec`).

Requires `steam_api64.dll` (from the Neon White game install) at the path set in `neonwhite_config.json`.

## Who it's for

Neon White speedrunners and competitive players who want to analyze leaderboard standings, plan randomizer runs, or push data to community spreadsheets.

## Module layout

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
