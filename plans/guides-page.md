# Guides page (community-facing index of the Guides sheet)

## Context

The user maintains a public Google Sheet of Neon White guides (`1v0PT3dATQREHa6Bxjea2VeNL6oFyddBIvBxEtqNCxTs`, gid=0). Today there's no way to search or browse it from the app. They want a new tab in the webview app that fetches the sheet live and lets a speedrunner find a relevant guide quickly. Audience is the speedrun community, so the page needs to feel like a curated index, not a spreadsheet dump.

**Sheet shape (confirmed with the user):**
- Column A: level names (rows ~2–14)
- Columns B–F: per-level tutorials by medal tier — `Emerald`, `Amethyst 1`, `Amethyst 2`, `Sapphire 1`, `Sapphire 2`. Cells hold a guide title like `"Loki's Amethyst"`.
- Column G, rows 2–14: **technical guides** (mod install, audio/visual setup, RTSS, etc.)
- Column G, rows 19+: **medal / rush playlists**

Open detail: whether cells have hyperlinks behind the text. Plan handles both cases — fetcher tries GViz HTML (preserves `<a href>`) and falls back to plain text.

## Approach

**Layout: flat searchable list.** Flatten the matrix into one record per non-empty cell, tagged with `category` (`route` | `technical` | `playlist`), `level` (for route guides only), `tier` (medal tier for route guides), `title`, `author` (parsed from `"Author's Title"` pattern when possible), `url` (if the cell had a hyperlink).

UX:
- Search box (filters by title/author/level, case-insensitive substring)
- Three category filter chips: `Route guides` / `Technical guides` / `Medal playlists` (multi-select; all on by default)
- Optional secondary filter: level dropdown (only meaningful when `Route guides` chip is active)
- Result rows: title (clickable if URL present), author chip, level + tier badge for route guides, category badge

Why flat list over matrix: the community is filtering, not browsing. A speedrunner asking "what's the best Cascade Sapphire guide" wants two clicks (filter level → see guides), not a grid scan. Matrix view can be added later if requested.

## Data flow

Mirror the existing `resources.py` pattern (which already fetches Ghosts / RouteVideos / WorldRecordVods from public sheets via GViz):

1. Add `_GUIDES: list[dict]` module global + `start_background_fetch()` spawns a daemon thread that calls a new `_fetch_guides()` on app boot.
2. `_fetch_guides()` fetches `https://docs.google.com/spreadsheets/d/{ID}/gviz/tq?tqx=out:html&gid=0`, parses the returned HTML table with stdlib `html.parser` (no new deps — matches the project's "no `requests`" stance from `todo.md`). HTML preserves `<a href>` cell links if present.
3. Walk the parsed rows:
   - Rows 2–14: col A = level. For cols B–F, if cell non-empty, emit `{category: "route", level, tier: <header>, title, author, url}`. For col G, emit `{category: "technical", title, author, url}`.
   - Rows 19+ in col G only: emit `{category: "playlist", title, author, url}`.
4. `author` parsed by splitting on `"'s "` (e.g. `"Loki's Amethyst"` → author `Loki`, remainder kept as title). Falls back to whole string if no apostrophe.
5. Expose `get_guides() -> list[dict]` for the bridge.

Refresh strategy: same as other resources — fetched once at boot, cached in memory. Add a lightweight `refresh_guides()` bridge method later if the user wants a manual refresh button (out of scope for v1).

## Files to modify

**Backend:**
- `SteamScraper/webview_app/resources.py` — add `_GUIDES`, `_fetch_guides()`, `_parse_guides_html()`, register thread in `start_background_fetch()`, expose `get_guides()`. Reuse the existing `urllib.request.urlopen()` + 8s timeout pattern already there.
- `SteamScraper/webview_app/bridge.py` — add `def get_guides(self) -> dict` returning `{guides: [...]}`. No long-running work, no `_emit` needed.
- `SteamScraper/webview_app/models/` — add `GuidesResponse` Pydantic model (match the convention used by Ghosts).

**Frontend:**
- `frontend/src/api.js` — add `export async function getGuides()`.
- `frontend/src/pages/Guides.jsx` — new component. Reference `Ghosts.jsx` for layout primitives and `RouteVideos.jsx` for filter-chip pattern.
- `frontend/src/main.jsx` — import `Guides`, add to `WIRED_PAGES` and `PAGE_TITLES` (`guides: "Guides"`).
- `frontend/src/shared.jsx` — add nav entry to `NAV_ITEMS.resources` (lines 60–79): `{ key: "guides", label: "Guides", icn: "book" }` (or whichever icon already exists in `Icon`).

## Things explicitly out of scope

- No write-back to the sheet (read-only).
- No auth — public sheet, GViz endpoint, no OAuth.
- No category filter UI for tier (we'll just show the tier as a badge; users filter by level instead).
- No manual refresh button in v1.
- No matrix/grid view toggle in v1.

## Verification

1. **Live fetch works.** Launch the app, open the Guides tab, confirm rows render. Spot-check 3 cells against the sheet (one route guide, one technical guide, one playlist).
2. **Hyperlinks survive (if present).** Click a title — opens the linked URL via the existing `webview.open_url_in_browser` bridge (or `window.open` fallback). If the sheet has no hyperlinks, titles render as non-clickable text and a console log warns once.
3. **Search.** Type `Loki` — only Loki's guides show. Type `Cascade` — only Cascade-row guides show.
4. **Filter chips.** Toggle off `Route guides` — only technical + playlists remain. Toggle off all — empty state with helpful message.
5. **Offline degradation.** Disable network, restart app — Guides tab shows empty list with a "couldn't fetch" message; rest of app unaffected (matches behavior of other Resource fetchers).
6. **No layout regressions** in existing tabs after adding the nav entry.

---

## Handoff prompt for Sonnet

> You are implementing a new **Guides** tab in the Neon White Leaderboard Tool (pywebview + React). It surfaces a public Google Sheet of community speedrun guides as a flat, searchable, filterable list.
>
> **Sheet:** `https://docs.google.com/spreadsheets/d/1v0PT3dATQREHa6Bxjea2VeNL6oFyddBIvBxEtqNCxTs/` (gid=0). Public, no auth. Layout:
> - Col A rows 2–14: level names (`Movement`, `Pummel`, `Gunner`, ...).
> - Cols B–F rows 2–14: per-level tutorials, headers `Emerald`, `Amethyst 1`, `Amethyst 2`, `Sapphire 1`, `Sapphire 2`. Cells like `"Loki's Amethyst"` (author + title).
> - Col G rows 2–14: technical guides (mod install, audio/visual setup, etc.).
> - Col G rows 19+: medal/rush playlists.
> - Empty cells exist and must be skipped. Some cells may have hyperlinks behind the text.
>
> **Read first:**
> - `01_Codebase_Map/overview.md` for current architecture.
> - `SteamScraper/webview_app/resources.py` — this is the precedent. Read `_fetch_*`, `start_background_fetch()`, and `get_*` for Ghosts / RouteVideos / WorldRecordVods. **Match this style exactly.** Same `urllib.request.urlopen()` + 8s timeout, same daemon thread, same module-level cache, same graceful empty-on-failure behavior. Do **not** introduce `requests`, `httpx`, `beautifulsoup4`, or any new dependency — `urllib` + stdlib `html.parser` is sufficient.
> - `SteamScraper/webview_app/bridge.py` to see the `JsApi` bridge pattern and how methods return Pydantic models.
> - `SteamScraper/webview_app/models/` for the response model convention.
> - `frontend/src/pages/Ghosts.jsx` for the resource-page layout primitives.
> - `frontend/src/pages/RouteVideos.jsx` for filter-chip / search-box patterns to reuse.
> - `frontend/src/api.js`, `frontend/src/main.jsx`, `frontend/src/shared.jsx` to see how a page is wired in.
>
> **Deliver these changes:**
>
> 1. **Extend `SteamScraper/webview_app/resources.py`:**
>    - Constants: `GUIDES_SHEET_ID = "1v0PT3dATQREHa6Bxjea2VeNL6oFyddBIvBxEtqNCxTs"`, `GUIDES_GID = "0"`.
>    - Module global: `_GUIDES: list[dict] = []`.
>    - `_fetch_guides() -> None`: GET `https://docs.google.com/spreadsheets/d/{ID}/gviz/tq?tqx=out:html&gid={GID}` (HTML preserves `<a href>`). Parse the returned table via a small `html.parser.HTMLParser` subclass that captures cell text and any `<a href>` per cell. Return `(text, url_or_None)` per cell. Wrap in `try/except (URLError, TimeoutError, OSError, ValueError)` returning silently on failure — match `_fetch_ghosts` style. Log one debug line on each outcome via `logger.get_logger`.
>    - `_parse_guides(rows: list[list[tuple[str, str | None]]]) -> list[dict]`: walk the parsed rows.
>      - Identify the header row (find the row containing `"Emerald"` and `"Amethyst 1"`). Subsequent rows up to and including the last row whose col A has a level name are the **route** rows.
>      - For each route row: col A is `level`. For cols B–F, if cell text non-empty, emit `{"category": "route", "level": level, "tier": <header text>, "title": title, "author": author, "url": url}`.
>      - For col G in route rows: emit `{"category": "technical", "title": title, "author": author, "url": url}` if non-empty.
>      - For col G in rows past the route block (the row index where col A first goes blank for the rest of the sheet), emit `{"category": "playlist", "title": title, "author": author, "url": url}` if non-empty.
>      - **Author parsing:** split cell text on `"'s "` (literal). If split yields 2 parts → `author = parts[0]`, `title = parts[1]`. Otherwise → `author = ""`, `title = cell text`.
>    - `start_background_fetch()`: add a daemon thread that calls `_fetch_guides()`. Mirror the existing pattern verbatim.
>    - `get_guides() -> list[dict]`: return a copy of `_GUIDES`.
>
> 2. **`SteamScraper/webview_app/models/` — add response model:**
>    ```python
>    class Guide(BaseModel):
>        category: Literal["route", "technical", "playlist"]
>        level: str | None = None
>        tier: str | None = None
>        title: str
>        author: str
>        url: str | None = None
>
>    class GuidesResponse(BaseModel):
>        guides: list[Guide]
>    ```
>    Export from the package `__init__.py` if other models are exported there.
>
> 3. **`SteamScraper/webview_app/bridge.py`:** add
>    ```python
>    def get_guides(self) -> dict:
>        return GuidesResponse(guides=resources.get_guides()).model_dump()
>    ```
>    Match the call style of the other resource bridge methods.
>
> 4. **`frontend/src/api.js`:** add
>    ```js
>    export async function getGuides() {
>      const api = await waitForApi();
>      return api.get_guides();
>    }
>    ```
>
> 5. **`frontend/src/pages/Guides.jsx` (new):**
>    - On mount, call `getGuides()` once, store in state.
>    - State: `query` (string), `categories` (Set of `"route" | "technical" | "playlist"`, default all three), `level` (string | null, only meaningful when `route` is in `categories`).
>    - UI:
>      - Search input at top (placeholder: "Search guides by title, author, or level").
>      - Three filter chips: `Route guides`, `Technical guides`, `Medal playlists`. Click toggles. Visually match the chip style already in `RouteVideos.jsx`.
>      - When `route` is active, show a `<select>` of distinct level names (alphabetical, with a "All levels" option).
>      - Result list: `<ul>` of cards. Each card: title (anchor → `url` opening externally if `url` present, otherwise plain text), author chip, category badge. Route cards also show level + tier badge.
>      - Empty state: "No guides match these filters."
>      - Loading state: "Loading guides…" (until first fetch returns).
>      - Fetch-failure state (returned list is empty AND first fetch finished): "Couldn't load the guide sheet. Check your connection and restart the app."
>    - Filtering logic: lowercase substring match of `query` against `title + " " + author + " " + (level || "")`.
>    - Open external URLs via the existing pattern used in `RouteVideos.jsx` (find how it opens video links — reuse exactly that mechanism, do not invent a new one).
>
> 6. **`frontend/src/main.jsx`:** import `Guides`, register in `WIRED_PAGES`, add `guides: "Guides"` to `PAGE_TITLES`.
>
> 7. **`frontend/src/shared.jsx`:** add `{ key: "guides", label: "Guides", icn: "<existing-icon-name>" }` to `NAV_ITEMS.resources`. Use an icon already present in the `Icon` component — do **not** add a new icon asset for this task.
>
> **Do not:**
> - Introduce new Python dependencies. `urllib` + `html.parser` only.
> - Introduce new JS dependencies.
> - Use the Google Sheets API or OAuth — the sheet is public; GViz HTML endpoint is sufficient.
> - Add a manual refresh button, a matrix/grid view, or a tier filter — out of scope for v1.
> - Block app startup on the network call. Fetch runs in a daemon thread; failure is silent.
> - Modify any other tab.
>
> **Verify before reporting done:**
> 1. *Online:* launch the app, open Guides tab — list renders with route, technical, and playlist entries. Spot-check 3 cells against the sheet (one of each category).
> 2. *Hyperlinks:* if a cell in the source sheet has a link, the rendered title is clickable and opens externally. If not, it renders as plain text.
> 3. *Search:* `Loki` filters to Loki's guides; `Cascade` filters to Cascade-row guides; empty query shows everything.
> 4. *Filter chips:* toggling chips correctly hides/shows category groups. Toggling all off shows the empty state.
> 5. *Level dropdown:* only appears when `Route guides` is active; "All levels" shows all route entries.
> 6. *Offline:* disable network, restart — Guides tab shows the fetch-failure message, no exception, rest of app works.
> 7. *No regressions:* every other Resources tab (Ghosts, RouteVideos, WorldRecordVods) still loads.
>
> Keep the patch tight: ~120 lines of Python (mostly the HTML parser and `_parse_guides`) + ~150 lines of JSX. No refactors of unrelated code, no cleanup of nearby files.
