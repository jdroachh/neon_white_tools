from typing import Literal
from pydantic import BaseModel


class Settings(BaseModel):
    theme: Literal["light", "dark"] = "dark"
    default_rush: str = "White / Mikey"
    last_lss_path: str | None = None
    last_csv_dir: str | None = None
    sheets_credentials_path: str | None = None
    sheet_id: str | None = None
    dll_path: str | None = None   # existing key from neonwhite_config.json
