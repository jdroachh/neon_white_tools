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
from rush_data import LEVELS, LEVEL_LOOKUP, RUSH_LEVELS, RUSH_ALIASES, STANDARD_MEDAL_DATA
from seed_search import _seed_search_worker, _expected_match_count

APP_VERSION = "2.0.0-dev"

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

MAX_SEED = 2_147_483_647


def _resolve_rush(rush_name: str) -> tuple[str, int, list[str]]:
    """Return (key, num_levels, names_list) for a rush display name."""
    key   = _RUSH_KEY.get(rush_name, "96")
    count = _RUSH_COUNT.get(rush_name, 96)
    names = RUSH_LEVELS[key]
    return key, count, names


# ── Shared helpers (used by timer and finder) ─────────────────────────────

# Build a display-name → code lookup from LEVELS once.
_DISPLAY_TO_CODE = {disp.lower(): code.upper() for disp, code in LEVELS}

def _resolve_level_code(level_name: str, rush_key: str) -> str | None:
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


def _get_medal(level_name: str, secs: float, rush_key: str) -> str:
    code = _resolve_level_code(level_name, rush_key)
    if not code:
        return ""
    us = int(secs * 1_000_000)
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


def _compute_medals(level_names: list[str], time_strs: list[str], rush_key: str) -> list[str]:
    medals = []
    for name, s in zip(level_names, time_strs):
        t = _parse_time_to_secs(s)
        medals.append(_get_medal(name, t, rush_key) if t is not None else "")
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


class JsApi:
    """pywebview js_api bridge. Instantiated once in main.py."""

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
            "gold_medals":     _compute_medals(level_order, gold_out, key) if gold_out else [],
            "segments":        seg_out,
            "segment_medals":  _compute_medals(level_order, seg_out, key) if seg_out else [],
        }

    # ── Rush metadata ── (extended) ──────────────────────────────────────────

    def get_standard_order(self, rush_name: str) -> dict:
        """Return the standard (non-shuffled) level name list for a rush."""
        _, _, names = _resolve_rush(rush_name)
        return {"ok": True, "lines": list(names)}

    # ── Seed Finder ───────────────────────────────────────────────────────────

    def start_finder(self, rush_name: str, levels_str: str, depth: str,
                     mode: str, max_seeds: str) -> dict:
        """
        Begin a seed search. Returns {ok} immediately; progress events are
        pushed to window._nwFinderEvent({type, ...}) in the JS layer.
        Event types: "progress" | "result" | "done" | "error"
        """
        if getattr(self, "_finder_running", False):
            return {"ok": False, "error": "Search already running."}

        key, count, names = _resolve_rush(rush_name)

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

        expected = _expected_match_count(count, len(target_indices), depth_int, MAX_SEED)

        self._finder_stop_event = threading.Event()
        self._finder_user_stopped = False
        self._finder_running = True

        num_cores = max(1, (__import__("os").cpu_count() or 1) - 1)
        chunk_size = MAX_SEED // num_cores

        def manager():
            result_queue = queue.Queue()
            workers = []
            for core in range(num_cores):
                start = core * chunk_size + 1
                end = (core + 1) * chunk_size + 1 if core < num_cores - 1 else MAX_SEED
                t = threading.Thread(
                    target=_seed_search_worker,
                    args=((start, end, count, set(target_indices), depth_int,
                           result_queue, self._finder_stop_event),),
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
                    if self._finder_stop_event.is_set():
                        break
                    continue

                if item is None:
                    done_workers += 1
                    continue

                if isinstance(item, tuple) and item and item[0] == "progress":
                    seeds_checked += item[1]
                    pct = min(99, int(seeds_checked / MAX_SEED * 100))
                    _emit({"type": "progress", "seeds_checked": seeds_checked,
                           "total": MAX_SEED, "found_count": len(found), "pct": pct})
                    continue

                seed = item
                found.append(seed)
                order = full_shuffle(count, seed)
                target_set = set(target_indices)
                positions = {idx: pos + 1 for pos, idx in enumerate(order) if idx in target_set}
                level_order = [
                    {"name": names[idx], "is_target": idx in target_set,
                     "position": positions.get(idx)}
                    for pos, idx in enumerate(order)
                ]
                pos_strs = ", ".join(f"{names[idx]} @{positions[idx]}" for idx in target_indices)
                _emit({"type": "result", "seed": seed, "summary": pos_strs,
                       "level_order": level_order})

                if len(found) >= max_seeds_int:
                    self._finder_stop_event.set()
                    break

            user_stopped = getattr(self, "_finder_user_stopped", False)
            self._finder_stop_event.set()
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
        self._finder_user_stopped = True
        self._finder_running = False  # reset immediately so start_finder can be called again
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

    def calculate_timer(self, rush_name: str, seed: str, splits_text: str) -> dict:
        """
        Parse cumulative split times and compute segment times + medal grades.
        splits_text: one split per line, format "Name time" or "Name: time" or bare "time".
        seed is optional (pass "" to skip medal lookup fallback to standard order).
        Returns {ok, rows: [{name, cumulative, segment, segment_fmt, medal}]} or {ok: false, error}.
        """
        raw_lines = [l for l in str(splits_text).strip().splitlines() if l.strip()]
        if not raw_lines:
            return {"ok": False, "error": "Please enter at least one split time."}

        key, count, names = _resolve_rush(rush_name)

        cumulative = []
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
            if cumulative and t_val <= cumulative[-1]:
                errors.append(
                    f"Row {i + 1} ({name_part}): time {_format_secs(t_val)} must be "
                    f"greater than previous ({_format_secs(cumulative[-1])})"
                )
                continue
            cumulative.append(t_val)
            level_names.append(name_part)

        if errors:
            return {"ok": False, "error": "\n".join(errors)}

        segments = [cumulative[0]] + [cumulative[i] - cumulative[i - 1]
                                       for i in range(1, len(cumulative))]
        rows = []
        for i, (seg, cum, name) in enumerate(zip(segments, cumulative, level_names)):
            medal = _get_medal(name, seg, key)
            rows.append({
                "name":         name,
                "cumulative":   _format_secs(cum),
                "segment":      seg,
                "segment_fmt":  _format_secs(seg),
                "medal":        medal,
            })

        return {"ok": True, "rows": rows}

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
            "gold_medals":    _compute_medals(std_names, gold_out, key) if gold_out else [],
            "segments":       seg_out,
            "segment_medals": _compute_medals(std_names, seg_out, key) if seg_out else [],
        }
