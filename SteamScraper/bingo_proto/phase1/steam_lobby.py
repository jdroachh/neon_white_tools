"""
steam_lobby — Steam Matchmaking ctypes bindings + polling-based callback dispatch.
Phase 1 extension of Phase 0's steam_lobby.py.

Direct event callbacks are delivered by polling ISteamMatchmaking rather than
SteamAPI_RegisterCallback, which proved incompatible with the DLL version bundled
with Neon White.  This is the third instance of the "polling because vtable
registration doesn't work with this DLL" pattern:

  - LobbyDataUpdate: GetLobbyData compared against last-seen value each pump tick.
  - LobbyChatMsg:    GetLobbyChatEntry polled by incrementing index each pump tick.
  - LobbyChatUpdate: GetNumLobbyMembers + GetLobbyMemberByIndex diffed against
                     last-seen member set each pump tick (NEW in Phase 1).
    Callback ID 506 is registered against but never actually fires via vtable, so
    we synthesize LobbyChatUpdate_t events from the set diff instead.  Stage 2
    leader-transfer logic relies on this synthesized event to detect departures.

  - Async results: IsAPICallCompleted + GetAPICallResult (same as steam_api.py).

Quick-start (module-level API):
    ok, msg = init()
    lid = create_lobby(8)
    register(LOBBY_CHAT_MSG, my_handler)
    register(LOBBY_CHAT_UPDATE, on_member_change)
    while True:
        pump()
        time.sleep(0.1)
"""
import ctypes
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

APP_ID = "1533420"

# ── Callback IDs (isteammatchmaking.h) ───────────────────────────────────────
LOBBY_CREATED        = 513
LOBBY_ENTER          = 504
LOBBY_DATA_UPDATE    = 505
LOBBY_CHAT_UPDATE    = 506   # LobbyChatUpdate_t — member join/leave/kick/ban
LOBBY_CHAT_MSG       = 507

# ── ELobbyType ───────────────────────────────────────────────────────────────
LOBBY_TYPE_PRIVATE      = 0
LOBBY_TYPE_FRIENDS_ONLY = 1
LOBBY_TYPE_PUBLIC       = 2
LOBBY_TYPE_INVISIBLE    = 4

# ── EChatMemberStateChange bitmask ───────────────────────────────────────────
CHAT_MEMBER_ENTERED      = 0x01
CHAT_MEMBER_LEFT         = 0x02
CHAT_MEMBER_DISCONNECTED = 0x04
CHAT_MEMBER_KICKED       = 0x08
CHAT_MEMBER_BANNED       = 0x10

# ── EChatRoomEnterResponse ───────────────────────────────────────────────────
CHAT_ROOM_SUCCESS = 1


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


# ── Callback structures ───────────────────────────────────────────────────────
# All use Steamworks default packing (pack 8).

class LobbyCreated_t(ctypes.Structure):
    """EResult(4) + pad(4) + lobby_id(8) = 16 bytes."""
    _fields_ = [
        ("result",         ctypes.c_int),
        ("lobby_steam_id", ctypes.c_uint64),
    ]

class LobbyEnter_t(ctypes.Structure):
    """lobby(8) + perms(4) + locked(1) + pad(3) + response(4) = 20 bytes."""
    _fields_ = [
        ("lobby_steam_id",     ctypes.c_uint64),
        ("chat_permissions",   ctypes.c_uint32),
        ("locked",             ctypes.c_bool),
        ("chat_room_response", ctypes.c_uint32),
    ]

class LobbyDataUpdate_t(ctypes.Structure):
    """lobby(8) + member(8) + success(1) + pad(7) = 24 bytes."""
    _fields_ = [
        ("lobby_steam_id",  ctypes.c_uint64),
        ("member_steam_id", ctypes.c_uint64),
        ("success",         ctypes.c_uint8),
    ]

class LobbyChatMsg_t(ctypes.Structure):
    """lobby(8) + user(8) + entry_type(1) + pad(3) + chat_id(4) = 24 bytes."""
    _fields_ = [
        ("lobby_steam_id",  ctypes.c_uint64),
        ("user_steam_id",   ctypes.c_uint64),
        ("chat_entry_type", ctypes.c_uint8),
        ("chat_id",         ctypes.c_uint32),
    ]

class LobbyChatUpdate_t(ctypes.Structure):
    """
    Synthesized member-change event (callback ID 506).

    The real SteamAPI_RegisterCallback vtable path does not fire with this
    DLL build (pre-SDK-1.50).  We synthesize these events in pump() by
    diffing GetNumLobbyMembers + GetLobbyMemberByIndex against last-seen
    member sets.  See _poll_members() below.

    Fields mirror the Steamworks SDK struct:
      lobby(8) + user_changed(8) + making_change(8) + state_change(4) = 28 bytes.

    state_change bitmask:
      0x01 = entered   0x02 = left   0x04 = disconnected   0x08 = kicked   0x10 = banned
    For synthesized events we use 0x01 (entered) and 0x02 (left/disconnect/kick —
    we can't distinguish these without the real callback; Stage 2 only needs "gone").
    """
    _fields_ = [
        ("steam_id_lobby",           ctypes.c_uint64),
        ("steam_id_user_changed",    ctypes.c_uint64),
        ("steam_id_making_change",   ctypes.c_uint64),
        ("chat_member_state_change", ctypes.c_uint32),
    ]


# ── Steam directory lookup ───────────────────────────────────────────────────

def _find_steam_dir() -> str:
    """Return Steam's installation directory from the Windows registry."""
    try:
        import winreg
        for hive, key in [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
            (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Valve\Steam"),
        ]:
            try:
                with winreg.OpenKey(hive, key) as k:
                    path, _ = winreg.QueryValueEx(k, "InstallPath")
                    if path and os.path.isdir(path):
                        return path
            except OSError:
                pass
    except ImportError:
        pass
    return r"C:\Program Files (x86)\Steam"


# ── Module-level state (populated by init()) ─────────────────────────────────

_dll         = None    # ctypes.CDLL
_mm          = None    # ISteamMatchmaking interface pointer
_utils       = None    # ISteamUtils interface pointer
_friends     = None    # ISteamFriends interface pointer
_pending     = {}      # SteamAPICall_t → (cb_id, struct_class, fn)
_handlers    = {}      # callback_id → list[fn]

# per-lobby polling state
_watched_lobbies     = {}   # lobby_id → {"next_chat_idx": int, "last_data": dict, "last_members": set}
_watched_data_keys   = {}   # lobby_id → set[str]

player_name        = "Unknown"
local_steam_id     = 0
_ready             = False


# ── Init / Shutdown ──────────────────────────────────────────────────────────

def _write_appid(dll_path: str) -> None:
    bingo_proto_dir = Path(__file__).parent.parent
    for dest in [Path.cwd() / "steam_appid.txt",
                 bingo_proto_dir / "steam_appid.txt"]:
        try:
            dest.write_text(APP_ID)
        except OSError:
            pass


def _bind_funcs() -> None:
    """Set restype/argtypes on every DLL function used by Phase 1."""
    dll = _dll
    vp  = ctypes.c_void_p
    u64 = ctypes.c_uint64
    i32 = ctypes.c_int
    bl  = ctypes.c_bool
    ch  = ctypes.c_char_p

    # ── General ──────────────────────────────────────────────────────────────
    dll.SteamAPI_RunCallbacks.restype  = None
    dll.SteamAPI_RunCallbacks.argtypes = []

    dll.SteamAPI_Shutdown.restype  = None
    dll.SteamAPI_Shutdown.argtypes = []

    # ── ISteamUtils ───────────────────────────────────────────────────────────
    dll.SteamAPI_ISteamUtils_IsAPICallCompleted.restype  = bl
    dll.SteamAPI_ISteamUtils_IsAPICallCompleted.argtypes = [
        vp, u64, ctypes.POINTER(bl)
    ]
    dll.SteamAPI_ISteamUtils_GetAPICallResult.restype  = bl
    dll.SteamAPI_ISteamUtils_GetAPICallResult.argtypes = [
        vp, u64, vp, i32, i32, ctypes.POINTER(bl)
    ]

    # ── ISteamMatchmaking — Phase 0 bindings ──────────────────────────────────
    dll.SteamAPI_ISteamMatchmaking_CreateLobby.restype   = u64
    dll.SteamAPI_ISteamMatchmaking_CreateLobby.argtypes  = [vp, i32, i32]
    dll.SteamAPI_ISteamMatchmaking_JoinLobby.restype     = u64
    dll.SteamAPI_ISteamMatchmaking_JoinLobby.argtypes    = [vp, u64]
    dll.SteamAPI_ISteamMatchmaking_LeaveLobby.restype    = None
    dll.SteamAPI_ISteamMatchmaking_LeaveLobby.argtypes   = [vp, u64]
    dll.SteamAPI_ISteamMatchmaking_SetLobbyData.restype  = bl
    dll.SteamAPI_ISteamMatchmaking_SetLobbyData.argtypes = [vp, u64, ch, ch]
    dll.SteamAPI_ISteamMatchmaking_GetLobbyData.restype  = ch
    dll.SteamAPI_ISteamMatchmaking_GetLobbyData.argtypes = [vp, u64, ch]
    dll.SteamAPI_ISteamMatchmaking_SendLobbyChatMsg.restype  = bl
    dll.SteamAPI_ISteamMatchmaking_SendLobbyChatMsg.argtypes = [vp, u64, vp, i32]
    dll.SteamAPI_ISteamMatchmaking_GetLobbyChatEntry.restype  = i32
    dll.SteamAPI_ISteamMatchmaking_GetLobbyChatEntry.argtypes = [
        vp, u64, i32,
        ctypes.POINTER(u64),
        vp, i32,
        ctypes.POINTER(i32),
    ]
    dll.SteamAPI_ISteamMatchmaking_GetNumLobbyMembers.restype  = i32
    dll.SteamAPI_ISteamMatchmaking_GetNumLobbyMembers.argtypes = [vp, u64]

    # ── ISteamMatchmaking — Phase 1 new bindings ──────────────────────────────
    dll.SteamAPI_ISteamMatchmaking_GetLobbyMemberByIndex.restype  = u64
    dll.SteamAPI_ISteamMatchmaking_GetLobbyMemberByIndex.argtypes = [vp, u64, i32]

    dll.SteamAPI_ISteamMatchmaking_GetLobbyOwner.restype  = u64
    dll.SteamAPI_ISteamMatchmaking_GetLobbyOwner.argtypes = [vp, u64]

    dll.SteamAPI_ISteamMatchmaking_SetLobbyOwner.restype  = bl
    dll.SteamAPI_ISteamMatchmaking_SetLobbyOwner.argtypes = [vp, u64, u64]

    dll.SteamAPI_ISteamMatchmaking_SetLobbyMemberData.restype  = None
    dll.SteamAPI_ISteamMatchmaking_SetLobbyMemberData.argtypes = [vp, u64, ch, ch]

    dll.SteamAPI_ISteamMatchmaking_GetLobbyMemberData.restype  = ch
    dll.SteamAPI_ISteamMatchmaking_GetLobbyMemberData.argtypes = [vp, u64, u64, ch]

    # ── ISteamFriends ─────────────────────────────────────────────────────────
    dll.SteamAPI_ISteamFriends_GetPersonaName.restype        = ch
    dll.SteamAPI_ISteamFriends_GetPersonaName.argtypes       = [vp]
    # Phase 1 new: look up any user's display name
    dll.SteamAPI_ISteamFriends_GetFriendPersonaName.restype  = ch
    dll.SteamAPI_ISteamFriends_GetFriendPersonaName.argtypes = [vp, u64]

    # ── ISteamUser ────────────────────────────────────────────────────────────
    dll.SteamAPI_ISteamUser_GetSteamID.restype  = u64
    dll.SteamAPI_ISteamUser_GetSteamID.argtypes = [vp]


def init(dll_path: str | None = None) -> tuple[bool, str]:
    """
    Load DLL, initialise Steam, acquire interfaces.

    If dll_path is None, attempts:
      1. $STEAM_API_DLL env var
      2. steam_api64.dll beside this file
      3. Default Neon White install path inside Steam's install dir
    Returns (True, "Connected as Name (id)") on success,
            (False, reason) on failure.
    """
    global _dll, _mm, _utils, _friends, player_name, local_steam_id, _ready
    global _pending, _handlers, _watched_lobbies, _watched_data_keys

    # ── Resolve DLL path ──────────────────────────────────────────────────────
    if not dll_path:
        dll_path = os.environ.get("STEAM_API_DLL", "")
    if not dll_path:
        beside = Path(__file__).parent / "steam_api64.dll"
        if beside.exists():
            dll_path = str(beside)
    if not dll_path:
        steam_dir = _find_steam_dir()
        candidate = os.path.join(
            steam_dir, "steamapps", "common", "Neon White",
            "Neon White_Data", "Plugins", "x86_64", "steam_api64.dll"
        )
        if os.path.exists(candidate):
            dll_path = candidate
    if not dll_path:
        return False, ("steam_api64.dll not found — pass --dll, set STEAM_API_DLL, "
                       "or copy the DLL beside smoke_test.py")

    _write_appid(dll_path)

    for d in [_find_steam_dir(), os.path.dirname(os.path.abspath(dll_path))]:
        if d:
            try:
                os.add_dll_directory(d)
            except Exception:
                pass

    try:
        _dll = ctypes.CDLL(dll_path)
    except Exception as e:
        return False, f"Failed to load DLL: {e}"

    _dll.SteamAPI_Init.restype = ctypes.c_bool
    if not _dll.SteamAPI_Init():
        return False, "SteamAPI_Init failed — is Steam running and logged in?"

    _dll.SteamAPI_GetHSteamPipe.restype = ctypes.c_int
    _dll.SteamAPI_GetHSteamUser.restype = ctypes.c_int
    h_pipe = _dll.SteamAPI_GetHSteamPipe()
    h_user = _dll.SteamAPI_GetHSteamUser()

    _dll.SteamInternal_CreateInterface.restype  = ctypes.c_void_p
    _dll.SteamInternal_CreateInterface.argtypes = [ctypes.c_char_p]
    client = (_dll.SteamInternal_CreateInterface(b"SteamClient021") or
              _dll.SteamInternal_CreateInterface(b"SteamClient020"))
    if not client:
        return False, "SteamInternal_CreateInterface failed"

    def _get(method, *names):
        fn = getattr(_dll, method)
        fn.restype  = ctypes.c_void_p
        fn.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
        for n in names:
            p = fn(client, h_user, h_pipe, n)
            if p:
                return p
        return None

    def _get_pipe(method, *names):
        fn = getattr(_dll, method)
        fn.restype  = ctypes.c_void_p
        fn.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
        for n in names:
            p = fn(client, h_pipe, n)
            if p:
                return p
        return None

    _mm = _get("SteamAPI_ISteamClient_GetISteamMatchmaking",
               b"SteamMatchMaking009")
    if not _mm:
        return False, "GetISteamMatchmaking failed"

    _utils = _get_pipe("SteamAPI_ISteamClient_GetISteamUtils",
                       b"SteamUtils010", b"SteamUtils009")

    # SteamFriends017 matches steam_api.py's init_steam — keeping version consistent.
    _friends = _get("SteamAPI_ISteamClient_GetISteamFriends",
                    b"SteamFriends017", b"SteamFriends015")

    isteam_user = _get("SteamAPI_ISteamClient_GetISteamUser",
                       b"SteamUser023", b"SteamUser021")

    _bind_funcs()

    if isteam_user:
        local_steam_id = _dll.SteamAPI_ISteamUser_GetSteamID(isteam_user)
    if _friends:
        nb = _dll.SteamAPI_ISteamFriends_GetPersonaName(_friends)
        player_name = nb.decode("utf-8", errors="replace") if nb else "Unknown"

    _dll.SteamAPI_RunCallbacks()
    time.sleep(0.5)

    _ready = True
    return True, f"Connected as {player_name} ({local_steam_id})"


def shutdown() -> None:
    """Shut down Steamworks cleanly."""
    global _ready
    if _dll:
        _dll.SteamAPI_Shutdown()
    _ready = False


# ── Handler registration ─────────────────────────────────────────────────────

def register(callback_id: int, handler: Callable) -> None:
    """
    Attach a Python handler that fires during pump().

    Supported callback_ids: LOBBY_DATA_UPDATE, LOBBY_CHAT_MSG, LOBBY_CHAT_UPDATE.
    Polling because vtable callback registration doesn't work with this DLL —
    see Phase 0 session log.
    """
    _handlers.setdefault(callback_id, []).append(handler)


# ── Lobby watch (enables polling) ────────────────────────────────────────────

def _ensure_watched(lobby_id: int) -> None:
    """Initialise per-lobby polling state on first access."""
    if lobby_id not in _watched_lobbies:
        _watched_lobbies[lobby_id] = {
            "next_chat_idx": 0,
            "last_data":     {},
            "last_members":  set(),
        }
    if lobby_id not in _watched_data_keys:
        _watched_data_keys[lobby_id] = set()


def watch_lobby(lobby_id: int, data_keys: tuple = ("counter",)) -> None:
    """
    Start polling lobby_id.  Kept for Phase 0 compatibility.
    Phase 1 callers can call this explicitly or just call create_lobby()/join_lobby()
    which call it automatically.
    """
    _ensure_watched(lobby_id)
    _watched_data_keys[lobby_id] = set(data_keys)


# ── Pump ────────────────────────────────────────────────────────────────────

def pump(once: bool = False) -> None:
    """
    One dispatch tick.

    1. Polls async call results (CreateLobby / JoinLobby).
    2. Calls SteamAPI_RunCallbacks() for general Steam housekeeping.
    3. Polls chat by index for LobbyChatMsg_t.
    4. Polls lobby data diffs for LobbyDataUpdate_t.
    5. Polls member-set diffs for synthesized LobbyChatUpdate_t.
       (vtable callback registration doesn't work with this DLL — see Phase 0)

    `once` param is accepted for forward-compat with the public API but has no
    effect; one tick is always exactly one tick.
    """
    if _pending and _utils:
        for call_handle, (cb_id, struct_cls, fn) in list(_pending.items()):
            failed = ctypes.c_bool(False)
            if _dll.SteamAPI_ISteamUtils_IsAPICallCompleted(
                    _utils, call_handle, ctypes.byref(failed)):
                del _pending[call_handle]
                if not failed.value:
                    result = struct_cls()
                    io_fail = ctypes.c_bool(False)
                    ok = _dll.SteamAPI_ISteamUtils_GetAPICallResult(
                        _utils, call_handle,
                        ctypes.byref(result), ctypes.sizeof(result),
                        cb_id, ctypes.byref(io_fail),
                    )
                    if ok and not io_fail.value:
                        fn(result)

    _dll.SteamAPI_RunCallbacks()

    for lid in list(_watched_lobbies.keys()):
        _poll_chat(lid)
        _poll_data(lid)
        _poll_members(lid)


def _poll_chat(lid: int) -> None:
    """Read any new chat entries by sequential index."""
    handlers = _handlers.get(LOBBY_CHAT_MSG, [])
    if not handlers:
        return
    state  = _watched_lobbies[lid]
    buf        = ctypes.create_string_buffer(4096)
    sender     = ctypes.c_uint64(0)
    entry_type = ctypes.c_int(0)
    while True:
        length = _dll.SteamAPI_ISteamMatchmaking_GetLobbyChatEntry(
            _mm, lid, state["next_chat_idx"],
            ctypes.byref(sender), buf, ctypes.sizeof(buf),
            ctypes.byref(entry_type),
        )
        if length <= 0:
            break
        msg = LobbyChatMsg_t()
        msg.lobby_steam_id  = lid
        msg.user_steam_id   = sender.value
        msg.chat_entry_type = entry_type.value & 0xFF
        msg.chat_id         = state["next_chat_idx"]
        state["next_chat_idx"] += 1
        for fn in handlers:
            fn(msg)


def _poll_data(lid: int) -> None:
    """Fire LOBBY_DATA_UPDATE handlers when a watched key changes value."""
    handlers = _handlers.get(LOBBY_DATA_UPDATE, [])
    if not handlers:
        return
    state = _watched_lobbies[lid]
    for key in _watched_data_keys.get(lid, set()):
        val = get_lobby_data(lid, key)
        if state["last_data"].get(key) != val:
            state["last_data"][key] = val
            upd = LobbyDataUpdate_t()
            upd.lobby_steam_id  = lid
            upd.member_steam_id = 0
            upd.success         = 1
            for fn in handlers:
                fn(upd)


def _poll_members(lid: int) -> None:
    """
    Diff current member list against last-seen to synthesize LobbyChatUpdate_t.

    Polling because vtable callback registration (callback ID 506) doesn't work
    with this DLL build — third instance of this pattern, see Phase 0 session log.
    Stage 2's leader-transfer logic will consume these synthesized events.
    """
    handlers = _handlers.get(LOBBY_CHAT_UPDATE, [])
    if not handlers:
        return
    state   = _watched_lobbies[lid]
    current = set(get_lobby_members(lid))
    last    = state["last_members"]
    if current == last:
        return

    for uid in current - last:
        evt = LobbyChatUpdate_t()
        evt.steam_id_lobby           = lid
        evt.steam_id_user_changed    = uid
        evt.steam_id_making_change   = uid
        evt.chat_member_state_change = CHAT_MEMBER_ENTERED
        for fn in handlers:
            fn(evt)

    for uid in last - current:
        # Can't distinguish leave/disconnect/kick without real callback; Stage 2
        # only needs "they're gone" — report as LEFT (0x02).
        evt = LobbyChatUpdate_t()
        evt.steam_id_lobby           = lid
        evt.steam_id_user_changed    = uid
        evt.steam_id_making_change   = uid
        evt.chat_member_state_change = CHAT_MEMBER_LEFT
        for fn in handlers:
            fn(evt)

    state["last_members"] = current


# ── Lobby operations ─────────────────────────────────────────────────────────

def create_lobby(max_members: int = 8) -> int:
    """
    Blocking create: returns lobby_id on success, 0 on failure.
    Waits up to 10 s for LobbyCreated_t.
    """
    result_box = [0]
    done_box   = [False]

    def _on_created(r: LobbyCreated_t) -> None:
        if r.result == 1:   # k_EResultOK
            result_box[0] = r.lobby_steam_id
        done_box[0] = True

    call = _dll.SteamAPI_ISteamMatchmaking_CreateLobby(
        _mm, LOBBY_TYPE_PUBLIC, max_members
    )
    _pending[call] = (LOBBY_CREATED, LobbyCreated_t, _on_created)

    deadline = time.time() + 10.0
    while not done_box[0] and time.time() < deadline:
        pump()
        time.sleep(0.1)

    if result_box[0]:
        _ensure_watched(result_box[0])
    return result_box[0]


def join_lobby(lobby_id: int) -> bool:
    """Blocking join: returns True on success. Waits up to 10 s for LobbyEnter_t."""
    result_box = [False]
    done_box   = [False]

    def _on_join(r: LobbyEnter_t) -> None:
        result_box[0] = (r.chat_room_response == CHAT_ROOM_SUCCESS)
        done_box[0]   = True

    call = _dll.SteamAPI_ISteamMatchmaking_JoinLobby(_mm, lobby_id)
    _pending[call] = (LOBBY_ENTER, LobbyEnter_t, _on_join)

    deadline = time.time() + 10.0
    while not done_box[0] and time.time() < deadline:
        pump()
        time.sleep(0.1)

    if result_box[0]:
        _ensure_watched(lobby_id)
    return result_box[0]


def leave_lobby(lobby_id: int) -> None:
    _dll.SteamAPI_ISteamMatchmaking_LeaveLobby(_mm, lobby_id)
    _watched_lobbies.pop(lobby_id, None)
    _watched_data_keys.pop(lobby_id, None)


def set_lobby_data(lobby_id: int, key: str, value: str) -> bool:
    return bool(_dll.SteamAPI_ISteamMatchmaking_SetLobbyData(
        _mm, lobby_id, key.encode(), value.encode()
    ))


def get_lobby_data(lobby_id: int, key: str) -> str:
    raw = _dll.SteamAPI_ISteamMatchmaking_GetLobbyData(
        _mm, lobby_id, key.encode()
    )
    return raw.decode("utf-8", errors="replace") if raw else ""


def get_lobby_owner(lobby_id: int) -> int:
    """Return SteamID64 of the current lobby host."""
    return _dll.SteamAPI_ISteamMatchmaking_GetLobbyOwner(_mm, lobby_id)


def set_lobby_owner(lobby_id: int, new_owner: int) -> bool:
    """
    Transfer lobby host to new_owner.
    Only the current host may call this.  Returns True on success.
    """
    return bool(_dll.SteamAPI_ISteamMatchmaking_SetLobbyOwner(_mm, lobby_id, new_owner))


def get_lobby_members(lobby_id: int) -> list[int]:
    """Return list of SteamID64s currently in the lobby."""
    count = _dll.SteamAPI_ISteamMatchmaking_GetNumLobbyMembers(_mm, lobby_id)
    return [
        _dll.SteamAPI_ISteamMatchmaking_GetLobbyMemberByIndex(_mm, lobby_id, i)
        for i in range(count)
    ]


def set_lobby_member_data(lobby_id: int, key: str, value: str) -> None:
    """
    Write OWN per-member data.
    No setter for other members exists in the Steamworks SDK.
    """
    _dll.SteamAPI_ISteamMatchmaking_SetLobbyMemberData(
        _mm, lobby_id, key.encode(), value.encode()
    )


def get_lobby_member_data(lobby_id: int, user: int, key: str) -> str:
    """Read per-member data for any user in the lobby."""
    raw = _dll.SteamAPI_ISteamMatchmaking_GetLobbyMemberData(
        _mm, lobby_id, user, key.encode()
    )
    return raw.decode("utf-8", errors="replace") if raw else ""


def send_chat_msg(lobby_id: int, body: bytes) -> bool:
    """Send raw bytes as a lobby chat message."""
    return bool(_dll.SteamAPI_ISteamMatchmaking_SendLobbyChatMsg(
        _mm, lobby_id, body, len(body)
    ))


def persona_name(user: int) -> str:
    """
    Return UTF-8 display name for user, or str(user) if not resolvable.
    Uses GetFriendPersonaName — works for lobby members (Steam caches nearby
    users automatically even if not in the friends list).
    """
    if not _friends:
        return str(user)
    raw = _dll.SteamAPI_ISteamFriends_GetFriendPersonaName(_friends, user)
    if not raw:
        return str(user)
    name = raw.decode("utf-8", errors="replace")
    return name if name else str(user)
