"""
Bingo Mode Phase 0 — Steam Lobby smoke test CLI.

Usage (run from SteamScraper/bingo_proto/):
    python phase0/main.py --host
    python phase0/main.py --join <lobby_id>
    python phase0/main.py --host --dll path/to/steam_api64.dll

DLL search order:
  1. --dll argument
  2. STEAM_API_DLL environment variable
  3. Neon White default install path
  4. steam_api64.dll in cwd
"""
import argparse
import os
import sys
import time
from pathlib import Path

# Allow running as `python phase0/main.py` from bingo_proto/ or as `python main.py` from phase0/
sys.path.insert(0, str(Path(__file__).parent))

from steam_lobby import (
    SteamLobby, ts,
    LOBBY_CHAT_MSG, LOBBY_DATA_UPDATE,
    LOBBY_TYPE_PUBLIC, CHAT_ROOM_SUCCESS,
)

_DEFAULT_DLL = (
    r"C:\Program Files (x86)\Steam\steamapps\common"
    r"\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll"
)


# ── DLL discovery ────────────────────────────────────────────────────────────

def find_dll() -> str | None:
    for candidate in [
        os.environ.get("STEAM_API_DLL"),
        _DEFAULT_DLL,
        str(Path(__file__).parent.parent / "steam_api64.dll"),  # bingo_proto/
        "steam_api64.dll",
    ]:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


# ── Arg parsing ──────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Steam Lobby smoke test (Phase 0)")
    p.add_argument("--dll", help="Path to steam_api64.dll (or set STEAM_API_DLL)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--host",       action="store_true", help="Create a lobby (host mode)")
    g.add_argument("--join", metavar="LOBBY_ID",         help="Join lobby by ID")
    return p.parse_args()


# ── Mode setup — registers callbacks, returns mutable state ─────────────────

def setup_mode(lobby: SteamLobby, args) -> dict:
    """
    Register callbacks and kick off the initial async Steam call.
    Returns a state dict shared between check_timers() and cleanup().
    """
    state = {
        "mode":          "host" if args.host else "join",
        "lobby_id":      None,
        "joined":        False,
        "counter":       0,
        "ping_n":        0,
        "last_counter_t": time.monotonic(),
        "last_ping_t":    time.monotonic(),
        "stop":          False,
    }

    if args.host:
        _setup_host(lobby, state)
    else:
        _setup_join(lobby, state, int(args.join))

    return state


def _setup_host(lobby: SteamLobby, state: dict):
    def on_chat_msg(data):
        sender_id, body = lobby.get_chat_entry(data.lobby_steam_id, data.chat_id)
        name = lobby.get_friend_name(sender_id)
        print(f"[{ts()}] LobbyChatMsg  [{name} / {sender_id}] {body!r}")

    def on_created(result):
        if result.result == 1:  # k_EResultOK
            state["lobby_id"] = result.lobby_steam_id
            lobby.watch_lobby(result.lobby_steam_id)
            print(f"[{ts()}] LobbyCreated  LOBBY ID: {result.lobby_steam_id}  (copy-paste this to joiner)")
        else:
            print(f"[{ts()}] LobbyCreated  ERROR result={result.result} — lobby creation failed")
            state["stop"] = True

    lobby.register(LOBBY_CHAT_MSG, on_chat_msg)
    lobby.create_lobby(LOBBY_TYPE_PUBLIC, 8, on_created=on_created)
    print(f"[{ts()}] CreateLobby called — waiting for LobbyCreated_t ...")


def _setup_join(lobby: SteamLobby, state: dict, target_id: int):
    def on_data_update(data):
        val = lobby.get_lobby_data(data.lobby_steam_id, "counter")
        print(f"[{ts()}] LobbyDataUpdate  lobby={data.lobby_steam_id}"
              f"  member={data.member_steam_id}  counter={val!r}")

    def on_enter(result):
        if result.chat_room_response == CHAT_ROOM_SUCCESS:
            count = lobby.get_member_count(result.lobby_steam_id)
            state["lobby_id"] = result.lobby_steam_id
            state["joined"]   = True
            lobby.watch_lobby(result.lobby_steam_id)
            print(f"[{ts()}] LobbyEnter  lobby={result.lobby_steam_id}  members={count}")
        else:
            print(f"[{ts()}] LobbyEnter  ERROR response={result.chat_room_response} — join failed")
            state["stop"] = True

    lobby.register(LOBBY_DATA_UPDATE, on_data_update)
    lobby.join_lobby(target_id, on_join=on_enter)
    print(f"[{ts()}] JoinLobby({target_id}) called — waiting for LobbyEnter_t ...")


# ── Periodic timer logic (called every pump tick) ────────────────────────────

def check_timers(lobby: SteamLobby, state: dict):
    """Fire counter writes (host) or chat pings (joiner) every 5 s."""
    now = time.monotonic()

    if state["mode"] == "host" and state["lobby_id"]:
        if now - state["last_counter_t"] >= 5.0:
            state["counter"] += 1
            ok = lobby.set_lobby_data(state["lobby_id"], "counter", str(state["counter"]))
            print(f"[{ts()}] SetLobbyData  counter={state['counter']}  ok={ok}")
            state["last_counter_t"] = now

    elif state["mode"] == "join" and state["joined"] and state["lobby_id"]:
        if now - state["last_ping_t"] >= 5.0:
            state["ping_n"] += 1
            msg = f"ping from {lobby.player_name} #{state['ping_n']}"
            ok  = lobby.send_chat_msg(state["lobby_id"], msg)
            print(f"[{ts()}] SendLobbyChatMsg  {msg!r}  ok={ok}")
            state["last_ping_t"] = now


# ── Cleanup ──────────────────────────────────────────────────────────────────

def cleanup(lobby: SteamLobby, state: dict):
    print(f"[{ts()}] Shutting down ...")
    lid = state.get("lobby_id")
    if lid:
        lobby.leave_lobby(lid)
    lobby.shutdown()


# ── Console entry point ──────────────────────────────────────────────────────

def run_console(lobby: SteamLobby, state: dict):
    """Main loop: pump + timers at ~100 ms.  Exits on Ctrl+C or state['stop']."""
    try:
        while not state["stop"]:
            lobby.pump()
            check_timers(lobby, state)
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup(lobby, state)


def main():
    args     = parse_args()
    dll_path = args.dll or find_dll()
    if not dll_path:
        print(f"ERROR: steam_api64.dll not found.\n"
              f"  Pass --dll <path>  or  set STEAM_API_DLL=<path>")
        sys.exit(1)

    lobby = SteamLobby()
    ok, msg = lobby.init(dll_path)
    print(f"[{ts()}] Steam init: {msg}")
    if not ok:
        sys.exit(1)

    state = setup_mode(lobby, args)
    run_console(lobby, state)


if __name__ == "__main__":
    main()
