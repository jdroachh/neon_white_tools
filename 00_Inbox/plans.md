# Plans

Saved Claude-authored plans for the Neon White app. Newest at the top.

---

## 2026-05-06 — Wire the Hi-Fi mockup to a Python backend

### Context

`ClaudeDesignHandoff/` is a finished Hi-Fi React/JSX mockup of a redesigned Neon White Tools desktop app. It runs Babel-in-browser, holds all state in `useState`, and uses placeholder data. The `BACKEND_HANDOFF.md` was authored as if greenfield — but a working Python backend already exists in `SteamScraper/` (3,400 LOC, debugged), including the verified seed→level-order RNG (`shuffle.dll` matching C# `System.Random`, ground-truth-tested 2026-05-05). Goal: ship the new UI without rewriting the backend. Treat this as a **renderer swap**, not a rewrite.

### Decisions locked in

- **Backend language:** Python. Reuse `SteamScraper/` modules unchanged. PyInstaller → **Nuitka swap scheduled in M4** for ~40% smaller binary and far fewer AV false positives.
- **tk transition:** Both apps run side-by-side off shared backend modules during M1-M3. Delete `neonwhite_app.py` + `tab_*.py` in M4 once the new UI hits feature parity.
- **Run Timer scope:** On-demand splits calculator (matches what the JSX mockup shows). The live websocket timer in BACKEND_HANDOFF.md §4.5 is **out of scope** — UI doesn't surface those controls.
- **Frontend build pipeline:** esbuild. Compiles JSX to JS, bundles, ships static assets in `frontend/dist/`. PyInstaller/Nuitka adds the dist directory via `--add-data`.
- **Bridge layer:** pywebview `js_api` + `evaluate_js` for server→client events. **No FastAPI** — adds nothing for a single-process app with one in-process client.

### Architecture summary

Same-process pywebview hosting WebView2 against the existing Python modules. JSX→JS via esbuild → static bundle → loaded by `pywebview.create_window`. JsApi class on the Python side exposes one method per page action; long-running operations (Seed Finder, Global Export) push progress events via `window.evaluate_js`. Steamworks `SteamAPI_RunCallbacks` polling moves from `root.after(100, ...)` to a daemon thread.

### Repo layout

Graft onto existing repo. New: `SteamScraper/webview_app/` (entry point + bridge + Pydantic models), `frontend/` (built from `ClaudeDesignHandoff/`), `data/` (extracted placeholders). Don't restructure `SteamScraper/`.

### Phasing

- **M1 (~1 wk):** pywebview shell + offline pages (Seed Parser, Splits Updater, Standardize Splits). Validates JSX build pipeline, Pydantic round-trip, JsApi shape. tk app keeps running.
- **M2 (~1 wk):** Seed Finder (with progress streaming via `evaluate_js`) + Run Timer (on-demand splits calculator). Validates the streaming contract.
- **M3 (~1.5 wk):** Leaderboard pages (Global Export, Level Search, Player Lookup), Settings, Steamworks polling moved to daemon thread. Validates OAuth alongside webview.
- **M4 (4-5 days):** Packaging. PyInstaller spec first → smoke-test → Nuitka swap → smoke-test → delete tk app + `tab_*.py` + `fonts.py`. Optional Defender allowlist submission.

### Pydantic models

Generated for: seed (find/parse + progress + done), splits (parse/update/standardize), timer (calc-only — diverges from BACKEND_HANDOFF §4.5), leaderboard (global/level/player + log + done), settings. Form-state fields are all strings in the JSX → Pydantic coerces. Full code blocks in plan file.

### Verification gates

Each milestone has a hard gate before the next begins. M1: parse_seed output matches tk app for same input. M2: 50M-seed search streams ≥10 events/sec, results match tk. M3: leaderboard pages run end-to-end against live Steam, OAuth Sheets push works, no 30-min idle leaks. M4: packaged `.exe` runs on clean Windows VM with no Python installed.

### Open M1-blocker questions (need answers before code)

1. `HEALTHPACK_LEVELS` — authoritative source? (current 39-item list in JSX is a guess)
2. Standardize canonical orders per rush — does `rush_data.py` have these or do we need new data?
3. `state.sampleSeedsOverride` Storybook hatch — keep it or strip on first wire-up?
4. Settings location — stay with `SteamScraper/neonwhite_config.json` or migrate to `platformdirs.user_config_dir`?
5. Hell Rush spacing score formula — RNG is solved but the 0-100 scoring formula isn't in the existing code.
6. Theme switching — persist in Settings (yes/no), pure-CSS or backend-aware?

### Reference: alternative backend languages (NOT this plan)

Captured in §8 of the plan file for future-rewrite reference. Cost/benefit table for Rust+Tauri (4-6 wk, smallest binary, loses verified RNG), C#+WebView2 (3-4 wk, best Steam/Sheets SDKs, same RNG re-verify cost), Go+Wails (4-5 wk). Trigger conditions to revisit: real user AV reports persist after Nuitka, bundle size becomes a deployment constraint, cross-platform need emerges, second contributor joins. **Until any of those: stay Python.** AV pain is a packaging-layer problem (Nuitka kills ~80% of false positives) not a language problem.

### Plan file

Full plan with code blocks: `C:\Users\iamro\.claude\plans\you-are-picking-piped-teacup.md`

**Status:** approved 2026-05-06. Awaiting answers to the 6 M1-blocker questions before code begins.

---

## 2026-05-05 — Can the Python backend support a Claude-designed web UI?

### Context

User has a (presumed React/HTML/CSS) UI mockup from claude.ai and wants to know whether the current Python codebase can serve as the backend for it. The current app is a single-process tkinter desktop app — there is no existing frontend/backend split. So the real question is two-part:

1. Is the *application logic* (Steamworks, shuffle DLL, seed search, Sheets, config/log) reusable behind a web-style UI? **Yes.**
2. What architecture lets a web UI talk to it without rewriting everything? **Embed a webview in the same Python process.**

This document is analysis only. No code changes.

### Short answer

**Yes — with one architectural change: introduce a bridge layer.** tkinter cannot render HTML/React, so the UI mockup cannot be dropped onto the current widget tree. But none of the *backend* concerns — Steamworks ctypes, `shuffle.dll`, multiprocessing seed search, Google Sheets, config persistence — care what renders the UI. They are pure Python and bridge cleanly to a web frontend.

The Steamworks layer is the only hard constraint: `SteamAPI_RunCallbacks` must be polled (~100 ms) inside the *same OS process* that called `SteamAPI_Init`. That rules out "static React app + remote Python server on a different host" but is fine for any in-process or local-loopback architecture.

### Recommended architecture: pywebview + same-process Python

Run the React build inside an embedded Chromium/WebView2 control hosted by the existing Python process. Python exposes a JS-callable API (`window.pywebview.api.*`); the UI calls it; long-running operations push progress back via `window.evaluate_js`. Everything backend-side stays Python.

```
┌─────────────────────────────────────────────────┐
│  single Python process (NeonWhiteLeaderboardTool.exe) │
│                                                 │
│  ┌─────────────────────┐    ┌────────────────┐ │
│  │ pywebview window    │◄──►│  Python API    │ │
│  │ (Edge WebView2)     │ JS │  (exposed fns) │ │
│  │  - React build      │    │                │ │
│  │  - Claude's mockup  │    │  - tab handlers│ │
│  └─────────────────────┘    │  - progress emit│ │
│                              └───────┬────────┘ │
│                                      │          │
│   ┌──────────┬───────────┬───────────┼────────┐ │
│   ▼          ▼           ▼           ▼        ▼ │
│ steam_api  shuffle_lib  seed_search sheets  logger
│ (ctypes)  (ctypes DLL) (multiprocessing) (Google) │
└─────────────────────────────────────────────────┘
```

#### Why pywebview specifically

- **Zero rewrite of backend logic.** `steam_api.py`, `shuffle_lib.py`, `seed_search.py`, `sheets.py`, `rush_data.py`, `logger.py` all keep their current public surfaces.
- **Same-process Steamworks.** WebView2 runs as child windows of the Python process; `SteamAPI_RunCallbacks` polling continues unchanged in a Python timer (`webview.windows[0].evaluate_js` replaces tkinter `root.after`).
- **No HTTP server, no port collisions, no firewall prompts.** The JS↔Python bridge is in-process.
- **Lighter than alternatives.** Eel runs a real local HTTP+WebSocket server (extra moving parts). Flask/FastAPI + browser is even heavier and breaks single-EXE packaging. Tauri requires a Rust host (kills the ctypes layer you already have working).
- **Packages with PyInstaller.** WebView2 runtime is already on every modern Windows machine; pywebview detects it. No bundle increase like Electron.

#### What changes vs. stays

| Component | Status under web UI |
|---|---|
| `steam_api.py` | **Unchanged.** Polling moves from `root.after(100, ...)` to `webview.windows[0].run_in_background` or a daemon `threading.Timer`. |
| `shuffle_lib.py` | **Unchanged.** |
| `seed_search.py` + multiprocessing | **Unchanged.** Progress queue drained on a background thread that pushes events via `window.evaluate_js("emit(...)")`. |
| `sheets.py` | **Unchanged.** OAuth `InstalledAppFlow` still pops a system browser — works fine alongside webview. |
| `logger.py` | **Unchanged.** Add a tee that forwards new lines to JS for the on-screen log pane. |
| `rush_data.py` | **Unchanged.** |
| `neonwhite_config.json` / `token.json` / `credentials.json` | **Unchanged.** |
| `fonts.py` | **Replaced.** Custom font ships as a `@font-face` CSS asset instead of a tk font load. |
| `neonwhite_app.py` | **Slimmed.** Becomes process bootstrap + bridge class definition; no widget code. |
| All `tab_*.py` mixins | **Replaced.** Method bodies survive *as Python* but stop building tk widgets — they become bridge methods returning JSON. The tk-specific helpers (`_clear_table`, `_add_row`, `_build_results_area`, `_section_header`, `_build_radio_group`, theme dict) all go. The data-shaping logic and Steam/Sheets/seed calls inside them stay. |
| Theme dict | **Replaced** by CSS variables in the React build. |

Rough estimate: ~40–50% of `neonwhite_app.py` + tab mixins is widget construction and gets deleted; the remaining handler logic ports nearly verbatim into bridge methods.

### Friction points

1. **Steam callback polling cadence.** Today `root.after(100, _poll)` runs on the tk main loop. Under pywebview the simplest replacement is a daemon thread with a 100 ms `time.sleep` loop calling `SteamAPI_RunCallbacks`. Steamworks callbacks fire on whatever thread calls `RunCallbacks`, so any Python state they touch needs the same threading discipline you'd already need today.
2. **Multiprocessing + frozen EXE.** PyInstaller already requires `multiprocessing.freeze_support()` and the workers spawn against `seed_search.py` to avoid re-importing tkinter. Under pywebview the worker module avoids re-importing the *webview* on spawn — same pattern, swap the dodge target. Already half-done in `seed_search.py`.
3. **OAuth `InstalledAppFlow`.** Opens the system browser and runs a localhost callback server. Works fine with pywebview running. No change needed.
4. **Logging to UI.** Add a `logging.Handler` subclass that buffers and ships lines to JS. The `tk.Text` log pane disappears.
5. **Bundle size.** Roughly neutral. You lose tkinter's `_tkinter.pyd` + Tcl/Tk DLLs (~5 MB), gain pywebview (~1 MB) and the React build (~500 KB–2 MB depending on dependencies). Still dominated by the Google SDK chain (see `00_Inbox/ideas.md` analysis).
6. **AV false positives.** Same situation as today (PyInstaller-packed). If this is a pain point, the Nuitka recommendation in `ideas.md` still applies and is independent of UI choice.
7. **React build pipeline.** You add a `frontend/` directory with `npm run build` producing static assets that PyInstaller bundles via `--add-data`. New tooling dependency for development, but the *user* still gets a single EXE.

### What this is *not*

- **Not a rewrite.** The "C# / .NET 8 + WPF" path in `ideas.md` is a different conversation. That's "if rewriting anyway, pick the best language for a Win32 desktop app." pywebview is "keep all Python logic, just swap the rendering layer."
- **Not a server split.** No Flask/FastAPI, no separate process, no localhost port. The web UI is an embedded view, not a website.
- **Not Electron.** No bundled Chromium; uses the WebView2 runtime that Windows already ships.

### Open questions before implementation

1. Is the mockup a full-app redesign (all ten tabs) or a single surface (e.g., just the Seed Finder)? Affects whether this is a phased migration or a single cutover.
2. Should the web UI replace tkinter entirely, or run alongside it during transition? (Both are possible; alongside is more work but lower risk.)
3. Is the React mockup using a component library (shadcn, Material, etc.)? Affects bundled asset size.
4. Any appetite for the Nuitka packager swap from `ideas.md` as part of the same effort? Independent of UI work but easy to bundle.

### Verification (for the eventual implementation)

A minimal proof-of-concept worth doing first is a one-tab pywebview shell that calls `find_leaderboard` from `steam_api.py` and renders the result. That validates (a) Steamworks init survives outside tk, (b) the JS↔Python bridge handles the data shapes, and (c) PyInstaller still packages cleanly. ~1–2 days. If that works, the rest is mechanical.

**Status:** saved for later — user is finishing the Claude Design work first and will revisit with concrete mockups in hand.
