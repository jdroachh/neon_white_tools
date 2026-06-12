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

_USE_WORKER = os.environ.get("NW_STEAM_WORKER", "").strip().lower() in ("1", "true", "yes", "on")

if _USE_WORKER:
    import steam_client as steam
    logger.info("Steam backend: worker subprocess (NW_STEAM_WORKER on)")
else:
    import steam_api as steam
    logger.info("Steam backend: in-process steam_api (default)")
