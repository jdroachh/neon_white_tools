# webview_app — Bridge Layer

Location: `SteamScraper/webview_app/`

Added in M1 (2026-05-06). M2 wiring complete (2026-05-06): Seed Finder + Run Timer added. Hosts the pywebview window and exposes the Python API surface to the JSX frontend.

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
| `bridge.py` | `JsApi` class — every public method is callable from JS as `window.pywebview.api.<method>` |
| `progress.py` | (M3 stub) `evaluate_js` helper for server→client event streaming (Global Export log lines) — Seed Finder uses `_emit()` in `bridge.py` directly |
| `steam_runtime.py` | (M3 stub) Daemon thread for `SteamAPI_RunCallbacks` polling — replaces tkinter `root.after(100, ...)` |
| `models/` | Pydantic request/response types for every API endpoint |

## Bridge pattern

JS calls a method synchronously (pywebview serialises through a JS Promise):

```js
const result = await window.pywebview.api.ping();
```

Long-running ops (Seed Finder, Global Export) return immediately and push progress events back via `evaluate_js`:

```python
webview.windows[0].evaluate_js(f"window._nwFinderEvent && window._nwFinderEvent({json.dumps(payload)})")
```

The frontend registers `window._nwFinderEvent` on mount to receive these. Event types: `"progress"`, `"result"`, `"done"`, `"error"`.

## Models

One file per domain:

| File | Covers |
|---|---|
| `models/seed.py` | Seed Finder + Seed Parser requests/responses/progress |
| `models/splits.py` | Splits Updater + Standardize Splits |
| `models/timer.py` | Run Timer (on-demand splits calculator — NOT a live timer) |
| `models/leaderboard.py` | Global Export, Level Search, Player Lookup |
| `models/settings.py` | App settings (wraps `neonwhite_config.json`) |

## Testing

`tests/test_bridge.py` instantiates `JsApi` directly and exercises all model round-trips. No webview or GUI required — safe to run in CI.

## JsApi methods (M2 wired)

| Method | Args | Returns |
|---|---|---|
| `ping()` | — | `{ok, version}` |
| `get_rushes()` | — | `[{name, count}]` |
| `parse_seed(rush_name, seed)` | strings | `{ok, rush_name, seed, level_count, level_order}` |
| `reorder_splits(rush_name, seed, gold, segments)` | strings; splits newline-delimited | `{ok, level_order, gold, segments}` |
| `standardize_splits(rush_name, seed, gold, segments)` | strings; splits newline-delimited | `{ok, gold, segments}` |
| `start_finder(rush_name, levels_str, depth, mode, max_seeds)` | all strings | `{ok, expected}` — starts background search; pushes events to `window._nwFinderEvent` |
| `stop_finder()` | — | `{ok}` |
| `load_timer_seed(rush_name, seed)` | strings | `{ok, lines: [str]}` |
| `calculate_timer(rush_name, seed, splits_text)` | strings | `{ok, rows: [{name, cumulative, segment, segment_fmt, medal}]}` |

All methods return `{ok: false, error: str}` on validation failure.
