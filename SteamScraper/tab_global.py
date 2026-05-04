"""Global Export tab.

Mixin for NeonWhiteApp. Fetches the top N entries for every level and
writes a single CSV plus optional in-app display.
"""
import csv
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from rush_data import LEVELS
import steam_api


class GlobalTabMixin:
    def _build_global_section(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.global_frame = f

        self._section_header(f, "Global Export",
                             "Fetch the top N entries for every level and save to CSV.")

        ctrl = tk.Frame(f, bg=t["bg"], padx=24)
        ctrl.pack(fill=tk.X, pady=(0, 12))

        # Entry count
        r1 = tk.Frame(ctrl, bg=t["bg"])
        r1.pack(fill=tk.X, pady=4)
        tk.Label(r1, text="Entries per level", width=18, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.global_count_var = tk.StringVar(value=str(self.cfg["entry_count"]))
        tk.Entry(r1, textvariable=self.global_count_var, width=10,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)

        # Output folder
        r2 = tk.Frame(ctrl, bg=t["bg"])
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text="Output folder", width=18, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.global_folder_var = tk.StringVar(value=self.cfg["output_folder"])
        tk.Entry(r2, textvariable=self.global_folder_var, width=38,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(r2, text="Browse", command=self._browse_output_global,
                  font=("Helvetica", 9)).pack(side=tk.LEFT)

        # Output options
        r3 = tk.Frame(ctrl, bg=t["bg"])
        r3.pack(fill=tk.X, pady=4)
        tk.Label(r3, text="Output", width=18, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.global_out_var = tk.StringVar(value="csv")
        self._build_radio_group(r3, self.global_out_var,
            [("display", "Display in app"), ("csv", "Save to CSV"), ("both", "Both")]
        ).pack(side=tk.LEFT)

        # Run button
        self.global_run_btn = tk.Button(ctrl, text="Run Export",
                                        font=("Helvetica", 10, "bold"),
                                        command=self._run_global)
        self.global_run_btn.pack(anchor="w", pady=(10, 0))

        self._build_results_area(f, "global")

    def _browse_output_global(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.global_folder_var.set(folder)

    def _run_global(self):
        if not steam_api.steam_ready:
            messagebox.showerror("Not connected", "Connect to Steam first in Settings.")
            return
        if self.running:
            return
        try:
            count = int(self.global_count_var.get())
        except ValueError:
            messagebox.showerror("Error", "Entry count must be a number.")
            return
        folder = self.global_folder_var.get()
        out    = self.global_out_var.get()

        self.running = True
        self.global_run_btn.configure(state=tk.DISABLED, text="Running...")
        self._clear_log("global")
        self._clear_table("global")

        threading.Thread(
            target=self._global_worker,
            args=(count, folder, out),
            daemon=True
        ).start()

    def _global_worker(self, count, folder, out):
        csv_path = os.path.join(folder, "neon_white_top_entries.csv")
        csv_file = None
        writer   = None

        if out in ("csv", "both"):
            csv_file = open(csv_path, "w", newline="", encoding="utf-8")
            writer = csv.DictWriter(
                csv_file, fieldnames=["rank","level","name","score_ms","time"]
            )
            writer.writeheader()

        total_levels = len(LEVELS)
        for idx, (display, internal) in enumerate(LEVELS, 1):
            self._log("global", f"[{idx}/{total_levels}] {display}...")
            lb = steam_api.find_leaderboard(internal)
            if not lb:
                self._log("global", f"  → not found, skipping.")
                continue

            total_entries = steam_api.steam.SteamAPI_ISteamUserStats_GetLeaderboardEntryCount(steam_api.user_stats, lb)
            fetch = min(total_entries, count)
            start = 1
            level_rows = []
            while start <= fetch:
                end   = min(start + steam_api.BATCH_SIZE - 1, fetch)
                batch = steam_api.fetch_batch(lb, start, end)
                if not batch:
                    break
                for e in batch:
                    e["level"] = display
                level_rows.extend(batch)
                start = end + 1
                time.sleep(0.05)

            for r in level_rows:
                if out in ("display", "both"):
                    self._add_row("global", r["rank"], display, r["name"], r["time"])
                if writer:
                    writer.writerow({k: r[k] for k in ["rank","level","name","score_ms","time"]})
            if csv_file:
                csv_file.flush()

            self._log("global", f"  → {len(level_rows)} entries fetched.")

        if csv_file:
            csv_file.close()
            self._log("global", f"\nSaved to {csv_path}")

        self._log("global", "Done!")
        self.global_run_btn.configure(state=tk.NORMAL, text="Run Export")
        self.running = False
