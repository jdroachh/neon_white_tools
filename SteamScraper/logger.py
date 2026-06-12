"""
logger — centralized logging for the Neon White Tool.

Writes rotating log files to SteamScraper/logs/app.log and mirrors output to
stderr when run from a terminal. Level is INFO by default; flip via the
LOG_LEVEL env var or by editing _DEFAULT_LEVEL below.
"""
import logging
import logging.handlers
import os
import sys

# Logs live in %APPDATA%\NeonWhiteLeaderboardTool\logs — same root as the config
# (see bridge.py). This keeps user data out of the EXE folder so an update/reinstall
# (or a future self-updater's folder swap) never wipes or locks the log files.
_appdata = os.environ.get("APPDATA")
if _appdata:
    _HERE = os.path.join(_appdata, "NeonWhiteLeaderboardTool")
elif getattr(sys, "frozen", False):
    _HERE = os.path.dirname(sys.executable)
else:
    _HERE = os.path.dirname(os.path.abspath(__file__))
_LOG_DIR      = os.path.join(_HERE, "logs")
# The Steam worker subprocess sets NW_LOG_FILE so it logs to its own file
# (steam_worker.log) instead of sharing the parent's rotating app.log — two
# processes cannot share one RotatingFileHandler on Windows (file locking).
_LOG_FILE     = os.path.join(_LOG_DIR, os.environ.get("NW_LOG_FILE", "app.log"))
_MAX_BYTES    = 5 * 1024 * 1024   # 5 MB per file
_BACKUP_COUNT = 3                  # 3 rotated backups
_FORMAT       = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT      = "%Y-%m-%d %H:%M:%S"
_DEFAULT_LEVEL = logging.INFO

_configured = False


def _configure_root():
    """Configure root logger once. Idempotent."""
    global _configured
    if _configured:
        return
    _configured = True

    os.makedirs(_LOG_DIR, exist_ok=True)
    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    level_name = os.environ.get("LOG_LEVEL", "").upper()
    level = getattr(logging, level_name, _DEFAULT_LEVEL) if level_name else _DEFAULT_LEVEL

    root = logging.getLogger("neonwhite")
    root.setLevel(level)
    root.propagate = False

    # File handler — always on
    try:
        fh = logging.handlers.RotatingFileHandler(
            _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except Exception:
        # Logging setup itself must not crash the app — fall through to stderr only.
        pass

    # Stream handler — only when stderr is a real terminal (not a frozen EXE)
    if sys.stderr is not None:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(formatter)
        root.addHandler(sh)


def get_logger(name):
    """Return a module-scoped logger under the 'neonwhite' namespace."""
    _configure_root()
    # Strip __main__ / package prefix so names stay readable
    short = name.split(".")[-1] if name else "app"
    return logging.getLogger(f"neonwhite.{short}")


def get_log_dir() -> str:
    """Absolute path to the directory holding app.log.
    Created on first call so callers can safely open it in Explorer.
    """
    os.makedirs(_LOG_DIR, exist_ok=True)
    return _LOG_DIR
