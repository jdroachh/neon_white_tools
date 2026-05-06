"""
timer models

NOTE: diverges from BACKEND_HANDOFF §4.5. The JSX Run Timer is an on-demand
splits calculator (paste cumulative times, see deltas + medals). There is no
websocket, no live tick. Modeling what the mockup actually shows.
"""
from __future__ import annotations
from typing import Literal, TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from .splits import SplitLevel


class TimerInputRow(BaseModel):
    level_name: str | None = None  # frozen when mode != "Enter Manually"
    cumulative: str                # user-pasted time string


class TimerCalcRequest(BaseModel):
    rush_name: str
    mode: Literal["Load by Seed", "Enter Manually", "Standard Order"]
    seed: int | None = None        # required when mode == "Load by Seed"
    output_format: Literal["plain", "mmss"] = "mmss"
    medals_on: bool = True
    rows: list[TimerInputRow]


class TimerCalcResponse(BaseModel):
    levels: list[dict]             # SplitLevel dicts — avoids circular import at model layer
    errors: list[str] = []        # row-level parse errors
