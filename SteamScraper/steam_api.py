"""
steam_api — Steamworks API integration via ctypes.

Loads steam_api64.dll, binds the Steamworks SDK functions used by this app,
and exposes a small Python surface for finding leaderboards and fetching
entries. Module-level globals hold the live Steam handles after init_steam()
succeeds — callers reference them as e.g. `steam_api.steam_ready`.

Also owns the cheater-list fetch (it's used by fetch_batch to filter known
cheaters out of leaderboard entries).

Future home (see 00_Inbox/todo.md) for:
- Per-session find_leaderboard handle cache
- Self-imposed rate limiter on bulk operations
- Result cache with short TTL
"""
import ctypes
import json
import os
import time
from urllib.request import urlopen

from logger import get_logger
logger = get_logger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────
APP_ID     = "1533420"
BATCH_SIZE = 100
CHEATER_LIST_URL = "https://raw.githubusercontent.com/Faustas156/NeonLite/main/Resources/cheaterlist.json"

LEADERBOARD_FIND_CALLBACK   = 1104
LEADERBOARD_SCORES_CALLBACK = 1105


# ── Live Steam handles — populated by init_steam() ────────────────────────
steam        = None
user_stats   = None
utils_iface  = None
friends      = None
steam_ready  = False
player_name  = "Not connected"
logged_in_steam_id = 0
cheater_ids  = set()


# ── ctypes Structures ─────────────────────────────────────────────────────
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


# ── Cheater list ──────────────────────────────────────────────────────────
def fetch_cheater_list():
    """Fetch cheater Steam IDs from NeonLite GitHub. Returns a set of ints."""
    global cheater_ids
    try:
        with urlopen(CHEATER_LIST_URL, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # Handle both array of ints and array of strings
        if isinstance(data, list):
            cheater_ids = {int(x) for x in data}
        elif isinstance(data, dict):
            # Some lists use {"cheaters": [...]} or similar
            for v in data.values():
                if isinstance(v, list):
                    cheater_ids = {int(x) for x in v}
                    break
        return len(cheater_ids)
    except Exception:
        logger.warning("Cheater list fetch failed (%s); cheater filtering disabled this session",
                       CHEATER_LIST_URL, exc_info=True)
        cheater_ids = set()
        return 0


# ── Steam API init + low-level call helpers ───────────────────────────────
def init_steam(dll_path):
    global steam, user_stats, utils_iface, friends, steam_ready, player_name, logged_in_steam_id

    steam_dir = r"C:\Program Files (x86)\Steam"
    try:
        os.add_dll_directory(steam_dir)
    except Exception:
        logger.debug("add_dll_directory(%r) skipped", steam_dir, exc_info=True)
    try:
        os.add_dll_directory(os.path.dirname(dll_path))
    except Exception:
        logger.debug("add_dll_directory(%r) skipped", os.path.dirname(dll_path), exc_info=True)

    with open("steam_appid.txt", "w") as f:
        f.write(APP_ID)

    try:
        steam = ctypes.CDLL(dll_path)
    except Exception as e:
        logger.error("Failed to load Steam DLL %r", dll_path, exc_info=True)
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

    # Get logged-in player name and Steam ID
    steam.SteamAPI_ISteamFriends_GetPersonaName.restype = ctypes.c_char_p
    steam.SteamAPI_ISteamFriends_GetPersonaName.argtypes = [ctypes.c_void_p]
    name_bytes = steam.SteamAPI_ISteamFriends_GetPersonaName(friends)
    player_name = name_bytes.decode("utf-8", errors="replace") if name_bytes else "Unknown"

    steam.SteamAPI_ISteamUser_GetSteamID.restype = ctypes.c_uint64
    steam.SteamAPI_ISteamUser_GetSteamID.argtypes = [ctypes.c_void_p]
    steam.SteamAPI_ISteamClient_GetISteamUser.restype = ctypes.c_void_p
    steam.SteamAPI_ISteamClient_GetISteamUser.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p
    ]
    isteam_user = steam.SteamAPI_ISteamClient_GetISteamUser(
        client, h_user, h_pipe, b"SteamUser023"
    ) or steam.SteamAPI_ISteamClient_GetISteamUser(
        client, h_user, h_pipe, b"SteamUser021"
    )
    if isteam_user:
        logged_in_steam_id = steam.SteamAPI_ISteamUser_GetSteamID(isteam_user)

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
            # Skip known cheaters
            if entry.steam_id_user in cheater_ids:
                continue
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
