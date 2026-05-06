from typing import Literal
from pydantic import BaseModel


class ExcludeSpec(BaseModel):
    window: int
    levels: list[str]


class HellRushSpec(BaseModel):
    spacing_mode: Literal["Best Spacing Only", "Secondary Filter"]
    # Required when spacing_mode == "Secondary Filter" and min_score_on is true
    min_score: int | None = None


class SeedFindRequest(BaseModel):
    rush_name: str
    depth: int
    mode: Literal["First Match", "Find Multiple"]
    match_count: int = 5
    order_matters: Literal["Any Order", "Exact Order"] = "Any Order"
    desired_levels: list[str]
    force_first: str | None = None
    exclude: ExcludeSpec | None = None
    hell_rush: HellRushSpec | None = None
    seed_min: int = 0
    seed_max: int = 2_147_483_647
    use_gpu: bool = False  # unused — kept for forward-compat with the advanced panel


class LevelTag(BaseModel):
    name: str
    kinds: list[Literal["forced", "desired", "excluded", "healthpack"]] = []


class SeedResult(BaseModel):
    seed: int
    score: int | None = None
    level_order: list[LevelTag]


class SeedFindResponse(BaseModel):
    summary: str
    elapsed_seconds: float
    threads: int
    results: list[SeedResult]


class SeedFindProgress(BaseModel):
    type: Literal["progress"] = "progress"
    seeds_checked: int
    elapsed: float


class SeedFindDone(BaseModel):
    type: Literal["done"] = "done"
    response: SeedFindResponse


class SeedParseRequest(BaseModel):
    rush_name: str
    seed: int


class SeedParseResponse(BaseModel):
    rush_name: str
    seed: int
    level_count: int
    level_order: list[str]
