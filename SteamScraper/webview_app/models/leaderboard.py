from typing import Literal
from pydantic import BaseModel


class GlobalExportRequest(BaseModel):
    top_n: int
    output: Literal["display", "csv", "both"]
    csv_path: str | None = None


class LevelSearchRequest(BaseModel):
    level_name: str
    top_n: int = 100


class PlayerLookupRequest(BaseModel):
    player_name: str
    mode: Literal["Single Level", "Chapter", "Whole Game"]
    level_name: str | None = None
    chapter: str | None = None


class LeaderboardRow(BaseModel):
    rank: str
    level: str
    player: str
    time: str


class LogLine(BaseModel):
    text: str
    kind: Literal["info", "ok", "warn", "err"] | None = None
    cursor: bool = False


class LeaderboardProgress(BaseModel):
    type: Literal["log"] = "log"
    line: LogLine


class LeaderboardDone(BaseModel):
    type: Literal["done"] = "done"
    rows: list[LeaderboardRow]
    csv_path: str | None = None
