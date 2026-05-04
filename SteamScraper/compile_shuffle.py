"""
compile_shuffle.py — Compile shuffle.dll for Neon White Tools
Run this once to produce shuffle.dll, then place it alongside neonwhite_app.py

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
__declspec(dllexport) void full_shuffle(int num_levels, int seed, int* arr) {
    long long SA[56]; int i, k;
    memset(SA, 0, sizeof(SA));
    long long absseed = seed >= 0 ? (long long)seed : -(long long)seed;
    long long mj = 161803398LL - absseed;
    SA[55] = mj;
    long long mk = 1;
    for (i = 1; i < 55; i++) {
        int ix = (21 * i) % 55; SA[ix] = mk;
        mk = mj - mk; if (mk < 0) mk += MBIG; mj = SA[ix];
    }
    for (k = 0; k < 4; k++)
        for (i = 1; i < 56; i++) {
            int n = i + 30; if (n >= 55) n -= 55;
            SA[i] -= SA[1 + n]; if (SA[i] < 0) SA[i] += MBIG;
        }
    for (i = 0; i < num_levels; i++) arr[i] = i;
    int ie = 0, ixx = 21;
    for (i = 0; i < num_levels; i++) {
        if (++ie  >= 56) ie  = 1;
        if (++ixx >= 56) ixx = 1;
        long long r = SA[ie] - SA[ixx];
        if (r == MBIG) r--;
        if (r < 0) r += MBIG;
        SA[ie] = r;
        int j = (int)(r % (long long)num_levels);
        if (j < 0) j += num_levels;
        int tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
    }
}

/* target_mask_lo: bits for indices 0-63; target_mask_hi: bits for indices 64-127.
   Splitting avoids undefined behavior from 1ULL<<N with N>=64 on x86. */
__declspec(dllexport) int find_seeds_batch(
    int      num_levels,
    int      seed_start,
    int      seed_end,
    uint64_t target_mask_lo,
    uint64_t target_mask_hi,
    int      depth,
    int*     out_seeds,
    int      out_capacity,
    int*     out_count
) {
    int seed;
    for (seed = seed_start; seed < seed_end; seed++) {
        long long SA[56]; int i, k;
        int arr[128];  /* 96 levels max in practice; 128 gives headroom */
        memset(SA, 0, sizeof(SA));
        long long absseed = seed >= 0 ? (long long)seed : -(long long)seed;
        long long mj = 161803398LL - absseed;
        SA[55] = mj;
        long long mk = 1;
        for (i = 1; i < 55; i++) {
            int ix = (21 * i) % 55; SA[ix] = mk;
            mk = mj - mk; if (mk < 0) mk += MBIG; mj = SA[ix];
        }
        for (k = 0; k < 4; k++)
            for (i = 1; i < 56; i++) {
                int n = i + 30; if (n >= 55) n -= 55;
                SA[i] -= SA[1 + n]; if (SA[i] < 0) SA[i] += MBIG;
            }
        for (i = 0; i < num_levels; i++) arr[i] = i;
        int ie = 0, ixx = 21;
        for (i = 0; i < num_levels; i++) {
            if (++ie  >= 56) ie  = 1;
            if (++ixx >= 56) ixx = 1;
            long long r = SA[ie] - SA[ixx];
            if (r == MBIG) r--;
            if (r < 0) r += MBIG;
            SA[ie] = r;
            int j = (int)(r % (long long)num_levels);
            if (j < 0) j += num_levels;
            int tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
        }
        uint64_t seen_lo = 0, seen_hi = 0;
        for (i = 0; i < depth; i++) {
            if (arr[i] < 64) seen_lo |= (1ULL << arr[i]);
            else             seen_hi |= (1ULL << (arr[i] - 64));
        }
        if ((target_mask_lo & seen_lo) == target_mask_lo &&
            (target_mask_hi & seen_hi) == target_mask_hi) {
            out_seeds[*out_count] = seed;
            (*out_count)++;
            if (*out_count == out_capacity) return seed + 1;
        }
    }
    return seed_end;
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
        if arr[0] != 60:
            return False, f"Correctness check failed: expected 60, got {arr[0]}"

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
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.find_seeds_batch.restype = ctypes.c_int

        out_buf   = (ctypes.c_int * 4096)()
        out_count = ctypes.c_int(0)
        stopped   = lib.find_seeds_batch(8, 0, 1000, 0b111, 0, 3, out_buf, 4096, ctypes.byref(out_count))

        # Cross-check with full_shuffle
        expected = []
        arr8 = (ctypes.c_int * 8)()
        for s in range(1000):
            lib.full_shuffle(8, s, arr8)
            if {0, 1, 2}.issubset(arr8[:3]):
                expected.append(s)
        actual = sorted(out_buf[i] for i in range(out_count.value))
        if actual != expected:
            return False, f"find_seeds_batch smoke check failed: got {actual}, expected {expected}"

        return True, f"{rate:,.0f} seeds/sec (full_shuffle); find_seeds_batch smoke OK ({out_count.value} matches in seeds 0–999)"
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
        print("  1. Open Visual Studio Installer → Modify → ensure")
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
