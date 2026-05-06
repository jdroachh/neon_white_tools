"""
steam_runtime — daemon thread for SteamAPI_RunCallbacks polling.

M3 implementation: moves the 100ms SteamAPI_RunCallbacks poll off the
(now-deleted) tkinter root.after() loop into a plain daemon thread.
The thread is started once Steam is initialised and stopped on window close.

Today (M1): stub only. The tkinter app still owns SteamAPI_RunCallbacks.
"""
# TODO(M3): implement _poll_thread() and start/stop lifecycle tied to webview window events
