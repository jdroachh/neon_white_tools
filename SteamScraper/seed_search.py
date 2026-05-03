"""
seed_search — multiprocessing worker + helpers for the Rush Seed Finder.

Deliberately tiny: only depends on shuffle_lib (and stdlib). Workers spawned
against this module's _seed_search_worker re-import only this file plus
shuffle_lib + ctypes, instead of all 2991 lines of neonwhite_app.py.
"""
from shuffle_lib import _load_c_shuffle, full_shuffle


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
    args: (seed_start, seed_end, num_levels, target_indices_set, depth, result_queue, stop_event)

    Queue messages:
        int                    -> matching seed
        ("progress", count)    -> seeds checked since last report
        None                   -> sentinel: worker finished
    """
    seed_start, seed_end, num_levels, target_set, depth, result_queue, stop_event = args
    # On Windows, spawned children don't run NeonWhiteApp.__init__, so
    # _SHUFFLE_LIB stays None and full_shuffle silently uses the slow Python
    # fallback. Load the DLL here so workers run the native shuffle.
    _load_c_shuffle()

    PROGRESS_BATCH = 200_000
    since_report = 0
    for seed in range(seed_start, seed_end):
        if stop_event.is_set():
            break
        order = full_shuffle(num_levels, seed)
        if target_set.issubset(set(order[:depth])):
            result_queue.put(seed)
        since_report += 1
        if since_report >= PROGRESS_BATCH:
            result_queue.put(("progress", since_report))
            since_report = 0
    if since_report:
        result_queue.put(("progress", since_report))
    result_queue.put(None)  # sentinel — this worker is done
