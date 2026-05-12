# ADR: Window resize / snap-back on frameless Windows

**Date:** 2026-05-11
**Status:** Proposed — awaiting user approval before implementation

---

## Symptoms (reported by Restrain)

- Dragging window edges does nothing or causes the window to snap back.
- Window cannot be resized by grabbing its border.

---

## Current setup

```python
webview.create_window(
    frameless=True,
    easy_drag=False,
    width=1440, height=900,
    min_size=(800, 600),
    # no resizable param — defaults to True, but ineffective for frameless
)
webview.settings['DRAG_REGION_SELECTOR'] = '.titlebar'
```

**pywebview 6.2.1 · WebView2 · Windows 11**

---

## Root cause

`frameless=True` strips the native Win32 frame (`WS_CAPTION` / `WS_THICKFRAME`). That frame is what gives the OS its resize hit-test zones along the window edges. Without it, edge-dragging has no effect — the window neither resizes nor moves (because `easy_drag=False` and drag is limited to `.titlebar`). The "snap back" feel is the window not responding to the drag gesture at all and returning to where it started.

`resizable=True` (the default) only adds back the resize cursor and behaviour when the native frame is present. It has no effect on frameless windows.

---

## Options

### A — Drop `frameless=True` (native chrome)

Remove `frameless=True`. The OS draws its own title bar and resize border. Native edge-drag resize just works.

**Cost:** The custom title bar (NEON WHITE wordmark, window buttons) would sit below the OS title bar — ugly duplication. We'd need to either hide the custom `Titlebar` component or restyle it as a toolbar row below the native bar. The dark custom chrome disappears.

**Verdict:** Technically correct but visually regressive for our design.

---

### B — CSS invisible resize handles (recommended)

Keep `frameless=True`. Add a thin (6 px) transparent border layer around the window in CSS, divided into 8 hit zones (4 edges + 4 corners). Each zone listens for `mousedown` and calls a bridge method `resize_window_edge(edge)` that uses Win32 `SendMessage(WM_NCLBUTTONDOWN, HTLEFT / HTRIGHT / ...)` to hand the resize gesture back to the OS. This is the standard approach for custom-chrome Electron apps.

```
┌──────────────────────────────┐
│ N (top edge, cursor: n-resize)│
├─┬────────────────────────────┬─┤
│W│      window content        │E│
├─┴────────────────────────────┴─┤
│ S (bottom edge)               │
└──────────────────────────────┘
```

**Python side:** one new bridge method using `ctypes.windll.user32`:
```python
import ctypes, ctypes.wintypes
_HT = {"n": 12, "ne": 14, "e": 11, "se": 17, "s": 15, "sw": 16, "w": 10, "nw": 13}
WM_NCLBUTTONDOWN = 0x00A1

def resize_window_edge(self, edge: str) -> None:
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ht = _HT.get(edge)
    if ht:
        ctypes.windll.user32.ReleaseCapture()
        ctypes.windll.user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, ht, 0)
```

**JS side:** 8 `<div>` elements absolutely positioned around the border, each with the appropriate `cursor` style and `onMouseDown={() => api.resize_window_edge(edge)}`.

**Cost:** ~40 lines Python + ~60 lines CSS/JSX. Windows-only (the bridge method no-ops gracefully on other platforms). The hit zones need to sit above all other content in z-order — needs careful positioning so they don't eat clicks in the corner buttons area.

**Snap-back fix:** The snap-back is a symptom of the missing resize — once the resize gesture is wired, the window resizes normally and the OS tracks position. If snap-back persists after wiring (unlikely), we can additionally call `window.pywebview.api.save_window_pos()` on `resize` events and restore on next launch.

---

### C — Invisible resize only via `WS_THICKFRAME` re-injection

Keep `frameless=True` but patch the Win32 window style after creation to add back `WS_THICKFRAME` using ctypes. This restores OS edge-drag natively without any JS hit zones. Downside: the injected frame may draw a thin 1px border line on some DPI settings (WebView2 quirk).

**Verdict:** Worth trying as a one-liner, but the 1px artifact makes it less clean than Option B.

---

## Decision: A (implemented 2026-05-12)

Option B was fully explored and ruled out. All three JS/Win32 approaches failed:
1. React `onMouseDown` on fixed divs — OS intercepts edge clicks before WebView2 sees them.
2. `document.addEventListener("mousedown", ..., true)` capture — same: OS eats the event at Win32 level before any JS runs.
3. WM_NCHITTEST WNDPROC subclass — hook installs successfully (confirmed via log), returns HTLEFT/HTRIGHT/etc., but WebView2's input capture prevents the OS from acting on the resize HT codes. Cursor changes (mousemove passes through) but click-drag does not resize.

Root cause: WebView2 in pywebview occupies the full client area and intercepts all mouse input, including what the OS would normally treat as non-client-area events. Fixing this would require a dedicated native C/C++ extension or deep Win32 integration beyond scope for V1.

**Shipped: Option A.** Dropped `frameless=True`; native chrome provides edge-drag resize, window position persistence, and snap-to-edge. Custom `Titlebar` component removed from render — native title bar shows "Neon White Tools". The custom minimize/maximize/close bridge methods remain in bridge.py for potential future use.

## Recommendation: B (superseded — see Decision above)

Option B is the standard approach used by VS Code, Discord, and every other Electron-style frameless custom-chrome app on Windows. It's ~100 lines of contained change, it's Windows-only code behind a platform check, and it gives the user proper native OS resize semantics (snap-to-edge, quarter-tile, etc. all still work because the OS handles the gesture once we hand it `WM_NCLBUTTONDOWN`).

---

## Files to touch

- `SteamScraper/webview_app/bridge.py` — `resize_window_edge(edge)` method
- `frontend/src/api.js` — `resizeWindowEdge(edge)` wrapper
- `frontend/src/styles.css` or a new `ResizeHandles` component in `shared.jsx`

## Acceptance criteria

1. Dragging any window edge or corner resizes cleanly.
2. Resize cursor appears on hover over the 6px border zone.
3. Existing titlebar drag (move) still works.
4. No click-through issues on the rest of the UI.
5. App runs without errors on non-Windows (bridge method returns early).
