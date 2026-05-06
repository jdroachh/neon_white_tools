"""
bridge — JsApi class exposed to the webview via pywebview js_api.

Every public method becomes callable from JS as window.pywebview.api.<method>.
Long-running operations push progress via progress.emit() rather than blocking.
"""
import sys
import os

# Workers import this module — avoid re-importing heavy tk-side things.
# sys.path already has SteamScraper/ when launched via main.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shuffle_lib import _load_c_shuffle, full_shuffle
from rush_data import RUSH_LEVELS

APP_VERSION = "2.0.0-dev"

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


def _resolve_rush(rush_name: str) -> tuple[str, int, list[str]]:
    """Return (key, num_levels, names_list) for a rush display name."""
    key   = _RUSH_KEY.get(rush_name, "96")
    count = _RUSH_COUNT.get(rush_name, 96)
    names = RUSH_LEVELS[key]
    return key, count, names


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

        _, count, names = _resolve_rush(rush_name)
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
            "ok":          True,
            "level_order": level_order,
            "gold":        gold_out,
            "segments":    seg_out,
        }

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

        _, count, names = _resolve_rush(rush_name)
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

        return {
            "ok":       True,
            "gold":     gold_out,
            "segments": seg_out,
        }
