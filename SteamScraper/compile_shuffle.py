"""
compile_shuffle.py — Compile shuffle.dll for Neon White Tools
Run this once to produce shuffle.dll, then place it in SteamScraper/ alongside shuffle_lib.py

Supports:
  - Visual Studio cl.exe (auto-detected, called directly — no vcvars needed)
  - MinGW gcc (fallback if cl.exe not found)

Usage:
  python compile_shuffle.py
"""

import os
import sys
import ctypes
import subprocess
import tempfile
import glob

C_CODE = r"""
#include <string.h>
#include <stdint.h>
#define MBIG 2147483647LL
#define MAX_LEVELS 128  /* 96 White-rush levels + headroom */
__declspec(dllexport) void full_shuffle(int num_levels, int seed, int* arr) {
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

/* target_mask_lo: bits for indices 0-63; target_mask_hi: bits for indices 64-127.
   Splitting avoids undefined behavior from 1ULL<<N with N>=64 on x86. */
/* Returns count<<32 | stopped_at_seed (packed long long).
   No pointer output arg — eliminates ctypes POINTER-in-stack-args issues on Python 3.14. */
__declspec(dllexport) long long find_seeds_batch(
    int      num_levels,
    int      seed_start,
    int      seed_end,
    uint64_t target_mask_lo,
    uint64_t target_mask_hi,
    int      depth,
    int*     out_seeds,
    int      out_capacity
) {
    int seed, count = 0;
    if (depth > num_levels) depth = num_levels;
    for (seed = seed_start; seed < seed_end; seed++) {
        int SA[56]; int i, k;
        int arr[MAX_LEVELS];
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
        uint64_t seen_lo = 0, seen_hi = 0;
        for (i = 0; i < depth; i++) {
            if (arr[i] < 64) seen_lo |= (1ULL << arr[i]);
            else             seen_hi |= (1ULL << (arr[i] - 64));
        }
        if ((target_mask_lo & seen_lo) == target_mask_lo &&
            (target_mask_hi & seen_hi) == target_mask_hi) {
            out_seeds[count++] = seed;
            if (count == out_capacity)
                return ((long long)count << 32) | (unsigned int)(seed + 1);
        }
    }
    return ((long long)count << 32) | (unsigned int)seed_end;
}
"""

OUTPUT_DLL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shuffle.dll")


def find_cl():
    """Find cl.exe and its MSVC root directory."""
    search_roots = [
        r"C:\Program Files\Microsoft Visual Studio",
        r"C:\Program Files (x86)\Microsoft Visual Studio",
    ]
    for root in search_roots:
        pattern = os.path.join(root, "**", "Hostx64", "x64", "cl.exe")
        matches = glob.glob(pattern, recursive=True)
        if matches:
            cl = matches[0]
            # cl is at: <msvc_root>\bin\Hostx64\x64\cl.exe
            msvc_root = os.path.normpath(
                os.path.join(os.path.dirname(cl), "..", "..", "..")
            )
            return cl, msvc_root
    # Fallback without Hostx64 constraint
    for root in search_roots:
        pattern = os.path.join(root, "**", "cl.exe")
        matches = glob.glob(pattern, recursive=True)
        if matches:
            cl = matches[0]
            msvc_root = os.path.normpath(
                os.path.join(os.path.dirname(cl), "..", "..", "..")
            )
            return cl, msvc_root
    return None, None


def find_windows_sdk():
    """Find the latest Windows SDK ucrt include and lib paths."""
    sdk_roots = [
        r"C:\Program Files (x86)\Windows Kits\10",
        r"C:\Program Files\Windows Kits\10",
    ]
    for sdk_root in sdk_roots:
        inc_root = os.path.join(sdk_root, "Include")
        lib_root = os.path.join(sdk_root, "Lib")
        if not os.path.isdir(inc_root):
            continue
        versions = sorted(
            [v for v in os.listdir(inc_root) if os.path.isdir(os.path.join(inc_root, v))],
            reverse=True
        )
        for ver in versions:
            ucrt_inc = os.path.join(inc_root, ver, "ucrt")
            ucrt_lib = os.path.join(lib_root, ver, "ucrt", "x64")
            um_lib   = os.path.join(lib_root, ver, "um",   "x64")
            if os.path.isdir(ucrt_inc):
                return ucrt_inc, ucrt_lib, um_lib
    return None, None, None


def compile_with_cl(src_path, tmpdir):
    """Compile using cl.exe directly, setting INCLUDE/LIB from known paths."""
    cl, msvc_root = find_cl()
    if not cl:
        return False, "cl.exe not found"

    msvc_inc = os.path.join(msvc_root, "include")
    msvc_lib = os.path.join(msvc_root, "lib", "x64")

    ucrt_inc, ucrt_lib, um_lib = find_windows_sdk()

    include_paths = [msvc_inc]
    lib_paths     = [msvc_lib]
    if ucrt_inc: include_paths.append(ucrt_inc)
    if ucrt_lib: lib_paths.append(ucrt_lib)
    if um_lib:   lib_paths.append(um_lib)

    env            = os.environ.copy()
    env["INCLUDE"] = ";".join(include_paths)
    env["LIB"]     = ";".join(lib_paths)
    env["PATH"]    = os.path.dirname(cl) + os.pathsep + env.get("PATH", "")

    obj_path = os.path.join(tmpdir, "shuffle.obj")

    cmd = [
        cl,
        "/nologo",
        "/O2",
        "/LD",
        src_path,
        "/Fe" + OUTPUT_DLL,
        "/Fo" + obj_path,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=tmpdir,
    )

    if result.returncode == 0 and os.path.exists(OUTPUT_DLL):
        return True, None
    return False, (result.stderr + result.stdout).strip()


def compile_with_gcc(src_path):
    """Fallback: compile using MinGW gcc."""
    try:
        result = subprocess.run(
            ["gcc", "-O3", "-shared", "-o", OUTPUT_DLL, src_path],
            capture_output=True, text=True
        )
        if result.returncode == 0 and os.path.exists(OUTPUT_DLL):
            return True, None
        return False, result.stderr
    except FileNotFoundError:
        return False, "gcc not found on PATH"


def verify_dll():
    """Load the DLL and verify correctness + benchmark speed."""
    try:
        lib = ctypes.CDLL(OUTPUT_DLL)
        lib.full_shuffle.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)
        ]
        lib.full_shuffle.restype = None

        arr = (ctypes.c_int * 96)()
        lib.full_shuffle(96, 58685, arr)
        if arr[0] != 95:
            return False, f"Correctness check failed: expected 95, got {arr[0]}"

        import time
        N = 200_000
        t0 = time.time()
        for s in range(1, N + 1):
            lib.full_shuffle(96, s, arr)
        rate = N / (time.time() - t0)

        # Smoke-test find_seeds_batch: num_levels=8, seeds 0..999, target_mask=0b111 (levels 0,1,2), depth=3
        # Expected: seeds where levels 0,1,2 all appear in first 3 positions.
        lib.find_seeds_batch.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_uint64, ctypes.c_uint64, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.c_int,
        ]
        lib.find_seeds_batch.restype = ctypes.c_longlong

        out_buf  = (ctypes.c_int * 4096)()
        r        = lib.find_seeds_batch(8, 0, 1000, 0b111, 0, 3, out_buf, 4096)
        stopped  = r & 0xFFFFFFFF
        n_found  = (r >> 32) & 0xFFFFFFFF

        # Cross-check with full_shuffle
        expected = []
        arr8 = (ctypes.c_int * 8)()
        for s in range(1000):
            lib.full_shuffle(8, s, arr8)
            if {0, 1, 2}.issubset(arr8[:3]):
                expected.append(s)
        actual = sorted(out_buf[i] for i in range(n_found))
        if actual != expected:
            return False, f"find_seeds_batch smoke check failed: got {actual}, expected {expected}"

        # --- 96-level hi-mask smoke test: straddles the 64-boundary ---
        # Levels 5 and 60 land in target_mask_lo; 70 and 90 land in target_mask_hi.
        # depth=50 gives ~3400 expected matches in 50K seeds, making the
        # buffer-full test below meaningful (depth=10 gives ~3, too sparse).
        target_levels_96 = {5, 60, 70, 90}
        DEPTH_96 = 50
        target_mask_lo_96 = 0
        target_mask_hi_96 = 0
        for lv in target_levels_96:
            if lv < 64:
                target_mask_lo_96 |= (1 << lv)
            else:
                target_mask_hi_96 |= (1 << (lv - 64))

        arr96 = (ctypes.c_int * 96)()
        expected_96 = []
        for s in range(50_000):
            lib.full_shuffle(96, s, arr96)
            if target_levels_96.issubset(arr96[:DEPTH_96]):
                expected_96.append(s)

        out_buf_96 = (ctypes.c_int * 4096)()
        r96        = lib.find_seeds_batch(
            96, 0, 50_000,
            target_mask_lo_96, target_mask_hi_96, DEPTH_96,
            out_buf_96, 4096,
        )
        actual_96 = sorted(out_buf_96[i] for i in range((r96 >> 32) & 0xFFFFFFFF))
        if actual_96 != expected_96:
            missing = [s for s in expected_96 if s not in set(actual_96)]
            extra   = [s for s in actual_96   if s not in set(expected_96)]
            # Diagnose which mask half causes missed seeds: re-check each missing
            # seed and see whether it satisfies lo/hi independently.
            lo_only_fail = hi_only_fail = both_fail = 0
            for s in missing[:200]:
                lib.full_shuffle(96, s, arr96)
                top = set(arr96[:DEPTH_96])
                lo_ok = {lv for lv in target_levels_96 if lv < 64}.issubset(top)
                hi_ok = {lv for lv in target_levels_96 if lv >= 64}.issubset(top)
                if not lo_ok and not hi_ok: both_fail += 1
                elif not lo_ok:             lo_only_fail += 1
                else:                       hi_only_fail += 1
            return False, (
                f"96-level hi-mask smoke failed: {len(missing)} missing, {len(extra)} extra. "
                f"First missing: {missing[:3]}, first extra: {extra[:3]}. "
                f"(lo-only failures: {lo_only_fail}, hi-only: {hi_only_fail}, both: {both_fail})"
            )

        # --- buffer-full path test: out_capacity=4 forces multiple slab calls ---
        SMALL_CAP   = 4
        out_buf_sm  = (ctypes.c_int * SMALL_CAP)()
        accumulated = []
        total_scanned = 0
        cur = 0
        while cur < 50_000:
            rsm     = lib.find_seeds_batch(
                96, cur, 50_000,
                target_mask_lo_96, target_mask_hi_96, DEPTH_96,
                out_buf_sm, SMALL_CAP,
            )
            stopped = rsm & 0xFFFFFFFF
            cnt_sm  = (rsm >> 32) & 0xFFFFFFFF
            total_scanned += stopped - cur
            accumulated.extend(out_buf_sm[i] for i in range(cnt_sm))
            cur = stopped

        if accumulated != expected_96:
            missing_bf = [s for s in expected_96 if s not in set(accumulated)]
            extra_bf   = [s for s in accumulated  if s not in set(expected_96)]
            return False, (
                f"buffer-full path failed: {len(missing_bf)} missing, {len(extra_bf)} extra. "
                f"First missing: {missing_bf[:3]}, first extra: {extra_bf[:3]}"
            )
        if total_scanned != 50_000:
            return False, f"buffer-full coverage wrong: scanned {total_scanned}, expected 50000"

        # --- high-seed cross-check: DLL vs Python fallback ---
        import sys as _sys
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        if _script_dir not in _sys.path:
            _sys.path.insert(0, _script_dir)
        import shuffle_lib as _sl
        _saved_lib = _sl._SHUFFLE_LIB
        _sl._SHUFFLE_LIB = None  # force Python branch for cross-check
        try:
            _high_seeds = [200_000_000, 257_267_304, 500_000_000,
                           1_000_000_000, 1_500_000_000, 2_147_483_647]
            _arr_dll = (ctypes.c_int * 96)()
            for _hs in _high_seeds:
                lib.full_shuffle(96, _hs, _arr_dll)
                _py = _sl.full_shuffle(96, _hs)
                if list(_arr_dll) != _py:
                    return False, (
                        f"high-seed cross-check failed at seed {_hs}: "
                        f"DLL[0:5]={list(_arr_dll)[:5]}, Python[0:5]={_py[:5]}"
                    )
            # crash check: previously-AV-ing seed range must return cleanly
            _out_crash = (ctypes.c_int * 32)()
            lib.find_seeds_batch(96, 257_267_303, 257_267_310, 0, 0, 25, _out_crash, 32)
        finally:
            _sl._SHUFFLE_LIB = _saved_lib

        return True, (
            f"{rate:,.0f} seeds/sec (full_shuffle); "
            f"find_seeds_batch smoke OK ({n_found} matches in 0–999); "
            f"96-level hi-mask OK ({len(expected_96)} matches in 0–49999); "
            f"buffer-full path OK; "
            f"high-seed cross-check OK ({len(_high_seeds)} seeds)"
        )
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 55)
    print("  Neon White Tools — shuffle.dll compiler")
    print("=" * 55)
    print()

    tmpdir   = tempfile.mkdtemp()
    src_path = os.path.join(tmpdir, "shuffle.c")
    with open(src_path, "w") as f:
        f.write(C_CODE)

    print("Looking for Visual Studio cl.exe...", end=" ", flush=True)
    cl, msvc_root = find_cl()
    ok = False

    if cl:
        print(f"found\n  {cl}")
        print(f"  MSVC root: {msvc_root}")
        ucrt_inc, ucrt_lib, um_lib = find_windows_sdk()
        print(f"  Windows SDK ucrt: {ucrt_inc or 'not found'}")
        print("Compiling with cl.exe...", end=" ", flush=True)
        ok, err = compile_with_cl(src_path, tmpdir)
        if not ok:
            print(f"failed\n  {err}\nFalling back to gcc...")
    else:
        print("not found")

    if not ok:
        print("Trying gcc...", end=" ", flush=True)
        ok, err = compile_with_gcc(src_path)

    if not ok:
        print(f"failed\n  {err}")
        print()
        print("To fix:")
        print("  1. Open Visual Studio Installer > Modify > ensure")
        print("     'Desktop development with C++' workload is installed")
        print("  2. Or install MinGW from winlibs.com and add to PATH")
        sys.exit(1)

    print("done")
    print(f"Output: {OUTPUT_DLL}")
    print()

    print("Verifying...", end=" ", flush=True)
    ok, info = verify_dll()
    if ok:
        print(f"OK — {info}")
        print()
        print("shuffle.dll is ready. The app will use it automatically.")
    else:
        print(f"FAILED — {info}")
        sys.exit(1)


if __name__ == "__main__":
    main()
