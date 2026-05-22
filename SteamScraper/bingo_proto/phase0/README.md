# Bingo Mode — Phase 0: Steam Lobbies Smoke Test

Console-only transport test.  No bingo logic.  Goal: confirm Steam Matchmaking
works from a non-game Python process before any UI is built.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Neon White installed via Steam | App ID 1533420 — lobbies are tied to this app |
| Steam running and logged in | On both machines for cross-network tests |
| `steam_api64.dll` accessible | Found inside `Neon White_Data/Plugins/x86_64/` |
| Python 3.10+ | No third-party packages required |

---

## Setup

```
cd SteamScraper\bingo_proto
```

The `steam_appid.txt` file is already here (contains `1533420`).  Run all
commands from this directory so Steam's DLL search finds it.

**DLL path — pick one:**

```
:: Option A: pass --dll directly (simplest, works in any shell)
python phase0\main.py --host --dll "C:\Program Files (x86)\Steam\steamapps\common\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll"

:: Option B: set env var once per cmd.exe session, then run normally
set STEAM_API_DLL=C:\Program Files (x86)\Steam\steamapps\common\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll
python phase0\main.py --host

:: Option C: copy steam_api64.dll into this directory (bingo_proto\)
::           — the DLL finder checks here automatically
```

The default install path is tried automatically if it exists:
`C:\Program Files (x86)\Steam\steamapps\common\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll`

---

## Running the smoke test

### Machine A — host

```
python phase0\main.py --host
```

Output includes:
```
[HH:MM:SS.mmm] Steam init: Connected as YourName (76561198XXXXXXXXX)
[HH:MM:SS.mmm] CreateLobby called — waiting for LobbyCreated_t ...
[HH:MM:SS.mmm] LobbyCreated  LOBBY ID: 109775241234567890  (copy-paste this to joiner)
[HH:MM:SS.mmm] SetLobbyData  counter=1  ok=True
```

Copy the LOBBY ID line.  Every 5 s the host increments `counter` in lobby data.
Incoming chat messages are logged as they arrive.  Press **Ctrl+C** to exit cleanly.

### Machine B — joiner

```
python phase0\main.py --join 109775241234567890
```

Output includes:
```
[HH:MM:SS.mmm] Steam init: Connected as FriendName (76561198YYYYYYYYY)
[HH:MM:SS.mmm] JoinLobby(109775241234567890) called — waiting for LobbyEnter_t ...
[HH:MM:SS.mmm] LobbyEnter  lobby=109775241234567890  members=2
[HH:MM:SS.mmm] LobbyDataUpdate  lobby=...  member=...  counter='1'
[HH:MM:SS.mmm] SendLobbyChatMsg  'ping from FriendName #1'  ok=True
```

Every 5 s the joiner sends a `ping from <name> #N` chat message.
Press **Ctrl+C** to exit cleanly.

### Test 9 — tkinter pump

Same flags as above but via `main_tk.py`.  A hidden tk window provides the
event loop; all other output is identical.

```
python phase0\main_tk.py --host
python phase0\main_tk.py --join <id>
```

---

## Success criteria

Run each test, observe the timestamped log, and record pass/fail in `RESULTS.md`
(template below).  Tests 1–4 can be done on a single machine with two separate
Steam accounts (use Steam's "Add account" family-sharing flow or two machines on
the same LAN).  Test 5 requires two machines on different ISPs.

| # | Test | Pass condition |
|---|---|---|
| 1 | **Lobby creates from non-game process** | `LobbyCreated_t` fires and prints a non-zero lobby ID within 5 s of `--host` start |
| 2 | **Joiner can join by pasted ID** | `LobbyEnter_t` fires within 5 s of `--join <id>` start; `chat_room_response == 1` |
| 3 | **Lobby data replicates host→joiner** | `LobbyDataUpdate_t` fires on the joiner within 2 s of the host's `SetLobbyData` (visible in timestamps) |
| 4 | **Chat msg replicates joiner→host** | `LobbyChatMsg_t` fires on the host within 2 s of the joiner's `SendLobbyChatMsg` |
| 5 | **Works across networks** | Repeat tests 1–4 with two machines on different ISPs; all pass |
| 6 | **Idle survivability (10 min)** | Leave host + joiner running with no interaction for 10 min; lobby still responds to a new `SetLobbyData` / chat ping after the idle period |
| 7 | **Lobby-data per-key size ceiling** | Binary-search `SetLobbyData(lobby_id, "probe", "X"*N)` until it returns `False`; record the byte limit |
| 8 | **Chat-msg size ceiling** | Binary-search `SendLobbyChatMsg(lobby_id, "X"*N)` until it returns `False`; record the byte limit |
| 9 | **Callbacks under tkinter polling** | Run `main_tk.py --host` and `main_tk.py --join <id>`; confirm tests 1–4 all fire identically |

---

## RESULTS.md template

Copy to `bingo_proto/RESULTS.md` (gitignored) and fill in after running.

```markdown
# Phase 0 Smoke Test Results — YYYY-MM-DD

Machine A: <OS, CPU, ISP>
Machine B: <OS, CPU, ISP>

| # | Pass? | Notes |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | latency: Xs | |
| 4 | latency: Xs | |
| 5 | | |
| 6 | | |
| 7 | | lobby-data key limit: N bytes |
| 8 | | chat-msg limit: N bytes |
| 9 | | |

## Surprises / issues
-
```
