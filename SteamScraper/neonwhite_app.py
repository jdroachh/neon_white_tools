import ctypes
import os
import time
import csv
import json
import threading
import multiprocessing
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from urllib.request import urlopen

# Seed-search modules — kept slim so multiprocessing workers re-import only
# these files (not all 2991 lines of this module + tkinter) on spawn.
from shuffle_lib import _load_c_shuffle, full_shuffle
from seed_search import _seed_search_worker, _expected_match_count

from logger import get_logger
logger = get_logger(__name__)

# Google Sheets imports — gracefully optional until credentials.json is present
SHEETS_AVAILABLE = False
try:
    import importlib
    # Force-resolve namespace packages before importing
    import google
    import google.auth
    import google.oauth2
    import google.oauth2.credentials
    import google.auth.transport.requests
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    SHEETS_AVAILABLE = True
except Exception:
    SHEETS_AVAILABLE = False
    logger.info("Google Sheets libraries not available; Sheets push will be disabled",
                exc_info=True)

SHEETS_SCOPE      = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE  = "credentials.json"
TOKEN_FILE        = "token.json"

# ── Constants ──────────────────────────────────────────────────────────────
APP_ID       = "1533420"
BATCH_SIZE   = 100
CONFIG_FILE  = "neonwhite_config.json"
APP_TITLE    = "Neon White Leaderboard Tool"
VERSION      = "1.10.5"

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

CHEATER_LIST_URL = "https://raw.githubusercontent.com/Faustas156/NeonLite/main/Resources/cheaterlist.json"

# ── Steam API globals ──────────────────────────────────────────────────────
steam        = None
user_stats   = None
utils_iface  = None
friends      = None
steam_ready  = False
player_name  = "Not connected"
logged_in_steam_id = 0
cheater_ids  = set()  # populated on startup

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

# ── Rush Tools data ────────────────────────────────────────────────────────
RUSH_LEVELS = {
    "96":     ["Movement","Pummel","Gunner","Cascade","Elevate","Bounce","Purify","Climb",
               "Fasttrack","Glass Port","Take Flight","Godspeed","Dasher","Thrasher",
               "Outstretched","Smackdown","Catwalk","Fastlane","Distinguish","Dancer",
               "Guardian","Stomp","Jumper","Dash Tower","Descent","Driller","Canals",
               "Sprint","Mountain","Superkinetic","Arrival","Forgotten City","The Clocktower",
               "Fireball","Ringer","Cleaner","Warehouse","Boom","Streets","Steps","Demolition",
               "Arcs","Apartment","Hanging Gardens","Tangled","Waterworks","Killswitch","Falling",
               "Shocker","Bouquet","Prepare","Triptrack","Race","Bubble","Shield","Overlook",
               "Pop","Minefield","Mimic","Trigger","Greenhouse","Sweep","Fuse","Heaven's Edge",
               "Zipline","Swing","Chute","Crash","Ascent","Straightaway","Firecracker","Streak",
               "Mirror","Escalation","Bolt","Godstreak","Plunge","Mayhem","Barrage","Estate",
               "Trapwire","Ricochet","Fortress","Holy Ground","The Third Temple","Spree",
               "Breakthrough","Glide","Closer","Hike","Switch","Access","Congregation",
               "Sequence","Marathon","Absolution"],
    "violet": ["Doghouse","Choker","Chain","Hellevator","Razor","All Seeing Eye",
               "Resident Saw I","Resident Saw II"],
    "red":    ["Elevate Traversal I","Elevate Traversal II","Purify Traversal","Godspeed Traversal",
               "Stomp Traversal","Fireball Traversal","Dominion Traversal","Book of Life Traversal"],
    "yellow": ["Sunset Flip Powerbomb","Balloon Mountain","Climbing Gym","Fisherman Suplex",
               "STF","Arena","Attitude Adjustment","Rocket"],
}

RUSH_ALIASES = {
    "glort": "glass port", "ttt": "the third temple", "ct": "the clocktower",
    "clocktower": "the clocktower", "sfp": "sunset flip powerbomb",
    "bm": "balloon mountain", "cg": "climbing gym",
    "fish sup": "fisherman suplex", "fish soup": "fisherman suplex",
    "eti": "elevate traversal i", "et1": "elevate traversal i",
    "etii": "elevate traversal ii", "et2": "elevate traversal ii",
    "boof trav": "book of life traversal", "ase": "all seeing eye",
    "rsi": "resident saw i", "rs1": "resident saw i",
    "rsii": "resident saw ii", "rs2": "resident saw ii",
}

# Standard medal data — [bronze_us, silver_us, gold_us, ace_us, dev_us]
STANDARD_MEDAL_DATA = {
    "TUT_MOVEMENT":[900000000,38000000,31000000,24000000,18930000],
    "TUT_SHOOTINGRANGE":[900000000,22500000,17500000,13000000,8329000],
    "SLUGGER":[900000000,26000000,19500000,14000000,9479000],
    "TUT_FROG":[900000000,28000000,20500000,15500000,10210000],
    "TUT_JUMP":[900000000,27000000,23000000,21000000,16420000],
    "GRID_TUT_BALLOON":[900000000,40000000,35000000,30000000,19059000],
    "TUT_BOMB2":[900000000,21000000,16500000,13500000,10449000],
    "TUT_BOMBJUMP":[900000000,38000000,31000000,27000000,12750000],
    "TUT_FASTTRACK":[900000000,38000000,33000000,30000000,25440000],
    "GRID_PORT":[900000000,64000000,54500000,37000000,25319000],
    "GRID_PAGODA":[900000000,32500000,28500000,23000000,17540000],
    "TUT_RIFLE":[900000000,18000000,13000000,11000000,6139000],
    "TUT_RIFLEJOCK":[900000000,25000000,19500000,15000000,10210000],
    "TUT_DASHENEMY":[900000000,27000000,22000000,18000000,12420000],
    "GRID_JUMPDASH":[900000000,23000000,16000000,12500000,10350000],
    "GRID_SMACKDOWN":[900000000,27000000,22500000,14000000,10819000],
    "GRID_MEATY_BALLOONS":[900000000,22500000,19500000,16500000,14229000],
    "GRID_FAST_BALLOON":[900000000,34000000,30000000,26000000,22450000],
    "GRID_DRAGON2":[900000000,32500000,29500000,21500000,15890000],
    "GRID_DASHDANCE":[900000000,29000000,25000000,22000000,17069000],
    "TUT_GUARDIAN":[900000000,40000000,35000000,28500000,22649000],
    "TUT_UZI":[900000000,32000000,27500000,19500000,15340000],
    "TUT_JUMPER":[900000000,31000000,27000000,24000000,19159000],
    "TUT_BOMB":[900000000,28000000,24000000,20500000,14729000],
    "GRID_DESCEND":[900000000,23000000,20000000,16000000,11399000],
    "GRID_STAMPEROUT":[900000000,23000000,19500000,16500000,12619000],
    "GRID_CRUISE":[900000000,55000000,48000000,40000000,30079000],
    "GRID_SPRINT":[900000000,33000000,29000000,25000000,19639000],
    "GRID_MOUNTAIN":[900000000,34000000,28000000,25000000,19809000],
    "GRID_SUPERKINETIC":[900000000,38000000,31000000,24000000,20100000],
    "GRID_ARRIVAL":[900000000,37000000,32500000,26000000,22959000],
    "FLOATING":[900000000,46000000,41000000,37500000,33020000],
    "GRID_BOSS_YELLOW":[900000000,130000000,120000000,97000000,53680000],
    "GRID_HOPHOP":[900000000,31000000,27000000,24000000,19120000],
    "GRID_RINGER_TUTORIAL":[900000000,27000000,23500000,20500000,16600000],
    "GRID_RINGER_EXPLORATION":[900000000,35500000,31000000,28000000,14319000],
    "GRID_HOPSCOTCH":[900000000,27000000,22000000,17000000,13989000],
    "GRID_BOOM":[900000000,35000000,30000000,24500000,18450000],
    "GRID_SNAKE_IN_MY_BOOT":[900000000,24000000,18000000,15000000,9609000],
    "GRID_FLOCK":[900000000,26000000,22000000,19000000,15159000],
    "GRID_BOMBS_AHOY":[900000000,26000000,23000000,16500000,9739000],
    "GRID_ARCS":[900000000,37000000,29000000,25500000,18620000],
    "GRID_APARTMENT":[900000000,46000000,40000000,35000000,23799000],
    "TUT_TRIPWIRE":[900000000,50000000,45500000,39500000,24790000],
    "GRID_TANGLED":[900000000,36000000,31500000,21500000,13989000],
    "GRID_HUNT":[900000000,33000000,28500000,25000000,21979000],
    "GRID_CANNONS":[900000000,40000000,36500000,32500000,27649000],
    "GRID_FALLING":[900000000,38000000,32000000,28000000,22489000],
    "TUT_SHOCKER2":[900000000,49500000,46000000,37000000,28750000],
    "TUT_SHOCKER":[900000000,49000000,45500000,33500000,27760000],
    "GRID_PREPARE":[900000000,48000000,42000000,34500000,30090000],
    "GRID_TRIPMAZE":[900000000,59000000,53000000,44000000,35979000],
    "GRID_RACE":[900000000,34000000,32000000,28500000,26139000],
    "TUT_FORCEFIELD2":[900000000,36000000,32500000,26500000,19430000],
    "GRID_SHIELD":[900000000,38000000,31000000,26500000,18739000],
    "SA L VAGE2":[900000000,29000000,25000000,19500000,15449000],
    "GRID_VERTICAL":[900000000,48000000,45000000,41000000,26030000],
    "GRID_MINEFIELD":[900000000,30000000,24500000,22000000,17559000],
    "TUT_MIMIC":[900000000,25000000,20500000,14500000,10700000],
    "GRID_MIMICPOP":[900000000,42000000,37500000,31500000,24389000],
    "GRID_SWARM":[900000000,20000000,16000000,13000000,8329000],
    "GRID_SWITCH":[900000000,36000000,28000000,22000000,14819000],
    "GRID_TRAPS2":[900000000,52000000,44000000,37500000,28190000],
    "TUT_ROCKETJUMP":[900000000,21000000,16500000,12000000,8939000],
    "TUT_ZIPLINE":[900000000,21000000,17000000,14000000,10399000],
    "GRID_CLIMBANG":[900000000,35000000,30000000,22000000,14939000],
    "GRID_ROCKETUZI":[900000000,65000000,55000000,46000000,34849000],
    "GRID_CRASHLAND":[900000000,52000000,44000000,36500000,25159000],
    "GRID_ESCALATE":[900000000,46000000,38000000,31000000,21909000],
    "GRID_SPIDERCLAUS":[900000000,76000000,65000000,54000000,39119000],
    "GRID_FIRECRACKER_2":[900000000,62000000,51000000,42000000,30409000],
    "GRID_SPIDERMAN":[900000000,45000000,36000000,27000000,19779000],
    "GRID_DESTRUCTION":[900000000,52000000,43000000,37000000,25479000],
    "GRID_HEAT":[900000000,52000000,41000000,32000000,21879000],
    "GRID_BOLT":[900000000,62000000,50000000,39000000,25439000],
    "GRID_PON":[900000000,60000000,50000000,40000000,27489000],
    "GRID_CHARGE":[900000000,55000000,47000000,40000000,30499000],
    "GRID_MIMICFINALE":[900000000,36000000,30000000,23000000,14809000],
    "GRID_BARRAGE":[900000000,66000000,55000000,45000000,28359000],
    "GRID_1GUN":[900000000,73000000,61000000,49000000,32219000],
    "GRID_HECK":[900000000,41000000,35000000,30000000,21859000],
    "GRID_ANTFARM":[900000000,72000000,60000000,50000000,30199000],
    "GRID_FORTRESS":[900000000,62000000,50000000,39000000,22679000],
    "GRID_GODTEMPLE_ENTRY":[900000000,90000000,82000000,70000000,52299000],
    "GRID_BOSS_GODSDEATHTEMPLE":[900000000,145000000,130000000,111000000,54039000],
    "GRID_EXTERMINATOR":[900000000,14000000,11000000,8000000,5729000],
    "GRID_FEVER":[900000000,12000000,9000000,7000000,3909000],
    "GRID_SKIPSLIDE":[900000000,17000000,13000000,9500000,6789000],
    "GRID_CLOSER":[900000000,22000000,17500000,14000000,10099000],
    "GRID_HIKE":[900000000,14000000,11000000,8500000,5409000],
    "GRID_SKIP":[900000000,24000000,19000000,15000000,10009000],
    "GRID_CEILING":[900000000,20000000,16000000,12500000,8809000],
    "GRID_BOOP":[900000000,24000000,19500000,16000000,11589000],
    "GRID_TRIPRAP":[900000000,27000000,22000000,18000000,12829000],
    "GRID_ZIPRAP":[900000000,32000000,26000000,21500000,16809000],
    "TUT_ORIGIN":[900000000,24000000,18500000,15500000,10109000],
    "GRID_BOSS_RAPTURE":[900000000,145000000,125000000,100000000,65149000],
    "SIDEQUEST_DODGER":[900000000,300000000,180000000,65000000,52000000],
    "GRID_GLASSPATH":[900000000,300000000,180000000,30000000,26000000],
    "GRID_GLASSPATH2":[900000000,300000000,180000000,25000000,22000000],
    "GRID_HELLVATOR":[900000000,300000000,180000000,25000000,20000000],
    "GRID_GLASSPATH3":[900000000,300000000,180000000,22000000,18000000],
    "SIDEQUEST_ALL_SEEING_EYE":[900000000,300000000,180000000,40000000,32000000],
    "SIDEQUEST_RESIDENTSAWB":[900000000,300000000,180000000,28000000,22000000],
    "SIDEQUEST_RESIDENTSAW":[900000000,300000000,180000000,45000000,18000000],
    "SIDEQUEST_SUNSET_FLIP_POWERBOMB":[900000000,300000000,180000000,50000000,40000000],
    "GRID_BALLOONLAIR":[900000000,300000000,180000000,40000000,22000000],
    "SIDEQUEST_BARREL_CLIMB":[900000000,300000000,180000000,60000000,42000000],
    "SIDEQUEST_FISHERMAN_SUPLEX":[900000000,300000000,180000000,75000000,47000000],
    "SIDEQUEST_STF":[900000000,300000000,180000000,35000000,22000000],
    "SIDEQUEST_ARENASIXNINE":[900000000,300000000,180000000,60000000,30000000],
    "SIDEQUEST_ATTITUDE_ADJUSTMENT":[900000000,300000000,180000000,48000000,44000000],
    "SIDEQUEST_ROCKETGODZ":[900000000,300000000,180000000,80000000,60000000],
    "SIDEQUEST_OBSTACLE_PISTOL":[900000000,300000000,180000000,25000000,19000000],
    "SIDEQUEST_OBSTACLE_PISTOL_SHOOT":[900000000,300000000,180000000,29000000,27000000],
    "SIDEQUEST_OBSTACLE_MACHINEGUN":[900000000,300000000,180000000,40000000,35000000],
    "SIDEQUEST_OBSTACLE_RIFLE_2":[900000000,300000000,180000000,34000000,16000000],
    "SIDEQUEST_OBSTACLE_UZI2":[900000000,300000000,180000000,44000000,42000000],
    "SIDEQUEST_OBSTACLE_SHOTGUN":[900000000,300000000,180000000,44000000,40500000],
    "SIDEQUEST_OBSTACLE_ROCKETLAUNCHER":[900000000,300000000,180000000,60000000,45000000],
    "SIDEQUEST_RAPTURE_QUEST":[900000000,300000000,180000000,11549000,6549000],
}

# Community medal data — fetched live on startup, falls back to embedded
COMMUNITY_MEDAL_DATA = {}
COMMUNITY_MEDALS_URL = "https://raw.githubusercontent.com/Faustas156/NeonLite/main/Resources/communitymedals.json"

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
            logger.exception("Failed to load %s; falling back to DEFAULT_CONFIG", CONFIG_FILE)
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# ── Cheater list ───────────────────────────────────────────────────────────
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

# ── Google Sheets helpers ──────────────────────────────────────────────────
def get_sheets_service():
    """Authenticate and return a Google Sheets service object."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except Exception as e:
        raise RuntimeError(
            f"Google API libraries failed to load: {e}\n\n"
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

def format_time_mmss(score_ms):
    """Convert milliseconds to MM:SS.mmm string."""
    total_seconds = score_ms / 1000
    minutes       = int(total_seconds // 60)
    seconds       = total_seconds % 60
    return f"{minutes:02d}:{seconds:06.3f}"

# ── Steam API functions ────────────────────────────────────────────────────
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

# ── Themes ─────────────────────────────────────────────────────────────────
THEMES = {
    "light": {
        # RL-C palette
        "bg":              "#ffffff",
        "bg2":             "#f0fff0",
        "bg3":             "#0a1a0a",
        "fg":              "#0a1a0a",
        "fg2":             "#3B6D11",
        "accent":          "#00aa55",
        "border":          "#c0e8c0",
        "success":         "#3B6D11",
        "error":           "#cc2222",
        "row_alt":         "#f8fff8",
        "select":          "#d0f0d8",
        "log_bg":          "#f0fff0",
        "log_fg":          "#3B6D11",
        "btn_bg":          "#00aa55",
        "btn_active":      "#008844",
        "sidebar_sel":     "#0a1a0a",
        "input_bg":        "#f0fff0",
        "input_fg":        "#0a1a0a",
        "sidebar_bg":      "#f8fff8",
        "nav_active_fg":   "#ffffff",
        "nav_inactive_fg": "#3B6D11",
    },
    "dark": {
        # R2 palette
        "bg":              "#111118",
        "bg2":             "#0a0a0f",
        "bg3":             "#1a1a2a",
        "fg":              "#ffffff",
        "fg2":             "#7070a0",
        "accent":          "#00ff9f",
        "border":          "#1e1e2e",
        "success":         "#00ff9f",
        "error":           "#ef5350",
        "row_alt":         "#0d0d14",
        "select":          "#1a1a2a",
        "log_bg":          "#0a0a0f",
        "log_fg":          "#7070a0",
        "btn_bg":          "#00ff9f",
        "btn_active":      "#00dd88",
        "sidebar_sel":     "#1a1a2a",
        "input_bg":        "#0a0a0f",
        "input_fg":        "#c8c8d8",
        "sidebar_bg":      "#0a0a0f",
        "nav_active_fg":   "#ffffff",
        "nav_inactive_fg": "#7070a0",
    },
}

GOHU_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "GohuFont14NerdFont-Regular.ttf")
GOHU_FONT_NAME = "GohuFont 14 Nerd Font"

def load_gohu_font():
    """Register the GOHU font with Windows so Tkinter can use it."""
    if not os.path.exists(GOHU_FONT_PATH):
        return False
    try:
        FR_PRIVATE = 0x10
        result = ctypes.windll.gdi32.AddFontResourceExW(GOHU_FONT_PATH, FR_PRIVATE, 0)
        return result > 0
    except Exception:
        logger.debug("Custom font load via AddFontResourceExW failed; using fallback",
                     exc_info=True)
        return False

def gohu(size=14, bold=False, italic=False):
    """Return a Tkinter font tuple using GOHU if available, else Helvetica."""
    weight = "bold" if bold else "normal"
    if os.path.exists(GOHU_FONT_PATH):
        return (GOHU_FONT_NAME, size, weight)
    return ("Helvetica", size, weight)

def gohu_mono(size=14):
    """Monospace variant — GOHU if available, else Courier."""
    if os.path.exists(GOHU_FONT_PATH):
        return (GOHU_FONT_NAME, size, "normal")
    return ("Courier", size, "normal")

def fetch_community_medals():
    """Fetch community medal data from NeonLite GitHub on startup."""
    global COMMUNITY_MEDAL_DATA
    try:
        with urlopen(COMMUNITY_MEDALS_URL, timeout=8) as resp:
            COMMUNITY_MEDAL_DATA = json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.warning("Community medals fetch failed (%s); medal data unavailable this session",
                       COMMUNITY_MEDALS_URL, exc_info=True)

# ── Main App ───────────────────────────────────────────────────────────────
class NeonWhiteApp:
    def __init__(self, root):
        self.root        = root
        self.cfg         = load_config()
        self.t           = THEMES[self.cfg["theme"]]
        self.running     = False
        self.current_section = None
        self._player_results = []
        self._finder_running = False

        root.title(APP_TITLE)
        root.geometry("1020x740")
        root.minsize(900, 640)
        root.configure(bg=self.t["bg"])

        # Load GOHU font before building UI
        load_gohu_font()

        # Compile C shuffle library for fast seed search
        threading.Thread(target=self._init_c_shuffle, daemon=True).start()

        self._build_ui()
        self._apply_theme()
        self._show_section("global")

        # Auto-connect if DLL path saved
        if self.cfg["dll_path"] and os.path.exists(self.cfg["dll_path"]):
            threading.Thread(target=self._connect_steam, daemon=True).start()

        # Fetch cheater list in background on startup
        threading.Thread(target=self._fetch_cheaters_bg, daemon=True).start()

        # Fetch community medals in background on startup
        threading.Thread(target=fetch_community_medals, daemon=True).start()

    # ── UI Construction ────────────────────────────────────────────────────
    def _build_ui(self):
        t = self.t

        # Root panes
        self.sidebar_frame = tk.Frame(self.root, width=210, bg=t["bg2"])
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar_frame.pack_propagate(False)

        self.main_frame = tk.Frame(self.root, bg=t["bg"])
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_sidebar()
        self._build_global_section()
        self._build_level_section()
        self._build_player_section()
        self._build_settings_section()

        self._build_rush_sections()

    def _build_rush_sections(self):
        """Build all five Rush Tools sections."""
        self._build_rush_finder()
        self._build_rush_parser()
        self._build_rush_splits()
        self._build_rush_std()
        self._build_rush_timer()

    # ── Rush Tools shared helpers ──────────────────────────────────────────
    def _rush_header(self, parent, title, subtitle):
        t = self.t
        hdr = tk.Frame(parent, bg=t["bg"], padx=24, pady=18)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=title, font=("Helvetica", 16, "bold"),
                 bg=t["bg"], fg=t["fg"]).pack(anchor="w")
        tk.Label(hdr, text=subtitle, font=("Helvetica", 10),
                 bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(2, 0))
        tk.Frame(parent, height=1, bg=t["border"]).pack(fill=tk.X, padx=24, pady=(0, 10))

    def _rush_field_label(self, parent, text):
        t = self.t
        tk.Label(parent, text=text.upper(), font=("Helvetica", 8),
                 bg=t["bg"], fg=t["fg2"], anchor="w").pack(anchor="w", pady=(4, 2))

    def _rush_entry(self, parent, var=None, placeholder="", width=None):
        t = self.t
        kw = dict(font=("Helvetica", 11), bg=t["input_bg"], fg=t["input_fg"],
                  insertbackground=t["fg"], relief="flat", bd=1)
        if width:
            kw["width"] = width
        e = tk.Entry(parent, textvariable=var, **kw) if var else tk.Entry(parent, **kw)
        e.pack(fill=tk.X if not width else tk.NONE, pady=(0, 8))
        if placeholder and not var:
            e.insert(0, placeholder)
            e.config(fg=t["fg2"])
            def on_focus_in(ev, ent=e, ph=placeholder):
                if ent.get() == ph:
                    ent.delete(0, tk.END)
                    ent.config(fg=t["fg"])
            def on_focus_out(ev, ent=e, ph=placeholder):
                if not ent.get():
                    ent.insert(0, ph)
                    ent.config(fg=t["fg2"])
            e.bind("<FocusIn>",  on_focus_in)
            e.bind("<FocusOut>", on_focus_out)
        return e

    def _rush_text(self, parent, height=6):
        t = self.t
        txt = tk.Text(parent, height=height, font=("Courier", 10),
                      bg=t["log_bg"], fg=t["fg"], insertbackground=t["fg"],
                      relief="flat", bd=1, wrap=tk.NONE)
        txt.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        return txt

    def _rush_btn(self, parent, text, cmd):
        t = self.t
        btn = tk.Button(parent, text=text, command=cmd,
                        font=("Helvetica", 10, "bold"),
                        bg=t["btn_bg"], fg="#0a0a0f" if self.cfg["theme"] == "dark" else "#ffffff",
                        relief="flat", bd=0, padx=16, pady=6, cursor="hand2")
        btn.pack(anchor="w", pady=(4, 8))
        return btn

    def _rush_result_box(self, parent, height=10):
        t = self.t
        box = tk.Text(parent, height=height, font=("Courier", 10),
                      bg=t["log_bg"], fg=t["accent"],
                      insertbackground=t["fg"], relief="flat", bd=1,
                      state=tk.DISABLED, wrap=tk.NONE)
        sb = ttk.Scrollbar(parent, orient="vertical", command=box.yview)
        box.configure(yscrollcommand=sb.set)
        box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        return box

    def _rush_show(self, box, text):
        box.configure(state=tk.NORMAL)
        box.delete("1.0", tk.END)
        box.insert(tk.END, text)
        box.configure(state=tk.DISABLED)

    def _rush_dropdown(self, parent, var, options, cmd=None):
        t = self.t
        cb = ttk.Combobox(parent, textvariable=var, values=options,
                          font=("Helvetica", 10), state="readonly")
        cb.pack(anchor="w", pady=(0, 8))
        if cmd:
            cb.bind("<<ComboboxSelected>>", lambda e: cmd())
        return cb

    # ── Seed Finder ────────────────────────────────────────────────────────
    def _build_rush_finder(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.rush_finder_frame = f
        self._rush_header(f, "Seed Finder",
            "Search up to 2.1 billion seeds to find ones where your desired levels appear early.")

        body = tk.Frame(f, bg=t["bg"], padx=24)
        body.pack(fill=tk.BOTH, expand=True)

        # Rush selector + search depth row — use grid for stable alignment
        row1 = tk.Frame(body, bg=t["bg"])
        row1.pack(fill=tk.X, pady=(0, 4))
        row1.columnconfigure(0, weight=3)
        row1.columnconfigure(1, weight=1)

        lc = tk.Frame(row1, bg=t["bg"])
        lc.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self._rush_field_label(lc, "Rush")
        self.finder_rush_var = tk.StringVar(value="White / Mikey")
        rush_cb = ttk.Combobox(lc, textvariable=self.finder_rush_var,
                               values=["White / Mikey", "Violet", "Red", "Yellow"],
                               font=gohu(14), state="readonly")
        rush_cb.pack(anchor="w", pady=(0, 8))
        rush_cb.bind("<<ComboboxSelected>>", lambda e: self._finder_on_rush_change())

        rc = tk.Frame(row1, bg=t["bg"])
        rc.grid(row=0, column=1, sticky="ew")
        self._rush_field_label(rc, "Search Depth")
        self.finder_depth_var = tk.StringVar(value="10")
        depth_entry = tk.Entry(rc, textvariable=self.finder_depth_var, width=8,
                               font=gohu(14), bg=t["input_bg"], fg=t["input_fg"],
                               relief="flat")
        depth_entry.pack(anchor="w", pady=(0, 8))

        # Desired levels — dynamic depth update on key release
        self._rush_field_label(body, "Desired Starting Levels")
        self.finder_levels_entry = self._rush_entry(body,
            placeholder="e.g. The Third Temple, Absolution, The Clocktower")
        self.finder_levels_entry.bind("<KeyRelease>", lambda e: self._finder_update_depth())
        tk.Label(body, text="Comma-separated level names. Case insensitive.",
                 font=gohu(12), bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(0, 8))

        # Result mode
        self._rush_field_label(body, "Result Mode")
        mode_frame = tk.Frame(body, bg=t["bg"])
        mode_frame.pack(anchor="w", pady=(0, 8))
        self.finder_mode_var = tk.StringVar(value="first")
        self._build_radio_group(mode_frame, self.finder_mode_var,
            [("first", "First Match"), ("multi", "Find Multiple")]).pack(side=tk.LEFT)

        maxseeds_frame = tk.Frame(body, bg=t["bg"])
        maxseeds_frame.pack(anchor="w", pady=(0, 8))
        tk.Label(maxseeds_frame, text="Max seeds to find:", font=("Helvetica", 10),
                 bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT, padx=(0, 8))
        self.finder_maxseeds_var = tk.StringVar(value="5")
        tk.Entry(maxseeds_frame, textvariable=self.finder_maxseeds_var, width=6,
                 font=("Helvetica", 10), bg=t["input_bg"], fg=t["input_fg"],
                 relief="flat").pack(side=tk.LEFT)

        # Buttons
        btn_frame = tk.Frame(body, bg=t["bg"])
        btn_frame.pack(anchor="w", pady=(4, 8))
        self.finder_run_btn = tk.Button(btn_frame, text="Find Seed",
                                        command=self._run_finder,
                                        font=("Helvetica", 10, "bold"),
                                        bg=t["btn_bg"],
                                        fg="#0a0a0f" if self.cfg["theme"] == "dark" else "#ffffff",
                                        relief="flat", bd=0, padx=16, pady=6, cursor="hand2")
        self.finder_run_btn.pack(side=tk.LEFT)
        self.finder_stop_btn = tk.Button(btn_frame, text="Stop",
                                         command=self._stop_finder,
                                         font=("Helvetica", 10, "bold"),
                                         bg=t["error"], fg="#ffffff",
                                         relief="flat", bd=0, padx=16, pady=6, cursor="hand2",
                                         state=tk.DISABLED)
        self.finder_stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Progress bar + status
        self.finder_progress = ttk.Progressbar(
            body, mode="determinate", maximum=100, value=0,
            style="NeonGreen.Horizontal.TProgressbar"
        )
        self.finder_progress.pack(fill=tk.X, pady=(4, 0))
        self.finder_status_var = tk.StringVar(value="")
        tk.Label(body, textvariable=self.finder_status_var, font=gohu(12),
                 bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(2, 6))

        # Results — collapsible treeview
        self._rush_field_label(body, "Results (click a seed to expand/collapse level order)")
        result_frame = tk.Frame(body, bg=t["bg"])
        result_frame.pack(fill=tk.BOTH, expand=True)
        self.finder_tree = ttk.Treeview(result_frame, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(result_frame, orient="vertical", command=self.finder_tree.yview)
        self.finder_tree.configure(yscrollcommand=vsb.set)
        self.finder_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.finder_tree.tag_configure("seed",    font=gohu(13, bold=True),
                                       foreground=t["accent"])
        self.finder_tree.tag_configure("match",   foreground=t["accent"])
        self.finder_tree.tag_configure("level",   foreground=t["fg2"])
        self.finder_tree.tag_configure("no_match",foreground=t["fg2"])

    def _rush_key_to_num(self, rush_var_str):
        mapping = {
            "White / Mikey": 96,
            "Violet":        8,
            "Red":           8,
            "Yellow":        8,
        }
        return mapping.get(rush_var_str, 96)

    def _rush_key_from_display(self, display):
        mapping = {
            "White / Mikey": "96",
            "Violet":        "violet",
            "Red":           "red",
            "Yellow":        "yellow",
        }
        return mapping.get(display, "96")

    def _finder_on_rush_change(self):
        """Auto-set search depth to 8 for non-White/Mikey rushes."""
        rush = self.finder_rush_var.get()
        if rush != "White / Mikey":
            self.finder_depth_var.set("8")
        else:
            # Restore depth based on current level count
            self._finder_update_depth()

    def _finder_update_depth(self):
        """Dynamically update search depth to match number of entered levels."""
        raw = self.finder_levels_entry.get().strip()
        placeholder = "e.g. The Third Temple, Absolution, The Clocktower"
        if not raw or raw == placeholder:
            return
        # Count non-empty comma-separated entries
        count = len([p for p in raw.split(",") if p.strip()])
        if count < 1:
            return
        rush = self.finder_rush_var.get()
        max_depth = self._rush_key_to_num(rush)
        try:
            current = int(self.finder_depth_var.get())
        except ValueError:
            current = 0
        # Only increase depth automatically, never decrease while typing
        new_depth = max(current, min(count, max_depth))
        self.finder_depth_var.set(str(new_depth))

    def _run_finder(self):
        rush_display = self.finder_rush_var.get()
        rush_key     = self._rush_key_from_display(rush_display)
        num_levels   = self._rush_key_to_num(rush_display)
        mode         = self.finder_mode_var.get()

        raw_levels = self.finder_levels_entry.get().strip()
        if raw_levels in ("", "e.g. The Third Temple, Absolution, The Clocktower"):
            self._rush_show(self.finder_result, "Please enter at least one desired level.")
            return
        try:
            depth = int(self.finder_depth_var.get())
        except ValueError:
            self._rush_show(self.finder_result, "Search Depth must be a number.")
            return
        max_seeds = 1 if mode == "first" else max(1, int(self.finder_maxseeds_var.get() or "5"))

        target_indices, err = self._parse_level_names(raw_levels, rush_key)
        if err:
            self._rush_show(self.finder_result, f"Error: {err}")
            return

        target_set = set(target_indices)
        names      = RUSH_LEVELS[rush_key]

        # Determine core count — all minus one, minimum 1
        num_cores  = max(1, multiprocessing.cpu_count() - 1)
        MAX_SEED   = 2_147_483_647
        chunk_size = MAX_SEED // num_cores

        # Warn if the search is statistically near-impossible
        expected = _expected_match_count(num_levels, len(target_indices), depth, MAX_SEED)
        if expected < 10:
            msg = (f"Expected matches across the full 2.1B seed range: ~{expected:.2f}.\n\n"
                   f"With {len(target_indices)} target level(s) at depth {depth} "
                   f"in a pool of {num_levels}, this search is unlikely to find any "
                   f"results.\n\nIncrease Search Depth or reduce target levels for a "
                   f"feasible search.\n\nProceed anyway?")
            if not messagebox.askyesno("Unlikely search", msg):
                self._rush_show(self.finder_result, "Search cancelled.")
                return

        self._finder_running   = True
        self._finder_stop_event = multiprocessing.Event()
        self.finder_run_btn.configure(state=tk.DISABLED)
        self.finder_stop_btn.configure(state=tk.NORMAL)
        self.finder_progress.configure(value=0)
        self.finder_status_var.set(f"Searching across {num_cores} core(s)...")
        # Clear previous results
        for item in self.finder_tree.get_children():
            self.finder_tree.delete(item)

        def manager_thread():
            result_queue = multiprocessing.Queue()
            workers      = []
            MAX_SEED     = 2_147_483_647

            for core in range(num_cores):
                start = core * chunk_size + 1
                end   = (core + 1) * chunk_size + 1 if core < num_cores - 1 else MAX_SEED + 1
                p = multiprocessing.Process(
                    target=_seed_search_worker,
                    args=((start, end, num_levels, target_set, depth,
                           result_queue, self._finder_stop_event),),
                    daemon=True
                )
                p.start()
                workers.append(p)

            found         = []
            done_workers  = 0
            seeds_checked = 0
            TOTAL_SEEDS   = MAX_SEED

            while done_workers < num_cores:
                try:
                    item = result_queue.get(timeout=0.2)
                except Exception:
                    if self._finder_stop_event.is_set():
                        break
                    continue

                if item is None:
                    done_workers += 1
                    continue

                if isinstance(item, tuple) and item and item[0] == "progress":
                    seeds_checked += item[1]
                    pct = min(99, int(seeds_checked / TOTAL_SEEDS * 100))
                    self.root.after(0, lambda p=pct: self.finder_progress.configure(value=p))
                    self.root.after(0, lambda s=seeds_checked, f=len(found):
                        self.finder_status_var.set(
                            f"Searching... {s:,} of {TOTAL_SEEDS:,} seeds checked, {f} found"
                        ))
                    continue

                seed  = item
                found.append(seed)
                order = full_shuffle(num_levels, seed)
                names = RUSH_LEVELS[rush_key]

                def add_to_tree(s=seed, o=order, ns=names, ti=target_indices):
                    target_set_local = set(ti)
                    positions = {idx: pos+1 for pos, idx in enumerate(o) if idx in target_set_local}
                    pos_strs  = ", ".join(f"{ns[idx]} @{positions[idx]}" for idx in ti)
                    node = self.finder_tree.insert(
                        "", "end",
                        text=f"Seed {s}  —  {pos_strs}",
                        tags=("seed",), open=False
                    )
                    for pos, idx in enumerate(o):
                        tag    = "match" if idx in target_set_local else "level"
                        marker = " ◀" if idx in target_set_local else ""
                        self.finder_tree.insert(
                            node, "end",
                            text=f"  {pos+1:>3}.  {ns[idx]}{marker}",
                            tags=(tag,)
                        )

                self.root.after(0, add_to_tree)
                self.root.after(0, lambda n=len(found):
                    self.finder_status_var.set(f"Found {n} seed(s). Still searching..."))

                if len(found) >= max_seeds:
                    self._finder_stop_event.set()
                    break

            self._finder_stop_event.set()
            for p in workers:
                p.join(timeout=2)

            done_msg = (f"Done. Found {len(found)} seed(s)."
                        if found else "No matching seeds found in full range.")
            self.root.after(0, lambda: self.finder_progress.configure(value=100))
            self.root.after(0, lambda: self.finder_status_var.set(done_msg))
            self.root.after(0, lambda: self.finder_run_btn.configure(state=tk.NORMAL))
            self.root.after(0, lambda: self.finder_stop_btn.configure(state=tk.DISABLED))
            self._finder_running = False

        threading.Thread(target=manager_thread, daemon=True).start()

    def _stop_finder(self):
        if hasattr(self, "_finder_stop_event"):
            self._finder_stop_event.set()
        self._finder_running = False
        self.finder_status_var.set("Search stopped.")
        self.finder_progress.configure(value=0)
        self.finder_run_btn.configure(state=tk.NORMAL)
        self.finder_stop_btn.configure(state=tk.DISABLED)

    def _parse_level_names(self, raw, rush_key):
        """Parse comma-separated level names/numbers. Returns (indices_list, error_str)."""
        names  = RUSH_LEVELS[rush_key]
        name_map = {n.lower(): i for i, n in enumerate(names)}
        parts  = [p.strip() for p in raw.split(",") if p.strip()]
        indices = []
        for p in parts:
            pl = p.lower()
            # Exact match
            if pl in name_map:
                indices.append(name_map[pl])
                continue
            # Alias match
            alias = RUSH_ALIASES.get(pl)
            if alias and alias in name_map:
                indices.append(name_map[alias])
                continue
            # Partial match
            matches = [i for i, n in enumerate(names) if pl in n.lower()]
            if len(matches) == 1:
                indices.append(matches[0])
            elif len(matches) > 1:
                return None, f'"{p}" matches multiple levels: {", ".join(names[i] for i in matches)}'
            else:
                # Try numeric
                if p.isdigit():
                    idx = int(p) - 1
                    if 0 <= idx < len(names):
                        indices.append(idx)
                    else:
                        return None, f"Level number {p} out of range."
                else:
                    return None, f'Unknown level: "{p}"'
        if not indices:
            return None, "No valid levels entered."
        return indices, None

    # ── Seed Parser ────────────────────────────────────────────────────────
    def _build_rush_parser(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.rush_parser_frame = f
        self._rush_header(f, "Seed Parser",
            "Enter any seed number to see the full level play order it produces.")

        body = tk.Frame(f, bg=t["bg"], padx=24)
        body.pack(fill=tk.BOTH, expand=True)

        self._rush_field_label(body, "Rush")
        self.parser_rush_var = tk.StringVar(value="White / Mikey")
        self._rush_dropdown(body, self.parser_rush_var,
            ["White / Mikey", "Violet", "Red", "Yellow"])

        self._rush_field_label(body, "Seed Number")
        seed_row = tk.Frame(body, bg=t["bg"])
        seed_row.pack(anchor="w", pady=(0, 8))
        self.parser_seed_var = tk.StringVar()
        tk.Entry(seed_row, textvariable=self.parser_seed_var, width=24,
                 font=gohu(14), bg=t["input_bg"], fg=t["input_fg"],
                 insertbackground=t["fg"], relief="flat").pack(side=tk.LEFT)

        self._rush_btn(body, "Parse Seed", self._run_parser)

        self._rush_field_label(body, "Level Order")
        result_frame = tk.Frame(body, bg=t["bg"])
        result_frame.pack(fill=tk.BOTH, expand=True)
        self.parser_result = self._rush_result_box(result_frame, height=14)

    def _run_parser(self):
        try:
            seed = int(self.parser_seed_var.get().strip())
            if seed < 1 or seed > 2147483647:
                raise ValueError
        except ValueError:
            self._rush_show(self.parser_result, "Please enter a valid seed number (1 to 2,147,483,647).")
            return
        rush_key   = self._rush_key_from_display(self.parser_rush_var.get())
        num_levels = self._rush_key_to_num(self.parser_rush_var.get())
        order      = full_shuffle(num_levels, seed)
        names      = RUSH_LEVELS[rush_key]
        lines      = [f"Seed {seed} — {self.parser_rush_var.get()}\n"]
        for pos, idx in enumerate(order):
            lines.append(f"{pos+1:>3}. {names[idx]}")
        self._rush_show(self.parser_result, "\n".join(lines))

    # ── Splits Updater ─────────────────────────────────────────────────────
    def _build_rush_splits(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.rush_splits_frame = f
        self._rush_header(f, "Splits Updater",
            "Paste your splits in standard level order and reorder them to match a seed.")

        body = tk.Frame(f, bg=t["bg"], padx=24)
        body.pack(fill=tk.BOTH, expand=True)

        self._rush_field_label(body, "Rush")
        self.splits_rush_var = tk.StringVar(value="White / Mikey")
        self._rush_dropdown(body, self.splits_rush_var,
            ["White / Mikey", "Violet", "Red", "Yellow"])

        self._rush_field_label(body, "Seed Number")
        splits_seed_row = tk.Frame(body, bg=t["bg"])
        splits_seed_row.pack(anchor="w", pady=(0, 8))
        self.splits_seed_var = tk.StringVar()
        tk.Entry(splits_seed_row, textvariable=self.splits_seed_var, width=24,
                 font=gohu(14), bg=t["input_bg"], fg=t["input_fg"],
                 insertbackground=t["fg"], relief="flat").pack(side=tk.LEFT)

        # Two text areas side by side
        cols = tk.Frame(body, bg=t["bg"])
        cols.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(cols, bg=t["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._rush_field_label(left, "Gold Splits (standard order, one per line)")
        self.splits_gold_text = self._rush_text(left, height=8)

        right = tk.Frame(cols, bg=t["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rush_field_label(right, "Segment Splits (standard order, one per line)")
        self.splits_seg_text = self._rush_text(right, height=8)

        self._rush_btn(body, "Generate Splits", self._run_splits)

        result_cols = tk.Frame(body, bg=t["bg"])
        result_cols.pack(fill=tk.BOTH, expand=True)

        rl = tk.Frame(result_cols, bg=t["bg"])
        rl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._rush_field_label(rl, "Reordered Gold")
        self.splits_gold_result = self._rush_result_box(rl, height=6)

        rr = tk.Frame(result_cols, bg=t["bg"])
        rr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rush_field_label(rr, "Reordered Segments")
        self.splits_seg_result = self._rush_result_box(rr, height=6)

    def _run_splits(self):
        try:
            seed = int(self.splits_seed_var.get().strip())
            if seed < 1 or seed > 2147483647:
                raise ValueError
        except ValueError:
            self._rush_show(self.splits_gold_result, "Invalid seed number.")
            return
        rush_key   = self._rush_key_from_display(self.splits_rush_var.get())
        num_levels = self._rush_key_to_num(self.splits_rush_var.get())
        order      = full_shuffle(num_levels, seed)
        names      = RUSH_LEVELS[rush_key]

        gold_raw = [l for l in self.splits_gold_text.get("1.0", tk.END).strip().splitlines() if l.strip()]
        seg_raw  = [l for l in self.splits_seg_text.get("1.0", tk.END).strip().splitlines() if l.strip()]

        if gold_raw and len(gold_raw) != num_levels:
            self._rush_show(self.splits_gold_result,
                f"Expected {num_levels} gold splits, got {len(gold_raw)}.")
            return
        if seg_raw and len(seg_raw) != num_levels:
            self._rush_show(self.splits_seg_result,
                f"Expected {num_levels} segment splits, got {len(seg_raw)}.")
            return

        gold_out = [gold_raw[idx] for idx in order] if gold_raw else []
        seg_out  = [seg_raw[idx]  for idx in order] if seg_raw  else []

        if gold_out:
            lines = [f"{pos+1:>3}. {names[order[pos]]:<28} {t}"
                     for pos, t in enumerate(gold_out)]
            self._rush_show(self.splits_gold_result, "\n".join(lines))
        if seg_out:
            lines = [f"{pos+1:>3}. {names[order[pos]]:<28} {t}"
                     for pos, t in enumerate(seg_out)]
            self._rush_show(self.splits_seg_result, "\n".join(lines))

    # ── Standardize Splits ─────────────────────────────────────────────────
    def _build_rush_std(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.rush_std_frame = f
        self._rush_header(f, "Standardize Splits",
            "Convert splits recorded in seed order back to standard level order.")

        body = tk.Frame(f, bg=t["bg"], padx=24)
        body.pack(fill=tk.BOTH, expand=True)

        self._rush_field_label(body, "Rush")
        self.std_rush_var = tk.StringVar(value="White / Mikey")
        self._rush_dropdown(body, self.std_rush_var,
            ["White / Mikey", "Violet", "Red", "Yellow"])

        self._rush_field_label(body, "Seed Number")
        std_seed_row = tk.Frame(body, bg=t["bg"])
        std_seed_row.pack(anchor="w", pady=(0, 8))
        self.std_seed_var = tk.StringVar()
        tk.Entry(std_seed_row, textvariable=self.std_seed_var, width=24,
                 font=gohu(14), bg=t["input_bg"], fg=t["input_fg"],
                 insertbackground=t["fg"], relief="flat").pack(side=tk.LEFT)

        cols = tk.Frame(body, bg=t["bg"])
        cols.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(cols, bg=t["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._rush_field_label(left, "Gold Splits (seed order, one per line)")
        self.std_gold_text = self._rush_text(left, height=8)

        right = tk.Frame(cols, bg=t["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rush_field_label(right, "Segment Splits (seed order, one per line)")
        self.std_seg_text = self._rush_text(right, height=8)

        self._rush_btn(body, "Standardize", self._run_std)

        result_cols = tk.Frame(body, bg=t["bg"])
        result_cols.pack(fill=tk.BOTH, expand=True)

        rl = tk.Frame(result_cols, bg=t["bg"])
        rl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._rush_field_label(rl, "Standard Order Gold")
        self.std_gold_result = self._rush_result_box(rl, height=6)

        rr = tk.Frame(result_cols, bg=t["bg"])
        rr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rush_field_label(rr, "Standard Order Segments")
        self.std_seg_result = self._rush_result_box(rr, height=6)

    def _run_std(self):
        try:
            seed = int(self.std_seed_var.get().strip())
            if seed < 1 or seed > 2147483647:
                raise ValueError
        except ValueError:
            self._rush_show(self.std_gold_result, "Invalid seed number.")
            return
        rush_key   = self._rush_key_from_display(self.std_rush_var.get())
        num_levels = self._rush_key_to_num(self.std_rush_var.get())
        order      = full_shuffle(num_levels, seed)
        names      = RUSH_LEVELS[rush_key]

        # Build inverse: standard_index -> seed_position
        seed_position = [0] * num_levels
        for pos, idx in enumerate(order):
            seed_position[idx] = pos

        gold_raw = [l for l in self.std_gold_text.get("1.0", tk.END).strip().splitlines() if l.strip()]
        seg_raw  = [l for l in self.std_seg_text.get("1.0", tk.END).strip().splitlines() if l.strip()]

        if gold_raw and len(gold_raw) != num_levels:
            self._rush_show(self.std_gold_result,
                f"Expected {num_levels} gold splits, got {len(gold_raw)}.")
            return
        if seg_raw and len(seg_raw) != num_levels:
            self._rush_show(self.std_seg_result,
                f"Expected {num_levels} segment splits, got {len(seg_raw)}.")
            return

        if gold_raw:
            lines = [f"{i+1:>3}. {names[i]:<28} {gold_raw[seed_position[i]]}"
                     for i in range(num_levels)]
            self._rush_show(self.std_gold_result, "\n".join(lines))
        if seg_raw:
            lines = [f"{i+1:>3}. {names[i]:<28} {seg_raw[seed_position[i]]}"
                     for i in range(num_levels)]
            self._rush_show(self.std_seg_result, "\n".join(lines))

    # ── Run Timer ──────────────────────────────────────────────────────────
    def _build_rush_timer(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.rush_timer_frame = f
        self._rush_header(f, "Run Timer",
            "Enter cumulative split times per level to get segment times and medal grades.")

        body = tk.Frame(f, bg=t["bg"], padx=24)
        body.pack(fill=tk.BOTH, expand=True)

        # Rush + seed row
        row1 = tk.Frame(body, bg=t["bg"])
        row1.pack(fill=tk.X)
        lc = tk.Frame(row1, bg=t["bg"])
        lc.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        self._rush_field_label(lc, "Rush")
        self.timer_rush_var = tk.StringVar(value="White / Mikey")
        self._rush_dropdown(lc, self.timer_rush_var,
            ["White / Mikey", "Violet", "Red", "Yellow"],
            cmd=self._timer_on_rush_change)

        rc = tk.Frame(row1, bg=t["bg"])
        rc.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._rush_field_label(rc, "Seed Number (optional)")
        self.timer_seed_var = tk.StringVar()
        seed_entry = self._rush_entry(rc, var=self.timer_seed_var, width=20)

        load_btn = tk.Button(rc, text="Load Seed Order",
                             command=self._timer_load_seed,
                             font=("Helvetica", 9),
                             bg=t["bg2"] if hasattr(t, 'bg2') else t["log_bg"],
                             fg=t["fg"], relief="flat", bd=1, cursor="hand2")
        load_btn.pack(anchor="w", pady=(0, 8))

        # Splits input
        self._rush_field_label(body, "Cumulative Split Times (level name: time, one per line)")
        tk.Label(body, text='e.g. "Movement: 17.442" or just "17.442" (in level order)',
                 font=("Helvetica", 9), bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(0, 4))
        self.timer_input = self._rush_text(body, height=8)

        self._rush_btn(body, "Calculate Segments", self._run_timer)

        # Results
        result_cols = tk.Frame(body, bg=t["bg"])
        result_cols.pack(fill=tk.BOTH, expand=True)

        rl = tk.Frame(result_cols, bg=t["bg"])
        rl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._rush_field_label(rl, "Segment Times")
        self.timer_result = self._rush_result_box(rl, height=6)

        rr = tk.Frame(result_cols, bg=t["bg"])
        rr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rush_field_label(rr, "Level Order")
        self.timer_names_result = self._rush_result_box(rr, height=6)

    def _timer_on_rush_change(self):
        pass  # placeholder for future auto-reload

    def _timer_load_seed(self):
        try:
            seed = int(self.timer_seed_var.get().strip())
            if seed < 1 or seed > 2147483647:
                raise ValueError
        except ValueError:
            self._rush_show(self.timer_result, "Invalid seed number.")
            return
        rush_key   = self._rush_key_from_display(self.timer_rush_var.get())
        num_levels = self._rush_key_to_num(self.timer_rush_var.get())
        order      = full_shuffle(num_levels, seed)
        names      = RUSH_LEVELS[rush_key]
        self.timer_input.delete("1.0", tk.END)
        for idx in order:
            self.timer_input.insert(tk.END, f"{names[idx]}: \n")

    def _run_timer(self):
        raw_lines = [l for l in self.timer_input.get("1.0", tk.END).strip().splitlines() if l.strip()]
        if not raw_lines:
            self._rush_show(self.timer_result, "Please enter at least one split time.")
            return

        cumulative = []
        level_names = []
        errors = []

        for i, line in enumerate(raw_lines):
            if ":" in line and not line.strip().startswith(("0:", "1:", "2:", "3:")):
                parts = line.split(":", 1)
                name_part = parts[0].strip()
                time_part = parts[1].strip() if len(parts) > 1 else ""
            else:
                name_part = f"Level {i+1}"
                time_part = line.strip()

            t_val = self._parse_time_to_secs(time_part)
            if t_val is None:
                errors.append(f"Row {i+1}: invalid time '{time_part}'")
                continue
            if cumulative and t_val <= cumulative[-1]:
                errors.append(f"Row {i+1} ({name_part}): time must be greater than previous ({self._format_secs(cumulative[-1])})")
                continue
            cumulative.append(t_val)
            level_names.append(name_part)

        if errors:
            self._rush_show(self.timer_result, "\n".join(errors))
            return

        segments = [cumulative[0]] + [cumulative[i] - cumulative[i-1] for i in range(1, len(cumulative))]
        rush_key = self._rush_key_from_display(self.timer_rush_var.get())

        seg_lines  = []
        name_lines = []
        for i, (seg, name) in enumerate(zip(segments, level_names)):
            medal = self._get_medal(name, seg, rush_key)
            seg_lines.append(f"{self._format_secs(seg):<14} {medal}")
            name_lines.append(name)

        self._rush_show(self.timer_result,  "\n".join(seg_lines))
        self._rush_show(self.timer_names_result, "\n".join(name_lines))

    def _parse_time_to_secs(self, raw):
        import re
        s = (raw or "").strip()
        m = re.match(r'^(\d+):(\d{1,2})(?:\.(\d+))?$', s)
        if m:
            return int(m.group(1))*60 + int(m.group(2)) + (float("0."+m.group(3)) if m.group(3) else 0)
        m2 = re.match(r'^(\d+)(?:\.(\d+))?$', s)
        if m2:
            return int(m2.group(1)) + (float("0."+m2.group(2)) if m2.group(2) else 0)
        return None

    def _format_secs(self, secs):
        if secs < 60:
            return f"{secs:.3f}"
        mins = int(secs // 60)
        s = secs - mins * 60
        return f"{mins}:{s:06.3f}"

    def _get_medal(self, level_name, secs, rush_key):
        """Return a medal label string for a given level and time."""
        code = self._resolve_level_code(level_name, rush_key)
        if not code:
            return ""
        us = int(secs * 1_000_000)
        std = STANDARD_MEDAL_DATA.get(code)
        if std:
            if us <= std[4]: return "DEV"
            if us <= std[3]: return "ACE"
            if us <= std[2]: return "GOLD"
            if us <= std[1]: return "SILVER"
            if us <= std[0]: return "BRONZE"
        comm = COMMUNITY_MEDAL_DATA.get(code)
        if comm and len(comm) >= 3:
            if len(comm) >= 5 and us <= comm[4]: return "BLOOD DIAMOND"
            if len(comm) >= 5 and us <= comm[3]: return "TOPAZ"
            if us <= comm[2]: return "SAPPHIRE"
            if us <= comm[1]: return "AMETHYST"
            if us <= comm[0]: return "EMERALD"
        return ""

    def _resolve_level_code(self, level_name, rush_key):
        """Resolve a display name to its internal code name for medal lookup."""
        names = RUSH_LEVELS.get(rush_key, RUSH_LEVELS["96"])
        nl = level_name.lower().strip()
        # Try direct match in alias map (reverse lookup)
        for code, display in RUSH_ALIASES.items():
            if display == nl:
                return code.upper()
        # Try matching against display names
        for i, n in enumerate(names):
            if n.lower() == nl:
                # Map display name back to code via our existing LEVELS list
                for disp, internal in LEVELS:
                    if disp.lower() == nl:
                        return internal.upper()
        return None

    def _build_radio_group(self, parent, var, options):
        t = self.t
        frame = tk.Frame(parent, bg=t["bg"])
        buttons = []

        # In dark mode (neon green bg), use dark text for legibility
        # In light mode (green bg), use white text
        selected_fg = "#0a0a0f" if self.cfg["theme"] == "dark" else "#ffffff"

        def select(val):
            var.set(val)
            for v, lbl_widget in buttons:
                is_sel = (v == val)
                lbl_widget.configure(
                    bg=t["btn_bg"] if is_sel else t["bg"],
                    fg=selected_fg if is_sel else t["fg2"],
                    relief="flat",
                    bd=0,
                )

        for val, label in options:
            lbl = tk.Label(
                frame, text=label,
                font=("Helvetica", 10),
                bg=t["bg"], fg=t["fg2"],
                padx=10, pady=3,
                cursor="hand2",
                relief="flat", bd=0,
                borderwidth=1,
            )
            lbl.pack(side=tk.LEFT, padx=(0, 4))
            lbl.bind("<Button-1>", lambda e, v=val: select(v))
            buttons.append((val, lbl))

        select(var.get())
        return frame

    def _build_sidebar(self):
        t = self.t
        sb = self.sidebar_frame
        sb.configure(bg=t["sidebar_bg"])

        # ── App title ──────────────────────────────────────────────────────
        tk.Label(sb, text="Neon White Tools", font=("Helvetica", 13, "bold"),
                 bg=t["sidebar_bg"], fg=t["fg"], anchor="w",
                 padx=16, pady=14).pack(fill=tk.X)

        tk.Frame(sb, height=1, bg=t["border"]).pack(fill=tk.X)

        # ── Scrollable nav area ────────────────────────────────────────────
        nav_area = tk.Frame(sb, bg=t["sidebar_bg"])
        nav_area.pack(fill=tk.BOTH, expand=True)

        # ── Group builder helper ───────────────────────────────────────────
        def make_group(parent, label, items, item_click_fn, group_key):
            """
            Creates a collapsible group with a header and child items.
            items: list of (section_key, display_label)
            Returns dict of {key: label_widget}
            """
            group_frame = tk.Frame(parent, bg=t["sidebar_bg"])
            group_frame.pack(fill=tk.X)

            # Track collapsed state
            state = {"collapsed": False}

            # Header row
            header = tk.Frame(group_frame, bg=t["sidebar_bg"])
            header.pack(fill=tk.X)

            arrow = tk.Label(header, text="▾", font=("Helvetica", 9),
                             bg=t["sidebar_bg"], fg=t["fg2"], padx=6)
            arrow.pack(side=tk.LEFT)

            tk.Label(header, text=label, font=("Helvetica", 9, "bold"),
                     bg=t["sidebar_bg"], fg=t["fg2"], anchor="w",
                     pady=6, cursor="hand2").pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Items container
            items_frame = tk.Frame(group_frame, bg=t["sidebar_bg"])
            items_frame.pack(fill=tk.X)

            def toggle(e=None):
                state["collapsed"] = not state["collapsed"]
                if state["collapsed"]:
                    items_frame.pack_forget()
                    arrow.configure(text="▸")
                else:
                    items_frame.pack(fill=tk.X)
                    arrow.configure(text="▾")

            header.bind("<Button-1>", toggle)
            arrow.bind("<Button-1>", toggle)
            for w in header.winfo_children():
                w.bind("<Button-1>", toggle)

            btns = {}
            for key, lbl_text in items:
                btn = tk.Label(items_frame, text=lbl_text,
                               font=("Helvetica", 11),
                               bg=t["sidebar_bg"], fg=t["nav_inactive_fg"],
                               anchor="w", padx=24, pady=8, cursor="hand2")
                btn.pack(fill=tk.X)
                btn.bind("<Button-1>", lambda e, k=key: item_click_fn(k))
                btns[key] = btn

            return btns, group_frame

        # ── Leaderboard Tools group ────────────────────────────────────────
        lb_items = [
            ("global", "Global Export"),
            ("level",  "Level Search"),
            ("player", "Player Lookup"),
        ]
        lb_btns, _ = make_group(
            nav_area, "Leaderboard Tools", lb_items,
            lambda k: self._show_section(k), "leaderboard"
        )

        tk.Frame(nav_area, height=1, bg=t["border"]).pack(fill=tk.X, pady=4)

        # ── Rush Tools group ───────────────────────────────────────────────
        rush_items = [
            ("rush_finder",  "Seed Finder"),
            ("rush_parser",  "Seed Parser"),
            ("rush_splits",  "Splits Updater"),
            ("rush_std",     "Standardize Splits"),
            ("rush_timer",   "Run Timer"),
        ]
        rush_btns, _ = make_group(
            nav_area, "Rush Tools", rush_items,
            lambda k: self._show_section(k), "rush"
        )

        tk.Frame(nav_area, height=1, bg=t["border"]).pack(fill=tk.X, pady=4)

        # Merge all nav buttons into one dict
        self.nav_btns = {**lb_btns, **rush_btns}

        # ── Settings button — always visible at bottom of nav ──────────────
        self.settings_btn = tk.Label(nav_area, text="Settings",
                                     font=("Helvetica", 11),
                                     bg=t["sidebar_bg"], fg=t["nav_inactive_fg"],
                                     anchor="w", padx=16, pady=8, cursor="hand2")
        self.settings_btn.pack(fill=tk.X)
        self.settings_btn.bind("<Button-1>", lambda e: self._show_section("settings"))

        # ── Status panel at bottom ─────────────────────────────────────────
        self.status_frame = tk.Frame(sb, bg=t["sidebar_bg"])
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=12)

        tk.Frame(self.status_frame, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 10))

        self.status_dot = tk.Label(self.status_frame, text="●", font=("Helvetica", 10),
                                   bg=t["sidebar_bg"], fg=t["error"])
        self.status_dot.pack(anchor="w")

        self.status_label = tk.Label(self.status_frame, text="Not connected",
                                     font=("Helvetica", 9), bg=t["sidebar_bg"], fg=t["fg2"],
                                     wraplength=155, justify=tk.LEFT, anchor="w")
        self.status_label.pack(fill=tk.X)

        self.dll_label = tk.Label(self.status_frame, text="DLL: not set",
                                  font=("Helvetica", 8), bg=t["sidebar_bg"], fg=t["fg2"],
                                  wraplength=155, justify=tk.LEFT, anchor="w")
        self.dll_label.pack(fill=tk.X, pady=(2, 0))

        self.player_label = tk.Label(self.status_frame, text="Player: —",
                                     font=("Helvetica", 8), bg=t["sidebar_bg"], fg=t["fg2"],
                                     wraplength=155, justify=tk.LEFT, anchor="w")
        self.player_label.pack(fill=tk.X, pady=(2, 0))

        self.cheater_label = tk.Label(self.status_frame, text="Cheater list: loading...",
                                      font=("Helvetica", 8), bg=t["sidebar_bg"], fg=t["fg2"],
                                      wraplength=155, justify=tk.LEFT, anchor="w")
        self.cheater_label.pack(fill=tk.X, pady=(2, 0))

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
        self._build_radio_group(r3, self.global_out_var,
            [("display", "Display in app"), ("csv", "Save to CSV"), ("both", "Both")]
        ).pack(side=tk.LEFT)

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
        self._build_radio_group(r3, self.level_out_var,
            [("display", "Display in app"), ("csv", "Save to CSV"), ("both", "Both")]
        ).pack(side=tk.LEFT)

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
        tk.Button(r1, text="Use My Steam ID",
                  font=("Helvetica", 9),
                  command=self._use_my_steam_id).pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(r1, text="  17-digit number from Steam profile URL",
                 font=("Helvetica", 9), bg=t["bg"], fg=t["fg2"]).pack(side=tk.LEFT)

        # Search mode
        r2 = tk.Frame(ctrl, bg=t["bg"])
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text="Search mode", width=16, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.player_mode_var = tk.StringVar(value="level")
        mode_group = self._build_radio_group(r2, self.player_mode_var,
            [("level", "Single level"), ("chapter", "Chapter"), ("game", "Whole game")]
        )
        mode_group.pack(side=tk.LEFT)
        self.player_mode_var.trace_add("write", lambda *_: self._update_player_mode())

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
        self._build_radio_group(r4, self.player_out_var,
            [("display", "Display in app"), ("csv", "Save to CSV"), ("both", "Both")]
        ).pack(side=tk.LEFT)

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
        self._build_radio_group(r4, self.settings_theme_var,
            [("light", "Light"), ("dark", "Dark")]
        ).pack(side=tk.LEFT)

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

        # Single save button covering all settings
        tk.Frame(ctrl, height=1, bg=t["border"]).pack(fill=tk.X, pady=(20, 12))
        tk.Button(ctrl, text="Save Settings", font=("Helvetica", 10, "bold"),
                  command=self._save_settings).pack(anchor="w")

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
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=8)
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

        # Push to Sheet button — pinned below table, always visible on player tab
        if key == "player":
            sheet_btn_frame = tk.Frame(parent, bg=t["bg"], padx=24, pady=8)
            sheet_btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
            tk.Frame(sheet_btn_frame, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))
            self.push_sheet_btn = tk.Button(
                sheet_btn_frame,
                text="Push to Google Sheet",
                font=("Helvetica", 10, "bold"),
                command=self._push_to_sheet,
                state=tk.DISABLED
            )
            self.push_sheet_btn.pack(anchor="w")
            tk.Label(sheet_btn_frame,
                     text="Runs a Player Lookup first, then click to push times and ranks to your sheet.",
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
            "global":       self.global_frame,
            "level":        self.level_frame,
            "player":       self.player_frame,
            "settings":     self.settings_frame,
            "rush_finder":  self.rush_finder_frame,
            "rush_parser":  self.rush_parser_frame,
            "rush_splits":  self.rush_splits_frame,
            "rush_std":     self.rush_std_frame,
            "rush_timer":   self.rush_timer_frame,
        }
        for k, frame in sections.items():
            frame.pack_forget()
        if key in sections:
            sections[key].pack(fill=tk.BOTH, expand=True)
        self.current_section = key

        # Update nav button highlights
        for k, btn in self.nav_btns.items():
            is_active = (k == key)
            btn.configure(
                bg=t["sidebar_sel"] if is_active else t["sidebar_bg"],
                fg=t["nav_active_fg"] if is_active else t["nav_inactive_fg"],
                font=("Helvetica", 11, "bold" if is_active else "normal")
            )
        is_settings = (key == "settings")
        self.settings_btn.configure(
            bg=t["sidebar_sel"] if is_settings else t["sidebar_bg"],
            fg=t["nav_active_fg"] if is_settings else t["nav_inactive_fg"],
            font=("Helvetica", 11, "bold" if is_settings else "normal")
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

    # ── C shuffle init ─────────────────────────────────────────────────────
    def _init_c_shuffle(self):
        ok = _load_c_shuffle()
        mode = "C-accelerated" if ok else "Python fallback"
        if not ok:
            logger.warning("shuffle.dll did not load; seed search will use the slow "
                           "Python fallback. Run compile_shuffle.py to (re)build.")
        self.root.after(0, lambda m=mode: self.finder_status_var.set(
            f"Seed search engine: {m}"
        ))

    # ── Cheater list ───────────────────────────────────────────────────────
    def _fetch_cheaters_bg(self):
        count = fetch_cheater_list()
        if count > 0:
            self.cheater_label.configure(
                text=f"Cheaters filtered: {count:,}",
                fg=self.t["success"]
            )
        else:
            self.cheater_label.configure(
                text="Cheater list: unavailable",
                fg=self.t["fg2"]
            )

    # ── Use My Steam ID ────────────────────────────────────────────────────
    def _use_my_steam_id(self):
        if not steam_ready or not logged_in_steam_id:
            messagebox.showerror(
                "Not connected",
                "Connect to Steam first in Settings — your Steam ID will be populated automatically."
            )
            return
        self.player_id_var.set(str(logged_in_steam_id))

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
                logger.exception("Google Sheets authentication failed")
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
                service = get_sheets_service()

                # Build indexed lists — one entry per level in game order,
                # skipping levels the player has no time for
                result_by_level = {r["level"]: r for r in self._player_results}
                times_vals = []
                ranks_vals = []
                for offset, (display_name, _) in enumerate(WHOLE_GAME_LEVELS):
                    if display_name in result_by_level:
                        r = result_by_level[display_name]
                        times_vals.append((offset, format_time_mmss(r["score_ms"])))
                        ranks_vals.append((offset, r["rank"]))
                    # levels with no entry are simply omitted — cell untouched

                if times_tab:
                    push_to_sheet(service, sheet_id, times_tab, times_cell, times_vals)
                if ranks_tab:
                    push_to_sheet(service, sheet_id, ranks_tab, ranks_cell, ranks_vals)

                pushed = len(times_vals)
                parts  = []
                if times_tab:
                    parts.append(f"{pushed} times → '{times_tab}'!{times_cell}")
                if ranks_tab:
                    parts.append(f"{pushed} ranks → '{ranks_tab}'!{ranks_cell}")
                messagebox.showinfo("Success", "Pushed to Google Sheet:\n" + "\n".join(parts))

            except Exception as e:
                logger.exception("Google Sheets push failed")
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
        self._apply_widget_defaults()

    def _apply_widget_defaults(self):
        t   = self.t
        fnt      = gohu(14)
        fnt_bold = gohu(13, bold=True)
        fnt_sm   = gohu(12)
        fnt_mono = gohu_mono(14)

        self.root.option_add("*Font",               fnt)
        self.root.option_add("*Background",         t["bg"])
        self.root.option_add("*Foreground",         t["fg"])
        self.root.option_add("*Entry.Background",   t["input_bg"])
        self.root.option_add("*Entry.Foreground",   t["input_fg"])
        self.root.option_add("*Entry.Font",         fnt)
        self.root.option_add("*Entry.Relief",       "flat")
        self.root.option_add("*Entry.BorderWidth",  "1")
        self.root.option_add("*Button.Background",  t["btn_bg"])
        self.root.option_add("*Button.Foreground",
                             "#0a0a0f" if self.cfg["theme"] == "dark" else "#ffffff")
        self.root.option_add("*Button.Font",        fnt_bold)
        self.root.option_add("*Button.Relief",      "flat")
        self.root.option_add("*Button.BorderWidth", "0")
        self.root.option_add("*Button.Cursor",      "hand2")
        self.root.option_add("*Button.Padx",        "10")
        self.root.option_add("*Label.Background",   t["bg"])
        self.root.option_add("*Label.Foreground",   t["fg"])
        self.root.option_add("*Label.Font",         fnt)
        self.root.option_add("*Text.Background",    t["log_bg"])
        self.root.option_add("*Text.Foreground",    t["log_fg"])
        self.root.option_add("*Text.Font",          fnt_mono)
        self.root.option_add("*Text.Relief",        "flat")
        self.root.option_add("*Listbox.Font",       fnt)

        # Fix sidebar to set width, content area flexes
        self.sidebar_frame.pack_propagate(False)
        self.sidebar_frame.configure(width=210)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.theme_use("default")

        # Progress bar — neon green fill
        style.configure("NeonGreen.Horizontal.TProgressbar",
                        troughcolor=t["bg2"],
                        background=t["accent"],
                        bordercolor=t["border"],
                        lightcolor=t["accent"],
                        darkcolor=t["accent"])

        style.configure("Treeview",
                        background=t["bg"], foreground=t["fg"],
                        fieldbackground=t["bg"], rowheight=24,
                        font=fnt_sm)
        style.configure("Treeview.Heading",
                        background=t["bg2"], foreground=t["fg2"],
                        font=fnt_sm, relief="flat")
        style.map("Treeview",
                  background=[("selected", t["select"])],
                  foreground=[("selected", t["fg"])])
        style.configure("TScrollbar",
                        background=t["bg2"], troughcolor=t["bg"],
                        bordercolor=t["border"], arrowcolor=t["fg2"])

        # Combobox — fix font for both dropdown list AND selected value display
        style.configure("TCombobox",
                        fieldbackground=t["input_bg"],
                        background=t["bg2"],
                        foreground=t["input_fg"],
                        selectbackground=t["input_bg"],
                        selectforeground=t["input_fg"],
                        arrowcolor=t["fg2"],
                        font=fnt)
        style.map("TCombobox",
                  fieldbackground=[("readonly", t["input_bg"])],
                  foreground=[("readonly", t["input_fg"])],
                  selectbackground=[("readonly", t["input_bg"])],
                  selectforeground=[("readonly", t["input_fg"])])
        self.root.option_add("*TCombobox*Listbox.background",       t["bg2"])
        self.root.option_add("*TCombobox*Listbox.foreground",       t["fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["select"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", t["fg"])
        self.root.option_add("*TCombobox*Listbox.font",             fnt)

        # Apply GOHU font to all tk widgets globally via option_add
        # Note: ttk widgets need explicit style config above
        self.root.tk.call("option", "add", "*TCombobox*font", f"{{{GOHU_FONT_NAME}}} 14")


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for PyInstaller on Windows
    root = tk.Tk()
    app  = NeonWhiteApp(root)
    root.mainloop()
    if steam_ready:
        steam.SteamAPI_Shutdown()
