"""
sheets — Google Sheets push for Player Lookup data.

Designed for **lazy import** by neonwhite_app.py — callers should write
`import sheets` inside the function that needs it (auth_worker /
push_worker), NOT at the top of their module. The Google client libraries
take ~500ms+ to import on cold start; deferring until the user actually
clicks Sign-In or Push keeps app launch snappy for users who never use
Sheets.

Module import itself is cheap and always succeeds, even when the Google
libs aren't installed. The actual library-availability check happens
inside `get_sheets_service()`, which raises RuntimeError with a helpful
pip-install message if the libs failed to load at module-load time.
"""
import os
from logger import get_logger

logger = get_logger(__name__)


SHEETS_SCOPE     = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE       = "token.json"


# Google libs are optional — capture the import error if they're missing,
# so get_sheets_service() can raise a helpful message instead of a bare
# ImportError at the module level.
_imports_ok = True
_imports_err = None
try:
    import importlib
    # Force-resolve namespace packages before importing (PyInstaller workaround)
    import google
    import google.auth
    import google.oauth2
    import google.oauth2.credentials
    import google.auth.transport.requests
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except Exception as e:
    _imports_ok = False
    _imports_err = e
    logger.info("Google Sheets libraries not available; Sheets push will be disabled",
                exc_info=True)


def get_sheets_service():
    """Authenticate and return a Google Sheets service object."""
    if not _imports_ok:
        raise RuntimeError(
            f"Google API libraries failed to load: {_imports_err}\n\n"
            "If you are running the EXE, please report this error.\n"
            "If you are running the Python script directly, run:\n"
            "python -m pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    if not os.path.exists(CREDENTIALS_FILE):
        raise RuntimeError(
            "credentials.json not found.\n"
            "Place your OAuth credentials file in the same folder as this app."
        )

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SHEETS_SCOPE)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SHEETS_SCOPE)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("sheets", "v4", credentials=creds)


def col_letter_to_index(letter):
    """Convert column letter(s) to 0-based index. e.g. 'A' -> 0, 'B' -> 1."""
    letter = letter.upper()
    result = 0
    for ch in letter:
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result - 1


def parse_cell(cell):
    """Parse a cell reference like 'B3' into (col_index, row_index) both 0-based."""
    import re
    m = re.match(r"([A-Za-z]+)(\d+)", cell.strip())
    if not m:
        raise ValueError(f"Invalid cell reference: {cell}")
    return col_letter_to_index(m.group(1)), int(m.group(2)) - 1


def push_to_sheet(service, sheet_id, tab, start_cell, values):
    """
    Write values to a sheet column starting at start_cell, filling downward.
    values is a list of (row_offset, value) tuples — gaps are skipped entirely.
    """
    if not values:
        return

    col_idx, row_idx = parse_cell(start_cell)
    col_letter = ""
    n = col_idx + 1
    while n:
        n, r = divmod(n - 1, 26)
        col_letter = chr(65 + r) + col_letter

    # Write each value individually to its correct row, skipping gaps
    data = []
    for offset, val in values:
        row_num   = row_idx + offset + 1
        range_str = f"'{tab}'!{col_letter}{row_num}"
        data.append({"range": range_str, "values": [[val]]})

    if data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": data}
        ).execute()
