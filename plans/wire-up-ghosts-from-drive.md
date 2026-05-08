# Plan — Wire up the Ghosts library from Drive

## Context

The Ghosts page (`frontend/src/pages/Ghosts.jsx`) and its bridge (`get_ghosts` → `resources.get_ghosts_for`) are already shipped and rendering. The cache layer in `SteamScraper/webview_app/resources.py:31` reads a public-published Google Sheet via the GViz CSV endpoint — no OAuth, no `credentials.json`, no API key. It just needs the real sheet ID and the rows.

The user has ~300 `.phant` files in a Drive tree shaped:

```
Ghosts/<Chapter>/<Level>/<Medal>/<PlayerName> - <Time>/<file>.phant
```

Updates are infrequent (every couple of months), so a one-shot dev-side script is the right tool — not runtime Drive calls. The end-user app stays anonymous-CSV-only, matching the recent direction in `feedback_distribution_secrets.md` (no secrets in distributed builds).

The chosen UX is "Open in browser" (already implemented) — the Drive URL in each row just needs to be the file's share link. No download/install logic, no Steam ghosts-folder integration, no new bridge methods.

## Approach

Three pieces, in order:

### 1. Create + publish the Ghosts sheet (manual, one-time)

- Create a new Google Sheet, e.g. **"Neon White — Ghosts Index"**.
- One tab named **`Ghosts`** with header row exactly: `level, medal, player, time, drive_url`.
- File → Share → **Publish to web** → entire document → CSV. (This is what enables the GViz endpoint without auth.)
- Confirm `https://docs.google.com/spreadsheets/d/<ID>/gviz/tq?tqx=out:csv&sheet=Ghosts` returns the header row in a browser.
- Capture the sheet ID.

### 2. Build the publishing script (dev-machine only, not bundled)

New file: **`tools/build_ghosts_sheet.py`** (new top-level `tools/` directory; **not** under `SteamScraper/` so PyInstaller never picks it up).

Responsibilities:
- OAuth via `InstalledAppFlow` against scopes:
  - `https://www.googleapis.com/auth/drive.readonly` (walk the folder tree, read share links)
  - `https://www.googleapis.com/auth/spreadsheets` (write the `Ghosts` tab)
- Token cached at `tools/.ghosts_token.json` (gitignored).
- Use the existing `credentials.json` (already on disk for Sheets push); no new client setup needed.

Walker logic:
1. Take a root Drive folder ID (the "Ghosts" parent) as a CLI arg or constant near the top of the file.
2. Recursively list children with `drive.files.list(q="'<parent_id>' in parents and trashed=false", fields="files(id,name,mimeType,webViewLink)")`.
3. Tree shape is fixed at 4 levels deep below root: chapter → level → medal → player-folder → file. Walk strictly by depth — chapter names are not used (cleaner; avoids fragile string matching against `CHAPTERS` in `rush_data.py`).
4. At the player-folder layer:
   - Split folder name on `" - "` (with surrounding spaces) → `(player, time)`. Skip with a warning if the split fails.
   - List the folder's contents; pick the first child whose name ends in `.phant` (case-insensitive). Skip with a warning if none found.
   - Use that file's `webViewLink` (Drive's standard share-page URL — opens cleanly in browser, allow-listed for `drive.google.com` in `bridge.py` `open_external_url`).
5. Validate the medal folder name is one of `{Emerald, Amethyst, Sapphire}` (case-insensitive). Skip + warn otherwise.
6. Validate the level folder name matches a display name in `rush_data.LEVELS` (case-insensitive lookup against `[display for display, _ in LEVELS]`). Print mismatches loudly so folder-name typos surface — do **not** auto-correct.

Output:
- Build `rows: list[dict]` with keys `level, medal, player, time, drive_url`.
- Sort rows by (level display order from `LEVELS`, medal in Emerald/Amethyst/Sapphire order, time ascending).
- Write to the sheet via `sheets.values().update(range="Ghosts!A1", valueInputOption="RAW", body={values: [header, *rows]})` — overwrites the whole tab. Idempotent: re-running fully refreshes.
- Print summary: `N rows written across M levels; K skipped (see warnings)`.

Add `tools/.ghosts_token.json` and `tools/__pycache__/` to `.gitignore`.

### 3. Wire the real sheet ID

Edit `SteamScraper/webview_app/resources.py:32`:
```python
_GHOSTS_SHEET_ID = "<the new sheet ID>"
```
Drop the `TODO(M4)` comment on line 31. Nothing else changes — `_index_ghosts` already matches the schema written by the script.

## Files touched

- **New:** `tools/build_ghosts_sheet.py` (~150–200 LOC)
- **New:** `.gitignore` entry for `tools/.ghosts_token.json`
- **Edit:** `SteamScraper/webview_app/resources.py:31-32` (replace placeholder ID, drop TODO)

No frontend changes. No bridge changes. No PyInstaller spec changes. No new runtime dependencies — `googleapiclient` and `google_auth_oauthlib` are already installed for the Sheets push feature, and the script imports them just like `sheets.py` does.

## Reused utilities

- `rush_data.LEVELS` (`SteamScraper/rush_data.py:198` area) — canonical list of `(display, internal)` tuples; the walker uses the display column for the level-name match and for sort order.
- OAuth + token caching pattern: copy from `SteamScraper/sheets.py` (same `InstalledAppFlow` flow, same `token.json` shape — but a separate token file so the user-facing app's token isn't affected).
- `_index_ghosts` (`SteamScraper/webview_app/resources.py:82`) — unchanged; the script writes exactly the schema it expects.

## What this plan deliberately does not do

- No live Drive calls in the running app.
- No download-to-disk for `.phant` files.
- No "install ghost into Neon White directory" feature.
- No CI / GitHub Actions automation of the walker — it's a manual run on the dev machine when ghosts get added. (Easy to add later if updates accelerate.)

## Verification

1. **Walker dry-run on a small subtree:** point the script at a single chapter folder first; confirm it parses player/time, finds the `.phant`, and gets a working `webViewLink`. Spot-check 2–3 URLs in a browser.
2. **Full run:** point at the real Ghosts root; confirm the sheet is populated with ~300 rows and warnings (if any) name specific folders.
3. **Sheet publish check:** open `https://docs.google.com/spreadsheets/d/<ID>/gviz/tq?tqx=out:csv&sheet=Ghosts` in a browser and confirm CSV with the right headers comes back.
4. **End-to-end app smoke:** launch `python -m SteamScraper.webview_app.main`, navigate to **Resources → Ghosts**, pick a level + medal, click **Open in browser** on a row → confirm Drive page loads. Try a level/medal with no ghosts → confirm the empty-state message renders.
5. **Logs:** check `logs/app.log` for `Ghosts loaded: N stages indexed` (no longer the old "Could not load Ghosts sheet" message).
