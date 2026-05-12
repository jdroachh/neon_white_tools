# Todo

<!-- Concrete tasks for Claude to pick up. Examples:
- Finish the Rush Timer tab (placeholder at neonwhite_app.py:1695)
- Replace the bare `except Exception: pass` blocks with logging
-->

## BETA round 1 feedback — Quick wins ✓ DONE 2026-05-11

- ~~**Route Videos: move route-select buttons above the video player**~~ ✓ — route table now above player, max-height 40%
- ~~**Community Guides: convert filter pills → tabs**~~ ✓ — single-active tab bar, search/level/watch pills below
- ~~**Status indicators: hardcode green/red, exempt from accent color**~~ ✓ — `.dot.ok` now hardcoded `#2ecc71` instead of `var(--accent)`; `.dot.bad` already used static `--bad`
- ~~**Player Lookup: drop "show average placement" toggle**~~ ✓ — always renders avg row when results present; removed `AvgPlacementToggle` component
- ~~**Level Search: fix empty-on-first-boot race**~~ ✓ — retry-on-empty loop in useEffect (20 attempts × 250ms), also catches Promise rejection

## BETA round 2 feedback — Phase C (research first, then implement)

- ~~**First page: Welcome + smart routing**~~ ✓ DONE 2026-05-11 — Welcome page on first launch (`welcome_seen` flag); "GETTING STARTED" header; "Find Steam DLL & Connect" button (registry → VDF → recursive game-dir search); "I'll set it up later" link; "Don't show again" checkbox; post-connect landing panel; `last_tab` smart routing on subsequent launches.
- ~~**Smart `steam_api64.dll` finder**~~ ✓ DONE 2026-05-11 — `dll_finder.py`; wired into Welcome + Settings "Find DLL" button; finds DLL inside `Neon White_Data/Plugins/x86_64/` via unlimited-depth game-dir search.
- ~~**Window snaps back to center, can't drag edges to resize**~~ ✓ DONE 2026-05-12 — Dropped `frameless=True`; native chrome provides edge-drag resize. Title bar themed to `#050505` / `#f0f0e8` via DWM `DWMWA_CAPTION_COLOR` + `DWMWA_TEXT_COLOR`. ADR: `02_Decisions/2026-05-11-window-resize.md`.
- ~~**Tied WRs / multiple WRs handling**~~ — investigated 2026-05-11: WR sheet stores only one runner per platform per level; ties are informally noted in the video title string only. Deferred — consider speedrun.com API as a proper data source post-V1.
- [ ] **Side panel scrolling broken** (Restrain) — backlog; need repro (which page, what they tried to scroll). Working theory: `overflow: hidden` on a `.panel-left` container that should be `overflow: auto` on one or two specific pages. 2-minute CSS fix once the page is identified.

- ~~**Community Guides: watchlist / watched markers**~~ ✓ DONE — cycling ○/✓/✗ icon per row, "Hide watched" + "Watchlist only" filter pills (combinable, now persistent), keyed by YouTube ID, persisted in `neonwhite_config.json`. Race conditions fixed: `_CONFIG_LOCK` + atomic `save_config_fields`, functional setState. Resource-page load race fixed for Guides, Route Videos, Ghosts (polling until `*_loaded` flips).

- ~~**Guides tab — video links blocked by GViz endpoint**~~ ✓ DONE — sheet owner added 3 link tabs (`stages`, `technical`, `rush/route`); parser now reads plain-text CSV from those tabs; 194 guides all have URLs.

- ~~**Player Lookup: Medals toggle + Text size toggle**~~ ✓ DONE — also extended to Level Search and Global Export.
- ~~**Wire up the Ghosts library from Drive**~~ ✓ DONE — 472 ghosts across 121 levels. `tools/build_ghosts_sheet.py` for re-runs when Drive is updated.
- ~~Active Bugs: Two UI sets of Windows window buttons (minimize, maximize, close)~~ ✓ DONE — frameless=True + bridge methods for minimize/maximize/close; titlebar drag region wired
- ~~Seed Parser reads left to right in groups of four, need to mirror Seed Finder results~~ ✓ DONE — vertical flex column, matches SeedFinder card layout
- Make the highlight in the player comparison window for the lower time brighter or more obvious
- ~~Make a color picker (change the highlights like the search button, accents, etc) (Restrain Mode)~~ ✓ DONE — 8-preset accent swatches on Settings page, persisted via neonwhite_config.json
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

6. ~~**Cheater list lookup**~~ ✓ DONE — already a `set`; also fixed: `fetch_cheater_list()` was never called in webview app (filtering silently disabled); now called on Steam init. Count displayed in Level Search + Global Export results header.

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

- **Auto-connect to Steam on launch if `dll_path` is set.** Today the user has to click Settings → Connect every time. Once `neonwhite_config.json` has a valid `dll_path`, the app should call `init_steam(cfg.dll_path)` automatically on mount and only fall back to the manual Connect flow if it fails. Implementation: in `frontend/src/main.jsx` `useEffect` (or a new effect right after `getSteamStatus`), if `cfg.dll_path` is truthy and `!steamStatus.ready`, kick off `initSteam(cfg.dll_path)`; on success update `steamStatus`; on failure leave the Settings page reachable for manual recovery. ~10 lines. Validated 2026-05-10 beta smoke test surfaced the friction.

- **Silence Google OAuth URL print** in `sheets.get_sheets_service`. `flow.run_local_server` prints the auth URL to stdout as a browser-open fallback. Pass `authorization_prompt_message=""` to suppress, or route through `logger.info` so it ends up in `app.log` instead. One-line change.

- **Drop unused `rush_key` parameter from `_compute_medals`** in `SteamScraper/webview_app/bridge.py:199`. After the 2026-05-10 fix to line 203 (extra arg removed from `_get_medal` call), `rush_key` is passed in but never read inside the function — medal lookup goes through `_resolve_level_code(level_name)`. Cleanup touches 4 call sites (`bridge.py:336`, `:338`, `:1189`, `:1191`). Cosmetic only.

- **Migrate `_csv_url` to accept gids in `resources.py`.** Currently the helper uses `&sheet=<name>`, hardcoding tab names (`stages`, `technical`, `rush/route`, `helpful_links`). If the sheet owner ever renames a tab, the fetch breaks silently. Robustness fix: make `_csv_url` accept either a name or a numeric gid (gids are immutable). Need the user to grab the four gids from the sheet (click each tab → copy `gid=NNN` from URL). ~10 lines.

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

