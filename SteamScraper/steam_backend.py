r"""
steam_backend — selects the Steam backend at import time.

Two interchangeable implementations of the same surface:
  - steam_api    (default) — in-process ctypes; the shipping behavior.
  - steam_client (NW_STEAM_WORKER=1) — isolated worker subprocess via RPC.

Phase 1 ships DARK: the env var defaults off, so this resolves to steam_api and
the app behaves identically. Flipping NW_STEAM_WORKER routes the same calls to
the worker — instant rollback either way (set/unset the var, no code change).

Usage (Phase 2 onward): `from steam_backend import steam` then `steam.fetch_batch(...)`,
`steam.steam_ready`, etc. — a drop-in for the current `import steam_api`.
"""
import os

from logger import get_logger

logger = get_logger("steam_backend")

# Default-ON since Phase 3 (the worker is the shipping backend): the worker is
# selected unless NW_STEAM_WORKER is explicitly set to a falsy value. Setting it
# to 0/false/no/off is the in-process rollback (the only backend without
# disconnect/crash-isolation).
_FLAG = os.environ.get("NW_STEAM_WORKER", "").strip().lower()
_USE_WORKER = _FLAG not in ("0", "false", "no", "off")

# True when the worker backend is active. bridge.py reads this to decide whether
# to run its own 100ms callback pump + cheater fetch (the in-process backend has
# neither built in; the worker runs both itself).
IS_WORKER = _USE_WORKER

if _USE_WORKER:
    import steam_client as steam
    logger.info("Steam backend: worker subprocess (default; NW_STEAM_WORKER=%r)", _FLAG or "unset")
else:
    import steam_api as steam
    logger.info("Steam backend: in-process steam_api (rollback; NW_STEAM_WORKER=%r)", _FLAG)
