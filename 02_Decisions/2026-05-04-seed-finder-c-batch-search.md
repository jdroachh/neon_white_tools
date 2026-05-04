# Seed Finder — move search loop into C (`find_seeds_batch`)

**Date:** 2026-05-04
**Status:** Designed, not yet implemented
**Owner:** to be picked up by Sonnet (see prompt at the bottom of this doc)

---

## Context

The Seed Finder iterates seeds 0..2,147,483,647 looking for permutations where a chosen subset of levels lands in the first `depth` positions. Today's hot loop (`seed_search.py:44–56`):

```python
for seed in range(seed_start, seed_end):
    if stop_event.is_set(): break
    order = full_shuffle(num_levels, seed)         # ctypes call into shuffle.dll
    if target_set.issubset(order[:depth]):          # Python set op
        result_queue.put(seed)
```

Per seed we currently pay:
- A Python function call into `full_shuffle` (`shuffle_lib.py:75`),
- A fresh `(ctypes.c_int * num_levels)(*range(num_levels))` allocation (`shuffle_lib.py:81`),
- A `list(arr)` round-trip back to Python (`shuffle_lib.py:83`),
- A `target_set.issubset(order[:depth])` Python-level subset op,
- A `multiprocessing.Event.is_set()` IPC poll.

The actual C shuffle runs in a few hundred nanoseconds; everything above it is overhead. `00_Inbox/todo.md` flagged this as item **#4** ("Move the entire seed-search loop into C") with an estimated 5–20× win on top of the existing C shuffle. Items **#1** (slim worker) and **#2** (issubset fix) are already done — workers don't import tkinter, and `target_set.issubset(order[:depth])` already drops the redundant outer `set()`. Item **#5** (buffer reuse) is naturally subsumed once the loop lives in C.

**Goal:** a `find_seeds_batch` C entry point that runs the whole shuffle + subset check in native code, called from Python in slab-sized batches so the existing Stop button, progress bar, and queue plumbing keep working.

## Decision (architecture)

**One new C function added to `shuffle.dll`, two thin Python wrappers, one rewrite of the worker hot loop.** Keep `full_shuffle` exactly as it is — Parser, Splits Updater, Standardize Splits, and Run Timer all call it once per request and don't need batching.

### Subset check encoded as a bitmask

A Rush has ≤16 levels in practice, but a 64-bit mask costs nothing extra and future-proofs the API. Targets and "seen-in-first-N-positions" both become `uint64_t`; the check is one AND-equals.

```c
uint64_t target_mask = 0;
for (int i = 0; i < num_targets; i++) target_mask |= (1ULL << target_indices[i]);
// inside the per-seed body, after running the shuffle into local arr[]:
uint64_t seen_mask = 0;
for (int i = 0; i < depth; i++) seen_mask |= (1ULL << arr[i]);
if ((target_mask & seen_mask) == target_mask) { /* match */ }
```

Replaces a `set.issubset(list_slice)` (~hundreds of ns of Python) with two ORs and one AND.

### Slab-based control flow

Python calls C in slabs (default ~1,000,000 seeds, tunable). Between slabs the worker:
- checks `stop_event.is_set()`,
- emits a single `("progress", slab_size)` message,
- drains any matches the C side wrote into the out-buffer.

Stop responsiveness is bounded by SLAB_SIZE / per-slab-rate ≈ 100–300 ms. Drop the slab to 250k if testing shows a laggier feel.

## Files to modify

### 1. `SteamScraper/compile_shuffle.py`

Add a second exported function in `C_CODE` next to `full_shuffle` (the existing function stays untouched). Signature:

```c
__declspec(dllexport) int find_seeds_batch(
    int       num_levels,
    int       seed_start,
    int       seed_end,         // exclusive
    uint64_t  target_mask,
    int       depth,
    int*      out_seeds,        // caller-owned buffer
    int       out_capacity,     // size of out_seeds in ints
    int*      out_count         // OUT: matches written
);
// returns the seed it stopped at (== seed_end if completed; < seed_end if out_seeds filled)
```

Implementation: copy the shuffle body from the existing `full_shuffle`, write into a fixed-size local `int arr[64]` (no heap), compute `seen_mask` over the first `depth` slots, do the AND-equals check, append to `out_seeds` on match, early-return if `*out_count == out_capacity`. No printf, no allocations.

Add `#include <stdint.h>` at the top of `C_CODE`.

The build path (`compile_with_cl` / `compile_with_gcc` / `verify_dll`) needs no other changes — `cl /LD` and `gcc -shared` already export every `__declspec(dllexport)` symbol. Re-run `python compile_shuffle.py` after editing to rebuild `shuffle.dll`. Optionally extend `verify_dll()` to also benchmark `find_seeds_batch`.

### 2. `SteamScraper/shuffle_lib.py`

In `_load_c_shuffle()` (`shuffle_lib.py:52`), after the existing `lib.full_shuffle.argtypes = ...` block, register the new function:

```python
lib.find_seeds_batch.argtypes = [
    ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_uint64, ctypes.c_int,
    ctypes.POINTER(ctypes.c_int), ctypes.c_int,
    ctypes.POINTER(ctypes.c_int),
]
lib.find_seeds_batch.restype = ctypes.c_int
```

Add a Python wrapper alongside `full_shuffle` (`shuffle_lib.py:75`):

```python
def find_seeds_batch(num_levels, seed_start, seed_end, target_mask, depth,
                    out_buffer, out_count_box):
    """Run the seed search inside shuffle.dll. Returns seed it stopped at."""
    if _SHUFFLE_LIB is None:
        raise RuntimeError("shuffle.dll not loaded — run compile_shuffle.py")
    return _SHUFFLE_LIB.find_seeds_batch(
        num_levels, seed_start, seed_end,
        target_mask, depth,
        out_buffer, len(out_buffer),
        out_count_box,
    )
```

Note: deliberately raise instead of falling back to Python. The pure-Python fallback for the *single-seed* `full_shuffle` is already mostly cosmetic (item #7 in the todo); for a 2.1B-seed search it would be unusable. If `shuffle.dll` is missing, the user is told at app startup via the existing `_init_c_shuffle` path; we just refuse to start the search rather than running for hours in pure Python.

### 3. `SteamScraper/seed_search.py`

Rewrite `_seed_search_worker` (`seed_search.py:25–59`) to call `find_seeds_batch` in slabs. Sketch:

```python
import ctypes
from shuffle_lib import _load_c_shuffle, find_seeds_batch

SLAB_SIZE       = 1_000_000
MATCHES_PER_SLAB = 4096   # generous; matches are rare

def _seed_search_worker(args):
    seed_start, seed_end, num_levels, target_set, depth, result_queue, stop_event = args
    _load_c_shuffle()

    target_mask = 0
    for idx in target_set:
        target_mask |= (1 << idx)

    out_buffer = (ctypes.c_int * MATCHES_PER_SLAB)()
    out_count  = ctypes.c_int(0)

    seed = seed_start
    while seed < seed_end:
        if stop_event.is_set():
            break
        slab_end = min(seed + SLAB_SIZE, seed_end)
        stopped_at = find_seeds_batch(
            num_levels, seed, slab_end,
            target_mask, depth,
            out_buffer, ctypes.byref(out_count),
        )
        for i in range(out_count.value):
            result_queue.put(out_buffer[i])
        result_queue.put(("progress", stopped_at - seed))
        seed = stopped_at

    result_queue.put(None)
```

Caveats baked into the sketch:
- `target_set` arrives as a `set[int]` from `tab_rush_finder.py:_run_finder` (existing pickle path, unchanged) — convert to mask in the worker, not the parent, so the IPC payload stays small.
- `MATCHES_PER_SLAB` of 4096 is comfortably above any realistic match rate; if the C side fills the buffer it returns early and the next iteration picks up where it left off.
- `_expected_match_count` (`seed_search.py:11`) is unchanged — it's purely a UI-level "is this search statistically infeasible" warning.

### 4. `SteamScraper/tab_rush_finder.py` — no edits expected

The UI layer (`_run_finder`, `manager_thread`, `_stop_finder`) talks to the worker only through `result_queue` and `_finder_stop_event`. Both are preserved. Verify after the change that:
- the progress bar still ticks (driven by `("progress", N)` messages),
- the Stop button still cancels within ~slab time,
- found seeds still surface in the Treeview.

## Expected wins

- Per-seed Python overhead → eliminated. The ~3M seeds/sec figure baked into `verify_dll()` (`compile_shuffle.py:191`) is the *isolated* shuffle rate; the current end-to-end search rate is much lower because of the wrapper costs above. Realistic estimate: **5–10× end-to-end speedup** on a typical "find seeds where 4 levels appear in the first 5" query. The exact factor will be visible once the `verify_dll()` benchmark is extended.
- Stop responsiveness: bounded by SLAB_SIZE / per-slab-rate ≈ 100–300 ms. Tunable.
- Memory: fixed `4096 × 4 = 16 KB` per worker process — negligible.

## Out of scope (deliberately)

- **Removing the Python fallback in `full_shuffle`** (todo item #7): cosmetic. Leave it; Parser/Splits use it once per request and the branch cost is meaningless there.
- **`_expected_match_count` improvements:** orthogonal to throughput.
- **Pipelining or rate-limiting Steam API calls** (todo items #3 / Steam API #1–#5): different code path; not Seed Finder.
- **Replacing multiprocessing with threads:** `full_shuffle` releases the GIL only inside the C call; the rest of the loop holds it. Multi-process is the right model and already works.

## Verification

1. **Rebuild and unit-verify the DLL:**
   - `python compile_shuffle.py` — check `verify_dll()` reports the same 200k-seed `full_shuffle` rate as before (regression check that we didn't break the existing function).
   - Add a quick `find_seeds_batch` smoke check to `verify_dll()`: e.g. with `num_levels=8, seed_start=0, seed_end=1000, target_mask=0b00000111, depth=3`, confirm `out_count` matches what the old Python path produces for the same inputs.

2. **End-to-end in the running app:**
   - Launch `python neonwhite_app.py`, open Seed Finder, run a small known-good search (Red rush, 2 targets, depth 4, search depth 100,000) and confirm the same matching seeds appear in the same order as the previous version. The existing `_seed_finder_test.py` harness is the obvious place to lock this in if you want a regression test — re-use it.
   - Run a long-form search (whole 2.1B range, 4 targets, depth 6) and time it end-to-end against the old code on the same inputs. Record the speedup in `00_Inbox/todo.md` so item #4 can be marked done with measured numbers.
   - Click **Stop** mid-search; confirm it halts within ≤500 ms and the UI returns to idle cleanly (no lingering workers — `tab_rush_finder.py:_stop_finder`).

3. **Sanity:**
   - Run Seed Parser (`tab_rush_parser.py`) and Splits Updater on at least one seed each — they still use `full_shuffle`, so any breakage there means the C edit nicked the existing function.

## Critical files

- `SteamScraper/compile_shuffle.py` (C source for the DLL — add `find_seeds_batch`)
- `SteamScraper/shuffle_lib.py` (loader + Python wrapper — register and expose)
- `SteamScraper/seed_search.py` (worker hot loop — rewrite)
- `SteamScraper/shuffle.dll` (rebuilt artifact, not edited by hand)
- `SteamScraper/tab_rush_finder.py` (consumer — no edits expected, just verify)
- `SteamScraper/_seed_finder_test.py` (existing test harness — use for regression check)

---

## Hand-off prompt for Sonnet

Paste the block below into a fresh Sonnet session in this repo. It's self-contained — Sonnet should not need to re-derive design choices.

````
You're picking up an already-designed change in the Neon White Tools repo. The full design lives at `02_Decisions/2026-05-04-seed-finder-c-batch-search.md` — read it once before touching anything; don't redesign it.

**Repo:** E:\Claude-Neon-White-App  (work happens in `SteamScraper/`)
**Branch:** main
**OS:** Windows 11, PowerShell. Use the Bash tool (Git Bash) for `python compile_shuffle.py` etc., or PowerShell — either is fine.

**One-line goal:** Move the Seed Finder's per-seed loop into `shuffle.dll` as a new function `find_seeds_batch`, then call it in slabs from the worker so the search runs ~5–10× faster end-to-end. Stop button, progress bar, and result queue must keep working.

**Implement in this order. Do not skip steps.**

1. **`SteamScraper/compile_shuffle.py`** — add `#include <stdint.h>` to `C_CODE`. Add a second `__declspec(dllexport)` function `find_seeds_batch` next to the existing `full_shuffle`. Signature and semantics are spelled out in §"Files to modify" of the decision doc — copy the shuffle body verbatim, allocate `int arr[64]` on the stack (no malloc), encode targets and seen-positions as `uint64_t` masks, return early when `out_seeds` fills. Do NOT modify `full_shuffle`. Extend `verify_dll()` with a smoke test for the new function (cite: §Verification step 1).

2. **Rebuild the DLL:** run `python compile_shuffle.py` from `SteamScraper/`. Confirm `verify_dll()` reports a non-zero `full_shuffle` rate AND your new smoke check passes. If compilation fails, fix and retry — the existing build path supports both `cl.exe` and `gcc`.

3. **`SteamScraper/shuffle_lib.py`** — in `_load_c_shuffle()`, register `lib.find_seeds_batch` argtypes/restype. Export a `find_seeds_batch(...)` Python wrapper that raises `RuntimeError` if `_SHUFFLE_LIB is None`. Don't add a Python fallback for the batch search — see the design doc for why.

4. **`SteamScraper/seed_search.py`** — rewrite `_seed_search_worker` to call `find_seeds_batch` in slabs of 1,000,000 seeds, with a `MATCHES_PER_SLAB = 4096` ctypes int buffer. Convert the incoming `target_set` to a `uint64` mask inside the worker (NOT in the parent — keeps IPC payload small). Preserve the existing queue protocol exactly: matching seed = bare int, progress = `("progress", N)`, sentinel = `None`. Check `stop_event.is_set()` between slabs.

5. **DO NOT edit `tab_rush_finder.py`.** It only talks to the worker through `result_queue` + `_finder_stop_event`. The design doc explicitly calls this out.

**Verify before reporting done — all three steps from §Verification of the decision doc:**
- Rebuild + DLL smoke check passes.
- Run the app (`python neonwhite_app.py`), open Seed Finder, run the same small known-good search before/after on the same inputs and confirm the matching seeds and their order are unchanged. Use `_seed_finder_test.py` as a starting point if it covers this.
- Click Stop mid-search; confirm halt within ~500 ms and clean UI return.
- Sanity: run Seed Parser and Splits Updater on at least one seed each (they still use `full_shuffle` — this catches any C edit that nicked the existing function).

**Reporting:**
- Brief end-of-turn summary: what changed, measured speedup (or honest "couldn't measure because X"), and any deviations from the design doc with reasoning.
- If you hit something the design doc didn't anticipate, STOP and flag it before continuing — don't quietly redesign.

**Project conventions (from CLAUDE.md):**
- Be terse; lead with the answer or the change.
- Confirm before risky actions on `SteamScraper/` source — but you have approval for THIS task as scoped above.
- After significant work, append a short log to `03_Sessions/YYYY-MM-DD.md`.
- Don't restructure unrelated code.

When the implementation is verified working, also update `00_Inbox/todo.md` — under "Efficiency / performance", strike through item #4 with a "DONE" note and the measured speedup, matching the format already used for items #2 and #8.
````
