# Plans

Saved Claude-authored plans for the Neon White app. Newest at the top.

---

## 2026-05-07 — Player Lookup: Medals toggle + Text size toggle ✓ DONE

**Files to change:** `SteamScraper/webview_app/bridge.py`, `frontend/src/shared.jsx`, `frontend/src/pages/PlayerLookup.jsx`, `SteamScraper/tests/test_bridge.py`

### Context

Two enhancements to the **Player Lookup results page** (pywebview/React frontend; legacy tkinter out of scope):

1. **Medals toggle** — when ON, color-coded medal label appears next to each time. `_get_medal` already returns one label that mixes standard (DEV/ACE/GOLD/SILVER/BRONZE) and community (BLOOD DIAMOND/TOPAZ/SAPPHIRE/AMETHYST/EMERALD) tiers — community checked first, so the highest applicable tier wins. Example: 24.000s on Movement → `ACE`; 6.124s on Pummel → `SAPPHIRE`.
2. **Text size toggle** — Normal / Large segmented switch, scoped to the Player Lookup results table only. (Same pattern will land on Level Search and Global Export in a follow-up.)

Existing infrastructure: `_get_medal` at `bridge.py:136-158`; `MedalBadge` + `MedalToggle` at `frontend/src/shared.jsx:212-253` (used by Run Timer).

### Decisions

- **Badge style:** plain colored text (no pill). Add a `plain` prop to existing `MedalBadge` — default keeps the current pill so Run Timer is unchanged.
- **`rush_key` parameter on medal helpers — dropped.** `_resolve_level_code` never reads it; medal tables are keyed by globally-unique level codes. Refactor it out so Player Lookup's new call site doesn't pass a placeholder.
- **Medal computation site:** bridge — emit precomputed `medal` field on each `row` event (mirrors Run Timer's pattern; no frontend medal logic).
- **Text-size implementation:** wrap the results table in `<div style={{ fontSize: largeText ? 14 : 11 }}>` and convert hardcoded inline `fontSize` values inside that subtree to `em` (relative). No CSS-variable refactor.
- **State persistence:** local `useState` on the page. No global store, no Settings entry — toggles reset on navigation.

### Implementation

- **Bridge step 0 (refactor):** drop `rush_key` from `_resolve_level_code` and `_get_medal`. Update the one caller in `calculate_timer` (~`bridge.py:578`).
- **Bridge step 1:** in `run_player_lookup` row emit (~`bridge.py:896`), add `medal = _get_medal(display, entry.score / 1000.0)` to the payload.
- **shared.jsx:** extend `MedalBadge` with a `plain` prop. When true: `fontSize: "0.82em"`, `fontWeight: 700`, `letterSpacing: 0.5`, `MEDAL_COLORS[medal]` color, `whiteSpace: "nowrap"`, no background/border.
- **PlayerLookup.jsx:** `useState(false)` for `showMedals` and `largeText`. Place `<MedalToggle>` and a 2-option `<Seg>` (Normal/Large) in the results-pane header. Add a 5th "Medal" `<th>`+`<td>` rendered only when `showMedals`. Wrap the table in the font-size scaler; convert internal `fontSize: 10/11/12` to `em`.
- **Tests (`test_bridge.py`):** assert `run_player_lookup` rows include `medal: str`; minimal `_get_medal` integration test (Movement @ 24.0s → `"ACE"`).

### Verification

- `cd frontend && npm run build` — clean.
- `pytest SteamScraper/tests/` — all pass + new test.
- Launch and run a Player Lookup: toggle Medals OFF→ON (5th column appears with correct colors), Normal→Large (table scales, no clipping), Run Timer Medal column unchanged (regression).
- See full handoff prompt for Sonnet in `~/.claude/plans/3-valiant-meerkat.md`.

---

## 2026-05-07 — Order Matters? toggle (Seed Finder, Violet/Red/Yellow)

**Files to change:** `SteamScraper/webview_app/bridge.py`, `SteamScraper/webview_app/models/`, `frontend/src/api.js`, `frontend/src/pages/SeedFinder.jsx`, `SteamScraper/tests/test_bridge.py`

### Context

Final website-parity feature. Web Seed Finder offers an "Order Matters?" option for the small (8-level) rushes; the desktop app needs it too. Toggle is visible only for **Violet, Red, Yellow** (White/Mikey already has Force First Level for the related need).

### Decisions

- Two settings: **"No - Any Order"** (default, current behavior) and **"Yes - Exact Order"**. Labels are user-specified verbatim — do not abbreviate.
- **Anchored semantics:** when "Yes", returned seeds must have target levels at positions 1..N where N = len(targets). Positions N+1..depth are unconstrained.
- Implementation is a **manager-loop post-filter**, alongside `forced_idx` / `excluded_set` at `bridge.py:450-453`. No C-kernel changes — Violet/Red/Yellow have only 8 levels, so post-filter cost is trivial.
- `_expected_match_count` not modified; it overcounts by N! when Order=Yes, banner stays conservative.

### Implementation

- **Bridge** (`bridge.py`): `start_finder` gets a trailing `order_matters: bool = False`. Reject when `order_matters=True` and rush is not Violet/Red/Yellow. In manager loop, after the `excluded_set` check (line ~452), add `if order_matters and any(order[i] != target_indices[i] for i in range(len(target_indices))): continue`. Verify `_parse_level_names` preserves user-input order.
- **Pydantic model** (`webview_app/models/`): add `order_matters: bool = False` to `start_finder` request model.
- **API** (`api.js`): trailing `orderMatters` arg threaded through to bridge.
- **UI** (`SeedFinder.jsx`): `useState(false)`. `<Field label="Order Matters?">` with `<Seg options={["No - Any Order", "Yes - Exact Order"]}>`, gated on `!isWhiteMikey`. Place after Result Mode block, before White/Mikey-gated Hell Rush / Force First / Excluded sections. In `handleRushChange`, reset to `false` when switching into White/Mikey only — let it persist between Violet/Red/Yellow.
- **Tests** (`test_bridge.py`): 4 new — White/Mikey rejection, Violet acceptance, end-to-end ordering correctness, default-off baseline.

### Verification

- `npm run build` clean; `pytest SteamScraper/tests/` — 31 + 4 = 35 passing.
- Manual: Violet, "Doghouse, Choker", depth=2, Order=Yes → Doghouse @01, Choker @02. Same with depth=4 → still anchored. Order=No → either ordering. Switch to White/Mikey → toggle disappears. Repeat with Red and Yellow.

### Handoff prompt for Sonnet

> You are implementing the **"Order Matters?"** toggle in the Neon White Leaderboard Tool's Seed Finder. This is the final piece of website-parity work — the web version of this tool offers this option for the small 8-level rushes (Violet, Red, Yellow), and the desktop app needs it too.
>
> **Read first:**
> - `01_Codebase_Map/overview.md` — current architecture; pywebview bridge layer is the live UI.
> - `03_Sessions/2026-05-07.md` — most recent shipped features (Hell Rush, Force First Level, Excluded Levels). Mirror the patterns described there.
> - `SteamScraper/webview_app/bridge.py` — specifically `start_finder` (lines ~331-497) and the manager-loop post-filter trio (`forced_idx`, `excluded_set`, hell-rush score) at lines 450-462. Your new filter slots in alongside these.
> - `frontend/src/pages/SeedFinder.jsx` — note how `excludedOn`/`forceFirst` are gated on rush type and how state resets on rush change in `handleRushChange`.
> - `SteamScraper/webview_app/models/` — find the `start_finder` request model and mirror the field-naming convention used by `hell_rush` / `excluded_levels`.
>
> **Deliver these changes:**
>
> 1. **Bridge.** Extend `start_finder` with a trailing `order_matters: bool = False` parameter. Reject the request with a clear error message when `order_matters=True` and the rush is not Violet, Red, or Yellow. In the manager loop, immediately after the existing `excluded_set` check (line ~452), insert: `if order_matters and any(order[i] != target_indices[i] for i in range(len(target_indices))): continue`. Verify that `_parse_level_names` preserves user-input order — it must, because Force First and Excluded Levels rely on the same function. If it doesn't, fix it there rather than reordering at the call site.
>
> 2. **Pydantic model.** Add `order_matters: bool = False` to the `start_finder` request model in `SteamScraper/webview_app/models/`.
>
> 3. **Frontend API.** In `frontend/src/api.js`, add `orderMatters` as the trailing argument to the `startFinder` wrapper and pass it through to `window.pywebview.api.start_finder`.
>
> 4. **Frontend UI** in `frontend/src/pages/SeedFinder.jsx`:
>    - Add `const [orderMatters, setOrderMatters] = useState(false);`.
>    - Render a `<Field label="Order Matters?">` containing a `<Seg>` with options `["No - Any Order", "Yes - Exact Order"]`, gated on `!isWhiteMikey`. Place it logically — after Result Mode / Max Seeds, before the White-Mikey-gated section (Hell Rush, Force First, Excluded Levels). The labels are user-specified verbatim — do not abbreviate to "Yes"/"No".
>    - Disable the toggle while `running` is true (mirror the other Seg blocks).
>    - In `handleRushChange`, when switching *into* White/Mikey, set `orderMatters` to `false` (consistent with how `hellRush`/`forceFirst`/`excludedOn` are reset). Do NOT reset when switching between Violet/Red/Yellow — let the value persist.
>    - In `handleStart`, append `orderMatters` to the `startFinder(...)` call.
>
> 5. **Tests.** Add 4 tests to `SteamScraper/tests/test_bridge.py` mirroring the Excluded Levels test pattern: rejection on White/Mikey, acceptance on Violet, end-to-end correctness check (every returned seed has targets at the typed positions), default-off baseline.
>
> **Do not:**
> - Modify the C kernel (`shuffle.dll` / `compile_shuffle.py`) or `seed_search.py`. The post-filter at the manager-loop layer is intentional — Violet/Red/Yellow have 8 levels and the surviving-seed rate is high enough that filtering in Python is free.
> - Modify `_expected_match_count`. It will overcount by a factor of N! when order=Yes, but the warning banner stays conservative-or-accurate, which is fine.
> - Show the toggle for White/Mikey under any condition. The user explicitly excluded that rush from this feature.
> - Default the toggle to "Yes". Default is "No - Any Order" for backward compatibility.
> - Abbreviate the option labels — they must read exactly "No - Any Order" and "Yes - Exact Order".
>
> **Verify before reporting done:**
> 1. `npm run build` produces `frontend/dist/` cleanly.
> 2. `pytest SteamScraper/tests/` — all prior 31 tests pass plus your 4 new tests.
> 3. Launch the app (`python -m SteamScraper.webview_app.main` after building the frontend) and exercise the Seed Finder:
>    - Violet, "Doghouse, Choker", depth=2, mode=first, order=Yes → expanded card shows Doghouse at position 01 and Choker at position 02.
>    - Same query with depth=4, order=Yes → Doghouse @01, Choker @02 still anchored.
>    - Same query with order=No → either ordering may appear.
>    - Switch rush to White/Mikey mid-session → toggle disappears, no error.
>    - Repeat with Red and Yellow.
> 4. Append a session log entry to `03_Sessions/2026-05-07.md` (or create the next-day file if the date has rolled) describing what shipped.
>
> Keep the patch tight: ~30 lines of Python in `bridge.py`, ~15 lines in the model, ~25 lines of JSX, ~50 lines of tests. No unrelated refactors.

---

## 2026-05-07 — Excluded Levels (Seed Finder) ✓ DONE

**Files changed:** `SteamScraper/webview_app/bridge.py`, `frontend/src/api.js`, `frontend/src/pages/SeedFinder.jsx`, `tests/test_bridge.py`

### Context

Mirror of "Desired Starting Levels": a toggle that lets the user specify levels which must **not** appear within the first N positions of a shuffled seed. Useful for routing — e.g. force runs that defer a healthpack-poor or hard-to-reach level past the early game.

### Decisions

- Scope: **White / Mikey only** (same gating as Hell Rush + Force First).
- Stacks with Desired Starting Levels, Hell Rush, and Force First with no mutual exclusion.
- Window cap is dynamic: `1 .. count - 1` per rush (95 for White/Mikey).
- Empty textbox while toggle on → submit error (matches existing posture).

### Implementation

- **Bridge** (`bridge.py`): `start_finder` got two new params (`excluded_levels: str`, `excluded_window: str`). Validation reuses the existing `_parse_level_names` helper. Post-shuffle filter sits in the manager loop right next to the `forced_idx` check — zero C-kernel and zero `seed_search.py` changes.
- **API** (`api.js`): two trailing string args added to `startFinder`.
- **UI** (`SeedFinder.jsx`): toggle + window + textbox using the Hell Rush / Force First `<Seg>`+`<Field>` pattern. Reset on rush change. Result-card cells render with an amber tint (`rgba(255,180,60,*)`) when `is_excluded` is true; priority chain is target > forced > excluded.
- **Tests** (`test_bridge.py`): four new — bad name, out-of-range window, valid request, non-White rejection. **31 passed.**

### Polish round

- Excluded-level placeholder set to `e.g. Godspeed, Pummel`.
- Desired-starting-levels placeholder is now rush-aware via a `DESIRED_PLACEHOLDERS` map keyed on rush name (Violet → `Doghouse, Razor`, Red → `Stomp Traversal, Fireball Traversal`, Yellow → `Balloon Mountain, Arena`, White/Mikey → `The Third Temple, Absolution`).

---

## 2026-05-07 — Force First Level (Seed Finder) ✓ DONE

**Actual files changed:** `SteamScraper/webview_app/bridge.py`, `frontend/src/api.js`, `frontend/src/pages/SeedFinder.jsx`
*(Plan was written for tkinter; implementation correctly targeted the webview app.)*

### Context

The Seed Finder currently searches for seeds whose first `depth` shuffled levels contain a user-specified set of "desired starting levels" (set membership, position-agnostic). Speedrunners frequently want a stronger constraint: the *first* level of the seed must be a specific level. This plan adds a "Force First Level" toggle (White / Mikey only) with a level-name textbox that filters search results to only seeds where `shuffled[0] == forced_level_index`, while still honoring the existing desired-starts query.

Decisions from clarification:
- Forced level may be **any level in the White/Mikey pool**, independent of the desired-starts list.
- If toggle is on but textbox is empty / unparseable → **block search with an error** in `finder_status_var`.
- Implementation = **Python post-filter** on each candidate seed returned by `find_seeds_batch` (no DLL changes).

### Files to modify

1. `SteamScraper/tab_rush_finder.py` — UI + parse + post-filter
2. *(no changes)* `seed_search.py`, `shuffle_lib.py`, `compile_shuffle.py`, `rush_data.py`

### Changes

**1. UI (tab_rush_finder.py, ~lines 59–73, in `_build_rush_finder`)**

Insert after the "Desired Starting Levels" entry, before the "Result Mode" label:

- `self.finder_force_first_var = tk.BooleanVar(value=False)`
- `ttk.Checkbutton(... text="Force First Level", variable=self.finder_force_first_var, command=self._on_force_first_toggle)`
- `self.finder_force_first_entry = ttk.Entry(...)` initially `state="disabled"`
- Visibility rule: enabled only when rush is **White / Mikey** AND toggle is on. The rush combobox already has a change handler — extend it to also disable the toggle/entry when rush != "White / Mikey" and uncheck the toggle.

`_on_force_first_toggle` flips entry state between `"normal"` and `"disabled"`.

**2. Parse + validate (in `_run_finder`, ~lines 208–223)**

Before kicking off workers:

```python
forced_idx = None
if self.finder_force_first_var.get():
    if rush_key != "96":
        return self.finder_status_var.set("Force First Level only supported for White / Mikey.")
    raw = self.finder_force_first_entry.get().strip()
    if not raw:
        return self.finder_status_var.set("Force First Level is enabled but empty.")
    parsed = self._parse_level_names(raw, rush_key)
    if not parsed or len(parsed) != 1:
        return self.finder_status_var.set(f"Force First Level: '{raw}' is not a valid level.")
    forced_idx = parsed[0]
```

Reuse existing `_parse_level_names` (lines 306–341) — already handles aliases, partial match, numeric index.

**3. Post-filter on candidate seeds (~lines 252–275)**

The display loop already calls `order = full_shuffle(num_levels, seed)` per match. Add inline:

```python
order = full_shuffle(num_levels, seed)
if forced_idx is not None and order[0] != forced_idx:
    continue
```

Pure post-filter — no worker / queue / IPC changes.

**4. Stop-condition / "Search Depth" interaction**

No change. Forced-first and desired-starts are orthogonal; both must hold.

### Verification

1. White / Mikey selected → toggle enables/disables textbox. Switching to Violet auto-clears.
2. Toggle on + empty textbox → status `"Force First Level is enabled but empty."`; no worker spawn.
3. Toggle on + `"asdfgh"` → status `"Force First Level: 'asdfgh' is not a valid level."`
4. Toggle on + valid level X + desired-starts Y + depth 5 → all results show X at position 1 AND Y in positions 1–5.
5. Toggle off, same query → results no longer require X at position 1.
6. Non-White rush modes unchanged.

### Handoff prompt for Sonnet

> You are implementing **"Force First Level"** for the Seed Finder in the Neon White Leaderboard Tool. Repo root: `E:\Claude-Neon-White-App`. Live entry point: `SteamScraper/neonwhite_app.py`. **All edits are confined to `SteamScraper/tab_rush_finder.py`** — no DLL, worker, or other module changes.
>
> **Read first:**
> - `SteamScraper/tab_rush_finder.py` end-to-end — especially `_build_rush_finder` (the UI builder, ~lines 40–120), `_run_finder` / search-button handler (~lines 200–280), the per-match display loop that already calls `full_shuffle(num_levels, seed)` (~lines 252–275), and `_parse_level_names` (lines 306–341).
> - `SteamScraper/rush_data.py` for `RUSH_LEVELS` (level pools per character) and `RUSH_ALIASES`.
> - `SteamScraper/neonwhite_app.py` for `_rush_key_from_display` / `_rush_key_to_num` (rush-key mapping; White/Mikey key = `"96"`).
>
> **Feature spec:**
> 1. Add a **"Force First Level" checkbox** + adjacent **textbox** to the Seed Finder UI, inserted between the "Desired Starting Levels" entry and the "Result Mode" label.
> 2. The toggle and textbox are only meaningful for **White / Mikey** (`rush_key == "96"`). When the user switches to Violet/Red/Yellow, force the toggle off and disable both widgets. Hook into the existing rush-combobox change handler.
> 3. The textbox is `state="disabled"` whenever the toggle is off; `"normal"` when on.
> 4. **On search start (toggle on):**
>    - If textbox is empty/whitespace → set `finder_status_var` to `"Force First Level is enabled but empty."` and return without spawning workers.
>    - Else parse via the existing `_parse_level_names(raw, rush_key)`. If it returns a list of length != 1, set status to `"Force First Level: '{raw}' is not a valid level."` and return.
>    - Else capture the resulting `forced_idx: int`.
>    - The forced level may be **any level in the White/Mikey pool**, independent of the Desired Starts query.
> 5. **Post-filter:** in the existing per-match display loop where `order = full_shuffle(num_levels, seed)` is already computed, add `if forced_idx is not None and order[0] != forced_idx: continue` immediately after the shuffle call. Do not modify `seed_search.py`, `shuffle_lib.py`, or `compile_shuffle.py`.
>
> **Do not:**
> - Modify the C `find_seeds_batch` or recompile `shuffle.dll`.
> - Change the worker / multiprocessing protocol.
> - Add the forced level into the desired-starts target mask — the constraints are orthogonal.
> - Restructure unrelated parts of `tab_rush_finder.py`.
>
> **Verify before reporting done:**
> 1. Launch app → Seed Finder → White / Mikey. Toggling enables/disables the textbox.
> 2. Switching rush to Violet auto-clears the toggle and disables both widgets.
> 3. Toggle on + empty textbox + Find Seed → exact status message above; no worker spawn.
> 4. Toggle on + invalid name (`"asdfgh"`) → exact status message above.
> 5. Toggle on + valid level X + Desired Starts including a different level Y + depth 5 → all displayed results show level X at position 1 AND level Y somewhere in positions 1–5.
> 6. Toggle off, same query → results no longer require X at position 1.
> 7. Non-White rush modes behave exactly as before (toggle disabled).
>
> Patch should be ~40–60 lines in one file. Keep it tight; no surrounding cleanup.

---

## 2026-05-07 — Hell Rush Mode on Seed Finder

### Context

Hell Rush is a White/Mikey 96-level run where 11 specific stages drop healthpacks. A "good" Hell Rush seed has those HPs evenly spaced, not clustered, not all-front-loaded, and not all-back-loaded. The scoring formula and `score_hell_rush()` already exist in `SteamScraper/webview_app/hell_rush.py` (decision: `02_Decisions/2026-05-06-hell-rush-scoring.md`). What's missing is exposing it on the Seed Finder page so users can require a minimum spacing score in addition to their starting-level query.

This plan adds a Hell Rush toggle + threshold input to Seed Finder. When enabled, candidate seeds that already match the level-target query are additionally scored, dropped if below threshold, and the surviving seeds are re-sorted best-first when the search completes. White/Mikey only.

### Decisions (confirmed with user)

- **Rush scope:** White/Mikey only. Toggle is hidden/disabled for other rushes.
- **Threshold UI:** number field, default `70`. Range 0–100.
- **Result display:** score badge on each `SeedCard`; stream as found, sort best-first when search ends.
- **Empty levels:** still required. Hell Rush is an *additional* filter on top of level matching.

### Backend changes

**File: `SteamScraper/webview_app/bridge.py`**

1. Import: add `from hell_rush import score_hell_rush` near the existing `from shuffle_lib import …` line (~19).
2. `start_finder` signature (line 330): add two params `hell_rush: bool = False, hell_rush_min: str = "70"`.
3. Validation block right after `_resolve_rush`:
   - If `hell_rush` truthy and `key != "white"` (verify in `_resolve_rush`): return `{"ok": False, "error": "Hell Rush Mode requires the White / Mikey rush."}`.
   - Parse `hell_rush_min` as int, clamp 0–100; on `ValueError`, return `{"ok": False, "error": "Hell Rush threshold must be 0–100."}`.
4. Manager loop (line 405–417 — the block that handles a `seed` result):
   - After computing `order` and `level_order`, if `hell_rush` is on, build `name_order = [names[idx] for idx in order]`, call `score = score_hell_rush(name_order)`, and `continue` (do NOT count toward `found`, do NOT emit) if `score < hell_rush_min`.
   - When emitting, include `"score": score` (or `None` when HR off) in the `result` event payload.
   - **Always** (regardless of HR toggle) tag each cell in `level_order`: add `is_healthpack: names[idx] in HEALTHPACK_LEVELS` for White/Mikey rushes; `False` otherwise. Import `HEALTHPACK_LEVELS` alongside `score_hell_rush`.
   - Update the existing `summary` to append `· score N` when score present.
5. `done` event: when HR on, no change to backend ordering — frontend resorts.

**File: `SteamScraper/seed_search.py`** — no changes. The C-level `find_seeds_batch` still pre-filters by level-position bitmask; HR filter sits on the small set of bitmask survivors.

### Frontend changes

**File: `frontend/src/api.js`** (line 50)
- `startFinder` signature: add `hellRush, hellRushMin` params, pass through to `pywebview.api.start_finder(...)`.

**File: `frontend/src/pages/SeedFinder.jsx`**

1. New state: `hellRush` (bool, default false), `hellRushMin` (string, default `"70"`).
2. New form fields, rendered only when `rushName === "White / Mikey"`:
   - A `Seg` toggle "Hell Rush Mode" (`["off","on"]`).
   - When on: a `Field label="Min spacing score (0–100)"` with a numeric `input` (width 80, like Search Depth at lines 184–191).
3. `handleRushChange`: if user switches away from White/Mikey while HR is on, set `hellRush=false`.
4. `handleStart`: pass `hellRush, hellRushMin` to `startFinder`.
5. Event handler (lines 91–115):
   - `result` event: keep streaming as today. Score is on `data.score`.
   - `done` event: if `hellRush`, `setResults(prev => [...prev].sort((a,b) => (b.score ?? 0) - (a.score ?? 0)))`.
6. `SeedCard` (lines 21–75): when `result.score != null`, render a small score pill next to the seed number — reuse the accent-colored span style at line 35; format as `score 77`.
7. **HP indicator in expanded grid (White/Mikey only, always on):** in each level cell render a small `♥` glyph next to the name when `lvl.is_healthpack` is true. Muted color so it doesn't fight the accent-green target styling; survives the "target AND HP" overlap case.

### Tests

**File: `tests/test_bridge.py`** — extend existing finder tests:
- HR on with non-White rush → returns validation error, finder does not start.
- HR on, threshold above achievable → search completes with 0 results.
- HR off behaves identically to before (regression).
- `result` payload includes `score` when HR on, `None`/absent when off.

### Verification (manual)

1. HR toggle hidden for non-White/Mikey rushes.
2. White/Mikey → toggle appears, default 70.
3. Run levels = `Absolution, The Third Temple`, threshold 70 → results stream in, sorted desc on completion, score badges visible.
4. Threshold 95 → very few/zero results, no crash.
5. Switch to a stage rush with HR on → toggle hides, state resets.
6. Seed 712788 → score 77 in card.

### Files touched

- `SteamScraper/webview_app/bridge.py`
- `frontend/src/api.js`
- `frontend/src/pages/SeedFinder.jsx`
- `tests/test_bridge.py`
- `01_Codebase_Map/overview.md`
- `03_Sessions/2026-05-07.md`

### Out of scope

- Pushing HR scoring into the C `find_seeds_batch` path.
- HR-only searches (no level targets).

---

## 2026-05-06 — M4: Resources section (Ghosts + Route Videos), credential-free

### Context

The webview migration through M3 has every legacy feature ported except the Sheets *push* (Player Lookup → user's Google Sheet). Push is **deferred to v1.0+**; M4 adds a new **Resources** section instead, with two pages — **Ghosts** and **Route Videos** — fed by Google Sheets the user owns and publishes-to-web. This avoids:

- `credentials.json` shipped in the EXE (concern #1 from `ideas.md`)
- GCP-project quota tied to a single OAuth client (concern #4)
- OAuth consent screen for end users
- Google API key entirely — published Sheets URLs serve cached CSV anonymously

**Ghosts:** browse `.phant` ghost replay files in a public Drive folder, indexed stage × medal-tier (Emerald/Amethyst/Sapphire) × player. User picks stage → medal → row → "Open in browser" → Drive preview/download page. Drive root: `https://drive.google.com/drive/folders/1JiN4Y-Qj-W84va0joZh6NzeYsOq3EVc1`.

**Route Videos:** stage × medal → list of YouTube links (one or more videos per medal). Click → opens YouTube URL.

### Architecture

The published Sheet — not the Drive API — is the index. App never crawls Drive. User manually fills two sheets that link to those Drive resources. Feature collapses to "fetch CSV at startup, render 3-level picker."

Both sheets are published via `File → Share → Publish to web` and read via the GViz CSV endpoint:
```
https://docs.google.com/spreadsheets/d/<SHEET_ID>/gviz/tq?tqx=out:csv&sheet=<TAB>
```
Anonymous, edge-cached, no API key.

### Schemas

**Ghosts:** `level_code, level_name, medal, player, time, drive_url`
**Route Videos:** `level_code, medal, title, youtube_url`

Sheet IDs + tab names hard-coded in the new bridge module.

### Files

**Backend:**
- New `SteamScraper/webview_app/resources.py` (~80 lines) — constants, cache dicts, `_fetch_csv`, `_fetch_resources_bg` daemon thread, `get_ghosts_for/get_videos_for/get_resources_status`. Mirrors error posture of `bridge.py:_fetch_medal_data_bg`.
- New `SteamScraper/webview_app/models/resources.py` — `GhostRow`, `VideoRow`, `ResourcesStatus`. Re-export from `models/__init__.py`.
- Modify `SteamScraper/webview_app/bridge.py` — methods `get_resources_status`, `get_ghosts`, `get_videos`, `open_external_url` (allow-listed to drive.google.com / youtube.com / youtu.be via `webbrowser.open`).

**Frontend:**
- New `frontend/src/pages/Ghosts.jsx` — stage picker (reuse `getLevels()` from `LevelSearch.jsx:8-23`) → medal `Seg` → result table (Player, Time, Open in browser).
- New `frontend/src/pages/RouteVideos.jsx` — stage → medal → table (Title, Watch).
- Modify `frontend/src/api.js` — `getResourcesStatus`, `getGhosts`, `getVideos`, `openExternalUrl`.
- Modify `frontend/src/shared.jsx` — new "Resources" sidebar section between Leaderboard and Rush Tools; `NAV_ITEMS.resources = [{key:"ghosts"...},{key:"videos"...}]`.
- Modify `frontend/src/main.jsx` — register two new routes.

**Docs:**
- Update `01_Codebase_Map/overview.md` (9 pages → 11; add Resources methods).
- Append `03_Sessions/2026-05-06-M4.md`.

**Cleanup:** remove `credentials.json` / `token.json` from `neonwhite.spec` bundling (push deferred to v1.0). `sheets.py` stays on disk, not imported by webview.

### Verification

1. Network down → logged failures, no crash, "Could not reach resource sheet" shown.
2. Sheets populated → drill-down opens Drive / YouTube link in default browser.
3. Empty stage+medal → "No ghosts indexed" message.
4. Malformed row → dropped, others load, one logged warning.
5. `open_external_url("file:///etc/passwd")` → rejected + logged.
6. Background fetch must not block UI mount.
7. `npm run build` clean; 5/5 Python tests pass.

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
