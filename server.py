"""FastAPI HTTP Service for AstraZeneca Campaign Lab (UC4)."""
from __future__ import annotations

from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel

from agents.orchestrator_agent import run_full_campaign_lab_pipeline
from config.settings import get_settings
from tools.grounding_tools import search_with_google_grounding

settings = get_settings()
app = FastAPI(
    title=settings.service_name,
    version="1.0.0",
    description="Generic Multimodal Campaign & Brand Studio with Google Search Grounding (UC4)",
)


class CampaignRequest(BaseModel):
    campaign_name: str = "AZD9550 Complementary Strategy"
    campaign_objective: str = (
        "Produce executive 4K slide deck, extended A4 pamphlet, 3 look-and-feel variations, SVG charts, and video."
    )
    master_strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE."
    theme_prompt: str = "astrazeneca_light"
    include_az_logo: Optional[bool] = None
    video_length_mode: str = "short"
    attached_file_path: Optional[str] = None
    upload_to_gcs: bool = False


class GroundedQueryRequest(BaseModel):
    query: str
    campaign_context: str = ""


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "healthy",
        "service": settings.service_name,
        "gcs_folder_prefix": settings.gcs_folder_prefix,
        "google_grounding_enabled": settings.enable_google_grounding,
        "datastore_enabled": settings.enable_datastore,
    }


@app.post("/grounding/search")
def grounded_search_endpoint(req: GroundedQueryRequest) -> dict:
    return search_with_google_grounding(
        query=req.query,
        campaign_context=req.campaign_context,
    )


@app.post("/campaign/generate")
def generate_campaign_endpoint(req: CampaignRequest) -> dict:
    return run_full_campaign_lab_pipeline(
        campaign_name=req.campaign_name,
        campaign_objective=req.campaign_objective,
        master_strapline=req.master_strapline,
        theme_prompt=req.theme_prompt,
        include_az_logo=req.include_az_logo,
        video_length_mode=req.video_length_mode,
        attached_file_path=req.attached_file_path,
        upload_to_gcs=req.upload_to_gcs,
    )
