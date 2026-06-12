r"""
steam_worker — the isolated Steam subprocess.

Owns the Steamworks session: it is the ONLY process that loads steam_api64.dll
and calls SteamAPI_Init. Steam binds the Neon White appid to the PID that called
Init until that PID dies (see plans/steam-worker-subprocess-2026-06-12.md), so
running the session here means killing this process cleanly frees the appid while
the main app keeps living — the whole point of the refactor.

Protocol: newline-delimited JSON ("JSON Lines") over stdin/stdout, driven by
steam_client.py in the parent.
  - Request  (parent -> worker): {"id": 42, "method": "fetch_batch", "params": {...}}
  - Response (worker -> parent): {"id": 42, "ok": true,  "result": ...}
                                  {"id": 42, "ok": false, "error": "..."}
  - Event    (worker -> parent, unsolicited): {"event": "cheater_list", "ids": [...]}

stdout carries ONLY protocol lines — logging goes to stderr and to the worker's
own log file (steam_worker.log via NW_LOG_FILE), never the parent's app.log.

Launched two ways (steam_client picks):
  - dev    : python <repo>/SteamScraper/steam_worker.py
  - frozen : <exe> --steam-worker   (run_app.py pivots here after freeze_support)

Phase 1 ships dark: nothing imports this unless NW_STEAM_WORKER selects it.
"""
import os
import sys
import threading


# ── Logging: OWN file, before importing steam_api (which configures logging) ──
# steam_api calls get_logger() at import, which attaches a RotatingFileHandler.
# Point that handler at steam_worker.log so we never share the parent's app.log
# (two processes on one rotating handle = Windows file-lock corruption).
os.environ.setdefault("NW_LOG_FILE", "steam_worker.log")

# Make `import steam_api` / `import logger` resolve whether we're launched as a
# loose script (dev) or frozen. In the frozen bundle these are already top-level
# modules; the path insert is a harmless no-op there.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from logger import get_logger
import steam_api

logger = get_logger("steam_worker")


# ── stdout/stdin hygiene ──────────────────────────────────────────────────────
# Force UTF-8 and LF so the parent's line reader sees clean JSON. Without newline
# control, Windows text mode would emit CRLF; the parent tolerates it, but pinning
# LF keeps the wire format unambiguous.
try:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
except Exception:
    logger.debug("stdio reconfigure unavailable", exc_info=True)

_OUT = sys.stdout
_out_lock = threading.Lock()


def _send(obj: dict) -> None:
    """Write one JSON line to stdout, atomically, and flush."""
    import json
    line = json.dumps(obj, separators=(",", ":"))
    with _out_lock:
        try:
            _OUT.write(line + "\n")
            _OUT.flush()
        except Exception:
            # If the parent's pipe is gone there's nothing we can do and no one to
            # tell — log and let the death-watchers take us down.
            logger.warning("stdout write failed (parent pipe closed?)", exc_info=True)


def _emit_event(event: str, **fields) -> None:
    payload = {"event": event}
    payload.update(fields)
    _send(payload)


# ── struct -> dict serialization ──────────────────────────────────────────────
def _entry_to_dict(entry):
    """LeaderboardEntry ctypes struct -> JSON-safe dict the client rehydrates."""
    if entry is None:
        return None
    return {
        "steam_id_user": entry.steam_id_user,
        "global_rank":   entry.global_rank,
        "score":         entry.score,
    }


# ── RPC method handlers ───────────────────────────────────────────────────────
# Each returns a JSON-serializable result (or raises, which becomes an error
# response). They run on per-request dispatch threads; steam_api serializes the
# native callback pump internally via _callbacks_lock, exactly as in-process.

def _rpc_ping(_params):
    return "pong"


def _rpc_init(params):
    dll_path = params["dll_path"]
    ok, msg = steam_api.init_steam(dll_path)
    if ok:
        # Start the callback pump (replaces the bridge's old 100ms _poll thread)
        # and fetch the cheater list, both worker-side now.
        _start_pump()
        threading.Thread(target=_fetch_cheaters, name="cheater-fetch", daemon=True).start()
    return {
        "ok":          ok,
        "message":     msg,
        "player_name": steam_api.player_name if ok else "",
        "steam_id":    str(steam_api.logged_in_steam_id) if ok else "",
        "cheater_count": len(steam_api.cheater_ids),
    }


def _rpc_status(_params):
    return {
        "ready":         steam_api.steam_ready,
        "player_name":   steam_api.player_name,
        "steam_id":      str(steam_api.logged_in_steam_id),
        "cheater_count": len(steam_api.cheater_ids),
    }


def _rpc_find_leaderboard(params):
    # Returns an opaque uint64 handle (JSON-safe int) or None. The worker owns
    # _lb_handle_cache, so its lifetime correctly dies with this process.
    return steam_api.find_leaderboard(params["name"])


def _rpc_get_entry_count(params):
    return steam_api.get_entry_count(params["handle"])


def _rpc_fetch_batch(params):
    # fetch_batch already returns plain dicts (and filters cheaters worker-side).
    return steam_api.fetch_batch(
        params["handle"], params["start"], params["end"],
        params.get("poll_interval", 0.02),
    )


def _rpc_get_player_entry(params):
    return _entry_to_dict(steam_api.get_player_entry(params["handle"], params["sid"]))


def _rpc_get_player_entries(params):
    # steam_api returns {sid:int -> struct|None}. JSON object keys must be strings;
    # the client restores int keys on rehydration.
    out = steam_api.get_player_entries(params["handle"], params["sids"])
    return {str(sid): _entry_to_dict(entry) for sid, entry in out.items()}


def _rpc_get_persona_name(params):
    return steam_api.get_persona_name(params["sid"])


def _rpc_get_cheater_count(_params):
    return len(steam_api.cheater_ids)


def _rpc_shutdown(_params):
    # Best-effort: acknowledge, then let the main loop exit. The parent kills us
    # right after for the actual appid release (process death is the only thing
    # that frees it), so we don't need to tear down the DLL here.
    return {"ok": True}


_DISPATCH = {
    "ping":               _rpc_ping,
    "init":               _rpc_init,
    "status":             _rpc_status,
    "find_leaderboard":   _rpc_find_leaderboard,
    "get_entry_count":    _rpc_get_entry_count,
    "fetch_batch":        _rpc_fetch_batch,
    "get_player_entry":   _rpc_get_player_entry,
    "get_player_entries": _rpc_get_player_entries,
    "get_persona_name":   _rpc_get_persona_name,
    "get_cheater_count":  _rpc_get_cheater_count,
    "shutdown":           _rpc_shutdown,
}


# ── Callback pump + cheater fetch ─────────────────────────────────────────────
_pump_started = False
_pump_lock = threading.Lock()


def _start_pump():
    """Start the 100ms Steam callback pump once (idempotent across reconnects)."""
    global _pump_started
    with _pump_lock:
        if _pump_started:
            return
        _pump_started = True
    threading.Thread(target=_pump_loop, name="steam-pump", daemon=True).start()


def _pump_loop():
    import time
    while steam_api.steam_ready:
        try:
            steam_api.run_callbacks()
        except Exception:
            logger.debug("run_callbacks raised in pump", exc_info=True)
        time.sleep(0.1)


def _fetch_cheaters():
    """Fetch the cheater list, then push it to the parent so its mirror's
    get_cheater_count and any membership checks match worker-side filtering."""
    try:
        steam_api.fetch_cheater_list()
    except Exception:
        logger.warning("cheater list fetch failed", exc_info=True)
    _emit_event("cheater_list", ids=sorted(steam_api.cheater_ids))


# ── Parent-death watchdog ─────────────────────────────────────────────────────
# Two independent guarantees the worker dies with the parent: (1) the main RPC
# loop exits on stdin EOF, which happens when the parent's stdout pipe closes;
# (2) this watchdog waits on the parent's process handle directly. The parent
# additionally enrolls us in a Job Object (KILL_ON_JOB_CLOSE). Belt and braces —
# orphaned workers would hold the appid and block the real game.
def _start_parent_watchdog():
    ppid_env = os.environ.get("NW_PARENT_PID")
    if not ppid_env or sys.platform != "win32":
        return
    try:
        ppid = int(ppid_env)
    except ValueError:
        return

    def _watch():
        import ctypes
        SYNCHRONIZE = 0x00100000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, ppid)
        if not handle:
            logger.debug("parent watchdog: OpenProcess(%d) failed", ppid)
            return
        # Block until the parent exits, then take ourselves down hard.
        kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)  # INFINITE
        logger.info("parent (PID %d) exited; worker self-terminating", ppid)
        os._exit(0)

    threading.Thread(target=_watch, name="parent-watchdog", daemon=True).start()


# ── Main RPC loop ─────────────────────────────────────────────────────────────
def _handle_request(req: dict) -> None:
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}
    fn = _DISPATCH.get(method)
    if fn is None:
        _send({"id": req_id, "ok": False, "error": f"unknown method: {method!r}"})
        return
    try:
        result = fn(params)
        _send({"id": req_id, "ok": True, "result": result})
    except Exception as e:
        logger.warning("RPC %r failed", method, exc_info=True)
        _send({"id": req_id, "ok": False, "error": f"{type(e).__name__}: {e}"})


def worker_main() -> None:
    import json
    logger.info("steam_worker started (PID %d, parent %s)",
                os.getpid(), os.environ.get("NW_PARENT_PID", "?"))
    _start_parent_watchdog()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            logger.warning("malformed RPC line dropped: %r", line[:200], exc_info=True)
            continue
        # One dispatch thread per request so a slow Steam round-trip never blocks
        # reading the next request (the in-process app already runs concurrent
        # Steam calls from multiple bridge threads).
        threading.Thread(
            target=_handle_request, args=(req,),
            name=f"rpc-{req.get('id')}", daemon=True,
        ).start()
        if req.get("method") == "shutdown":
            break

    logger.info("steam_worker stdin closed / shutdown; exiting")


if __name__ == "__main__":
    worker_main()
