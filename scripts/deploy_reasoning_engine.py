#!/usr/bin/env python3
"""Deploy AstraZeneca Campaign Lab (UC4) to Vertex AI Agent Engine & Gemini Enterprise.

Creates a NEW standalone Reasoning Engine for `AstraZeneca Campaign Lab` (or updates
`EXISTING_REASONING_ENGINE_ID` if set in `.env`) and registers it in the shared
Gemini Enterprise instance (`gemini-enterprise-commerci_1781864147849`) alongside UC1
without modifying UC1 (`Calquence Campaign Lab`).
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import httpx
import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.adk_conversational_agent import create_campaign_lab_adk_agent
from config.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _get_gcloud_access_token() -> str:
    res = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()


def deploy_to_vertex_agent_engine() -> str:
    """Deploy `AstraZeneca Campaign Lab` as an AdkApp on Vertex AI Agent Engine."""
    settings = get_settings()
    vertexai.init(
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        staging_bucket=settings.gcs_staging_bucket,
    )

    adk_agent = create_campaign_lab_adk_agent()
    app = AdkApp(agent=adk_agent, enable_tracing=True)

    requirements = [
        "google-adk>=1.0.0",
        "google-genai>=1.10.0",
        "google-cloud-aiplatform[adk,agent_engines]>=1.88.0",
        "google-cloud-storage>=2.18.0",
        "google-cloud-texttospeech>=2.21.0",
        "pydantic>=2.10.0",
        "pydantic-settings>=2.6.0",
        "python-dotenv>=1.0.1",
        "reportlab>=4.2.5",
        "python-docx>=1.1.2",
        "pillow>=11.0.0",
        "matplotlib>=3.9.2",
        "numpy>=2.1.0",
        "pypdf>=5.1.0",
        "httpx>=0.28.0",
    ]
    extra_packages = ["config", "tools", "agents"]

    env_vars = {
        "GOOGLE_CLOUD_PROJECT": settings.google_cloud_project,
        "GOOGLE_CLOUD_LOCATION": settings.google_cloud_location,
        "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
        "GCS_ASSETS_BUCKET": settings.gcs_assets_bucket,
        "GCS_FOLDER_PREFIX": settings.gcs_folder_prefix,
        "ENABLE_GOOGLE_GROUNDING": "true",
        "ENABLE_DATASTORE": "false",
        "SERVICE_NAME": settings.service_name,
    }

    if settings.existing_reasoning_engine_id:
        re_resource_name = (
            f"projects/{settings.google_cloud_project_number}/locations/"
            f"{settings.google_cloud_location}/reasoningEngines/"
            f"{settings.existing_reasoning_engine_id}"
        )
        logger.info("Updating existing UC4 Reasoning Engine: %s", re_resource_name)
        existing_engine = agent_engines.get(re_resource_name)
        updated = existing_engine.update(
            agent_engine=app,
            requirements=requirements,
            extra_packages=extra_packages,
            display_name=settings.service_name,
            description=(
                "AstraZeneca Campaign Lab (UC4) — Generic multimodal campaign, brand look-and-feel, "
                "and scientific communications studio with Google Search Grounding."
            ),
            env_vars=env_vars,
        )
        return updated.resource_name

    logger.info("Creating NEW Vertex AI Reasoning Engine for %s...", settings.service_name)
    remote_engine = agent_engines.create(
        agent_engine=app,
        requirements=requirements,
        extra_packages=extra_packages,
        display_name=settings.service_name,
        description=(
            "AstraZeneca Campaign Lab (UC4) — Generic multimodal campaign, brand look-and-feel, "
            "and scientific communications studio with Google Search Grounding."
        ),
        env_vars=env_vars,
    )
    logger.info("Created Reasoning Engine: %s", remote_engine.resource_name)
    return remote_engine.resource_name


def register_in_gemini_enterprise(reasoning_engine_resource_name: str) -> None:
    """Register `AstraZeneca Campaign Lab` in Gemini Enterprise (`eu` endpoint)."""
    settings = get_settings()
    token = _get_gcloud_access_token()
    loc = settings.gemini_enterprise_location
    base_url = (
        f"https://{loc}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{settings.google_cloud_project_number}/locations/{loc}/"
        f"collections/default_collection/engines/{settings.gemini_enterprise_engine_id}/"
        f"assistants/default_assistant/agents"
    )
    payload = {
        "displayName": settings.service_name,
        "description": (
            "Generic multimodal campaign & brand studio with Google Search Grounding, "
            "custom brand theme & hex palette engine, 4K slide decks, extended A4 pamphlets, "
            "SVG charts/logos, and short/long HD videos."
        ),
        "icon": {"uri": settings.agent_icon_uri},
        "adkAgentDefinition": {
            "toolSettings": {
                "toolDescription": (
                    "Use AstraZeneca Campaign Lab to research scientific/market queries with Google Search Grounding, "
                    "ingest attached documents/images, and generate 4K slide decks, extended A4 PDF pamphlets, "
                    "3 brand look-and-feel variations with a single master strapline, SVG charts/logos, and short/long MP4 videos."
                )
            },
            "provisionedReasoningEngine": {
                "reasoningEngine": reasoning_engine_resource_name
            },
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": settings.google_cloud_project,
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(base_url, headers=headers, json=payload)
        logger.info("Gemini Enterprise registration response (%s): %s", resp.status_code, resp.text)


if __name__ == "__main__":
    re_name = deploy_to_vertex_agent_engine()
    register_in_gemini_enterprise(re_name)
