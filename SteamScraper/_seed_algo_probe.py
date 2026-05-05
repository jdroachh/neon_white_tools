"""
_seed_algo_probe.py — Identify which RNG x output-mode x shuffle variant matches
the game's level ordering. Pure Python; no DLL.

Run:  python _seed_algo_probe.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _seed_ground_truth import GROUND_TRUTH

_MBIG = 2_147_483_647

# ── RNGs ─────────────────────────────────────────────────────────────────────

class DotNetRandom:
    """Exact port of .NET System.Random (Lagged Fibonacci Generator)."""
    def __init__(self, seed):
        SA = [0] * 56
        absseed = abs(seed)
        mj = 161803398 - absseed
        SA[55] = mj
        mk = 1
        for i in range(1, 55):
            ix = (21 * i) % 55
            SA[ix] = mk
            mk = mj - mk
            if mk < 0: mk += _MBIG
            mj = SA[ix]
        for _ in range(4):
            for i in range(1, 56):
                n = i + 30
                if n >= 55: n -= 55
                SA[i] -= SA[1 + n]
                if SA[i] < 0: SA[i] += _MBIG
        self._SA = SA
        self._ie = 0
        self._ixx = 21

    def _raw(self):
        self._ie += 1
        if self._ie >= 56: self._ie = 1
        self._ixx += 1
        if self._ixx >= 56: self._ixx = 1
        r = self._SA[self._ie] - self._SA[self._ixx]
        if r == _MBIG: r -= 1
        if r < 0: r += _MBIG
        self._SA[self._ie] = r
        return r

    def raw_mod(self, n):
        return self._raw() % n

    def next_int(self, n):
        """True .NET Random.Next(maxValue): int(r * (1.0/MBIG) * n)."""
        return int(self._raw() * (1.0 / _MBIG) * n)


class UnityXorshift128:
    """Marsaglia xorshift128 — standard Unity internal RNG (speculative)."""
    def __init__(self, seed):
        self._x = seed if seed != 0 else 1
        self._y = 362436069
        self._z = 521288629
        self._w = 88675123

    def _next(self):
        t = self._x ^ ((self._x << 11) & 0xFFFFFFFF)
        self._x = self._y
        self._y = self._z
        self._z = self._w
        self._w = (self._w ^ (self._w >> 19)) ^ (t ^ (t >> 8))
        return self._w & 0x7FFFFFFF

    def raw_mod(self, n):
        return self._next() % n

    def next_int(self, n):
        return int(self._next() * (1.0 / 0x7FFFFFFF) * n)


# ── Shuffle variants ──────────────────────────────────────────────────────────

def shuffle_A_naive_fwd(rng_fn, n):
    """Current impl: for i in 0..n-1, j = rng(n), swap(arr[i], arr[j])."""
    arr = list(range(n))
    for i in range(n):
        j = rng_fn(n)
        arr[i], arr[j] = arr[j], arr[i]
    return arr

def shuffle_B_durstenfeld_bwd(rng_fn, n):
    """Fisher-Yates backward: for i in n-1..1, j = rng(i+1), swap(arr[i], arr[j])."""
    arr = list(range(n))
    for i in range(n - 1, 0, -1):
        j = rng_fn(i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return arr

def shuffle_C_durstenfeld_fwd(rng_fn, n):
    """Fisher-Yates forward: for i in 0..n-2, j = i + rng(n-i), swap(arr[i], arr[j])."""
    arr = list(range(n))
    for i in range(n - 1):
        j = i + rng_fn(n - i)
        arr[i], arr[j] = arr[j], arr[i]
    return arr

def shuffle_D_linq_orderby(rng_fn, n):
    """LINQ OrderBy pattern: assign random key to each index, stable-sort by key."""
    keys = [rng_fn(0x7FFFFFFF) for _ in range(n)]
    return sorted(range(n), key=lambda i: keys[i])


# ── Probe ─────────────────────────────────────────────────────────────────────

SHUFFLES = [
    (shuffle_A_naive_fwd,      "A_naive_fwd"),
    (shuffle_B_durstenfeld_bwd,"B_durstenfeld_bwd"),
    (shuffle_C_durstenfeld_fwd,"C_durstenfeld_fwd"),
    (shuffle_D_linq_orderby,   "D_linq_orderby"),
]

RNGS = [
    (DotNetRandom,    "DotNetRandom"),
    (UnityXorshift128,"UnityXorshift128"),
]

MODES = ["raw_mod", "next_int"]


def run_combo(rng_cls, mode, shuffle_fn, seed, n):
    rng = rng_cls(seed)
    fn = getattr(rng, mode)
    return shuffle_fn(fn, n)


def main():
    combos = [
        (rng_cls, rng_name, mode, shuf_fn, shuf_name)
        for rng_cls, rng_name in RNGS
        for mode in MODES
        for shuf_fn, shuf_name in SHUFFLES
    ]

    print(f"Probing {len(combos)} combinations against {len(GROUND_TRUTH)} ground-truth pairs\n")
    print(f"{'RNG':<20} {'Mode':<10} {'Shuffle':<24} Result")
    print("-" * 72)

    winners = []
    for rng_cls, rng_name, mode, shuf_fn, shuf_name in combos:
        all_pass = True
        first_fail = None
        for rush_key, seed, expected in GROUND_TRUTH:
            n = len(expected)
            got = run_combo(rng_cls, mode, shuf_fn, seed, n)
            if got != expected:
                all_pass = False
                first_fail = (seed, expected, got)
                break
        if all_pass:
            status = "PASS ***"
            winners.append((rng_name, mode, shuf_name))
        else:
            status = f"fail (seed {first_fail[0]}: got {first_fail[2]}, want {first_fail[1]})"
        print(f"{rng_name:<20} {mode:<10} {shuf_name:<24} {status}")

    print()
    if len(winners) == 1:
        rng_n, mode_n, shuf_n = winners[0]
        print(f"WINNER: {rng_n} × {mode_n} × {shuf_n}")
        print("Next step: reimplement this combo in compile_shuffle.py and shuffle_lib.py")
    elif len(winners) == 0:
        print("NO WINNER — no combination matched all ground-truth pairs.")
        print("Possible causes: wrong seed values, different Unity RNG variant, or hash on seed input.")
        print("Try collecting violet/yellow seeds to cross-check.")
    else:
        print(f"AMBIGUOUS — {len(winners)} combinations matched all pairs:")
        for w in winners:
            print(f"  {w}")
        print("Collect more ground-truth pairs (different rush types) to disambiguate.")


if __name__ == "__main__":
    main()
