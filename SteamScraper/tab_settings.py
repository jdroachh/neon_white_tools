"""Settings tab.

Mixin for NeonWhiteApp. DLL path, output folder, default entry count,
theme, Google Sheets integration (Sheet ID, tab names, OAuth sign-in/out),
and a single Save button that writes to neonwhite_config.json.
"""
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from logger import get_logger

logger = get_logger(__name__)

# Duplicated from sheets.TOKEN_FILE on purpose — importing sheets at startup
# pulls in slow Google libs, and the Settings UI needs to render the auth
# status before the user has done anything.
TOKEN_FILE = "token.json"


class SettingsTabMixin:
    def _build_settings_section(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.settings_frame = f

        self._section_header(f, "Settings", "Configure the application.")

        ctrl = tk.Frame(f, bg=t["bg"], padx=24)
        ctrl.pack(fill=tk.X, pady=(0, 12))

        # DLL path
        r1 = tk.Frame(ctrl, bg=t["bg"])
        r1.pack(fill=tk.X, pady=6)
        tk.Label(r1, text="steam_api64.dll path", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_dll_var = tk.StringVar(value=self.cfg["dll_path"])
        tk.Entry(r1, textvariable=self.settings_dll_var, width=36,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(r1, text="Browse", command=self._browse_dll,
                  font=("Helvetica", 9)).pack(side=tk.LEFT)
        tk.Button(r1, text="Connect", command=self._connect_from_settings,
                  font=("Helvetica", 9)).pack(side=tk.LEFT, padx=(6, 0))

        # Output folder
        r2 = tk.Frame(ctrl, bg=t["bg"])
        r2.pack(fill=tk.X, pady=6)
        tk.Label(r2, text="Default output folder", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_folder_var = tk.StringVar(value=self.cfg["output_folder"])
        tk.Entry(r2, textvariable=self.settings_folder_var, width=36,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(r2, text="Browse", command=self._browse_output_settings,
                  font=("Helvetica", 9)).pack(side=tk.LEFT)

        # Default entry count
        r3 = tk.Frame(ctrl, bg=t["bg"])
        r3.pack(fill=tk.X, pady=6)
        tk.Label(r3, text="Default entry count", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_count_var = tk.StringVar(value=str(self.cfg["entry_count"]))
        tk.Entry(r3, textvariable=self.settings_count_var, width=10,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)

        # Theme
        r4 = tk.Frame(ctrl, bg=t["bg"])
        r4.pack(fill=tk.X, pady=6)
        tk.Label(r4, text="Theme", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_theme_var = tk.StringVar(value=self.cfg["theme"])
        self._build_radio_group(r4, self.settings_theme_var,
            [("light", "Light"), ("dark", "Dark")]
        ).pack(side=tk.LEFT)

        # ── Google Sheets ──────────────────────────────────────────────────
        tk.Frame(ctrl, height=1, bg=t["border"]).pack(fill=tk.X, pady=(20, 12))
        tk.Label(ctrl, text="Google Sheets Integration",
                 font=("Helvetica", 12, "bold"),
                 bg=t["bg"], fg=t["fg"], anchor="w").pack(anchor="w", pady=(0, 4))
        tk.Label(ctrl,
                 text="Place credentials.json in the app folder, then configure below.\n"
                      "On first use a browser will open to sign in with Google.",
                 font=("Helvetica", 9), bg=t["bg"], fg=t["fg2"], justify=tk.LEFT,
                 anchor="w").pack(anchor="w", pady=(0, 10))

        # Sheet ID
        rs1 = tk.Frame(ctrl, bg=t["bg"])
        rs1.pack(fill=tk.X, pady=4)
        tk.Label(rs1, text="Sheet URL or ID", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_sheet_id_var = tk.StringVar(value=self.cfg.get("sheet_id", ""))
        tk.Entry(rs1, textvariable=self.settings_sheet_id_var, width=44,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)

        # Times tab
        rs2 = tk.Frame(ctrl, bg=t["bg"])
        rs2.pack(fill=tk.X, pady=4)
        tk.Label(rs2, text="Times tab name", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_times_tab_var = tk.StringVar(value=self.cfg.get("times_tab", ""))
        tk.Entry(rs2, textvariable=self.settings_times_tab_var, width=20,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(rs2, text="Starting cell", font=("Helvetica", 10),
                 bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_times_cell_var = tk.StringVar(value=self.cfg.get("times_start_cell", "A1"))
        tk.Entry(rs2, textvariable=self.settings_times_cell_var, width=6,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(6, 0))

        # Ranks tab
        rs3 = tk.Frame(ctrl, bg=t["bg"])
        rs3.pack(fill=tk.X, pady=4)
        tk.Label(rs3, text="Ranks tab name", width=22, anchor="w",
                 font=("Helvetica", 10), bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_ranks_tab_var = tk.StringVar(value=self.cfg.get("ranks_tab", ""))
        tk.Entry(rs3, textvariable=self.settings_ranks_tab_var, width=20,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(rs3, text="Starting cell", font=("Helvetica", 10),
                 bg=t["bg"], fg=t["fg"]).pack(side=tk.LEFT)
        self.settings_ranks_cell_var = tk.StringVar(value=self.cfg.get("ranks_start_cell", "A1"))
        tk.Entry(rs3, textvariable=self.settings_ranks_cell_var, width=6,
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(6, 0))

        # Auth status + test button
        rs4 = tk.Frame(ctrl, bg=t["bg"])
        rs4.pack(fill=tk.X, pady=(10, 0))
        self.sheets_auth_label = tk.Label(
            rs4,
            text="● Not authenticated" if not os.path.exists(TOKEN_FILE) else "● Authenticated",
            font=("Helvetica", 9),
            bg=t["bg"],
            fg=t["error"] if not os.path.exists(TOKEN_FILE) else t["success"]
        )
        self.sheets_auth_label.pack(side=tk.LEFT)
        tk.Button(rs4, text="Sign in with Google",
                  font=("Helvetica", 9),
                  command=self._sheets_authenticate).pack(side=tk.LEFT, padx=(12, 0))
        tk.Button(rs4, text="Sign out",
                  font=("Helvetica", 9),
                  command=self._sheets_signout).pack(side=tk.LEFT, padx=(6, 0))

        # Single save button covering all settings
        tk.Frame(ctrl, height=1, bg=t["border"]).pack(fill=tk.X, pady=(20, 12))
        tk.Button(ctrl, text="Save Settings", font=("Helvetica", 10, "bold"),
                  command=self._save_settings).pack(anchor="w")

    def _browse_dll(self):
        path = filedialog.askopenfilename(
            title="Select steam_api64.dll",
            filetypes=[("DLL files", "*.dll"), ("All files", "*.*")]
        )
        if path:
            self.settings_dll_var.set(path)

    def _browse_output_settings(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.settings_folder_var.set(folder)

    def _connect_from_settings(self):
        from neonwhite_app import save_config
        path = self.settings_dll_var.get().strip()
        if not path:
            messagebox.showerror("Error", "Please set the DLL path first.")
            return
        self.cfg["dll_path"] = path
        save_config(self.cfg)
        threading.Thread(target=self._connect_steam, args=(path,), daemon=True).start()

    def _save_settings(self):
        from neonwhite_app import save_config
        self.cfg["dll_path"]         = self.settings_dll_var.get().strip()
        self.cfg["output_folder"]    = self.settings_folder_var.get().strip()
        self.cfg["theme"]            = self.settings_theme_var.get()
        self.cfg["sheet_id"]         = self._extract_sheet_id(self.settings_sheet_id_var.get().strip())
        self.cfg["times_tab"]        = self.settings_times_tab_var.get().strip()
        self.cfg["times_start_cell"] = self.settings_times_cell_var.get().strip()
        self.cfg["ranks_tab"]        = self.settings_ranks_tab_var.get().strip()
        self.cfg["ranks_start_cell"] = self.settings_ranks_cell_var.get().strip()
        try:
            self.cfg["entry_count"] = int(self.settings_count_var.get())
        except ValueError:
            messagebox.showerror("Error", "Entry count must be a number.")
            return
        save_config(self.cfg)
        self.global_count_var.set(str(self.cfg["entry_count"]))
        if self.cfg["theme"] != self.t:
            messagebox.showinfo("Theme", "Restart the app to apply the new theme.")
        messagebox.showinfo("Saved", "Settings saved successfully.")

    def _extract_sheet_id(self, url_or_id):
        m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url_or_id)
        return m.group(1) if m else url_or_id

    # ── Google Sheets auth ─────────────────────────────────────────────────
    def _sheets_authenticate(self):
        def auth_worker():
            try:
                # Lazy import — defers slow Google libs until user actually uses Sheets
                import sheets
                sheets.get_sheets_service()
                self.sheets_auth_label.configure(
                    text="● Authenticated", fg=self.t["success"]
                )
                messagebox.showinfo("Google Sheets", "Successfully signed in!")
            except Exception as e:
                logger.exception("Google Sheets authentication failed")
                messagebox.showerror("Authentication failed", str(e))
        threading.Thread(target=auth_worker, daemon=True).start()

    def _sheets_signout(self):
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        self.sheets_auth_label.configure(
            text="● Not authenticated", fg=self.t["error"]
        )
        messagebox.showinfo("Google Sheets", "Signed out. Token removed.")
