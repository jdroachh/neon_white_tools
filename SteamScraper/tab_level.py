"""Level Lookup tab.

Mixin for NeonWhiteApp. Fetches the top N entries for a single level.
"""
import csv
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from rush_data import LEVELS, LEVEL_LOOKUP
import steam_api


class LevelTabMixin:
    def _build_level_section(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.level_frame = f

        self._section_header(f, "Level Search",
                             "Fetch the top N entries for a specific level.")

        ctrl = tk.Frame(f, bg=t["bg"], padx=24)
        ctrl.pack(fill=tk.X, pady=(0, 12))

        # Level selector
        r1 = tk.Frame(ctrl, bg=t["bg"])
        r1.pack(fill=tk.X, pady=4)
        tk.Label(r1, text="Level", width=14, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.level_var = tk.StringVar()
        level_names = [d for d, _ in LEVELS]
        self.level_combo = ttk.Combobox(r1, textvariable=self.level_var,
                                        values=level_names, width=28,
                                        font=("Helvetica", 10))
        self.level_combo.pack(side=tk.LEFT)
        self.level_combo.bind("<KeyRelease>", self._filter_levels)

        # Entry count
        r2 = tk.Frame(ctrl, bg=t["bg"])
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text="Entries to fetch", width=14, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.level_count_var = tk.StringVar(value="100")
        tk.Entry(r2, textvariable=self.level_count_var, width=10,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)

        # Output options
        r3 = tk.Frame(ctrl, bg=t["bg"])
        r3.pack(fill=tk.X, pady=4)
        tk.Label(r3, text="Output", width=14, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.level_out_var = tk.StringVar(value="display")
        self._build_radio_group(r3, self.level_out_var,
            [("display", "Display in app"), ("csv", "Save to CSV"), ("both", "Both")]
        ).pack(side=tk.LEFT)

        self.level_run_btn = tk.Button(ctrl, text="Search",
                                       font=("Helvetica", 10, "bold"),
                                       command=self._run_level)
        self.level_run_btn.pack(anchor="w", pady=(10, 0))

        self._build_results_area(f, "level")

    def _filter_levels(self, event):
        val = self.level_var.get().lower()
        filtered = [d for d, _ in LEVELS if val in d.lower()]
        self.level_combo["values"] = filtered

    def _run_level(self):
        if not steam_api.steam_ready:
            messagebox.showerror("Not connected", "Connect to Steam first in Settings.")
            return
        if self.running:
            return

        level_name = self.level_var.get().strip()
        match = LEVEL_LOOKUP.get(level_name.lower())
        if not match:
            messagebox.showerror("Error", f"Level '{level_name}' not found.")
            return

        try:
            count = int(self.level_count_var.get())
        except ValueError:
            messagebox.showerror("Error", "Entry count must be a number.")
            return

        out = self.level_out_var.get()
        display_name, internal_name = match

        self.running = True
        self.level_run_btn.configure(state=tk.DISABLED, text="Searching...")
        self._clear_log("level")
        self._clear_table("level")

        threading.Thread(
            target=self._level_worker,
            args=(display_name, internal_name, count, out),
            daemon=True
        ).start()

    def _level_worker(self, display_name, internal_name, count, out):
        self._log("level", f"Finding leaderboard for {display_name}...")
        lb = steam_api.find_leaderboard(internal_name)
        if not lb:
            self._log("level", "Leaderboard not found.")
            self.level_run_btn.configure(state=tk.NORMAL, text="Search")
            self.running = False
            return

        total = steam_api.steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(steam_api.user_stats, lb)
        fetch = min(total, count)
        self._log("level", f"Total entries: {total:,}  |  Fetching top {fetch}...")

        start = 1
        all_rows = []
        while start <= fetch:
            end   = min(start + steam_api.BATCH_SIZE - 1, fetch)
            batch = steam_api.fetch_batch(lb, start, end)
            if not batch:
                break
            all_rows.extend(batch)
            start = end + 1
            time.sleep(0.05)

        for r in all_rows:
            if out in ("display", "both"):
                self._add_row("level", r["rank"], display_name, r["name"], r["time"])

        if out in ("csv", "both"):
            safe  = display_name.replace(" ", "_").replace("'", "")
            path  = os.path.join(self.cfg["output_folder"], f"{safe}_top{len(all_rows)}.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["rank","level","name","score_ms","time"])
                writer.writeheader()
                for r in all_rows:
                    writer.writerow({k: r.get(k, display_name) for k in ["rank","name","score_ms","time"]} | {"level": display_name})
            self._log("level", f"Saved to {path}")

        self._log("level", f"Done. {len(all_rows)} entries retrieved.")
        self.level_run_btn.configure(state=tk.NORMAL, text="Search")
        self.running = False
