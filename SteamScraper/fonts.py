"""GOHU font loading + Tkinter font tuples.

Extracted from neonwhite_app.py so tab modules can request fonts without
importing the main app module.
"""
import ctypes
import os

from logger import get_logger
logger = get_logger(__name__)

GOHU_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "GohuFont14NerdFont-Regular.ttf")
GOHU_FONT_NAME = "GohuFont 14 Nerd Font"


def load_gohu_font():
    """Register the GOHU font with Windows so Tkinter can use it."""
    if not os.path.exists(GOHU_FONT_PATH):
        return False
    try:
        FR_PRIVATE = 0x10
        result = ctypes.windll.gdi32.AddFontResourceExW(GOHU_FONT_PATH, FR_PRIVATE, 0)
        return result > 0
    except Exception:
        logger.debug("Custom font load via AddFontResourceExW failed; using fallback",
                     exc_info=True)
        return False


def gohu(size=14, bold=False, italic=False):
    """Return a Tkinter font tuple using GOHU if available, else Helvetica."""
    weight = "bold" if bold else "normal"
    if os.path.exists(GOHU_FONT_PATH):
        return (GOHU_FONT_NAME, size, weight)
    return ("Helvetica", size, weight)


def gohu_mono(size=14):
    """Monospace variant — GOHU if available, else Courier."""
    if os.path.exists(GOHU_FONT_PATH):
        return (GOHU_FONT_NAME, size, "normal")
    return ("Courier", size, "normal")
