# M1 Groundwork — Sonnet kickoff prompt

Self-contained prompt to paste into a fresh Sonnet session to start M1 scaffolding for the Hi-Fi UI wire-up. Plan: `C:\Users\iamro\.claude\plans\you-are-picking-piped-teacup.md` (also condensed in `00_Inbox/plans.md` under 2026-05-06).

---

You are continuing work on the Neon White Tools project at `E:\Claude-Neon-White-App`. A plan was approved by the user in a prior session — your job is to lay the groundwork for **Milestone 1**.

## First, run the project's startup ritual

`CLAUDE.md` at the repo root specifies a ritual: read everything in `00_Inbox/`, skim `01_Codebase_Map/overview.md`, check the most recent `03_Sessions/` log. Do that before anything else.

The approved plan lives at `C:\Users\iamro\.claude\plans\you-are-picking-piped-teacup.md` — read it in full. The condensed version is also in `00_Inbox/plans.md` under the 2026-05-06 entry.

## What's locked in (do not re-litigate)

- **Backend:** Python. Reuse existing `SteamScraper/` modules unchanged. PyInstaller → Nuitka in M4.
- **Renderer:** pywebview hosting an esbuild-bundled JSX frontend. No FastAPI, no HTTP layer — just `js_api` + `evaluate_js`.
- **Existing tkinter app stays running** through M3. Do not touch `neonwhite_app.py` or `tab_*.py` files.
- **Run Timer is a splits calculator,** not a live timer. Ignore BACKEND_HANDOFF.md §4.5 (the websocket TimerTick spec).
- **Frontend source of truth:** `ClaudeDesignHandoff/`. Don't edit those files — copy/transform into `frontend/src/`.

## Your M1 groundwork scope

Don't try to ship all of M1 in one go. Lay the scaffolding only — get a pywebview window opening with a smoke-test JsApi method, plus the Pydantic models. Specifically:

1. **Create the `SteamScraper/webview_app/` package** per the plan's repo layout (§2):
   - `__init__.py`
   - `main.py` — pywebview bootstrap, creates the window, points it at `frontend/dist/index.html`
   - `bridge.py` — `JsApi` class with a single `ping()` method returning `{"ok": True, "version": ...}` for now
   - `models/` — all Pydantic models from §4 of the plan, exactly as specified
   - `progress.py` and `steam_runtime.py` — empty stubs with docstrings, NOT implemented yet
2. **Create the `frontend/` package:**
   - `package.json` with esbuild as the only dependency
   - `vite.config.js` is mentioned in the plan but the locked decision is **esbuild** — use an `esbuild.config.mjs` instead
   - `src/index.html` lifted from `ClaudeDesignHandoff/Neon White Tools - Hi-Fi.html` but with the Babel-in-browser script tag removed and replaced with `<script src="bundle.js"></script>`
   - `src/main.jsx` — entry point that imports the page components
   - For M1 groundwork, get ONE trivial page rendering (just a div that calls `window.pywebview.api.ping()` on mount and shows the result). Do not yet port the real Hi-Fi pages.
3. **Add a `tests/test_bridge.py`** that instantiates `JsApi` directly and asserts `ping()` works. No webview needed — proves the bridge is testable in isolation.
4. **Update `01_Codebase_Map/`** with a new `webview_app.md` explaining the bridge layer (per the project's "keep the codebase map curated" rule in CLAUDE.md).

## Critical files to read before writing code

- `SteamScraper/seed_search.py`, `SteamScraper/shuffle_lib.py` — confirms the RNG/worker contracts
- `SteamScraper/steam_api.py` — note the callback polling pattern for M3 reference (don't touch yet)
- `ClaudeDesignHandoff/hifi-shared.jsx` — note where `seededOrder()` is called (will be replaced by API later)
- `ClaudeDesignHandoff/Neon White Tools - Hi-Fi.html` — the entry point to lift

## Open questions — DO NOT block on these

There are 6 unanswered questions in plan §6 (healthpack data, canonical orders, hell-rush scoring formula, etc.). All are M1-page-wiring blockers, NOT groundwork blockers. The Pydantic models are already pinned, so models/scaffolding can land without those answers. If you hit one mid-task, leave a `TODO(M1-Q<n>):` comment referencing the plan and keep going.

## Working style (per the user's saved feedback)

- **Be terse.** Lead with the change, no recap.
- **Confirm before destructive ops** — anything touching `SteamScraper/` source, anything that runs network/Steam, anything that installs packages globally. Local file creation in new directories is fine.
- **For git commands:** confirm exact command(s) first, never push without per-push approval.
- **Append a session log** to `03_Sessions/2026-05-06.md` when significant work lands.
- **Don't restructure** anything outside the new directories.

## Done criteria for this groundwork pass

- `python -m SteamScraper.webview_app.main` (or the equivalent invocation, depending on how you set up imports) opens a pywebview window. The window shows the result of `ping()` rendered by the trivial test page.
- `pytest tests/test_bridge.py` passes.
- `cd frontend && npm run build` produces `dist/bundle.js` and `dist/index.html`.
- Pydantic models import without error and round-trip a sample dict for each endpoint.
- New session log entry in `03_Sessions/`.

Once all four are green, stop and report back. The next pass (real Seed Parser wiring) starts with the user's answers to the 6 open questions.
