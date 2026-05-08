# World Record VODs tab (Resources)

## Context
Add a third Resources sub-page that lets users look up the current Neon White world-record video for a chosen level + platform (PC / Switch / PlayStation). Source is a community-maintained Google Sheet (`1rG5WNRp4XBGxImwF4c0cj5oYbdIC4yMTpx45BU3cOLU`) tracking WRs from speedrun.com.

This mirrors the existing Ghosts and Route Videos pages, both of which already pull anonymously from public sheets via the GViz CSV endpoint and index at startup. The same pattern fits here.

## Source — `WR Import` tab
After investigation, the cleanest source is the **`WR Import`** tab (a denormalized flat list with raw YouTube URLs in their own column — no hyperlink-extraction problem). Verified structure:

- **Row 1** = banner row (`"","","PC"`).
- **Row 2** = column header row, repeated 3× horizontally for PC / Switch / PS:
  - Cols 0–1: `Chapter Name`, `Level Name` (always blank in data rows — don't rely on these)
  - Cols 2–9: PC `Runner Name | Run Time | Run Time Formatted | Run Date | Video Link | Video Title | Runner Comment | True Link`
  - Cols 10–17: Switch (same shape)
  - Cols 18–25: PS (same shape)
- **Rows 3–123**: 121 data rows, **in canonical `rush_data.LEVELS` order**. Verified:
  - Row 3 → Movement (LEVELS index 0) ✓
  - Row 25 → Jumper (LEVELS index 22) ✓
  - Row 98 → Sacrifice (LEVELS index 95) ✓
  - Row 123 → Rocket (LEVELS index 120) ✓

### ⚠️ Critical parsing detail
`Runner Comment` cells are user-submitted text and frequently contain embedded newlines. **Must parse with Python's `csv.reader`** (not line-counting), which correctly handles multi-line quoted fields. This was the source of an early diagnostic dead-end where line-numbering looked misaligned with sheet rows.

## Approach
Extend `resources.py` with a third loader. Mirror the existing daemon-thread, fetch-once-at-startup pattern.

### Backend — `SteamScraper/webview_app/resources.py`
- Add module constants:
  - `_WR_SHEET_ID = "1rG5WNRp4XBGxImwF4c0cj5oYbdIC4yMTpx45BU3cOLU"`
  - `_WR_TAB = "WR Import"`
  - `_VALID_PLATFORMS = ("pc", "switch", "playstation")` (ordered, since column blocks are positional)
- Add `_index_wrs(rows: list[list[str]]) -> dict[str, dict[str, dict]]`:
  - Drop the first 2 rows (banner + header).
  - Import `rush_data.LEVELS` and assert `len(rows) == len(LEVELS)`. If it doesn't match, log warning and abort the load (status flag stays False so the page shows graceful unavailable state).
  - **Sanity-check canary rows** (Movement at idx 0, Sacrifice at idx 95, Rocket at idx 120) by scanning the row's PC `Video Title` for the level-name keyword. Mismatch → log + abort.
  - For each `(row_index, level_name)`, emit one entry per platform with column block offsets `[2, 10, 18]`:
    ```python
    {
      "level": level_name,
      "platform": "pc" | "switch" | "playstation",
      "player": ...,           # col +0
      "time_formatted": ...,   # col +2
      "date": ...,             # col +3
      "youtube_url": ...,      # col +4
      "title": ...,            # col +5
    }
    ```
  - Skip platforms whose row is missing `youtube_url` (some PS entries are blank — e.g. last row Rocket has no PS data).
  - Validate `youtube_url` starts with `https://www.youtube.com/`, `https://youtube.com/`, or `https://youtu.be/` (matches existing Routes loader pattern); skip otherwise with a warning.
- Build cache `_WRS: dict[str, dict[str, dict]]` keyed by `level.lower() → platform → row dict` (single dict per platform — only current WR per the user spec).
- Extend `_fetch_resources_bg()` with a third try/except block that calls `_fetch_csv_rows(_csv_url(_WR_SHEET_ID, _WR_TAB))` and `_index_wrs()`.
- Extend `_STATUS` with `wrs_loaded`.
- Add `get_wr_for(level: str, platform: str) -> dict | None`.

### Backend — `SteamScraper/webview_app/models/resources.py`
Add `WorldRecordRow` Pydantic model: `level, platform, player, time_formatted, date, youtube_url, title`.

### Bridge — `SteamScraper/webview_app/bridge.py`
Add `get_world_record(self, level: str, platform: str) -> dict | None` near the existing `get_ghosts` / `get_videos` methods (~line 1170). Delegates to `resources.get_wr_for(...)`.

### Frontend — `frontend/src/api.js`
Add `getWorldRecord(level, platform)` wrapper alongside `getGhosts` / `getVideos` (~line 158).

### Frontend — `frontend/src/shared.jsx`
Add nav entry in `NAV_ITEMS.resources` (line ~72):
```js
{ key: "wrs", label: "World Record VODs", icn: "trophy" /* TBD */ }
```

### Frontend — new file `frontend/src/pages/WorldRecordVods.jsx`
Copy `Ghosts.jsx` as the template. Differences:
- Left panel inputs: **Level dropdown** (full level list from existing stage-picker source) + **Platform segmented control** (PC / Switch / PlayStation) replacing the medal control.
- Result panel: single-row card with player, time, date, title, and a "Watch" button → opens `youtube_url` externally.
- Empty state: "No WR video listed for this level + platform yet."

### Frontend — `frontend/src/main.jsx`
Add `<WorldRecordVods />` to the `RES_PAGES` array (line ~50).

## Critical files
- `SteamScraper/webview_app/resources.py` (extend)
- `SteamScraper/webview_app/bridge.py` (one new method)
- `SteamScraper/webview_app/models/resources.py` (one new model)
- `frontend/src/api.js` (one wrapper)
- `frontend/src/shared.jsx` (one nav entry)
- `frontend/src/main.jsx` (one mount)
- `frontend/src/pages/WorldRecordVods.jsx` (new, copied from `Ghosts.jsx`)
- `SteamScraper/rush_data.py` (read-only — `LEVELS` is the canonical level list we zip against)

## Verification
1. Launch app; check logs for `WRs loaded: 121 rows indexed` (mirrors existing Ghosts/Videos log line). If row count or canaries mismatch, log warns and `wrs_loaded` stays False.
2. Open Resources → World Record VODs.
3. Pick **Pummel + PC** → expect Hyuniko 5.458 (FWR). Click Watch → YouTube opens to the right video.
4. Switch platform to **Switch** → expect TheVo1d 6.949. Then **PlayStation** → Indrik 7.150.
5. Pick **Rocket + PlayStation** → empty-state message renders (no PS data on that row), no error.
6. Kill internet before launch → page shows graceful "data unavailable" state (existing pattern for Ghosts/Routes).

## Out of scope
- Historical WR list (only current WR per platform).
- Auto-refresh during session (restart-to-repull, matching existing pattern).
- Sheet-write back to update WRs from the app.
- Mapping by `Level Name` column (currently empty across the sheet — positional mapping with sanity checks is cleaner until/unless the maintainer fills col B).
