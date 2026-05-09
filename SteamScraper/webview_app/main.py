"""
main — pywebview bootstrap for the Neon White Tools Hi-Fi UI.

Entry point: python -m SteamScraper.webview_app.main

Serves frontend/dist/ over a loopback HTTP server so WebView2 loads the page
from http://127.0.0.1:<port>/ instead of file://. This gives the page a proper
origin, which is required for YouTube iframes to load without error 153.
"""
import os
import socket
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import webview

from .bridge import JsApi

_DIST_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend", "dist",
)
_INDEX_HTML = os.path.join(_DIST_DIR, "index.html")


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(directory: str, port: int) -> None:
    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)
        def log_message(self, *args):
            pass  # silence request log noise

    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


def _main():
    if not os.path.exists(_INDEX_HTML):
        sys.exit(
            f"[webview_app] frontend not built — expected: {_INDEX_HTML}\n"
            "Run: cd frontend && npm run build"
        )

    port = _find_free_port()
    _start_server(_DIST_DIR, port)

    webview.settings['DRAG_REGION_SELECTOR'] = '.titlebar'

    api = JsApi()
    webview.create_window(
        title="Neon White Tools",
        url=f"http://127.0.0.1:{port}/",
        js_api=api,
        width=1440,
        height=900,
        min_size=(800, 600),
        text_select=False,
        frameless=True,
        easy_drag=False,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    _main()
