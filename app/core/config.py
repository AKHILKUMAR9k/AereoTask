import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = BASE_DIR / "geospatial.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".zip", ".kml"}


class Settings(BaseModel):
    app_name: str = "Geospatial File Measurement API"
    app_version: str = "1.0.0"
    upload_dir: Path = UPLOAD_DIR
    database_url: str = DATABASE_URL
    max_upload_size: int = MAX_UPLOAD_SIZE_BYTES
    allowed_extensions: set[str] = ALLOWED_EXTENSIONS


settings = Settings()
