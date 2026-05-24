# Bingo Mode — Phase 1: Bindings Smoke Test

Stage 1 of Phase 1 — extends the Phase 0 Steamworks bindings with everything
Phase 1 will need (member iteration, host ownership, per-member data, persona
names) and proves each new binding works via a standalone smoke test.

No protocol, no board, no UI.  Internal-only — two local machines is all that's
needed.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Neon White installed via Steam | App ID 1533420 |
| Steam running and logged in | On both machines |
| `steam_api64.dll` accessible | Found at `<Neon White_Data>/Plugins/x86_64/steam_api64.dll` |
| Python 3.10+ | No third-party packages — stdlib + ctypes only |

---

## Setup

Run all commands from `SteamScraper\bingo_proto\` so `steam_appid.txt` (which
already lives there) is found by Steam's DLL search.

**DLL resolution order (automatic):**

1. `--dll PATH` argument (always wins)
2. `STEAM_API_DLL` environment variable
3. `steam_api64.dll` beside `smoke_test.py` (i.e. in `phase1\`)
4. Default Neon White install path inside Steam's registry install dir

---

## Running the smoke test

### PowerShell

```powershell
# Machine A — host
cd E:\Claude-Neon-White-App\SteamScraper\bingo_proto
python -u phase1/smoke_test.py --host

# With explicit DLL path
python -u phase1/smoke_test.py --host --dll "C:\Program Files (x86)\Steam\steamapps\common\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll"

# Machine B — joiner (paste lobby ID from host output)
python -u phase1/smoke_test.py --join 109775241234567890
```

### cmd.exe

```
:: Machine A — host
cd /d E:\Claude-Neon-White-App\SteamScraper\bingo_proto
python -u phase1\smoke_test.py --host

:: Set DLL path once per session (Option A)
set STEAM_API_DLL=C:\Program Files (x86)\Steam\steamapps\common\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll
python -u phase1\smoke_test.py --host

:: Or pass it directly (Option B)
python -u phase1\smoke_test.py --host --dll "C:\Program Files (x86)\Steam\steamapps\common\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll"

:: Machine B — joiner
python -u phase1\smoke_test.py --join 109775241234567890
```

---

## Test descriptions

### Host-side (10 tests)

| # | Test | Pass condition |
|---|---|---|
| T1 | `init()` succeeds | Returns `(True, ...)` — Steam running and logged in |
| T2 | `create_lobby(8)` | Returns nonzero lobby ID within 10 s; ID is printed for joiner |
| T3 | `get_lobby_owner()` | Returns the host's own SteamID64 immediately after create |
| T4 | `get_lobby_members()` | List contains the host's SteamID64 |
| T5 | `persona_name(host_id)` | Returns a non-empty display name (not just the raw int) |
| T6 | Member-data round-trip | `set_lobby_member_data("team","0")` then `get_lobby_member_data` returns `"0"` |
| T7 | Synthesized join event | `LobbyChatUpdate_t` with `state_change=0x01` fires within 60 s when joiner connects |
| T8 | Member count | `get_lobby_members()` length is 2 after joiner appears |
| T9 | Synthesized leave event | `LobbyChatUpdate_t` with `state_change=0x02` fires within 30 s when joiner leaves |
| T10 | `shutdown()` | Returns cleanly with no exception |

### Joiner-side (7 steps)

| # | Step | Notes |
|---|---|---|
| J1 | `init()` | Same as T1 |
| J2 | `join_lobby(id)` | Blocking; waits for `LobbyEnter_t` |
| J3 | `persona_name(host_id)` | May be empty for non-friends on first connect (cache warms slowly) — WARN, not FAIL |
| J4 | `set_lobby_member_data("team","1")` | Sets own per-member data |
| J5 | `send_chat_msg(b"joiner-online")` | Confirms chat path still works |
| J6 | 30 s stay | Gives host the T7/T8 window |
| J7 | `leave_lobby` + `shutdown` | Triggers T9 on host side |

---

## Implementation notes

### Why polling instead of `SteamAPI_RegisterCallback`

The `steam_api64.dll` bundled with Neon White pre-dates SDK 1.50.  It does not
export `SteamAPI_ManualDispatch_*`, and vtable callback registration via
`SteamAPI_RegisterCallback` does not fire reliably.

Phase 1 continues Phase 0's polling approach — three polling loops run every
100 ms inside `pump()`:

- **LobbyChatMsg_t** — `GetLobbyChatEntry` by incrementing index
- **LobbyDataUpdate_t** — `GetLobbyData` vs. last-seen value per key
- **LobbyChatUpdate_t (synthesized)** — `GetNumLobbyMembers` +
  `GetLobbyMemberByIndex` diffed against a per-lobby `set[int]`.
  When the set grows: fire `state_change=0x01` (entered).
  When it shrinks: fire `state_change=0x02` (left).
  We cannot distinguish leave / disconnect / kick without the real callback;
  reporting all departures as `0x02` is sufficient for Stage 2's leader-transfer
  logic which only needs to know "they're gone".

### `SteamFriends017`

The friends interface is acquired as `SteamFriends017`, matching `steam_api.py`'s
`init_steam` to avoid version drift.  A `SteamFriends015` fallback is also
attempted in case of older installs.

---

## Recording results

Copy the template below to `bingo_proto/RESULTS.md` (gitignored — no secrets in
the repo) and fill in after running.

```markdown
# Phase 1 Smoke Test Results — YYYY-MM-DD

Machine A (host): <OS, CPU, ISP>
Machine B (joiner): <OS, CPU, ISP>

| # | Pass? | Latency / Notes |
|---|---|---|
| T1 | | |
| T2 | | lobby ID: |
| T3 | | |
| T4 | | |
| T5 | | name returned: |
| T6 | | |
| T7 | | latency from join to event: Xs |
| T8 | | |
| T9 | | latency from leave to event: Xs |
| T10 | | |
| J1 | | |
| J2 | | |
| J3 | | (WARN acceptable) |
| J4 | | |
| J5 | | |
| J7 | | |

## Surprises / issues
-
```
