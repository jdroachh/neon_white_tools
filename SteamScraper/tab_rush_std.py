"""Rush Tools — Standardize Splits tab.

Mixin for NeonWhiteApp. Converts splits recorded in seed order back to
standard level order.
"""
import tkinter as tk

from shuffle_lib import full_shuffle
from rush_data import RUSH_LEVELS
from fonts import gohu


class RushStdTabMixin:
    def _build_rush_std(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.rush_std_frame = f
        self._rush_header(f, "Standardize Splits",
            "Convert splits recorded in seed order back to standard level order.")

        body = tk.Frame(f, bg=t["bg"], padx=24)
        body.pack(fill=tk.BOTH, expand=True)

        self._rush_field_label(body, "Rush")
        self.std_rush_var = tk.StringVar(value="White / Mikey")
        self._rush_dropdown(body, self.std_rush_var,
            ["White / Mikey", "Violet", "Red", "Yellow"])

        self._rush_field_label(body, "Seed Number")
        std_seed_row = tk.Frame(body, bg=t["bg"])
        std_seed_row.pack(anchor="w", pady=(0, 8))
        self.std_seed_var = tk.StringVar()
        tk.Entry(std_seed_row, textvariable=self.std_seed_var, width=24,
                 font=gohu(14), bg=t["input_bg"], fg=t["input_fg"],
                 insertbackground=t["fg"], relief="flat").pack(side=tk.LEFT)

        cols = tk.Frame(body, bg=t["bg"])
        cols.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(cols, bg=t["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._rush_field_label(left, "Gold Splits (seed order, one per line)")
        self.std_gold_text = self._rush_text(left, height=8)

        right = tk.Frame(cols, bg=t["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rush_field_label(right, "Segment Splits (seed order, one per line)")
        self.std_seg_text = self._rush_text(right, height=8)

        self._rush_btn(body, "Standardize", self._run_std)

        result_cols = tk.Frame(body, bg=t["bg"])
        result_cols.pack(fill=tk.BOTH, expand=True)

        rl = tk.Frame(result_cols, bg=t["bg"])
        rl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._rush_field_label(rl, "Standard Order Gold")
        self.std_gold_result = self._rush_result_box(rl, height=6)

        rr = tk.Frame(result_cols, bg=t["bg"])
        rr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rush_field_label(rr, "Standard Order Segments")
        self.std_seg_result = self._rush_result_box(rr, height=6)

    def _run_std(self):
        try:
            seed = int(self.std_seed_var.get().strip())
            if seed < 1 or seed > 2147483647:
                raise ValueError
        except ValueError:
            self._rush_show(self.std_gold_result, "Invalid seed number.")
            return
        rush_key   = self._rush_key_from_display(self.std_rush_var.get())
        num_levels = self._rush_key_to_num(self.std_rush_var.get())
        order      = full_shuffle(num_levels, seed)
        names      = RUSH_LEVELS[rush_key]

        # Build inverse: standard_index -> seed_position
        seed_position = [0] * num_levels
        for pos, idx in enumerate(order):
            seed_position[idx] = pos

        gold_raw = [l for l in self.std_gold_text.get("1.0", tk.END).strip().splitlines() if l.strip()]
        seg_raw  = [l for l in self.std_seg_text.get("1.0", tk.END).strip().splitlines() if l.strip()]

        if gold_raw and len(gold_raw) != num_levels:
            self._rush_show(self.std_gold_result,
                f"Expected {num_levels} gold splits, got {len(gold_raw)}.")
            return
        if seg_raw and len(seg_raw) != num_levels:
            self._rush_show(self.std_seg_result,
                f"Expected {num_levels} segment splits, got {len(seg_raw)}.")
            return

        if gold_raw:
            lines = [f"{i+1:>3}. {names[i]:<28} {gold_raw[seed_position[i]]}"
                     for i in range(num_levels)]
            self._rush_show(self.std_gold_result, "\n".join(lines))
        if seg_raw:
            lines = [f"{i+1:>3}. {names[i]:<28} {seg_raw[seed_position[i]]}"
                     for i in range(num_levels)]
            self._rush_show(self.std_seg_result, "\n".join(lines))
