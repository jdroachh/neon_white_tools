"""Rush Tools — Run Timer tab.

Mixin for NeonWhiteApp. Takes cumulative split times and returns segment
times with medal grades.

Depends on `_get_medal` and `_resolve_level_code` on the host class — those
remain in `neonwhite_app.py` because they reference the runtime-mutable
`COMMUNITY_MEDAL_DATA` module global there.
"""
import re
import tkinter as tk

from shuffle_lib import full_shuffle
from rush_data import RUSH_LEVELS


class RushTimerTabMixin:
    def _build_rush_timer(self):
        t = self.t
        f = tk.Frame(self.main_frame, bg=t["bg"])
        self.rush_timer_frame = f
        self._rush_header(f, "Run Timer",
            "Enter cumulative split times per level to get segment times and medal grades.")

        body = tk.Frame(f, bg=t["bg"], padx=24)
        body.pack(fill=tk.BOTH, expand=True)

        # Rush + seed row
        row1 = tk.Frame(body, bg=t["bg"])
        row1.pack(fill=tk.X)
        lc = tk.Frame(row1, bg=t["bg"])
        lc.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        self._rush_field_label(lc, "Rush")
        self.timer_rush_var = tk.StringVar(value="White / Mikey")
        self._rush_dropdown(lc, self.timer_rush_var,
            ["White / Mikey", "Violet", "Red", "Yellow"],
            cmd=self._timer_on_rush_change)

        rc = tk.Frame(row1, bg=t["bg"])
        rc.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._rush_field_label(rc, "Seed Number (optional)")
        self.timer_seed_var = tk.StringVar()
        seed_entry = self._rush_entry(rc, var=self.timer_seed_var, width=20)

        load_btn = tk.Button(rc, text="Load Seed Order",
                             command=self._timer_load_seed,
                             font=("Helvetica", 9),
                             bg=t["bg2"] if hasattr(t, 'bg2') else t["log_bg"],
                             fg=t["fg"], relief="flat", bd=1, cursor="hand2")
        load_btn.pack(anchor="w", pady=(0, 8))

        # Splits input
        self._rush_field_label(body, "Cumulative Split Times (level name: time, one per line)")
        tk.Label(body, text='e.g. "Movement: 17.442" or just "17.442" (in level order)',
                 font=("Helvetica", 9), bg=t["bg"], fg=t["fg2"]).pack(anchor="w", pady=(0, 4))
        self.timer_input = self._rush_text(body, height=8)

        self._rush_btn(body, "Calculate Segments", self._run_timer)

        # Results
        result_cols = tk.Frame(body, bg=t["bg"])
        result_cols.pack(fill=tk.BOTH, expand=True)

        rl = tk.Frame(result_cols, bg=t["bg"])
        rl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._rush_field_label(rl, "Segment Times")
        self.timer_result = self._rush_result_box(rl, height=6)

        rr = tk.Frame(result_cols, bg=t["bg"])
        rr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rush_field_label(rr, "Level Order")
        self.timer_names_result = self._rush_result_box(rr, height=6)

    def _timer_on_rush_change(self):
        pass  # placeholder for future auto-reload

    def _timer_load_seed(self):
        try:
            seed = int(self.timer_seed_var.get().strip())
            if seed < 1 or seed > 2147483647:
                raise ValueError
        except ValueError:
            self._rush_show(self.timer_result, "Invalid seed number.")
            return
        rush_key   = self._rush_key_from_display(self.timer_rush_var.get())
        num_levels = self._rush_key_to_num(self.timer_rush_var.get())
        order      = full_shuffle(num_levels, seed)
        names      = RUSH_LEVELS[rush_key]
        self.timer_input.delete("1.0", tk.END)
        for idx in order:
            self.timer_input.insert(tk.END, f"{names[idx]}: \n")

    def _run_timer(self):
        raw_lines = [l for l in self.timer_input.get("1.0", tk.END).strip().splitlines() if l.strip()]
        if not raw_lines:
            self._rush_show(self.timer_result, "Please enter at least one split time.")
            return

        cumulative = []
        level_names = []
        errors = []

        for i, line in enumerate(raw_lines):
            if ":" in line and not line.strip().startswith(("0:", "1:", "2:", "3:")):
                parts = line.split(":", 1)
                name_part = parts[0].strip()
                time_part = parts[1].strip() if len(parts) > 1 else ""
            else:
                name_part = f"Level {i+1}"
                time_part = line.strip()

            t_val = self._parse_time_to_secs(time_part)
            if t_val is None:
                errors.append(f"Row {i+1}: invalid time '{time_part}'")
                continue
            if cumulative and t_val <= cumulative[-1]:
                errors.append(f"Row {i+1} ({name_part}): time must be greater than previous ({self._format_secs(cumulative[-1])})")
                continue
            cumulative.append(t_val)
            level_names.append(name_part)

        if errors:
            self._rush_show(self.timer_result, "\n".join(errors))
            return

        segments = [cumulative[0]] + [cumulative[i] - cumulative[i-1] for i in range(1, len(cumulative))]
        rush_key = self._rush_key_from_display(self.timer_rush_var.get())

        seg_lines  = []
        name_lines = []
        for i, (seg, name) in enumerate(zip(segments, level_names)):
            medal = self._get_medal(name, seg, rush_key)
            seg_lines.append(f"{self._format_secs(seg):<14} {medal}")
            name_lines.append(name)

        self._rush_show(self.timer_result,  "\n".join(seg_lines))
        self._rush_show(self.timer_names_result, "\n".join(name_lines))

    def _parse_time_to_secs(self, raw):
        s = (raw or "").strip()
        m = re.match(r'^(\d+):(\d{1,2})(?:\.(\d+))?$', s)
        if m:
            return int(m.group(1))*60 + int(m.group(2)) + (float("0."+m.group(3)) if m.group(3) else 0)
        m2 = re.match(r'^(\d+)(?:\.(\d+))?$', s)
        if m2:
            return int(m2.group(1)) + (float("0."+m2.group(2)) if m2.group(2) else 0)
        return None

    def _format_secs(self, secs):
        if secs < 60:
            return f"{secs:.3f}"
        mins = int(secs // 60)
        s = secs - mins * 60
        return f"{mins}:{s:06.3f}"
