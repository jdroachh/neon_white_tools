"""Sidebar (navigation + status panel).

Mixin for NeonWhiteApp. Builds the left-hand collapsible nav (Leaderboard
Tools, Rush Tools, Settings), the bottom status panel (Steam state, DLL
path, player, cheater list), and owns the section-switching logic that
maps nav keys → tab frames built by the other mixins.
"""
import tkinter as tk


class SidebarTabMixin:
    def _build_sidebar(self):
        t = self.t
        sb = self.sidebar_frame
        sb.configure(bg=t["sidebar_bg"])

        # ── App title ──────────────────────────────────────────────────────
        tk.Label(sb, text="Neon White Tools", font=("Helvetica", 13, "bold"),
                 bg=t["sidebar_bg"], fg=t["fg"], anchor="w",
                 padx=16, pady=14).pack(fill=tk.X)

        tk.Frame(sb, height=1, bg=t["border"]).pack(fill=tk.X)

        # ── Scrollable nav area ────────────────────────────────────────────
        nav_area = tk.Frame(sb, bg=t["sidebar_bg"])
        nav_area.pack(fill=tk.BOTH, expand=True)

        # ── Group builder helper ───────────────────────────────────────────
        def make_group(parent, label, items, item_click_fn, group_key):
            """
            Creates a collapsible group with a header and child items.
            items: list of (section_key, display_label)
            Returns dict of {key: label_widget}
            """
            group_frame = tk.Frame(parent, bg=t["sidebar_bg"])
            group_frame.pack(fill=tk.X)

            # Track collapsed state
            state = {"collapsed": False}

            # Header row
            header = tk.Frame(group_frame, bg=t["sidebar_bg"])
            header.pack(fill=tk.X)

            arrow = tk.Label(header, text="▾", font=("Helvetica", 9),
                             bg=t["sidebar_bg"], fg=t["fg2"], padx=6)
            arrow.pack(side=tk.LEFT)

            tk.Label(header, text=label, font=("Helvetica", 9, "bold"),
                     bg=t["sidebar_bg"], fg=t["fg2"], anchor="w",
                     pady=6, cursor="hand2").pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Items container
            items_frame = tk.Frame(group_frame, bg=t["sidebar_bg"])
            items_frame.pack(fill=tk.X)

            def toggle(e=None):
                state["collapsed"] = not state["collapsed"]
                if state["collapsed"]:
                    items_frame.pack_forget()
                    arrow.configure(text="▸")
                else:
                    items_frame.pack(fill=tk.X)
                    arrow.configure(text="▾")

            header.bind("<Button-1>", toggle)
            arrow.bind("<Button-1>", toggle)
            for w in header.winfo_children():
                w.bind("<Button-1>", toggle)

            btns = {}
            for key, lbl_text in items:
                btn = tk.Label(items_frame, text=lbl_text,
                               font=("Helvetica", 11),
                               bg=t["sidebar_bg"], fg=t["nav_inactive_fg"],
                               anchor="w", padx=24, pady=8, cursor="hand2")
                btn.pack(fill=tk.X)
                btn.bind("<Button-1>", lambda e, k=key: item_click_fn(k))
                btns[key] = btn

            return btns, group_frame

        # ── Leaderboard Tools group ────────────────────────────────────────
        lb_items = [
            ("global", "Global Export"),
            ("level",  "Level Search"),
            ("player", "Player Lookup"),
        ]
        lb_btns, _ = make_group(
            nav_area, "Leaderboard Tools", lb_items,
            lambda k: self._show_section(k), "leaderboard"
        )

        tk.Frame(nav_area, height=1, bg=t["border"]).pack(fill=tk.X, pady=4)

        # ── Rush Tools group ───────────────────────────────────────────────
        rush_items = [
            ("rush_finder",  "Seed Finder"),
            ("rush_parser",  "Seed Parser"),
            ("rush_splits",  "Splits Updater"),
            ("rush_std",     "Standardize Splits"),
            ("rush_timer",   "Run Timer"),
        ]
        rush_btns, _ = make_group(
            nav_area, "Rush Tools", rush_items,
            lambda k: self._show_section(k), "rush"
        )

        tk.Frame(nav_area, height=1, bg=t["border"]).pack(fill=tk.X, pady=4)

        # Merge all nav buttons into one dict
        self.nav_btns = {**lb_btns, **rush_btns}

        # ── Settings button — always visible at bottom of nav ──────────────
        self.settings_btn = tk.Label(nav_area, text="Settings",
                                     font=("Helvetica", 11),
                                     bg=t["sidebar_bg"], fg=t["nav_inactive_fg"],
                                     anchor="w", padx=16, pady=8, cursor="hand2")
        self.settings_btn.pack(fill=tk.X)
        self.settings_btn.bind("<Button-1>", lambda e: self._show_section("settings"))

        # ── Status panel at bottom ─────────────────────────────────────────
        self.status_frame = tk.Frame(sb, bg=t["sidebar_bg"])
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=12)

        tk.Frame(self.status_frame, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 10))

        self.status_dot = tk.Label(self.status_frame, text="●", font=("Helvetica", 10),
                                   bg=t["sidebar_bg"], fg=t["error"])
        self.status_dot.pack(anchor="w")

        self.status_label = tk.Label(self.status_frame, text="Not connected",
                                     font=("Helvetica", 9), bg=t["sidebar_bg"], fg=t["fg2"],
                                     wraplength=155, justify=tk.LEFT, anchor="w")
        self.status_label.pack(fill=tk.X)

        self.dll_label = tk.Label(self.status_frame, text="DLL: not set",
                                  font=("Helvetica", 8), bg=t["sidebar_bg"], fg=t["fg2"],
                                  wraplength=155, justify=tk.LEFT, anchor="w")
        self.dll_label.pack(fill=tk.X, pady=(2, 0))

        self.player_label = tk.Label(self.status_frame, text="Player: —",
                                     font=("Helvetica", 8), bg=t["sidebar_bg"], fg=t["fg2"],
                                     wraplength=155, justify=tk.LEFT, anchor="w")
        self.player_label.pack(fill=tk.X, pady=(2, 0))

        self.cheater_label = tk.Label(self.status_frame, text="Cheater list: loading...",
                                      font=("Helvetica", 8), bg=t["sidebar_bg"], fg=t["fg2"],
                                      wraplength=155, justify=tk.LEFT, anchor="w")
        self.cheater_label.pack(fill=tk.X, pady=(2, 0))

    # ── Navigation ─────────────────────────────────────────────────────────
    def _show_section(self, key):
        t = self.t
        sections = {
            "global":       self.global_frame,
            "level":        self.level_frame,
            "player":       self.player_frame,
            "settings":     self.settings_frame,
            "rush_finder":  self.rush_finder_frame,
            "rush_parser":  self.rush_parser_frame,
            "rush_splits":  self.rush_splits_frame,
            "rush_std":     self.rush_std_frame,
            "rush_timer":   self.rush_timer_frame,
        }
        for k, frame in sections.items():
            frame.pack_forget()
        if key in sections:
            sections[key].pack(fill=tk.BOTH, expand=True)
        self.current_section = key

        # Update nav button highlights
        for k, btn in self.nav_btns.items():
            is_active = (k == key)
            btn.configure(
                bg=t["sidebar_sel"] if is_active else t["sidebar_bg"],
                fg=t["nav_active_fg"] if is_active else t["nav_inactive_fg"],
                font=("Helvetica", 11, "bold" if is_active else "normal")
            )
        is_settings = (key == "settings")
        self.settings_btn.configure(
            bg=t["sidebar_sel"] if is_settings else t["sidebar_bg"],
            fg=t["nav_active_fg"] if is_settings else t["nav_inactive_fg"],
            font=("Helvetica", 11, "bold" if is_settings else "normal")
        )
