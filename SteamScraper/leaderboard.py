import ctypes
import os
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

STEAM_PATH = r"C:\Program Files (x86)\Steam"
GAME_DLL_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll"

os.add_dll_directory(STEAM_PATH)
os.add_dll_directory(os.path.dirname(GAME_DLL_PATH))

if not os.path.exists("steam_appid.txt"):
    with open("steam_appid.txt", "w") as f:
        f.write("1533420")

steam = ctypes.CDLL(GAME_DLL_PATH)
print("✓ steam_api64.dll loaded")

steam.SteamAPI_Init.restype = ctypes.c_bool
if not steam.SteamAPI_Init():
    print("✗ SteamAPI_Init failed")
    exit(1)
print("✓ Steam initialized")

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
print("✓ Got ISteamUserStats")

steam.SteamAPI_ISteamUserStats_RequestCurrentStats.restype = ctypes.c_bool
steam.SteamAPI_ISteamUserStats_RequestCurrentStats.argtypes = [ctypes.c_void_p]
steam.SteamAPI_ISteamUserStats_RequestCurrentStats(user_stats)
steam.SteamAPI_RunCallbacks()
time.sleep(1)

# ── Async call result polling ──────────────────────────────────────────────
steam.SteamAPI_ISteamUtils_IsAPICallCompleted.restype = ctypes.c_bool
steam.SteamAPI_ISteamUtils_IsAPICallCompleted.argtypes = [
    ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_bool)
]
steam.SteamAPI_ISteamUtils_GetAPICallResult.restype = ctypes.c_bool
steam.SteamAPI_ISteamUtils_GetAPICallResult.argtypes = [
    ctypes.c_void_p, ctypes.c_uint64, ctypes.c_void_p,
    ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)
]

# Get ISteamUtils
steam.SteamAPI_ISteamClient_GetISteamUtils.restype = ctypes.c_void_p
steam.SteamAPI_ISteamClient_GetISteamUtils.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p
]
utils = steam.SteamAPI_ISteamClient_GetISteamUtils(
    client, h_pipe, b"SteamUtils010"
) or steam.SteamAPI_ISteamClient_GetISteamUtils(
    client, h_pipe, b"SteamUtils009"
)
print("✓ Got ISteamUtils")

steam.SteamAPI_ISteamUserStats_FindLeaderboard.restype = ctypes.c_uint64
steam.SteamAPI_ISteamUserStats_FindLeaderboard.argtypes = [
    ctypes.c_void_p, ctypes.c_char_p
]
steam.SteamAPI_ISteamUserStats_GetLeaderboardName.restype = ctypes.c_char_p
steam.SteamAPI_ISteamUserStats_GetLeaderboardName.argtypes = [
    ctypes.c_void_p, ctypes.c_uint64
]

# LeaderboardFindResult_t struct: uint64 leaderboard handle + uint8 found
class LeaderboardFindResult(ctypes.Structure):
    _fields_ = [
        ("leaderboard_handle", ctypes.c_uint64),
        ("leaderboard_found",  ctypes.c_uint8),
    ]

# k_iCallback for LeaderboardFindResult_t = 1100 + 4 = 1104
LEADERBOARD_FIND_RESULT_CALLBACK = 1104

def find_leaderboard(name):
    call_handle = steam.SteamAPI_ISteamUserStats_FindLeaderboard(
        user_stats, name.encode('utf-8')
    )
    if not call_handle:
        return None

    # Poll until the async call completes
    failed = ctypes.c_bool(False)
    for _ in range(20):  # up to 2 seconds
        steam.SteamAPI_RunCallbacks()
        time.sleep(0.1)
        completed = steam.SteamAPI_ISteamUtils_IsAPICallCompleted(
            utils, call_handle, ctypes.byref(failed)
        )
        if completed:
            break

    if failed.value:
        return None

    result = LeaderboardFindResult()
    io_failed = ctypes.c_bool(False)
    success = steam.SteamAPI_ISteamUtils_GetAPICallResult(
        utils,
        call_handle,
        ctypes.byref(result),
        ctypes.sizeof(result),
        LEADERBOARD_FIND_RESULT_CALLBACK,
        ctypes.byref(io_failed)
    )

    if success and result.leaderboard_found and result.leaderboard_handle:
        name_back = steam.SteamAPI_ISteamUserStats_GetLeaderboardName(
            user_stats, result.leaderboard_handle
        )
        return result.leaderboard_handle, name_back
    return None

candidates = [
    # Main missions
    "TUT_MOVEMENT", "TUT_SHOOTINGRANGE", "SLUGGER", "TUT_FROG", "TUT_JUMP",
    "GRID_TUT_BALLOON", "TUT_BOMB2", "TUT_BOMBJUMP", "TUT_FASTTRACK", "GRID_PORT",
    "GRID_PAGODA", "TUT_RIFLE", "TUT_RIFLEJOCK", "TUT_DASHENEMY", "GRID_JUMPDASH",
    "GRID_SMACKDOWN", "GRID_MEATY_BALLOONS", "GRID_FAST_BALLOON", "GRID_DRAGON2", "GRID_DASHDANCE",
    "TUT_GUARDIAN", "TUT_UZI", "TUT_JUMPER", "TUT_BOMB", "GRID_DESCEND",
    "GRID_STAMPEROUT", "GRID_CRUISE", "GRID_SPRINT", "GRID_MOUNTAIN", "GRID_SUPERKINETIC",
    "GRID_ARRIVAL", "FLOATING", "GRID_BOSS_YELLOW",
    "GRID_HOPHOP", "GRID_RINGER_TUTORIAL", "GRID_RINGER_EXPLORATION", "GRID_HOPSCOTCH", "GRID_BOOM",
    "GRID_SNAKE_IN_MY_BOOT", "GRID_FLOCK", "GRID_BOMBS_AHOY", "GRID_ARCS", "GRID_APARTMENT",
    "TUT_TRIPWIRE", "GRID_TANGLED", "GRID_HUNT", "GRID_CANNONS", "GRID_FALLING",
    "TUT_SHOCKER2", "TUT_SHOCKER", "GRID_PREPARE", "GRID_TRIPMAZE", "GRID_RACE",
    "TUT_FORCEFIELD2", "GRID_SHIELD", "SA L VAGE2", "GRID_VERTICAL", "GRID_MINEFIELD",
    "TUT_MIMIC", "GRID_MIMICPOP", "GRID_SWARM", "GRID_SWITCH", "GRID_TRAPS2",
    "TUT_ROCKETJUMP", "TUT_ZIPLINE", "GRID_CLIMBANG", "GRID_ROCKETUZI", "GRID_CRASHLAND",
    "GRID_ESCALATE", "GRID_SPIDERCLAUS", "GRID_FIRECRACKER_2", "GRID_SPIDERMAN", "GRID_DESTRUCTION",
    "GRID_HEAT", "GRID_BOLT", "GRID_PON", "GRID_CHARGE", "GRID_MIMICFINALE",
    "GRID_BARRAGE", "GRID_1GUN", "GRID_HECK", "GRID_ANTFARM", "GRID_FORTRESS",
    "GRID_GODTEMPLE_ENTRY", "GRID_BOSS_GODSDEATHTEMPLE",
    "GRID_EXTERMINATOR", "GRID_FEVER", "GRID_SKIPSLIDE", "GRID_CLOSER", "GRID_HIKE",
    "GRID_SKIP", "GRID_CEILING", "GRID_BOOP", "GRID_TRIPRAP", "GRID_ZIPRAP",
    "TUT_ORIGIN", "GRID_BOSS_RAPTURE",
    # Sidequests
    "SIDEQUEST_OBSTACLE_PISTOL", "SIDEQUEST_OBSTACLE_PISTOL_SHOOT",
    "SIDEQUEST_OBSTACLE_MACHINEGUN", "SIDEQUEST_OBSTACLE_RIFLE_2",
    "SIDEQUEST_OBSTACLE_UZI2", "SIDEQUEST_OBSTACLE_SHOTGUN",
    "SIDEQUEST_OBSTACLE_ROCKETLAUNCHER", "SIDEQUEST_RAPTURE_QUEST",
    "SIDEQUEST_DODGER", "GRID_GLASSPATH", "GRID_GLASSPATH2",
    "GRID_HELLEVATOR", "GRID_GLASSPATH3", "SIDEQUEST_ALL_SEEING_EYE",
    "SIDEQUEST_RESIDENTSAWB", "SIDEQUEST_RESIDENTSAW",
    "SIDEQUEST_SUNSET_FLIP_POWERBOMB", "SIDEQUEST_BALLOONLAIR",
    "SIDEQUEST_BARREL_CLIMB", "SIDEQUEST_FISHERMAN_SUPLEX",
    "SIDEQUEST_STF", "SIDEQUEST_AREASIXNINE", "SIDEQUEST_ATTITUDE_ADJUSTMENT",
    "SIDEQUEST_ROCKETGODZ", "SIDEQUEST_GREEN_MEMORY", "SIDEQUEST_GREEN_MEMORY_2",
    "SIDEQUEST_GREEN_MEMORY_3", "SIDEQUEST_GREEN_MEMORY_4",
]

print("\nSearching for leaderboards...\n")
for name in candidates:
    result = find_leaderboard(name)
    if result:
        handle, lb_name = result
        print(f"  ✓ FOUND: '{name}' → handle: {handle}, name: {lb_name}")
    else:
        print(f"  ✗ Not found: '{name}'")

steam.SteamAPI_Shutdown()
print("\nDone.")