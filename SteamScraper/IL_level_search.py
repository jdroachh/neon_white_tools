import ctypes
import os
import time
import csv

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── Config ─────────────────────────────────────────────────────────────────
STEAM_PATH    = r"C:\Program Files (x86)\Steam"
GAME_DLL_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll"
APP_ID        = "1533420"
BATCH_SIZE    = 100

with open("steam_appid.txt", "w") as f:
    f.write(APP_ID)

# ── Level list ─────────────────────────────────────────────────────────────
LEVELS = [
    # Mission 1 - Rebirth
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
    # Mission 2 - Killer Inside
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
    # Mission 3 - Only Shallow
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
    # Mission 4 - The Old City
    ("Arrival",                 "GRID_ARRIVAL"),
    ("Forgotten City",          "FLOATING"),
    ("The Clocktower",          "GRID_BOSS_YELLOW"),
    # Mission 5 - The Burn That Cures
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
    # Mission 6 - Covenant
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
    # Mission 7 - Reckoning
    ("Bubble",                  "TUT_FORCEFIELD2"),
    ("Shield",                  "GRID_SHIELD"),
    ("Overlook",                "SA L VAGE2"),
    ("Pop",                     "GRID_VERTICAL"),
    ("Minefield",               "GRID_MINEFIELD"),
    ("Mimic",                   "TUT_MIMIC"),
    ("Trigger",                 "GRID_MIMICPOP"),
    ("Greenhouse",              "GRID_SWARM"),
    ("Sweep",                   "GRID_SWITCH"),
    ("Fuse",                    "GRID_TRAPS2"),
    # Mission 8 - Benediction
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
    # Mission 9 - Apocrypha
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
    # Mission 10 - The Third Temple
    ("Holy Ground",             "GRID_GODTEMPLE_ENTRY"),
    ("The Third Temple",        "GRID_BOSS_GODSDEATHTEMPLE"),
    # Mission 11 - Thousand Pound Butterfly
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
    # Mission 12 - Hand of God
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
    ("Hellevator",              "GRID_HELLVATOR"),
    ("Razor",                   "GRID_GLASSPATH3"),
    ("All Seeing Eye",          "SIDEQUEST_ALL_SEEING_EYE"),
    ("Resident Saw I",          "SIDEQUEST_RESIDENTSAWB"),
    ("Resident Saw II",         "SIDEQUEST_RESIDENTSAW"),
    ("Sunset Flip Powerbomb",   "SIDEQUEST_SUNSET_FLIP_POWERBOMB"),
    ("Balloon Mountain",        "GRID_BALLOONLAIR"),
    ("Climbing Gym",            "SIDEQUEST_BARREL_CLIMB"),
    ("Fisherman Suplex",        "SIDEQUEST_FISHERMAN_SUPLEX"),
    ("STF",                     "SIDEQUEST_STF"),
    ("Arena",                   "SIDEQUEST_ARENASIXNINE"),
    ("Attitude Adjustment",     "SIDEQUEST_ATTITUDE_ADJUSTMENT"),
    ("Rocket",                  "SIDEQUEST_ROCKETGODZ"),
    # Green ??? Memory sidequests
    ("??? (Memory 1)",          "SIDEQUEST_GREEN_MEMORY"),
    ("??? (Memory 2)",          "SIDEQUEST_GREEN_MEMORY_2"),
    ("??? (Memory 3)",          "SIDEQUEST_GREEN_MEMORY_3"),
    ("??? (Memory 4)",          "SIDEQUEST_GREEN_MEMORY_4"),
]

# Build a lowercase lookup for fuzzy matching
LEVEL_LOOKUP = {display.lower(): (display, internal) for display, internal in LEVELS}

# ── Load DLL ───────────────────────────────────────────────────────────────
os.add_dll_directory(STEAM_PATH)
os.add_dll_directory(os.path.dirname(GAME_DLL_PATH))

steam = ctypes.CDLL(GAME_DLL_PATH)
steam.SteamAPI_Init.restype = ctypes.c_bool
if not steam.SteamAPI_Init():
    print("✗ SteamAPI_Init failed — is Steam running and logged in?")
    exit(1)

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

def find_leaderboard(internal_name):
    call = steam.SteamAPI_ISteamUserStats_FindLeaderboard(user_stats, internal_name.encode())
    result = LeaderboardFindResult()
    if wait_for_call(call, result, LEADERBOARD_FIND_CALLBACK):
        if result.leaderboard_found:
            return result.leaderboard_handle
    return None

def fetch_entries(lb_handle, count):
    entries = []
    start = 1
    while start <= count:
        end = min(start + BATCH_SIZE - 1, count)
        call = steam.SteamAPI_ISteamUserStats_DownloadLeaderboardEntries(
            user_stats, lb_handle, 0, start, end
        )
        result = LeaderboardScoresDownloaded()
        if not wait_for_call(call, result, LEADERBOARD_SCORES_CALLBACK):
            break
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
                    "score_ms": entry.score,
                    "time":     f"{entry.score / 1000:.3f}",
                })
        start = end + 1
        time.sleep(0.05)
    return entries

def match_level(query):
    """Try exact match first, then partial match, then show numbered list."""
    q = query.strip().lower()

    # Exact match
    if q in LEVEL_LOOKUP:
        return [LEVEL_LOOKUP[q]]

    # Partial match — find all levels containing the query string
    matches = [(d, i) for d, i in LEVELS if q in d.lower()]
    return matches

def print_results(entries, display_name):
    print(f"\n{'─'*55}")
    print(f"  {display_name} — Top {len(entries)} Global Times")
    print(f"{'─'*55}")
    print(f"  {'Rank':<8} {'Time':>10}  {'Player'}")
    print(f"{'─'*55}")
    for e in entries:
        print(f"  #{e['rank']:<7} {e['time']:>10}s  {e['name']}")
    print(f"{'─'*55}\n")

def save_csv(entries, display_name):
    safe_name = display_name.replace(" ", "_").replace("'", "").replace("?", "MEMORY")
    filename = f"{safe_name}_top{len(entries)}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "steam_id", "name", "score_ms", "time"])
        writer.writeheader()
        writer.writerows(entries)
    print(f"  Saved to C:\\SteamScraper\\{filename}\n")

# ── Main loop ──────────────────────────────────────────────────────────────
print("=" * 55)
print("  Neon White — Global Leaderboard Search")
print("=" * 55)
print("  Steam initialized. Type a level name to search.")
print("  Type 'list' to see all levels. Type 'quit' to exit.")
print("=" * 55)

while True:

    # ── Step 1: Level selection ────────────────────────────────────────────
    print()
    query = input("  Level name: ").strip()

    if query.lower() == "quit":
        break

    if query.lower() == "list":
        print()
        for idx, (display, _) in enumerate(LEVELS, 1):
            print(f"  {idx:>3}. {display}")
        continue

    matches = match_level(query)

    if not matches:
        print(f"\n  No levels found matching '{query}'. Try 'list' to see all levels.")
        continue

    if len(matches) == 1:
        display_name, internal_name = matches[0]
        print(f"\n  Matched: {display_name}")
    else:
        print(f"\n  Multiple matches for '{query}':")
        for idx, (d, _) in enumerate(matches, 1):
            print(f"    {idx}. {d}")
        while True:
            pick = input("\n  Enter number to select: ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(matches):
                display_name, internal_name = matches[int(pick) - 1]
                break
            print("  Invalid selection, try again.")

    # ── Step 2: Entry count ────────────────────────────────────────────────
    lb_handle = find_leaderboard(internal_name)
    if not lb_handle:
        print(f"\n  Could not find leaderboard for {display_name}.")
        continue

    total = steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(user_stats, lb_handle)
    print(f"  Total entries on leaderboard: {total:,}")

    while True:
        count_input = input(f"  How many entries to fetch? (1–{min(total, 10000)}): ").strip()
        if count_input.isdigit() and 1 <= int(count_input) <= min(total, 10000):
            fetch_count = int(count_input)
            break
        print(f"  Please enter a number between 1 and {min(total, 10000)}.")

    # ── Step 3: Output format ──────────────────────────────────────────────
    print()
    print("  Output options:")
    print("    1. Print to console")
    print("    2. Save to CSV")
    print("    3. Both")
    while True:
        out = input("  Select option (1/2/3): ").strip()
        if out in ("1", "2", "3"):
            break
        print("  Please enter 1, 2, or 3.")

    # ── Step 4: Fetch ──────────────────────────────────────────────────────
    print(f"\n  Fetching top {fetch_count} entries for {display_name}...")
    entries = fetch_entries(lb_handle, fetch_count)

    if not entries:
        print("  No entries returned.")
        continue

    if out in ("1", "3"):
        print_results(entries, display_name)

    if out in ("2", "3"):
        save_csv(entries, display_name)

    # ── Step 5: Loop prompt ────────────────────────────────────────────────
    again = input("  Search another level? (y/n): ").strip().lower()
    if again != "y":
        break

print("\n  Goodbye!")
steam.SteamAPI_Shutdown()
