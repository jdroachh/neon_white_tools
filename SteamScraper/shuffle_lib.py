"""
shuffle_lib — C-accelerated Fisher-Yates shuffle used by the Rush Seed Finder.

Kept deliberately small and import-light: only ctypes + os. This module is
re-imported by every spawned worker process, so adding heavy imports here
will slow per-search startup.
"""
import ctypes
import os
import sys

_MBIG = 2147483647
_SHUFFLE_LIB = None  # populated by _load_c_shuffle()

# Reference C source — actual DLL is built once via compile_shuffle.py.
# Kept here so the algorithm is documented alongside the loader.
_C_SHUFFLE_CODE = r"""
#include <string.h>
#define MBIG 2147483647LL
void full_shuffle(int num_levels, int seed, int* arr) {
    int SA[56]; int i, k;
    memset(SA, 0, sizeof(SA));
    long long absseed = seed >= 0 ? (long long)seed : -(long long)seed;
    long long mj = 161803398LL - absseed;
    SA[55] = (int)mj;
    long long mk = 1;
    for (i = 1; i < 55; i++) {
        int ix = (21 * i) % 55; SA[ix] = (int)mk;
        mk = mj - mk; if (mk < 0) mk += MBIG; mj = SA[ix];
    }
    for (k = 0; k < 4; k++)
        for (i = 1; i < 56; i++) {
            int n = i + 30; if (n >= 55) n -= 55;
            SA[i] = (int)((long long)SA[i] - SA[1 + n]); if (SA[i] < 0) SA[i] += MBIG;
        }
    for (i = 0; i < num_levels; i++) arr[i] = i;
    int ie = 0, ixx = 21;
    for (i = 0; i < num_levels; i++) {
        if (++ie  >= 56) ie  = 1;
        if (++ixx >= 56) ixx = 1;
        long long r = (long long)SA[ie] - (long long)SA[ixx];
        if (r == MBIG) r--;
        if (r < 0) r += MBIG;
        SA[ie] = (int)r;
        int j = (int)((double)r * (1.0 / MBIG) * num_levels);
        int tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
    }
}
"""


def _load_c_shuffle():
    """Load pre-compiled shuffle.dll. No compiler required at runtime."""
    global _SHUFFLE_LIB
    # When frozen, PyInstaller extracts bundled binaries to sys._MEIPASS.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        dll_path = os.path.join(sys._MEIPASS, "shuffle.dll")
    else:
        dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shuffle.dll")
    if not os.path.exists(dll_path):
        return False
    try:
        lib = ctypes.CDLL(dll_path)
        lib.full_shuffle.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)
        ]
        lib.full_shuffle.restype = None
        lib.find_seeds_batch.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_uint64, ctypes.c_uint64, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.c_int,
        ]
        lib.find_seeds_batch.restype = ctypes.c_longlong
        # Quick sanity check
        arr = (ctypes.c_int * 96)()
        lib.full_shuffle(96, 58685, arr)
        if arr[0] != 95:
            return False  # DLL produces wrong results
        # Smoke-test find_seeds_batch: 8 levels, seeds 0–99, target={0,1,2} at depth=3
        out_buf = (ctypes.c_int * 16)()
        r       = lib.find_seeds_batch(8, 0, 100, 0b111, 0, 3, out_buf, 16)
        if (r >> 32) < 0:
            return False
        _SHUFFLE_LIB = lib
        return True
    except Exception:
        return False


def find_seeds_batch(num_levels, seed_start, seed_end, target_mask_lo, target_mask_hi,
                     depth, out_buffer, out_capacity):
    """Run the seed search inside shuffle.dll.
    Returns (stopped_at_seed, match_count)."""
    if _SHUFFLE_LIB is None:
        raise RuntimeError("shuffle.dll not loaded — run compile_shuffle.py")
    r = _SHUFFLE_LIB.find_seeds_batch(
        num_levels, seed_start, seed_end,
        target_mask_lo, target_mask_hi, depth,
        out_buffer, out_capacity,
    )
    return r & 0xFFFFFFFF, (r >> 32) & 0xFFFFFFFF


def full_shuffle(num_levels, seed):
    """
    Fisher-Yates shuffle seeded with C# System.Random algorithm.
    Uses C-compiled shared library if available, falls back to pure Python.
    """
    if _SHUFFLE_LIB is not None:
        arr = (ctypes.c_int * num_levels)(*range(num_levels))
        _SHUFFLE_LIB.full_shuffle(num_levels, seed, arr)
        return list(arr)
    # Pure Python fallback
    SA = [0] * 56
    mj = 161803398 - (seed if seed >= 0 else -seed)
    SA[55] = mj
    mk = 1
    for i in range(1, 55):
        ix = (21 * i) % 55
        SA[ix] = mk
        mk = mj - mk
        if mk < 0: mk += _MBIG
        mj = SA[ix]
    for _ in range(1, 5):
        for i in range(1, 56):
            n = i + 30
            if n >= 55: n -= 55
            SA[i] = ctypes.c_int(SA[i] - SA[1 + n]).value  # match C# int32 wrap
            if SA[i] < 0: SA[i] += _MBIG
    arr = list(range(num_levels))
    ie = 0; ixx = 21
    for i in range(num_levels):
        ie  += 1
        if ie  >= 56: ie  = 1
        ixx += 1
        if ixx >= 56: ixx = 1
        r = SA[ie] - SA[ixx]
        if r == _MBIG: r -= 1
        if r < 0:      r += _MBIG
        SA[ie] = r
        j = int(r * (1.0 / _MBIG) * num_levels)
        arr[i], arr[j] = arr[j], arr[i]
    return arr
