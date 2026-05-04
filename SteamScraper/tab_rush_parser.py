"""Rush Tools — Seed Parser tab.

Mixin for NeonWhiteApp. Decodes a seed number into the resulting level order.
"""
import tkinter as tk

from shuffle_lib import full_shuffle
from rush_data import RUSH_LEVELS
from fonts import gohu


class RushParserTabMixin:
    def _build_rush_parser(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.rush_parser_frame = f
        self._rush_header(f, "Seed Parser",
            "Enter any seed number to see the full level play order it produces.")

        body = tk.Frame(f, bg=t["bg"], padx=24)
        body.pack(fill=tk.BOTH, expand=True)

        self._rush_field_label(body, "Rush")
        self.parser_rush_var = tk.StringVar(value="White / Mikey")
        self._rush_dropdown(body, self.parser_rush_var,
            ["White / Mikey", "Violet", "Red", "Yellow"])

        self._rush_field_label(body, "Seed Number")
        seed_row = tk.Frame(body, bg=t["bg"])
        seed_row.pack(anchor="w", pady=(0, 8))
        self.parser_seed_var = tk.StringVar()
        tk.Entry(seed_row, textvariable=self.parser_seed_var, width=24,
                 font=gohu(14), bg=t["input_bg"], fg=t["input_fg"],
                 insertbackground=t["fg"], relief="flat").pack(side=tk.LEFT)

        self._rush_btn(body, "Parse Seed", self._run_parser)

        self._rush_field_label(body, "Level Order")
        result_frame = tk.Frame(body, bg=t["bg"])
        result_frame.pack(fill=tk.BOTH, expand=True)
        self.parser_result = self._rush_result_box(result_frame, height=14)

    def _run_parser(self):
        try:
            seed = int(self.parser_seed_var.get().strip())
            if seed < 1 or seed > 2147483647:
                raise ValueError
        except ValueError:
            self._rush_show(self.parser_result, "Please enter a valid seed number (1 to 2,147,483,647).")
            return
        rush_key   = self._rush_key_from_display(self.parser_rush_var.get())
        num_levels = self._rush_key_to_num(self.parser_rush_var.get())
        order      = full_shuffle(num_levels, seed)
        names      = RUSH_LEVELS[rush_key]
        lines      = [f"Seed {seed} — {self.parser_rush_var.get()}\n"]
        for pos, idx in enumerate(order):
            lines.append(f"{pos+1:>3}. {names[idx]}")
        self._rush_show(self.parser_result, "\n".join(lines))
