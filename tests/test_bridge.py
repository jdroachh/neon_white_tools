"""
Smoke-tests for JsApi. No webview required — exercises the bridge class directly.

Run:  pytest tests/test_bridge.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "SteamScraper"))

from webview_app.bridge import JsApi
from webview_app.models import (
    SeedFindRequest, SeedParseRequest, SeedParseResponse,
    SplitsParseRequest, SplitsParseResponse, SplitLevel,
    TimerCalcRequest, TimerInputRow,
    GlobalExportRequest, LevelSearchRequest, PlayerLookupRequest,
    LeaderboardRow, LogLine,
    Settings,
)


def test_ping():
    api = JsApi()
    result = api.ping()
    assert result["ok"] is True
    assert "version" in result
    assert isinstance(result["version"], str)


# ── Pydantic model round-trip tests ──────────────────────────────────────────

def test_seed_find_request_roundtrip():
    data = {
        "rush_name": "White / Mikey",
        "depth": 10,
        "mode": "Find Multiple",
        "match_count": 3,
        "desired_levels": ["Movement", "Pummel"],
    }
    req = SeedFindRequest(**data)
    assert req.rush_name == "White / Mikey"
    assert req.seed_max == 2_147_483_647
    assert req.model_dump()["desired_levels"] == ["Movement", "Pummel"]


def test_seed_parse_roundtrip():
    req = SeedParseRequest(rush_name="White / Mikey", seed=12345)
    assert req.seed == 12345
    resp = SeedParseResponse(
        rush_name="White / Mikey", seed=12345,
        level_count=96, level_order=["Movement", "Pummel", "Gunner"],
    )
    assert resp.level_count == 96
    assert resp.level_order[0] == "Movement"


def test_splits_parse_response_roundtrip():
    level = SplitLevel(index=0, name="Movement", cumulative="0:35.573", segment="35.573", medal="gold")
    resp = SplitsParseResponse(rush_name="White / Mikey", seed=12345, levels=[level])
    dumped = resp.model_dump()
    assert dumped["levels"][0]["medal"] == "gold"


def test_timer_calc_request_roundtrip():
    req = TimerCalcRequest(
        rush_name="White / Mikey",
        mode="Load by Seed",
        seed=12345,
        rows=[TimerInputRow(cumulative="0:35.573"), TimerInputRow(cumulative="1:13.858")],
    )
    assert req.seed == 12345
    assert len(req.rows) == 2


def test_global_export_request_roundtrip():
    req = GlobalExportRequest(top_n=100, output="both", csv_path="C:/out.csv")
    assert req.top_n == 100


def test_player_lookup_request_roundtrip():
    req = PlayerLookupRequest(
        player_name="speedrunner42",
        mode="Whole Game",
        write_to_sheet=True,
        sheet_id="abc123",
    )
    assert req.write_to_sheet is True


def test_log_line_roundtrip():
    line = LogLine(text="Fetching page 1...", kind="info")
    assert line.cursor is False


def test_settings_defaults():
    s = Settings()
    assert s.theme == "dark"
    assert s.default_rush == "White / Mikey"


def test_settings_roundtrip():
    data = {"theme": "light", "dll_path": "C:/SteamApps/neonwhite/steam_api64.dll"}
    s = Settings(**data)
    assert s.theme == "light"
    assert s.dll_path is not None
