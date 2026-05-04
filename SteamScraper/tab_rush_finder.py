"""Rush Tools — Seed Finder tab.

Mixin for NeonWhiteApp. Searches up to 2.1B seeds across multiple worker
processes for ones where target levels appear within the first N positions.

Note: a few pre-existing error paths reference `self.finder_result`, which
is never created. Those branches (placeholder/empty input, non-numeric depth,
parse error) will raise AttributeError if ever hit. Preserved as-is during
extraction; tracked separately.
"""
import multiprocessing
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from shuffle_lib import full_shuffle
from seed_search import _seed_search_worker, _expected_match_count
from rush_data import RUSH_LEVELS, RUSH_ALIASES
from fonts import gohu


class RushFinderTabMixin:
    def _build_rush_finder(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.rush_finder_frame = f
        self._rush_header(f, "Seed Finder",
            "Search up to 2.1 billion seeds to find ones where your desired levels appear early.")

        body = tk.Frame(f, bg=t["bg"], padx=24)
        body.pack(fill=tk.BOTH, expand=True)

        # Rush selector + search depth row — use grid for stable alignment
        row1 = tk.Frame(body, bg=t["bg"])
        row1.pack(fill=tk.X, pady=(0, 4))
        row1.columnconfigure(0, weight=3)
        row1.columnconfigure(1, weight=1)

        lc = tk.Frame(row1, bg=t["bg"])
        lc.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self._rush_field_label(lc, "Rush")
        self.finder_rush_var = tk.StringVar(value="White / Mikey")
        rush_cb = ttk.Combobox(lc, textvariable=self.finder_rush_var,
                               values=["White / Mikey", "Violet", "Red", "Yellow"],
                               font=gohu(14), state="readonly")
        rush_cb.pack(anchor="w", pady=(0, 8))
        rush_cb.bind("<<ComboboxSelected>>", lambda e: self._finder_on_rush_change())

        rc = tk.Frame(row1, bg=t["bg"])
        rc.grid(row=0, column=1, sticky="ew")
        self._rush_field_label(rc, "Search Depth")
        self.finder_depth_var = tk.StringVar(value="10")
        depth_entry = tk.Entry(rc, textvariable=self.finder_depth_var, width=8,
                               font=gohu(14), bg=t["input_bg"], fg=t["input_fg"],
                               relief="flat")
        depth_entry.pack(anchor="w", pady=(0, 8))

        # Desired levels — dynamic depth update on key release
        self._rush_field_label(body, "Desired Starting Levels")
        self.finder_levels_entry = self._rush_entry(body,
            placeholder="e.g. The Third Temple, Absolution, The Clocktower")
        self.finder_levels_entry.bind("<KeyRelease>", lambda e: self._finder_update_depth())
        tk.Label(body, text="Comma-separated level names. Case insensitive.",
                 font=gohu(12), bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(0, 8))

        # Result mode
        self._rush_field_label(body, "Result Mode")
        mode_frame = tk.Frame(body, bg=t["bg"])
        mode_frame.pack(anchor="w", pady=(0, 8))
        self.finder_mode_var = tk.StringVar(value="first")
        self._build_radio_group(mode_frame, self.finder_mode_var,
            [("first", "First Match"), ("multi", "Find Multiple")]).pack(side=tk.LEFT)

        maxseeds_frame = tk.Frame(body, bg=t["bg"])
        maxseeds_frame.pack(anchor="w", pady=(0, 8))
        tk.Label(maxseeds_frame, text="Max seeds to find:", font=("Helvetica", 10),
                 bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT, padx=(0, 8))
        self.finder_maxseeds_var = tk.StringVar(value="5")
        tk.Entry(maxseeds_frame, textvariable=self.finder_maxseeds_var, width=6,
                 font=("Helvetica", 10), bg=t["input_bg"], fg=t["input_fg"],
                 relief="flat").pack(side=tk.LEFT)

        # Buttons
        btn_frame = tk.Frame(body, bg=t["bg"])
        btn_frame.pack(anchor="w", pady=(4, 8))
        self.finder_run_btn = tk.Button(btn_frame, text="Find Seed",
                                        command=self._run_finder,
                                        font=("Helvetica", 10, "bold"),
                                        bg=t["btn_bg"],
                                        fg="#0a0a0f" if self.cfg["theme"] == "dark" else "#ffffff",
                                        relief="flat", bd=0, padx=16, pady=6, cursor="hand2")
        self.finder_run_btn.pack(side=tk.LEFT)
        self.finder_stop_btn = tk.Button(btn_frame, text="Stop",
                                         command=self._stop_finder,
                                         font=("Helvetica", 10, "bold"),
                                         bg=t["error"], fg="#ffffff",
                                         relief="flat", bd=0, padx=16, pady=6, cursor="hand2",
                                         state=tk.DISABLED)
        self.finder_stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Progress bar + status
        self.finder_progress = ttk.Progressbar(
            body, mode="determinate", maximum=100, value=0,
            style="NeonGreen.Horizontal.TProgressbar"
        )
        self.finder_progress.pack(fill=tk.X, pady=(4, 0))
        self.finder_status_var = tk.StringVar(value="")
        tk.Label(body, textvariable=self.finder_status_var, font=gohu(12),
                 bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(2, 6))

        # Results — collapsible treeview
        self._rush_field_label(body, "Results (click a seed to expand/collapse level order)")
        result_frame = tk.Frame(body, bg=t["bg"])
        result_frame.pack(fill=tk.BOTH, expand=True)
        self.finder_tree = ttk.Treeview(result_frame, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(result_frame, orient="vertical", command=self.finder_tree.yview)
        self.finder_tree.configure(yscrollcommand=vsb.set)
        self.finder_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.finder_tree.tag_configure("seed",    font=gohu(13, bold=True),
                                       foreground=t["accent"])
        self.finder_tree.tag_configure("match",   foreground=t["accent"])
        self.finder_tree.tag_configure("level",   foreground=t["fg2"])
        self.finder_tree.tag_configure("no_match",foreground=t["fg2"])

    def _finder_on_rush_change(self):
        """Auto-set search depth to 8 for non-White/Mikey rushes."""
        rush = self.finder_rush_var.get()
        if rush != "White / Mikey":
            self.finder_depth_var.set("8")
        else:
            # Restore depth based on current level count
            self._finder_update_depth()

    def _finder_update_depth(self):
        """Dynamically update search depth to match number of entered levels."""
        raw = self.finder_levels_entry.get().strip()
        placeholder = "e.g. The Third Temple, Absolution, The Clocktower"
        if not raw or raw == placeholder:
            return
        # Count non-empty comma-separated entries
        count = len([p for p in raw.split(",") if p.strip()])
        if count < 1:
            return
        rush = self.finder_rush_var.get()
        max_depth = self._rush_key_to_num(rush)
        try:
            current = int(self.finder_depth_var.get())
        except ValueError:
            current = 0
        # Only increase depth automatically, never decrease while typing
        new_depth = max(current, min(count, max_depth))
        self.finder_depth_var.set(str(new_depth))

    def _run_finder(self):
        rush_display = self.finder_rush_var.get()
        rush_key     = self._rush_key_from_display(rush_display)
        num_levels   = self._rush_key_to_num(rush_display)
        mode         = self.finder_mode_var.get()

        raw_levels = self.finder_levels_entry.get().strip()
        if raw_levels in ("", "e.g. The Third Temple, Absolution, The Clocktower"):
            self._rush_show(self.finder_result, "Please enter at least one desired level.")
            return
        try:
            depth = int(self.finder_depth_var.get())
        except ValueError:
            self._rush_show(self.finder_result, "Search Depth must be a number.")
            return
        max_seeds = 1 if mode == "first" else max(1, int(self.finder_maxseeds_var.get() or "5"))

        target_indices, err = self._parse_level_names(raw_levels, rush_key)
        if err:
            self._rush_show(self.finder_result, f"Error: {err}")
            return

        target_set = set(target_indices)
        names      = RUSH_LEVELS[rush_key]

        # Determine core count — all minus one, minimum 1
        num_cores  = max(1, multiprocessing.cpu_count() - 1)
        MAX_SEED   = 2_147_483_647
        chunk_size = MAX_SEED // num_cores

        # Warn if the search is statistically near-impossible
        expected = _expected_match_count(num_levels, len(target_indices), depth, MAX_SEED)
        if expected < 10:
            msg = (f"Expected matches across the full 2.1B seed range: ~{expected:.2f}.\n\n"
                   f"With {len(target_indices)} target level(s) at depth {depth} "
                   f"in a pool of {num_levels}, this search is unlikely to find any "
                   f"results.\n\nIncrease Search Depth or reduce target levels for a "
                   f"feasible search.\n\nProceed anyway?")
            if not messagebox.askyesno("Unlikely search", msg):
                self._rush_show(self.finder_result, "Search cancelled.")
                return

        self._finder_running   = True
        self._finder_stop_event = multiprocessing.Event()
        self.finder_run_btn.configure(state=tk.DISABLED)
        self.finder_stop_btn.configure(state=tk.NORMAL)
        self.finder_progress.configure(value=0)
        self.finder_status_var.set(f"Searching across {num_cores} core(s)...")
        # Clear previous results
        for item in self.finder_tree.get_children():
            self.finder_tree.delete(item)

        def manager_thread():
            result_queue = multiprocessing.Queue()
            workers      = []
            MAX_SEED     = 2_147_483_647

            for core in range(num_cores):
                start = core * chunk_size + 1
                end   = (core + 1) * chunk_size + 1 if core < num_cores - 1 else MAX_SEED + 1
                p = multiprocessing.Process(
                    target=_seed_search_worker,
                    args=((start, end, num_levels, target_set, depth,
                           result_queue, self._finder_stop_event),),
                    daemon=True
                )
                p.start()
                workers.append(p)

            found         = []
            done_workers  = 0
            seeds_checked = 0
            TOTAL_SEEDS   = MAX_SEED

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
                    pct = min(99, int(seeds_checked / TOTAL_SEEDS * 100))
                    self.root.after(0, lambda p=pct: self.finder_progress.configure(value=p))
                    self.root.after(0, lambda s=seeds_checked, f=len(found):
                        self.finder_status_var.set(
                            f"Searching... {s:,} of {TOTAL_SEEDS:,} seeds checked, {f} found"
                        ))
                    continue

                seed  = item
                found.append(seed)
                order = full_shuffle(num_levels, seed)
                names = RUSH_LEVELS[rush_key]

                def add_to_tree(s=seed, o=order, ns=names, ti=target_indices):
                    target_set_local = set(ti)
                    positions = {idx: pos+1 for pos, idx in enumerate(o) if idx in target_set_local}
                    pos_strs  = ", ".join(f"{ns[idx]} @{positions[idx]}" for idx in ti)
                    node = self.finder_tree.insert(
                        "", "end",
                        text=f"Seed {s}  —  {pos_strs}",
                        tags=("seed",), open=False
                    )
                    for pos, idx in enumerate(o):
                        tag    = "match" if idx in target_set_local else "level"
                        marker = " ◀" if idx in target_set_local else ""
                        self.finder_tree.insert(
                            node, "end",
                            text=f"  {pos+1:>3}.  {ns[idx]}{marker}",
                            tags=(tag,)
                        )

                self.root.after(0, add_to_tree)
                self.root.after(0, lambda n=len(found):
                    self.finder_status_var.set(f"Found {n} seed(s). Still searching..."))

                if len(found) >= max_seeds:
                    self._finder_stop_event.set()
                    break

            self._finder_stop_event.set()
            for p in workers:
                p.join(timeout=2)

            done_msg = (f"Done. Found {len(found)} seed(s)."
                        if found else "No matching seeds found in full range.")
            self.root.after(0, lambda: self.finder_progress.configure(value=100))
            self.root.after(0, lambda: self.finder_status_var.set(done_msg))
            self.root.after(0, lambda: self.finder_run_btn.configure(state=tk.NORMAL))
            self.root.after(0, lambda: self.finder_stop_btn.configure(state=tk.DISABLED))
            self._finder_running = False

        threading.Thread(target=manager_thread, daemon=True).start()

    def _stop_finder(self):
        if hasattr(self, "_finder_stop_event"):
            self._finder_stop_event.set()
        self._finder_running = False
        self.finder_status_var.set("Search stopped.")
        self.finder_progress.configure(value=0)
        self.finder_run_btn.configure(state=tk.NORMAL)
        self.finder_stop_btn.configure(state=tk.DISABLED)

    def _parse_level_names(self, raw, rush_key):
        """Parse comma-separated level names/numbers. Returns (indices_list, error_str)."""
        names  = RUSH_LEVELS[rush_key]
        name_map = {n.lower(): i for i, n in enumerate(names)}
        parts  = [p.strip() for p in raw.split(",") if p.strip()]
        indices = []
        for p in parts:
            pl = p.lower()
            # Exact match
            if pl in name_map:
                indices.append(name_map[pl])
                continue
            # Alias match
            alias = RUSH_ALIASES.get(pl)
            if alias and alias in name_map:
                indices.append(name_map[alias])
                continue
            # Partial match
            matches = [i for i, n in enumerate(names) if pl in n.lower()]
            if len(matches) == 1:
                indices.append(matches[0])
            elif len(matches) > 1:
                return None, f'"{p}" matches multiple levels: {", ".join(names[i] for i in matches)}'
            else:
                # Try numeric
                if p.isdigit():
                    idx = int(p) - 1
                    if 0 <= idx < len(names):
                        indices.append(idx)
                    else:
                        return None, f"Level number {p} out of range."
                else:
                    return None, f'Unknown level: "{p}"'
        if not indices:
            return None, "No valid levels entered."
        return indices, None
