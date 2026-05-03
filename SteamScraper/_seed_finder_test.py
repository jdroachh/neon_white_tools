"""
Headless test for the Rush Seed Finder.
Reproduces the GUI's seed-search behavior without tkinter or Steam.

After the modularization split, this exercises the slim seed_search +
shuffle_lib modules directly — no neonwhite_app import needed.
"""
import multiprocessing
import time

import shuffle_lib as sl
import seed_search as ss


def test_main_process_dll():
    """Verify shuffle.dll loads in the main process and gives the expected answer."""
    ok = sl._load_c_shuffle()
    print(f"[main] _load_c_shuffle() -> {ok}")
    print(f"[main] _SHUFFLE_LIB is None? {sl._SHUFFLE_LIB is None}")

    order = sl.full_shuffle(96, 58685)
    print(f"[main] full_shuffle(96, 58685)[0] = {order[0]} (expected 60)")

    N = 50_000
    t0 = time.time()
    for s in range(1, N + 1):
        sl.full_shuffle(96, s)
    elapsed = time.time() - t0
    print(f"[main, C lib] {N} shuffles in {elapsed:.2f}s = {N/elapsed:,.0f} seeds/sec")


def test_worker_self_loads_dll():
    """
    Run _seed_search_worker directly in a child process and confirm it
    loads the C lib itself (Bug 1 fix, still in place after split).
    """
    print("\n--- Worker self-loads DLL test ---")
    q = multiprocessing.Queue()
    stop = multiprocessing.Event()
    target_set = set(range(96))  # impossible to fit all 96 in any depth < 96
    args = (1, 500_001, 96, target_set, 5, q, stop)
    t0 = time.time()
    p = multiprocessing.Process(target=ss._seed_search_worker, args=(args,))
    p.start()
    p.join(timeout=60)
    elapsed = time.time() - t0
    if p.is_alive():
        p.terminate()
        print("  [worker] TIMED OUT (would indicate C lib not loaded)")
        return

    progress_msgs = 0
    matches = 0
    sentinel = False
    while not q.empty():
        item = q.get()
        if item is None:
            sentinel = True
        elif isinstance(item, tuple) and item[0] == "progress":
            progress_msgs += 1
        else:
            matches += 1

    rate = 500_000 / elapsed if elapsed > 0 else 0
    print(f"  [worker] 500,000 shuffles in {elapsed:.2f}s = {rate:,.0f} seeds/sec")
    print(f"  [worker] progress messages received: {progress_msgs}")
    print(f"  [worker] sentinel received: {sentinel}")
    print(f"  [worker] matches (expected 0): {matches}")


def test_progress_messages_emitted():
    """The worker should emit ~ (range / PROGRESS_BATCH) progress messages."""
    print("\n--- Progress message cadence test ---")
    q = multiprocessing.Queue()
    stop = multiprocessing.Event()
    args = (1, 1_000_001, 96, set([0, 1, 2]), 5, q, stop)
    p = multiprocessing.Process(target=ss._seed_search_worker, args=(args,))
    p.start()
    p.join(timeout=60)

    progress_total = 0
    progress_msgs = 0
    while not q.empty():
        item = q.get()
        if isinstance(item, tuple) and item[0] == "progress":
            progress_msgs += 1
            progress_total += item[1]

    print(f"  [progress] {progress_msgs} messages, total seeds reported: {progress_total:,}")
    print(f"  [progress] expected ~5 messages of 200k each, total ~ 1,000,000")


def test_expected_match_count():
    """Sanity-check the probability helper."""
    print("\n--- Expected match count helper ---")
    cases = [
        (96, 12, 25),
        (96, 12, 40),
        (96, 5, 20),
        (96, 3, 10),
        (8, 3, 5),
    ]
    for nl, nt, d in cases:
        e = ss._expected_match_count(nl, nt, d)
        flag = "  [WOULD WARN]" if e < 10 else ""
        print(f"  num_levels={nl:>3}  targets={nt:>2}  depth={d:>2}  -> expected ~{e:>12,.2f}{flag}")


def test_subset_check_speedup():
    """
    Micro-benchmark: compare set-based subset check vs. bitmask check using
    the same shuffle outputs. Both must agree on every seed; bitmask should
    be meaningfully faster.
    """
    print("\n--- Subset check: set vs. bitmask benchmark ---")
    sl._load_c_shuffle()
    target_indices = [0, 5, 10, 15, 20, 25, 30, 35]  # 8 targets
    target_set     = set(target_indices)
    target_mask    = sum(1 << i for i in target_indices)
    depth          = 30
    N              = 200_000

    # Pre-generate orders so we benchmark the check, not the shuffle
    orders = [sl.full_shuffle(96, s) for s in range(1, N + 1)]

    # Set-based with redundant outer set() — the ORIGINAL path
    t0 = time.time()
    set_matches = 0
    for order in orders:
        if target_set.issubset(set(order[:depth])):
            set_matches += 1
    set_elapsed = time.time() - t0

    # Set-based, no redundant outer set() — issubset accepts any iterable
    t0 = time.time()
    iter_matches = 0
    for order in orders:
        if target_set.issubset(order[:depth]):
            iter_matches += 1
    iter_elapsed = time.time() - t0

    # Bitmask (the NEW path)
    t0 = time.time()
    mask_matches = 0
    for order in orders:
        m = 0
        for i in range(depth):
            m |= 1 << order[i]
        if (m & target_mask) == target_mask:
            mask_matches += 1
    mask_elapsed = time.time() - t0

    speedup = set_elapsed / mask_elapsed if mask_elapsed > 0 else float("inf")
    agree = "OK" if set_matches == mask_matches else f"MISMATCH ({set_matches} vs {mask_matches})"

    print(f"  set + outer set():  {N:>7,} in {set_elapsed:.3f}s "
          f"({N/set_elapsed:>9,.0f}/sec), {set_matches} matches")
    print(f"  set, iter direct:   {N:>7,} in {iter_elapsed:.3f}s "
          f"({N/iter_elapsed:>9,.0f}/sec), {iter_matches} matches")
    print(f"  bitmask:            {N:>7,} in {mask_elapsed:.3f}s "
          f"({N/mask_elapsed:>9,.0f}/sec), {mask_matches} matches")
    print(f"  bitmask vs original speedup: {speedup:.2f}x   correctness: {agree}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    test_main_process_dll()
    test_worker_self_loads_dll()
    test_progress_messages_emitted()
    test_expected_match_count()
    test_subset_check_speedup()
