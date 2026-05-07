# Todo

<!-- Concrete tasks for Claude to pick up. Examples:
- Finish the Rush Timer tab (placeholder at neonwhite_app.py:1695)
- Replace the bare `except Exception: pass` blocks with logging
-->

- May have to archive NeonWhite App versions
- Run insights
- Start config for sub-agent work
- What changed:
  - compile_shuffle.py: new find_seeds_batch C function + smoke test in verify_dll()
  - shuffle_lib.py: argtypes registered + Python wrapper
  - seed_search.py: worker rewritten to call C in 250k-seed slabs

  Measured speedup: ~12× end-to-end (89k → 1.1M seeds/sec). Stop latency: 234ms.

  Three deviations from design doc — all required for correctness:
  1. arr[64] → arr[128]: White rush has 96 levels, would have silently overflowed the stack
  2. Single uint64_t target_mask → target_mask_lo + target_mask_hi: 1ULL<<N with N≥64 is UB on x86; caused false positives on seeds where a level index ≥64 appeared in the first depth positions
  3. SLAB_SIZE 1M → 250k: 96-level slab at 1.1M seeds/sec took ~910ms > 500ms stop budget (design doc explicitly noted 250k as the tuning knob)

## Seed Finder error paths reference undefined `self.finder_result`

- **Repro:** in Seed Finder, leave the levels field empty (or matching the placeholder) and click Find Seed. Or enter non-numeric Search Depth. Or enter an unknown level name. Or click "No" on the unlikely-search confirmation dialog.
- **Symptom:** `AttributeError: 'NeonWhiteApp' object has no attribute 'finder_result'`. `_build_rush_finder` never creates `finder_result` — the Treeview-based results layout has no `_rush_result_box` like the other Rush tabs do.
- **Confirmed not** caused by the 2026-05-04 finder extraction — copy-paste of the original `_run_finder`. Pre-existing.
- **Fix sketch:** either (a) replace those `self._rush_show(self.finder_result, ...)` calls with `self.finder_status_var.set(...)` + maybe a `messagebox.showerror(...)`, or (b) add a small status label below the Treeview and use it as `finder_result`. Option (a) is simpler and matches the rest of the finder UX (uses `finder_status_var`).

## Run Timer split-input parser is too brittle

- **Repro:** paste lines like `Stomp Traversal 38.28` and `Fireball Traversal 2:27.26` into the Run Timer input. Errors out on row 1 (no colon → entire line treated as time) and on rows with `mm:ss.xxx` times prefixed by a name (splits at the *first* colon, so `name = "Fireball Traversal 2"`, `time = "27.26"`, and cumulative-time monotonicity check fails).
- **Confirmed not** caused by the 2026-05-04 timer extraction — copy-paste of the original `_run_timer`/`_parse_time_to_secs` logic. Pre-existing.
- **Fix sketch:** parse the *trailing* whitespace-separated token as the time first (covers `Name 1:51.85` and `Name 38.28`); fall back to the existing `Name: time` colon-split for backward compat; keep the bare-time path. ~10 lines in `tab_rush_timer.RushTimerTabMixin._run_timer`.
- **User-facing impact:** the format speedrunners actually paste from livesplit/etc. is `Name<whitespace>time` — current parser forces them to manually insert colons.

## Efficiency / performance (ranked by ROI — impact ÷ effort)

1. **Slim worker module** — split `_seed_search_worker`, `full_shuffle`, `_load_c_shuffle`, and the level constants into a small `seed_worker.py` with no tkinter import. Spawn workers against that module instead of `neonwhite_app.py` to drop per-search startup from "import 2991 lines + tkinter × N cores" to "import ~150 lines + ctypes × N cores". Biggest wall-clock win for the smallest change.

2. ~~**Bitmask subset check in the worker hot loop.**~~ **DONE — but not as predicted.** Bitmask in pure Python is ~2× *slower* than the original because CPython's set ops are heavily C-optimized; the OR-fold runs in the Python interpreter. The actual win came from removing a redundant `set()` call: `target_set.issubset(order[:depth])` instead of `target_set.issubset(set(order[:depth]))`. `issubset` accepts any iterable, so the outer `set()` was a wasted per-seed allocation. Measured **1.83× speedup** on the subset check itself (1.29M → 2.35M checks/sec) for one character of code change. End-to-end seed-search speedup is much smaller because the shuffle dominates, but it's free. The real bitmask win still exists — but only if combined with #4 (move the entire loop into C).

3. **Pipeline leaderboard fetches** in `_run_global` (line 2637) and `_run_player` (line 2792). Steam's `DownloadLeaderboardEntries` is async — currently awaited one level at a time. Cap at N concurrent calls and drain results as they come. "Player Lookup across all 96 levels" is the most user-visible win.

4. ~~**Move the entire seed-search loop into C.**~~ **DONE — ~12× end-to-end speedup.** Added `find_seeds_batch` to `shuffle.dll`; worker now calls it in 250k-seed slabs. Old path: ~89k seeds/sec (ctypes allocation + list round-trip + issubset dominated). New: ~1.1M seeds/sec. Stop latency: ~234ms. Deviation from design doc: used two `uint64_t` masks (`target_mask_lo`/`hi`) instead of one — required because White rush has 96 levels and `1ULL<<64` is UB on x86. Also `arr[64]` → `arr[128]` and `SLAB_SIZE` → 250k (design doc said 1M, but 96-level slab took ~910ms > 500ms stop budget).

5. **Reuse the shuffle output buffer** — `full_shuffle` (line 488) re-allocates `(ctypes.c_int * num_levels)` every call and re-initializes it with `*range(num_levels)`, but the C side already writes `arr[i] = i` itself (`compile_shuffle.py:39`). Allocate once per worker, reuse forever. Disappears entirely if #4 is done.

6. **Cheater list lookup** — confirm whether the cheater list is stored as a `set`/`dict` or a `list`. If it's a `list`, every leaderboard entry incurs an O(N) scan. Grep for the lookup site and convert to a `set` if needed. One-line fix, big win on large leaderboards.

7. **Dead-code-path branch in `full_shuffle`** — the pure-Python fallback (lines 491–523) is now unreachable in practice (DLL load is reliable + verified). The `if _SHUFFLE_LIB is not None` check runs every call. Either fail-loudly when the DLL doesn't load (and drop the fallback), or accept the marginal cost. Cosmetic only.

8. ~~**Replace broad `except Exception: pass` blocks**.~~ **DONE.** Phase 1: 5 high-value sites (load_config, fetch_cheater_list, fetch_community_medals, init_steam DLL fallbacks, Sheets push). Phase 2: 5 more (Google libs import, Steam CDLL load, font load, _init_c_shuffle, Sheets auth). Logs land in `SteamScraper/logs/app.log`. **Intentional skips:** the seed-finder manager's `result_queue.get(timeout=0.2)` (normal polling heartbeat, not an error) and `shuffle_lib._load_c_shuffle` (kept logger-free so workers re-import only ~110 lines on spawn, and to avoid multi-process `RotatingFileHandler` write contention).

## Steam API call efficiency / rate-limit safety

Ranked by ROI. Best done *after* the `steam_api.py` extraction so they live as internal details inside that module.

1. **Cache `find_leaderboard` handles per session.** Same internal name → same handle, always. Cuts ~96 calls per repeat Player Lookup or Global Export. ~10 lines.
2. **Self-imposed rate limit** (e.g. 10 calls/sec) on `find_leaderboard` and `fetch_batch`. Token bucket or simple sleep-since-last. Prevents button-mashing or burst-pattern triggers. ~15 lines.
3. **Exponential backoff on Steam errors.** Once logging is wired (already done), failures are visible — backoff prevents tight retry loops that compound into rate-limit triggers. ~20 lines.
4. **Result cache with short TTL** (e.g. 5 min) keyed on `(handle, start, end)`. Big call reduction for re-runs. Needs a "Force Refresh" button to bypass on demand. ~50 lines + UX.
5. **Reconsider perf item #3 (pipelining).** Concurrent calls reduce wall time but compress the call burst — *worse* for rate-limit safety. Only pursue if paired with #2 above (cap concurrency × rate limit).

## Polish (low priority)

- **Silence Google OAuth URL print** in `sheets.get_sheets_service`. `flow.run_local_server` prints the auth URL to stdout as a browser-open fallback. Pass `authorization_prompt_message=""` to suppress, or route through `logger.info` so it ends up in `app.log` instead. One-line change.

## M3 backlog

- **Seed Finder resume** — after clicking Stop, "Find Seed" currently starts fresh from seed 1. A resume feature would checkpoint the workers' last position and restart from there. Requires passing `seed_start` back to JS on stop and using it as the range start on the next run.

## Bigger-picture ideas (from 00_Inbox/ideas.md)

- **Rewrite the entire app using Opus.** Larger conversation. Worth scoping: clean-room rewrite vs. incremental refactor + AI-assisted polish. The current modularization work makes a clean-room rewrite easier to justify (slim modules already).
- **Google Auth alternatives.** Today's flow bundles `credentials.json` into the EXE (security concern flagged earlier). Options to explore: device-code OAuth (no client secret), service-account JSON file the user provides, or dropping Sheets push entirely in favor of CSV-only.

## After pywebview migration

### GitHub Releases update-notification on launch

**Goal:** when the user opens the app, quietly check GitHub for a newer release and show a non-blocking banner if one exists. No auto-download, no auto-install — just notify + link.

**Defer until after migration** so we only build it on the new (pywebview) UI. The legacy tkinter app will be retired by then.

**Prerequisites before this work starts:**
- App is published to a public GitHub repo with `vMAJOR.MINOR.PATCH` release tags (e.g. `v1.10.5`).
- `VERSION` constant in `SteamScraper/neonwhite_app.py` (currently line 51) — or wherever it lives post-migration — is the source of truth and matches the release tag.
- `OWNER` and `REPO` constants known and hard-coded into the new module.

#### Implementation prompt for Sonnet

> You are implementing a launch-time update notification for the Neon White Leaderboard Tool. The app is open-sourced on GitHub Releases; users download an EXE built with PyInstaller. On launch, the app should check GitHub's Releases API for a newer version and, if found, show a dismissable banner in the pywebview UI with the new version number, release notes preview, and a button to open the release page in a browser.
>
> **Read first:**
> - `01_Codebase_Map/overview.md` for current architecture (pywebview is the live UI by then; tkinter retired).
> - `SteamScraper/webview_app/bridge.py` to understand the `JsApi` bridge pattern and how existing methods return Pydantic models.
> - `SteamScraper/webview_app/models/` for the request/response type convention.
> - `frontend/src/shared.jsx` and `frontend/src/api.js` for how JS calls bridge methods and where global UI chrome lives.
> - The existing GitHub-raw fetcher in the codebase (search for `cheaterlist.json` and `communitymedals.json`) — that's the precedent for "fetch from GitHub at startup, fall back silently if offline." Reuse the same `urllib.request` posture; do **not** add `requests` as a dependency.
>
> **Deliver these changes:**
>
> 1. **New module** `SteamScraper/update_check.py`:
>    - Constants: `OWNER = "<fill in>"`, `REPO = "<fill in>"`, `TIMEOUT_S = 4`.
>    - `UpdateInfo` dataclass / NamedTuple: `current: str, latest: str, url: str, notes: str`.
>    - `check(current: str) -> Optional[UpdateInfo]` — GET `https://api.github.com/repos/{OWNER}/{REPO}/releases/latest` with `Accept: application/vnd.github+json` and a `User-Agent` header (GitHub requires one). Catch `URLError`, `TimeoutError`, `JSONDecodeError`, `OSError` and return `None` — *never raise* into the caller. Compare versions as integer tuples after stripping a leading `v` from `tag_name`.
>    - Use the project logger (`logger.get_logger`) for one debug-level line on each outcome (up-to-date, newer found, network error). Match the style of `fetch_cheater_list` and friends.
>
> 2. **Bridge method** in `SteamScraper/webview_app/bridge.py`:
>    - `def check_for_update(self) -> CheckForUpdateResponse` — calls `update_check.check(VERSION)`, consults `config.get("skipped_version")`, returns `{available: False}` if no update or if `latest == skipped_version`, else `{available: True, current, latest, url, notes}`.
>    - Add a sibling `def skip_update_version(self, version: str) -> None` that writes `skipped_version` into `neonwhite_config.json` via the existing `save_config_field` mechanism.
>    - Add corresponding Pydantic models in `SteamScraper/webview_app/models/`.
>
> 3. **Frontend banner** in `frontend/src/shared.jsx`:
>    - New `<UpdateBanner>` component that calls `api.checkForUpdate()` once on mount.
>    - If `available`, render a slim banner across the top of every page: "Version {latest} is available (you're on {current})."
>    - Three actions: **"Open release"** (`window.open(url)` — or pywebview's `webview.open_url_in_browser` equivalent if it exists in the bridge layer), **"Skip this version"** (calls `api.skipUpdateVersion(latest)` then hides the banner), **"Later"** (just hides the banner for the session, no persistence).
>    - Mount it once at the top of the root layout — must overlay every page route, not be inside any per-page component.
>
> 4. **API wrapper** in `frontend/src/api.js`: thin wrappers `checkForUpdate()` and `skipUpdateVersion(version)`.
>
> 5. **Config schema**: add optional `skipped_version: str | null` to `neonwhite_config.json`. Don't write it on app start; only when the user clicks "Skip this version".
>
> **Do not:**
> - Implement auto-download or auto-install. The "Open release" button is the only path forward; user does the rest manually.
> - Add a beta/pre-release channel. The `/releases/latest` endpoint already excludes pre-releases — keep that behavior.
> - Block app startup on the network call. The check runs after the UI is mounted; failures are silent.
> - Introduce `requests`, `httpx`, or `pygithub` as a dependency — `urllib.request` is sufficient and matches existing code.
> - Force the user to update or show modal dialogs. The banner is dismissable, always.
>
> **Verify before reporting done:**
> 1. *Offline:* disable the network adapter, launch the app — no banner, no error in `logs/app.log`, normal startup.
> 2. *Up-to-date:* point `OWNER/REPO` at a repo whose latest tag equals `VERSION` — no banner.
> 3. *Newer available:* point at a repo with a higher `vX.Y.Z` — banner appears with correct current/latest/URL; "Open release" opens the page; "Skip this version" hides the banner and persists; relaunch confirms it stays hidden until `VERSION` advances past it.
> 4. *5xx / 403 (rate-limited):* mock the request to fail — banner suppressed, app starts normally.
> 5. *Slow host:* point at a black-hole address — app starts within ~4 s, banner never appears.
> 6. Confirm `app.log` has one debug line per launch describing the outcome.
>
> Keep the patch tight; this should be ~150 lines of Python + ~80 lines of JSX. No refactors of unrelated code.

## Before pushing to GitHub
- `git init` and create a sensible `.gitignore` (must exclude: `credentials.json`, `token.json`, `tokenold.json`, `__pycache__/`, `build/`, `.obsidian/workspace.json`, `*.csv` outputs, `shuffle.exp`, `shuffle.lib`)
- Decide what to do with the credential files currently bundled into the EXE (`neonwhite.spec` line 27-28) — they should not land in a public repo
- Document the `neonwhite_config.json` schema (expected keys: `dll_path`, output dirs, sheet IDs) somewhere in `01_Codebase_Map/` or as a README
- Consider an `_archive/` subfolder under `SteamScraper/` to separate live code from legacy scripts and `Neon White App versions/`

