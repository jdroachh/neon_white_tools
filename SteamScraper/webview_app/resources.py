"""
resources — Ghost-replay and route-video index, sourced from two
public-published Google Sheets owned by the project maintainer.

Both sheets are read anonymously via the GViz CSV endpoint
(https://docs.google.com/spreadsheets/d/<ID>/gviz/tq?tqx=out:csv&sheet=<TAB>),
so no API key, OAuth, or `credentials.json` is required end-side.

Caches are populated in a daemon thread at app launch and never refreshed
again — restart the app to repull. Mirrors the posture of the cheater-list
and community-medal fetches.

Schemas (sheet column headers, lowercase, case-insensitive on read):
    Ghosts:        level, medal, player, time, drive_url
    RouteVideos:   level, medal, title, youtube_url

`level` holds the display name from rush_data.LEVELS (e.g. "Movement",
"Pummel"), matching what the frontend's stage picker passes back.
`medal` is one of: Emerald, Amethyst, Sapphire (case-insensitive on read).
"""
import csv
import io
import threading
from urllib.parse import quote
from urllib.request import urlopen, Request

from logger import get_logger

logger = get_logger(__name__)


_GHOSTS_SHEET_ID = "1FXr-2Rs4RgPF6Oo2BVz-_UQXf_3PPa8nCGstdIl12q8"
_GHOSTS_TAB      = "Ghosts"

# Route Videos: wide-format "Backend" tab with header
#   Mission, Stage, Emerald, Title, Alternate, Title, Amethyst, Title, Alternate, Title, Sapphire, Title, Alternate, Title
# Each medal block holds 4 cells: [primary_url, primary_title, alt_url, alt_title].
_VIDEOS_SHEET_ID = "1vd3aX5fz8FWKnIwj5VHibOiHkXv46kGHvvGzXdUEKik"
_VIDEOS_TAB      = "Backend"

# World Record VODs: community WR sheet, "WR Import" tab.
# Row 1 = banner, row 2 = column headers.  Rows 3-123 are 121 data rows in
# canonical rush_data.LEVELS order.  Column block offsets: PC=2, Switch=10, PS=18.
# Each block is 8 cols: Runner Name | Run Time | Run Time Formatted | Run Date |
#                        Video Link | Video Title | Runner Comment | True Link
_WR_SHEET_ID = "1rG5WNRp4XBGxImwF4c0cj5oYbdIC4yMTpx45BU3cOLU"
_WR_TAB      = "WR Import"

_TIMEOUT_S = 8

_VALID_MEDALS = {"emerald", "amethyst", "sapphire"}

# level (lowercase) -> medal (lowercase) -> [row dicts]
_GHOSTS: dict[str, dict[str, list[dict]]] = {}
_VIDEOS: dict[str, dict[str, list[dict]]] = {}
# level (lowercase) -> platform (lowercase) -> row dict  (single WR per platform)
_WRS: dict[str, dict[str, dict]] = {}

_STATUS = {
    "ghosts_loaded": False,
    "videos_loaded": False,
    "wrs_loaded":    False,
    "error": None,
}


def _csv_url(sheet_id: str, tab: str) -> str:
    return (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
            f"/gviz/tq?tqx=out:csv&sheet={quote(tab)}")


def _fetch_csv_dict(url: str) -> list[dict]:
    """Fetch + parse a published-Sheet CSV with unique column headers."""
    req = Request(url, headers={"User-Agent": "NeonWhiteTools/2.0"})
    with urlopen(req, timeout=_TIMEOUT_S) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in row.items()})
    return rows


def _fetch_csv_rows(url: str) -> list[list[str]]:
    """Fetch + parse a published-Sheet CSV positionally (handles duplicate headers)."""
    req = Request(url, headers={"User-Agent": "NeonWhiteTools/2.0"})
    with urlopen(req, timeout=_TIMEOUT_S) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    return [[(c or "").strip() for c in row]
            for row in csv.reader(io.StringIO(text))]


def _index_ghosts(rows: list[dict]) -> dict[str, dict[str, list[dict]]]:
    out: dict[str, dict[str, list[dict]]] = {}
    dropped = 0
    for r in rows:
        level = r.get("level", "")
        medal = r.get("medal", "").lower()
        url = r.get("drive_url", "")
        if not level or medal not in _VALID_MEDALS or not url:
            dropped += 1
            continue
        out.setdefault(level.lower(), {}).setdefault(medal, []).append({
            "level":     level,
            "medal":     medal.capitalize(),
            "player":    r.get("player", ""),
            "time":      r.get("time", ""),
            "drive_url": url,
        })
    if dropped:
        logger.warning("Ghosts sheet: %d malformed row(s) dropped", dropped)
    return out


def _index_videos(rows: list[list[str]]) -> dict[str, dict[str, list[dict]]]:
    """Parse the wide-format Backend tab into a level→medal→videos index.

    Header row defines column anchors. For each medal in {Emerald, Amethyst,
    Sapphire}, the four cells starting at that anchor are: primary_url,
    primary_title, alt_url, alt_title.
    """
    out: dict[str, dict[str, list[dict]]] = {}
    if not rows:
        logger.warning("Videos sheet: empty")
        return out

    header = [c.lower() for c in rows[0]]
    anchors = {}
    for medal in _VALID_MEDALS:
        try:
            anchors[medal] = header.index(medal)
        except ValueError:
            logger.warning("Videos sheet: medal column %r missing from header", medal)
            return out

    stage_col = header.index("stage") if "stage" in header else 1
    skipped = 0

    for row in rows[1:]:
        # Pad row to length so indexing never throws.
        row = row + [""] * max(0, max(anchors.values()) + 4 - len(row))
        stage = row[stage_col].strip()
        if not stage:
            continue

        for medal, idx in anchors.items():
            for variant, url_off, title_off in (("Primary", 0, 1), ("Alternate", 2, 3)):
                url = row[idx + url_off].strip()
                title = row[idx + title_off].strip()
                if not url:
                    continue
                if not (url.startswith("https://www.youtube.com/")
                        or url.startswith("https://youtube.com/")
                        or url.startswith("https://youtu.be/")):
                    skipped += 1
                    continue
                # Primary "title" is usually a redundant repeat of the stage
                # name; fall back to a synthetic label in that case.
                if not title or title.lower() == stage.lower():
                    title = (f"{stage} {medal.capitalize()}" if variant == "Primary"
                             else f"{medal.capitalize()} Alternate")
                out.setdefault(stage.lower(), {}).setdefault(medal, []).append({
                    "level":       stage,
                    "medal":       medal.capitalize(),
                    "title":       title,
                    "youtube_url": url,
                })
    if skipped:
        logger.warning("Videos sheet: %d non-YouTube URL(s) skipped", skipped)
    return out


def _index_wrs(rows: list[list[str]]) -> dict[str, dict[str, dict]]:
    """Parse the WR Import tab into a level→platform→row dict.

    Raises ValueError if the row count or canary checks fail so the caller
    can leave wrs_loaded=False and show the graceful unavailable state.
    """
    from rush_data import LEVELS  # local import — avoids circular at module load

    data_rows = rows[1:]  # drop column-header row (GViz omits the banner row)
    if len(data_rows) != len(LEVELS):
        raise ValueError(
            f"expected {len(LEVELS)} data rows, got {len(data_rows)}"
        )

    # PC Video Title is at col 2+5=7; verify three canary rows by keyword.
    for idx, keyword in ((0, "Movement"), (95, "Sacrifice"), (120, "Rocket")):
        row = data_rows[idx]
        pc_title = row[7] if len(row) > 7 else ""
        if keyword.lower() not in pc_title.lower():
            raise ValueError(
                f"canary mismatch at data row {idx}: expected {keyword!r} in PC title {pc_title!r}"
            )

    out: dict[str, dict[str, dict]] = {}
    skipped = 0
    for i, row in enumerate(data_rows):
        level_name = LEVELS[i][0]
        key = level_name.lower()
        out[key] = {}
        for platform, offset in (("pc", 2), ("switch", 10), ("playstation", 18)):
            if len(row) < offset + 8:
                row = list(row) + [""] * (offset + 8 - len(row))
            youtube_url = row[offset + 4].strip()
            if not youtube_url:
                continue
            if not (youtube_url.startswith("https://www.youtube.com/")
                    or youtube_url.startswith("https://youtube.com/")
                    or youtube_url.startswith("https://youtu.be/")):
                skipped += 1
                logger.warning("WR sheet: non-YouTube URL for %s/%s skipped", level_name, platform)
                continue
            out[key][platform] = {
                "level":          level_name,
                "platform":       platform,
                "player":         row[offset + 0].strip(),
                "time_formatted": row[offset + 2].strip(),
                "date":           row[offset + 3].strip(),
                "youtube_url":    youtube_url,
                "title":          row[offset + 5].strip(),
            }

    if skipped:
        logger.warning("WR sheet: %d non-YouTube URL(s) skipped", skipped)
    return out


def _fetch_resources_bg() -> None:
    global _GHOSTS, _VIDEOS, _WRS
    try:
        ghost_rows = _fetch_csv_dict(_csv_url(_GHOSTS_SHEET_ID, _GHOSTS_TAB))
        _GHOSTS = _index_ghosts(ghost_rows)
        _STATUS["ghosts_loaded"] = True
        logger.info("Ghosts loaded: %d stages indexed", len(_GHOSTS))
    except Exception as e:
        _STATUS["error"] = f"ghosts: {e}"
        logger.info("Could not load Ghosts sheet: %s", e)

    try:
        video_rows = _fetch_csv_rows(_csv_url(_VIDEOS_SHEET_ID, _VIDEOS_TAB))
        _VIDEOS = _index_videos(video_rows)
        _STATUS["videos_loaded"] = True
        total = sum(len(by_medal) for by_medal in _VIDEOS.values())
        logger.info("Videos loaded: %d stages, %d medal-groups indexed", len(_VIDEOS), total)
    except Exception as e:
        prev = _STATUS["error"]
        _STATUS["error"] = (prev + "; " if prev else "") + f"videos: {e}"
        logger.info("Could not load Videos sheet: %s", e)

    try:
        wr_rows = _fetch_csv_rows(_csv_url(_WR_SHEET_ID, _WR_TAB))
        _WRS = _index_wrs(wr_rows)
        _STATUS["wrs_loaded"] = True
        total = sum(len(p) for p in _WRS.values())
        logger.info("WRs loaded: %d rows indexed, %d platform entries", len(_WRS), total)
    except Exception as e:
        prev = _STATUS["error"]
        _STATUS["error"] = (prev + "; " if prev else "") + f"wrs: {e}"
        logger.info("Could not load WR sheet: %s", e)


def start_background_fetch() -> None:
    """Spawn the one-shot fetch thread. Idempotent across calls."""
    if getattr(start_background_fetch, "_started", False):
        return
    start_background_fetch._started = True  # type: ignore[attr-defined]
    threading.Thread(target=_fetch_resources_bg, daemon=True).start()


def get_ghosts_for(level: str, medal: str) -> list[dict]:
    return list(_GHOSTS.get(level.lower(), {}).get(medal.lower(), []))


def get_videos_for(level: str, medal: str) -> list[dict]:
    return list(_VIDEOS.get(level.lower(), {}).get(medal.lower(), []))


def get_wr_for(level: str, platform: str) -> dict | None:
    return _WRS.get(level.lower(), {}).get(platform.lower())


def get_status() -> dict:
    return dict(_STATUS)
