"""
Phase 1 smoke test — exercises every new binding introduced in steam_lobby.py.

Run from SteamScraper/bingo_proto/ (so steam_appid.txt is found):

    python -u phase1/smoke_test.py --host [--dll PATH]
    python -u phase1/smoke_test.py --join <lobby_id> [--dll PATH]

Each test prints:
    PASS: <description>   or   FAIL: <reason>
with a leading timestamp so you can eyeball latency from the log.
"""
import argparse
import sys
import time
from pathlib import Path

# ── ensure the phase1 package is importable regardless of cwd ────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))   # SteamScraper/
sys.path.insert(0, str(Path(__file__).parent))                 # phase1/

import steam_lobby as sl

# ── pretty timestamps ─────────────────────────────────────────────────────────
def ts() -> str:
    return time.strftime("%H:%M:%S")

def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)

def passed(desc: str) -> None:
    print(f"[{ts()}] PASS: {desc}", flush=True)

def failed(desc: str) -> None:
    print(f"[{ts()}] FAIL: {desc}", flush=True)


# ── Host-side test suite ──────────────────────────────────────────────────────

def run_host(dll_path: str | None) -> None:
    """
    Tests performed (in order):
      T1  init() succeeds
      T2  create_lobby(8) returns nonzero lobby ID
      T3  get_lobby_owner() returns local SteamID
      T4  get_lobby_members() contains local SteamID
      T5  persona_name(local_id) returns non-empty string
      T6  set_lobby_member_data / get_lobby_member_data round-trip
      T7  synthesized LobbyChatUpdate_t fires when joiner arrives (60 s timeout)
      T8  get_lobby_members() length is 2 after joiner appears
      T9  synthesized LobbyChatUpdate_t fires when joiner leaves (30 s grace)
      T10 shutdown() completes cleanly
    """

    # ── T1: init ──────────────────────────────────────────────────────────────
    ok, msg = sl.init(dll_path)
    if ok:
        passed(f"init() — {msg}")
    else:
        failed(f"init() — {msg}")
        sys.exit(1)

    local_id = sl.local_steam_id

    # ── T2: create lobby ──────────────────────────────────────────────────────
    log("create_lobby(8) — waiting for LobbyCreated_t …")
    lobby = sl.create_lobby(8)
    if lobby:
        passed(f"create_lobby → lobby ID: {lobby}  (share this with joiner)")
    else:
        failed("create_lobby returned 0")
        sl.shutdown()
        sys.exit(1)

    # ── T3: get_lobby_owner ───────────────────────────────────────────────────
    owner = sl.get_lobby_owner(lobby)
    if owner == local_id:
        passed(f"get_lobby_owner() == local SteamID ({local_id})")
    else:
        failed(f"get_lobby_owner() returned {owner}, expected {local_id}")

    # ── T4: get_lobby_members ─────────────────────────────────────────────────
    members = sl.get_lobby_members(lobby)
    if local_id in members:
        passed(f"get_lobby_members() contains local SteamID  members={members}")
    else:
        failed(f"get_lobby_members() did not contain {local_id}  got={members}")

    # ── T5: persona_name ──────────────────────────────────────────────────────
    name = sl.persona_name(local_id)
    if name and name != str(local_id):
        passed(f"persona_name({local_id}) = {name!r}")
    else:
        failed(f"persona_name returned {name!r} — expected a display name")

    # ── T6: set/get member data ───────────────────────────────────────────────
    sl.set_lobby_member_data(lobby, "team", "0")
    # Per-member data needs a pump tick to propagate internally
    for _ in range(5):
        sl.pump()
        time.sleep(0.1)
    got = sl.get_lobby_member_data(lobby, local_id, "team")
    if got == "0":
        passed('set_lobby_member_data("team","0") → get_lobby_member_data == "0"')
    else:
        failed(f'get_lobby_member_data returned {got!r}, expected "0"')

    # ── T7: wait for joiner via synthesized LobbyChatUpdate_t ────────────────
    log("Waiting up to 60 s for joiner …")
    joiner_id_box = [0]
    join_event_seen = [False]

    def on_member_change(evt: sl.LobbyChatUpdate_t) -> None:
        if (evt.steam_id_user_changed != local_id and
                evt.chat_member_state_change & sl.CHAT_MEMBER_ENTERED):
            joiner_id_box[0]    = evt.steam_id_user_changed
            join_event_seen[0]  = True

    sl.register(sl.LOBBY_CHAT_UPDATE, on_member_change)

    # Seed last_members so the diff fires when joiner arrives
    sl._watched_lobbies[lobby]["last_members"] = set(sl.get_lobby_members(lobby))

    deadline = time.time() + 60.0
    last_diag = 0.0
    while not join_event_seen[0] and time.time() < deadline:
        sl.pump()
        now = time.time()
        if now - last_diag >= 2.0:
            # DIAG: show what host actually sees while waiting for joiner.
            # Helps distinguish "Steam cache stale" from "diff logic broken".
            n = sl._dll.SteamAPI_ISteamMatchmaking_GetNumLobbyMembers(sl._mm, lobby)
            members = sl.get_lobby_members(lobby)
            print(f"[DIAG {time.strftime('%H:%M:%S')}] GetNumLobbyMembers={n}  get_lobby_members={members}")
            last_diag = now
        time.sleep(0.1)

    if join_event_seen[0]:
        passed(f"detected joiner via synthesized LobbyChatUpdate_t  id={joiner_id_box[0]}")
    else:
        failed("timed out (60 s) waiting for joiner — did the joiner run --join <id>?")

    joiner_id = joiner_id_box[0]

    # ── T8: member count after joiner arrives ─────────────────────────────────
    members_now = sl.get_lobby_members(lobby)
    if len(members_now) == 2:
        passed(f"get_lobby_members() length is 2  members={members_now}")
    else:
        failed(f"expected 2 members, got {len(members_now)}  members={members_now}")

    # ── T9: wait for joiner leave via synthesized LobbyChatUpdate_t ──────────
    # Cache lag is ~1s in both directions (measured 2026-05-23 against the
    # bundled DLL via cross-referenced host+joiner logs). 30s is comfortable.
    log("Waiting up to 30 s for joiner to leave …")
    leave_event_seen = [False]

    def on_member_leave(evt: sl.LobbyChatUpdate_t) -> None:
        if (joiner_id and evt.steam_id_user_changed == joiner_id and
                evt.chat_member_state_change & sl.CHAT_MEMBER_LEFT):
            leave_event_seen[0] = True

    sl.register(sl.LOBBY_CHAT_UPDATE, on_member_leave)

    deadline = time.time() + 30.0
    last_diag = 0.0
    while not leave_event_seen[0] and time.time() < deadline:
        sl.pump()
        now = time.time()
        if now - last_diag >= 2.0:
            n = sl._dll.SteamAPI_ISteamMatchmaking_GetNumLobbyMembers(sl._mm, lobby)
            members = sl.get_lobby_members(lobby)
            print(f"[DIAG {time.strftime('%H:%M:%S')}] GetNumLobbyMembers={n}  get_lobby_members={members}")
            last_diag = now
        time.sleep(0.1)

    if leave_event_seen[0]:
        passed("detected joiner leave via synthesized LobbyChatUpdate_t (state=0x02)")
    else:
        failed("timed out (30 s) waiting for joiner to leave")

    # ── T10: shutdown ─────────────────────────────────────────────────────────
    try:
        sl.leave_lobby(lobby)
        sl.shutdown()
        passed("shutdown() completed cleanly")
    except Exception as e:
        failed(f"shutdown() raised {e}")


# ── Joiner-side test suite ────────────────────────────────────────────────────

def run_joiner(lobby_id: int, dll_path: str | None) -> None:
    """
    Joiner subset:
      J1  init() succeeds
      J2  join_lobby(lobby_id) succeeds
      J3  persona_name(host_id) returns non-empty string
      J4  set_lobby_member_data("team", "1") then pump
      J5  send_chat_msg b"joiner-online"
      J6  sleep 10 s (gives host T8 + T9 time; ~1s cache lag each direction)
      J7  leave_lobby + shutdown
    """
    # ── J1 ────────────────────────────────────────────────────────────────────
    ok, msg = sl.init(dll_path)
    if ok:
        passed(f"init() — {msg}")
    else:
        failed(f"init() — {msg}")
        sys.exit(1)

    # ── J2 ────────────────────────────────────────────────────────────────────
    log(f"join_lobby({lobby_id}) — waiting for LobbyEnter_t …")
    joined = sl.join_lobby(lobby_id)
    if joined:
        passed(f"join_lobby({lobby_id}) succeeded")
    else:
        failed(f"join_lobby({lobby_id}) failed")
        sl.shutdown()
        sys.exit(1)

    # ── J3: host display name ─────────────────────────────────────────────────
    host_id = sl.get_lobby_owner(lobby_id)
    host_name = sl.persona_name(host_id)
    if host_name and host_name != str(host_id):
        passed(f"persona_name(host={host_id}) = {host_name!r}")
    else:
        # Not a hard failure — GetFriendPersonaName can return "" for non-friends
        # until Steam's presence cache is warmed up.
        log(f"WARN: persona_name returned {host_name!r} for host {host_id} "
            "(may be empty for non-friends before cache warms)")

    # ── J4: set own member data ───────────────────────────────────────────────
    sl.set_lobby_member_data(lobby_id, "team", "1")
    for _ in range(5):
        sl.pump()
        time.sleep(0.1)
    passed('set_lobby_member_data("team","1") sent')

    # ── J5: send chat message ─────────────────────────────────────────────────
    ok_send = sl.send_chat_msg(lobby_id, b"joiner-online")
    if ok_send:
        passed('send_chat_msg(b"joiner-online") ok')
    else:
        failed('send_chat_msg(b"joiner-online") returned False')

    # ── J6: stay in lobby for 10 s (host tests T8/T9 during this window) ─────
    # Cache lag is ~1s each direction (measured 2026-05-23). 10s gives the host
    # plenty of room for join_visible + T8 + leave_visible inside its T9 window.
    log("Staying in lobby for 10 s so host can run T8 + T9 …")
    deadline = time.time() + 10.0
    while time.time() < deadline:
        sl.pump()
        time.sleep(0.1)

    # ── J7: leave and shutdown ────────────────────────────────────────────────
    log("10 s elapsed — leaving lobby …")
    try:
        sl.leave_lobby(lobby_id)
        sl.shutdown()
        passed("leave_lobby + shutdown completed cleanly")
    except Exception as e:
        failed(f"leave/shutdown raised {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 1 Bingo smoke test — bindings only, no board/protocol."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--host", action="store_true",
                      help="Create lobby and run host-side tests.")
    mode.add_argument("--join", metavar="LOBBY_ID", type=int,
                      help="Join existing lobby (from host output) and run joiner-side tests.")
    parser.add_argument("--dll", metavar="PATH", default=None,
                        help="Path to steam_api64.dll (optional; auto-detected if omitted).")
    args = parser.parse_args()

    if args.host:
        run_host(args.dll)
    else:
        run_joiner(args.join, args.dll)


if __name__ == "__main__":
    main()
