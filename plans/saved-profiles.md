# Plan: Saved Profiles for Compare Players

## Context

The Compare Players tab requires the user to manually paste two 17-digit Steam IDs every time. Power users (the tool's primary audience — Neon White speedrunners comparing themselves against rivals/friends) end up typing the same handful of IDs repeatedly. This adds a lightweight "saved profiles" feature: a stored list of 5–10 nickname + Steam ID pairs that load into either compare slot via a dropdown next to each ID input. Profiles persist across sessions in the existing `neonwhite_config.json`.

## Decisions (from clarifying Qs)

- **Profile shape:** `{ nickname: string, steam_id: string }` — no auto-fetched Steam persona.
- **Load UX:** A `[▾ Saved]` dropdown attached to each Steam ID input (P1 and P2). Selecting an entry fills that slot's input.
- **Manage UX:** Both — quick-add via ★ on Compare Players; full rename/reorder/delete in Settings.
- **Quick save:** ★ button next to each ID input. Appears active when the input holds a valid 17-digit ID; click prompts for a nickname and saves.
- **Cap:** Soft cap at 10 profiles (UI-enforced; no hard backend limit).

## Storage

Add a new config key `saved_profiles` to `neonwhite_config.json`.

- **Schema:** `list[ {"nickname": str, "steam_id": str} ]`
- **Default:** `[]`
- **File:** `SteamScraper/webview_app/bridge.py:88` — extend `_DEFAULT_CONFIG`.
- Reuse the existing `save_config_field("saved_profiles", [...])` API at `bridge.py:598`. No new backend endpoint required — the frontend sends the full list when it changes.

## Backend changes

`SteamScraper/webview_app/bridge.py`

1. Line 88 (`_DEFAULT_CONFIG`): add `"saved_profiles": []`.
2. (Optional) Light validation in `save_config_field` for the `saved_profiles` key: ensure list of `{nickname, steam_id}` dicts, steam_id is 17 digits, dedupe by steam_id, cap length at 10. If we'd rather keep the backend dumb, do all validation in React. **Recommendation: validate in React only**, so backend stays a generic key/value setter.

No changes to `run_compare_players` — it still receives raw IDs.

## Frontend changes

### New shared piece: `frontend/src/lib/savedProfiles.js` (small module)

A tiny helper used by both `ComparePlayers.jsx` and `Settings.jsx`:

```
load()                  // reads from getConfig()
save(list)              // calls saveConfigField("saved_profiles", list)
add(list, profile)      // validate + dedupe + cap
update(list, idx, p)
remove(list, idx)
move(list, idx, dir)    // reorder for Settings
```

Validation rules: nickname trimmed, 1–24 chars; steam_id must match `/^\d{17}$/`; dedupe by steam_id; max 10. These already mirror existing patterns — see how `Settings.jsx` calls `saveConfigField` on blur/change.

### `frontend/src/pages/ComparePlayers.jsx`

Modify the existing two `Field` blocks at lines 126–141:

1. Add a `[▾ Saved]` button next to each `[Mine]` button. Disabled when `savedProfiles.length === 0`. Clicking opens a small popover listing nickname + truncated ID; selection fills the input.
2. Add a `★` button to the right of the input (same row as `[Mine]`/`[Saved]`). Visible only when the field's current value matches `^\d{17}$` AND that ID isn't already saved. Click opens a small inline prompt for a nickname (use existing `Field`/inline modal pattern; if none exists cleanly, a `window.prompt` is acceptable for v1) and calls `save(add(list, {nickname, steam_id}))`.
3. Load `savedProfiles` once in the existing config-load effect; keep in component state; on changes from Settings, re-read on tab focus (or accept that Settings edits show after a tab switch — fine for v1).

Reuse `Btn` (`kind="ghost"`, `size="sm"`) from `frontend/src/shared.jsx` for all three new buttons. The existing `[Mine]` button is the visual reference.

### `frontend/src/pages/Settings.jsx`

Add a new `Saved Profiles` section after the existing color/output settings:

- Render the list with rows: `nickname (editable)`, `steam_id (editable)`, `[↑] [↓] [delete]`.
- Below the list: a `+ Add manually` row with two inputs (nickname, steam_id) and a `Save` button.
- Inline error text per row when validation fails (bad ID format, duplicate, nickname empty).
- Cap reached → disable `+ Add` and show "Limit: 10 profiles".

All edits flow through `savedProfiles.js` and persist via `saveConfigField`.

## Critical files

- `SteamScraper/webview_app/bridge.py` (line 88) — add default
- `frontend/src/lib/savedProfiles.js` — **new**
- `frontend/src/pages/ComparePlayers.jsx` (lines 126–141) — picker dropdowns + ★
- `frontend/src/pages/Settings.jsx` — manage section
- `frontend/src/shared.jsx` — reuse `Btn`, `Field` (no changes)

## Verification

1. **Cold start:** Launch app with no `saved_profiles` key in config. Compare Players tab loads cleanly; `[▾ Saved]` is disabled. No console errors.
2. **Quick save:** Paste your own 17-digit ID into Player 1 input. ★ appears; click it; enter nickname "Me"; confirm. Reload app — profile persists.
3. **Slot fill:** Save 2–3 profiles. `[▾ Saved]` next to P1 lists them; selecting fills P1 only (P2 untouched). Repeat for P2.
4. **Settings manage:** Open Settings → Saved Profiles. Rename, reorder, delete. Switch back to Compare Players — dropdown reflects changes.
5. **Validation:** Try saving "12345" (too short), an empty nickname, and a duplicate ID — each rejected with a visible error. Try to add an 11th profile — `+ Add` disabled with cap message.
6. **Compare still works:** Load two saved profiles into P1/P2, run a game-mode compare. Results render identically to manually-typed IDs (no regression in `run_compare_players`).
7. **Config file inspection:** Open `neonwhite_config.json` in an editor; confirm `saved_profiles` is a clean JSON array with the entries in expected order.

---

## Handoff prompt for Sonnet

```
Implement the "Saved Profiles for Compare Players" feature per the plan at
E:\Claude-Neon-White-App\plans\saved-profiles.md.

Summary of what to build:
- New config key `saved_profiles` (list of {nickname, steam_id}) persisted to
  neonwhite_config.json. Add default `[]` in
  SteamScraper/webview_app/bridge.py at line 88 (_DEFAULT_CONFIG). No new
  backend endpoint — reuse save_config_field.
- New helper module: frontend/src/lib/savedProfiles.js with load/save/add/
  update/remove/move and validation (nickname 1–24 chars; steam_id /^\d{17}$/;
  dedupe by steam_id; cap 10).
- frontend/src/pages/ComparePlayers.jsx (lines 126–141): for each of P1 and P2,
  add a [▾ Saved] dropdown next to [Mine] (disabled when list empty), and a ★
  button shown only when the input holds a valid 17-digit ID not already saved
  — click prompts for nickname and saves.
- frontend/src/pages/Settings.jsx: add a "Saved Profiles" section with rows
  (editable nickname + steam_id, ↑/↓/delete) and a "+ Add manually" row.
  Inline validation errors. Disable add when 10 reached.
- Reuse Btn / Field from frontend/src/shared.jsx. No changes to
  run_compare_players.

Verification: see the "Verification" section in the plan file — cold start,
quick save persistence, slot fill (P1 vs P2 isolation), Settings manage round
trip, validation rejections, cap enforcement, and a real compare run using
two loaded profiles.

Working style for this repo (CLAUDE.md):
- Be terse. Confirm before edits to SteamScraper/. Local vault edits don't
  need confirmation.
- Append a short session log to 03_Sessions/2026-05-09.md when done.
- Don't restructure SteamScraper/ beyond what the plan specifies.
```
