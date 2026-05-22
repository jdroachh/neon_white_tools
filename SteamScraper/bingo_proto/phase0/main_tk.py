"""
main_tk.py — tkinter-event-loop driver for Steam callbacks (test 9).

Same CLI args as main.py.  Drives lobby.pump() via root.after(100, ...)
instead of a sleep loop so the test verifies callbacks survive a tkinter
event loop (the integration target for the shipping app).

Usage (from SteamScraper/bingo_proto/):
    python phase0/main_tk.py --host
    python phase0/main_tk.py --join <lobby_id>
"""
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import main as _m
from steam_lobby import SteamLobby, ts


def _tick(root: tk.Tk, lobby: SteamLobby, state: dict):
    if state["stop"]:
        _m.cleanup(lobby, state)
        root.destroy()
        return
    lobby.pump()
    _m.check_timers(lobby, state)
    root.after(100, _tick, root, lobby, state)


def main():
    args     = _m.parse_args()
    dll_path = args.dll or _m.find_dll()
    if not dll_path:
        print("ERROR: steam_api64.dll not found. Pass --dll <path> or set STEAM_API_DLL.")
        sys.exit(1)

    lobby = SteamLobby()
    ok, msg = lobby.init(dll_path)
    print(f"[{ts()}] Steam init: {msg}")
    if not ok:
        sys.exit(1)

    state = _m.setup_mode(lobby, args)

    root = tk.Tk()
    root.withdraw()          # no visible window; just need the event loop
    root.title("bingo-proto phase0 (tkinter pump)")

    root.after(100, _tick, root, lobby, state)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        _m.cleanup(lobby, state)


if __name__ == "__main__":
    main()
