#!/usr/bin/env python3
"""
tools/build_ghosts_sheet.py — one-shot dev script to populate the Ghosts index sheet.

Run from the repo root:
    python tools/build_ghosts_sheet.py

Prerequisites:
  - Fill in SHEET_ID below (from the published Google Sheet you just created).
  - SteamScraper/credentials.json on disk (same OAuth client used by the app).
  - The Ghosts tab must exist in the sheet and the sheet must be published to web
    (File → Share → Publish to web → entire document → CSV).

The script OAuths once, caches the token at tools/.ghosts_token.json, then:
  1. Walks the Drive tree rooted at DRIVE_ROOT_FOLDER_ID.
  2. Parses level / medal / player / time from the folder hierarchy.
  3. Validates level names against rush_data.LEVELS (mismatches printed loudly).
  4. Writes a single sorted batch to the Ghosts tab, overwriting it fully (idempotent).
"""
import re
import sys
from pathlib import Path

# ── Fill these in before running ─────────────────────────────────────────────
SHEET_ID             = "1FXr-2Rs4RgPF6Oo2BVz-_UQXf_3PPa8nCGstdIl12q8"
DRIVE_ROOT_FOLDER_ID = "1JiN4Y-Qj-W84va0joZh6NzeYsOq3EVc1"

# ── Paths (relative to this file) ────────────────────────────────────────────
_HERE        = Path(__file__).parent
_REPO        = _HERE.parent
CREDENTIALS  = _REPO / "SteamScraper" / "credentials.json"
TOKEN_FILE   = _HERE / ".ghosts_token.json"

SHEET_TAB    = "Ghosts"
HEADER       = ["level", "medal", "player", "time", "drive_url"]

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

VALID_MEDALS = ["Emerald", "Amethyst", "Sapphire"]
_MEDAL_ORDER = {m.lower(): i for i, m in enumerate(VALID_MEDALS)}

# ── Import rush_data for canonical level names ────────────────────────────────
sys.path.insert(0, str(_REPO / "SteamScraper"))
from rush_data import LEVELS  # noqa: E402

_LEVEL_ORDER   = {display.lower(): i for i, (display, _) in enumerate(LEVELS)}
_VALID_LEVELS  = {display.lower(): display for display, _ in LEVELS}


# ─────────────────────────────────────────────────────────────────────────────

def _get_creds():
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def _list_children(drive, parent_id: str) -> list[dict]:
    """Return all non-trashed children of a folder, handling pagination."""
    items, page_token = [], None
    while True:
        kwargs: dict = dict(
            q=f"'{parent_id}' in parents and trashed=false",
            fields="nextPageToken,files(id,name,mimeType,webViewLink)",
            pageSize=1000,
        )
        if page_token:
            kwargs["pageToken"] = page_token
        result = drive.files().list(**kwargs).execute()
        items.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return items


def _is_folder(item: dict) -> bool:
    return "folder" in item.get("mimeType", "")


def _walk(drive, root_id: str) -> list[dict]:
    """
    Walk Ghosts/<Chapter>/<Level>/<Medal>/<Player> - <Time>/<file>.phant
    Returns a list of row dicts ready for the sheet.
    """
    rows: list[dict] = []
    warnings = 0

    for chapter in _list_children(drive, root_id):
        if not _is_folder(chapter):
            continue

        for level_folder in _list_children(drive, chapter["id"]):
            if not _is_folder(level_folder):
                continue
            # Strip "1-1 " / "12-3 " and "V-1 " / "R-1 " / "Y-1 " prefixes.
            level_raw = re.sub(r'^(?:\d+|[A-Za-z])-\d+\s+', '', level_folder["name"].strip())
            level_key = level_raw.lower()
            if level_key not in _VALID_LEVELS:
                print(f"  WARNING: unknown level folder '{level_raw}' — skipping")
                warnings += 1
                continue
            level_display = _VALID_LEVELS[level_key]

            for medal_folder in _list_children(drive, level_folder["id"]):
                if not _is_folder(medal_folder):
                    continue
                medal_raw = medal_folder["name"].strip()
                medal_key = medal_raw.lower()
                if medal_key not in _MEDAL_ORDER:
                    print(f"  WARNING: unknown medal '{medal_raw}' under {level_raw} — skipping")
                    warnings += 1
                    continue
                medal_display = medal_raw.capitalize()

                for player_folder in _list_children(drive, medal_folder["id"]):
                    if not _is_folder(player_folder):
                        continue
                    parts = player_folder["name"].split(" - ", 1)
                    if len(parts) != 2:
                        print(f"  WARNING: can't parse player/time from '{player_folder['name']}' — skipping")
                        warnings += 1
                        continue
                    player, time_str = parts[0].strip(), parts[1].strip()

                    files = _list_children(drive, player_folder["id"])
                    phant = next((f for f in files if f["name"].lower().endswith(".phant")), None)
                    if phant is None:
                        print(f"  WARNING: no .phant in '{player_folder['name']}' ({level_raw}/{medal_raw}) — skipping")
                        warnings += 1
                        continue
                    drive_url = phant.get("webViewLink", "")
                    if not drive_url:
                        print(f"  WARNING: no webViewLink for '{phant['name']}' — skipping")
                        warnings += 1
                        continue

                    rows.append({
                        "level":     level_display,
                        "medal":     medal_display,
                        "player":    player,
                        "time":      time_str,
                        "drive_url": drive_url,
                    })

    print(f"\nWalked: {len(rows)} ghost files found, {warnings} warning(s).")
    return rows


def _sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (
        _LEVEL_ORDER.get(r["level"].lower(), 9999),
        _MEDAL_ORDER.get(r["medal"].lower(), 9999),
        r["time"],
    ))


def main() -> None:
    if SHEET_ID == "REPLACE_ME":
        print("ERROR: fill in SHEET_ID at the top of this script before running.")
        sys.exit(1)

    if not CREDENTIALS.exists():
        print(f"ERROR: credentials.json not found at {CREDENTIALS}")
        sys.exit(1)

    print("Authenticating with Google...")
    from googleapiclient.discovery import build
    creds  = _get_creds()
    drive  = build("drive",  "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)

    print(f"Walking Drive folder {DRIVE_ROOT_FOLDER_ID} ...")
    rows = _walk(drive, DRIVE_ROOT_FOLDER_ID)

    if not rows:
        print("No rows collected — aborting sheet write.")
        sys.exit(1)

    rows = _sort_rows(rows)
    values = [HEADER] + [
        [r["level"], r["medal"], r["player"], r["time"], r["drive_url"]]
        for r in rows
    ]

    print(f"Writing {len(rows)} rows to '{SHEET_TAB}!A1' in sheet {SHEET_ID!r} ...")
    sheets.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_TAB}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()

    levels_seen = len({r["level"] for r in rows})
    print(f"Done. {len(rows)} rows written across {levels_seen} levels.")


if __name__ == "__main__":
    main()
