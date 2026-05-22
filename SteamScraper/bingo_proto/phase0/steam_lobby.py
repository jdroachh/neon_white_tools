"""
steam_lobby — Steam Matchmaking ctypes bindings + polling-based callback dispatch.

Direct event callbacks (LobbyDataUpdate, LobbyChatMsg) are delivered by
polling ISteamMatchmaking rather than SteamAPI_RegisterCallback, which proved
incompatible with the DLL version bundled with Neon White.

  - LobbyDataUpdate: GetLobbyData compared against last-seen value each pump tick.
  - LobbyChatMsg:    GetLobbyChatEntry polled by incrementing index each pump tick.
  - Async results:   IsAPICallCompleted + GetAPICallResult (same as steam_api.py).

Quick-start:
    lobby = SteamLobby()
    ok, msg = lobby.init(r"path/to/steam_api64.dll")
    lobby.register(LOBBY_CHAT_MSG, my_handler)
    lobby.create_lobby(on_created=lambda r: lobby.watch_lobby(r.lobby_steam_id))
    while True:
        lobby.pump()
        time.sleep(0.1)
"""
import ctypes
import os
import time
from datetime import datetime
from pathlib import Path

APP_ID = "1533420"

# ── Callback IDs (isteammatchmaking.h) ───────────────────────────────────────
LOBBY_CREATED        = 513
LOBBY_ENTER          = 504
LOBBY_DATA_UPDATE    = 505
LOBBY_CHAT_MSG       = 507

# ── ELobbyType ───────────────────────────────────────────────────────────────
LOBBY_TYPE_PRIVATE      = 0
LOBBY_TYPE_FRIENDS_ONLY = 1
LOBBY_TYPE_PUBLIC       = 2
LOBBY_TYPE_INVISIBLE    = 4

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


# ── SteamLobby ───────────────────────────────────────────────────────────────

class SteamLobby:
    """
    Thin wrapper around ISteamMatchmaking.

    All Steam API calls and pump() must run from the same thread that
    called init().
    """

    def __init__(self):
        self._dll       = None
        self._mm        = None   # ISteamMatchmaking
        self._utils     = None   # ISteamUtils
        self._friends   = None   # ISteamFriends
        self._pending   = {}     # SteamAPICall_t → (cb_id, struct_class, fn)
        self._handlers  = {}     # callback_id → list[fn]
        # polling state — set by watch_lobby()
        self._watched_lobby  = 0
        self._next_chat_idx  = 0
        self._last_data      = {}  # key → last seen value
        self._watched_keys   = set()
        self.player_name     = "Unknown"
        self.local_steam_id  = 0
        self.ready           = False

    # ── Init ─────────────────────────────────────────────────────────────────

    def init(self, dll_path: str):
        """Load DLL, initialise Steam, acquire interfaces. Returns (ok, msg)."""
        self._write_appid(dll_path)

        for d in [_find_steam_dir(), os.path.dirname(os.path.abspath(dll_path))]:
            if d:
                try:
                    os.add_dll_directory(d)
                except Exception:
                    pass

        try:
            self._dll = ctypes.CDLL(dll_path)
        except Exception as e:
            return False, f"Failed to load DLL: {e}"

        self._dll.SteamAPI_Init.restype = ctypes.c_bool
        if not self._dll.SteamAPI_Init():
            return False, "SteamAPI_Init failed — is Steam running and logged in?"

        self._dll.SteamAPI_GetHSteamPipe.restype = ctypes.c_int
        self._dll.SteamAPI_GetHSteamUser.restype = ctypes.c_int
        h_pipe = self._dll.SteamAPI_GetHSteamPipe()
        h_user = self._dll.SteamAPI_GetHSteamUser()

        self._dll.SteamInternal_CreateInterface.restype  = ctypes.c_void_p
        self._dll.SteamInternal_CreateInterface.argtypes = [ctypes.c_char_p]
        client = (self._dll.SteamInternal_CreateInterface(b"SteamClient021") or
                  self._dll.SteamInternal_CreateInterface(b"SteamClient020"))
        if not client:
            return False, "SteamInternal_CreateInterface failed"

        def _get(method, *names):
            fn = getattr(self._dll, method)
            fn.restype  = ctypes.c_void_p
            fn.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
            for n in names:
                p = fn(client, h_user, h_pipe, n)
                if p:
                    return p
            return None

        def _get_pipe(method, *names):
            fn = getattr(self._dll, method)
            fn.restype  = ctypes.c_void_p
            fn.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
            for n in names:
                p = fn(client, h_pipe, n)
                if p:
                    return p
            return None

        self._mm = _get("SteamAPI_ISteamClient_GetISteamMatchmaking",
                        b"SteamMatchMaking009")
        if not self._mm:
            return False, "GetISteamMatchmaking failed"

        self._utils = _get_pipe("SteamAPI_ISteamClient_GetISteamUtils",
                                b"SteamUtils010", b"SteamUtils009")

        self._friends = _get("SteamAPI_ISteamClient_GetISteamFriends",
                             b"SteamFriends017", b"SteamFriends015")

        isteam_user = _get("SteamAPI_ISteamClient_GetISteamUser",
                           b"SteamUser023", b"SteamUser021")

        self._bind_funcs()

        if isteam_user:
            self.local_steam_id = self._dll.SteamAPI_ISteamUser_GetSteamID(isteam_user)
        if self._friends:
            nb = self._dll.SteamAPI_ISteamFriends_GetPersonaName(self._friends)
            self.player_name = nb.decode("utf-8", errors="replace") if nb else "Unknown"

        self._dll.SteamAPI_RunCallbacks()
        time.sleep(0.5)

        self.ready = True
        return True, f"Connected as {self.player_name} ({self.local_steam_id})"

    @staticmethod
    def _write_appid(dll_path: str):
        bingo_proto_dir = Path(__file__).parent.parent
        for dest in [Path.cwd() / "steam_appid.txt",
                     bingo_proto_dir / "steam_appid.txt"]:
            try:
                dest.write_text(APP_ID)
            except OSError:
                pass

    # ── Function bindings ────────────────────────────────────────────────────

    def _bind_funcs(self):
        dll = self._dll
        vp  = ctypes.c_void_p
        u64 = ctypes.c_uint64
        i32 = ctypes.c_int
        bl  = ctypes.c_bool
        ch  = ctypes.c_char_p

        dll.SteamAPI_RunCallbacks.restype  = None
        dll.SteamAPI_RunCallbacks.argtypes = []

        dll.SteamAPI_ISteamUtils_IsAPICallCompleted.restype  = bl
        dll.SteamAPI_ISteamUtils_IsAPICallCompleted.argtypes = [
            vp, u64, ctypes.POINTER(bl)
        ]
        dll.SteamAPI_ISteamUtils_GetAPICallResult.restype  = bl
        dll.SteamAPI_ISteamUtils_GetAPICallResult.argtypes = [
            vp, u64, vp, i32, i32, ctypes.POINTER(bl)
        ]

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

        dll.SteamAPI_ISteamFriends_GetPersonaName.restype        = ch
        dll.SteamAPI_ISteamFriends_GetPersonaName.argtypes       = [vp]
        dll.SteamAPI_ISteamFriends_GetFriendPersonaName.restype  = ch
        dll.SteamAPI_ISteamFriends_GetFriendPersonaName.argtypes = [vp, u64]

        dll.SteamAPI_ISteamUser_GetSteamID.restype  = u64
        dll.SteamAPI_ISteamUser_GetSteamID.argtypes = [vp]

        dll.SteamAPI_Shutdown.restype  = None
        dll.SteamAPI_Shutdown.argtypes = []

    # ── Handler registration ─────────────────────────────────────────────────

    def register(self, callback_id: int, fn):
        """Register a Python handler for LOBBY_DATA_UPDATE or LOBBY_CHAT_MSG."""
        self._handlers.setdefault(callback_id, []).append(fn)

    # ── Lobby watch (enables polling) ────────────────────────────────────────

    def watch_lobby(self, lobby_id: int, data_keys=("counter",)):
        """
        Start polling lobby_id for chat messages and lobby-data changes.
        Call this once you have a valid lobby ID (from on_created or on_join).
        data_keys: which GetLobbyData keys to watch for LOBBY_DATA_UPDATE.
        """
        self._watched_lobby = lobby_id
        self._next_chat_idx = 0
        self._watched_keys  = set(data_keys)
        self._last_data     = {}

    # ── Pump ────────────────────────────────────────────────────────────────

    def pump(self):
        """
        Process one frame.  Call every ~100 ms from the init() thread.

        1. Polls async call results (CreateLobby / JoinLobby).
        2. Calls SteamAPI_RunCallbacks() for general Steam housekeeping.
        3. Polls chat and data changes on the watched lobby.
        """
        if self._pending and self._utils:
            for call_handle, (cb_id, struct_cls, fn) in list(self._pending.items()):
                failed = ctypes.c_bool(False)
                if self._dll.SteamAPI_ISteamUtils_IsAPICallCompleted(
                        self._utils, call_handle, ctypes.byref(failed)):
                    del self._pending[call_handle]
                    if not failed.value:
                        result = struct_cls()
                        io_fail = ctypes.c_bool(False)
                        ok = self._dll.SteamAPI_ISteamUtils_GetAPICallResult(
                            self._utils, call_handle,
                            ctypes.byref(result), ctypes.sizeof(result),
                            cb_id, ctypes.byref(io_fail),
                        )
                        if ok and not io_fail.value:
                            fn(result)

        self._dll.SteamAPI_RunCallbacks()

        if self._watched_lobby:
            self._poll_chat()
            self._poll_data()

    def _poll_chat(self):
        """Read any new chat entries by sequential index."""
        handlers = self._handlers.get(LOBBY_CHAT_MSG, [])
        if not handlers:
            return
        lid = self._watched_lobby
        buf        = ctypes.create_string_buffer(4096)
        sender     = ctypes.c_uint64(0)
        entry_type = ctypes.c_int(0)
        while True:
            length = self._dll.SteamAPI_ISteamMatchmaking_GetLobbyChatEntry(
                self._mm, lid, self._next_chat_idx,
                ctypes.byref(sender), buf, ctypes.sizeof(buf),
                ctypes.byref(entry_type),
            )
            if length <= 0:
                break
            msg = LobbyChatMsg_t()
            msg.lobby_steam_id  = lid
            msg.user_steam_id   = sender.value
            msg.chat_entry_type = entry_type.value & 0xFF
            msg.chat_id         = self._next_chat_idx
            self._next_chat_idx += 1
            for fn in handlers:
                fn(msg)

    def _poll_data(self):
        """Fire LOBBY_DATA_UPDATE handlers when a watched key changes value."""
        handlers = self._handlers.get(LOBBY_DATA_UPDATE, [])
        if not handlers:
            return
        lid = self._watched_lobby
        for key in self._watched_keys:
            val = self.get_lobby_data(lid, key)
            if self._last_data.get(key) != val:
                self._last_data[key] = val
                upd = LobbyDataUpdate_t()
                upd.lobby_steam_id  = lid
                upd.member_steam_id = 0
                upd.success         = 1
                for fn in handlers:
                    fn(upd)

    # ── Lobby operations ─────────────────────────────────────────────────────

    def create_lobby(self, lobby_type=LOBBY_TYPE_PUBLIC, max_members=8, on_created=None):
        call = self._dll.SteamAPI_ISteamMatchmaking_CreateLobby(self._mm, lobby_type, max_members)
        if on_created:
            self._pending[call] = (LOBBY_CREATED, LobbyCreated_t, on_created)
        return call

    def join_lobby(self, lobby_id: int, on_join=None):
        call = self._dll.SteamAPI_ISteamMatchmaking_JoinLobby(self._mm, lobby_id)
        if on_join:
            self._pending[call] = (LOBBY_ENTER, LobbyEnter_t, on_join)
        return call

    def leave_lobby(self, lobby_id: int):
        self._dll.SteamAPI_ISteamMatchmaking_LeaveLobby(self._mm, lobby_id)

    def set_lobby_data(self, lobby_id: int, key: str, value: str) -> bool:
        return bool(self._dll.SteamAPI_ISteamMatchmaking_SetLobbyData(
            self._mm, lobby_id, key.encode(), value.encode()
        ))

    def get_lobby_data(self, lobby_id: int, key: str) -> str:
        raw = self._dll.SteamAPI_ISteamMatchmaking_GetLobbyData(
            self._mm, lobby_id, key.encode()
        )
        return raw.decode("utf-8", errors="replace") if raw else ""

    def send_chat_msg(self, lobby_id: int, msg: str) -> bool:
        data = msg.encode("utf-8")
        return bool(self._dll.SteamAPI_ISteamMatchmaking_SendLobbyChatMsg(
            self._mm, lobby_id, data, len(data)
        ))

    def get_chat_entry(self, lobby_id: int, chat_id: int):
        """Returns (sender_steam_id: int, body: str).  Returns (0, '') on error."""
        buf        = ctypes.create_string_buffer(4096)
        sender     = ctypes.c_uint64(0)
        entry_type = ctypes.c_int(0)
        length = self._dll.SteamAPI_ISteamMatchmaking_GetLobbyChatEntry(
            self._mm, lobby_id, chat_id,
            ctypes.byref(sender), buf, ctypes.sizeof(buf), ctypes.byref(entry_type),
        )
        if length <= 0:
            return 0, ""
        return sender.value, buf.raw[:length].decode("utf-8", errors="replace")

    def get_member_count(self, lobby_id: int) -> int:
        return self._dll.SteamAPI_ISteamMatchmaking_GetNumLobbyMembers(self._mm, lobby_id)

    def get_friend_name(self, steam_id: int) -> str:
        if not self._friends:
            return str(steam_id)
        nb = self._dll.SteamAPI_ISteamFriends_GetFriendPersonaName(self._friends, steam_id)
        return nb.decode("utf-8", errors="replace") if nb else str(steam_id)

    def shutdown(self):
        if self._dll:
            self._dll.SteamAPI_Shutdown()
        self.ready = False
