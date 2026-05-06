"""
main — pywebview bootstrap for the Neon White Tools Hi-Fi UI.

Entry point: python -m SteamScraper.webview_app.main

Loads frontend/dist/index.html into an Edge WebView2 window and exposes
JsApi as window.pywebview.api. SteamAPI_RunCallbacks polling is wired in
steam_runtime.py (M3); for now only the bridge is initialised.
"""
import os
import sys

import webview

from .bridge import JsApi

_DIST_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend", "dist",
)
_INDEX_HTML = os.path.join(_DIST_DIR, "index.html")


def _main():
    if not os.path.exists(_INDEX_HTML):
        sys.exit(
            f"[webview_app] frontend not built — expected: {_INDEX_HTML}\n"
            "Run: cd frontend && npm run build"
        )

    api = JsApi()
    window = webview.create_window(
        title="Neon White Tools",
        url=f"file:///{_INDEX_HTML.replace(os.sep, '/')}",
        js_api=api,
        width=1440,
        height=900,
        min_size=(800, 600),
        text_select=False,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    _main()
