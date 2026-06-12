from typing import Literal
from pydantic import BaseModel


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
