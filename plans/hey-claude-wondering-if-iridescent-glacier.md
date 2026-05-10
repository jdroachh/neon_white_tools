# Community Guides — Watchlist & Watched Markers

## Context

The Community Guides tab (`frontend/src/pages/Guides.jsx`) currently lists route/technical/playlist videos with category, level, and text-search filters. Users have no way to track which videos they've already watched or bookmark ones to revisit. This adds per-video state (watchlist / watched) and two filter toggles to make the page useful as a personal learning queue.

## Design decisions (confirmed with user)

- **One cycling icon per row.** None → ✓ (watchlist) → ✗ (watched) → None. Tooltip explains the next state on hover.
- **Two independent filter toggles** in the existing filter bar: "Hide watched" and "Show watchlist only". Combinable.
- **Storage key = YouTube video ID** (regex already exists at `Guides.jsx:10–13`).
- **Persistence in `neonwhite_config.json`** via existing `save_config_field` bridge method (parity with `accent_color` and `saved_profiles`).

## Files to modify

### Backend

**`webview_app/bridge.py`** (around lines 84–110, 596–603)
- Extend default config dict with `guide_watchlist: []` and `guide_watched: []` (lists of YouTube IDs).
- No new bridge methods needed — `get_config()` and `save_config_field(key, value)` already cover read/write.

### Frontend

**`frontend/src/api.js`** (near `getGuides` at line ~205)
- Add thin helpers `getWatchState()` and `setWatchState(watchlist, watched)` that wrap the existing config bridge calls. (Or inline the calls in Guides.jsx if simpler — match the pattern used by `savedProfiles.js`.)

**`frontend/src/pages/Guides.jsx`** — primary changes:
1. **State**: add `watchlist: Set<string>`, `watched: Set<string>`, `hideWatched: bool`, `watchlistOnly: bool`. Hydrate from config on mount (mirror the accent-color hydration in `main.jsx:87` / `Settings.jsx:39–42`).
2. **YT id helper**: reuse existing regex (lines 10–13); extract to a top-level `ytId(url)` if not already.
3. **Cycle handler**: `cycleWatchState(id)` — None → watchlist → watched → None. Updates both Sets, then persists via `save_config_field`. Persist debounced or per-click (per-click is fine; writes are cheap).
4. **Filter pipeline** (where current `query`/`level`/`categories` filtering happens, ~line 100s): add
   - if `hideWatched && watched.has(id)` → exclude
   - if `watchlistOnly && !watchlist.has(id)` → exclude
5. **Row UI** (lines 187–229): add a small icon button next to title/author chip. Three visual states: empty bookmark / accent-colored ✓ / muted ✗. Click cycles. Stop event propagation so it doesn't toggle the accordion.
6. **Filter bar UI** (near existing toggles ~lines 121–143): add two toggle pills "Hide watched" and "Watchlist only", styled to match existing segment buttons.

## Reused utilities

- `save_config_field` / `get_config` (`bridge.py:596–603`) — persistence.
- YT id regex (`Guides.jsx:10–13`) — keying.
- Segment-button styling pattern (`Guides.jsx:5–7, 95–101`) — for the new filter toggles.
- Accent color CSS var — for the active ✓ state on the cycle icon.

## Edge cases

- Guide list refreshes from Sheets: watch state is keyed by YT id, so it survives sheet edits as long as the URL/id stays the same.
- Non-YouTube URL slips into the sheet: `ytId()` returns null → row gets no cycle button (or falls back to URL — pick one; suggest hiding the button to keep the contract clean).
- Config file missing the new fields: default to empty arrays in `bridge.py`.

## Verification

1. `cd webview_app && python main.py` — launch app.
2. Open Community Guides tab. Confirm new icon appears on each row.
3. Click a video's icon: empty → ✓. Click again: ✓ → ✗. Click again: cleared. Verify tooltip text updates.
4. Inspect `neonwhite_config.json` between clicks — confirm `guide_watchlist` / `guide_watched` arrays update with YT ids.
5. Mark 2 videos as ✓ and 2 as ✗. Toggle "Hide watched" → the two ✗ rows disappear. Toggle "Watchlist only" → only the two ✓ rows show. Combine both → only the ✓ rows show (watched already excluded).
6. Restart app. Confirm marks and toggle states (if we persist toggle state — TBD, see open question) survive.

## Open question for implementation time

- Persist the two filter toggle states across sessions, or reset to off on each launch? Default to **reset to off** (matches behavior of the existing category/level filters) unless you'd prefer sticky.

---

## Handoff prompt for Sonnet

Paste the block below into a fresh Sonnet session at the repo root (`E:\Claude-Neon-White-App`):

```
Implement the Community Guides watchlist/watched feature per the plan at
C:\Users\iamro\.claude\plans\hey-claude-wondering-if-iridescent-glacier.md.

Read that plan first — it has the full design, file paths, line anchors,
edge cases, and verification steps. Also read CLAUDE.md for working style
(be terse, confirm before risky actions, neonwhite_app.py is dead code —
the live entry point is webview_app/main.py).

Scope summary:
- Backend: extend default config in webview_app/bridge.py with
  guide_watchlist:[] and guide_watched:[] (lists of YouTube video IDs).
  No new bridge methods — reuse get_config / save_config_field.
- Frontend (frontend/src/pages/Guides.jsx): add a single cycling icon per
  row (None → ✓ watchlist → ✗ watched → None), two filter toggle pills
  ("Hide watched", "Watchlist only") in the existing filter bar, and the
  state/persistence wiring. Key videos by YouTube ID using the existing
  regex at Guides.jsx:10–13. Hydrate state on mount, persist on each
  click via save_config_field.
- For non-YouTube URLs (no extractable id), hide the cycle button.
- Filter toggles reset to off on launch (don't persist).

Verification — actually run the app and click through it:
1. cd webview_app && python main.py
2. Open Community Guides. Click a video's icon through all three states;
   confirm tooltip updates and accent color shows on ✓.
3. Open neonwhite_config.json between clicks — confirm the YT IDs
   appear/disappear in guide_watchlist / guide_watched.
4. Mark 2 videos ✓ and 2 ✗. Toggle "Hide watched" — the ✗ rows hide.
   Toggle "Watchlist only" — only ✓ rows show. Combine both — same.
5. Restart the app — confirm marks survive, toggles reset to off.

Do NOT claim success based only on type-checks or builds. UI must be
exercised in the browser/webview. If you can't run it, say so.

When done, append a short log to 03_Sessions/2026-05-10.md per
CLAUDE.md's startup ritual.
```
