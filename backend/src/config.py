# backend/src/config.py

try:
    # Pydantic v2 preferred path (requires pydantic-settings package).
    from pydantic_settings import BaseSettings
except Exception:
    try:
        # Pydantic v2 compatibility namespace.
        from pydantic.v1 import BaseSettings
    except Exception:
        # Pydantic v1 legacy path.
        from pydantic import BaseSettings
from pathlib import Path
import base64
import json
from typing import Optional, Literal
import logging


ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    openai_api_key: str
    gcs_api_key_json_b64: str
    google_genai_api_key: Optional[str] = None
    local_data_path: str = "local_data"
    use_cloud_storage: bool = True  # Default to True; set to False to use local storage
    gcs_bucket_name: str = "kwento-books"  # GCS bucket name
    logging_level: int = logging.INFO
    gcs_service_account_json: Optional[str] = None
    enable_generation_progress_estimation: bool = True
    generation_progress_log_interval_seconds: int = 10
    image_generation_strategy: Literal["legacy", "seeded_reference_edit"] = (
        "seeded_reference_edit"
    )
    image_provider: Literal["google", "openai", "anthropic", "xai"] = "google"
    openai_text_model: str = "gpt-5-mini"
    openai_image_model: str = "dall-e-3"
    google_text_model: str = "gemini-2.5-flash"
    google_image_model: str = "gemini-2.5-flash-image"
    image_prompt_observability_mode: Literal["off", "metadata", "full"] = "metadata"
    image_prompt_log_max_chars: int = 12000

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
