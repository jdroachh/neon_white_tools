# webview_app — Bridge Layer

Location: `SteamScraper/webview_app/`

M1 (2026-05-06): bridge skeleton, Rush tools wired.
M2 (2026-05-06): Seed Finder + Run Timer.
M3 (2026-05-06): Leaderboard pages + Steam runtime + Settings. All 9 pages live.

## Why it lives under SteamScraper/

Relative imports (`from shuffle_lib import ...`, `from steam_api import ...`) work without sys.path gymnastics when the package is a sibling of those modules.

## Entry point

```
python -m SteamScraper.webview_app.main
```

Creates an Edge WebView2 window loading `frontend/dist/index.html` and wires `JsApi` as `window.pywebview.api`.

## Files

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `main.py` | pywebview bootstrap — creates window, passes `JsApi`, calls `webview.start()` |
| `bridge.py` | `JsApi` class — every public method callable from JS as `window.pywebview.api.<method>` |
| `hell_rush.py` | Hell Rush spacing scorer (`score_hell_rush`) |
| `models/` | Pydantic request/response types (seed, splits, timer, leaderboard, settings) |

## Bridge pattern

JS calls a method synchronously (pywebview serialises through a JS Promise):

```js
const result = await window.pywebview.api.ping();
```

Long-running ops return immediately and push progress events back via `evaluate_js`:

```python
webview.windows[0].evaluate_js(f"window._nwFinderEvent && window._nwFinderEvent({json.dumps(payload)})")
```

Each streaming page registers its own handler on mount:

| Handler | Page |
|---|---|
| `window._nwFinderEvent` | Seed Finder |
| `window._nwGlobalEvent` | Global Export |
| `window._nwLevelEvent` | Level Search |
| `window._nwPlayerEvent` | Player Lookup |

Event types per handler: `"progress"`, `"row"`, `"done"`, `"error"` (finder also has `"result"`).

## JsApi methods (M3 — all wired)

### Smoke test
| Method | Args | Returns |
|---|---|---|
| `ping()` | — | `{ok, version}` |

### Config
| Method | Args | Returns |
|---|---|---|
| `get_config()` | — | `{dll_path, output_folder, entry_count, ...}` |
| `save_config_field(key, value)` | strings | `{ok}` |

### Steam runtime
| Method | Args | Returns |
|---|---|---|
| `init_steam(dll_path)` | string | `{ok, message, player_name, steam_id: str}` — starts 100ms RunCallbacks daemon on success |
| `get_steam_status()` | — | `{ready, player_name, steam_id: str}` |
| `pick_dll_file()` | — | `{ok, path}` — native open dialog filtered to .dll |
| `pick_folder()` | — | `{ok, path}` — native folder picker |

**Note:** `steam_id` is returned as a string to avoid JS float precision loss (Steam IDs exceed `Number.MAX_SAFE_INTEGER`).

### Level / chapter metadata
| Method | Args | Returns |
|---|---|---|
| `get_levels()` | — | `[{display, internal}]` — 121 levels |
| `get_chapters()` | — | `[{name, levels: [str]}]` — 15 chapters |

### Rush tools
| Method | Args | Returns |
|---|---|---|
| `get_rushes()` | — | `[{name, count}]` |
| `get_standard_order(rush_name)` | string | `{ok, lines: [str]}` |
| `parse_seed(rush_name, seed)` | strings | `{ok, rush_name, seed, level_count, level_order}` |
| `reorder_splits(rush_name, seed, gold, segments)` | strings; splits newline-delimited | `{ok, level_order, gold, gold_medals, segments, segment_medals}` |
| `standardize_splits(rush_name, seed, gold, segments)` | strings; splits newline-delimited | `{ok, gold, gold_medals, segments, segment_medals}` |
| `start_finder(rush_name, levels_str, depth, mode, max_seeds)` | all strings | `{ok, expected}` — pushes to `_nwFinderEvent` |
| `stop_finder()` | — | `{ok}` |
| `load_timer_seed(rush_name, seed)` | strings | `{ok, lines: [str]}` |
| `calculate_timer(rush_name, seed, splits_text)` | strings | `{ok, rows: [{name, cumulative, segment, segment_fmt, medal}]}` |

### Leaderboard operations
All three return `{ok}` immediately and stream events to their JS handler. Accept `out_mode` ("display" \| "csv" \| "both") and `folder` (output path for CSV).

| Method | Args | Streams to | CSV filename |
|---|---|---|---|
| `run_global_export(count, out_mode, folder)` | strings | `_nwGlobalEvent` | `neon_white_top_{N}_entries.csv` |
| `run_level_search(level_name, count, out_mode, folder)` | strings | `_nwLevelEvent` | `{Level}_top{actual_count}.csv` |
| `run_player_lookup(steam_id, mode, target, out_mode, folder)` | strings; mode: "level"\|"chapter"\|"game" | `_nwPlayerEvent` | `{DisplayName}_{context}.csv` |
| `stop_leaderboard()` | — | emits done with `stopped: true` | — |

`done` events include `csv_path` (empty string if no CSV written).

All methods return `{ok: false, error: str}` on validation failure.

## Known limitation

Closing Steam while the app is connected terminates the process. `SteamAPI_RunCallbacks` is called via ctypes; when Steam unloads the DLL, the call causes a C-level access violation that Python cannot catch. Same behaviour as the legacy tkinter app.
