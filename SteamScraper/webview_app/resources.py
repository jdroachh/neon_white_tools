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
from urllib.request import urlopen, Request

from logger import get_logger

logger = get_logger(__name__)


# TODO(M4): replace placeholder with the real Ghosts sheet ID once it exists.
_GHOSTS_SHEET_ID = "REPLACE_ME_GHOSTS_SHEET_ID"
_GHOSTS_TAB      = "Ghosts"

# Route Videos: wide-format "Backend" tab with header
#   Mission, Stage, Emerald, Title, Alternate, Title, Amethyst, Title, Alternate, Title, Sapphire, Title, Alternate, Title
# Each medal block holds 4 cells: [primary_url, primary_title, alt_url, alt_title].
_VIDEOS_SHEET_ID = "1vd3aX5fz8FWKnIwj5VHibOiHkXv46kGHvvGzXdUEKik"
_VIDEOS_TAB      = "Backend"

_TIMEOUT_S = 8

_VALID_MEDALS = {"emerald", "amethyst", "sapphire"}

# level (lowercase) -> medal (lowercase) -> [row dicts]
_GHOSTS: dict[str, dict[str, list[dict]]] = {}
_VIDEOS: dict[str, dict[str, list[dict]]] = {}

_STATUS = {
    "ghosts_loaded": False,
    "videos_loaded": False,
    "error": None,
}


def _csv_url(sheet_id: str, tab: str) -> str:
    return (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
            f"/gviz/tq?tqx=out:csv&sheet={tab}")


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


def _fetch_resources_bg() -> None:
    global _GHOSTS, _VIDEOS
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


def get_status() -> dict:
    return dict(_STATUS)
