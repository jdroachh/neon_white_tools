"""
Pydantic types for the Multi-Compare bridge interface.

Event shapes match the prototype's heatmap models verbatim (renamed only).
Frontend listener code written against the prototype's wire format works
unchanged after graduation — the source of the data changed (mock_data ->
steam_api with batched fetches), not the shape on the wire.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ── Request ─────────────────────────────────────────────────────────────────
class MultiCompareRequest(BaseModel):
    """Input to JsApi.run_multi_compare."""
    steam_ids: list[str] = Field(min_length=1, max_length=10)
    mode: Literal["level", "chapter", "game"]
    target: str = ""  # level display name (mode=level), chapter key (mode=chapter), ignored for mode=game

    @field_validator("steam_ids")
    @classmethod
    def _validate_ids(cls, v: list[str]) -> list[str]:
        for sid in v:
            if not sid.isdigit() or len(sid) != 17:
                raise ValueError(f"Invalid Steam ID (must be 17 digits): {sid}")
        if len(set(v)) != len(v):
            raise ValueError("Duplicate Steam IDs not allowed")
        return v


# ── Stream events emitted through window._nwMultiCompareEvent ──────────────
class MultiCompareRowEvent(BaseModel):
    type: Literal["row"] = "row"
    steam_id: str
    level_code: str
    level_display: str
    time_us: Optional[int]   # None when missing=True
    rank: Optional[int]      # None when missing=True
    missing: bool
    medal: Optional[str] = None  # e.g. "AMETHYST", "GOLD", "BLOOD DIAMOND"; None when missing or unknown


class MultiCompareProgressEvent(BaseModel):
    type: Literal["progress"] = "progress"
    done: int
    total: int


class MultiCompareDoneEvent(BaseModel):
    type: Literal["done"] = "done"
    message: str  # "ok" on natural completion, "stopped" if cancelled
