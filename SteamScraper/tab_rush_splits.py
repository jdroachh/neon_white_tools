"""Rush Tools — Splits Updater tab.

Mixin for NeonWhiteApp. Reorders splits recorded in standard level order
into the order produced by a given seed.
"""
import tkinter as tk

from shuffle_lib import full_shuffle
from rush_data import RUSH_LEVELS
from fonts import gohu


class RushSplitsTabMixin:
    def _build_rush_splits(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.rush_splits_frame = f
        self._rush_header(f, "Splits Updater",
            "Paste your splits in standard level order and reorder them to match a seed.")

        body = tk.Frame(f, bg=t["bg"], padx=24)
        body.pack(fill=tk.BOTH, expand=True)

        self._rush_field_label(body, "Rush")
        self.splits_rush_var = tk.StringVar(value="White / Mikey")
        self._rush_dropdown(body, self.splits_rush_var,
            ["White / Mikey", "Violet", "Red", "Yellow"])

        self._rush_field_label(body, "Seed Number")
        splits_seed_row = tk.Frame(body, bg=t["bg"])
        splits_seed_row.pack(anchor="w", pady=(0, 8))
        self.splits_seed_var = tk.StringVar()
        tk.Entry(splits_seed_row, textvariable=self.splits_seed_var, width=24,
                 font=gohu(14), bg=t["input_bg"], fg=t["input_fg"],
                 insertbackground=t["fg"], relief="flat").pack(side=tk.LEFT)

        # Two text areas side by side
        cols = tk.Frame(body, bg=t["bg"])
        cols.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(cols, bg=t["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._rush_field_label(left, "Gold Splits (standard order, one per line)")
        self.splits_gold_text = self._rush_text(left, height=8)

        right = tk.Frame(cols, bg=t["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rush_field_label(right, "Segment Splits (standard order, one per line)")
        self.splits_seg_text = self._rush_text(right, height=8)

        self._rush_btn(body, "Generate Splits", self._run_splits)

        result_cols = tk.Frame(body, bg=t["bg"])
        result_cols.pack(fill=tk.BOTH, expand=True)

        rl = tk.Frame(result_cols, bg=t["bg"])
        rl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._rush_field_label(rl, "Reordered Gold")
        self.splits_gold_result = self._rush_result_box(rl, height=6)

        rr = tk.Frame(result_cols, bg=t["bg"])
        rr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rush_field_label(rr, "Reordered Segments")
        self.splits_seg_result = self._rush_result_box(rr, height=6)

    def _run_splits(self):
        try:
            seed = int(self.splits_seed_var.get().strip())
            if seed < 1 or seed > 2147483647:
                raise ValueError
        except ValueError:
            self._rush_show(self.splits_gold_result, "Invalid seed number.")
            return
        rush_key   = self._rush_key_from_display(self.splits_rush_var.get())
        num_levels = self._rush_key_to_num(self.splits_rush_var.get())
        order      = full_shuffle(num_levels, seed)
        names      = RUSH_LEVELS[rush_key]

        gold_raw = [l for l in self.splits_gold_text.get("1.0", tk.END).strip().splitlines() if l.strip()]
        seg_raw  = [l for l in self.splits_seg_text.get("1.0", tk.END).strip().splitlines() if l.strip()]

        if gold_raw and len(gold_raw) != num_levels:
            self._rush_show(self.splits_gold_result,
                f"Expected {num_levels} gold splits, got {len(gold_raw)}.")
            return
        if seg_raw and len(seg_raw) != num_levels:
            self._rush_show(self.splits_seg_result,
                f"Expected {num_levels} segment splits, got {len(seg_raw)}.")
            return

        gold_out = [gold_raw[idx] for idx in order] if gold_raw else []
        seg_out  = [seg_raw[idx]  for idx in order] if seg_raw  else []

        if gold_out:
            lines = [f"{pos+1:>3}. {names[order[pos]]:<28} {t}"
                     for pos, t in enumerate(gold_out)]
            self._rush_show(self.splits_gold_result, "\n".join(lines))
        if seg_out:
            lines = [f"{pos+1:>3}. {names[order[pos]]:<28} {t}"
                     for pos, t in enumerate(seg_out)]
            self._rush_show(self.splits_seg_result, "\n".join(lines))
