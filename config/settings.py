"""Centralized Pydantic settings for AstraZeneca Campaign Lab (UC4)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration for AstraZeneca Campaign Lab (UC4)."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Cloud Project & Region
    google_cloud_project: str = "gcp-ai-intelligence-dev-0a06"
    google_cloud_project_number: str = "726684663091"
    google_cloud_location: str = "europe-west1"
    google_genai_use_vertexai: str = "TRUE"
    vertex_global_location: str = "global"

    # Cloud Storage (Dedicated UC4 Bucket / Folder Prefix)
    gcs_staging_bucket: str = "gs://astrazeneca-ge-pilot-staging"
    gcs_assets_bucket: str = "astrazeneca-ge-pilot-usecase"
    gcs_folder_prefix: str = "UC4"

    # Gemini Enterprise & Reasoning Engine
    gemini_enterprise_engine_id: str = "gemini-enterprise-commerci_1781864147849"
    gemini_enterprise_location: str = "eu"
    existing_reasoning_engine_id: str = ""

    # Datastore (Optional / Disabled by default for UC4)
    enable_datastore: bool = False
    datastore_id: str = ""
    datastore_location: str = "eu"

    # Google Search Grounding (Enabled by default for UC4)
    enable_google_grounding: bool = True

    # Models
    gemini_pro_model: str = "gemini-2.5-pro"
    gemini_flash_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-3-pro-image"
    veo_video_model: str = "veo-3.0-generate-001"
    tts_voice_name: str = "en-GB-Neural2-B"

    # Service & Agent Identity
    port: int = 8080
    log_level: str = "INFO"
    service_name: str = "AstraZeneca Campaign Lab"
    agent_icon_uri: str = (
        "gs://astrazeneca-ge-pilot-usecase/UC4/logos/astrazeneca_symbol_gold.png"
    )

    @property
    def output_dir(self) -> Path:
        out = PROJECT_ROOT / "output"
        out.mkdir(parents=True, exist_ok=True)
        return out

    @property
    def assets_dir(self) -> Path:
        return PROJECT_ROOT / "assets"

    @property
    def logos_dir(self) -> Path:
        return PROJECT_ROOT / "assets" / "astrazeneca_logos_svg"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
