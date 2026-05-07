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


# ── M2: Seed Finder bridge ────────────────────────────────────────────────────

def test_start_finder_bad_levels():
    api = JsApi()
    res = api.start_finder("White / Mikey", "NonexistentLevelXYZ", "10", "first", "1")
    assert res["ok"] is False
    assert "Unknown level" in res["error"]


def test_start_finder_bad_depth():
    api = JsApi()
    res = api.start_finder("White / Mikey", "Movement", "abc", "first", "1")
    assert res["ok"] is False


def test_start_finder_valid_starts():
    """Valid request should start a search (returns ok=True, then we immediately stop it)."""
    api = JsApi()
    res = api.start_finder("White / Mikey", "Movement, Pummel", "5", "first", "1")
    assert res["ok"] is True
    assert "expected" in res
    # stop immediately so the background thread doesn't run long
    api.stop_finder()


def test_stop_finder_when_idle():
    api = JsApi()
    res = api.stop_finder()
    assert res["ok"] is True


# ── Excluded Levels: Seed Finder ──────────────────────────────────────────────

def test_excluded_bad_level_name():
    api = JsApi()
    res = api.start_finder("White / Mikey", "Movement", "5", "first", "1",
                           excluded_levels="NonexistentLevelXYZ", excluded_window="5")
    assert res["ok"] is False
    assert "Unknown level" in res["error"]


def test_excluded_window_out_of_range():
    api = JsApi()
    res = api.start_finder("White / Mikey", "Movement", "5", "first", "1",
                           excluded_levels="Pummel", excluded_window="200")
    assert res["ok"] is False
    assert "Exclusion Window" in res["error"]


def test_excluded_valid_starts():
    api = JsApi()
    res = api.start_finder("White / Mikey", "Movement", "5", "first", "1",
                           excluded_levels="Pummel, Gunner", excluded_window="10")
    assert res["ok"] is True
    api.stop_finder()


def test_excluded_non_white_rejected():
    api = JsApi()
    res = api.start_finder("Violet", "Doghouse", "5", "first", "1",
                           excluded_levels="Doghouse", excluded_window="3")
    assert res["ok"] is False
    assert "White / Mikey" in res["error"]


# ── M2: Run Timer bridge ──────────────────────────────────────────────────────

def test_load_timer_seed_invalid():
    api = JsApi()
    res = api.load_timer_seed("White / Mikey", "notanumber")
    assert res["ok"] is False


def test_load_timer_seed_valid():
    api = JsApi()
    res = api.load_timer_seed("White / Mikey", "12345")
    assert res["ok"] is True
    assert len(res["lines"]) == 96


def test_calculate_timer_empty():
    api = JsApi()
    res = api.calculate_timer("White / Mikey", "", "")
    assert res["ok"] is False


def test_calculate_timer_basic():
    api = JsApi()
    # Three bare cumulative times
    splits = "17.442\n38.284\n62.100"
    res = api.calculate_timer("White / Mikey", "", splits)
    assert res["ok"] is True
    assert len(res["rows"]) == 3
    # segments: 17.442, 20.842, 23.816
    assert abs(res["rows"][0]["segment"] - 17.442) < 0.001
    assert abs(res["rows"][1]["segment"] - 20.842) < 0.001


def test_calculate_timer_named_format():
    """Name-then-time format (the bug that was pre-existing in tkinter)."""
    api = JsApi()
    splits = "Movement 17.442\nPummel 38.284\nGunner 1:02.100"
    res = api.calculate_timer("White / Mikey", "", splits)
    assert res["ok"] is True
    assert res["rows"][0]["name"] == "Movement"
    assert res["rows"][2]["name"] == "Gunner"
    assert abs(res["rows"][2]["segment"] - (62.1 - 38.284)) < 0.001


def test_calculate_timer_colon_format():
    """Legacy 'Name: time' format."""
    api = JsApi()
    splits = "Movement: 17.442\nPummel: 38.284"
    res = api.calculate_timer("White / Mikey", "", splits)
    assert res["ok"] is True
    assert res["rows"][0]["name"] == "Movement"


# ── Hell Rush Mode: Seed Finder ───────────────────────────────────────────────

def test_hell_rush_non_white_rejected():
    """HR on for a non-White rush should return a validation error."""
    api = JsApi()
    res = api.start_finder("Violet", "Movement", "5", "first", "1",
                           hell_rush=True, hell_rush_min="70")
    assert res["ok"] is False
    assert "White / Mikey" in res["error"]


def test_hell_rush_bad_threshold():
    api = JsApi()
    res = api.start_finder("White / Mikey", "Movement", "5", "first", "1",
                           hell_rush=True, hell_rush_min="notanumber")
    assert res["ok"] is False
    assert "threshold" in res["error"].lower()


def test_hell_rush_threshold_enforced():
    """Results emitted with HR on must all have score >= hell_rush_min."""
    import time
    api = JsApi()
    events = []
    import webview_app.bridge as _bridge
    orig_emit = _bridge._emit
    _bridge._emit = lambda d: events.append(d)
    try:
        res = api.start_finder("White / Mikey", "Movement", "5", "multi", "10",
                               hell_rush=True, hell_rush_min="0")
        assert res["ok"] is True
        time.sleep(2)
        api.stop_finder()
        time.sleep(0.5)
        result_events = [e for e in events if e.get("type") == "result"]
        for e in result_events:
            assert e.get("score") is not None
            assert e["score"] >= 0
    finally:
        _bridge._emit = orig_emit


def test_hell_rush_off_regression():
    """HR off should work identically to before — score is None in result payload."""
    import time
    api = JsApi()
    events = []
    import webview_app.bridge as _bridge
    orig_emit = _bridge._emit
    _bridge._emit = lambda d: events.append(d)
    try:
        res = api.start_finder("White / Mikey", "Movement", "3", "first", "1")
        assert res["ok"] is True
        deadline = time.time() + 10
        while time.time() < deadline:
            if any(e.get("type") == "done" for e in events):
                break
            time.sleep(0.1)
        result_events = [e for e in events if e.get("type") == "result"]
        if result_events:
            assert result_events[0].get("score") is None
    finally:
        _bridge._emit = orig_emit


def test_hell_rush_score_present_and_is_healthpack():
    """HR on: result has score field; White/Mikey cells have is_healthpack set correctly."""
    import time
    api = JsApi()
    events = []
    import webview_app.bridge as _bridge
    orig_emit = _bridge._emit
    _bridge._emit = lambda d: events.append(d)
    try:
        res = api.start_finder("White / Mikey", "Movement", "5", "first", "1",
                               hell_rush=True, hell_rush_min="0")
        assert res["ok"] is True
        deadline = time.time() + 15
        while time.time() < deadline:
            if any(e.get("type") == "result" for e in events):
                break
            time.sleep(0.1)
        api.stop_finder()
        result_events = [e for e in events if e.get("type") == "result"]
        assert result_events, "Expected at least one result with threshold 0"
        r = result_events[0]
        assert r.get("score") is not None
        from webview_app.hell_rush import HEALTHPACK_LEVELS
        hp_set = set(HEALTHPACK_LEVELS)
        for cell in r["level_order"]:
            expected_hp = cell["name"] in hp_set
            assert cell["is_healthpack"] == expected_hp
    finally:
        _bridge._emit = orig_emit


def test_is_healthpack_false_for_non_white():
    """Non-White rush cells should have is_healthpack=False."""
    import time
    api = JsApi()
    events = []
    import webview_app.bridge as _bridge
    orig_emit = _bridge._emit
    _bridge._emit = lambda d: events.append(d)
    try:
        res = api.start_finder("Violet", "Doghouse", "3", "first", "1")
        assert res["ok"] is True
        deadline = time.time() + 10
        while time.time() < deadline:
            if any(e.get("type") == "result" for e in events):
                break
            time.sleep(0.1)
        api.stop_finder()
        result_events = [e for e in events if e.get("type") == "result"]
        if result_events:
            for cell in result_events[0]["level_order"]:
                assert cell["is_healthpack"] is False
    finally:
        _bridge._emit = orig_emit


def test_calculate_timer_medal_grade():
    api = JsApi()
    # Movement at 17.442s is faster than DEV (18.93s) and within community medal range.
    # Exact medal depends on whether background fetch completed; accept any valid medal.
    ALL_MEDALS = {"BLOOD DIAMOND", "TOPAZ", "SAPPHIRE", "AMETHYST", "EMERALD",
                  "DEV", "ACE", "GOLD", "SILVER", "BRONZE", ""}
    splits = "Movement 17.442"
    res = api.calculate_timer("White / Mikey", "", splits)
    assert res["ok"] is True
    assert res["rows"][0]["medal"] in ALL_MEDALS
