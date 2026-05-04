import ctypes
import os
import time
import csv
import json
import threading
import multiprocessing
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from urllib.request import urlopen

# Seed-search modules — kept slim so multiprocessing workers re-import only
# these files (not all 2991 lines of this module + tkinter) on spawn.
from shuffle_lib import _load_c_shuffle, full_shuffle

from logger import get_logger
logger = get_logger(__name__)

# Static level data + Rush mappings — pure constants, no functions.
from rush_data import (
    LEVELS, LEVEL_LOOKUP, WHOLE_GAME_LEVELS, CHAPTERS,
    RUSH_LEVELS, RUSH_ALIASES, STANDARD_MEDAL_DATA,
)

# Steam Steamworks API — globals are module-level state in steam_api.
# Reference live values via attribute access (e.g. steam_api.steam_ready),
# NOT `from steam_api import steam_ready` — the latter captures the value
# at import time and won't see mutations from `steam_api.init_steam`.
import steam_api

# Font helpers — extracted so tab modules can use them without importing this file.
from fonts import GOHU_FONT_NAME, load_gohu_font, gohu, gohu_mono

# Per-tab UI mixins — one file per tab area.
from tab_rush_parser import RushParserTabMixin
from tab_rush_splits import RushSplitsTabMixin
from tab_rush_std import RushStdTabMixin
from tab_rush_timer import RushTimerTabMixin
from tab_rush_finder import RushFinderTabMixin
from tab_level import LevelTabMixin
from tab_global import GlobalTabMixin
from tab_player import PlayerTabMixin
from tab_settings import SettingsTabMixin
from tab_sidebar import SidebarTabMixin


# ── Constants ──────────────────────────────────────────────────────────────
CONFIG_FILE  = "neonwhite_config.json"
APP_TITLE    = "Neon White Leaderboard Tool"
VERSION      = "1.10.5"

# Duplicated from sheets.TOKEN_FILE on purpose — UI uses it to render auth
# status without importing sheets (which would trigger the slow Google libs
# at app launch, defeating sheets.py's lazy-import design).
TOKEN_FILE = "token.json"

DEFAULT_CONFIG = {
    "dll_path":           "",
    "output_folder":      os.path.expanduser("~\\Desktop"),
    "entry_count":        1000,
    "theme":              "light",
    "sheet_id":           "",
    "times_tab":          "",
    "times_start_cell":   "A1",
    "ranks_tab":          "",
    "ranks_start_cell":   "A1",
}

# Community medal data — fetched live on startup, falls back to embedded
COMMUNITY_MEDAL_DATA = {}
COMMUNITY_MEDALS_URL = "https://raw.githubusercontent.com/Faustas156/NeonLite/main/Resources/communitymedals.json"

# ── Config ─────────────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            logger.exception("Failed to load %s; falling back to DEFAULT_CONFIG", CONFIG_FILE)
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def format_time_mmss(score_ms):
    """Convert milliseconds to MM:SS.mmm string."""
    total_seconds = score_ms / 1000
    minutes       = int(total_seconds // 60)
    seconds       = total_seconds % 60
    return f"{minutes:02d}:{seconds:06.3f}"


# ── Themes ─────────────────────────────────────────────────────────────────
THEMES = {
    "light": {
        # RL-C palette
        "bg":              "#ffffff",
        "bg2":             "#f0fff0",
        "bg3":             "#0a1a0a",
        "fg":              "#0a1a0a",
        "fg2":             "#3B6D11",
        "accent":          "#00aa55",
        "border":          "#c0e8c0",
        "success":         "#3B6D11",
        "error":           "#cc2222",
        "row_alt":         "#f8fff8",
        "select":          "#d0f0d8",
        "log_bg":          "#f0fff0",
        "log_fg":          "#3B6D11",
        "btn_bg":          "#00aa55",
        "btn_active":      "#008844",
        "sidebar_sel":     "#0a1a0a",
        "input_bg":        "#f0fff0",
        "input_fg":        "#0a1a0a",
        "sidebar_bg":      "#f8fff8",
        "nav_active_fg":   "#ffffff",
        "nav_inactive_fg": "#3B6D11",
    },
    "dark": {
        # R2 palette
        "bg":              "#111118",
        "bg2":             "#0a0a0f",
        "bg3":             "#1a1a2a",
        "fg":              "#ffffff",
        "fg2":             "#7070a0",
        "accent":          "#00ff9f",
        "border":          "#1e1e2e",
        "success":         "#00ff9f",
        "error":           "#ef5350",
        "row_alt":         "#0d0d14",
        "select":          "#1a1a2a",
        "log_bg":          "#0a0a0f",
        "log_fg":          "#7070a0",
        "btn_bg":          "#00ff9f",
        "btn_active":      "#00dd88",
        "sidebar_sel":     "#1a1a2a",
        "input_bg":        "#0a0a0f",
        "input_fg":        "#c8c8d8",
        "sidebar_bg":      "#0a0a0f",
        "nav_active_fg":   "#ffffff",
        "nav_inactive_fg": "#7070a0",
    },
}

def fetch_community_medals():
    """Fetch community medal data from NeonLite GitHub on startup."""
    global COMMUNITY_MEDAL_DATA
    try:
        with urlopen(COMMUNITY_MEDALS_URL, timeout=8) as resp:
            COMMUNITY_MEDAL_DATA = json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.warning("Community medals fetch failed (%s); medal data unavailable this session",
                       COMMUNITY_MEDALS_URL, exc_info=True)

# ── Main App ───────────────────────────────────────────────────────────────
class NeonWhiteApp(RushParserTabMixin, RushSplitsTabMixin, RushStdTabMixin,
                   RushTimerTabMixin, RushFinderTabMixin, LevelTabMixin,
                   GlobalTabMixin, PlayerTabMixin, SettingsTabMixin,
                   SidebarTabMixin):
    def __init__(self, root):
        self.root        = root
        self.cfg         = load_config()
        self.t           = THEMES[self.cfg["theme"]]
        self.running     = False
        self.current_section = None
        self._player_results = []
        self._finder_running = False

        root.title(APP_TITLE)
        root.geometry("1020x740")
        root.minsize(900, 640)
        root.configure(bg=self.t["bg"])

        # Load GOHU font before building UI
        load_gohu_font()

        # Compile C shuffle library for fast seed search
        threading.Thread(target=self._init_c_shuffle, daemon=True).start()

        self._build_ui()
        self._apply_theme()
        self._show_section("global")

        # Auto-connect if DLL path saved
        if self.cfg["dll_path"] and os.path.exists(self.cfg["dll_path"]):
            threading.Thread(target=self._connect_steam, daemon=True).start()

        # Fetch cheater list in background on startup
        threading.Thread(target=self._fetch_cheaters_bg, daemon=True).start()

        # Fetch community medals in background on startup
        threading.Thread(target=fetch_community_medals, daemon=True).start()

    # ── UI Construction ────────────────────────────────────────────────────
    def _build_ui(self):
        t = self.t

        # Root panes
        self.sidebar_frame = tk.Frame(self.root, width=210, bg=t["bg2"])
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar_frame.pack_propagate(False)

        self.main_frame = tk.Frame(self.root, bg=t["bg"])
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_sidebar()
        self._build_global_section()
        self._build_level_section()
        self._build_player_section()
        self._build_settings_section()

        self._build_rush_sections()

    def _build_rush_sections(self):
        """Build all five Rush Tools sections."""
        self._build_rush_finder()
        self._build_rush_parser()
        self._build_rush_splits()
        self._build_rush_std()
        self._build_rush_timer()

    # ── Rush Tools shared helpers ──────────────────────────────────────────
    def _rush_header(self, parent, title, subtitle):
        t = self.t
        hdr = tk.Frame(parent, bg=t["bg"], padx=24, pady=18)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=title, font=("Helvetica", 16, "bold"),
                 bg=t["bg"], fg=t["fg"]).pack(anchor="w")
        tk.Label(hdr, text=subtitle, font=("Helvetica", 10),
                 bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(2, 0))
        tk.Frame(parent, height=1, bg=t["border"]).pack(fill=tk.X, padx=24, pady=(0, 10))

    def _rush_field_label(self, parent, text):
        t = self.t
        tk.Label(parent, text=text.upper(), font=("Helvetica", 8),
                 bg=t["bg"], fg=t["fg2"], anchor="w").pack(anchor="w", pady=(4, 2))

    def _rush_entry(self, parent, var=None, placeholder="", width=None):
        t = self.t
        kw = dict(font=("Helvetica", 11), bg=t["input_bg"], fg=t["input_fg"],
                  insertbackground=t["fg"], relief="flat", bd=1)
        if width:
            kw["width"] = width
        e = tk.Entry(parent, textvariable=var, **kw) if var else tk.Entry(parent, **kw)
        e.pack(fill=tk.X if not width else tk.NONE, pady=(0, 8))
        if placeholder and not var:
            e.insert(0, placeholder)
            e.config(fg=t["fg2"])
            def on_focus_in(ev, ent=e, ph=placeholder):
                if ent.get() == ph:
                    ent.delete(0, tk.END)
                    ent.config(fg=t["fg"])
            def on_focus_out(ev, ent=e, ph=placeholder):
                if not ent.get():
                    ent.insert(0, ph)
                    ent.config(fg=t["fg2"])
            e.bind("<FocusIn>",  on_focus_in)
            e.bind("<FocusOut>", on_focus_out)
        return e

    def _rush_text(self, parent, height=6):
        t = self.t
        txt = tk.Text(parent, height=height, font=("Courier", 10),
                      bg=t["log_bg"], fg=t["fg"], insertbackground=t["fg"],
                      relief="flat", bd=1, wrap=tk.NONE)
        txt.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        return txt

    def _rush_btn(self, parent, text, cmd):
        t = self.t
        btn = tk.Button(parent, text=text, command=cmd,
                        font=("Helvetica", 10, "bold"),
                        bg=t["btn_bg"], fg="#0a0a0f" if self.cfg["theme"] == "dark" else "#ffffff",
                        relief="flat", bd=0, padx=16, pady=6, cursor="hand2")
        btn.pack(anchor="w", pady=(4, 8))
        return btn

    def _rush_result_box(self, parent, height=10):
        t = self.t
        box = tk.Text(parent, height=height, font=("Courier", 10),
                      bg=t["log_bg"], fg=t["accent"],
                      insertbackground=t["fg"], relief="flat", bd=1,
                      state=tk.DISABLED, wrap=tk.NONE)
        sb = ttk.Scrollbar(parent, orient="vertical", command=box.yview)
        box.configure(yscrollcommand=sb.set)
        box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        return box

    def _rush_show(self, box, text):
        box.configure(state=tk.NORMAL)
        box.delete("1.0", tk.END)
        box.insert(tk.END, text)
        box.configure(state=tk.DISABLED)

    def _rush_dropdown(self, parent, var, options, cmd=None):
        t = self.t
        cb = ttk.Combobox(parent, textvariable=var, values=options,
                          font=("Helvetica", 10), state="readonly")
        cb.pack(anchor="w", pady=(0, 8))
        if cmd:
            cb.bind("<<ComboboxSelected>>", lambda e: cmd())
        return cb

    # ── Seed Finder — see tab_rush_finder.RushFinderTabMixin ───────────────

    def _rush_key_to_num(self, rush_var_str):
        mapping = {
            "White / Mikey": 96,
            "Violet":        8,
            "Red":           8,
            "Yellow":        8,
        }
        return mapping.get(rush_var_str, 96)

    def _rush_key_from_display(self, display):
        mapping = {
            "White / Mikey": "96",
            "Violet":        "violet",
            "Red":           "red",
            "Yellow":        "yellow",
        }
        return mapping.get(display, "96")

    # ── Seed Parser — see tab_rush_parser.RushParserTabMixin ───────────────

    # ── Splits Updater — see tab_rush_splits.RushSplitsTabMixin ────────────

    # ── Standardize Splits — see tab_rush_std.RushStdTabMixin ──────────────

    # ── Run Timer — see tab_rush_timer.RushTimerTabMixin ───────────────────

    def _get_medal(self, level_name, secs, rush_key):
        """Return a medal label string for a given level and time."""
        code = self._resolve_level_code(level_name, rush_key)
        if not code:
            return ""
        us = int(secs * 1_000_000)
        std = STANDARD_MEDAL_DATA.get(code)
        if std:
            if us <= std[4]: return "DEV"
            if us <= std[3]: return "ACE"
            if us <= std[2]: return "GOLD"
            if us <= std[1]: return "SILVER"
            if us <= std[0]: return "BRONZE"
        comm = COMMUNITY_MEDAL_DATA.get(code)
        if comm and len(comm) >= 3:
            if len(comm) >= 5 and us <= comm[4]: return "BLOOD DIAMOND"
            if len(comm) >= 5 and us <= comm[3]: return "TOPAZ"
            if us <= comm[2]: return "SAPPHIRE"
            if us <= comm[1]: return "AMETHYST"
            if us <= comm[0]: return "EMERALD"
        return ""

    def _resolve_level_code(self, level_name, rush_key):
        """Resolve a display name to its internal code name for medal lookup."""
        names = RUSH_LEVELS.get(rush_key, RUSH_LEVELS["96"])
        nl = level_name.lower().strip()
        # Try direct match in alias map (reverse lookup)
        for code, display in RUSH_ALIASES.items():
            if display == nl:
                return code.upper()
        # Try matching against display names
        for i, n in enumerate(names):
            if n.lower() == nl:
                # Map display name back to code via our existing LEVELS list
                for disp, internal in LEVELS:
                    if disp.lower() == nl:
                        return internal.upper()
        return None

    def _build_radio_group(self, parent, var, options):
        t = self.t
        frame = tk.Frame(parent, bg=t["bg"])
        buttons = []

        # In dark mode (neon green bg), use dark text for legibility
        # In light mode (green bg), use white text
        selected_fg = "#0a0a0f" if self.cfg["theme"] == "dark" else "#ffffff"

        def select(val):
            var.set(val)
            for v, lbl_widget in buttons:
                is_sel = (v == val)
                lbl_widget.configure(
                    bg=t["btn_bg"] if is_sel else t["bg"],
                    fg=selected_fg if is_sel else t["fg2"],
                    relief="flat",
                    bd=0,
                )

        for val, label in options:
            lbl = tk.Label(
                frame, text=label,
                font=("Helvetica", 10),
                bg=t["bg"], fg=t["fg2"],
                padx=10, pady=3,
                cursor="hand2",
                relief="flat", bd=0,
                borderwidth=1,
            )
            lbl.pack(side=tk.LEFT, padx=(0, 4))
            lbl.bind("<Button-1>", lambda e, v=val: select(v))
            buttons.append((val, lbl))

        select(var.get())
        return frame

    # Sidebar — see tab_sidebar.SidebarTabMixin

    # ── Sections ───────────────────────────────────────────────────────────
    # Global Export — see tab_global.GlobalTabMixin
    # Level Search  — see tab_level.LevelTabMixin

    # Player Lookup — see tab_player.PlayerTabMixin

    # Settings — see tab_settings.SettingsTabMixin

    def _build_results_area(self, parent, key):
        t = self.t
        pane = tk.Frame(parent, bg=t["bg"], padx=24, pady=0)
        pane.pack(fill=tk.BOTH, expand=True)

        # Log area
        log_frame = tk.Frame(pane, bg=t["bg"])
        log_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(log_frame, text="Log", font=("Helvetica", 9, "bold"),
                 bg=t["bg"], fg=t["fg2"], anchor="w").pack(anchor="w")
        log = tk.Text(log_frame, height=4, font=("Courier", 9),
                      bg=t["log_bg"], fg=t["log_fg"], relief="flat",
                      bd=1, state=tk.DISABLED, wrap=tk.WORD)
        log.pack(fill=tk.X)
        setattr(self, f"{key}_log", log)

        # Table area
        table_frame = tk.Frame(pane, bg=t["bg"])
        table_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(table_frame, text="Results", font=("Helvetica", 9, "bold"),
                 bg=t["bg"], fg=t["fg2"], anchor="w").pack(anchor="w")

        cols = ("rank", "level", "name", "time")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=8)
        for col, width, label in [
            ("rank",  70,  "Rank"),
            ("level", 180, "Level"),
            ("name",  200, "Player"),
            ("time",  100, "Time"),
        ]:
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="center" if col in ("rank", "time") else "w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        setattr(self, f"{key}_tree", tree)

        # Push to Sheet button — pinned below table, always visible on player tab
        if key == "player":
            sheet_btn_frame = tk.Frame(parent, bg=t["bg"], padx=24, pady=8)
            sheet_btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
            tk.Frame(sheet_btn_frame, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))
            self.push_sheet_btn = tk.Button(
                sheet_btn_frame,
                text="Push to Google Sheet",
                font=("Helvetica", 10, "bold"),
                command=self._push_to_sheet,
                state=tk.DISABLED
            )
            self.push_sheet_btn.pack(anchor="w")
            tk.Label(sheet_btn_frame,
                     text="Runs a Player Lookup first, then click to push times and ranks to your sheet.",
                     font=("Helvetica", 8), bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(2, 0))

    def _section_header(self, parent, title, subtitle):
        t = self.t
        hdr = tk.Frame(parent, bg=t["bg"], padx=24, pady=18)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=title, font=("Helvetica", 16, "bold"),
                 bg=t["bg"], fg=t["fg"]).pack(anchor="w")
        tk.Label(hdr, text=subtitle, font=("Helvetica", 10),
                 bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(2, 0))
        tk.Frame(parent, height=1, bg=t["border"]).pack(fill=tk.X, padx=24, pady=(0, 12))

    # ── Navigation — see tab_sidebar.SidebarTabMixin._show_section ─────────

    # ── Player mode ────────────────────────────────────────────────────────
    # ── Steam connection ───────────────────────────────────────────────────
    def _connect_steam(self, dll_path=None):
        path = dll_path or self.cfg["dll_path"]
        if not path:
            self._set_status(False, "No DLL path set. Go to Settings.")
            return
        self._set_status(None, "Connecting...")
        ok, msg = steam_api.init_steam(path)
        if ok:
            self._set_status(True, "Connected", path)
        else:
            self._set_status(False, msg)

    def _set_status(self, connected, message, dll_path=None):
        t = self.t
        if connected is True:
            color = t["success"]
            self.status_label.configure(text="Connected", fg=t["success"])
            self.player_label.configure(text=f"Player: {steam_api.player_name}")
        elif connected is False:
            color = t["error"]
            self.status_label.configure(text=message, fg=t["error"])
            self.player_label.configure(text="Player: —")
        else:
            color = t["fg2"]
            self.status_label.configure(text=message, fg=t["fg2"])
            self.player_label.configure(text="Player: —")

        self.status_dot.configure(fg=color)

        if dll_path:
            short = dll_path if len(dll_path) < 28 else "..." + dll_path[-25:]
            self.dll_label.configure(text=f"DLL: {short}")
        elif connected is False and not dll_path:
            self.dll_label.configure(text="DLL: not connected")

    # ── Log helpers ────────────────────────────────────────────────────────
    def _log(self, key, msg):
        log = getattr(self, f"{key}_log")
        log.configure(state=tk.NORMAL)
        log.insert(tk.END, msg + "\n")
        log.see(tk.END)
        log.configure(state=tk.DISABLED)
        self.root.update_idletasks()

    def _clear_log(self, key):
        log = getattr(self, f"{key}_log")
        log.configure(state=tk.NORMAL)
        log.delete("1.0", tk.END)
        log.configure(state=tk.DISABLED)

    def _clear_table(self, key):
        tree = getattr(self, f"{key}_tree")
        tree.delete(*tree.get_children())

    def _add_row(self, key, rank, level, name, time_str):
        tree = getattr(self, f"{key}_tree")
        tree.insert("", tk.END, values=(f"#{rank}", level, name, f"{time_str}s"))

    # ── C shuffle init ─────────────────────────────────────────────────────
    def _init_c_shuffle(self):
        ok = _load_c_shuffle()
        mode = "C-accelerated" if ok else "Python fallback"
        if not ok:
            logger.warning("shuffle.dll did not load; seed search will use the slow "
                           "Python fallback. Run compile_shuffle.py to (re)build.")
        self.root.after(0, lambda m=mode: self.finder_status_var.set(
            f"Seed search engine: {m}"
        ))

    # ── Cheater list ───────────────────────────────────────────────────────
    def _fetch_cheaters_bg(self):
        count = steam_api.fetch_cheater_list()
        if count > 0:
            self.cheater_label.configure(
                text=f"Cheaters filtered: {count:,}",
                fg=self.t["success"]
            )
        else:
            self.cheater_label.configure(
                text="Cheater list: unavailable",
                fg=self.t["fg2"]
            )

    # ── Push to Sheet ──────────────────────────────────────────────────────
    def _push_to_sheet(self):
        if not self._player_results:
            messagebox.showerror("No data", "Run a Player Lookup first.")
            return

        sheet_id   = self.cfg.get("sheet_id", "").strip()
        times_tab  = self.cfg.get("times_tab", "").strip()
        times_cell = self.cfg.get("times_start_cell", "A1").strip()
        ranks_tab  = self.cfg.get("ranks_tab", "").strip()
        ranks_cell = self.cfg.get("ranks_start_cell", "A1").strip()

        if not sheet_id:
            messagebox.showerror("Error", "No Sheet ID set. Configure Google Sheets in Settings.")
            return
        if not times_tab and not ranks_tab:
            messagebox.showerror("Error", "Configure at least one tab name in Settings.")
            return

        self.push_sheet_btn.configure(state=tk.DISABLED, text="Pushing...")

        def push_worker():
            try:
                # Lazy import — defers slow Google libs until user actually uses Sheets
                import sheets
                service = sheets.get_sheets_service()

                # Build indexed lists — one entry per level in game order,
                # skipping levels the player has no time for
                result_by_level = {r["level"]: r for r in self._player_results}
                times_vals = []
                ranks_vals = []
                for offset, (display_name, _) in enumerate(WHOLE_GAME_LEVELS):
                    if display_name in result_by_level:
                        r = result_by_level[display_name]
                        times_vals.append((offset, format_time_mmss(r["score_ms"])))
                        ranks_vals.append((offset, r["rank"]))
                    # levels with no entry are simply omitted — cell untouched

                if times_tab:
                    sheets.push_to_sheet(service, sheet_id, times_tab, times_cell, times_vals)
                if ranks_tab:
                    sheets.push_to_sheet(service, sheet_id, ranks_tab, ranks_cell, ranks_vals)

                pushed = len(times_vals)
                parts  = []
                if times_tab:
                    parts.append(f"{pushed} times → '{times_tab}'!{times_cell}")
                if ranks_tab:
                    parts.append(f"{pushed} ranks → '{ranks_tab}'!{ranks_cell}")
                messagebox.showinfo("Success", "Pushed to Google Sheet:\n" + "\n".join(parts))

            except Exception as e:
                logger.exception("Google Sheets push failed")
                messagebox.showerror("Push failed", str(e))
            finally:
                self.push_sheet_btn.configure(state=tk.NORMAL, text="Push to Google Sheet")

        threading.Thread(target=push_worker, daemon=True).start()



    # ── Run: Global Export — see tab_global.GlobalTabMixin ─────────────────
    # ── Run: Level Search  — see tab_level.LevelTabMixin ───────────────────

    # ── Run: Player Lookup — see tab_player.PlayerTabMixin ─────────────────

    # ── Theme application ──────────────────────────────────────────────────
    def _apply_theme(self):
        self._apply_widget_defaults()

    def _apply_widget_defaults(self):
        t   = self.t
        fnt      = gohu(14)
        fnt_bold = gohu(13, bold=True)
        fnt_sm   = gohu(12)
        fnt_mono = gohu_mono(14)

        self.root.option_add("*Font",               fnt)
        self.root.option_add("*Background",         t["bg"])
        self.root.option_add("*Foreground",         t["fg"])
        self.root.option_add("*Entry.Background",   t["input_bg"])
        self.root.option_add("*Entry.Foreground",   t["input_fg"])
        self.root.option_add("*Entry.Font",         fnt)
        self.root.option_add("*Entry.Relief",       "flat")
        self.root.option_add("*Entry.BorderWidth",  "1")
        self.root.option_add("*Button.Background",  t["btn_bg"])
        self.root.option_add("*Button.Foreground",
                             "#0a0a0f" if self.cfg["theme"] == "dark" else "#ffffff")
        self.root.option_add("*Button.Font",        fnt_bold)
        self.root.option_add("*Button.Relief",      "flat")
        self.root.option_add("*Button.BorderWidth", "0")
        self.root.option_add("*Button.Cursor",      "hand2")
        self.root.option_add("*Button.Padx",        "10")
        self.root.option_add("*Label.Background",   t["bg"])
        self.root.option_add("*Label.Foreground",   t["fg"])
        self.root.option_add("*Label.Font",         fnt)
        self.root.option_add("*Text.Background",    t["log_bg"])
        self.root.option_add("*Text.Foreground",    t["log_fg"])
        self.root.option_add("*Text.Font",          fnt_mono)
        self.root.option_add("*Text.Relief",        "flat")
        self.root.option_add("*Listbox.Font",       fnt)

        # Fix sidebar to set width, content area flexes
        self.sidebar_frame.pack_propagate(False)
        self.sidebar_frame.configure(width=210)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.theme_use("default")

        # Progress bar — neon green fill
        style.configure("NeonGreen.Horizontal.TProgressbar",
                        troughcolor=t["bg2"],
                        background=t["accent"],
                        bordercolor=t["border"],
                        lightcolor=t["accent"],
                        darkcolor=t["accent"])

        style.configure("Treeview",
                        background=t["bg"], foreground=t["fg"],
                        fieldbackground=t["bg"], rowheight=24,
                        font=fnt_sm)
        style.configure("Treeview.Heading",
                        background=t["bg2"], foreground=t["fg2"],
                        font=fnt_sm, relief="flat")
        style.map("Treeview",
                  background=[("selected", t["select"])],
                  foreground=[("selected", t["fg"])])
        style.configure("TScrollbar",
                        background=t["bg2"], troughcolor=t["bg"],
                        bordercolor=t["border"], arrowcolor=t["fg2"])

        # Combobox — fix font for both dropdown list AND selected value display
        style.configure("TCombobox",
                        fieldbackground=t["input_bg"],
                        background=t["bg2"],
                        foreground=t["input_fg"],
                        selectbackground=t["input_bg"],
                        selectforeground=t["input_fg"],
                        arrowcolor=t["fg2"],
                        font=fnt)
        style.map("TCombobox",
                  fieldbackground=[("readonly", t["input_bg"])],
                  foreground=[("readonly", t["input_fg"])],
                  selectbackground=[("readonly", t["input_bg"])],
                  selectforeground=[("readonly", t["input_fg"])])
        self.root.option_add("*TCombobox*Listbox.background",       t["bg2"])
        self.root.option_add("*TCombobox*Listbox.foreground",       t["fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["select"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", t["fg"])
        self.root.option_add("*TCombobox*Listbox.font",             fnt)

        # Apply GOHU font to all tk widgets globally via option_add
        # Note: ttk widgets need explicit style config above
        self.root.tk.call("option", "add", "*TCombobox*font", f"{{{GOHU_FONT_NAME}}} 14")


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for PyInstaller on Windows
    root = tk.Tk()
    app  = NeonWhiteApp(root)
    root.mainloop()
    if steam_api.steam_ready:
        steam_api.steam.SteamAPI_Shutdown()
