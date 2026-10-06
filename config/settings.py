# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Centralized Pydantic settings for AstraZeneca Campaign Lab (UC4).

Defines Google Cloud project configuration, dedicated `UC4` Cloud Storage paths,
V4 Signed URL service account settings, Gemini Enterprise registration targets,
and Gemini 3.1 / 3.x model identifiers. Contains zero product-specific or Calquence hardcoding.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Set
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
    gcs_staging_bucket: str = "gs://astrazeneca-ge-pilot-usecase"
    gcs_assets_bucket: str = "astrazeneca-ge-pilot-usecase"
    artifact_service_uri: str = "gs://astrazeneca-ge-pilot-usecase"
    gcs_folder_prefix: str = "UC4"
    signing_service_account: str = (
        "project-service-account@gcp-ai-intelligence-dev-0a06.iam.gserviceaccount.com"
    )

    # Gemini Enterprise & Reasoning Engine
    gemini_enterprise_engine_id: str = "gemini-enterprise-commerci_1781864147849"
    gemini_enterprise_location: str = "eu"
    existing_reasoning_engine_id: str = ""

    # Datastore (Disabled by default for UC4 — uses Google Search Grounding + User Attachments)
    enable_datastore: bool = False
    datastore_id: str = ""
    datastore_location: str = "eu"

    # Google Search Grounding (Enabled by default for UC4)
    enable_google_grounding: bool = True

    # Gemini 3.1 Pro / 3 Flash / Nano Banana Pro 4K Models
    gemini_pro_model: str = "gemini-3.1-pro-preview"
    gemini_flash_model: str = "gemini-3-flash-preview"
    gemini_image_model: str = "gemini-3-pro-image"
    fallback_image_model: str = "gemini-3.1-flash-image"
    veo_video_model: str = "veo-3.0-generate-001"
    tts_voice_name: str = "en-GB-Neural2-B"

    # Service & Agent Identity
    port: int = 8080
    log_level: str = "INFO"
    service_name: str = "AstraZeneca Campaign Lab"
    agent_icon_uri: str = (
        "gs://astrazeneca-ge-pilot-usecase/UC4/logos/astrazeneca_symbol_gold.png"
    )

    # Upper-case compatibility aliases matching UC1 conventions
    @property
    def MODEL_TIER(self) -> str:
        return self.gemini_pro_model

    @property
    def FALLBACK_MODEL_TIER(self) -> str:
        return self.gemini_flash_model

    @property
    def IMAGEN_MODEL(self) -> str:
        return self.gemini_image_model

    @property
    def GCS_EXPORT_BUCKET(self) -> str:
        return self.gcs_assets_bucket

    @property
    def STAGING_BUCKET(self) -> str:
        return self.gcs_staging_bucket

    @property
    def GCS_FOLDER_PREFIX(self) -> str:
        return self.gcs_folder_prefix

    @property
    def SIGNING_SERVICE_ACCOUNT(self) -> str:
        return self.signing_service_account

    @property
    def llm_model_candidates(self) -> List[str]:
        """Ordered list of Gemini 3.x reasoning models."""
        candidates = [
            "gemini-3.1-pro-preview",
            "gemini-3-flash-preview",
            self.gemini_pro_model,
            "gemini-3.2-pro",
            self.gemini_flash_model,
            "gemini-3.6-flash",
        ]
        seen: Set[str] = set()
        ordered: List[str] = []
        for m in candidates:
            if m and m not in seen:
                seen.add(m)
                ordered.append(m)
        return ordered

    @property
    def image_model_candidates(self) -> List[str]:
        """Ordered list of Gemini 3.x 4K image generation models."""
        return [
            self.gemini_image_model,
            self.fallback_image_model,
        ]

    @property
    def output_dir(self) -> Path:
        """Directory where generated slides, PDFs, SVGs, and MP4 videos are written."""
        out = PROJECT_ROOT / "output"
        out.mkdir(parents=True, exist_ok=True)
        return out

    @property
    def uploads_dir(self) -> Path:
        """Directory where user-attached chat files (PDFs, DOCX, Images) are staged."""
        up = self.output_dir / "uploads"
        up.mkdir(parents=True, exist_ok=True)
        return up

    @property
    def assets_dir(self) -> Path:
        """Root directory for static brand assets."""
        return PROJECT_ROOT / "assets"

    @property
    def logos_dir(self) -> Path:
        """Directory containing official AstraZeneca vector SVG and 4K PNG logos."""
        return PROJECT_ROOT / "assets" / "astrazeneca_logos_svg"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()


settings = get_settings()
