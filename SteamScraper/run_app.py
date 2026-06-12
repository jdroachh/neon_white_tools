"""Frozen-build entry point.

PyInstaller runs the entry script standalone, which breaks the relative
imports inside `webview_app/main.py` (`from .bridge import ...`).
This launcher imports `webview_app.main` as a proper subpackage so those
relative imports resolve.

freeze_support() must be the FIRST call so worker processes pivot to the
worker target before we import webview_app.main (which would otherwise
re-fetch medal data, spawn resource threads, etc. on every worker spawn).

The `--steam-worker` flag is the frozen Steam-worker pivot: when the EXE is
re-launched with it (by steam_client), we run the worker target and MUST NOT
import webview_app.main — the worker needs no HTTP server, webview window, or
medal threads, and importing it would fire all those side effects. Dev spawns
the loose steam_worker.py instead, so this branch is frozen-only in practice.

Dev mode still uses `python -m SteamScraper.webview_app.main` — this file
is only the frozen entry.
"""
import multiprocessing
import sys


if __name__ == "__main__":
    multiprocessing.freeze_support()
    # Only the main process reaches here — multiprocessing workers exit inside
    # freeze_support. Check the Steam-worker pivot BEFORE importing webview_app.main.
    if "--steam-worker" in sys.argv:
        from steam_worker import worker_main
        worker_main()
    else:
        from webview_app.main import _main
        _main()
