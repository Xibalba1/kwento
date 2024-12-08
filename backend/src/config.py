# backend/src/config.py

from pydantic import BaseSettings
import base64
import json
from typing import Optional
import logging


class Settings(BaseSettings):
    openai_api_key: str
    gcs_api_key_json_b64: str
    local_data_path: str = "local_data"
    use_cloud_storage: bool = (
        False  # Default to False; set to True to use Google Cloud Storage
    )
    gcs_bucket_name: str = "kwento-books"  # GCS bucket name
    logging_level = logging.INFO
    gcs_service_account_json: Optional[str]

    class Config:
        env_file = ".env"


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
