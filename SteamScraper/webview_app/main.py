"""
main — pywebview bootstrap for the Neon White Tools Hi-Fi UI.

Entry point: python -m SteamScraper.webview_app.main

Serves frontend/dist/ over a loopback HTTP server so WebView2 loads the page
from http://127.0.0.1:<port>/ instead of file://. This gives the page a proper
origin, which is required for YouTube iframes to load without error 153.
"""
import multiprocessing
import os
import platform
import socket
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import webview

# ── Win32 title-bar theming ───────────────────────────────────────────────────
# Match the native title bar to the app's dark theme using DWM attributes.
# DWMWA_USE_IMMERSIVE_DARK_MODE works on Windows 10 21H1+.
# DWMWA_CAPTION_COLOR / DWMWA_TEXT_COLOR require Windows 11 Build 22000+.
# All three are applied best-effort — failures are logged and ignored.

def _rgb_to_colorref(hex_color: str) -> int:
    """Convert #RRGGBB to a Win32 COLORREF (0x00BBGGRR)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r

_TITLEBAR_BG   = "#050505"   # native titlebar bg, matched to the dark theme
_TITLEBAR_TEXT = "#f0f0e8"   # native titlebar text, matched to the dark theme

def _apply_titlebar_theme(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    import ctypes
    dwm = ctypes.windll.dwmapi
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    DWMWA_CAPTION_COLOR           = 35
    DWMWA_TEXT_COLOR              = 36

    try:
        dark = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                                   ctypes.byref(dark), ctypes.sizeof(dark))
    except Exception as e:
        _log.debug("titlebar dark mode unavailable: %s", e)

    for attr, color in ((DWMWA_CAPTION_COLOR, _TITLEBAR_BG),
                        (DWMWA_TEXT_COLOR,    _TITLEBAR_TEXT)):
        try:
            ref = ctypes.c_uint32(_rgb_to_colorref(color))
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(ref), ctypes.sizeof(ref))
        except Exception as e:
            _log.debug("DwmSetWindowAttribute attr=%d failed: %s", attr, e)

def _titlebar_theme_worker() -> None:
    """Poll until the window is visible, then apply DWM title-bar theming."""
    if sys.platform != "win32":
        return
    import ctypes
    import time
    for _ in range(40):
        time.sleep(0.1)
        hwnd = ctypes.windll.user32.FindWindowW(None, "Neon White Tools")
        if hwnd and ctypes.windll.user32.IsWindowVisible(hwnd):
            _apply_titlebar_theme(hwnd)
            _log.debug("titlebar theme applied to hwnd=0x%x", hwnd)
            return
    _log.warning("titlebar theme: window not found after 4s")

# sys.path setup so `logger` and `bridge` resolve identically.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import get_logger
from .bridge import JsApi, APP_VERSION

_log = get_logger(__name__)

# When frozen, frontend assets land inside the PyInstaller bundle's _internal/
# directory (a.k.a. sys._MEIPASS). In dev they sit three levels up from this file.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _DIST_DIR = os.path.join(sys._MEIPASS, "frontend", "dist")
else:
    _DIST_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "frontend", "dist",
    )
_INDEX_HTML = os.path.join(_DIST_DIR, "index.html")


def _install_crash_hooks() -> None:
    """Funnel uncaught exceptions (main thread + worker threads) into app.log.
    Without this, pywebview's traceback only reaches stderr — invisible to
    end-users running the frozen EXE.
    """
    def _hook(exc_type, exc_value, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, tb)
            return
        _log.exception("Unhandled exception", exc_info=(exc_type, exc_value, tb))
    sys.excepthook = _hook

    def _thread_hook(args):
        if issubclass(args.exc_type, SystemExit):
            return
        _log.exception(
            "Unhandled exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
    threading.excepthook = _thread_hook


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
    _install_crash_hooks()
    _log.info(
        "NeonWhiteTool v%s starting (Python %s on %s)",
        APP_VERSION, platform.python_version(), platform.platform(),
    )

    if not os.path.exists(_INDEX_HTML):
        sys.exit(
            f"[webview_app] frontend not built — expected: {_INDEX_HTML}\n"
            "Run: cd frontend && npm run build"
        )

    port = _find_free_port()
    _start_server(_DIST_DIR, port)

    threading.Thread(target=_titlebar_theme_worker, daemon=True).start()
    api = JsApi()
    webview.create_window(
        title="Neon White Tools",
        url=f"http://127.0.0.1:{port}/",
        js_api=api,
        width=1440,
        height=900,
        min_size=(800, 600),
        resizable=True,
        text_select=False,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    # Must be the very first call when frozen on Windows — without it, worker
    # processes re-execute the whole app instead of running the worker target.
    multiprocessing.freeze_support()
    _main()
