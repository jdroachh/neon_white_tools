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
BATCH_SIZE = 100
ENTRIES_PER_LEVEL = 1000

# ── Level map: display name -> internal name ───────────────────────────────
LEVELS = [
    ("Movement",                "TUT_MOVEMENT"),
    ("Pummel",                  "TUT_SHOOTINGRANGE"),
    ("Gunner",                  "SLUGGER"),
    ("Cascade",                 "TUT_FROG"),
    ("Elevate",                 "TUT_JUMP"),
    ("Bounce",                  "GRID_TUT_BALLOON"),
    ("Purify",                  "TUT_BOMB2"),
    ("Climb",                   "TUT_BOMBJUMP"),
    ("Fasttrack",               "TUT_FASTTRACK"),
    ("Glass Port",              "GRID_PORT"),
    ("Take Flight",             "GRID_PAGODA"),
    ("Godspeed",                "TUT_RIFLE"),
    ("Dasher",                  "TUT_RIFLEJOCK"),
    ("Thrasher",                "TUT_DASHENEMY"),
    ("Outstretched",            "GRID_JUMPDASH"),
    ("Smackdown",               "GRID_SMACKDOWN"),
    ("Catwalk",                 "GRID_MEATY_BALLOONS"),
    ("Fastlane",                "GRID_FAST_BALLOON"),
    ("Distinguish",             "GRID_DRAGON2"),
    ("Dancer",                  "GRID_DASHDANCE"),
    ("Guardian",                "TUT_GUARDIAN"),
    ("Stomp",                   "TUT_UZI"),
    ("Jumper",                  "TUT_JUMPER"),
    ("Dash Tower",              "TUT_BOMB"),
    ("Descent",                 "GRID_DESCEND"),
    ("Driller",                 "GRID_STAMPEROUT"),
    ("Canals",                  "GRID_CRUISE"),
    ("Sprint",                  "GRID_SPRINT"),
    ("Mountain",                "GRID_MOUNTAIN"),
    ("Superkinetic",            "GRID_SUPERKINETIC"),
    ("Arrival",                 "GRID_ARRIVAL"),
    ("Forgotten City",          "FLOATING"),
    ("The Clocktower",          "GRID_BOSS_YELLOW"),
    ("Fireball",                "GRID_HOPHOP"),
    ("Ringer",                  "GRID_RINGER_TUTORIAL"),
    ("Cleaner",                 "GRID_RINGER_EXPLORATION"),
    ("Warehouse",               "GRID_HOPSCOTCH"),
    ("Boom",                    "GRID_BOOM"),
    ("Streets",                 "GRID_SNAKE_IN_MY_BOOT"),
    ("Steps",                   "GRID_FLOCK"),
    ("Demolition",              "GRID_BOMBS_AHOY"),
    ("Arcs",                    "GRID_ARCS"),
    ("Apartment",               "GRID_APARTMENT"),
    ("Hanging Gardens",         "TUT_TRIPWIRE"),
    ("Tangled",                 "GRID_TANGLED"),
    ("Waterworks",              "GRID_HUNT"),
    ("Killswitch",              "GRID_CANNONS"),
    ("Falling",                 "GRID_FALLING"),
    ("Shocker",                 "TUT_SHOCKER2"),
    ("Bouquet",                 "TUT_SHOCKER"),
    ("Prepare",                 "GRID_PREPARE"),
    ("Triptrack",               "GRID_TRIPMAZE"),
    ("Race",                    "GRID_RACE"),
    ("Bubble",                  "TUT_FORCEFIELD2"),
    ("Shield",                  "GRID_SHIELD"),
    ("Pop",                     "GRID_VERTICAL"),
    ("Minefield",               "GRID_MINEFIELD"),
    ("Mimic",                   "TUT_MIMIC"),
    ("Trigger",                 "GRID_MIMICPOP"),
    ("Greenhouse",              "GRID_SWARM"),
    ("Sweep",                   "GRID_SWITCH"),
    ("Fuse",                    "GRID_TRAPS2"),
    ("Heaven's Edge",           "TUT_ROCKETJUMP"),
    ("Zipline",                 "TUT_ZIPLINE"),
    ("Swing",                   "GRID_CLIMBANG"),
    ("Chute",                   "GRID_ROCKETUZI"),
    ("Crash",                   "GRID_CRASHLAND"),
    ("Ascent",                  "GRID_ESCALATE"),
    ("Straightaway",            "GRID_SPIDERCLAUS"),
    ("Firecracker",             "GRID_FIRECRACKER_2"),
    ("Streak",                  "GRID_SPIDERMAN"),
    ("Mirror",                  "GRID_DESTRUCTION"),
    ("Escalation",              "GRID_HEAT"),
    ("Bolt",                    "GRID_BOLT"),
    ("Godstreak",               "GRID_PON"),
    ("Plunge",                  "GRID_CHARGE"),
    ("Mayhem",                  "GRID_MIMICFINALE"),
    ("Barrage",                 "GRID_BARRAGE"),
    ("Estate",                  "GRID_1GUN"),
    ("Trapwire",                "GRID_HECK"),
    ("Ricochet",                "GRID_ANTFARM"),
    ("Fortress",                "GRID_FORTRESS"),
    ("Holy Ground",             "GRID_GODTEMPLE_ENTRY"),
    ("The Third Temple",        "GRID_BOSS_GODSDEATHTEMPLE"),
    ("Spree",                   "GRID_EXTERMINATOR"),
    ("Breakthrough",            "GRID_FEVER"),
    ("Glide",                   "GRID_SKIPSLIDE"),
    ("Closer",                  "GRID_CLOSER"),
    ("Hike",                    "GRID_HIKE"),
    ("Switch",                  "GRID_SKIP"),
    ("Access",                  "GRID_CEILING"),
    ("Congregation",            "GRID_BOOP"),
    ("Sequence",                "GRID_TRIPRAP"),
    ("Marathon",                "GRID_ZIPRAP"),
    ("Sacrifice",               "TUT_ORIGIN"),
    ("Absolution",              "GRID_BOSS_RAPTURE"),
    # Sidequests
    ("Elevate Traversal I",     "SIDEQUEST_OBSTACLE_PISTOL"),
    ("Elevate Traversal II",    "SIDEQUEST_OBSTACLE_PISTOL_SHOOT"),
    ("Purify Traversal",        "SIDEQUEST_OBSTACLE_MACHINEGUN"),
    ("Godspeed Traversal",      "SIDEQUEST_OBSTACLE_RIFLE_2"),
    ("Stomp Traversal",         "SIDEQUEST_OBSTACLE_UZI2"),
    ("Fireball Traversal",      "SIDEQUEST_OBSTACLE_SHOTGUN"),
    ("Dominion Traversal",      "SIDEQUEST_OBSTACLE_ROCKETLAUNCHER"),
    ("Book of Life Traversal",  "SIDEQUEST_RAPTURE_QUEST"),
    ("Doghouse",                "SIDEQUEST_DODGER"),
    ("Choker",                  "GRID_GLASSPATH"),
    ("Chain",                   "GRID_GLASSPATH2"),
    ("Razor",                   "GRID_GLASSPATH3"),
    ("All Seeing Eye",          "SIDEQUEST_ALL_SEEING_EYE"),
    ("Resident Saw I",          "SIDEQUEST_RESIDENTSAWB"),
    ("Resident Saw II",         "SIDEQUEST_RESIDENTSAW"),
    ("Sunset Flip Powerbomb",   "SIDEQUEST_SUNSET_FLIP_POWERBOMB"),
    ("Climbing Gym",            "SIDEQUEST_BARREL_CLIMB"),
    ("Fisherman Suplex",        "SIDEQUEST_FISHERMAN_SUPLEX"),
    ("STF",                     "SIDEQUEST_STF"),
    ("Attitude Adjustment",     "SIDEQUEST_ATTITUDE_ADJUSTMENT"),
    ("Rocket",                  "SIDEQUEST_ROCKETGODZ"),
    ("??? (Memory 1)",          "SIDEQUEST_GREEN_MEMORY"),
    ("??? (Memory 2)",          "SIDEQUEST_GREEN_MEMORY_2"),
    ("??? (Memory 3)",          "SIDEQUEST_GREEN_MEMORY_3"),
    ("??? (Memory 4)",          "SIDEQUEST_GREEN_MEMORY_4"),
]

# ── Function signatures ────────────────────────────────────────────────────
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
            name_bytes = steam.SteamAPI_ISteamFriends_GetFriendPersonaName(
                friends, entry.steam_id_user
            )
            player_name = name_bytes.decode('utf-8', errors='replace') \
                          if name_bytes else str(entry.steam_id_user)
            entries.append({
                "level":    None,  # filled in by caller
                "rank":     entry.global_rank,
                "steam_id": entry.steam_id_user,
                "name":     player_name,
                "score_ms": entry.score,
                "time":     f"{entry.score / 1000:.3f}",
            })
    return entries

# ── Main loop ──────────────────────────────────────────────────────────────
OUTPUT_CSV = "neon_white_top1000.csv"

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["level", "rank", "steam_id", "name", "score_ms", "time"])
    writer.writeheader()

    for display_name, internal_name in LEVELS:
        print(f"\n[{display_name}] Finding leaderboard...", end=" ", flush=True)
        lb_handle = find_leaderboard(internal_name)
        if not lb_handle:
            print("not found, skipping.")
            continue

        total = steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(user_stats, lb_handle)
        fetch_count = min(total, ENTRIES_PER_LEVEL)
        print(f"{total:,} total entries, fetching top {fetch_count}.")

        start = 1
        level_entries = []
        while start <= fetch_count:
            end = min(start + BATCH_SIZE - 1, fetch_count)
            batch = fetch_batch(lb_handle, start, end)
            if not batch:
                break
            for e in batch:
                e["level"] = display_name
            level_entries.extend(batch)
            start = end + 1
            time.sleep(0.05)

        writer.writerows(level_entries)
        f.flush()  # write to disk after each level in case of interruption
        print(f"  -> Wrote {len(level_entries)} entries.")

print(f"\nAll done. Results saved to C:\\SteamScraper\\{OUTPUT_CSV}")
steam.SteamAPI_Shutdown()