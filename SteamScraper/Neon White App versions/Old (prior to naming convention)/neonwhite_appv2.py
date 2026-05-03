import ctypes
import os
import time
import csv
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Google Sheets imports — gracefully optional until credentials.json is present
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False

SHEETS_SCOPE      = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE  = "credentials.json"
TOKEN_FILE        = "token.json"

# ── Constants ──────────────────────────────────────────────────────────────
APP_ID       = "1533420"
BATCH_SIZE   = 100
CONFIG_FILE  = "neonwhite_config.json"
APP_TITLE    = "Neon White Leaderboard Tool"
VERSION      = "1.0.0"

DEFAULT_CONFIG = {
    "dll_path":           "",
    "output_folder":      os.path.expanduser("~\\Desktop"),
    "entry_count":        1000,
    "theme":              "light",
    "sheet_id":           "",
    "times_tab":          "",
    "times_start_cell":   "A1",
    "ranks_tab":          "",
    "ranks_start_cell":   "A1",
}

# ── Level list ─────────────────────────────────────────────────────────────
LEVELS = [
    ("Movement",               "TUT_MOVEMENT"),
    ("Pummel",                 "TUT_SHOOTINGRANGE"),
    ("Gunner",                 "SLUGGER"),
    ("Cascade",                "TUT_FROG"),
    ("Elevate",                "TUT_JUMP"),
    ("Bounce",                 "GRID_TUT_BALLOON"),
    ("Purify",                 "TUT_BOMB2"),
    ("Climb",                  "TUT_BOMBJUMP"),
    ("Fasttrack",              "TUT_FASTTRACK"),
    ("Glass Port",             "GRID_PORT"),
    ("Take Flight",            "GRID_PAGODA"),
    ("Godspeed",               "TUT_RIFLE"),
    ("Dasher",                 "TUT_RIFLEJOCK"),
    ("Thrasher",               "TUT_DASHENEMY"),
    ("Outstretched",           "GRID_JUMPDASH"),
    ("Smackdown",              "GRID_SMACKDOWN"),
    ("Catwalk",                "GRID_MEATY_BALLOONS"),
    ("Fastlane",               "GRID_FAST_BALLOON"),
    ("Distinguish",            "GRID_DRAGON2"),
    ("Dancer",                 "GRID_DASHDANCE"),
    ("Guardian",               "TUT_GUARDIAN"),
    ("Stomp",                  "TUT_UZI"),
    ("Jumper",                 "TUT_JUMPER"),
    ("Dash Tower",             "TUT_BOMB"),
    ("Descent",                "GRID_DESCEND"),
    ("Driller",                "GRID_STAMPEROUT"),
    ("Canals",                 "GRID_CRUISE"),
    ("Sprint",                 "GRID_SPRINT"),
    ("Mountain",               "GRID_MOUNTAIN"),
    ("Superkinetic",           "GRID_SUPERKINETIC"),
    ("Arrival",                "GRID_ARRIVAL"),
    ("Forgotten City",         "FLOATING"),
    ("The Clocktower",         "GRID_BOSS_YELLOW"),
    ("Fireball",               "GRID_HOPHOP"),
    ("Ringer",                 "GRID_RINGER_TUTORIAL"),
    ("Cleaner",                "GRID_RINGER_EXPLORATION"),
    ("Warehouse",              "GRID_HOPSCOTCH"),
    ("Boom",                   "GRID_BOOM"),
    ("Streets",                "GRID_SNAKE_IN_MY_BOOT"),
    ("Steps",                  "GRID_FLOCK"),
    ("Demolition",             "GRID_BOMBS_AHOY"),
    ("Arcs",                   "GRID_ARCS"),
    ("Apartment",              "GRID_APARTMENT"),
    ("Hanging Gardens",        "TUT_TRIPWIRE"),
    ("Tangled",                "GRID_TANGLED"),
    ("Waterworks",             "GRID_HUNT"),
    ("Killswitch",             "GRID_CANNONS"),
    ("Falling",                "GRID_FALLING"),
    ("Shocker",                "TUT_SHOCKER2"),
    ("Bouquet",                "TUT_SHOCKER"),
    ("Prepare",                "GRID_PREPARE"),
    ("Triptrack",              "GRID_TRIPMAZE"),
    ("Race",                   "GRID_RACE"),
    ("Bubble",                 "TUT_FORCEFIELD2"),
    ("Shield",                 "GRID_SHIELD"),
    ("Overlook",               "SA L VAGE2"),
    ("Pop",                    "GRID_VERTICAL"),
    ("Minefield",              "GRID_MINEFIELD"),
    ("Mimic",                  "TUT_MIMIC"),
    ("Trigger",                "GRID_MIMICPOP"),
    ("Greenhouse",             "GRID_SWARM"),
    ("Sweep",                  "GRID_SWITCH"),
    ("Fuse",                   "GRID_TRAPS2"),
    ("Heaven's Edge",          "TUT_ROCKETJUMP"),
    ("Zipline",                "TUT_ZIPLINE"),
    ("Swing",                  "GRID_CLIMBANG"),
    ("Chute",                  "GRID_ROCKETUZI"),
    ("Crash",                  "GRID_CRASHLAND"),
    ("Ascent",                 "GRID_ESCALATE"),
    ("Straightaway",           "GRID_SPIDERCLAUS"),
    ("Firecracker",            "GRID_FIRECRACKER_2"),
    ("Streak",                 "GRID_SPIDERMAN"),
    ("Mirror",                 "GRID_DESTRUCTION"),
    ("Escalation",             "GRID_HEAT"),
    ("Bolt",                   "GRID_BOLT"),
    ("Godstreak",              "GRID_PON"),
    ("Plunge",                 "GRID_CHARGE"),
    ("Mayhem",                 "GRID_MIMICFINALE"),
    ("Barrage",                "GRID_BARRAGE"),
    ("Estate",                 "GRID_1GUN"),
    ("Trapwire",               "GRID_HECK"),
    ("Ricochet",               "GRID_ANTFARM"),
    ("Fortress",               "GRID_FORTRESS"),
    ("Holy Ground",            "GRID_GODTEMPLE_ENTRY"),
    ("The Third Temple",       "GRID_BOSS_GODSDEATHTEMPLE"),
    ("Spree",                  "GRID_EXTERMINATOR"),
    ("Breakthrough",           "GRID_FEVER"),
    ("Glide",                  "GRID_SKIPSLIDE"),
    ("Closer",                 "GRID_CLOSER"),
    ("Hike",                   "GRID_HIKE"),
    ("Switch",                 "GRID_SKIP"),
    ("Access",                 "GRID_CEILING"),
    ("Congregation",           "GRID_BOOP"),
    ("Sequence",               "GRID_TRIPRAP"),
    ("Marathon",               "GRID_ZIPRAP"),
    ("Sacrifice",              "TUT_ORIGIN"),
    ("Absolution",             "GRID_BOSS_RAPTURE"),
    ("Elevate Traversal I",    "SIDEQUEST_OBSTACLE_PISTOL"),
    ("Elevate Traversal II",   "SIDEQUEST_OBSTACLE_PISTOL_SHOOT"),
    ("Purify Traversal",       "SIDEQUEST_OBSTACLE_MACHINEGUN"),
    ("Godspeed Traversal",     "SIDEQUEST_OBSTACLE_RIFLE_2"),
    ("Stomp Traversal",        "SIDEQUEST_OBSTACLE_UZI2"),
    ("Fireball Traversal",     "SIDEQUEST_OBSTACLE_SHOTGUN"),
    ("Dominion Traversal",     "SIDEQUEST_OBSTACLE_ROCKETLAUNCHER"),
    ("Book of Life Traversal", "SIDEQUEST_RAPTURE_QUEST"),
    ("Doghouse",               "SIDEQUEST_DODGER"),
    ("Choker",                 "GRID_GLASSPATH"),
    ("Chain",                  "GRID_GLASSPATH2"),
    ("Hellevator",             "GRID_HELLVATOR"),
    ("Razor",                  "GRID_GLASSPATH3"),
    ("All Seeing Eye",         "SIDEQUEST_ALL_SEEING_EYE"),
    ("Resident Saw I",         "SIDEQUEST_RESIDENTSAWB"),
    ("Resident Saw II",        "SIDEQUEST_RESIDENTSAW"),
    ("Sunset Flip Powerbomb",  "SIDEQUEST_SUNSET_FLIP_POWERBOMB"),
    ("Balloon Mountain",       "GRID_BALLOONLAIR"),
    ("Climbing Gym",           "SIDEQUEST_BARREL_CLIMB"),
    ("Fisherman Suplex",       "SIDEQUEST_FISHERMAN_SUPLEX"),
    ("STF",                    "SIDEQUEST_STF"),
    ("Arena",                  "SIDEQUEST_ARENASIXNINE"),
    ("Attitude Adjustment",    "SIDEQUEST_ATTITUDE_ADJUSTMENT"),
    ("Rocket",                 "SIDEQUEST_ROCKETGODZ"),
    ("??? (Memory 1)",         "SIDEQUEST_GREEN_MEMORY"),
    ("??? (Memory 2)",         "SIDEQUEST_GREEN_MEMORY_2"),
    ("??? (Memory 3)",         "SIDEQUEST_GREEN_MEMORY_3"),
    ("??? (Memory 4)",         "SIDEQUEST_GREEN_MEMORY_4"),
]

LEVEL_LOOKUP = {d.lower(): (d, i) for d, i in LEVELS}
WHOLE_GAME_LEVELS = [(d, i) for d, i in LEVELS if not d.startswith("???")]

CHAPTERS = {
    "1 - Rebirth":                   ["Movement","Pummel","Gunner","Cascade","Elevate","Bounce","Purify","Climb","Fasttrack","Glass Port"],
    "2 - Killer Inside":             ["Take Flight","Godspeed","Dasher","Thrasher","Outstretched","Smackdown","Catwalk","Fastlane","Distinguish","Dancer"],
    "3 - Only Shallow":              ["Guardian","Stomp","Jumper","Dash Tower","Descent","Driller","Canals","Sprint","Mountain","Superkinetic"],
    "4 - The Old City":              ["Arrival","Forgotten City","The Clocktower"],
    "5 - The Burn That Cures":       ["Fireball","Ringer","Cleaner","Warehouse","Boom","Streets","Steps","Demolition","Arcs","Apartment"],
    "6 - Covenant":                  ["Hanging Gardens","Tangled","Waterworks","Killswitch","Falling","Shocker","Bouquet","Prepare","Triptrack","Race"],
    "7 - Reckoning":                 ["Bubble","Shield","Overlook","Pop","Minefield","Mimic","Trigger","Greenhouse","Sweep","Fuse"],
    "8 - Benediction":               ["Heaven's Edge","Zipline","Swing","Chute","Crash","Ascent","Straightaway","Firecracker","Streak","Mirror"],
    "9 - Apocrypha":                 ["Escalation","Bolt","Godstreak","Plunge","Mayhem","Barrage","Estate","Trapwire","Ricochet","Fortress"],
    "10 - The Third Temple":         ["Holy Ground","The Third Temple"],
    "11 - Thousand Pound Butterfly": ["Spree","Breakthrough","Glide","Closer","Hike","Switch","Access","Congregation","Sequence","Marathon"],
    "12 - Hand of God":              ["Sacrifice","Absolution"],
    "Sidequests - Red":              ["Elevate Traversal I","Elevate Traversal II","Purify Traversal","Godspeed Traversal","Stomp Traversal","Fireball Traversal","Dominion Traversal","Book of Life Traversal"],
    "Sidequests - Violet":           ["Doghouse","Choker","Chain","Hellevator","Razor","All Seeing Eye","Resident Saw I","Resident Saw II"],
    "Sidequests - Yellow":           ["Sunset Flip Powerbomb","Balloon Mountain","Climbing Gym","Fisherman Suplex","STF","Arena","Attitude Adjustment","Rocket"],
}

# ── Steam API globals ──────────────────────────────────────────────────────
steam       = None
user_stats  = None
utils_iface = None
friends     = None
steam_ready = False
player_name = "Not connected"

class LeaderboardFindResult(ctypes.Structure):
    _fields_ = [("leaderboard_handle", ctypes.c_uint64),
                ("leaderboard_found",  ctypes.c_uint8)]

class LeaderboardEntry(ctypes.Structure):
    _fields_ = [("steam_id_user",  ctypes.c_uint64),
                ("global_rank",    ctypes.c_int32),
                ("score",          ctypes.c_int32),
                ("details_count",  ctypes.c_int32),
                ("ugc_handle",     ctypes.c_uint64)]

class LeaderboardScoresDownloaded(ctypes.Structure):
    _fields_ = [("leaderboard_handle",        ctypes.c_uint64),
                ("leaderboard_entries_handle", ctypes.c_uint64),
                ("entry_count",               ctypes.c_int32)]

LEADERBOARD_FIND_CALLBACK   = 1104
LEADERBOARD_SCORES_CALLBACK = 1105

# ── Config ─────────────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# ── Google Sheets helpers ──────────────────────────────────────────────────
def get_sheets_service():
    """Authenticate and return a Google Sheets service object."""
    if not SHEETS_AVAILABLE:
        raise RuntimeError(
            "Google API libraries not installed.\n"
            "Run: pip install google-api-python-client google-auth-httplib2 "
            "google-auth-oauthlib"
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
    Write a single column of values to a sheet tab starting at start_cell,
    filling downward. values is a list of scalars.
    """
    col_idx, row_idx = parse_cell(start_cell)
    col_letter = ""
    n = col_idx + 1
    while n:
        n, r = divmod(n - 1, 26)
        col_letter = chr(65 + r) + col_letter

    start_row = row_idx + 1
    end_row   = row_idx + len(values)
    range_str = f"'{tab}'!{col_letter}{start_row}:{col_letter}{end_row}"

    body = {"values": [[v] for v in values]}
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_str,
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()

# ── Steam API functions ────────────────────────────────────────────────────
def init_steam(dll_path):
    global steam, user_stats, utils_iface, friends, steam_ready, player_name

    steam_dir = r"C:\Program Files (x86)\Steam"
    try:
        os.add_dll_directory(steam_dir)
    except Exception:
        pass
    try:
        os.add_dll_directory(os.path.dirname(dll_path))
    except Exception:
        pass

    with open("steam_appid.txt", "w") as f:
        f.write(APP_ID)

    try:
        steam = ctypes.CDLL(dll_path)
    except Exception as e:
        return False, f"Failed to load DLL: {e}"

    steam.SteamAPI_Init.restype = ctypes.c_bool
    if not steam.SteamAPI_Init():
        return False, "SteamAPI_Init failed — is Steam running and logged in?"

    steam.SteamAPI_GetHSteamPipe.restype = ctypes.c_int
    steam.SteamAPI_GetHSteamUser.restype = ctypes.c_int
    h_pipe = steam.SteamAPI_GetHSteamPipe()
    h_user = steam.SteamAPI_GetHSteamUser()

    steam.SteamInternal_CreateInterface.restype = ctypes.c_void_p
    steam.SteamInternal_CreateInterface.argtypes = [ctypes.c_char_p]
    client = steam.SteamInternal_CreateInterface(b"SteamClient021") or \
             steam.SteamInternal_CreateInterface(b"SteamClient020")

    steam.SteamAPI_ISteamClient_GetISteamUserStats.restype = ctypes.c_void_p
    steam.SteamAPI_ISteamClient_GetISteamUserStats.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p
    ]
    user_stats = steam.SteamAPI_ISteamClient_GetISteamUserStats(
        client, h_user, h_pipe, b"STEAMUSERSTATS_INTERFACE_VERSION012"
    ) or steam.SteamAPI_ISteamClient_GetISteamUserStats(
        client, h_user, h_pipe, b"STEAMUSERSTATS_INTERFACE_VERSION011"
    )

    steam.SteamAPI_ISteamClient_GetISteamUtils.restype = ctypes.c_void_p
    steam.SteamAPI_ISteamClient_GetISteamUtils.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p
    ]
    utils_iface = steam.SteamAPI_ISteamClient_GetISteamUtils(
        client, h_pipe, b"SteamUtils010"
    ) or steam.SteamAPI_ISteamClient_GetISteamUtils(
        client, h_pipe, b"SteamUtils009"
    )

    steam.SteamAPI_ISteamClient_GetISteamFriends.restype = ctypes.c_void_p
    steam.SteamAPI_ISteamClient_GetISteamFriends.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p
    ]
    friends = steam.SteamAPI_ISteamClient_GetISteamFriends(
        client, h_user, h_pipe, b"SteamFriends017"
    ) or steam.SteamAPI_ISteamClient_GetISteamFriends(
        client, h_user, h_pipe, b"SteamFriends015"
    )

    steam.SteamAPI_ISteamUserStats_RequestCurrentStats.restype = ctypes.c_bool
    steam.SteamAPI_ISteamUserStats_RequestCurrentStats.argtypes = [ctypes.c_void_p]
    steam.SteamAPI_ISteamUserStats_RequestCurrentStats(user_stats)
    steam.SteamAPI_RunCallbacks()
    time.sleep(1)

    # Get logged-in player name
    steam.SteamAPI_ISteamFriends_GetPersonaName.restype = ctypes.c_char_p
    steam.SteamAPI_ISteamFriends_GetPersonaName.argtypes = [ctypes.c_void_p]
    name_bytes = steam.SteamAPI_ISteamFriends_GetPersonaName(friends)
    player_name = name_bytes.decode("utf-8", errors="replace") if name_bytes else "Unknown"

    # Setup remaining signatures
    steam.SteamAPI_ISteamUtils_IsAPICallCompleted.restype = ctypes.c_bool
    steam.SteamAPI_ISteamUtils_IsAPICallCompleted.argtypes = [
        ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_bool)
    ]
    steam.SteamAPI_ISteamUtils_GetAPICallResult.restype = ctypes.c_bool
    steam.SteamAPI_ISteamUtils_GetAPICallResult.argtypes = [
        ctypes.c_void_p, ctypes.c_uint64, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)
    ]
    steam.SteamAPI_ISteamUserStats_FindLeaderboard.restype = ctypes.c_uint64
    steam.SteamAPI_ISteamUserStats_FindLeaderboard.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    steam.SteamAPI_ISteamUserStats_DownloadLeaderboardEntries.restype = ctypes.c_uint64
    steam.SteamAPI_ISteamUserStats_DownloadLeaderboardEntries.argtypes = [
        ctypes.c_void_p, ctypes.c_uint64, ctypes.c_int, ctypes.c_int, ctypes.c_int
    ]
    steam.SteamAPI_ISteamUserStats_DownloadLeaderboardEntriesForUsers.restype = ctypes.c_uint64
    steam.SteamAPI_ISteamUserStats_DownloadLeaderboardEntriesForUsers.argtypes = [
        ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.c_int
    ]
    steam.SteamAPI_ISteamUserStats_GetDownloadedLeaderboardEntry.restype = ctypes.c_bool
    steam.SteamAPI_ISteamUserStats_GetDownloadedLeaderboardEntry.argtypes = [
        ctypes.c_void_p, ctypes.c_uint64, ctypes.c_int,
        ctypes.POINTER(LeaderboardEntry), ctypes.c_void_p, ctypes.c_int
    ]
    steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount.restype = ctypes.c_int
    steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount.argtypes = [
        ctypes.c_void_p, ctypes.c_uint64
    ]
    steam.SteamAPI_ISteamFriends_GetFriendPersonaName.restype = ctypes.c_char_p
    steam.SteamAPI_ISteamFriends_GetFriendPersonaName.argtypes = [
        ctypes.c_void_p, ctypes.c_uint64
    ]

    steam_ready = True
    return True, "Connected"

def wait_for_call(call_handle, result_struct, callback_id, timeout=10.0):
    failed = ctypes.c_bool(False)
    deadline = time.time() + timeout
    while time.time() < deadline:
        steam.SteamAPI_RunCallbacks()
        time.sleep(0.1)
        if steam.SteamAPI_ISteamUtils_IsAPICallCompleted(
                utils_iface, call_handle, ctypes.byref(failed)):
            break
    if failed.value:
        return False
    io_failed = ctypes.c_bool(False)
    return steam.SteamAPI_ISteamUtils_GetAPICallResult(
        utils_iface, call_handle, ctypes.byref(result_struct),
        ctypes.sizeof(result_struct), callback_id, ctypes.byref(io_failed)
    )

def find_leaderboard(name):
    call = steam.SteamAPI_ISteamUserStats_FindLeaderboard(user_stats, name.encode())
    result = LeaderboardFindResult()
    if wait_for_call(call, result, LEADERBOARD_FIND_CALLBACK):
        if result.leaderboard_found:
            return result.leaderboard_handle
    return None

def fetch_batch(lb_handle, start, end):
    call = steam.SteamAPI_ISteamUserStats_DownloadLeaderboardEntries(
        user_stats, lb_handle, 0, start, end
    )
    result = LeaderboardScoresDownloaded()
    if not wait_for_call(call, result, LEADERBOARD_SCORES_CALLBACK):
        return []
    entries = []
    for i in range(result.entry_count):
        entry = LeaderboardEntry()
        ok = steam.SteamAPI_ISteamUserStats_GetDownloadedLeaderboardEntry(
            user_stats, result.leaderboard_entries_handle, i,
            ctypes.byref(entry), None, 0
        )
        if ok:
            nb = steam.SteamAPI_ISteamFriends_GetFriendPersonaName(friends, entry.steam_id_user)
            pname = nb.decode("utf-8", errors="replace") if nb else str(entry.steam_id_user)
            entries.append({
                "rank": entry.global_rank, "steam_id": entry.steam_id_user,
                "name": pname, "score_ms": entry.score,
                "time": f"{entry.score / 1000:.3f}",
            })
    return entries

def get_player_entry(lb_handle, steam_id):
    id_array = (ctypes.c_uint64 * 1)(steam_id)
    call = steam.SteamAPI_ISteamUserStats_DownloadLeaderboardEntriesForUsers(
        user_stats, lb_handle, id_array, 1
    )
    result = LeaderboardScoresDownloaded()
    if not wait_for_call(call, result, LEADERBOARD_SCORES_CALLBACK):
        return None
    if result.entry_count == 0:
        return None
    entry = LeaderboardEntry()
    ok = steam.SteamAPI_ISteamUserStats_GetDownloadedLeaderboardEntry(
        user_stats, result.leaderboard_entries_handle, 0,
        ctypes.byref(entry), None, 0
    )
    return entry if (ok and entry.steam_id_user == steam_id) else None

# ── Themes ─────────────────────────────────────────────────────────────────
THEMES = {
    "light": {
        "bg":          "#ffffff",
        "bg2":         "#f5f5f5",
        "bg3":         "#ebebeb",
        "fg":          "#1a1a1a",
        "fg2":         "#555555",
        "accent":      "#1a1a1a",
        "border":      "#dddddd",
        "success":     "#2d7a2d",
        "error":       "#cc2222",
        "row_alt":     "#f9f9f9",
        "select":      "#e8e8e8",
        "log_bg":      "#f5f5f5",
        "log_fg":      "#333333",
        "btn_bg":      "#ffffff",
        "btn_active":  "#ebebeb",
        "sidebar_sel": "#e0e0e0",
    },
    "dark": {
        "bg":          "#1e1e1e",
        "bg2":         "#2a2a2a",
        "bg3":         "#333333",
        "fg":          "#e8e8e8",
        "fg2":         "#999999",
        "accent":      "#e8e8e8",
        "border":      "#3a3a3a",
        "success":     "#4caf50",
        "error":       "#ef5350",
        "row_alt":     "#242424",
        "select":      "#3a3a3a",
        "log_bg":      "#2a2a2a",
        "log_fg":      "#cccccc",
        "btn_bg":      "#2a2a2a",
        "btn_active":  "#3a3a3a",
        "sidebar_sel": "#3a3a3a",
    },
}

# ── Main App ───────────────────────────────────────────────────────────────
class NeonWhiteApp:
    def __init__(self, root):
        self.root        = root
        self.cfg         = load_config()
        self.t           = THEMES[self.cfg["theme"]]
        self.running     = False
        self.current_section = None
        self._player_results = []

        root.title(APP_TITLE)
        root.geometry("900x620")
        root.minsize(800, 500)
        root.configure(bg=self.t["bg"])

        self._build_ui()
        self._apply_theme()
        self._show_section("global")

        # Auto-connect if DLL path saved
        if self.cfg["dll_path"] and os.path.exists(self.cfg["dll_path"]):
            threading.Thread(target=self._connect_steam, daemon=True).start()

    # ── UI Construction ────────────────────────────────────────────────────
    def _build_ui(self):
        t = self.t

        # Root panes
        self.sidebar_frame = tk.Frame(self.root, width=190, bg=t["bg2"])
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar_frame.pack_propagate(False)

        self.main_frame = tk.Frame(self.root, bg=t["bg"])
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_sidebar()
        self._build_global_section()
        self._build_level_section()
        self._build_player_section()
        self._build_settings_section()

    def _build_sidebar(self):
        t = self.t
        sb = self.sidebar_frame

        # App title
        tk.Label(sb, text="Neon White", font=("Helvetica", 13, "bold"),
                 bg=t["bg2"], fg=t["fg"], anchor="w",
                 padx=16, pady=14).pack(fill=tk.X)
        tk.Label(sb, text="Leaderboard Tool", font=("Helvetica", 10),
                 bg=t["bg2"], fg=t["fg2"], anchor="w",
                 padx=16).pack(fill=tk.X)

        # Divider
        tk.Frame(sb, height=1, bg=t["border"]).pack(fill=tk.X, pady=12)

        # Nav buttons
        nav_items = [
            ("global",   "Global Export"),
            ("level",    "Level Search"),
            ("player",   "Player Lookup"),
        ]
        self.nav_btns = {}
        for key, label in nav_items:
            btn = tk.Label(sb, text=label, font=("Helvetica", 11),
                           bg=t["bg2"], fg=t["fg"], anchor="w",
                           padx=20, pady=9, cursor="hand2")
            btn.pack(fill=tk.X)
            btn.bind("<Button-1>", lambda e, k=key: self._show_section(k))
            self.nav_btns[key] = btn

        # Divider
        tk.Frame(sb, height=1, bg=t["border"]).pack(fill=tk.X, pady=12)

        # Settings button
        self.settings_btn = tk.Label(sb, text="Settings", font=("Helvetica", 11),
                                     bg=t["bg2"], fg=t["fg"], anchor="w",
                                     padx=20, pady=9, cursor="hand2")
        self.settings_btn.pack(fill=tk.X)
        self.settings_btn.bind("<Button-1>", lambda e: self._show_section("settings"))

        # Status panel at bottom
        self.status_frame = tk.Frame(sb, bg=t["bg2"])
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=12)

        tk.Frame(self.status_frame, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 10))

        self.status_dot = tk.Label(self.status_frame, text="●", font=("Helvetica", 10),
                                   bg=t["bg2"], fg=t["error"])
        self.status_dot.pack(anchor="w")

        self.status_label = tk.Label(self.status_frame, text="Not connected",
                                     font=("Helvetica", 9), bg=t["bg2"], fg=t["fg2"],
                                     wraplength=155, justify=tk.LEFT, anchor="w")
        self.status_label.pack(fill=tk.X)

        self.dll_label = tk.Label(self.status_frame, text="DLL: not set",
                                  font=("Helvetica", 8), bg=t["bg2"], fg=t["fg2"],
                                  wraplength=155, justify=tk.LEFT, anchor="w")
        self.dll_label.pack(fill=tk.X, pady=(2, 0))

        self.player_label = tk.Label(self.status_frame, text="Player: —",
                                     font=("Helvetica", 8), bg=t["bg2"], fg=t["fg2"],
                                     wraplength=155, justify=tk.LEFT, anchor="w")
        self.player_label.pack(fill=tk.X, pady=(2, 0))

    # ── Sections ───────────────────────────────────────────────────────────
    def _build_global_section(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.global_frame = f

        self._section_header(f, "Global Export",
                             "Fetch the top N entries for every level and save to CSV.")

        ctrl = tk.Frame(f, bg=t["bg"], padx=24)
        ctrl.pack(fill=tk.X, pady=(0, 12))

        # Entry count
        r1 = tk.Frame(ctrl, bg=t["bg"])
        r1.pack(fill=tk.X, pady=4)
        tk.Label(r1, text="Entries per level", width=18, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.global_count_var = tk.StringVar(value=str(self.cfg["entry_count"]))
        tk.Entry(r1, textvariable=self.global_count_var, width=10,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)

        # Output folder
        r2 = tk.Frame(ctrl, bg=t["bg"])
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text="Output folder", width=18, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.global_folder_var = tk.StringVar(value=self.cfg["output_folder"])
        tk.Entry(r2, textvariable=self.global_folder_var, width=38,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(r2, text="Browse", command=self._browse_output_global,
                  font=("Helvetica", 9)).pack(side=tk.LEFT)

        # Output options
        r3 = tk.Frame(ctrl, bg=t["bg"])
        r3.pack(fill=tk.X, pady=4)
        tk.Label(r3, text="Output", width=18, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.global_out_var = tk.StringVar(value="csv")
        for val, lbl in [("display", "Display in app"), ("csv", "Save to CSV"), ("both", "Both")]:
            tk.Radiobutton(r3, text=lbl, variable=self.global_out_var, value=val,
                           font=("Helvetica", 10), bg=t["bg"], fg=t["fg"],
                           selectcolor=t["bg3"], activebackground=t["bg"]).pack(side=tk.LEFT, padx=6)

        # Run button
        self.global_run_btn = tk.Button(ctrl, text="Run Export",
                                        font=("Helvetica", 10, "bold"),
                                        command=self._run_global)
        self.global_run_btn.pack(anchor="w", pady=(10, 0))

        self._build_results_area(f, "global")

    def _build_level_section(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.level_frame = f

        self._section_header(f, "Level Search",
                             "Fetch the top N entries for a specific level.")

        ctrl = tk.Frame(f, bg=t["bg"], padx=24)
        ctrl.pack(fill=tk.X, pady=(0, 12))

        # Level selector
        r1 = tk.Frame(ctrl, bg=t["bg"])
        r1.pack(fill=tk.X, pady=4)
        tk.Label(r1, text="Level", width=14, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.level_var = tk.StringVar()
        level_names = [d for d, _ in LEVELS]
        self.level_combo = ttk.Combobox(r1, textvariable=self.level_var,
                                        values=level_names, width=28,
                                        font=("Helvetica", 10))
        self.level_combo.pack(side=tk.LEFT)
        self.level_combo.bind("<KeyRelease>", self._filter_levels)

        # Entry count
        r2 = tk.Frame(ctrl, bg=t["bg"])
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text="Entries to fetch", width=14, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.level_count_var = tk.StringVar(value="100")
        tk.Entry(r2, textvariable=self.level_count_var, width=10,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)

        # Output options
        r3 = tk.Frame(ctrl, bg=t["bg"])
        r3.pack(fill=tk.X, pady=4)
        tk.Label(r3, text="Output", width=14, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.level_out_var = tk.StringVar(value="display")
        for val, lbl in [("display", "Display in app"), ("csv", "Save to CSV"), ("both", "Both")]:
            tk.Radiobutton(r3, text=lbl, variable=self.level_out_var, value=val,
                           font=("Helvetica", 10), bg=t["bg"], fg=t["fg"],
                           selectcolor=t["bg3"], activebackground=t["bg"]).pack(side=tk.LEFT, padx=6)

        self.level_run_btn = tk.Button(ctrl, text="Search",
                                       font=("Helvetica", 10, "bold"),
                                       command=self._run_level)
        self.level_run_btn.pack(anchor="w", pady=(10, 0))

        self._build_results_area(f, "level")

    def _build_player_section(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.player_frame = f

        self._section_header(f, "Player Lookup",
                             "Look up a player's rank and time by Steam ID.")

        ctrl = tk.Frame(f, bg=t["bg"], padx=24)
        ctrl.pack(fill=tk.X, pady=(0, 12))

        # Steam ID
        r1 = tk.Frame(ctrl, bg=t["bg"])
        r1.pack(fill=tk.X, pady=4)
        tk.Label(r1, text="Steam ID", width=16, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.player_id_var = tk.StringVar()
        tk.Entry(r1, textvariable=self.player_id_var, width=22,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        tk.Label(r1, text="  17-digit number from Steam profile URL",
                 font=("Helvetica", 9), bg=t["bg"], fg=t["fg2"]).pack(side=tk.LEFT)

        # Search mode
        r2 = tk.Frame(ctrl, bg=t["bg"])
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text="Search mode", width=16, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.player_mode_var = tk.StringVar(value="level")
        for val, lbl in [("level", "Single level"), ("chapter", "Chapter"), ("game", "Whole game")]:
            tk.Radiobutton(r2, text=lbl, variable=self.player_mode_var, value=val,
                           font=("Helvetica", 10), bg=t["bg"], fg=t["fg"],
                           selectcolor=t["bg3"], activebackground=t["bg"],
                           command=self._update_player_mode).pack(side=tk.LEFT, padx=6)

        # Dynamic sub-selector
        self.player_sub_frame = tk.Frame(ctrl, bg=t["bg"])
        self.player_sub_frame.pack(fill=tk.X, pady=4)
        self._update_player_mode()

        # Output options
        r4 = tk.Frame(ctrl, bg=t["bg"])
        r4.pack(fill=tk.X, pady=4)
        tk.Label(r4, text="Output", width=16, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.player_out_var = tk.StringVar(value="display")
        for val, lbl in [("display", "Display in app"), ("csv", "Save to CSV"), ("both", "Both")]:
            tk.Radiobutton(r4, text=lbl, variable=self.player_out_var, value=val,
                           font=("Helvetica", 10), bg=t["bg"], fg=t["fg"],
                           selectcolor=t["bg3"], activebackground=t["bg"]).pack(side=tk.LEFT, padx=6)

        self.player_run_btn = tk.Button(ctrl, text="Look Up",
                                        font=("Helvetica", 10, "bold"),
                                        command=self._run_player)
        self.player_run_btn.pack(anchor="w", pady=(10, 0))

        self._build_results_area(f, "player")

    def _build_settings_section(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.settings_frame = f

        self._section_header(f, "Settings", "Configure the application.")

        ctrl = tk.Frame(f, bg=t["bg"], padx=24)
        ctrl.pack(fill=tk.X, pady=(0, 12))

        # DLL path
        r1 = tk.Frame(ctrl, bg=t["bg"])
        r1.pack(fill=tk.X, pady=6)
        tk.Label(r1, text="steam_api64.dll path", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_dll_var = tk.StringVar(value=self.cfg["dll_path"])
        tk.Entry(r1, textvariable=self.settings_dll_var, width=36,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(r1, text="Browse", command=self._browse_dll,
                  font=("Helvetica", 9)).pack(side=tk.LEFT)
        tk.Button(r1, text="Connect", command=self._connect_from_settings,
                  font=("Helvetica", 9)).pack(side=tk.LEFT, padx=(6, 0))

        # Output folder
        r2 = tk.Frame(ctrl, bg=t["bg"])
        r2.pack(fill=tk.X, pady=6)
        tk.Label(r2, text="Default output folder", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_folder_var = tk.StringVar(value=self.cfg["output_folder"])
        tk.Entry(r2, textvariable=self.settings_folder_var, width=36,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(r2, text="Browse", command=self._browse_output_settings,
                  font=("Helvetica", 9)).pack(side=tk.LEFT)

        # Default entry count
        r3 = tk.Frame(ctrl, bg=t["bg"])
        r3.pack(fill=tk.X, pady=6)
        tk.Label(r3, text="Default entry count", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_count_var = tk.StringVar(value=str(self.cfg["entry_count"]))
        tk.Entry(r3, textvariable=self.settings_count_var, width=10,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)

        # Theme
        r4 = tk.Frame(ctrl, bg=t["bg"])
        r4.pack(fill=tk.X, pady=6)
        tk.Label(r4, text="Theme", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_theme_var = tk.StringVar(value=self.cfg["theme"])
        for val, lbl in [("light", "Light"), ("dark", "Dark")]:
            tk.Radiobutton(r4, text=lbl, variable=self.settings_theme_var, value=val,
                           font=("Helvetica", 10), bg=t["bg"], fg=t["fg"],
                           selectcolor=t["bg3"], activebackground=t["bg"]).pack(side=tk.LEFT, padx=6)

        tk.Button(ctrl, text="Save Settings", font=("Helvetica", 10, "bold"),
                  command=self._save_settings).pack(anchor="w", pady=(14, 0))

        # ── Google Sheets ──────────────────────────────────────────────────
        tk.Frame(ctrl, height=1, bg=t["border"]).pack(fill=tk.X, pady=(20, 12))
        tk.Label(ctrl, text="Google Sheets Integration",
                 font=("Helvetica", 12, "bold"),
                 bg=t["bg"], fg=t["fg"], anchor="w").pack(anchor="w", pady=(0, 4))
        tk.Label(ctrl,
                 text="Place credentials.json in the app folder, then configure below.\n"
                      "On first use a browser will open to sign in with Google.",
                 font=("Helvetica", 9), bg=t["bg"], fg=t["fg2"], justify=tk.LEFT,
                 anchor="w").pack(anchor="w", pady=(0, 10))

        # Sheet ID
        rs1 = tk.Frame(ctrl, bg=t["bg"])
        rs1.pack(fill=tk.X, pady=4)
        tk.Label(rs1, text="Sheet URL or ID", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_sheet_id_var = tk.StringVar(value=self.cfg.get("sheet_id", ""))
        tk.Entry(rs1, textvariable=self.settings_sheet_id_var, width=44,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)

        # Times tab
        rs2 = tk.Frame(ctrl, bg=t["bg"])
        rs2.pack(fill=tk.X, pady=4)
        tk.Label(rs2, text="Times tab name", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_times_tab_var = tk.StringVar(value=self.cfg.get("times_tab", ""))
        tk.Entry(rs2, textvariable=self.settings_times_tab_var, width=20,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(rs2, text="Starting cell", font=("Helvetica", 10),
                 bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_times_cell_var = tk.StringVar(value=self.cfg.get("times_start_cell", "A1"))
        tk.Entry(rs2, textvariable=self.settings_times_cell_var, width=6,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(6, 0))

        # Ranks tab
        rs3 = tk.Frame(ctrl, bg=t["bg"])
        rs3.pack(fill=tk.X, pady=4)
        tk.Label(rs3, text="Ranks tab name", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_ranks_tab_var = tk.StringVar(value=self.cfg.get("ranks_tab", ""))
        tk.Entry(rs3, textvariable=self.settings_ranks_tab_var, width=20,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(rs3, text="Starting cell", font=("Helvetica", 10),
                 bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_ranks_cell_var = tk.StringVar(value=self.cfg.get("ranks_start_cell", "A1"))
        tk.Entry(rs3, textvariable=self.settings_ranks_cell_var, width=6,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(6, 0))

        # Auth status + test button
        rs4 = tk.Frame(ctrl, bg=t["bg"])
        rs4.pack(fill=tk.X, pady=(10, 0))
        self.sheets_auth_label = tk.Label(
            rs4,
            text="● Not authenticated" if not os.path.exists(TOKEN_FILE) else "● Authenticated",
            font=("Helvetica", 9),
            bg=t["bg"],
            fg=t["error"] if not os.path.exists(TOKEN_FILE) else t["success"]
        )
        self.sheets_auth_label.pack(side=tk.LEFT)
        tk.Button(rs4, text="Sign in with Google",
                  font=("Helvetica", 9),
                  command=self._sheets_authenticate).pack(side=tk.LEFT, padx=(12, 0))
        tk.Button(rs4, text="Sign out",
                  font=("Helvetica", 9),
                  command=self._sheets_signout).pack(side=tk.LEFT, padx=(6, 0))

    def _build_results_area(self, parent, key):
        t = self.t
        pane = tk.Frame(parent, bg=t["bg"], padx=24, pady=0)
        pane.pack(fill=tk.BOTH, expand=True)

        # Log area
        log_frame = tk.Frame(pane, bg=t["bg"])
        log_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(log_frame, text="Log", font=("Helvetica", 9, "bold"),
                 bg=t["bg"], fg=t["fg2"], anchor="w").pack(anchor="w")
        log = tk.Text(log_frame, height=4, font=("Courier", 9),
                      bg=t["log_bg"], fg=t["log_fg"], relief="flat",
                      bd=1, state=tk.DISABLED, wrap=tk.WORD)
        log.pack(fill=tk.X)
        setattr(self, f"{key}_log", log)

        # Table area
        table_frame = tk.Frame(pane, bg=t["bg"])
        table_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(table_frame, text="Results", font=("Helvetica", 9, "bold"),
                 bg=t["bg"], fg=t["fg2"], anchor="w").pack(anchor="w")

        cols = ("rank", "level", "name", "time")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=10)
        for col, width, label in [
            ("rank",  70,  "Rank"),
            ("level", 180, "Level"),
            ("name",  200, "Player"),
            ("time",  100, "Time"),
        ]:
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="center" if col in ("rank", "time") else "w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        setattr(self, f"{key}_tree", tree)

        # Push to Sheet button — only shown on player tab
        if key == "player":
            sheet_btn_frame = tk.Frame(pane, bg=t["bg"])
            sheet_btn_frame.pack(fill=tk.X, pady=(8, 0))
            self.push_sheet_btn = tk.Button(
                sheet_btn_frame,
                text="Push to Google Sheet",
                font=("Helvetica", 10, "bold"),
                command=self._push_to_sheet,
                state=tk.DISABLED
            )
            self.push_sheet_btn.pack(anchor="w")
            tk.Label(sheet_btn_frame,
                     text="Configure Google Sheets in Settings before using.",
                     font=("Helvetica", 8), bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(2, 0))

    def _section_header(self, parent, title, subtitle):
        t = self.t
        hdr = tk.Frame(parent, bg=t["bg"], padx=24, pady=18)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=title, font=("Helvetica", 16, "bold"),
                 bg=t["bg"], fg=t["fg"]).pack(anchor="w")
        tk.Label(hdr, text=subtitle, font=("Helvetica", 10),
                 bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(2, 0))
        tk.Frame(parent, height=1, bg=t["border"]).pack(fill=tk.X, padx=24, pady=(0, 12))

    # ── Navigation ─────────────────────────────────────────────────────────
    def _show_section(self, key):
        t = self.t
        sections = {
            "global":   self.global_frame,
            "level":    self.level_frame,
            "player":   self.player_frame,
            "settings": self.settings_frame,
        }
        for k, frame in sections.items():
            frame.pack_forget()
        sections[key].pack(fill=tk.BOTH, expand=True)
        self.current_section = key

        # Highlight sidebar
        for k, btn in self.nav_btns.items():
            btn.configure(bg=t["sidebar_sel"] if k == key else t["bg2"],
                          font=("Helvetica", 11, "bold" if k == key else "normal"))
        self.settings_btn.configure(
            bg=t["sidebar_sel"] if key == "settings" else t["bg2"],
            font=("Helvetica", 11, "bold" if key == "settings" else "normal")
        )

    # ── Player mode ────────────────────────────────────────────────────────
    def _update_player_mode(self):
        t = self.t
        for w in self.player_sub_frame.winfo_children():
            w.destroy()

        mode = self.player_mode_var.get()

        if mode == "level":
            tk.Label(self.player_sub_frame, text="Level", width=16, anchor="w",
                     font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
            self.player_level_var = tk.StringVar()
            combo = ttk.Combobox(self.player_sub_frame, textvariable=self.player_level_var,
                                 values=[d for d, _ in LEVELS], width=28, font=("Helvetica", 10))
            combo.pack(side=tk.LEFT)

        elif mode == "chapter":
            tk.Label(self.player_sub_frame, text="Chapter", width=16, anchor="w",
                     font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
            self.player_chapter_var = tk.StringVar()
            combo = ttk.Combobox(self.player_sub_frame, textvariable=self.player_chapter_var,
                                 values=list(CHAPTERS.keys()), width=34, font=("Helvetica", 10))
            combo.pack(side=tk.LEFT)

        elif mode == "game":
            tk.Label(self.player_sub_frame,
                     text="All 121 levels will be searched.",
                     font=("Helvetica", 10), bg=t["bg"], fg=t["fg2"]).pack(side=tk.LEFT)

    # ── Steam connection ───────────────────────────────────────────────────
    def _connect_steam(self, dll_path=None):
        path = dll_path or self.cfg["dll_path"]
        if not path:
            self._set_status(False, "No DLL path set. Go to Settings.")
            return
        self._set_status(None, "Connecting...")
        ok, msg = init_steam(path)
        if ok:
            self._set_status(True, "Connected", path)
        else:
            self._set_status(False, msg)

    def _connect_from_settings(self):
        path = self.settings_dll_var.get().strip()
        if not path:
            messagebox.showerror("Error", "Please set the DLL path first.")
            return
        self.cfg["dll_path"] = path
        save_config(self.cfg)
        threading.Thread(target=self._connect_steam, args=(path,), daemon=True).start()

    def _set_status(self, connected, message, dll_path=None):
        t = self.t
        if connected is True:
            color = t["success"]
            self.status_label.configure(text="Connected", fg=t["success"])
            self.player_label.configure(text=f"Player: {player_name}")
        elif connected is False:
            color = t["error"]
            self.status_label.configure(text=message, fg=t["error"])
            self.player_label.configure(text="Player: —")
        else:
            color = t["fg2"]
            self.status_label.configure(text=message, fg=t["fg2"])
            self.player_label.configure(text="Player: —")

        self.status_dot.configure(fg=color)

        if dll_path:
            short = dll_path if len(dll_path) < 28 else "..." + dll_path[-25:]
            self.dll_label.configure(text=f"DLL: {short}")
        elif connected is False and not dll_path:
            self.dll_label.configure(text="DLL: not connected")

    # ── Log helpers ────────────────────────────────────────────────────────
    def _log(self, key, msg):
        log = getattr(self, f"{key}_log")
        log.configure(state=tk.NORMAL)
        log.insert(tk.END, msg + "\n")
        log.see(tk.END)
        log.configure(state=tk.DISABLED)
        self.root.update_idletasks()

    def _clear_log(self, key):
        log = getattr(self, f"{key}_log")
        log.configure(state=tk.NORMAL)
        log.delete("1.0", tk.END)
        log.configure(state=tk.DISABLED)

    def _clear_table(self, key):
        tree = getattr(self, f"{key}_tree")
        tree.delete(*tree.get_children())

    def _add_row(self, key, rank, level, name, time_str):
        tree = getattr(self, f"{key}_tree")
        tree.insert("", tk.END, values=(f"#{rank}", level, name, f"{time_str}s"))

    # ── Browse helpers ─────────────────────────────────────────────────────
    def _browse_dll(self):
        path = filedialog.askopenfilename(
            title="Select steam_api64.dll",
            filetypes=[("DLL files", "*.dll"), ("All files", "*.*")]
        )
        if path:
            self.settings_dll_var.set(path)

    def _browse_output_global(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.global_folder_var.set(folder)

    def _browse_output_settings(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.settings_folder_var.set(folder)

    def _filter_levels(self, event):
        val = self.level_var.get().lower()
        filtered = [d for d, _ in LEVELS if val in d.lower()]
        self.level_combo["values"] = filtered

    # ── Save settings ──────────────────────────────────────────────────────
    def _save_settings(self):
        self.cfg["dll_path"]         = self.settings_dll_var.get().strip()
        self.cfg["output_folder"]    = self.settings_folder_var.get().strip()
        self.cfg["theme"]            = self.settings_theme_var.get()
        self.cfg["sheet_id"]         = self._extract_sheet_id(self.settings_sheet_id_var.get().strip())
        self.cfg["times_tab"]        = self.settings_times_tab_var.get().strip()
        self.cfg["times_start_cell"] = self.settings_times_cell_var.get().strip()
        self.cfg["ranks_tab"]        = self.settings_ranks_tab_var.get().strip()
        self.cfg["ranks_start_cell"] = self.settings_ranks_cell_var.get().strip()
        try:
            self.cfg["entry_count"] = int(self.settings_count_var.get())
        except ValueError:
            messagebox.showerror("Error", "Entry count must be a number.")
            return
        save_config(self.cfg)
        self.global_count_var.set(str(self.cfg["entry_count"]))
        if self.cfg["theme"] != self.t:
            messagebox.showinfo("Theme", "Restart the app to apply the new theme.")
        messagebox.showinfo("Saved", "Settings saved successfully.")

    def _extract_sheet_id(self, url_or_id):
        import re
        m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url_or_id)
        return m.group(1) if m else url_or_id

    # ── Google Sheets auth ─────────────────────────────────────────────────
    def _sheets_authenticate(self):
        def auth_worker():
            try:
                get_sheets_service()
                self.sheets_auth_label.configure(
                    text="● Authenticated", fg=self.t["success"]
                )
                messagebox.showinfo("Google Sheets", "Successfully signed in!")
            except Exception as e:
                messagebox.showerror("Authentication failed", str(e))
        threading.Thread(target=auth_worker, daemon=True).start()

    def _sheets_signout(self):
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        self.sheets_auth_label.configure(
            text="● Not authenticated", fg=self.t["error"]
        )
        messagebox.showinfo("Google Sheets", "Signed out. Token removed.")

    # ── Push to Sheet ──────────────────────────────────────────────────────
    def _push_to_sheet(self):
        if not self._player_results:
            messagebox.showerror("No data", "Run a Player Lookup first.")
            return

        sheet_id   = self.cfg.get("sheet_id", "").strip()
        times_tab  = self.cfg.get("times_tab", "").strip()
        times_cell = self.cfg.get("times_start_cell", "A1").strip()
        ranks_tab  = self.cfg.get("ranks_tab", "").strip()
        ranks_cell = self.cfg.get("ranks_start_cell", "A1").strip()

        if not sheet_id:
            messagebox.showerror("Error", "No Sheet ID set. Configure Google Sheets in Settings.")
            return
        if not times_tab and not ranks_tab:
            messagebox.showerror("Error", "Configure at least one tab name in Settings.")
            return

        self.push_sheet_btn.configure(state=tk.DISABLED, text="Pushing...")

        def push_worker():
            try:
                service     = get_sheets_service()
                times_vals  = [r["time"]  for r in self._player_results]
                ranks_vals  = [r["rank"]  for r in self._player_results]

                if times_tab:
                    push_to_sheet(service, sheet_id, times_tab, times_cell, times_vals)
                if ranks_tab:
                    push_to_sheet(service, sheet_id, ranks_tab, ranks_cell, ranks_vals)

                count = len(self._player_results)
                parts = []
                if times_tab:
                    parts.append(f"{count} times → '{times_tab}'!{times_cell}")
                if ranks_tab:
                    parts.append(f"{count} ranks → '{ranks_tab}'!{ranks_cell}")
                messagebox.showinfo("Success", "Pushed to Google Sheet:\n" + "\n".join(parts))

            except Exception as e:
                messagebox.showerror("Push failed", str(e))
            finally:
                self.push_sheet_btn.configure(state=tk.NORMAL, text="Push to Google Sheet")

        threading.Thread(target=push_worker, daemon=True).start()



    # ── Run: Global Export ─────────────────────────────────────────────────
    def _run_global(self):
        if not steam_ready:
            messagebox.showerror("Not connected", "Connect to Steam first in Settings.")
            return
        if self.running:
            return
        try:
            count = int(self.global_count_var.get())
        except ValueError:
            messagebox.showerror("Error", "Entry count must be a number.")
            return
        folder = self.global_folder_var.get()
        out    = self.global_out_var.get()

        self.running = True
        self.global_run_btn.configure(state=tk.DISABLED, text="Running...")
        self._clear_log("global")
        self._clear_table("global")

        threading.Thread(
            target=self._global_worker,
            args=(count, folder, out),
            daemon=True
        ).start()

    def _global_worker(self, count, folder, out):
        csv_path = os.path.join(folder, "neon_white_top_entries.csv")
        csv_file = None
        writer   = None

        if out in ("csv", "both"):
            csv_file = open(csv_path, "w", newline="", encoding="utf-8")
            writer = csv.DictWriter(
                csv_file, fieldnames=["rank","level","name","score_ms","time"]
            )
            writer.writeheader()

        total_levels = len(LEVELS)
        for idx, (display, internal) in enumerate(LEVELS, 1):
            self._log("global", f"[{idx}/{total_levels}] {display}...")
            lb = find_leaderboard(internal)
            if not lb:
                self._log("global", f"  → not found, skipping.")
                continue

            total_entries = steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(user_stats, lb)
            fetch = min(total_entries, count)
            start = 1
            level_rows = []
            while start <= fetch:
                end   = min(start + BATCH_SIZE - 1, fetch)
                batch = fetch_batch(lb, start, end)
                if not batch:
                    break
                for e in batch:
                    e["level"] = display
                level_rows.extend(batch)
                start = end + 1
                time.sleep(0.05)

            for r in level_rows:
                if out in ("display", "both"):
                    self._add_row("global", r["rank"], display, r["name"], r["time"])
                if writer:
                    writer.writerow({k: r[k] for k in ["rank","level","name","score_ms","time"]})
            if csv_file:
                csv_file.flush()

            self._log("global", f"  → {len(level_rows)} entries fetched.")

        if csv_file:
            csv_file.close()
            self._log("global", f"\nSaved to {csv_path}")

        self._log("global", "Done!")
        self.global_run_btn.configure(state=tk.NORMAL, text="Run Export")
        self.running = False

    # ── Run: Level Search ──────────────────────────────────────────────────
    def _run_level(self):
        if not steam_ready:
            messagebox.showerror("Not connected", "Connect to Steam first in Settings.")
            return
        if self.running:
            return

        level_name = self.level_var.get().strip()
        match = LEVEL_LOOKUP.get(level_name.lower())
        if not match:
            messagebox.showerror("Error", f"Level '{level_name}' not found.")
            return

        try:
            count = int(self.level_count_var.get())
        except ValueError:
            messagebox.showerror("Error", "Entry count must be a number.")
            return

        out = self.level_out_var.get()
        display_name, internal_name = match

        self.running = True
        self.level_run_btn.configure(state=tk.DISABLED, text="Searching...")
        self._clear_log("level")
        self._clear_table("level")

        threading.Thread(
            target=self._level_worker,
            args=(display_name, internal_name, count, out),
            daemon=True
        ).start()

    def _level_worker(self, display_name, internal_name, count, out):
        self._log("level", f"Finding leaderboard for {display_name}...")
        lb = find_leaderboard(internal_name)
        if not lb:
            self._log("level", "Leaderboard not found.")
            self.level_run_btn.configure(state=tk.NORMAL, text="Search")
            self.running = False
            return

        total = steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(user_stats, lb)
        fetch = min(total, count)
        self._log("level", f"Total entries: {total:,}  |  Fetching top {fetch}...")

        start = 1
        all_rows = []
        while start <= fetch:
            end   = min(start + BATCH_SIZE - 1, fetch)
            batch = fetch_batch(lb, start, end)
            if not batch:
                break
            all_rows.extend(batch)
            start = end + 1
            time.sleep(0.05)

        for r in all_rows:
            if out in ("display", "both"):
                self._add_row("level", r["rank"], display_name, r["name"], r["time"])

        if out in ("csv", "both"):
            safe  = display_name.replace(" ", "_").replace("'", "")
            path  = os.path.join(self.cfg["output_folder"], f"{safe}_top{len(all_rows)}.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["rank","level","name","score_ms","time"])
                writer.writeheader()
                for r in all_rows:
                    writer.writerow({k: r.get(k, display_name) for k in ["rank","name","score_ms","time"]} | {"level": display_name})
            self._log("level", f"Saved to {path}")

        self._log("level", f"Done. {len(all_rows)} entries retrieved.")
        self.level_run_btn.configure(state=tk.NORMAL, text="Search")
        self.running = False

    # ── Run: Player Lookup ─────────────────────────────────────────────────
    def _run_player(self):
        if not steam_ready:
            messagebox.showerror("Not connected", "Connect to Steam first in Settings.")
            return
        if self.running:
            return

        sid_str = self.player_id_var.get().strip()
        if not sid_str.isdigit() or len(sid_str) != 17:
            messagebox.showerror("Error", "Steam ID must be a 17-digit number.")
            return
        steam_id = int(sid_str)
        mode = self.player_mode_var.get()
        out  = self.player_out_var.get()

        levels_to_search = []
        context = ""

        if mode == "level":
            name = self.player_level_var.get().strip()
            match = LEVEL_LOOKUP.get(name.lower())
            if not match:
                messagebox.showerror("Error", f"Level '{name}' not found.")
                return
            levels_to_search = [match]
            context = match[0]

        elif mode == "chapter":
            chap = self.player_chapter_var.get().strip()
            if chap not in CHAPTERS:
                messagebox.showerror("Error", "Please select a valid chapter.")
                return
            for dn in CHAPTERS[chap]:
                m = LEVEL_LOOKUP.get(dn.lower())
                if m:
                    levels_to_search.append(m)
            context = chap

        elif mode == "game":
            levels_to_search = list(WHOLE_GAME_LEVELS)
            context = "Whole Game"

        self.running = True
        self.player_run_btn.configure(state=tk.DISABLED, text="Looking up...")
        self._clear_log("player")
        self._clear_table("player")

        threading.Thread(
            target=self._player_worker,
            args=(steam_id, levels_to_search, context, out),
            daemon=True
        ).start()

    def _player_worker(self, steam_id, levels_to_search, context, out):
        # Resolve player name once upfront
        nb = steam.SteamAPI_ISteamFriends_GetFriendPersonaName(friends, steam_id)
        looked_up_name = nb.decode("utf-8", errors="replace") if nb else str(steam_id)
        self._log("player", f"Looking up {looked_up_name} across {len(levels_to_search)} levels...")
        rows = []

        for display_name, internal_name in levels_to_search:
            self._log("player", f"  {display_name}...")
            lb = find_leaderboard(internal_name)
            if not lb:
                self._log("player", f"  {display_name}... not found.")
                continue
            total = steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(user_stats, lb)
            entry = get_player_entry(lb, steam_id)
            if entry:
                time_str = f"{entry.score / 1000:.3f}"
                self._log("player", f"  {display_name}... rank #{entry.global_rank}, {time_str}s")
                rows.append({
                    "level":    display_name,
                    "rank":     entry.global_rank,
                    "time":     time_str,
                    "score_ms": entry.score,
                    "total":    total,
                })
                if out in ("display", "both"):
                    self._add_row("player", entry.global_rank, display_name, looked_up_name, time_str)
            else:
                self._log("player", f"  {display_name}... no entry.")

        if out in ("csv", "both") and rows:
            safe_ctx = context.replace(" ", "_").replace("/", "_").replace("-", "")
            path = os.path.join(self.cfg["output_folder"], f"player_{safe_ctx}.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["level","rank","time","score_ms","total"]
                )
                writer.writeheader()
                writer.writerows(rows)
            self._log("player", f"\nSaved to {path}")

        self._log("player", f"Done. Found entries on {len(rows)}/{len(levels_to_search)} levels.")
        self._player_results = rows  # store for Push to Sheet
        if rows:
            self.push_sheet_btn.configure(state=tk.NORMAL)
        self.player_run_btn.configure(state=tk.NORMAL, text="Look Up")
        self.running = False

    # ── Theme application ──────────────────────────────────────────────────
    def _apply_theme(self):
        t = self.t
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=t["bg"],
                        foreground=t["fg"],
                        fieldbackground=t["bg"],
                        rowheight=22,
                        font=("Helvetica", 9))
        style.configure("Treeview.Heading",
                        background=t["bg2"],
                        foreground=t["fg"],
                        font=("Helvetica", 9, "bold"))
        style.map("Treeview", background=[("selected", t["select"])])
        style.configure("TScrollbar", background=t["bg2"])
        style.configure("TCombobox", fieldbackground=t["bg"], background=t["bg2"],
                        foreground=t["fg"])


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = NeonWhiteApp(root)
    root.mainloop()
    if steam_ready:
        steam.SteamAPI_Shutdown()
