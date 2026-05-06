"""
bridge — JsApi class exposed to the webview via pywebview js_api.

Every public method becomes callable from JS as window.pywebview.api.<method>.
Long-running operations push progress via progress.emit() rather than blocking.
"""
import importlib.metadata

APP_VERSION = "2.0.0-dev"


class JsApi:
    """pywebview js_api bridge. Instantiated once in main.py and passed to create_window."""

    def ping(self) -> dict:
        """Smoke-test endpoint. Returns ok + version so the UI can confirm the bridge is live."""
        return {"ok": True, "version": APP_VERSION}
