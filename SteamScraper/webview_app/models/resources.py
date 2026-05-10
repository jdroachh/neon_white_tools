from typing import Literal
from pydantic import BaseModel


class GhostRow(BaseModel):
    level: str
    medal: str
    player: str
    time: str
    drive_url: str


class VideoRow(BaseModel):
    level: str
    medal: str
    title: str
    youtube_url: str


class WorldRecordRow(BaseModel):
    level: str
    platform: str
    player: str
    time_formatted: str
    date: str
    youtube_url: str
    title: str


class ResourcesStatus(BaseModel):
    ghosts_loaded: bool
    videos_loaded: bool
    wrs_loaded: bool = False
    guides_loaded: bool = False
    error: str | None = None


class Guide(BaseModel):
    category: Literal["route", "technical", "playlist"]
    level: str | None = None
    tier: str | None = None
    title: str
    author: str
    url: str | None = None


class GuidesResponse(BaseModel):
    guides: list[Guide]
    loaded: bool = False
