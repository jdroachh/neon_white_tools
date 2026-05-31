"""
In-memory per-session cache for Multi-Compare leaderboard entries.

Keyed `(steam_id, level_code) -> entry_or_None`. Entry is whatever the bridge
worker stores after a Steam fetch — typically a small dict shaped like
`{"time_us": int, "rank": int}` or None for "player has no entry on this
level". Storing None is meaningful: it lets us avoid re-fetching known-missing
players on mode-switch.

Lifetime: the pywebview window. Cleared implicitly when the process exits.
No disk persistence in v1 — times go stale fast as players set new PBs, and
disk-cache with TTL is its own design problem (see plans/multi-compare-graduation.md
"Out of scope").

Designed to be swappable to a disk-backed implementation later without
changing callers — the get/put/clear surface stays the same.
"""

import threading
from typing import Optional


_lock = threading.Lock()
_store: dict[tuple[int, str], Optional[dict]] = {}


def get(steam_id: int, level_code: str) -> tuple[bool, Optional[dict]]:
    """
    Returns (hit, value). `hit=True` means the key is present (value may be
    None — that's a cached "missing entry"). `hit=False` means never fetched.
    """
    key = (steam_id, level_code)
    with _lock:
        if key in _store:
            return True, _store[key]
        return False, None


def put(steam_id: int, level_code: str, entry: Optional[dict]) -> None:
    """Insert or overwrite. `entry=None` is valid and means 'fetched, no result'."""
    with _lock:
        _store[(steam_id, level_code)] = entry


def clear() -> None:
    with _lock:
        _store.clear()


def clear_for_sids(steam_ids) -> int:
    """Evict every cached entry for the given Steam IDs, across all levels.

    Used by the Multi-Compare "Refresh" button: the roster (UI state) is kept,
    but those players' cached times are dropped so the next run re-fetches them
    fresh. Returns the number of keys removed (diagnostic).
    """
    targets = set(steam_ids)
    with _lock:
        stale = [k for k in _store if k[0] in targets]
        for k in stale:
            del _store[k]
    return len(stale)


def size() -> int:
    """Diagnostic — current number of cached keys."""
    with _lock:
        return len(_store)
