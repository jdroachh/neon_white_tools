"""Player Lookup tab.

Mixin for NeonWhiteApp. Looks up a Steam player's rank/time on a single
level, a chapter, or the whole game. Stores results on
`self._player_results` for the Sheets push (handled in core).
"""
import csv
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from rush_data import LEVELS, LEVEL_LOOKUP, CHAPTERS, WHOLE_GAME_LEVELS
import steam_api


class PlayerTabMixin:
    def _build_player_section(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.player_frame = f

        self._section_header(f, "Player Lookup",
                             "Look up a player's rank and time by Steam ID.")

        ctrl = tk.Frame(f, bg=t["bg"], padx=24)
        ctrl.pack(fill=tk.X, pady=(0, 12))

        # Steam ID
        r1 = tk.Frame(ctrl, bg=t["bg"])
        r1.pack(fill=tk.X, pady=4)
        tk.Label(r1, text="Steam ID", width=16, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.player_id_var = tk.StringVar()
        tk.Entry(r1, textvariable=self.player_id_var, width=22,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        tk.Button(r1, text="Use My Steam ID",
                  font=("Helvetica", 9),
                  command=self._use_my_steam_id).pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(r1, text="  17-digit number from Steam profile URL",
                 font=("Helvetica", 9), bg=t["bg"], fg=t["fg2"]).pack(side=tk.LEFT)

        # Search mode
        r2 = tk.Frame(ctrl, bg=t["bg"])
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text="Search mode", width=16, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.player_mode_var = tk.StringVar(value="level")
        mode_group = self._build_radio_group(r2, self.player_mode_var,
            [("level", "Single level"), ("chapter", "Chapter"), ("game", "Whole game")]
        )
        mode_group.pack(side=tk.LEFT)
        self.player_mode_var.trace_add("write", lambda *_: self._update_player_mode())

        # Dynamic sub-selector
        self.player_sub_frame = tk.Frame(ctrl, bg=t["bg"])
        self.player_sub_frame.pack(fill=tk.X, pady=4)
        self._update_player_mode()

        # Output options
        r4 = tk.Frame(ctrl, bg=t["bg"])
        r4.pack(fill=tk.X, pady=4)
        tk.Label(r4, text="Output", width=16, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.player_out_var = tk.StringVar(value="display")
        self._build_radio_group(r4, self.player_out_var,
            [("display", "Display in app"), ("csv", "Save to CSV"), ("both", "Both")]
        ).pack(side=tk.LEFT)

        self.player_run_btn = tk.Button(ctrl, text="Look Up",
                                        font=("Helvetica", 10, "bold"),
                                        command=self._run_player)
        self.player_run_btn.pack(anchor="w", pady=(10, 0))

        self._build_results_area(f, "player")

    def _update_player_mode(self):
        t = self.t
        for w in self.player_sub_frame.winfo_children():
            w.destroy()

        mode = self.player_mode_var.get()

        if mode == "level":
            tk.Label(self.player_sub_frame, text="Level", width=16, anchor="w",
                     font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
            self.player_level_var = tk.StringVar()
            combo = ttk.Combobox(self.player_sub_frame, textvariable=self.player_level_var,
                                 values=[d for d, _ in LEVELS], width=28, font=("Helvetica", 10))
            combo.pack(side=tk.LEFT)

        elif mode == "chapter":
            tk.Label(self.player_sub_frame, text="Chapter", width=16, anchor="w",
                     font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
            self.player_chapter_var = tk.StringVar()
            combo = ttk.Combobox(self.player_sub_frame, textvariable=self.player_chapter_var,
                                 values=list(CHAPTERS.keys()), width=34, font=("Helvetica", 10))
            combo.pack(side=tk.LEFT)

        elif mode == "game":
            tk.Label(self.player_sub_frame,
                     text="All 121 levels will be searched.",
                     font=("Helvetica", 10), bg=t["bg"], fg=t["fg2"]).pack(side=tk.LEFT)

    def _use_my_steam_id(self):
        if not steam_api.steam_ready or not steam_api.logged_in_steam_id:
            messagebox.showerror(
                "Not connected",
                "Connect to Steam first in Settings — your Steam ID will be populated automatically."
            )
            return
        self.player_id_var.set(str(steam_api.logged_in_steam_id))

    def _run_player(self):
        if not steam_api.steam_ready:
            messagebox.showerror("Not connected", "Connect to Steam first in Settings.")
            return
        if self.running:
            return

        sid_str = self.player_id_var.get().strip()
        if not sid_str.isdigit() or len(sid_str) != 17:
            messagebox.showerror("Error", "Steam ID must be a 17-digit number.")
            return
        steam_id = int(sid_str)
        mode = self.player_mode_var.get()
        out  = self.player_out_var.get()

        levels_to_search = []
        context = ""

        if mode == "level":
            name = self.player_level_var.get().strip()
            match = LEVEL_LOOKUP.get(name.lower())
            if not match:
                messagebox.showerror("Error", f"Level '{name}' not found.")
                return
            levels_to_search = [match]
            context = match[0]

        elif mode == "chapter":
            chap = self.player_chapter_var.get().strip()
            if chap not in CHAPTERS:
                messagebox.showerror("Error", "Please select a valid chapter.")
                return
            for dn in CHAPTERS[chap]:
                m = LEVEL_LOOKUP.get(dn.lower())
                if m:
                    levels_to_search.append(m)
            context = chap

        elif mode == "game":
            levels_to_search = list(WHOLE_GAME_LEVELS)
            context = "Whole Game"

        self.running = True
        self.player_run_btn.configure(state=tk.DISABLED, text="Looking up...")
        self._clear_log("player")
        self._clear_table("player")

        threading.Thread(
            target=self._player_worker,
            args=(steam_id, levels_to_search, context, out),
            daemon=True
        ).start()

    def _player_worker(self, steam_id, levels_to_search, context, out):
        nb = steam_api.steam.SteamAPI_ISteamFriends_GetFriendPersonaName(steam_api.friends, steam_id)
        looked_up_name = nb.decode("utf-8", errors="replace") if nb else str(steam_id)
        self._log("player", f"Looking up {looked_up_name} across {len(levels_to_search)} levels...")
        rows = []

        for display_name, internal_name in levels_to_search:
            self._log("player", f"  {display_name}...")
            lb = steam_api.find_leaderboard(internal_name)
            if not lb:
                self._log("player", f"  {display_name}... not found.")
                continue
            total = steam_api.steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(steam_api.user_stats, lb)
            entry = steam_api.get_player_entry(lb, steam_id)
            if entry:
                time_str = f"{entry.score / 1000:.3f}"
                self._log("player", f"  {display_name}... rank #{entry.global_rank}, {time_str}s")
                rows.append({
                    "level":    display_name,
                    "rank":     entry.global_rank,
                    "time":     time_str,
                    "score_ms": entry.score,
                    "total":    total,
                })
                if out in ("display", "both"):
                    self._add_row("player", entry.global_rank, display_name, looked_up_name, time_str)
            else:
                self._log("player", f"  {display_name}... no entry.")

        if out in ("csv", "both") and rows:
            safe_ctx = context.replace(" ", "_").replace("/", "_").replace("-", "")
            path = os.path.join(self.cfg["output_folder"], f"player_{safe_ctx}.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["level","rank","time","score_ms","total"]
                )
                writer.writeheader()
                writer.writerows(rows)
            self._log("player", f"\nSaved to {path}")

        self._log("player", f"Done. Found entries on {len(rows)}/{len(levels_to_search)} levels.")
        self._player_results = rows
        if rows:
            self.push_sheet_btn.configure(state=tk.NORMAL)
        self.player_run_btn.configure(state=tk.NORMAL, text="Look Up")
        self.running = False
