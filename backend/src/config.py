# backend/src/config.py

from pydantic import BaseSettings
from pathlib import Path
import base64
import json
from typing import Optional
import logging


ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    openai_api_key: str
    gcs_api_key_json_b64: str
    local_data_path: str = "local_data"
    use_cloud_storage: bool = True  # Default to True; set to False to use local storage
    gcs_bucket_name: str = "kwento-books"  # GCS bucket name
    logging_level = logging.INFO
    gcs_service_account_json: Optional[str]
    enable_generation_progress_estimation: bool = True
    generation_progress_log_interval_seconds: int = 10

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"


def set_gcs_cred_info_from_b64(settings: Settings) -> Settings:
    """
    Converts B64 creds data to JSON object and sets to approprate attr of `Settings`
    """
    s = base64.b64decode(settings.gcs_api_key_json_b64).decode("utf-8")
    j = json.loads(s)
    settings.gcs_service_account_json = j
    return settings


settings = Settings()
settings = set_gcs_cred_info_from_b64(settings)
settings.use_cloud_storage = True
