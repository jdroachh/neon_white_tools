"""
bridge — JsApi class exposed to the webview via pywebview js_api.

Every public method becomes callable from JS as window.pywebview.api.<method>.
Long-running operations push progress via window.evaluate_js rather than blocking.
"""
import json
import os
import queue
import re
import sys
import threading
from urllib.request import urlopen

# Workers import this module — avoid re-importing heavy tk-side things.
# sys.path already has SteamScraper/ when launched via main.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shuffle_lib import _load_c_shuffle, full_shuffle
from .hell_rush import score_hell_rush, HEALTHPACK_LEVELS
from rush_data import (LEVELS, LEVEL_LOOKUP, RUSH_LEVELS, RUSH_ALIASES, STANDARD_MEDAL_DATA,
                       CHAPTERS, WHOLE_GAME_LEVELS, RUSH_BOARDS, RUSH_BOARD_LOOKUP)
from seed_search import _seed_search_worker, _expected_match_count
from .models.resources import GuidesResponse, HelpfulLinksResponse
from .models.multi_compare import MultiCompareRequest
from . import resources as _resources
from . import multi_compare_cache
from . import avg_rankings as _avg_rankings

# Steam access goes through the backend selector: in-process steam_api (default)
# or the worker subprocess (NW_STEAM_WORKER=1). `steam` is a drop-in for the old
# `import steam_api`; IS_WORKER gates the bridge-side callback pump (see init_steam).
from steam_backend import steam, IS_WORKER

_resources.start_background_fetch()

APP_VERSION = "1.8.1"

_UPDATE_CACHE: dict = {}  # {"checked_at": float, "result": dict}
_UPDATE_CACHE_TTL_SEC = 6 * 60 * 60
_UPDATE_LATEST_URL = "https://api.github.com/repos/jdroachh/neon_white_tools/releases/latest"

def _parse_version_tuple(v: str) -> tuple:
    s = (v or "").strip().lstrip("vV")
    s = s.split("-", 1)[0]  # drop pre-release suffix like "-beta.2"
    parts = []
    for p in s.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)

# Community medal data — fetched once at module init in background threads.
# communitymedals.json: {code: [emerald_us, amethyst_us, sapphire_us]}
# topaz2.json:          {code: [topaz_us]}
# bd2.json:             {code: [bd_us]}
_COMMUNITY_MEDAL_DATA: dict = {}
_TOPAZ_MEDAL_DATA: dict = {}
_BD_MEDAL_DATA: dict = {}

_COMMUNITY_MEDALS_URL = "https://raw.githubusercontent.com/Faustas156/NeonLite/main/Resources/communitymedals.json"
_TOPAZ_MEDALS_URL     = "https://raw.githubusercontent.com/DerelictJade/NeonLite/main/Resources/topaz2.json"
_BD_MEDALS_URL        = "https://raw.githubusercontent.com/DerelictJade/NeonLite/main/Resources/bd2.json"

def _fetch_medal_data_bg():
    global _COMMUNITY_MEDAL_DATA, _TOPAZ_MEDAL_DATA, _BD_MEDAL_DATA
    for url, target in (
        (_COMMUNITY_MEDALS_URL, "_COMMUNITY_MEDAL_DATA"),
        (_TOPAZ_MEDALS_URL,     "_TOPAZ_MEDAL_DATA"),
        (_BD_MEDALS_URL,        "_BD_MEDAL_DATA"),
    ):
        try:
            with urlopen(url, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                data.pop("_metadata", None)
                globals()[target] = data
        except Exception:
            pass

threading.Thread(target=_fetch_medal_data_bg, daemon=True).start()

_RUSH_KEY = {
    "White / Mikey": "96",
    "Violet":        "violet",
    "Red":           "red",
    "Yellow":        "yellow",
}
_RUSH_COUNT = {
    "White / Mikey": 96,
    "Violet":        8,
    "Red":           8,
    "Yellow":        8,
}
RUSHES = [
    {"name": "White / Mikey", "count": 96},
    {"name": "Violet",        "count": 8},
    {"name": "Red",           "count": 8},
    {"name": "Yellow",        "count": 8},
]

_loaded = _load_c_shuffle()
if not _loaded:
    from logger import get_logger
    get_logger("bridge").warning(
        "shuffle.dll failed to load — full_shuffle using pure-Python fallback; "
        "Rush Seed Finder will be unavailable")

MAX_SEED = 2_147_483_647
# Small (8-level) sidequest rushes — Red, Violet, Yellow — match densely, so
# all 8! = 40,320 orderings provably appear within the first ~695k seeds,
# uniformly distributed. Capping the scan keeps the progress bar meaningful and
# finishes in under a second instead of stalling on a dense full-buffer return.
SMALL_RUSH_SCAN_CAP = 2_000_000

# ── Config ────────────────────────────────────────────────────────────────
# neonwhite_config.json lives in %APPDATA%\NeonWhiteLeaderboardTool\ so it
# survives app updates/reinstalls — the EXE folder can be wiped or replaced
# (incl. by a future self-updater) without touching the user's rosters, saved
# IDs, seeds, or settings. A one-time migration (_migrate_legacy_config below)
# copies a legacy beside-EXE / repo-root config forward on first launch.
_APP_DIR_NAME = "NeonWhiteLeaderboardTool"

# Legacy location (pre-APPDATA): beside the EXE when frozen, repo root in dev.
if getattr(sys, "frozen", False):
    _LEGACY_CONFIG_DIR = os.path.dirname(sys.executable)
else:
    _LEGACY_CONFIG_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_appdata = os.environ.get("APPDATA")
if _appdata:
    _CONFIG_DIR = os.path.join(_appdata, _APP_DIR_NAME)
else:
    # APPDATA unset (extremely rare) — fall back to the old beside-EXE behavior.
    _CONFIG_DIR = _LEGACY_CONFIG_DIR

_CONFIG_FILE        = os.path.join(_CONFIG_DIR, "neonwhite_config.json")
_LEGACY_CONFIG_FILE = os.path.join(_LEGACY_CONFIG_DIR, "neonwhite_config.json")
_DEFAULT_CONFIG = {
    "dll_path":        "",
    "output_folder":   os.path.expanduser("~\\Desktop"),
    "entry_count":     1000,
    "accent_color":    "#00e09a",
    "saved_profiles":  [],
    "saved_rosters":   [],
    "guide_watchlist":     [],
    "guide_watched":       [],
    "guide_hide_watched":  False,
    "guide_watchlist_only": False,
    "custom_levels_last_pl": [],
    "custom_levels_last_cp": [],
    "custom_levels_last_mc": [],
    "custom_levels_last_avg": [],
    "custom_level_presets":  [],
    "custom_rushes":         [],
}

_CONFIG_LOCK = __import__("threading").Lock()

def _migrate_legacy_config() -> None:
    """One-time: copy a pre-APPDATA config forward so users keep their saved
    data across the move. No-op if an APPDATA config already exists, if APPDATA
    is unavailable (same dir), or if there's no legacy file."""
    try:
        if os.path.exists(_CONFIG_FILE):
            return                       # already migrated / fresh APPDATA config
        if _CONFIG_DIR == _LEGACY_CONFIG_DIR:
            return                       # APPDATA fallback — nothing to migrate
        if not os.path.exists(_LEGACY_CONFIG_FILE):
            return
        import shutil
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        shutil.copy2(_LEGACY_CONFIG_FILE, _CONFIG_FILE)
        from logger import get_logger
        get_logger("bridge").info("Migrated legacy config %s -> %s",
                                  _LEGACY_CONFIG_FILE, _CONFIG_FILE)
    except Exception:
        try:
            from logger import get_logger
            get_logger("bridge").exception("Legacy config migration failed")
        except Exception:
            pass

_migrate_legacy_config()

def _load_config_raw() -> dict:
    """Read config from disk. Caller must hold _CONFIG_LOCK."""
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE) as f:
                cfg = json.load(f)
            for k, v in _DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return dict(_DEFAULT_CONFIG)

def _save_config_raw(cfg: dict) -> None:
    """Write config to disk atomically. Caller must hold _CONFIG_LOCK.

    Writes to a sibling .tmp then os.replace() to swap. Prevents an out-of-process
    reader (AV scan, the user inspecting the file, a crash mid-write) from ever
    seeing a truncated/empty config — which would otherwise surface as the
    "boots with defaults" bug (welcome reappears, accent lost, DLL forgotten).
    """
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    tmp = _CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, _CONFIG_FILE)

def _load_config() -> dict:
    with _CONFIG_LOCK:
        return _load_config_raw()

def _save_config(cfg: dict) -> None:
    with _CONFIG_LOCK:
        _save_config_raw(cfg)


def _resolve_rush(rush_name: str) -> tuple[str, int, list[str]]:
    """Return (key, num_levels, names_list) for a rush display name."""
    key   = _RUSH_KEY.get(rush_name, "96")
    count = _RUSH_COUNT.get(rush_name, 96)
    names = RUSH_LEVELS[key]
    return key, count, names


# ── Shared helpers (used by timer and finder) ─────────────────────────────

# Build a display-name → code lookup from LEVELS once.
_DISPLAY_TO_CODE = {disp.lower(): code.upper() for disp, code in LEVELS}

def _resolve_level_code(level_name: str) -> str | None:
    """Map a display name to its internal Steam stat code for medal lookup."""
    nl = level_name.lower().strip()
    code = _DISPLAY_TO_CODE.get(nl)
    if code:
        return code
    # Alias lookup (RUSH_ALIASES maps alias -> canonical display name)
    alias_target = RUSH_ALIASES.get(nl)
    if alias_target:
        return _DISPLAY_TO_CODE.get(alias_target.lower())
    return None


def _get_medal(level_name: str, secs: float) -> str:
    code = _resolve_level_code(level_name)
    if not code:
        return ""
    us = round(secs * 1000) * 1000   # snap to ms grid; int(secs*1_000_000) truncated 16.08 -> 16079999
    # Community medals are faster than DEV — check hardest first.
    bd = _BD_MEDAL_DATA.get(code)
    if bd and us <= bd[0]: return "BLOOD DIAMOND"
    topaz = _TOPAZ_MEDAL_DATA.get(code)
    if topaz and us <= topaz[0]: return "TOPAZ"
    comm = _COMMUNITY_MEDAL_DATA.get(code)
    if comm and len(comm) >= 3:
        if us <= comm[2]: return "SAPPHIRE"
        if us <= comm[1]: return "AMETHYST"
        if us <= comm[0]: return "EMERALD"
    std = STANDARD_MEDAL_DATA.get(code)
    if std:
        if us <= std[4]: return "DEV"
        if us <= std[3]: return "ACE"
        if us <= std[2]: return "GOLD"
        if us <= std[1]: return "SILVER"
        if us <= std[0]: return "BRONZE"
    return ""


def _next_medal(level_name: str, secs: float) -> dict | None:
    """Best medal just out of reach for `secs` on this level.
    Returns {"name", "gap_secs"} for the closest faster threshold, or None
    if no data or already at the top tier.
    """
    code = _resolve_level_code(level_name)
    if not code:
        return None
    us = round(secs * 1000) * 1000   # snap to ms grid; int(secs*1_000_000) truncated 16.08 -> 16079999
    tiers: list[tuple[str, int]] = []  # (name, threshold_us)
    bd = _BD_MEDAL_DATA.get(code)
    if bd: tiers.append(("BLOOD DIAMOND", bd[0]))
    topaz = _TOPAZ_MEDAL_DATA.get(code)
    if topaz: tiers.append(("TOPAZ", topaz[0]))
    comm = _COMMUNITY_MEDAL_DATA.get(code)
    if comm and len(comm) >= 3:
        tiers += [("SAPPHIRE", comm[2]), ("AMETHYST", comm[1]), ("EMERALD", comm[0])]
    std = STANDARD_MEDAL_DATA.get(code)
    if std:
        tiers += [("DEV", std[4]), ("ACE", std[3]), ("GOLD", std[2]),
                  ("SILVER", std[1]), ("BRONZE", std[0])]
    # Next target = the slowest threshold still faster than your time
    # (the closest tier you'd reach by improving). Robust to tier overlap.
    candidates = [(name, th) for name, th in tiers if th < us]
    if not candidates:
        return None
    name, th = max(candidates, key=lambda t: t[1])
    return {"name": name, "gap_secs": (us - th) / 1_000_000}


def _parse_time_to_secs(raw: str) -> float | None:
    s = (raw or "").strip()
    m = re.match(r'^(\d+):(\d{1,2})(?:\.(\d+))?$', s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)) + (float("0." + m.group(3)) if m.group(3) else 0)
    m2 = re.match(r'^(\d+)(?:\.(\d+))?$', s)
    if m2:
        return int(m2.group(1)) + (float("0." + m2.group(2)) if m2.group(2) else 0)
    return None


def _format_secs(secs: float) -> str:
    if secs < 60:
        return f"{secs:.3f}"
    mins = int(secs // 60)
    s = secs - mins * 60
    return f"{mins}:{s:06.3f}"


def _compute_medals(level_names: list[str], time_strs: list[str]) -> list[str]:
    medals = []
    for name, s in zip(level_names, time_strs):
        t = _parse_time_to_secs(s)
        medals.append(_get_medal(name, t) if t is not None else "")
    return medals


def _parse_level_names(raw: str, rush_key: str) -> tuple[list[int], str | None]:
    """Parse comma-separated level names/numbers. Returns (indices, error_or_None)."""
    names = RUSH_LEVELS[rush_key]
    name_map = {n.lower(): i for i, n in enumerate(names)}
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    indices = []
    for p in parts:
        pl = p.lower()
        if pl in name_map:
            indices.append(name_map[pl])
            continue
        alias = RUSH_ALIASES.get(pl)
        if alias and alias in name_map:
            indices.append(name_map[alias])
            continue
        matches = [i for i, n in enumerate(names) if pl in n.lower()]
        if len(matches) == 1:
            indices.append(matches[0])
        elif len(matches) > 1:
            return [], f'"{p}" matches multiple levels: {", ".join(names[i] for i in matches)}'
        else:
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(names):
                    indices.append(idx)
                else:
                    return [], f"Level number {p} out of range."
            else:
                return [], f'Unknown level: "{p}"'
    if not indices:
        return [], "No valid levels entered."
    return indices, None


def _emit(event_data: dict) -> None:
    """Push an event to the webview JS layer via evaluate_js."""
    try:
        import webview
        if webview.windows:
            js = f"window._nwFinderEvent && window._nwFinderEvent({json.dumps(event_data)})"
            webview.windows[0].evaluate_js(js)
    except Exception:
        pass


def _emit_to(handler: str, event_data: dict) -> None:
    """Push an event to a named JS handler."""
    try:
        import webview
        if webview.windows:
            js = f"window.{handler} && window.{handler}({json.dumps(event_data)})"
            webview.windows[0].evaluate_js(js)
    except Exception:
        pass


def _fmt_ms_clock(score_ms) -> str:
    """Format a millisecond leaderboard score as mm:ss.mmm. Used for Rush
    Rankings, where totals run long (White ~18 min) — the level-search
    '{s}.{ms}' format would be unreadable for whole-rush sums."""
    total_ms = max(0, int(score_ms))
    minutes = total_ms // 60000
    seconds = (total_ms % 60000) // 1000
    millis = total_ms % 1000
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def _csv_safe(value):
    """Neutralise CSV formula injection.

    Steam persona names are attacker-chosen and flow verbatim into exports; a
    name like ``=HYPERLINK(...)`` becomes a live formula when the CSV is opened
    in Excel/Sheets. Prefix a leading ``= + - @`` with a single quote so the
    cell is treated as text. Non-string / empty / benign values pass through.
    """
    if isinstance(value, str) and value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def _guard_output_folder(folder: str, out_mode: str) -> dict | None:
    """Validate CSV export folder before kicking off a worker thread.

    Returns an error dict to short-circuit the caller, or None if the folder
    is fine (or unused because out_mode is display-only).
    """
    if out_mode not in ("csv", "both"):
        return None
    f = str(folder).strip()
    if not f:
        return {"ok": False, "error": "Select an output folder."}
    if not os.path.isabs(f):
        # A relative path resolves against the launch CWD, which can be a
        # non-writable System32 (the class of bug behind the v1.7.0 crash).
        # Require an absolute destination.
        return {"ok": False, "error": f"Output folder must be an absolute path: {f}"}
    if not os.path.isdir(f):
        return {"ok": False, "error": f"Output folder does not exist: {f}"}
    return None


def _fetch_page(lb_handle, start, end):
    """steam.fetch_batch with retry-once on a genuine Steam failure.

    steam.fetch_batch returns None on a failed/timed-out call, distinct from []
    for a genuine empty window (past end of board / all-cheater page). On None we
    sleep briefly and retry once — a fast ``failed``-flag return would otherwise
    retry straight into the same transient. Returns:

      * None  → confirmed failure after the retry (caller counts a failed page)
      * []    → genuine empty window / end of board (caller breaks)
      * [...] → rows

    NOTE: this bridge-side retry-once would compound with any future
    steam_api-internal backoff/retry layer. If one is added, drop this retry
    (single edit here) or exclude fetch_batch from it — never both.
    """
    import time as _time
    batch = steam.fetch_batch(lb_handle, start, end)
    if batch is None:
        _time.sleep(0.5)
        batch = steam.fetch_batch(lb_handle, start, end)
    return batch


class JsApi:
    """pywebview js_api bridge. Instantiated once in main.py."""

    def __init__(self):
        # Serialises the check-and-set on _lb_running / _finder_running so two
        # rapid JS calls can't both pass the "already running?" gate and start
        # overlapping workers.
        self._run_gate = threading.Lock()

        # Worker backend: when the worker dies unexpectedly (Steam client exit,
        # worker fault — NOT a deliberate disconnect), push a lost-connection event
        # so the UI flips to "Not connected". This is what turns the old steam-exit
        # hard crash into graceful degradation.
        if IS_WORKER:
            steam.set_on_lost(lambda: _emit_to("_nwSteamEvent", {"type": "lost"}))

    # ── Smoke test ────────────────────────────────────────────────────────────

    def ping(self) -> dict:
        return {"ok": True, "version": APP_VERSION}

    # ── Rush metadata ─────────────────────────────────────────────────────────

    def get_rushes(self) -> list:
        """Return the list of available rush names and level counts."""
        return RUSHES

    # ── Seed Parser ───────────────────────────────────────────────────────────

    def parse_seed(self, rush_name: str, seed: str) -> dict:
        """
        Decode a seed into its resulting level order.
        Returns {ok, rush_name, seed, level_count, level_order} or {ok: false, error}.
        """
        try:
            s = int(str(seed).strip())
            if not (1 <= s <= 2_147_483_647):
                raise ValueError
        except ValueError:
            return {"ok": False, "error": "Seed must be an integer between 1 and 2,147,483,647."}

        _, count, names = _resolve_rush(rush_name)
        order = full_shuffle(count, s)
        return {
            "ok":          True,
            "rush_name":   rush_name,
            "seed":        s,
            "level_count": count,
            "level_order": [names[i] for i in order],
        }

    # ── Splits Updater ────────────────────────────────────────────────────────

    def reorder_splits(self, rush_name: str, seed: str,
                       gold: str, segments: str) -> dict:
        """
        Reorder standard-order splits to match the play order for a seed.
        gold, segments: newline-delimited strings (one time per line).
        Returns {ok, level_order, gold, segments} or {ok: false, error}.
        """
        try:
            s = int(str(seed).strip())
            if not (1 <= s <= 2_147_483_647):
                raise ValueError
        except ValueError:
            return {"ok": False, "error": "Seed must be an integer between 1 and 2,147,483,647."}

        key, count, names = _resolve_rush(rush_name)
        order = full_shuffle(count, s)

        gold_lines = [l for l in str(gold).splitlines() if l.strip()]
        seg_lines  = [l for l in str(segments).splitlines() if l.strip()]

        if gold_lines and len(gold_lines) != count:
            return {"ok": False, "error": f"Expected {count} gold splits, got {len(gold_lines)}."}
        if seg_lines and len(seg_lines) != count:
            return {"ok": False, "error": f"Expected {count} segment splits, got {len(seg_lines)}."}

        level_order = [names[i] for i in order]
        gold_out    = [gold_lines[i] for i in order] if gold_lines else []
        seg_out     = [seg_lines[i]  for i in order] if seg_lines  else []

        return {
            "ok":              True,
            "level_order":     level_order,
            "gold":            gold_out,
            "gold_medals":     _compute_medals(level_order, gold_out) if gold_out else [],
            "segments":        seg_out,
            "segment_medals":  _compute_medals(level_order, seg_out) if seg_out else [],
        }

    # ── Rush metadata ── (extended) ──────────────────────────────────────────

    def get_standard_order(self, rush_name: str) -> dict:
        """Return the standard (non-shuffled) level name list for a rush."""
        _, _, names = _resolve_rush(rush_name)
        return {"ok": True, "lines": list(names)}

    # ── Seed Finder ───────────────────────────────────────────────────────────

    def start_finder(self, rush_name: str, levels_str: str, depth: str,
                     mode: str, max_seeds: str,
                     hell_rush: bool = False, hell_rush_min: str = "70",
                     force_first: str = "",
                     excluded_levels: str = "", excluded_window: str = "",
                     order_matters: bool = False) -> dict:
        """
        Begin a seed search. Returns {ok} immediately; progress events are
        pushed to window._nwFinderEvent({type, ...}) in the JS layer.
        Event types: "progress" | "result" | "done" | "error"
        """
        if getattr(self, "_finder_running", False):
            return {"ok": False, "error": "Search already running."}

        key, count, names = _resolve_rush(rush_name)
        scan_max = SMALL_RUSH_SCAN_CAP if count <= 16 else MAX_SEED

        if order_matters and key == "96":
            return {"ok": False, "error": "Order Matters is only supported for Violet, Red, and Yellow."}

        if hell_rush and key != "96":
            return {"ok": False, "error": "Hell Rush Mode requires the White / Mikey rush."}
        try:
            hell_rush_min_int = max(0, min(100, int(str(hell_rush_min).strip())))
        except ValueError:
            return {"ok": False, "error": "Hell Rush threshold must be 0–100."}

        target_indices, err = _parse_level_names(levels_str.strip(), key)
        if err:
            return {"ok": False, "error": err}

        try:
            depth_int = int(str(depth).strip())
            if depth_int < 1 or depth_int > count:
                raise ValueError
        except ValueError:
            return {"ok": False, "error": f"Search Depth must be 1–{count}."}

        try:
            max_seeds_int = 1 if mode == "first" else max(1, int(str(max_seeds).strip() or "5"))
        except ValueError:
            max_seeds_int = 5

        # Force First Level — White / Mikey only
        forced_idx = None
        force_first_str = str(force_first or "").strip()
        if force_first_str:
            if key != "96":
                return {"ok": False, "error": "Force First Level is only supported for White / Mikey."}
            fi, ferr = _parse_level_names(force_first_str, key)
            if ferr or len(fi) != 1:
                return {"ok": False, "error": f"Force First Level: '{force_first_str}' is not a valid level."}
            forced_idx = fi[0]

        # Excluded Levels — White / Mikey only
        excluded_set: set[int] = set()
        excluded_window_int = 0
        excluded_str = str(excluded_levels or "").strip()
        excluded_window_raw = str(excluded_window or "").strip()
        if excluded_str or excluded_window_raw:
            if key != "96":
                return {"ok": False, "error": "Excluded Levels is only supported for White / Mikey."}
            ei, eerr = _parse_level_names(excluded_str, key)
            if eerr:
                return {"ok": False, "error": eerr}
            try:
                excluded_window_int = int(excluded_window_raw)
                if excluded_window_int < 1 or excluded_window_int > count - 1:
                    raise ValueError
            except ValueError:
                return {"ok": False, "error": f"Exclusion Window must be 1–{count - 1}."}
            excluded_set = set(ei)

        expected = _expected_match_count(count, len(target_indices), depth_int, scan_max)

        with self._run_gate:
            if getattr(self, "_finder_running", False):
                return {"ok": False, "error": "Search already running."}
            self._finder_running = True
            # Assign inside the gate so a Stop can't target the previous run's event.
            stop_event = self._finder_stop_event = threading.Event()
        self._finder_user_stopped = False

        num_cores = max(1, (__import__("os").cpu_count() or 1) - 1)
        chunk_size = scan_max // num_cores

        def manager():
            result_queue = queue.Queue()
            workers = []
            for core in range(num_cores):
                start = core * chunk_size + 1
                end = (core + 1) * chunk_size + 1 if core < num_cores - 1 else scan_max
                t = threading.Thread(
                    target=_seed_search_worker,
                    args=((start, end, count, set(target_indices), depth_int,
                           result_queue, stop_event),),
                    daemon=True,
                )
                t.start()
                workers.append(t)

            found = []
            done_workers = 0
            seeds_checked = 0

            while done_workers < num_cores:
                try:
                    item = result_queue.get(timeout=0.2)
                except Exception:
                    if stop_event.is_set():
                        break
                    continue

                if item is None:
                    done_workers += 1
                    continue

                if isinstance(item, tuple) and item and item[0] == "progress":
                    seeds_checked += item[1]
                    pct = min(99, int(seeds_checked / scan_max * 100))
                    _emit({"type": "progress", "seeds_checked": seeds_checked,
                           "total": scan_max, "found_count": len(found), "pct": pct})
                    continue

                seed = item
                if stop_event.is_set():
                    break
                order = full_shuffle(count, seed)
                if forced_idx is not None and order[0] != forced_idx:
                    continue
                if excluded_set and any(order[pos] in excluded_set for pos in range(excluded_window_int)):
                    continue
                if order_matters and any(order[i] != target_indices[i] for i in range(len(target_indices))):
                    continue
                target_set = set(target_indices)
                positions = {idx: pos + 1 for pos, idx in enumerate(order) if idx in target_set}
                is_white_mikey = key == "96"

                if hell_rush:
                    name_order = [names[idx] for idx in order]
                    score = score_hell_rush(name_order)
                    if score < hell_rush_min_int:
                        continue
                else:
                    score = None

                found.append(seed)
                level_order = [
                    {"name": names[idx], "is_target": idx in target_set,
                     "is_forced": idx == forced_idx,
                     "is_excluded": idx in excluded_set,
                     "position": positions.get(idx),
                     "is_healthpack": (names[idx] in HEALTHPACK_LEVELS) if is_white_mikey else False}
                    for pos, idx in enumerate(order)
                ]
                pos_strs = ", ".join(f"{names[idx]} @{positions[idx]}" for idx in target_indices)
                forced_prefix = (f"[{names[forced_idx]} @1] " if forced_idx is not None and forced_idx not in target_set else "")
                summary = forced_prefix + pos_strs + (f" · score {score}" if score is not None else "")
                _emit({"type": "result", "seed": seed, "summary": summary,
                       "score": score, "level_order": level_order})

                if len(found) >= max_seeds_int:
                    stop_event.set()
                    break

            user_stopped = getattr(self, "_finder_user_stopped", False)
            stop_event.set()
            for w in workers:
                w.join(timeout=2)

            msg = (f"Done. Found {len(found)} seed(s)."
                   if found else "No matching seeds found in full range.")
            _emit({"type": "done", "stopped": user_stopped,
                   "found_count": len(found), "message": msg})
            self._finder_running = False

        threading.Thread(target=manager, daemon=True).start()
        return {"ok": True, "expected": round(expected, 2)}

    def stop_finder(self) -> dict:
        # Signal the search to stop, but leave _finder_running set — the manager
        # clears it when it exits (after joining its workers, line ~653). Clearing
        # it here would let a new search start while the old workers are still
        # winding down.
        self._finder_user_stopped = True
        if hasattr(self, "_finder_stop_event"):
            self._finder_stop_event.set()
        return {"ok": True}

    # ── Run Timer ─────────────────────────────────────────────────────────────

    def load_timer_seed(self, rush_name: str, seed: str) -> dict:
        """Decode a seed and return level names pre-filled for the timer textarea."""
        try:
            s = int(str(seed).strip())
            if not (1 <= s <= MAX_SEED):
                raise ValueError
        except ValueError:
            return {"ok": False, "error": "Seed must be an integer between 1 and 2,147,483,647."}
        key, count, names = _resolve_rush(rush_name)
        order = full_shuffle(count, s)
        return {"ok": True, "lines": [names[i] for i in order]}

    def calculate_timer(self, rush_name: str, seed: str, splits_text: str,
                        cumulative: bool = True) -> dict:
        """
        Parse split times and compute segment times + medal grades.
        splits_text: one split per line, format "Name time" or "Name: time" or bare "time".
        cumulative: True  -> times are running totals (default; segments = successive diffs).
                    False -> times are per-segment durations (segments = the values as-is).
        seed is optional (pass "" to skip medal lookup fallback to standard order).
        Returns {ok, rows: [{name, cumulative, segment, segment_fmt, medal}]} or {ok: false, error}.
        """
        raw_lines = [l for l in str(splits_text).strip().splitlines() if l.strip()]
        if not raw_lines:
            return {"ok": False, "error": "Please enter at least one split time."}

        key, count, names = _resolve_rush(rush_name)

        values = []
        level_names = []
        errors = []

        for i, line in enumerate(raw_lines):
            # Fixed parser: try trailing-token as time first (covers "Name 1:51.85" and "Name 38.28")
            tokens = line.strip().split()
            t_val = None
            name_part = None
            if tokens:
                t_val = _parse_time_to_secs(tokens[-1])
                if t_val is not None:
                    name_part = " ".join(tokens[:-1]).rstrip(":") or f"Level {i + 1}"
            # Fallback: colon split for "Name: time" format
            if t_val is None and ":" in line:
                parts = line.split(":", 1)
                candidate = parts[1].strip()
                t_val = _parse_time_to_secs(candidate)
                if t_val is not None:
                    name_part = parts[0].strip() or f"Level {i + 1}"
            if t_val is None:
                errors.append(f"Row {i + 1}: cannot parse time from '{line.strip()}'")
                continue
            if cumulative and values and t_val <= values[-1]:
                errors.append(
                    f"Row {i + 1} ({name_part}): cumulative time {_format_secs(t_val)} must be "
                    f"greater than previous ({_format_secs(values[-1])})"
                )
                continue
            if not cumulative and t_val <= 0:
                errors.append(f"Row {i + 1} ({name_part}): segment time must be greater than 0")
                continue
            values.append(t_val)
            level_names.append(name_part)

        if errors:
            return {"ok": False, "error": "\n".join(errors)}

        if cumulative:
            cumulative_totals = values
            segments = [values[0]] + [values[i] - values[i - 1]
                                       for i in range(1, len(values))]
        else:
            segments = values
            cumulative_totals = []
            running = 0.0
            for v in values:
                running += v
                cumulative_totals.append(running)
        cumulative = cumulative_totals
        rows = []
        for i, (seg, cum, name) in enumerate(zip(segments, cumulative, level_names)):
            medal = _get_medal(name, seg)
            rows.append({
                "name":         name,
                "cumulative":   _format_secs(cum),
                "segment":      seg,
                "segment_fmt":  _format_secs(seg),
                "medal":        medal,
            })

        return {"ok": True, "rows": rows}

    # ── Standardize Splits ────────────────────────────────────────────────────

    # ── Config ───────────────────────────────────────────────────────────────

    def get_config(self) -> dict:
        return _load_config()

    def save_config_field(self, key: str, value) -> dict:
        with _CONFIG_LOCK:
            cfg = _load_config_raw()
            cfg[key] = value
            _save_config_raw(cfg)
        return {"ok": True}

    def save_config_fields(self, fields: dict) -> dict:
        """Atomically update multiple config keys in one write."""
        with _CONFIG_LOCK:
            cfg = _load_config_raw()
            cfg.update(fields)
            _save_config_raw(cfg)
        return {"ok": True}

    # ── Steam runtime ─────────────────────────────────────────────────────────

    def init_steam(self, dll_path: str) -> dict:
        ok, msg = steam.init_steam(dll_path)
        if ok:
            # Locked read-modify-write so a concurrent boot-time
            # save_config_field (accent, profiles) isn't clobbered.
            with _CONFIG_LOCK:
                cfg = _load_config_raw()
                cfg["dll_path"] = dll_path
                _save_config_raw(cfg)
            # The in-process backend has no internal callback pump and doesn't
            # auto-fetch the cheater list, so the bridge drives both here. The
            # worker backend runs its own pump + cheater fetch inside the child,
            # so we skip this entirely (steam.run_callbacks/fetch_cheater_list are
            # no-ops there anyway).
            if not IS_WORKER and not getattr(self, "_steam_polling", False):
                self._steam_polling = True
                import time as _time

                def _poll():
                    while steam.steam_ready:
                        try:
                            steam.run_callbacks()
                        except Exception:
                            pass
                        _time.sleep(0.1)
                    self._steam_polling = False

                threading.Thread(target=_poll, daemon=True).start()
                threading.Thread(target=steam.fetch_cheater_list, daemon=True).start()
        return {
            "ok":          ok,
            "message":     msg,
            "player_name": steam.player_name if ok else "",
            "steam_id":    str(steam.logged_in_steam_id) if ok else "",
        }

    def disconnect_steam(self) -> dict:
        """Release the Steam session by killing the worker subprocess — the only
        thing that frees the appid (Steam binds it to the SteamAPI_Init PID until
        that PID dies). Refused mid-run so we never yank the session out from under
        an in-flight leaderboard/finder worker.

        Only the worker backend can disconnect; in-process (NW_STEAM_WORKER=0) has
        no way to release the appid without exiting the whole app, so it's refused.
        """
        if not IS_WORKER:
            return {"ok": False,
                    "error": "Disconnect requires the worker backend (unset NW_STEAM_WORKER)."}
        if getattr(self, "_lb_running", False) or getattr(self, "_finder_running", False):
            return {"ok": False, "error": "An operation is running — stop it first."}
        try:
            steam.shutdown()
        except Exception as e:
            return {"ok": False, "error": f"Disconnect failed: {e}"}
        return {"ok": True}

    def get_cheater_count(self) -> int:
        return len(steam.cheater_ids)

    def get_steam_status(self) -> dict:
        return {
            "ready":       steam.steam_ready,
            "player_name": steam.player_name,
            "steam_id":    str(steam.logged_in_steam_id),
        }

    def pick_dll_file(self) -> dict:
        try:
            import webview
            if webview.windows:
                result = webview.windows[0].create_file_dialog(
                    webview.OPEN_DIALOG,
                    file_types=("DLL Files (*.dll)", "All Files (*.*)"),
                )
                if result:
                    return {"ok": True, "path": result[0]}
        except Exception:
            pass
        return {"ok": False, "path": ""}

    def pick_folder(self) -> dict:
        try:
            import webview
            if webview.windows:
                result = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
                if result:
                    return {"ok": True, "path": result[0]}
        except Exception:
            pass
        return {"ok": False, "path": ""}

    def find_steam_dll(self) -> dict:
        """User-triggered DLL finder. Never called on startup."""
        from .dll_finder import find_neon_white_dll
        return find_neon_white_dll()

    def open_log_folder(self) -> dict:
        """Open the log directory in the user's file explorer.
        Beta tester workflow: click → Explorer opens → drag app.log into Discord.
        """
        from logger import get_log_dir
        path = get_log_dir()
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "path": path, "error": str(e)}

    def open_config_folder(self) -> dict:
        """Open the folder holding neonwhite_config.json (%APPDATA%\\NeonWhiteLeaderboardTool)."""
        path = _CONFIG_DIR
        try:
            os.makedirs(path, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "path": path, "error": str(e)}

    def export_config(self) -> dict:
        """Write the full config to a user-chosen .json via a Save dialog.

        Full backup: saved profiles, rosters, seeds, accent, watchlists, paths —
        everything in neonwhite_config.json. Used to carry data between app
        versions or back it up.
        """
        try:
            import time
            import webview
            if not webview.windows:
                return {"ok": False, "error": "No window available."}
            cfg = _load_config()
            default_name = f"neonwhite_backup_{time.strftime('%Y%m%d')}.json"
            result = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=default_name,
                file_types=("JSON Files (*.json)", "All Files (*.*)"),
            )
            if not result:
                return {"ok": False, "cancelled": True}
            path = result if isinstance(result, str) else result[0]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            return {"ok": True, "path": path}
        except Exception as e:
            try:
                from logger import get_logger
                get_logger("bridge").exception("export_config failed")
            except Exception:
                pass
            return {"ok": False, "error": str(e)}

    def save_text_file(self, default_name: str, content: str) -> dict:
        """Write arbitrary text to a user-chosen file via a Save dialog.

        WebView2 silently drops browser blob/anchor downloads, so pages that
        build a file client-side (e.g. Multi Compare CSV export) route the
        content here to be written by Python. Generic on purpose. Returns
        {ok, path} / {cancelled} / {error}.
        """
        try:
            import webview
            if not webview.windows:
                return {"ok": False, "error": "No window available."}
            name = str(default_name or "export.txt")
            is_csv = name.lower().endswith(".csv")
            file_types = (
                ("CSV Files (*.csv)", "All Files (*.*)") if is_csv
                else ("Text Files (*.txt)", "All Files (*.*)")
            )
            result = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=name,
                file_types=file_types,
            )
            if not result:
                return {"ok": False, "cancelled": True}
            path = result if isinstance(result, str) else result[0]
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(content if isinstance(content, str) else str(content))
            return {"ok": True, "path": path}
        except Exception as e:
            try:
                from logger import get_logger
                get_logger("bridge").exception("save_text_file failed")
            except Exception:
                pass
            return {"ok": False, "error": str(e)}

    def import_config(self) -> dict:
        """Restore config from a user-chosen .json via an Open dialog.

        Full restore: recognised keys overwrite the current config; unknown keys
        are dropped (light validation) and any missing keys fall back to defaults.
        Overwrites machine-specific paths too (dll_path/output_folder) — the
        primary use case is migrating saved data to a freshly downloaded version
        on the same machine.
        """
        try:
            import webview
            if not webview.windows:
                return {"ok": False, "error": "No window available."}
            result = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=("JSON Files (*.json)", "All Files (*.*)"),
            )
            if not result:
                return {"ok": False, "cancelled": True}
            path = result if isinstance(result, str) else result[0]
            with open(path, encoding="utf-8") as f:
                incoming = json.load(f)
            if not isinstance(incoming, dict):
                return {"ok": False, "error": "That file isn't a Neon White config backup."}
            imported = [k for k in _DEFAULT_CONFIG if k in incoming]
            with _CONFIG_LOCK:
                merged = dict(_DEFAULT_CONFIG)
                for k in _DEFAULT_CONFIG:
                    if k in incoming:
                        merged[k] = incoming[k]
                _save_config_raw(merged)
            return {"ok": True, "path": path, "imported_keys": imported,
                    "count": len(imported)}
        except json.JSONDecodeError:
            return {"ok": False, "error": "That file isn't valid JSON."}
        except Exception as e:
            try:
                from logger import get_logger
                get_logger("bridge").exception("import_config failed")
            except Exception:
                pass
            return {"ok": False, "error": str(e)}

    def get_app_version(self) -> str:
        return APP_VERSION

    def check_for_update(self) -> dict:
        """Compare APP_VERSION to GitHub's latest release tag. Cached 6h."""
        import time
        now = time.time()
        cached = _UPDATE_CACHE.get("result")
        if cached and (now - _UPDATE_CACHE.get("checked_at", 0)) < _UPDATE_CACHE_TTL_SEC:
            return cached
        result = {"ok": False, "current": APP_VERSION, "update_available": False}
        try:
            req_headers = {"User-Agent": f"NeonWhiteTool/{APP_VERSION}",
                           "Accept": "application/vnd.github+json"}
            from urllib.request import Request
            req = Request(_UPDATE_LATEST_URL, headers=req_headers)
            with urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            tag = data.get("tag_name") or ""
            latest = tag.lstrip("vV") or APP_VERSION
            result = {
                "ok": True,
                "current": APP_VERSION,
                "latest": latest,
                "update_available": _parse_version_tuple(latest) > _parse_version_tuple(APP_VERSION),
                "release_url": data.get("html_url") or "",
                "release_notes": data.get("body") or "",
            }
            _UPDATE_CACHE["result"] = result
            _UPDATE_CACHE["checked_at"] = now
        except Exception as e:
            try:
                from logger import get_logger
                get_logger("bridge").info("check_for_update failed: %s", e)
            except Exception:
                pass
            result["error"] = str(e)
        return result

    # ── Level / chapter metadata ──────────────────────────────────────────────

    def get_levels(self) -> list:
        return [{"display": d, "internal": i} for d, i in LEVELS]

    def get_chapters(self) -> list:
        return [{"name": k, "levels": v} for k, v in CHAPTERS.items()]

    # ── Leaderboard operations ────────────────────────────────────────────────

    def _run_worker_safe(self, fn, channel: str) -> None:
        """Wrap a leaderboard worker so any unhandled exception still emits a
        done/error event and clears _lb_running. Without this, an exception in
        the worker thread (bad output path, permission error, etc.) leaves the
        UI thinking the run is still in progress forever."""
        try:
            fn()
        except Exception as exc:
            _emit_to(channel, {
                "type": "done", "stopped": True, "error": True,
                "message": f"Export failed: {exc}",
            })
        finally:
            self._lb_running = False

    def run_global_export(self, count: str, out_mode: str = "display", folder: str = "") -> dict:
        import time as _time, csv as _csv
        if not steam.steam_ready:
            return {"ok": False, "error": "Steam not connected. Connect in Settings first."}
        if getattr(self, "_lb_running", False):
            return {"ok": False, "error": "An operation is already running."}
        try:
            count_int = max(1, int(str(count).strip()))
        except ValueError:
            return {"ok": False, "error": "Entry count must be a number."}
        err = _guard_output_folder(folder, out_mode)
        if err:
            return err

        with self._run_gate:
            if getattr(self, "_lb_running", False):
                return {"ok": False, "error": "An operation is already running."}
            self._lb_running = True
            # Capture the event in a local (inside the gate) so a later run that
            # reassigns self._lb_stop_event can't make this worker poll the wrong
            # event, and a Stop can't target the previous run's event.
            stop_event = self._lb_stop_event = threading.Event()

        def worker():
            csv_path = None
            csv_file = None
            writer = None
            if out_mode in ("csv", "both"):
                csv_path = os.path.join(folder.strip(), f"neon_white_top_{count_int}_entries.csv")
                csv_file = open(csv_path, "w", newline="", encoding="utf-8")
                writer = _csv.DictWriter(
                    csv_file, fieldnames=["rank", "level", "name", "score_ms", "time"])
                writer.writeheader()

            total_levels = len(LEVELS)
            all_rows = 0
            failed_pages = 0   # run-wide count of pages that failed after a retry
            for idx, (display, internal) in enumerate(LEVELS, 1):
                if stop_event.is_set():
                    break
                _emit_to("_nwGlobalEvent", {
                    "type": "progress", "level_idx": idx,
                    "total_levels": total_levels, "level_name": display,
                })
                lb = steam.find_leaderboard(internal)
                if not lb:
                    continue
                total_lb = steam.get_entry_count(lb)
                fetch = min(total_lb, count_int)
                start = 1
                while start <= fetch and not stop_event.is_set():
                    end = min(start + steam.BATCH_SIZE - 1, fetch)
                    batch = _fetch_page(lb, start, end)
                    if batch is None:
                        # Steam failed this page (after a retry). Skip to the next
                        # level rather than aborting the whole export; count it so
                        # the done message can warn the data is incomplete.
                        failed_pages += 1
                        break
                    if not batch:
                        break   # genuine end of this board
                    for e in batch:
                        if out_mode in ("display", "both"):
                            _emit_to("_nwGlobalEvent", {
                                "type": "row", "rank": e["rank"],
                                "level": display, "name": e["name"], "time": e["time"],
                                "medal": _get_medal(display, e["score_ms"] / 1000.0),
                            })
                        if writer:
                            writer.writerow({"rank": e["rank"], "level": display,
                                             "name": _csv_safe(e["name"]), "score_ms": e["score_ms"],
                                             "time": e["time"]})
                    all_rows += len(batch)
                    start = end + 1
                    _time.sleep(0.05)
                if csv_file:
                    csv_file.flush()

            if csv_file:
                csv_file.close()
            stopped = stop_event.is_set()
            msg = (f"Stopped. {all_rows} entries fetched." if stopped
                   else f"Done. {all_rows} entries fetched.")
            if failed_pages:
                msg += f" {failed_pages} page(s) failed — data may be incomplete."
            _emit_to("_nwGlobalEvent", {
                "type": "done", "total_rows": all_rows, "stopped": stopped,
                "csv_path": csv_path or "", "failed_pages": failed_pages,
                "message": msg,
            })
            self._lb_running = False

        threading.Thread(
            target=lambda: self._run_worker_safe(worker, "_nwGlobalEvent"),
            daemon=True,
        ).start()
        return {"ok": True}

    def run_global_neon_rankings(self, count: str, out_mode: str = "display", folder: str = "") -> dict:
        """Top-N entries from the GlobalNeonRankings aggregate board.

        Story-only sum of all level times (in ms). In-game total adds Sidequest
        client-side per modders — that's not Steam-queryable. See memory
        [[project-global-neon-rankings]] for the discrepancy.
        """
        import time as _time, csv as _csv
        if not steam.steam_ready:
            return {"ok": False, "error": "Steam not connected. Connect in Settings first."}
        if getattr(self, "_lb_running", False):
            return {"ok": False, "error": "An operation is already running."}
        try:
            count_int = max(1, int(str(count).strip()))
        except ValueError:
            return {"ok": False, "error": "Entry count must be a number."}
        err = _guard_output_folder(folder, out_mode)
        if err:
            return err

        with self._run_gate:
            if getattr(self, "_lb_running", False):
                return {"ok": False, "error": "An operation is already running."}
            self._lb_running = True
            # Capture the event in a local (inside the gate) so a later run that
            # reassigns self._lb_stop_event can't make this worker poll the wrong
            # event, and a Stop can't target the previous run's event.
            stop_event = self._lb_stop_event = threading.Event()

        def worker():
            csv_path = None
            csv_file = None
            writer = None
            if out_mode in ("csv", "both"):
                csv_path = os.path.join(folder.strip(), f"neon_white_global_rankings_top_{count_int}.csv")
                csv_file = open(csv_path, "w", newline="", encoding="utf-8")
                writer = _csv.DictWriter(csv_file, fieldnames=["rank", "name", "score_ms", "time"])
                writer.writeheader()

            _emit_to("_nwNeonRankingsEvent", {"type": "status", "message": "Finding leaderboard..."})
            lb = steam.find_leaderboard("GlobalNeonRankings")
            if not lb:
                _emit_to("_nwNeonRankingsEvent", {"type": "error",
                                                  "message": "GlobalNeonRankings leaderboard not found."})
                if csv_file:
                    csv_file.close()
                self._lb_running = False
                return

            total_lb = steam.get_entry_count(lb)
            fetch = min(total_lb, count_int)
            all_rows = 0
            failed_pages = 0
            start = 1
            while start <= fetch and not stop_event.is_set():
                end = min(start + steam.BATCH_SIZE - 1, fetch)
                _emit_to("_nwNeonRankingsEvent", {"type": "progress",
                                                  "current": end, "total": fetch})
                batch = _fetch_page(lb, start, end)
                if batch is None:
                    failed_pages += 1
                    break   # Steam failed this page (after retry) — surface below
                if not batch:
                    break   # genuine end of board
                for e in batch:
                    if out_mode in ("display", "both"):
                        _emit_to("_nwNeonRankingsEvent", {
                            "type": "row", "rank": e["rank"],
                            "name": e["name"], "time": e["time"], "score_ms": e["score_ms"],
                        })
                    if writer:
                        writer.writerow({"rank": e["rank"], "name": _csv_safe(e["name"]),
                                         "score_ms": e["score_ms"], "time": e["time"]})
                all_rows += len(batch)
                start = end + 1
                _time.sleep(0.05)
                if csv_file:
                    csv_file.flush()

            if csv_file:
                csv_file.close()
            stopped = stop_event.is_set()
            msg = (f"Stopped. {all_rows} entries fetched." if stopped
                   else f"Done. {all_rows} entries fetched.")
            if failed_pages:
                msg += f" {failed_pages} page(s) failed — data may be incomplete."
            _emit_to("_nwNeonRankingsEvent", {
                "type": "done", "total_rows": all_rows, "stopped": stopped,
                "csv_path": csv_path or "", "failed_pages": failed_pages,
                "message": msg,
            })
            self._lb_running = False

        threading.Thread(
            target=lambda: self._run_worker_safe(worker, "_nwNeonRankingsEvent"),
            daemon=True,
        ).start()
        return {"ok": True}

    def get_global_neon_rank(self, steam_id: str) -> dict:
        """Single-player lookup on GlobalNeonRankings. Story-only — see
        [[project-global-neon-rankings]]. Returns {ok, rank, score_ms, time}
        or {ok: False, error} when the player has no entry."""
        if not steam.steam_ready:
            return {"ok": False, "error": "Steam not connected."}
        try:
            sid = int(str(steam_id).strip())
        except ValueError:
            return {"ok": False, "error": "Invalid Steam ID."}

        lb = steam.find_leaderboard("GlobalNeonRankings")
        if not lb:
            return {"ok": False, "error": "GlobalNeonRankings leaderboard not found."}
        entry = steam.get_player_entry(lb, sid)
        if not entry:
            return {"ok": False, "error": "No entry on Global Rankings."}
        pname = steam.get_persona_name(sid)
        total = steam.get_entry_count(lb)
        return {
            "ok": True,
            "rank": entry.global_rank,
            "name": pname,
            "total": total,
            "score_ms": entry.score,
            "time": f"{entry.score / 1000:.3f}",
        }

    def run_avg_rankings(self, k: str = "500", scope: str = "story+side",
                         out_mode: str = "display", folder: str = "",
                         source: str = "depth", sids=None, levels: str = "[]") -> dict:
        """Average Placement Leaderboard — rank players by mean per-level placement.

        Seed method: take the top-`k` players from GlobalNeonRankings (complete-game
        players), then look up each one's rank on every in-scope board via batched
        get_player_entries, and score the average. The consistency counterpart to the
        sum-of-times GlobalNeonRankings page. Players without a complete game have no
        GlobalNeonRankings entry and are unrankable here (known v1 exclusion).
        See plans/2026-06-22-avg-rankings-in-app.md.
        """
        import time as _time, csv as _csv, datetime as _dt
        if not steam.steam_ready:
            return {"ok": False, "error": "Steam not connected. Connect in Settings first."}
        if getattr(self, "_lb_running", False):
            return {"ok": False, "error": "An operation is already running."}
        if scope not in ("story", "story+side", "side", "custom"):
            scope = "story+side"

        # Resolve the in-scope boards. "custom" reuses the shared level resolver
        # (a JSON list of display names -> (display, internal) pairs) that Player
        # Lookup / Compare use for their own custom mode.
        if scope == "custom":
            board_pairs, _ctx, lerr = self._resolve_levels_for_mode("custom", levels)
            if lerr:
                return lerr
        else:
            board_pairs = _avg_rankings.board_list(scope)

        # Candidate source: "depth" pages the top-k of GlobalNeonRankings;
        # "roster" scores an explicit, user-supplied Steam-ID list with no
        # coverage gate (the user chose these players, so partial coverage is
        # shown, not dropped).
        source = source if source in ("depth", "roster") else "depth"
        roster_sids = None
        if source == "roster":
            raw = sids if isinstance(sids, list) else []
            if not raw:
                return {"ok": False, "error": "Add at least one Steam ID to the roster."}
            roster_sids = []
            seen = set()
            for s in raw:
                s = str(s).strip()
                if not (s.isdigit() and len(s) == 17):
                    return {"ok": False, "error": f"Invalid Steam ID: {s or '(empty)'}"}
                v = int(s)
                if v not in seen:
                    seen.add(v)
                    roster_sids.append(v)
            k_int = len(roster_sids)
        else:
            try:
                k_int = max(1, int(str(k).strip()))
            except ValueError:
                return {"ok": False, "error": "Candidate count must be a number."}

        err = _guard_output_folder(folder, out_mode)
        if err:
            return err

        with self._run_gate:
            if getattr(self, "_lb_running", False):
                return {"ok": False, "error": "An operation is already running."}
            self._lb_running = True
            # Capture in a local (inside the gate) so a later run reassigning
            # self._lb_stop_event can't make this worker poll the wrong event,
            # and a Stop can't target the previous run's event.
            stop_event = self._lb_stop_event = threading.Event()

        def worker():
            CH = "_nwAvgRankEvent"
            if source == "roster":
                # Explicit roster: no Global seed. Resolve display names up front
                # the same way Player Lookup / Compare do (get_persona_name), with
                # the SteamID string as the fallback for unknown personas.
                _emit_to(CH, {"type": "status", "message": "Resolving player names…"})
                sids = list(roster_sids)
                names = {}
                for sid in sids:
                    if stop_event.is_set():
                        break
                    try:
                        nm = steam.get_persona_name(sid)
                    except Exception:
                        nm = ""
                    names[sid] = nm or str(sid)
                ranks = {sid: {} for sid in sids}
                entry_counts = {}
            else:
                _emit_to(CH, {"type": "status",
                              "message": "Selecting the top players to measure (from Global Rankings)…"})
                glb = steam.find_leaderboard("GlobalNeonRankings")
                if not glb:
                    _emit_to(CH, {"type": "error",
                                  "message": "GlobalNeonRankings leaderboard not found."})
                    self._lb_running = False
                    return

                # Page the top-k candidate set (cheater-filtered by fetch_batch already).
                candidates = []
                start = 1
                while start <= k_int and not stop_event.is_set():
                    end = min(start + steam.BATCH_SIZE - 1, k_int)
                    batch = _fetch_page(glb, start, end)
                    if batch is None:
                        # Hard error, NOT warn-and-continue: a failed seed page
                        # silently shrinks the candidate *population*, biasing every
                        # board's placement stats for the whole run. Abort so the
                        # user re-runs against the full top-k (matches the
                        # no-candidates hard error just below).
                        _emit_to(CH, {"type": "error",
                                      "message": "Couldn't fetch the full top-k candidate set — "
                                                 "Steam failed. Please try again."})
                        self._lb_running = False
                        return
                    if not batch:
                        break   # genuine end of the Global Rankings board
                    candidates.extend(batch)
                    start = end + 1
                if not candidates:
                    _emit_to(CH, {"type": "error",
                                  "message": "No candidates returned from Global Rankings."})
                    self._lb_running = False
                    return

                names = {c["steam_id"]: c["name"] for c in candidates}
                sids = [c["steam_id"] for c in candidates]
                ranks = {sid: {} for sid in sids}
                entry_counts = {}

            total_boards = len(board_pairs)
            board_times = []   # wall-clock per completed board, for ETA
            empty_boards = []  # display names that returned zero coverage (diagnostic)
            for idx, (display, internal) in enumerate(board_pairs, 1):
                if stop_event.is_set():
                    break
                # ETA: mean of completed boards x remaining. Skip the first 2
                # (handle-resolve + entry-count make them slower/noisier).
                eta = None
                if len(board_times) >= 2:
                    eta = (sum(board_times) / len(board_times)) * (total_boards - idx + 1)

                t_board = _time.time()
                # Board-start tick — keeps the UI moving while the handle resolves.
                _emit_to(CH, {"type": "progress", "board_idx": idx,
                              "total_boards": total_boards, "board_name": display,
                              "eta_seconds": eta, "chunk_idx": 0, "chunk_total": 0,
                              "slow": False})
                lb = steam.find_leaderboard(internal)
                if not lb:
                    empty_boards.append(display)  # didn't resolve — no data for anyone
                    board_times.append(_time.time() - t_board)
                    continue
                entry_counts[internal] = steam.get_entry_count(lb)
                chunk_list = list(_avg_rankings.chunks(sids, 100))
                nchunks = len(chunk_list)
                found = 0
                for ci, chunk in enumerate(chunk_list, 1):
                    if stop_event.is_set():
                        break
                    _emit_to(CH, {"type": "progress", "board_idx": idx,
                                  "total_boards": total_boards, "board_name": display,
                                  "eta_seconds": eta, "chunk_idx": ci,
                                  "chunk_total": nchunks,
                                  "slow": (_time.time() - t_board) > 45})
                    # fallback=False: a player missing this board is expected, not an
                    # error — skip the per-sid retry that otherwise turns an all-missing
                    # 100-id chunk into 100 single calls (minutes on sparse boards).
                    res = steam.get_player_entries(lb, chunk, fallback=False)
                    for sid, entry in res.items():
                        if entry is not None:
                            ranks[sid][internal] = entry.global_rank
                            found += 1
                    _time.sleep(0.02)
                if found == 0 and not stop_event.is_set():
                    empty_boards.append(display)  # resolved but nobody charted
                board_times.append(_time.time() - t_board)

            if empty_boards:
                from logger import get_logger
                get_logger("bridge").info(
                    "avg_rankings: %d board(s) returned zero coverage: %s",
                    len(empty_boards), ", ".join(empty_boards))

            # Roster mode shows everyone (threshold 0) — the user picked these
            # players, so partial coverage is flagged, not dropped. Depth keeps
            # the validated 0.95 gate.
            threshold = 0.0 if source == "roster" else 0.95
            rows, dropped = _avg_rankings.compute_scores(
                ranks, entry_counts, names, [b for _, b in board_pairs],
                threshold=threshold)
            ranked = _avg_rankings.sort_rows(rows, "rank")
            as_of = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            stopped = stop_event.is_set()

            # Which in-scope boards a player has NO entry on — for verifying that a
            # sub-121 coverage count is genuine (player truly never charted there)
            # vs a fetch artifact. Short for kept rows (coverage gate caps the gap).
            def _missing_for(sid):
                present = ranks.get(sid, {})
                return [d for d, i in board_pairs if i not in present]

            csv_path = None
            if out_mode in ("csv", "both"):
                fname = (f"avg_placement_{scope}_roster.csv" if source == "roster"
                         else f"avg_placement_{scope}_top{k_int}.csv")
                csv_path = os.path.join(folder.strip(), fname)
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    w = _csv.DictWriter(f, fieldnames=[
                        "pos", "name", "avg_rank", "avg_pct",
                        "median_rank", "boards_covered", "boards_total", "missing_boards"])
                    w.writeheader()
                    for i, r in enumerate(ranked, 1):
                        w.writerow({
                            "pos": i, "name": _csv_safe(r["name"]),
                            "avg_rank": round(r["avg_rank"], 2),
                            "avg_pct": "" if r["avg_pct"] is None else round(r["avg_pct"], 6),
                            "median_rank": r["median_rank"],
                            "boards_covered": r["boards_n"], "boards_total": total_boards,
                            "missing_boards": "; ".join(_missing_for(r["steam_id"])),
                        })

            # steam_id exceeds JS's 2^53 safe-integer range — send as string.
            out_rows = [{
                "pos": i, "steam_id": str(r["steam_id"]), "name": r["name"],
                "avg_rank": round(r["avg_rank"], 2),
                "avg_pct": r["avg_pct"],
                "median_rank": r["median_rank"],
                "boards_n": r["boards_n"], "boards_total": total_boards,
                "missing": _missing_for(r["steam_id"]),
            } for i, r in enumerate(ranked, 1)]

            _emit_to(CH, {
                "type": "done", "rows": out_rows, "as_of": as_of,
                "stopped": stopped, "dropped": dropped, "boards_total": total_boards,
                "empty_boards": empty_boards, "csv_path": csv_path or "",
                "message": (f"Stopped. {len(out_rows)} players ranked."
                            if stopped else
                            f"Done. {len(out_rows)} players ranked."
                            if source == "roster" else
                            f"Done. {len(out_rows)} players ranked, {dropped} below coverage."),
            })
            self._lb_running = False

        threading.Thread(
            target=lambda: self._run_worker_safe(worker, "_nwAvgRankEvent"),
            daemon=True,
        ).start()
        return {"ok": True}

    def stop_avg_rankings(self) -> dict:
        # Mirror stop_leaderboard: signal the worker, let it clear _lb_running
        # when it actually exits (and emit partial results).
        if hasattr(self, "_lb_stop_event"):
            self._lb_stop_event.set()
        return {"ok": True}

    def run_level_search(self, level_name: str, count: str,
                         out_mode: str = "display", folder: str = "") -> dict:
        import time as _time, csv as _csv
        if not steam.steam_ready:
            return {"ok": False, "error": "Steam not connected. Connect in Settings first."}
        if getattr(self, "_lb_running", False):
            return {"ok": False, "error": "An operation is already running."}

        match = LEVEL_LOOKUP.get(str(level_name).strip().lower())
        if not match:
            return {"ok": False, "error": f"Level '{level_name}' not found."}
        display, internal = match

        try:
            count_int = max(1, int(str(count).strip()))
        except ValueError:
            return {"ok": False, "error": "Entry count must be a number."}
        err = _guard_output_folder(folder, out_mode)
        if err:
            return err

        with self._run_gate:
            if getattr(self, "_lb_running", False):
                return {"ok": False, "error": "An operation is already running."}
            self._lb_running = True
            # Capture the event in a local (inside the gate) so a later run that
            # reassigns self._lb_stop_event can't make this worker poll the wrong
            # event, and a Stop can't target the previous run's event.
            stop_event = self._lb_stop_event = threading.Event()

        def worker():
            _emit_to("_nwLevelEvent", {"type": "status", "message": f"Finding {display}..."})
            lb = steam.find_leaderboard(internal)
            if not lb:
                _emit_to("_nwLevelEvent", {"type": "error", "message": "Leaderboard not found."})
                self._lb_running = False
                return
            total_lb = steam.get_entry_count(lb)
            fetch = min(total_lb, count_int)
            _emit_to("_nwLevelEvent", {
                "type": "status",
                "message": f"Total: {total_lb:,}  |  Fetching top {fetch:,}...",
            })
            all_entries = []
            failed_pages = 0
            start = 1
            while start <= fetch and not stop_event.is_set():
                end = min(start + steam.BATCH_SIZE - 1, fetch)
                batch = _fetch_page(lb, start, end)
                if batch is None:
                    failed_pages += 1
                    break   # Steam failed this page (after retry) — surface below
                if not batch:
                    break   # genuine end of board
                for e in batch:
                    if out_mode in ("display", "both"):
                        _emit_to("_nwLevelEvent", {
                            "type": "row", "rank": e["rank"],
                            "name": e["name"], "time": e["time"], "score_ms": e["score_ms"],
                            "medal": _get_medal(display, e["score_ms"] / 1000.0),
                        })
                    if out_mode in ("csv", "both"):
                        all_entries.append(e)
                start = end + 1
                _time.sleep(0.05)

            csv_path = None
            if out_mode in ("csv", "both") and all_entries:
                safe = display.replace(" ", "_").replace("'", "")
                csv_path = os.path.join(folder.strip(), f"{safe}_top{len(all_entries)}.csv")
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = _csv.DictWriter(f, fieldnames=["rank", "name", "score_ms", "time"])
                    writer.writeheader()
                    for e in all_entries:
                        writer.writerow({"rank": e["rank"], "name": _csv_safe(e["name"]),
                                         "score_ms": e["score_ms"], "time": e["time"]})

            stopped = stop_event.is_set()
            total = len(all_entries) if out_mode in ("csv", "both") else (start - 1)
            msg = (f"Stopped. {total} entries." if stopped else f"Done. {total} entries.")
            if failed_pages:
                msg += f" {failed_pages} page(s) failed — data may be incomplete."
            _emit_to("_nwLevelEvent", {
                "type": "done", "total": total, "stopped": stopped,
                "csv_path": csv_path or "", "failed_pages": failed_pages,
                "message": msg,
            })
            self._lb_running = False

        threading.Thread(
            target=lambda: self._run_worker_safe(worker, "_nwLevelEvent"),
            daemon=True,
        ).start()
        return {"ok": True}

    # ── Rush Rankings ─────────────────────────────────────────────────────────

    def get_rush_boards(self) -> list:
        """Return the Rush Rankings board list with per-difficulty availability
        flags. All 5 rushes are resolved (White = HeavenRush_*); the None-guard
        remains so any future unknown board degrades instead of erroring."""
        return [
            {"key": b["key"], "label": b["label"],
             "heaven_available": b["heaven"] is not None,
             "hell_available": b["hell"] is not None}
            for b in RUSH_BOARDS
        ]

    def run_rush_search(self, rush_key: str, difficulty: str, count: str,
                        out_mode: str = "display", folder: str = "") -> dict:
        """Top-N fetch on a Level Rush board. Clone of run_level_search streaming
        via _nwRushEvent — no medal field (no rush threshold data), times as
        mm:ss.mmm via _fmt_ms_clock."""
        import time as _time, csv as _csv
        if not steam.steam_ready:
            return {"ok": False, "error": "Steam not connected. Connect in Settings first."}
        if getattr(self, "_lb_running", False):
            return {"ok": False, "error": "An operation is already running."}

        board = RUSH_BOARD_LOOKUP.get(str(rush_key).strip().lower())
        if not board:
            return {"ok": False, "error": f"Unknown rush '{rush_key}'."}
        diff = str(difficulty).strip().lower()
        if diff not in ("heaven", "hell"):
            return {"ok": False, "error": "Difficulty must be Heaven or Hell."}
        board_name = board[diff]
        if not board_name:
            return {"ok": False, "error": f"{board['label']} {diff.title()} Rush board name is not known yet."}

        try:
            count_int = max(1, int(str(count).strip()))
        except ValueError:
            return {"ok": False, "error": "Entry count must be a number."}
        err = _guard_output_folder(folder, out_mode)
        if err:
            return err

        label = f"{board['label']} {diff.title()}"
        with self._run_gate:
            if getattr(self, "_lb_running", False):
                return {"ok": False, "error": "An operation is already running."}
            self._lb_running = True
            # Capture the event in a local (inside the gate) so a later run that
            # reassigns self._lb_stop_event can't make this worker poll the wrong
            # event, and a Stop can't target the previous run's event.
            stop_event = self._lb_stop_event = threading.Event()

        def worker():
            _emit_to("_nwRushEvent", {"type": "status", "message": f"Finding {label} Rush..."})
            lb = steam.find_leaderboard(board_name)
            if not lb:
                _emit_to("_nwRushEvent", {"type": "error", "message": "Leaderboard not found."})
                self._lb_running = False
                return
            total_lb = steam.get_entry_count(lb)
            fetch = min(total_lb, count_int)
            _emit_to("_nwRushEvent", {
                "type": "status",
                "message": f"Total: {total_lb:,}  |  Fetching top {fetch:,}...",
            })
            all_entries = []
            failed_pages = 0
            start = 1
            while start <= fetch and not stop_event.is_set():
                end = min(start + steam.BATCH_SIZE - 1, fetch)
                batch = _fetch_page(lb, start, end)
                if batch is None:
                    failed_pages += 1
                    break   # Steam failed this page (after retry) — surface below
                if not batch:
                    break   # genuine end of board
                for e in batch:
                    clock = _fmt_ms_clock(e["score_ms"])
                    if out_mode in ("display", "both"):
                        _emit_to("_nwRushEvent", {
                            "type": "row", "rank": e["rank"],
                            "name": e["name"], "time": clock, "score_ms": e["score_ms"],
                        })
                    if out_mode in ("csv", "both"):
                        all_entries.append({**e, "time": clock})
                start = end + 1
                _time.sleep(0.05)

            csv_path = None
            if out_mode in ("csv", "both") and all_entries:
                safe = f"{board['label']}_{diff.title()}"
                csv_path = os.path.join(folder.strip(), f"{safe}_top{len(all_entries)}.csv")
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = _csv.DictWriter(f, fieldnames=["rank", "name", "score_ms", "time"])
                    writer.writeheader()
                    for e in all_entries:
                        writer.writerow({"rank": e["rank"], "name": _csv_safe(e["name"]),
                                         "score_ms": e["score_ms"], "time": e["time"]})

            stopped = stop_event.is_set()
            total = len(all_entries) if out_mode in ("csv", "both") else (start - 1)
            msg = (f"Stopped. {total} entries." if stopped else f"Done. {total} entries.")
            if failed_pages:
                msg += f" {failed_pages} page(s) failed — data may be incomplete."
            _emit_to("_nwRushEvent", {
                "type": "done", "total": total, "stopped": stopped,
                "csv_path": csv_path or "", "failed_pages": failed_pages,
                "message": msg,
            })
            self._lb_running = False

        threading.Thread(
            target=lambda: self._run_worker_safe(worker, "_nwRushEvent"),
            daemon=True,
        ).start()
        return {"ok": True}

    def find_rush_player(self, rush_key: str, difficulty: str, steam_id: str) -> dict:
        """Single-player lookup on a Level Rush board. Synchronous on the
        pywebview worker thread. Returns {ok, rank, name, total, time} or
        {ok: False, error}."""
        if not steam.steam_ready:
            return {"ok": False, "error": "Steam not connected."}
        board = RUSH_BOARD_LOOKUP.get(str(rush_key).strip().lower())
        if not board:
            return {"ok": False, "error": f"Unknown rush '{rush_key}'."}
        diff = str(difficulty).strip().lower()
        if diff not in ("heaven", "hell"):
            return {"ok": False, "error": "Difficulty must be Heaven or Hell."}
        board_name = board[diff]
        if not board_name:
            return {"ok": False, "error": f"{board['label']} {diff.title()} Rush board name is not known yet."}
        try:
            sid = int(str(steam_id).strip())
        except ValueError:
            return {"ok": False, "error": "Steam ID must be a 17-digit number."}

        lb = steam.find_leaderboard(board_name)
        if not lb:
            return {"ok": False, "error": "Leaderboard not found."}
        entry = steam.get_player_entry(lb, sid)
        if not entry:
            return {"ok": False, "error": f"No entry on {board['label']} {diff.title()} Rush."}
        pname = steam.get_persona_name(sid)
        total = steam.get_entry_count(lb)
        return {
            "ok": True,
            "rank": entry.global_rank,
            "name": pname,
            "total": total,
            "score_ms": entry.score,
            "time": _fmt_ms_clock(entry.score),
        }

    def find_rank(self, board_kind: str, board_key: str, time_str: str) -> dict:
        """Binary-search for where time_str would rank on a Level or Rush board.
        board_kind: "level" | "rush"
        board_key:  level display name, or "rush_key:difficulty" (e.g. "white:heaven")
        time_str:   "MM:SS.mmm" or bare seconds
        Returns {rank, total, medal|null, board_kind} or {error}.
        """
        if not steam.steam_ready:
            return {"error": "Steam not connected. Connect in Settings first."}

        secs = _parse_time_to_secs(str(time_str))
        if secs is None:
            return {"error": "Invalid time. Use MM:SS.mmm, e.g. 0:45.123."}
        target_ms = int(round(secs * 1000))

        kind = str(board_kind).strip().lower()
        display = None
        if kind == "level":
            match = LEVEL_LOOKUP.get(str(board_key).strip().lower())
            if not match:
                return {"error": f"Level '{board_key}' not found."}
            display, board_name = match
        elif kind == "rush":
            parts = str(board_key).split(":", 1)
            if len(parts) != 2:
                return {"error": "Rush board key must be 'rush_key:difficulty' (e.g. 'white:heaven')."}
            rk, diff = parts[0].strip().lower(), parts[1].strip().lower()
            board = RUSH_BOARD_LOOKUP.get(rk)
            if not board:
                return {"error": f"Unknown rush '{rk}'."}
            if diff not in ("heaven", "hell"):
                return {"error": "Difficulty must be 'heaven' or 'hell'."}
            board_name = board[diff]
            if not board_name:
                return {"error": f"{board['label']} {diff.title()} Rush board name is not known."}
        else:
            return {"error": f"Unknown board_kind '{board_kind}'."}

        # Single-flight guard so only one rank query runs at a time — also gives
        # stop_find_rank a single in-flight query to cancel.
        with self._run_gate:
            if getattr(self, "_rank_running", False):
                return {"error": "A rank query is already running."}
            self._rank_running = True
            self._rank_cancel = False

        try:
            import time
            handle = steam.find_leaderboard(board_name)
            if not handle:
                return {"error": "Leaderboard not found on Steam."}

            N = steam.get_entry_count(handle)
            if N == 0:
                return {"rank": 1, "rank_low": 1, "rank_high": 1, "tie_count": 0,
                        "total": 0, "medal": None, "board_kind": kind,
                        "target_ms": target_ms, "above": None, "below": None,
                        "next_medal": None}

            # Guard the bisect against a flaky / rate-limited Steam. Two distinct
            # failure shapes: fetch_batch returns None on a genuine Steam
            # failure/timeout and [] for a real empty/all-cheater window.
            # A failed window must NOT be absorbed as real data (the bisect would
            # narrow on false emptiness → confidently wrong rank). An overall
            # wall-clock budget plus a cancel flag (set by stop_find_rank) turn a
            # grind into a fast, surfaced bail.
            class _Cancelled(Exception):
                pass

            class _Stalled(Exception):
                pass

            deadline = time.time() + 25.0
            empty_streak = [0]

            def _fetch(a, b):
                """fetch_batch with cancel + stall guards (used only in the bisect loops).

                None (genuine failure) → retry-once via _fetch_page → still None →
                _Stalled immediately: two consecutive failures end the bisect
                rather than tolerating up to 8, because the retry IS the tolerance
                and Stalled beats a confidently wrong rank. [] is still a real
                empty window and feeds empty_streak as before.
                """
                if getattr(self, "_rank_cancel", False):
                    raise _Cancelled()
                if time.time() > deadline:
                    raise _Stalled()
                batch = _fetch_page(handle, a, b)   # retry-once; None = confirmed failure
                if batch is None:
                    raise _Stalled()
                if batch:
                    empty_streak[0] = 0
                else:
                    empty_streak[0] += 1
                    if empty_streak[0] >= 8:        # 8 real-empty windows → Steam isn't answering
                        raise _Stalled()
                return batch

            _PAD = 2
            try:
                # Bisect-RIGHT: first rank r where score_ms > target_ms.
                # Fetch 5 entries per step (mid±2) — single Steam call, more narrowing per
                # round-trip. Invariant: all ranks < lo have score_ms <= target_ms;
                #                        all ranks >= hi have score_ms > target_ms.
                lo, hi = 1, N + 1
                while lo < hi:
                    mid = (lo + hi) // 2
                    w_lo = max(1, mid - _PAD)
                    w_hi = min(N, w_lo + _PAD * 2)
                    batch = _fetch(w_lo, w_hi)
                    new_lo, new_hi = lo, hi
                    for e in batch:                      # batch is rank-ascending
                        if e["score_ms"] <= target_ms:
                            new_lo = max(new_lo, e["rank"] + 1)
                        else:
                            new_hi = min(new_hi, e["rank"])
                            break
                    else:
                        new_lo = max(new_lo, w_hi + 1)   # all batch entries at/below target
                    lo, hi = new_lo, new_hi

                # `lo` is the bisect-RIGHT insertion point. If the run directly above (rank lo-1)
                # ties the target exactly, the target lands inside a block of equal-time runs;
                # find that block's start (bisect-LEFT) so we can report the tied range your run
                # would occupy (lo_left … lo_right, your worst-case slot) instead of one number.
                lo_right = lo
                lo_left = lo_right

                # Probe rank lo_right-1 (slot directly above) — also our ▼below source at lo_right.
                below = None
                probe_lo, probe_hi = max(1, lo_right - 1), min(N, lo_right)
                # MUST route through _fetch: this iterates nb with no falsy check,
                # so a raw None (Steam failure) would TypeError out of find_rank's
                # try. _fetch turns a genuine failure into _Stalled instead.
                nb = _fetch(probe_lo, probe_hi)
                by_rank = {e["rank"]: e for e in nb}
                if lo_right <= N and lo_right in by_rank:
                    e = by_rank[lo_right]
                    below = {"rank": e["rank"], "score_ms": e["score_ms"]}

                tied = (lo_right - 1) >= 1 and (lo_right - 1) in by_rank \
                    and by_rank[lo_right - 1]["score_ms"] == target_ms
                if tied:
                    # bisect-LEFT: first rank with score_ms >= target_ms. Same windowed pattern;
                    # only runs on an exact tie, so no extra Steam calls in the common no-tie case.
                    llo, lhi = 1, lo_right
                    while llo < lhi:
                        mid = (llo + lhi) // 2
                        w_lo = max(1, mid - _PAD)
                        w_hi = min(N, w_lo + _PAD * 2)
                        batch = _fetch(w_lo, w_hi)
                        new_lo, new_hi = llo, lhi
                        for e in batch:                  # batch is rank-ascending
                            if e["score_ms"] < target_ms:
                                new_lo = max(new_lo, e["rank"] + 1)
                            else:
                                new_hi = min(new_hi, e["rank"])
                                break
                        else:
                            new_lo = max(new_lo, w_hi + 1)
                        llo, lhi = new_lo, new_hi
                    lo_left = llo

                # ▲above: the next genuinely-faster run at rank lo_left-1 (not a tied peer). Reuse
                # the probe fetch when not tied (it already returned lo_left-1); else fetch it.
                above = None
                if lo_left == lo_right:
                    if (lo_left - 1) >= 1 and (lo_left - 1) in by_rank:
                        e = by_rank[lo_left - 1]
                        above = {"rank": e["rank"], "score_ms": e["score_ms"]}
                elif lo_left - 1 >= 1:
                    ab = _fetch(lo_left - 1, lo_left - 1)   # _Stalled on genuine failure, not a dropped ▲above
                    if ab:
                        e = ab[0]
                        above = {"rank": e["rank"], "score_ms": e["score_ms"]}
            except _Cancelled:
                return {"cancelled": True}
            except _Stalled:
                return {"error": "Steam stopped responding — try again in a moment."}

            medal = None
            next_medal = None
            if kind == "level" and display:
                medal = _get_medal(display, secs) or None
                next_medal = _next_medal(display, secs)

            # tie_count = how many OTHER runs share this exact time. When you tie, your run
            # extends the block, so the range you'd occupy is lo_left … lo_right (your worst
            # slot). No tie ⇒ rank_high == rank_low and the UI shows a single number.
            tie_count = lo_right - lo_left
            rank_high = lo_right if tie_count else lo_left
            return {"rank": lo_left, "rank_low": lo_left, "rank_high": rank_high,
                    "tie_count": tie_count, "total": N, "medal": medal, "board_kind": kind,
                    "target_ms": target_ms, "above": above, "below": below,
                    "next_medal": next_medal}
        finally:
            self._rank_running = False

    def stop_find_rank(self) -> dict:
        """Signal an in-flight find_rank to abort. The query's finally clause clears
        _rank_running once it unwinds, so a fresh query can start right after."""
        self._rank_cancel = True
        return {"ok": True}

    def _resolve_levels_for_mode(self, mode, target):
        """Resolve a (mode, target) selection into the levels to search.

        Shared by Player Lookup / Compare Players / Multi Compare. Returns
        ``(levels_to_search, context, error)``:
          - ``levels_to_search`` — list of ``(display, internal)`` tuples
          - ``context`` — short human label (level name / chapter / "Whole Game"
            / "Custom_N_levels"); callers that don't need it ignore it
          - ``error`` — an ``{"ok": False, "error": ...}`` dict when the selection
            is invalid (caller returns it as-is), else ``None``

        ``target`` may be a JSON-encoded list of display names (custom mode) or an
        already-decoded list.
        """
        levels_to_search = []
        context = ""
        if mode == "level":
            match = LEVEL_LOOKUP.get(str(target).strip().lower())
            if not match:
                return [], "", {"ok": False, "error": f"Level '{target}' not found."}
            levels_to_search = [match]
            context = match[0]
        elif mode == "chapter":
            chap = str(target).strip()
            if chap not in CHAPTERS:
                return [], "", {"ok": False, "error": f"Chapter '{chap}' not found."}
            for dn in CHAPTERS[chap]:
                m = LEVEL_LOOKUP.get(dn.lower())
                if m:
                    levels_to_search.append(m)
            context = chap
        elif mode == "game":
            levels_to_search = list(WHOLE_GAME_LEVELS)
            context = "Whole Game"
        elif mode == "custom":
            # target arrives as a JSON-encoded list of display names (the frontend
            # JSON.stringifies it so it survives api.js's String() wrapper), or an
            # already-decoded list.
            try:
                requested = target if isinstance(target, list) else json.loads(target or "[]")
            except (ValueError, TypeError):
                requested = []
            seen = set()
            for name in requested:
                m = LEVEL_LOOKUP.get(str(name).strip().lower())
                if m and m[0] not in seen:  # dedupe + drop unknown (stale presets)
                    levels_to_search.append(m)
                    seen.add(m[0])
            if not levels_to_search:
                return [], "", {"ok": False, "error": "Pick at least one level for custom search."}
            context = f"Custom_{len(levels_to_search)}_levels"
        else:
            return [], "", {"ok": False, "error": f"Unknown mode '{mode}'."}
        return levels_to_search, context, None

    def run_player_lookup(self, steam_id: str, mode: str, target: str,
                          out_mode: str = "display", folder: str = "") -> dict:
        import csv as _csv
        if not steam.steam_ready:
            return {"ok": False, "error": "Steam not connected. Connect in Settings first."}
        if getattr(self, "_lb_running", False):
            return {"ok": False, "error": "An operation is already running."}

        sid_str = str(steam_id).strip()
        if not sid_str.isdigit() or len(sid_str) != 17:
            return {"ok": False, "error": "Steam ID must be a 17-digit number."}
        sid = int(sid_str)

        levels_to_search, context, err = self._resolve_levels_for_mode(mode, target)
        if err:
            return err

        err = _guard_output_folder(folder, out_mode)
        if err:
            return err

        with self._run_gate:
            if getattr(self, "_lb_running", False):
                return {"ok": False, "error": "An operation is already running."}
            self._lb_running = True
            # Capture the event in a local (inside the gate) so a later run that
            # reassigns self._lb_stop_event can't make this worker poll the wrong
            # event, and a Stop can't target the previous run's event.
            stop_event = self._lb_stop_event = threading.Event()

        def worker():
            pname = steam.get_persona_name(sid)
            _emit_to("_nwPlayerEvent", {
                "type": "status",
                "message": f"Looking up {pname} across {len(levels_to_search)} levels...",
                "player_name": pname,
            })
            found = 0
            all_rows = []
            for display, internal in levels_to_search:
                if stop_event.is_set():
                    break
                lb = steam.find_leaderboard(internal)
                if not lb:
                    continue
                total_lb = steam.get_entry_count(lb)
                entry = steam.get_player_entry(lb, sid)
                if entry:
                    time_str = f"{entry.score / 1000:.3f}"
                    medal = _get_medal(display, entry.score / 1000.0)
                    if out_mode in ("display", "both"):
                        _emit_to("_nwPlayerEvent", {
                            "type": "row", "level": display,
                            "rank": entry.global_rank, "time": time_str,
                            "score_ms": entry.score, "total": total_lb,
                            "medal": medal,
                        })
                    if out_mode in ("csv", "both"):
                        all_rows.append({"level": display, "rank": entry.global_rank,
                                         "time": time_str, "score_ms": entry.score,
                                         "total": total_lb})
                    found += 1

            csv_path = None
            if out_mode in ("csv", "both") and all_rows:
                safe_name = "".join(c if c.isalnum() or c in " _-" else "" for c in pname).strip().replace(" ", "_")
                safe_ctx = context.replace(" ", "_").replace("/", "_").replace("-", "")
                csv_path = os.path.join(folder.strip(), f"{safe_name}_{safe_ctx}.csv")
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = _csv.DictWriter(
                        f, fieldnames=["level", "rank", "time", "score_ms", "total"])
                    writer.writeheader()
                    writer.writerows(all_rows)

            stopped = stop_event.is_set()
            _emit_to("_nwPlayerEvent", {
                "type": "done", "found": found,
                "total_levels": len(levels_to_search), "stopped": stopped,
                "csv_path": csv_path or "",
                "message": (f"Stopped. {found} entries so far." if stopped
                            else f"Done. Found {found}/{len(levels_to_search)} entries."),
            })
            self._lb_running = False

        threading.Thread(
            target=lambda: self._run_worker_safe(worker, "_nwPlayerEvent"),
            daemon=True,
        ).start()
        return {"ok": True}

    def run_compare_players(self, steam_id_1: str, steam_id_2: str,
                            mode: str, target: str,
                            out_mode: str = "display", folder: str = "") -> dict:
        import csv as _csv
        sid1_str = str(steam_id_1).strip()
        if not sid1_str.isdigit() or len(sid1_str) != 17:
            return {"ok": False, "error": "Player 1 Steam ID must be a 17-digit number."}
        sid2_str = str(steam_id_2).strip()
        if not sid2_str.isdigit() or len(sid2_str) != 17:
            return {"ok": False, "error": "Player 2 Steam ID must be a 17-digit number."}
        err = _guard_output_folder(folder, out_mode)
        if err:
            return err

        if not steam.steam_ready:
            return {"ok": False, "error": "Steam not connected. Connect in Settings first."}
        if getattr(self, "_lb_running", False):
            return {"ok": False, "error": "An operation is already running."}
        sid1 = int(sid1_str)
        sid2 = int(sid2_str)

        levels_to_search, context, err = self._resolve_levels_for_mode(mode, target)
        if err:
            return err

        with self._run_gate:
            if getattr(self, "_lb_running", False):
                return {"ok": False, "error": "An operation is already running."}
            self._lb_running = True
            # Capture the event in a local (inside the gate) so a later run that
            # reassigns self._lb_stop_event can't make this worker poll the wrong
            # event, and a Stop can't target the previous run's event.
            stop_event = self._lb_stop_event = threading.Event()

        def worker():
            pname1 = steam.get_persona_name(sid1)
            pname2 = steam.get_persona_name(sid2)
            _emit_to("_nwCompareEvent", {
                "type": "status",
                "message": f"Comparing {pname1} vs {pname2} across {len(levels_to_search)} levels...",
                "player_name_1": pname1,
                "player_name_2": pname2,
            })

            def safe(s):
                return "".join(c if c.isalnum() or c in " _-" else "" for c in s).strip().replace(" ", "_")

            found_p1 = 0
            found_p2 = 0
            all_rows = []
            for display, internal in levels_to_search:
                if stop_event.is_set():
                    break
                lb = steam.find_leaderboard(internal)
                if not lb:
                    continue
                total_lb = steam.get_entry_count(lb)
                entries = steam.get_player_entries(lb, [sid1, sid2])
                entry1 = entries.get(sid1)
                entry2 = entries.get(sid2)
                p1_data = None
                if entry1:
                    p1_data = {
                        "rank": entry1.global_rank,
                        "time": f"{entry1.score / 1000:.3f}",
                        "score_ms": entry1.score,
                        "medal": _get_medal(display, entry1.score / 1000.0),
                    }
                    found_p1 += 1
                p2_data = None
                if entry2:
                    p2_data = {
                        "rank": entry2.global_rank,
                        "time": f"{entry2.score / 1000:.3f}",
                        "score_ms": entry2.score,
                        "medal": _get_medal(display, entry2.score / 1000.0),
                    }
                    found_p2 += 1
                delta_ms = None
                faster = None
                if p1_data and p2_data:
                    delta_ms = p2_data["score_ms"] - p1_data["score_ms"]
                    if delta_ms > 0:
                        faster = "p1"
                    elif delta_ms < 0:
                        faster = "p2"
                    else:
                        faster = "tie"
                if out_mode in ("display", "both"):
                    _emit_to("_nwCompareEvent", {
                        "type": "row",
                        "level": display,
                        "p1": p1_data,
                        "p2": p2_data,
                        "delta_ms": delta_ms,
                        "faster": faster,
                        "total": total_lb,
                    })
                if out_mode in ("csv", "both"):
                    all_rows.append({
                        "level": display,
                        "p1_rank": p1_data["rank"] if p1_data else "",
                        "p1_time": p1_data["time"] if p1_data else "",
                        "p1_medal": p1_data["medal"] if p1_data else "",
                        "delta_ms": delta_ms if delta_ms is not None else "",
                        "p2_rank": p2_data["rank"] if p2_data else "",
                        "p2_time": p2_data["time"] if p2_data else "",
                        "p2_medal": p2_data["medal"] if p2_data else "",
                    })

            csv_path = None
            if out_mode in ("csv", "both") and all_rows:
                safe_ctx = context.replace(" ", "_").replace("/", "_").replace("-", "")
                fname = f"{safe(pname1)}_vs_{safe(pname2)}_{safe_ctx}.csv"
                csv_path = os.path.join(folder.strip(), fname)
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = _csv.DictWriter(f, fieldnames=[
                        "level", "p1_rank", "p1_time", "p1_medal",
                        "delta_ms", "p2_rank", "p2_time", "p2_medal"])
                    writer.writeheader()
                    writer.writerows(all_rows)

            stopped = stop_event.is_set()
            base_msg = (f"Stopped. {found_p1} P1 / {found_p2} P2 entries so far."
                        if stopped
                        else f"Done. {found_p1} P1 / {found_p2} P2 entries found.")
            _emit_to("_nwCompareEvent", {
                "type": "done",
                "message": f"{base_msg} → {csv_path}" if csv_path else base_msg,
                "found_p1": found_p1,
                "found_p2": found_p2,
                "total_levels": len(levels_to_search),
                "csv_path": csv_path or "",
            })
            self._lb_running = False

        threading.Thread(
            target=lambda: self._run_worker_safe(worker, "_nwCompareEvent"),
            daemon=True,
        ).start()
        return {"ok": True}

    def run_multi_compare(self, steam_ids: list, mode: str, target: str = "") -> dict:
        """
        Up to 16 players × Level/Chapter/Whole-Game compare. Batches Steam
        calls per level (one DownloadLeaderboardEntriesForUsers round-trip
        for whoever's not in cache). Streams row/progress/done events via
        window._nwMultiCompareEvent.
        """
        try:
            req = MultiCompareRequest(steam_ids=steam_ids, mode=mode, target=target)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        if not steam.steam_ready:
            return {"ok": False, "error": "Steam not connected. Connect in Settings first."}
        if getattr(self, "_lb_running", False):
            return {"ok": False, "error": "An operation is already running."}

        levels_to_search, _context, err = self._resolve_levels_for_mode(req.mode, req.target)
        if err:
            return err

        sid_ints = [int(s) for s in req.steam_ids]
        sid_pairs = list(zip(req.steam_ids, sid_ints))  # (display_str, int) for emit + lookup

        with self._run_gate:
            if getattr(self, "_lb_running", False):
                return {"ok": False, "error": "An operation is already running."}
            self._lb_running = True
            # Capture the event in a local (inside the gate) so a later run that
            # reassigns self._lb_stop_event can't make this worker poll the wrong
            # event, and a Stop can't target the previous run's event.
            stop_event = self._lb_stop_event = threading.Event()

        def worker():
            total = len(sid_ints) * len(levels_to_search)
            done = 0
            for display, internal in levels_to_search:
                if stop_event.is_set():
                    _emit_to("_nwMultiCompareEvent", {"type": "done", "message": "stopped"})
                    self._lb_running = False
                    return

                # Cache lookup per sid; collect misses for a single batched fetch.
                cached: dict = {}
                missing: list = []
                for sid in sid_ints:
                    hit, val = multi_compare_cache.get(sid, internal)
                    if hit:
                        cached[sid] = val
                    else:
                        missing.append(sid)

                if missing:
                    lb = steam.find_leaderboard(internal)
                    if lb:
                        fetched = steam.get_player_entries(lb, missing)
                        for sid, entry in fetched.items():
                            cache_val = None
                            if entry is not None:
                                cache_val = {
                                    "time_us": entry.score * 1000,  # ms → us
                                    "rank": entry.global_rank,
                                }
                            multi_compare_cache.put(sid, internal, cache_val)
                            cached[sid] = cache_val
                    else:
                        # Leaderboard not found / call failed. Do NOT cache as
                        # missing — a transient Steam failure would otherwise
                        # poison these cells as authoritative "no time" for the
                        # whole session. Render missing this pass; retry next run.
                        for sid in missing:
                            cached[sid] = None

                for sid_str, sid_int in sid_pairs:
                    val = cached.get(sid_int)
                    if val is None:
                        _emit_to("_nwMultiCompareEvent", {
                            "type": "row",
                            "steam_id": sid_str,
                            "level_code": internal,
                            "level_display": display,
                            "time_us": None,
                            "rank": None,
                            "missing": True,
                        })
                    else:
                        _emit_to("_nwMultiCompareEvent", {
                            "type": "row",
                            "steam_id": sid_str,
                            "level_code": internal,
                            "level_display": display,
                            "time_us": val["time_us"],
                            "rank": val["rank"],
                            "missing": False,
                            "medal": _get_medal(display, val["time_us"] / 1_000_000.0),
                        })
                    done += 1
                    if done % 10 == 0 or done == total:
                        _emit_to("_nwMultiCompareEvent", {
                            "type": "progress", "done": done, "total": total,
                        })

            _emit_to("_nwMultiCompareEvent", {"type": "done", "message": "ok"})
            self._lb_running = False

        threading.Thread(
            target=lambda: self._run_worker_safe(worker, "_nwMultiCompareEvent"),
            daemon=True,
        ).start()
        return {"ok": True}

    def stop_multi_compare(self) -> dict:
        if hasattr(self, "_lb_stop_event"):
            self._lb_stop_event.set()
        return {"ok": True}

    def clear_multi_compare_cache(self, steam_ids: list) -> dict:
        """Drop cached Multi-Compare times for the given roster's Steam IDs so
        the next run re-fetches fresh data. Roster/UI state is untouched.
        Returns {ok, removed} where removed is the key count evicted."""
        sids = []
        for s in steam_ids or []:
            try:
                sids.append(int(str(s).strip()))
            except (TypeError, ValueError):
                continue
        removed = multi_compare_cache.clear_for_sids(sids)
        return {"ok": True, "removed": removed}

    def stop_leaderboard(self) -> dict:
        # Signal the worker to stop, but leave _lb_running set — the worker
        # clears it when it actually exits (_run_worker_safe's finally / its own
        # tail). Clearing it here would let a new run start while the old worker
        # is still mid-batch, interleaving rows into the same event channel.
        if hasattr(self, "_lb_stop_event"):
            self._lb_stop_event.set()
        return {"ok": True}

    # ── Standardize Splits ────────────────────────────────────────────────────

    def standardize_splits(self, rush_name: str, seed: str,
                           gold: str, segments: str) -> dict:
        """
        Convert seed-order splits back to standard (index) level order.
        Inverse of reorder_splits.
        Returns {ok, gold, segments} or {ok: false, error}.
        """
        try:
            s = int(str(seed).strip())
            if not (1 <= s <= 2_147_483_647):
                raise ValueError
        except ValueError:
            return {"ok": False, "error": "Seed must be an integer between 1 and 2,147,483,647."}

        key, count, names = _resolve_rush(rush_name)
        order = full_shuffle(count, s)

        # Build inverse: standard_index -> seed_position
        seed_position = [0] * count
        for pos, idx in enumerate(order):
            seed_position[idx] = pos

        gold_lines = [l for l in str(gold).splitlines() if l.strip()]
        seg_lines  = [l for l in str(segments).splitlines() if l.strip()]

        if gold_lines and len(gold_lines) != count:
            return {"ok": False, "error": f"Expected {count} gold splits, got {len(gold_lines)}."}
        if seg_lines and len(seg_lines) != count:
            return {"ok": False, "error": f"Expected {count} segment splits, got {len(seg_lines)}."}

        gold_out = [gold_lines[seed_position[i]] for i in range(count)] if gold_lines else []
        seg_out  = [seg_lines[seed_position[i]]  for i in range(count)] if seg_lines  else []
        std_names = list(names)  # standard index order for medal lookup

        return {
            "ok":             True,
            "gold":           gold_out,
            "gold_medals":    _compute_medals(std_names, gold_out) if gold_out else [],
            "segments":       seg_out,
            "segment_medals": _compute_medals(std_names, seg_out) if seg_out else [],
        }

    # ── Medal targets ─────────────────────────────────────────────────────────

    def get_medal_times(self, level: str) -> dict:
        """Return community medal target times (in seconds) for a stage display name.

        Returns {} if the stage isn't recognized or community-medal data hasn't
        finished loading yet. Caller should treat empty as "no targets available."
        """
        nl = (level or "").strip().lower()
        if nl not in LEVEL_LOOKUP:
            return {}
        _, code = LEVEL_LOOKUP[nl]
        comm = _COMMUNITY_MEDAL_DATA.get(code)
        if not comm or len(comm) < 3:
            return {}
        out = {
            "emerald":  comm[0] / 1_000_000,
            "amethyst": comm[1] / 1_000_000,
            "sapphire": comm[2] / 1_000_000,
        }
        # Higher community tiers — only present when their data has loaded.
        # Keys match the frontend's medal.toLowerCase() ("topaz", "blood diamond").
        topaz = _TOPAZ_MEDAL_DATA.get(code)
        if topaz:
            out["topaz"] = topaz[0] / 1_000_000
        bd = _BD_MEDAL_DATA.get(code)
        if bd:
            out["blood diamond"] = bd[0] / 1_000_000
        return out

    # ── Resources (Ghosts + Route Videos) ─────────────────────────────────────

    def get_resources_status(self) -> dict:
        return _resources.get_status()

    def get_ghosts(self, level: str, medal: str) -> list:
        return _resources.get_ghosts_for(str(level or ""), str(medal or ""))

    def get_videos(self, level: str, medal: str) -> list:
        return _resources.get_videos_for(str(level or ""), str(medal or ""))

    def get_world_record(self, level: str, platform: str) -> dict | None:
        return _resources.get_wr_for(str(level or ""), str(platform or ""))

    def get_guides(self) -> dict:
        return GuidesResponse(
            guides=_resources.get_guides(),
            loaded=_resources.get_status()["guides_loaded"],
        ).model_dump()

    def get_helpful_links(self) -> dict:
        return HelpfulLinksResponse(
            links=_resources.get_helpful_links(),
            loaded=_resources.get_status()["helpful_links_loaded"],
        ).model_dump()

    def open_external_url(self, url: str) -> dict:
        """Open an allow-listed external URL in the user's default browser.

        Restricted to Drive + YouTube to keep the JS↔Python bridge from
        becoming an arbitrary-URL launcher.
        """
        import webbrowser
        u = str(url or "").strip()
        allowed_prefixes = (
            "https://drive.google.com/",
            "https://docs.google.com/",
            "https://www.youtube.com/",
            "https://youtube.com/",
            "https://youtu.be/",
            "https://discord.gg/",
            "https://discord.com/",
            "https://www.discord.com/",
            "https://www.speedrun.com/",
            "https://speedrun.com/",
            "https://github.com/",
            "https://www.github.com/",
            "https://raw.githubusercontent.com/",
            "https://derelictjade.github.io/",
            "https://nwbingo.pages.dev/",
        )
        if not any(u.startswith(p) for p in allowed_prefixes):
            try:
                from logger import get_logger
                get_logger("bridge").warning("open_external_url rejected: %r", u)
            except Exception:
                pass
            return {"ok": False, "error": "URL not in allow-list."}
        try:
            webbrowser.open(u)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
