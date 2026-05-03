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
    ("Overlook",                "SA L VAGE2"),
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
    ("??? (Memory 1)",          "SIDEQUEST_GREEN_MEMORY"),
    ("??? (Memory 2)",          "SIDEQUEST_GREEN_MEMORY_2"),
    ("??? (Memory 3)",          "SIDEQUEST_GREEN_MEMORY_3"),
    ("??? (Memory 4)",          "SIDEQUEST_GREEN_MEMORY_4"),
]

LEVEL_LOOKUP = {d.lower(): (d, i) for d, i in LEVELS}

# ── Chapter map ────────────────────────────────────────────────────────────
CHAPTERS = {
    "1 - Rebirth": [
        "Movement", "Pummel", "Gunner", "Cascade", "Elevate",
        "Bounce", "Purify", "Climb", "Fasttrack", "Glass Port",
    ],
    "2 - Killer Inside": [
        "Take Flight", "Godspeed", "Dasher", "Thrasher", "Outstretched",
        "Smackdown", "Catwalk", "Fastlane", "Distinguish", "Dancer",
    ],
    "3 - Only Shallow": [
        "Guardian", "Stomp", "Jumper", "Dash Tower", "Descent",
        "Driller", "Canals", "Sprint", "Mountain", "Superkinetic",
    ],
    "4 - The Old City": [
        "Arrival", "Forgotten City", "The Clocktower",
    ],
    "5 - The Burn That Cures": [
        "Fireball", "Ringer", "Cleaner", "Warehouse", "Boom",
        "Streets", "Steps", "Demolition", "Arcs", "Apartment",
    ],
    "6 - Covenant": [
        "Hanging Gardens", "Tangled", "Waterworks", "Killswitch", "Falling",
        "Shocker", "Bouquet", "Prepare", "Triptrack", "Race",
    ],
    "7 - Reckoning": [
        "Bubble", "Shield", "Overlook", "Pop", "Minefield",
        "Mimic", "Trigger", "Greenhouse", "Sweep", "Fuse",
    ],
    "8 - Benediction": [
        "Heaven's Edge", "Zipline", "Swing", "Chute", "Crash",
        "Ascent", "Straightaway", "Firecracker", "Streak", "Mirror",
    ],
    "9 - Apocrypha": [
        "Escalation", "Bolt", "Godstreak", "Plunge", "Mayhem",
        "Barrage", "Estate", "Trapwire", "Ricochet", "Fortress",
    ],
    "10 - The Third Temple": [
        "Holy Ground", "The Third Temple",
    ],
    "11 - Thousand Pound Butterfly": [
        "Spree", "Breakthrough", "Glide", "Closer", "Hike",
        "Switch", "Access", "Congregation", "Sequence", "Marathon",
    ],
    "12 - Hand of God": [
        "Sacrifice", "Absolution",
    ],
    "Sidequests - Red": [
        "Elevate Traversal I", "Elevate Traversal II", "Purify Traversal",
        "Godspeed Traversal", "Stomp Traversal", "Fireball Traversal",
        "Dominion Traversal", "Book of Life Traversal",
    ],
    "Sidequests - Violet": [
        "Doghouse", "Choker", "Chain", "Hellevator", "Razor",
        "All Seeing Eye", "Resident Saw I", "Resident Saw II",
    ],
    "Sidequests - Yellow": [
        "Sunset Flip Powerbomb", "Balloon Mountain", "Climbing Gym",
        "Fisherman Suplex", "STF", "Arena", "Attitude Adjustment", "Rocket",
    ],
}

CHAPTER_NAMES = list(CHAPTERS.keys())

# All 121 levels excluding the 4 ??? Green Memory sidequests
WHOLE_GAME_LEVELS = [
    (d, i) for d, i in LEVELS if not d.startswith("???")
]

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

LEADERBOARD_FIND_CALLBACK         = 1104
LEADERBOARD_SCORES_CALLBACK       = 1105
K_LEADERBOARD_DATA_REQUEST_USERS  = 2  # DownloadLeaderboardEntriesForUsers

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
steam.SteamAPI_ISteamUserStats_FindLeaderboard.argtypes = [
    ctypes.c_void_p, ctypes.c_char_p
]
steam.SteamAPI_ISteamUserStats_DownloadLeaderboardEntriesForUsers.restype = ctypes.c_uint64
steam.SteamAPI_ISteamUserStats_DownloadLeaderboardEntriesForUsers.argtypes = [
    ctypes.c_void_p, ctypes.c_uint64,
    ctypes.POINTER(ctypes.c_uint64), ctypes.c_int
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
    call = steam.SteamAPI_ISteamUserStats_FindLeaderboard(
        user_stats, internal_name.encode()
    )
    result = LeaderboardFindResult()
    if wait_for_call(call, result, LEADERBOARD_FIND_CALLBACK):
        if result.leaderboard_found:
            return result.leaderboard_handle
    return None

def get_player_entry(lb_handle, steam_id):
    """Fetch a specific player's entry using DownloadLeaderboardEntriesForUsers."""
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
    if ok and entry.steam_id_user == steam_id:
        return entry
    return None

def lookup_level(display_name):
    """Return (display_name, internal_name) for a given display name."""
    return LEVEL_LOOKUP.get(display_name.lower())

def match_level_input(query):
    """Fuzzy match typed input against level display names."""
    q = query.strip().lower()
    if q in LEVEL_LOOKUP:
        return [LEVEL_LOOKUP[q]]
    return [(d, i) for d, i in LEVELS if q in d.lower()]

def get_player_name(steam_id):
    name_bytes = steam.SteamAPI_ISteamFriends_GetFriendPersonaName(friends, steam_id)
    return name_bytes.decode('utf-8', errors='replace') if name_bytes else str(steam_id)

def format_result_row(display_name, rank, score_ms, total_entries):
    time_str = f"{score_ms / 1000:.3f}s"
    return {
        "level":    display_name,
        "rank":     rank,
        "time":     time_str,
        "score_ms": score_ms,
        "total":    total_entries,
    }

def print_results(rows, player_name, context_label):
    print(f"\n{'─'*55}")
    print(f"  Player: {player_name}  |  {context_label}")
    print(f"{'─'*55}")
    print(f"  {'Level':<28} {'Rank':>7}  {'Time':>10}")
    print(f"{'─'*55}")
    for r in rows:
        print(f"  {r['level']:<28} #{r['rank']:<6}  {r['time']:>10}")
    print(f"{'─'*55}\n")

def save_csv(rows, player_name, context_label):
    safe_player = player_name.replace(" ", "_").replace("/", "_")
    safe_context = context_label.replace(" ", "_").replace("/", "_").replace("-", "")
    filename = f"{safe_player}_{safe_context}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["level", "rank", "time", "score_ms", "total"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved to C:\\SteamScraper\\{filename}\n")

def prompt_output():
    print()
    print("  Output options:")
    print("    1. Print to console")
    print("    2. Save to CSV")
    print("    3. Both")
    while True:
        out = input("  Select option (1/2/3): ").strip()
        if out in ("1", "2", "3"):
            return out
        print("  Please enter 1, 2, or 3.")

# ── Main loop ──────────────────────────────────────────────────────────────
print("=" * 65)
print("  Neon White — Player Leaderboard Lookup")
print("=" * 65)
print("  Steam initialized.")
print("=" * 65)

while True:
    print()

    # ── Steam ID input ─────────────────────────────────────────────────────
    steam_id_input = input("  Enter Steam ID (17-digit number) or 'quit': ").strip()
    if steam_id_input.lower() == "quit":
        break
    if not steam_id_input.isdigit() or len(steam_id_input) != 17:
        print("  Invalid Steam ID — must be a 17-digit number.")
        print("  Tip: find it in the URL of a Steam profile page.")
        continue

    steam_id = int(steam_id_input)
    player_name = get_player_name(steam_id)
    print(f"\n  Player: {player_name} ({steam_id})")

    # ── Search mode ────────────────────────────────────────────────────────
    print()
    print("  Search mode:")
    print("    1. Single level")
    print("    2. Chapter / Sidequest group")
    print("    3. Whole game (all 121 levels)")
    while True:
        mode = input("  Select mode (1/2/3): ").strip()
        if mode in ("1", "2", "3"):
            break
        print("  Please enter 1, 2, or 3.")

    rows = []
    context_label = ""

    # ── Single level ───────────────────────────────────────────────────────
    if mode == "1":
        print()
        print("  Type a level name, or 'list' to see all levels.")
        while True:
            query = input("  Level name: ").strip()
            if query.lower() == "list":
                print()
                for idx, (d, _) in enumerate(LEVELS, 1):
                    print(f"    {idx:>3}. {d}")
                print()
                continue

            matches = match_level_input(query)
            if not matches:
                print(f"  No levels found matching '{query}'. Try again or type 'list'.")
                continue

            if len(matches) == 1:
                display_name, internal_name = matches[0]
                print(f"  Matched: {display_name}")
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
            break

        context_label = display_name
        print(f"\n  Looking up {player_name} on {display_name}...", end=" ", flush=True)

        lb_handle = find_leaderboard(internal_name)
        if not lb_handle:
            print("leaderboard not found.")
        else:
            total = steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(
                user_stats, lb_handle
            )
            entry = get_player_entry(lb_handle, steam_id)
            if entry:
                rows.append(format_result_row(display_name, entry.global_rank, entry.score, total))
                print("found.")
            else:
                print("no entry found for this player.")

    # ── Chapter search ─────────────────────────────────────────────────────
    elif mode == "2":
        print()
        print("  Select a chapter:")
        for idx, name in enumerate(CHAPTER_NAMES, 1):
            print(f"    {idx:>2}. {name}")
        while True:
            pick = input("\n  Enter number: ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(CHAPTER_NAMES):
                chapter_name = CHAPTER_NAMES[int(pick) - 1]
                break
            print(f"  Please enter a number between 1 and {len(CHAPTER_NAMES)}.")

        context_label = chapter_name
        level_names = CHAPTERS[chapter_name]
        print(f"\n  Looking up {player_name} across {chapter_name} ({len(level_names)} levels)...\n")

        for display_name in level_names:
            match = lookup_level(display_name)
            if not match:
                continue
            _, internal_name = match
            print(f"    {display_name}...", end=" ", flush=True)

            lb_handle = find_leaderboard(internal_name)
            if not lb_handle:
                print("leaderboard not found.")
                continue

            total = steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(
                user_stats, lb_handle
            )
            entry = get_player_entry(lb_handle, steam_id)
            if entry:
                rows.append(format_result_row(display_name, entry.global_rank, entry.score, total))
                print(f"rank #{entry.global_rank}")
            else:
                print("no entry.")

    # ── Whole game ─────────────────────────────────────────────────────────
    elif mode == "3":
        context_label = "Whole Game"
        print(f"\n  Looking up {player_name} across all 121 levels...\n")

        for display_name, internal_name in WHOLE_GAME_LEVELS:
            print(f"    {display_name}...", end=" ", flush=True)

            lb_handle = find_leaderboard(internal_name)
            if not lb_handle:
                print("leaderboard not found.")
                continue

            total = steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(
                user_stats, lb_handle
            )
            entry = get_player_entry(lb_handle, steam_id)
            if entry:
                rows.append(format_result_row(display_name, entry.global_rank, entry.score, total))
                print(f"rank #{entry.global_rank}")
            else:
                print("no entry.")

    # ── Output ─────────────────────────────────────────────────────────────
    if not rows:
        print(f"\n  No results found for {player_name}.")
    else:
        out = prompt_output()
        if out in ("1", "3"):
            print_results(rows, player_name, context_label)
        if out in ("2", "3"):
            save_csv(rows, player_name, context_label)

    # ── Loop ───────────────────────────────────────────────────────────────
    again = input("  Search another player or level? (y/n): ").strip().lower()
    if again != "y":
        break

print("\n  Goodbye!")
steam.SteamAPI_Shutdown()
