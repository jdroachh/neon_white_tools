"""Frozen-build entry point.

PyInstaller runs the entry script standalone, which breaks the relative
imports inside `webview_app/main.py` (`from .bridge import ...`).
This launcher imports `webview_app.main` as a proper subpackage so those
relative imports resolve.

freeze_support() must be the FIRST call so worker processes pivot to the
worker target before we import webview_app.main (which would otherwise
re-fetch medal data, spawn resource threads, etc. on every worker spawn).

Dev mode still uses `python -m SteamScraper.webview_app.main` — this file
is only the frozen entry.
"""
import multiprocessing


if __name__ == "__main__":
    multiprocessing.freeze_support()
    # Only the main process reaches here — workers exit inside freeze_support.
    from webview_app.main import _main
    _main()
