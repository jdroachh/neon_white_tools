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


class ResourcesStatus(BaseModel):
    ghosts_loaded: bool
    videos_loaded: bool
    error: str | None = None
