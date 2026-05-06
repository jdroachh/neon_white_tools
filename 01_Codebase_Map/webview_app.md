# webview_app — Bridge Layer

Location: `SteamScraper/webview_app/`

Added in M1 (2026-05-06). M1 wiring complete (2026-05-06): Seed Parser, Splits Updater, Standardize Splits all live and wired to `shuffle_lib` + `rush_data`. Hosts the pywebview window and exposes the Python API surface to the JSX frontend.

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
| `progress.py` | (M2 stub) `evaluate_js` helper for server→client event streaming (Seed Finder progress, Global Export log lines) |
| `steam_runtime.py` | (M3 stub) Daemon thread for `SteamAPI_RunCallbacks` polling — replaces tkinter `root.after(100, ...)` |
| `models/` | Pydantic request/response types for every API endpoint |

## Bridge pattern

JS calls a method synchronously (pywebview serialises through a JS Promise):

```js
const result = await window.pywebview.api.ping();
```

Long-running ops (Seed Finder, Global Export) return immediately and push progress events back via `evaluate_js`:

```python
window.evaluate_js(f"window.__nwEvent({json.dumps(payload)})")
```

The frontend registers `window.__nwEvent` on mount to receive these.

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

## JsApi methods (M1 wired)

| Method | Args | Returns |
|---|---|---|
| `ping()` | — | `{ok, version}` |
| `get_rushes()` | — | `[{name, count}]` |
| `parse_seed(rush_name, seed)` | strings | `{ok, rush_name, seed, level_count, level_order}` |
| `reorder_splits(rush_name, seed, gold, segments)` | strings; splits newline-delimited | `{ok, level_order, gold, segments}` |
| `standardize_splits(rush_name, seed, gold, segments)` | strings; splits newline-delimited | `{ok, gold, segments}` |

All methods return `{ok: false, error: str}` on validation failure.

## All 6 M1 open questions resolved

Q1 ✓ HP list: 11 levels in `data/healthpacks.json`; scorer in `hell_rush.py`  
Q2 ✓ Standard order = `RUSH_LEVELS` in `rush_data.py`  
Q3 ✓ Strip `sampleSeedsOverride` on M2 wire-up  
Q4 ✓ Stay with `neonwhite_config.json` through M3  
Q5 ✓ Hell Rush scoring formula implemented + verified (seed 712788 → 77)  
Q6 ✓ Pure CSS, persist `theme` string in Settings
