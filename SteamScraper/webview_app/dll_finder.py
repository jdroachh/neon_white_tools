"""
dll_finder — opt-in Steam DLL locator. Pure functions, no GUI/webview imports.

Call find_neon_white_dll() only in response to a user button press — never on startup.
"""
import os
import re

from logger import get_logger

logger = get_logger(__name__)

_TARGET_DLL = "steam_api64.dll"
_NEON_WHITE_DIR = os.path.join("steamapps", "common", "Neon White")


def read_steam_path() -> str | None:
    """Read HKCU\\Software\\Valve\\Steam\\SteamPath from the Windows registry."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
            return str(value) if value else None
    except Exception:
        return None


def parse_library_folders(vdf_path: str) -> list[str]:
    """Parse Valve's libraryfolders.vdf and return all library root paths."""
    try:
        with open(vdf_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        raw_paths = re.findall(r'"path"\s+"([^"]+)"', text, re.IGNORECASE)
        # VDF escapes backslashes as \\; unescape so os.path works correctly.
        return [p.replace("\\\\", "\\") for p in raw_paths]
    except Exception:
        return []


def search_for_dll(start_dir: str, max_depth: int = 5, max_files: int = 0) -> str | None:
    """Walk start_dir recursively looking for steam_api64.dll.

    max_files=0 means unlimited (safe for known-bounded dirs like a single game folder).
    Use a positive limit only for broad searches over large library roots.
    """
    files_checked = 0
    base_depth = start_dir.rstrip(os.sep).count(os.sep)
    try:
        for root, dirs, files in os.walk(start_dir):
            depth = root.count(os.sep) - base_depth
            if depth >= max_depth:
                dirs.clear()
                continue
            for fname in files:
                if fname.lower() == _TARGET_DLL.lower():
                    return os.path.join(root, fname)
                if max_files:
                    files_checked += 1
                    if files_checked >= max_files:
                        return None
    except Exception:
        pass
    return None


def find_neon_white_dll() -> dict:
    """
    Orchestrate DLL discovery. Returns:
      {found: bool, path: str | None, steps: list[str]}
    Never raises.
    """
    steps: list[str] = []

    # Step 1 — registry
    steam_path = read_steam_path()
    if steam_path:
        steam_path = steam_path.replace("/", os.sep)
        steps.append(f"registry SteamPath={steam_path}")
        logger.debug("find_dll: registry SteamPath=%s", steam_path)
    else:
        steps.append("registry SteamPath: not found (non-Windows or key missing)")
        logger.debug("find_dll: registry key not found")

    # Step 2 — check default library in the steam path itself
    candidate_roots: list[str] = []
    if steam_path:
        candidate_roots.append(steam_path)

        vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf_path):
            extra = parse_library_folders(vdf_path)
            steps.append(f"libraryfolders.vdf found {len(extra)} extra root(s)")
            logger.debug("find_dll: libraryfolders.vdf found %d roots", len(extra))
            candidate_roots.extend(extra)
        else:
            steps.append("libraryfolders.vdf not found, using steam root only")

    # Deduplicate roots (registry and VDF often point at the same path)
    seen: set[str] = set()
    unique_roots: list[str] = []
    for r in candidate_roots:
        key = os.path.normcase(os.path.normpath(r))
        if key not in seen:
            seen.add(key)
            unique_roots.append(r)

    # Step 3a — check exact path steamapps/common/Neon White/steam_api64.dll
    # Step 3b — if the Neon White dir exists but DLL isn't at root, search within it
    #            (DLL may be in a subdirectory, e.g. Neon White_Data/Plugins/x86_64/)
    for root in unique_roots:
        nw_dir = os.path.join(root, _NEON_WHITE_DIR)
        dll_path = os.path.join(nw_dir, _TARGET_DLL)
        if os.path.isfile(dll_path):
            steps.append(f"found at {dll_path}")
            logger.debug("find_dll: found at %s", dll_path)
            return {"found": True, "path": dll_path, "steps": steps}
        elif os.path.isdir(nw_dir):
            steps.append(f"Neon White dir found at {nw_dir}, searching within it")
            logger.debug("find_dll: searching within %s", nw_dir)
            found = search_for_dll(nw_dir, max_depth=6, max_files=0)
            if found:
                steps.append(f"found at {found}")
                logger.debug("find_dll: found at %s", found)
                return {"found": True, "path": found, "steps": steps}
            steps.append(f"not found within {nw_dir}")
        else:
            steps.append(f"Neon White not installed under {root}")
            logger.debug("find_dll: Neon White not installed under %s", root)

    # Step 4 — broad recursive fallback from each library root (last resort, capped)
    for root in unique_roots:
        steps.append(f"broad search under {root} (depth 5, capped)")
        logger.debug("find_dll: broad search under %s", root)
        found = search_for_dll(root, max_depth=5, max_files=1000)
        if found:
            steps.append(f"found at {found} (broad search)")
            logger.debug("find_dll: found at %s (broad search)", found)
            return {"found": True, "path": found, "steps": steps}

    steps.append("DLL not found by any method")
    logger.debug("find_dll: not found")
    return {"found": False, "path": None, "steps": steps}
