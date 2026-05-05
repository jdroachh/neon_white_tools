# Decision: Shuffle output mapping — `Random.Next(N)` multiply formula

**Date:** 2026-05-04

## What was decided

The level-shuffle output mapping is `.NET Random.Next(maxValue)` semantics:

```
j = int(r * (1.0 / MBIG) * N)
```

where `r` is the raw Lagged Fibonacci output and `MBIG = 2147483647`.

The RNG (System.Random Lagged Fibonacci) and shuffle structure (naive forward, `i = 0..N-1, swap arr[i] ↔ arr[j]`) remain unchanged from prior code.

## Why

An empirical probe (`_seed_algo_probe.py`) tested 16 combinations of RNG × output-mode × shuffle variant against 5 in-game ground-truth pairs for Red rush:

| seed   | in-game order (indices into RUSH_LEVELS["red"]) |
|--------|--------------------------------------------------|
| 54304  | [4, 6, 3, 1, 5, 2, 0, 7]                        |
| 5189   | [3, 5, 6, 4, 7, 0, 1, 2]                        |
| 2222   | [4, 2, 5, 3, 1, 7, 0, 6]                        |
| 4444   | [1, 5, 3, 2, 4, 6, 0, 7]                        |
| 123456 | [0, 4, 3, 7, 6, 1, 2, 5]                        |

Exactly one combination matched all pairs: **DotNetRandom × next_int × A_naive_fwd**.

The prior code used `j = r % N` (modulo). This produces a different value than the multiply form because MBIG ≈ 2.1×10⁹ is not a power of two — modulo introduces a slight bias toward low indices, but more importantly it produces systematically wrong values (not just biased ones) for the game's actual output. The game uses Unity/Mono .NET, and `Random.Next(maxValue)` is defined as `(int)(Sample() * maxValue)` where `Sample() = InternalSample() / MBIG`.

## Consequences

- `compile_shuffle.py`: both `full_shuffle` and `find_seeds_batch` use the multiply formula. The `verify_dll()` reference value for seed 58685 (96 levels, arr[0]) is now 95.
- `shuffle_lib.py`: Python fallback uses the same formula. `_load_c_shuffle()` sanity check updated to 95.
- `_seed_ground_truth.py` + `_seed_algo_probe.py` are new files in `SteamScraper/` for future regression and re-probing if algorithm questions arise again.
- All 5 Rush caller tabs (Seed Parser, Splits Updater, Standardize Splits, Seed Finder, Timer) now produce correct orderings for all tested seeds.
- The `find_seeds_batch` bitmask subset check is unaffected — it only tests set membership, not order.
- Previously-saved seed-search outputs (which seeds match a target subset) are now invalid, since the shuffle result changes for every seed. The user opted out of invalidation tooling; users will need to re-run searches.
