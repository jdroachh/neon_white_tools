import ctypes
import os
import time
import csv

os.chdir(os.path.dirname(os.path.abspath(__file__)))

STEAM_PATH = r"C:\Program Files (x86)\Steam"
GAME_DLL_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll"

os.add_dll_directory(STEAM_PATH)
os.add_dll_directory(os.path.dirname(GAME_DLL_PATH))

if not os.path.exists("steam_appid.txt"):
    with open("steam_appid.txt", "w") as f:
        f.write("1533420")

steam = ctypes.CDLL(GAME_DLL_PATH)
steam.SteamAPI_Init.restype = ctypes.c_bool
steam.SteamAPI_Init()

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
utils = steam.SteamAPI_ISteamClient_GetISteamUtils(
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

# ── Structs ────────────────────────────────────────────────────────────────
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
BATCH_SIZE = 100  # Steam's maximum per request

# ── Setup function signatures ──────────────────────────────────────────────
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

# ── Helpers ────────────────────────────────────────────────────────────────
def wait_for_call(call_handle, result_struct, callback_id, timeout=10.0):
    failed = ctypes.c_bool(False)
    deadline = time.time() + timeout
    while time.time() < deadline:
        steam.SteamAPI_RunCallbacks()
        time.sleep(0.1)
        if steam.SteamAPI_ISteamUtils_IsAPICallCompleted(
                utils, call_handle, ctypes.byref(failed)):
            break
    if failed.value:
        return False
    io_failed = ctypes.c_bool(False)
    return steam.SteamAPI_ISteamUtils_GetAPICallResult(
        utils, call_handle, ctypes.byref(result_struct),
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
    """Fetch entries from rank `start` to `end` (1-indexed, inclusive)."""
    call = steam.SteamAPI_ISteamUserStats_DownloadLeaderboardEntries(
        user_stats, lb_handle, 0, start, end  # 0 = k_ELeaderboardDataRequestGlobal
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
            name_bytes = steam.SteamAPI_ISteamFriends_GetFriendPersonaName(
                friends, entry.steam_id_user
            )
            player_name = name_bytes.decode('utf-8', errors='replace') \
                          if name_bytes else str(entry.steam_id_user)
            entries.append({
                "rank":     entry.global_rank,
                "steam_id": entry.steam_id_user,
                "name":     player_name,
                "score":    entry.score,
            })
    return entries

# ── Main ───────────────────────────────────────────────────────────────────
LEVEL_NAME    = "TUT_MOVEMENT"
DISPLAY_NAME  = "Movement"
OUTPUT_CSV    = f"{DISPLAY_NAME}_leaderboard.csv"

print(f"Finding leaderboard: {LEVEL_NAME}")
lb_handle = find_leaderboard(LEVEL_NAME)
if not lb_handle:
    print("Leaderboard not found.")
    steam.SteamAPI_Shutdown()
    exit(1)

total = steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(user_stats, lb_handle)
total = min(total, 1000)  # remove this line after confirming CSV looks correct
print(f"Total entries: {total:,}")
print(f"Total entries: {total:,}")
print(f"Fetching all {total:,} entries in batches of {BATCH_SIZE}...\n")

all_entries = []
batch_num = 0
start = 1

while start <= total:
    end = min(start + BATCH_SIZE - 1, total)
    batch_num += 1
    print(f"  Batch {batch_num}: ranks {start}–{end}...", end=" ", flush=True)
    batch = fetch_batch(lb_handle, start, end)
    if not batch:
        print("empty/failed, stopping.")
        break
    all_entries.extend(batch)
    print(f"got {len(batch)} entries (total so far: {len(all_entries):,})")
    start = end + 1
    time.sleep(0.05)  # small delay to be polite to Steam's servers

# ── Write CSV ──────────────────────────────────────────────────────────────
print(f"\nWriting {len(all_entries):,} entries to {OUTPUT_CSV}...")
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["rank", "steam_id", "name", "score"])
    writer.writeheader()
    writer.writerows(all_entries)

print(f"Done. Saved to C:\\SteamScraper\\{OUTPUT_CSV}")
steam.SteamAPI_Shutdown()