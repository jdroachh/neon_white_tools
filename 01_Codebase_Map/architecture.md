# Architecture

## Entry Point

[`SteamScraper/neonwhite_app.py`](../SteamScraper/neonwhite_app.py) — 2991-line tkinter GUI app. All core features live here. Run directly with Python or as a compiled EXE.

The app boots from `__main__` (line 2985), constructs a single `NeonWhiteApp` instance (line 937), initializes Steam via ctypes, kicks off background data-fetch threads, and builds a tabbed UI where each major feature is its own section:

```
main (if __name__ == "__main__")                          ← line 2985
  └── NeonWhiteApp(root)                                  ← line 937
        ├── Steam init (ctypes → steam_api64.dll)         ← init_steam, line 650
        ├── Background threads: cheater list, community medals
        ├── UI tabs: Global, Level Search, Player Lookup, Rush Tools
        └── Rush Tools sub-tabs: Seed Finder, Seed Parser, Splits, Medals, Timer
```

### Jump-to anchors for `neonwhite_app.py`

| What | Line |
|------|------|
| `NeonWhiteApp.__init__` | [938](../SteamScraper/neonwhite_app.py) |
| `_build_ui` (top-level UI) | 973 |
| Steam init (`init_steam`) | 650 |
| `find_leaderboard` / `fetch_batch` | 795 / 803 |
| Rush Seed Finder UI / runner | 1084 / 1234 |
| Seed search worker (multiprocessing) | 400 |
| Rush Timer (incomplete) | 1638 / 1713 |
| Global runner | 2637 |
| Level runner | 2716 |
| Player lookup runner | 2792 |
| Google Sheets push | 562–640 |

## Key Modules

| File | Role |
|------|------|
| [`neonwhite_app.py`](../SteamScraper/neonwhite_app.py) | Main GUI application — all user-facing features |
| [`shuffle_lib.py`](../SteamScraper/shuffle_lib.py) | Slim module: `_load_c_shuffle`, `full_shuffle`, reference C source. Imports only `ctypes`/`os`. |
| [`seed_search.py`](../SteamScraper/seed_search.py) | Slim module: `_seed_search_worker`, `_expected_match_count`. Workers spawn against this so they re-import ~170 lines instead of all 2800+ of `neonwhite_app.py` + tkinter. |
| [`logger.py`](../SteamScraper/logger.py) | Centralized logging. Rotating file handler at `SteamScraper/logs/app.log` (5 MB × 3 backups) plus stderr when run from a terminal. Level via `LOG_LEVEL` env var, default `INFO`. Use `from logger import get_logger` then `logger = get_logger(__name__)`. |
| [`rush_data.py`](../SteamScraper/rush_data.py) | Static read-only level data: `LEVELS`, `LEVEL_LOOKUP`, `WHOLE_GAME_LEVELS`, `CHAPTERS`, `RUSH_LEVELS`, `RUSH_ALIASES`, `STANDARD_MEDAL_DATA`. Imported by `neonwhite_app.py` only — workers don't need it. |
| [`steam_api.py`](../SteamScraper/steam_api.py) | Steamworks API integration via ctypes. Owns: `init_steam`, `find_leaderboard`, `fetch_batch`, `get_player_entry`, `wait_for_call`, `fetch_cheater_list`, plus the `Leaderboard*` ctypes Structures and module-level globals (`steam_ready`, `player_name`, `logged_in_steam_id`, `cheater_ids`, etc.). **Access pattern:** `import steam_api` then reference as `steam_api.steam_ready` etc. — `from steam_api import steam_ready` would capture the pre-init value and not see mutations. Future home for handle caching, rate limiting, and result TTL caching (see todo). |
| [`compile_shuffle.py`](../SteamScraper/compile_shuffle.py) | Compiles `shuffle.dll` (C extension) for fast seed searching |
| [`rthook_google.py`](../SteamScraper/rthook_google.py) | PyInstaller runtime hook — fixes Google namespace packages on Python 3.12+ |
| [`neonwhite.spec`](../SteamScraper/neonwhite.spec) | PyInstaller build spec — produces `NeonWhiteLeaderboardTool.exe` |
| [`neonwhite_config.json`](../SteamScraper/neonwhite_config.json) | User config: DLL path, output dirs, Google Sheet IDs |
| [`credentials.json`](../SteamScraper/credentials.json) | Google OAuth2 client credentials (bundled in EXE at build time) |
| [`token.json`](../SteamScraper/token.json) | Cached Google OAuth token |
| [`steam_appid.txt`](../SteamScraper/steam_appid.txt) | Steam App ID: 1533420 |
| [`shuffle.dll`](../SteamScraper/shuffle.dll) | Pre-compiled C shuffle engine (used by Seed Finder) |

### Legacy / standalone scripts (not used by main app)

- [`leaderboard.py`](../SteamScraper/leaderboard.py), [`globalLeaderboard.py`](../SteamScraper/globalLeaderboard.py), [`fullGlobalTop1000.py`](../SteamScraper/fullGlobalTop1000.py) — early standalone scrapers
- [`neonwhite_player_lookup.py`](../SteamScraper/neonwhite_player_lookup.py), [`neonwhite_player_lookup-v2.py`](../SteamScraper/neonwhite_player_lookup-v2.py) — player lookup scripts (v2 supersedes v1)
- [`IL_level_search.py`](../SteamScraper/IL_level_search.py), [`movement_leaderboard.py`](../SteamScraper/movement_leaderboard.py) — individual level tools
- [`discover.py`](../SteamScraper/discover.py) — one-off: lists available SteamAPI exports in the DLL
- [`testingBalloon.py`](../SteamScraper/testingBalloon.py), [`test_sheets_write.py`](../SteamScraper/test_sheets_write.py) — debug/test scripts

## Data Flow

User input flows from the UI into the Steam Steamworks API via a ctypes bridge, comes back as `LeaderboardEntry` structs, gets filtered against a community cheater list and reformatted into human-readable times, then fans out to three possible destinations (in-app table, CSV, or Google Sheets):

```
User Input (level name / player ID / seed)
       │
       ▼
Steam Steamworks API  ←──  steam_api64.dll  (ctypes bridge)
       │                        ▲
       │                        └── SteamClient021 → ISteamUserStats
       ▼
LeaderboardEntry structs  (score in milliseconds, SteamID, global rank)
       │
       ├──► Cheater list filter  (fetched from GitHub/NeonLite at startup)
       ├──► Score formatter  (ms → MM:SS.mmm)
       ├──► Player name lookup  (Steam username via SteamID)
       │
       ▼
Output destinations:
  ├── tkinter Treeview  (in-app table)
  ├── CSV files  (configurable output dir)
  └── Google Sheets  (OAuth2 → Sheets API v4)
```

## External Dependencies

| Service | How used |
|---------|----------|
| Steam Steamworks API | Core leaderboard data — requires local `steam_api64.dll` |
| Google Sheets API v4 | Optional: push player data to a sheet |
| GitHub (NeonLite repo) | Fetches cheater list + community medal times at startup |

## Build

```bash
cd SteamScraper
python compile_shuffle.py   # builds shuffle.dll (only needed once)
pyinstaller neonwhite.spec  # produces NeonWhiteLeaderboardTool.exe
```

## Threading Model

- UI runs on the main thread (tkinter requirement)
- Steam API callbacks polled via `root.after()` timer loop
- Leaderboard fetches run in `threading.Thread` workers
- Seed search spawns a `multiprocessing.Process` (CPU-bound; communicates via `multiprocessing.Queue`)
- Cheater list + medal data fetched in daemon threads at startup

## Notable Quirks

- `credentials.json` is baked into the EXE by PyInstaller — Google OAuth credentials are embedded in the binary
- Many broad `except Exception: pass` blocks silence errors quietly
- The Rush Timer tab is incomplete (placeholder `pass` at line 1695)
- `Neon White App versions/` folder contains deprecated v1/v2 app files still in the repo
