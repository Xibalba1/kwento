# backend/src/config.py

from pydantic import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    use_cloud_storage: bool = (
        True  # Default to False; set to True to use Google Cloud Storage
    )
    gcs_bucket_name: str = "kwento-books"  # GCS bucket name
    gcs_service_account_json: str = (
        "secrets/kwento-88cf359a16d5.json"  # Path GCP storage service account JSON key
    )

    class Config:
        env_file = ".env"


settings = Settings()
