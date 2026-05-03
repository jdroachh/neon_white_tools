# Todo

<!-- Concrete tasks for Claude to pick up. Examples:
- Finish the Rush Timer tab (placeholder at neonwhite_app.py:1695)
- Replace the bare `except Exception: pass` blocks with logging
-->

- May have to archive NeonWhite App versions
- Modularize the code
- Run insights

## Efficiency / performance (ranked by ROI — impact ÷ effort)

1. **Slim worker module** — split `_seed_search_worker`, `full_shuffle`, `_load_c_shuffle`, and the level constants into a small `seed_worker.py` with no tkinter import. Spawn workers against that module instead of `neonwhite_app.py` to drop per-search startup from "import 2991 lines + tkinter × N cores" to "import ~150 lines + ctypes × N cores". Biggest wall-clock win for the smallest change.

2. ~~**Bitmask subset check in the worker hot loop.**~~ **DONE — but not as predicted.** Bitmask in pure Python is ~2× *slower* than the original because CPython's set ops are heavily C-optimized; the OR-fold runs in the Python interpreter. The actual win came from removing a redundant `set()` call: `target_set.issubset(order[:depth])` instead of `target_set.issubset(set(order[:depth]))`. `issubset` accepts any iterable, so the outer `set()` was a wasted per-seed allocation. Measured **1.83× speedup** on the subset check itself (1.29M → 2.35M checks/sec) for one character of code change. End-to-end seed-search speedup is much smaller because the shuffle dominates, but it's free. The real bitmask win still exists — but only if combined with #4 (move the entire loop into C).

3. **Pipeline leaderboard fetches** in `_run_global` (line 2637) and `_run_player` (line 2792). Steam's `DownloadLeaderboardEntries` is async — currently awaited one level at a time. Cap at N concurrent calls and drain results as they come. "Player Lookup across all 96 levels" is the most user-visible win.

4. **Move the entire seed-search loop into C** (extends `compile_shuffle.py` and the DLL ABI). Add `find_seeds(num_levels, seed_start, seed_end, target_mask, depth, out_buffer)` that does the shuffle + subset check inside the DLL, returning matches in a buffer. Python crosses the ctypes boundary once per ~1M-seed slab instead of every seed. Estimated 5–20× speedup on top of the current C shuffle. Do this after #1 and #2.

5. **Reuse the shuffle output buffer** — `full_shuffle` (line 488) re-allocates `(ctypes.c_int * num_levels)` every call and re-initializes it with `*range(num_levels)`, but the C side already writes `arr[i] = i` itself (`compile_shuffle.py:39`). Allocate once per worker, reuse forever. Disappears entirely if #4 is done.

6. **Cheater list lookup** — confirm whether the cheater list is stored as a `set`/`dict` or a `list`. If it's a `list`, every leaderboard entry incurs an O(N) scan. Grep for the lookup site and convert to a `set` if needed. One-line fix, big win on large leaderboards.

7. **Dead-code-path branch in `full_shuffle`** — the pure-Python fallback (lines 491–523) is now unreachable in practice (DLL load is reliable + verified). The `if _SHUFFLE_LIB is not None` check runs every call. Either fail-loudly when the DLL doesn't load (and drop the fallback), or accept the marginal cost. Cosmetic only.

8. **Replace broad `except Exception: pass` blocks** (e.g. lines 532, 557, 660, 911) with at minimum a debug log. Doesn't directly cost perf, but masks slow paths (silent retry loops, swallowed Steam errors) that would otherwise be obvious.

## Before pushing to GitHub
- `git init` and create a sensible `.gitignore` (must exclude: `credentials.json`, `token.json`, `tokenold.json`, `__pycache__/`, `build/`, `.obsidian/workspace.json`, `*.csv` outputs, `shuffle.exp`, `shuffle.lib`)
- Decide what to do with the credential files currently bundled into the EXE (`neonwhite.spec` line 27-28) — they should not land in a public repo
- Document the `neonwhite_config.json` schema (expected keys: `dll_path`, output dirs, sheet IDs) somewhere in `01_Codebase_Map/` or as a README
- Consider an `_archive/` subfolder under `SteamScraper/` to separate live code from legacy scripts and `Neon White App versions/`
