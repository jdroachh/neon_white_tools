"""
seed_search — multiprocessing worker + helpers for the Rush Seed Finder.

Deliberately tiny: only depends on shuffle_lib (and stdlib). Workers spawned
against this module's _seed_search_worker re-import only this file plus
shuffle_lib + ctypes, instead of pulling in the full application module.
"""
import ctypes
from shuffle_lib import _load_c_shuffle, find_seeds_batch

SLAB_SIZE        = 250_000
MATCHES_PER_SLAB = 4096


def _expected_match_count(num_levels, num_targets, depth, seed_range=2_147_483_647):
    """
    Expected number of seeds (out of seed_range) where all `num_targets` chosen
    levels land within the first `depth` positions of a uniform random permutation
    of `num_levels` levels. Used to warn users about statistically infeasible searches.
    """
    if num_targets <= 0 or num_targets > depth or num_targets > num_levels:
        return 0.0
    p = 1.0
    for i in range(num_targets):
        p *= (depth - i) / (num_levels - i)
    return p * seed_range


def _seed_search_worker(args):
    """
    Worker function for multiprocessing seed search.
    Runs in a separate process — must be a module-level function (picklable).
    args: (seed_start, seed_end, num_levels, target_set, depth, result_queue, stop_event)

    Queue messages:
        int                    -> matching seed
        ("progress", count)    -> seeds checked since last report
        None                   -> sentinel: worker finished
    """
    seed_start, seed_end, num_levels, target_set, depth, result_queue, stop_event = args
    # The sentinel MUST be delivered no matter how this worker exits, or the
    # manager loop (which counts sentinels to know when all workers are done)
    # waits forever and the UI stays stuck "in progress". A missing/quarantined
    # DLL makes _load_c_shuffle() return False and find_seeds_batch raise; any
    # mid-loop exception is the same hazard. try/finally guarantees the sentinel.
    # (No error channel back to the manager — it only groks ints / ("progress",n)
    # / None — so a failed load just yields a clean "no matches" for this chunk.)
    try:
        if not _load_c_shuffle():
            return

        target_mask_lo = 0
        target_mask_hi = 0
        for idx in target_set:
            if idx < 64:
                target_mask_lo |= (1 << idx)
            else:
                target_mask_hi |= (1 << (idx - 64))

        out_buffer = (ctypes.c_int * MATCHES_PER_SLAB)()

        seed = seed_start
        while seed < seed_end:
            if stop_event.is_set():
                break
            slab_end   = min(seed + SLAB_SIZE, seed_end)
            stopped_at, count = find_seeds_batch(
                num_levels, seed, slab_end,
                target_mask_lo, target_mask_hi, depth,
                out_buffer, MATCHES_PER_SLAB,
            )
            for i in range(count):
                result_queue.put(out_buffer[i])
            result_queue.put(("progress", stopped_at - seed))
            seed = stopped_at
    finally:
        result_queue.put(None)  # sentinel — this worker is done (even on error)
