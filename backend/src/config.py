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
        story_generation_timeout_seconds (int):
            App-level timeout for story text generation. Values: positive integers.
        total_generation_timeout_seconds (int):
            App-level timeout for the full book generation workflow. Values: positive integers.
        provider_request_timeout_seconds (int):
            Provider SDK/request timeout for text generation calls. Values: positive integers.
        image_provider_request_timeout_seconds (int):
            Provider SDK/request timeout for image generation calls. Values: positive integers.
        prompt_path_version (Literal["v1", "v2", "v3"]):
            Story prompt/schema path selector. Values: "v1", "v2", "v3".
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
        openai_image_aspect_profile (str):
            OpenAI image sizing strategy. Values: "portrait_model_aware", "square".
        openai_image_size_override (Optional[str]):
            Explicit OpenAI image size override. Values: None or model-supported size string.
        openai_image_quality_mode (str):
            OpenAI quality strategy. Values: "medium_model_aware", "auto", "low", "medium", "high", "standard", "hd".
        openai_image_output_format (str):
            OpenAI image output format. Values: "b64_json", "url", "png", "jpeg", "webp".
        openai_image_output_compression (Optional[int]):
            OpenAI image compression quality for lossy formats. Values: None or integer 0-100.
        openai_image_background (Optional[str]):
            OpenAI image background mode. Values: None, "transparent", "opaque", "auto".
        google_text_model (str):
            Google model for text generation. Values: any supported Google text model string.
            See: https://ai.google.dev/gemini-api/docs/models
        google_image_model (str):
            Google model for image generation. Values: any supported Google image model string.
            See: https://ai.google.dev/gemini-api/docs/models
        google_image_aspect_ratio (str):
            Gemini image aspect ratio. Values: "1:1","1:4","1:8","2:3","3:2","3:4","4:1","4:3","4:5","5:4","8:1","9:16","16:9","21:9".
        google_image_size (str):
            Gemini image size/resolution. Values: "512px", "1K", "2K", "4K".
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
    story_generation_timeout_seconds: int = 60
    total_generation_timeout_seconds: int = 300
    provider_request_timeout_seconds: int = 55
    image_provider_request_timeout_seconds: int = 55
    prompt_path_version: Literal["v1", "v2", "v3"] = "v3"
    image_generation_strategy: Literal["legacy", "seeded_reference_edit"] = (
        "seeded_reference_edit"
    )
    text_provider: Literal["google", "openai", "anthropic", "xai"] = "google"
    image_provider: Literal["google", "openai", "anthropic", "xai"] = "google"
    image_generation_min_workers: int = 3
    image_generation_max_workers: int = 5
    image_generation_retry_attempts: int = 3
    image_generation_retry_backoff_base_seconds: float = 0.5
    image_generation_retry_backoff_max_seconds: float = 8.0
    image_generation_retry_use_jitter: bool = True
    openai_text_model: str = "gpt-5"
    openai_image_model: str = "gpt-image-1.5"
    openai_image_aspect_profile: Literal["portrait_model_aware", "square"] = "square"
    openai_image_size_override: Optional[str] = None
    openai_image_quality_mode: Literal[
        "medium_model_aware", "auto", "low", "medium", "high", "standard", "hd"
    ] = "medium_model_aware"
    openai_image_output_format: Literal["b64_json", "url", "png", "jpeg", "webp"] = (
        "b64_json"
    )
    openai_image_output_compression: Optional[int] = None
    openai_image_background: Optional[Literal["transparent", "opaque", "auto"]] = None
    google_text_model: str = "gemini-3.1-flash-lite-preview"
    google_image_model: str = "gemini-3.1-flash-image-preview"
    google_image_aspect_ratio: str = "1:1"
    google_image_size: str = "512px"
    image_prompt_observability_mode: Literal["off", "metadata", "full"] = "off"
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
