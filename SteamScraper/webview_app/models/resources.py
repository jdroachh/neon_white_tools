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
    error: str | None = None
