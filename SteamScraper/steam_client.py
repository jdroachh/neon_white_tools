r"""
steam_client — main-process proxy for the Steam worker subprocess.

Mirrors steam_api's public surface (functions + the module globals other code
reads as steam_api.steam_ready / player_name / logged_in_steam_id / cheater_ids)
but answers every Steam call by RPC to steam_worker.py over a pipe instead of
loading steam_api64.dll in-process. This process NEVER imports steam_api and
NEVER loads the DLL — that is what keeps the appid unbound here so the worker can
be killed to release it (see plans/steam-worker-subprocess-2026-06-12.md).

steam_backend.py picks this vs steam_api by the NW_STEAM_WORKER env var. Phase 1
ships dark: the selector defaults to in-process, so nothing reaches this unless a
dev flips the flag (or the Phase 1 smoke script drives it directly).

The bridge reads module globals (steam_client.steam_ready, etc.); PEP 562
__getattr__ at the bottom serves those from a parent-side mirror that stays
correct — and instantly reports "not connected" — even if the worker dies.
"""
import os
import subprocess
import sys
import threading
from collections import namedtuple

from logger import get_logger, get_app_data_dir

logger = get_logger("steam_client")

# Mirrors steam_api.BATCH_SIZE (Valve's DownloadLeaderboardEntriesForUsers cap).
# Defined locally so the main process never has to import steam_api.
BATCH_SIZE = 100

# Default per-RPC ceiling. Individual RPCs are one Steam round-trip; steam_api's
# wait_for_call tops out at 10s, so 60s is comfortable headroom incl. init's DLL
# load + 1s settle.
_RPC_TIMEOUT = 60.0


class SteamWorkerError(RuntimeError):
    """An RPC failed (worker returned an error, timed out, or isn't running)."""


class SteamWorkerDied(SteamWorkerError):
    """The worker process exited while a request was outstanding / being sent."""


# Rehydrated leaderboard entry. Only the three fields any consumer reads
# (entry.steam_id_user / global_rank / score) survive the JSON hop; the ctypes
# struct's details_count / ugc_handle were never used downstream.
Entry = namedtuple("Entry", ["steam_id_user", "global_rank", "score"])


def _rehydrate(d):
    if d is None:
        return None
    return Entry(d["steam_id_user"], d["global_rank"], d["score"])


# ── Parent-side mirror of worker state ────────────────────────────────────────
_mirror_lock = threading.Lock()
_mirror = {
    "ready":              False,
    "player_name":        "Not connected",
    "logged_in_steam_id": 0,
    "cheater_ids":        set(),
}


def _set_mirror(**fields):
    with _mirror_lock:
        _mirror.update(fields)


def _reset_mirror():
    _set_mirror(ready=False, player_name="Not connected", logged_in_steam_id=0)


# ── Worker process + RPC plumbing ─────────────────────────────────────────────
_proc = None
_proc_lock = threading.Lock()       # guards spawn/kill of _proc
_write_lock = threading.Lock()      # serializes stdin writes
_pending = {}                       # id -> _Slot
_pending_lock = threading.Lock()
_id_counter = 0
_id_lock = threading.Lock()
_job_handle = None                  # Windows Job Object; kept alive intentionally

# Crash detection. _intentional_stop is True while we deliberately kill the worker
# (disconnect / clean shutdown) so its death doesn't masquerade as a crash. _on_lost
# fires only on UNEXPECTED worker death (Steam client exit, worker fault) so the
# bridge can push a lost-connection event to the UI.
_intentional_stop = False
_on_lost = None
# Liveness keyed off the reader thread (stdout EOF), not proc.poll(): after a
# crash, poll() can briefly still read None while the OS tears the process down,
# which would make _ensure_running write to a dead pipe instead of respawning.
# The reader sets this False the instant it sees EOF — an authoritative signal.
_proc_alive = False


def set_on_lost(callback):
    """Register a 0-arg callback fired when the worker dies unexpectedly (not via
    our own disconnect/shutdown). The bridge uses this to notify the webview."""
    global _on_lost
    _on_lost = callback


class _Slot:
    __slots__ = ("event", "ok", "result", "error")

    def __init__(self):
        self.event = threading.Event()
        self.ok = False
        self.result = None
        self.error = None


def _next_id() -> int:
    global _id_counter
    with _id_lock:
        _id_counter += 1
        return _id_counter


def _worker_argv():
    """Frozen: re-exec the EXE with --steam-worker (run_app.py pivots on it).
    Dev: launch the loose steam_worker.py with the same interpreter."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--steam-worker"]
    worker_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steam_worker.py")
    return [sys.executable, worker_py]


def _create_job_object(pid: int):
    """Enroll the worker in a Job Object with KILL_ON_JOB_CLOSE so it dies if the
    parent dies without a clean shutdown. The job handle is parked in a module
    global; if it were GC'd/closed the kernel would kill the worker immediately."""
    global _job_handle
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit",     ctypes.c_int64),
            ("LimitFlags",              wintypes.DWORD),
            ("MinimumWorkingSetSize",   ctypes.c_size_t),
            ("MaximumWorkingSetSize",   ctypes.c_size_t),
            ("ActiveProcessLimit",      wintypes.DWORD),
            ("Affinity",                ctypes.c_size_t),
            ("PriorityClass",           wintypes.DWORD),
            ("SchedulingClass",         wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [("ReadOperationCount", ctypes.c_uint64),
                    ("WriteOperationCount", ctypes.c_uint64),
                    ("OtherOperationCount", ctypes.c_uint64),
                    ("ReadTransferCount", ctypes.c_uint64),
                    ("WriteTransferCount", ctypes.c_uint64),
                    ("OtherTransferCount", ctypes.c_uint64)]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo",                IO_COUNTERS),
            ("ProcessMemoryLimit",    ctypes.c_size_t),
            ("JobMemoryLimit",        ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed",     ctypes.c_size_t),
        ]

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    JobObjectExtendedLimitInformation = 9

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.OpenProcess.restype = wintypes.HANDLE

    try:
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            logger.debug("CreateJobObject failed; relying on watchdog + atexit")
            return
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
                job, JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info)):
            logger.debug("SetInformationJobObject failed")
            return
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        hproc = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
        if not hproc:
            logger.debug("OpenProcess(%d) for job assignment failed", pid)
            return
        try:
            if not kernel32.AssignProcessToJobObject(job, hproc):
                logger.debug("AssignProcessToJobObject failed")
                return
            _job_handle = job  # keep alive for the life of the parent process
        finally:
            kernel32.CloseHandle(hproc)
    except Exception:
        logger.debug("Job Object setup raised; falling back to watchdog", exc_info=True)


def _spawn():
    """Spawn the worker and start its reader thread. Caller holds _proc_lock."""
    global _proc, _intentional_stop, _proc_alive
    _intentional_stop = False        # a fresh worker; its next death is a crash unless we kill it
    _proc_alive = True
    env = os.environ.copy()
    env["NW_PARENT_PID"] = str(os.getpid())
    env["NW_LOG_FILE"] = "steam_worker.log"

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    _proc = subprocess.Popen(
        _worker_argv(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,                 # inherit; worker logs to stderr + its own file
        cwd=get_app_data_dir(),      # guaranteed-writable CWD so the worker can
                                     # write/read steam_appid.txt (the launch CWD
                                     # may be System32 from Windows Search)
        env=env,
        encoding="utf-8",
        bufsize=1,                   # line-buffered text mode
        creationflags=creationflags,
    )
    logger.info("steam_worker spawned (PID %d)", _proc.pid)
    _create_job_object(_proc.pid)

    t = threading.Thread(target=_reader_loop, args=(_proc,), name="worker-reader", daemon=True)
    t.start()
    return _proc


def _ensure_running():
    with _proc_lock:
        if _proc is None or not _proc_alive or _proc.poll() is not None:
            _spawn()


def _reader_loop(proc):
    """Demux worker stdout: id'd lines -> waiting slots; events -> handlers.
    Exits on EOF (worker death), failing every outstanding request."""
    import json
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                logger.warning("malformed line from worker: %r", line[:200])
                continue
            if "event" in msg:
                _handle_event(msg)
                continue
            slot_id = msg.get("id")
            with _pending_lock:
                slot = _pending.pop(slot_id, None)
            if slot is None:
                logger.debug("response for unknown id %r dropped", slot_id)
                continue
            slot.ok = msg.get("ok", False)
            slot.result = msg.get("result")
            slot.error = msg.get("error")
            slot.event.set()
    finally:
        _on_worker_exit(proc)


def _on_worker_exit(proc):
    """Worker stdout closed: mark disconnected and wake every pending caller.
    `proc` is the worker this reader owned — guard against a newer worker that a
    concurrent respawn may already have installed as `_proc`."""
    global _proc_alive
    _reset_mirror()
    with _pending_lock:
        pending = list(_pending.values())
        _pending.clear()
    for slot in pending:
        if not slot.event.is_set():
            slot.error = "worker process exited"
            slot.ok = False
            slot.event.set()

    # Only clear liveness if this IS the current worker — a faster respawn may have
    # already replaced _proc, and we must not mark the new one dead. Flip the flag
    # BEFORE firing on_lost so a reconnect triggered from the callback respawns.
    with _proc_lock:
        is_current = (_proc is proc)
        if is_current:
            _proc_alive = False
    logger.info("steam_worker reader exited (worker exit code=%s, current=%s)",
                proc.poll(), is_current)

    # Unexpected death of the current worker (Steam client exit, worker fault) —
    # not our own kill: tell the bridge so it can flip the UI to "Not connected".
    # Subsumes the old steam-exit hard crash, which now only takes down the worker.
    if is_current and not _intentional_stop and _on_lost is not None:
        logger.warning("worker died unexpectedly; firing on_lost")
        try:
            _on_lost()
        except Exception:
            logger.debug("on_lost callback raised", exc_info=True)


def _handle_event(msg: dict):
    event = msg.get("event")
    if event == "cheater_list":
        ids = set(msg.get("ids") or [])
        _set_mirror(cheater_ids=ids)
        logger.info("cheater list received from worker: %d ids", len(ids))
    else:
        logger.debug("unhandled worker event: %r", event)


def _request(method: str, params: dict = None, timeout: float = _RPC_TIMEOUT):
    """Send one RPC and block for its response. Raises SteamWorkerError on
    failure/timeout, SteamWorkerDied if the worker isn't/stops running."""
    _ensure_running()
    proc = _proc
    if proc is None or proc.poll() is not None:
        raise SteamWorkerDied("worker not running")

    req_id = _next_id()
    slot = _Slot()
    with _pending_lock:
        _pending[req_id] = slot

    payload = {"id": req_id, "method": method, "params": params or {}}
    import json
    line = json.dumps(payload, separators=(",", ":")) + "\n"
    try:
        with _write_lock:
            proc.stdin.write(line)
            proc.stdin.flush()
    except Exception as e:
        with _pending_lock:
            _pending.pop(req_id, None)
        raise SteamWorkerDied(f"failed to send {method!r}: {e}")

    if not slot.event.wait(timeout):
        with _pending_lock:
            _pending.pop(req_id, None)
        raise SteamWorkerError(f"RPC {method!r} timed out after {timeout}s")

    if not slot.ok:
        # An "exited" sentinel comes from _on_worker_exit; everything else is a
        # real error response from the worker.
        if slot.error == "worker process exited":
            raise SteamWorkerDied(f"worker died during {method!r}")
        raise SteamWorkerError(f"{method} failed: {slot.error}")
    return slot.result


# ── Public surface: mirrors steam_api ─────────────────────────────────────────
def init_steam(dll_path):
    """Spawn the worker (if needed) and initialize Steam inside it. Returns
    (ok, message), matching steam_api.init_steam, and refreshes the mirror."""
    _ensure_running()
    try:
        res = _request("init", {"dll_path": dll_path})
    except SteamWorkerError as e:
        _reset_mirror()
        return False, str(e)
    ok = bool(res.get("ok"))
    if ok:
        _set_mirror(
            ready=True,
            player_name=res.get("player_name") or "Unknown",
            logged_in_steam_id=int(res.get("steam_id") or 0),
        )
    else:
        _reset_mirror()
    return ok, res.get("message", "")


def run_callbacks():
    """No-op: the worker runs its own 100ms callback pump. Kept for surface
    parity with steam_api (the bridge's legacy _poll thread calls this)."""
    return None


def fetch_cheater_list():
    """No-op trigger: the worker fetches the cheater list itself on init and
    pushes it via the cheater_list event. Returns the current mirror count."""
    with _mirror_lock:
        return len(_mirror["cheater_ids"])


def get_cheater_count() -> int:
    with _mirror_lock:
        return len(_mirror["cheater_ids"])


def find_leaderboard(name):
    return _request("find_leaderboard", {"name": name})


def get_entry_count(handle) -> int:
    return _request("get_entry_count", {"handle": handle})


def fetch_batch(lb_handle, start, end, _poll_interval=0.02):
    return _request("fetch_batch", {
        "handle": lb_handle, "start": start, "end": end,
        "poll_interval": _poll_interval,
    })


def get_player_entry(lb_handle, steam_id):
    return _rehydrate(_request("get_player_entry", {"handle": lb_handle, "sid": steam_id}))


def get_player_entries(lb_handle, steam_ids, fallback=True):
    res = _request("get_player_entries",
                   {"handle": lb_handle, "sids": list(steam_ids), "fallback": fallback})
    # JSON object keys came back as strings; restore int sids for callers.
    return {int(sid): _rehydrate(d) for sid, d in res.items()}


def get_persona_name(steam_id) -> str:
    return _request("get_persona_name", {"sid": steam_id})


def get_steam_status() -> dict:
    """Answered from the parent mirror — instant, and correctly 'not connected'
    the moment the worker dies (no RPC round-trip needed)."""
    with _mirror_lock:
        return {
            "ready":       _mirror["ready"],
            "player_name": _mirror["player_name"],
            "steam_id":    str(_mirror["logged_in_steam_id"]),
        }


def ping():
    return _request("ping", timeout=10.0)


# ── Lifecycle (used in full by Phase 3; available now for the smoke script) ───
def shutdown(timeout: float = 1.0):
    """Best-effort clean shutdown RPC, then kill — process death is the only
    thing that frees the appid, so we always follow through with the kill.

    Note: not held under _proc_lock — _request -> _ensure_running needs that lock,
    and threading.Lock isn't reentrant, so holding it here would deadlock."""
    global _intentional_stop
    if _proc is None:
        return
    _intentional_stop = True         # this death is deliberate — don't fire on_lost
    try:
        _request("shutdown", timeout=timeout)
    except SteamWorkerError:
        pass
    kill()


def kill():
    """Terminate the worker and wait. Safe to call directly."""
    global _proc, _intentional_stop
    proc = _proc
    if proc is None:
        return
    _intentional_stop = True         # deliberate kill — don't fire on_lost
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    _reset_mirror()
    _proc = None


def is_running() -> bool:
    return _proc is not None and _proc.poll() is None


# ── PEP 562 module __getattr__: serve steam_api-style globals from the mirror ──
def __getattr__(name):
    if name == "steam_ready":
        with _mirror_lock:
            return _mirror["ready"]
    if name == "player_name":
        with _mirror_lock:
            return _mirror["player_name"]
    if name == "logged_in_steam_id":
        with _mirror_lock:
            return _mirror["logged_in_steam_id"]
    if name == "cheater_ids":
        with _mirror_lock:
            return set(_mirror["cheater_ids"])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
