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
    """
    Application configuration loaded from environment variables and defaults.

    Attributes:
        openai_api_key (str):
            OpenAI API key. Values: any non-empty string.
        gcs_api_key_json_b64 (str):
            Base64-encoded Google service account JSON. Values: any valid base64 string.
        google_genai_api_key (Optional[str]):
            Google GenAI API key. Values: None or any non-empty string.
        local_data_path (str):
            Local filesystem root for stored data. Values: any valid relative/absolute path string.
        use_cloud_storage (bool):
            Storage backend toggle. Values: True, False.
        gcs_bucket_name (str):
            Google Cloud Storage bucket name. Values: any valid GCS bucket name string.
        logging_level (int):
            Python logging level. Values: standard logging level integers (e.g., 10, 20, 30, 40, 50).
        gcs_service_account_json (Optional[str]):
            Decoded service account JSON payload object/string container. Values: None or decoded JSON content.
        enable_generation_progress_estimation (bool):
            Enables periodic generation progress logs. Values: True, False.
        generation_progress_log_interval_seconds (int):
            Progress log interval. Values: positive integers.
        image_generation_strategy (Literal["legacy", "seeded_reference_edit"]):
            Illustration strategy selector. Values: "legacy", "seeded_reference_edit".
        text_provider (Literal["google", "openai", "anthropic", "xai"]):
            Text generation provider selector. Values: "google", "openai", "anthropic", "xai".
        image_provider (Literal["google", "openai", "anthropic", "xai"]):
            Image generation provider selector. Values: "google", "openai", "anthropic", "xai".
        image_generation_min_workers (int):
            Minimum parallel worker count for image generation. Values: integers >= 1 (effective).
        image_generation_max_workers (int):
            Maximum parallel worker count for image generation. Values: integers >= 1 (effective).
        image_generation_retry_attempts (int):
            Retry attempts per page image generation. Values: integers >= 1 (effective).
        image_generation_retry_backoff_base_seconds (float):
            Exponential backoff base delay. Values: floats >= 0.0.
        image_generation_retry_backoff_max_seconds (float):
            Exponential backoff max delay cap. Values: floats >= 0.0.
        image_generation_retry_use_jitter (bool):
            Whether retry delay uses jitter randomization. Values: True, False.
        openai_text_model (str):
            OpenAI model for text generation. Values: any supported OpenAI text model string.
        openai_image_model (str):
            OpenAI model for image generation. Values: any supported OpenAI image model string.
        google_text_model (str):
            Google model for text generation. Values: any supported Google text model string.
        google_image_model (str):
            Google model for image generation. Values: any supported Google image model string.
        image_prompt_observability_mode (Literal["off", "metadata", "full"]):
            Prompt observability detail mode. Values: "off", "metadata", "full".
        image_prompt_log_max_chars (int):
            Maximum prompt characters included in logs. Values: integers >= 0.
    """

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
    text_provider: Literal["google", "openai", "anthropic", "xai"] = "google"
    image_provider: Literal["google", "openai", "anthropic", "xai"] = "google"
    image_generation_min_workers: int = 2
    image_generation_max_workers: int = 4
    image_generation_retry_attempts: int = 3
    image_generation_retry_backoff_base_seconds: float = 0.5
    image_generation_retry_backoff_max_seconds: float = 8.0
    image_generation_retry_use_jitter: bool = True
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
