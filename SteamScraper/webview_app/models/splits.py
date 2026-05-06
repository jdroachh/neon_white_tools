from typing import Literal
from pydantic import BaseModel


class SplitLevel(BaseModel):
    index: int
    name: str
    cumulative: str  # e.g. "1:13.858"
    segment: str     # e.g. "35.573"
    medal: Literal["ace", "gold", "silver", "bronze", "red"]


class SplitsParseRequest(BaseModel):
    file_path: str


class SplitsParseResponse(BaseModel):
    rush_name: str | None
    seed: int | None
    levels: list[SplitLevel]


class SplitsUpdateRequest(BaseModel):
    file_path: str
    levels: list[SplitLevel]


class StandardizeRequest(BaseModel):
    file_path: str
    rush_name: str
    # TODO(M1-Q2): canonical_orders per rush — needs rush_data.py audit or new data/canonical_orders.json


class StandardizeResponse(BaseModel):
    canonical_order: list[str]
    seeded_order: list[str]
    reordered_segments: list[SplitLevel]
    output_path: str
