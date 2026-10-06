"""5-Agent Generic Omnichannel Orchestrator for AstraZeneca Campaign Lab (UC4).

Coordinates:
1. Grounding & Attachment Intelligence Agent (Google Search Grounding + PDF/DOCX/Image parsing)
2. Brand Look & Feel & Strapline Director Agent (3 Look & Feel variations + Anchor Recommendation + Single Strapline)
3. Vector SVG & Data Visualization Agent (SVG + 450-DPI PNG charts, synergy diagrams, and logos)
4. 4K Slide Deck & Extended A4 Pamphlet Agent (Extra-large typography + custom or AstraZeneca theme)
5. Motion & Video Production Agent (Short 20s or Long 64s 1080p HD MP4 video)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.cloud import storage

from config.brand_guidelines import parse_brand_theme
from config.settings import get_settings
from tools.chart_tools import (
    generate_campaign_chart_svg_and_png,
    generate_pathway_synergy_svg_and_png,
)
from tools.docx_tools import generate_campaign_brief_docx
from tools.grounding_tools import (
    extract_attached_document_or_image_context,
    search_with_google_grounding,
)
from tools.image_tools import (
    generate_4k_campaign_key_visual,
    generate_brand_look_and_feel_variations_4k,
)
from tools.logo_tools import (
    ensure_astrazeneca_logo_assets,
    generate_custom_brand_logo_svg,
)
from tools.pdf_tools import generate_extended_campaign_pamphlet_pdf
from tools.slide_deck_tools import generate_4k_slide_deck
from tools.video_tools import generate_campaign_video_mp4

logger = logging.getLogger(__name__)


def upload_deliverable_to_gcs(local_path: str, subfolder: str = "deliverables") -> Dict[str, str]:
    """Upload a generated deliverable to the dedicated UC4 GCS bucket/prefix and return authenticated URLs."""
    settings = get_settings()
    p = Path(local_path)
    if not p.exists():
        return {"local_path": local_path, "gcs_uri": "", "authenticated_url": ""}

    prefix = settings.gcs_folder_prefix.strip("/")
    blob_name = f"{prefix}/{subfolder}/{p.name}"
    gcs_uri = f"gs://{settings.gcs_assets_bucket}/{blob_name}"
    auth_url = f"https://storage.mtls.cloud.google.com/{settings.gcs_assets_bucket}/{blob_name}"

    try:
        client = storage.Client(project=settings.google_cloud_project)
        bucket = client.bucket(settings.gcs_assets_bucket)
        blob = bucket.blob(blob_name)
        content_type_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".pdf": "application/pdf",
            ".mp4": "video/mp4",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        blob.upload_from_filename(
            str(p),
            content_type=content_type_map.get(p.suffix.lower(), "application/octet-stream"),
        )
    except Exception as exc:
        logger.info("Offline or skipped GCS upload for %s: %s", p.name, exc)

    return {
        "local_path": str(p),
        "gcs_uri": gcs_uri,
        "authenticated_url": auth_url,
    }


def run_full_campaign_lab_pipeline(
    campaign_name: str,
    campaign_objective: str = "Launch a high-impact scientific and commercial campaign highlighting complementary mechanisms and unified brand storytelling.",
    master_strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
    theme_prompt: str = "astrazeneca_light",
    include_az_logo: Optional[bool] = None,
    video_length_mode: str = "short",
    attached_file_path: Optional[str] = None,
    upload_to_gcs: bool = False,
) -> Dict[str, Any]:
    """Execute the end-to-end generic AstraZeneca Campaign Lab studio pipeline for any product or theme.

    Args:
        campaign_name: Product, molecule, or initiative name (e.g., 'AZD9550', 'Tagrisso', 'NextGen CVRM').
        campaign_objective: Core objective or scientific narrative.
        master_strapline: Single unifying master strapline for the campaign.
        theme_prompt: Preset ('astrazeneca_light', 'astrazeneca_dark', 'google_brand') or free-text
                      custom branding prompt with Hex/RGB colors, background, and text rules.
        include_az_logo: Explicitly include or exclude official AstraZeneca vector logos.
        video_length_mode: 'short' (20s teaser) or 'long' (64s full narrative video).
        attached_file_path: Optional path to a user-attached PDF, DOCX, TXT, or Image.
        upload_to_gcs: Whether to upload generated assets to gs://astrazeneca-ge-pilot-usecase/UC4/.

    Returns:
        Dictionary of all generated deliverables, theme metadata, grounded insights, and GCS URLs.
    """
    ensure_astrazeneca_logo_assets()
    theme = parse_brand_theme(theme_prompt, include_az_logo=include_az_logo)
    slug = campaign_name.lower().replace(" ", "_")

    # 1. Attachment ingestion (if provided) + Google Search Grounding
    attachment_info: Dict[str, Any] = {}
    if attached_file_path:
        attachment_info = extract_attached_document_or_image_context(attached_file_path)

    grounding_info = search_with_google_grounding(
        query=f"{campaign_name} {campaign_objective}",
        campaign_context=attachment_info.get("extracted_text", "")[:2000],
    )

    # 2. Vector SVG Custom Brand Crest + Evidence Chart + Synergy Architecture Diagram
    logo_svg_res = generate_custom_brand_logo_svg(
        brand_title=campaign_name,
        subtitle=master_strapline[:34],
        theme_prompt=theme_prompt,
        output_filename=f"{slug}_brand_crest.svg",
    )
    chart_res = generate_campaign_chart_svg_and_png(
        chart_title=f"{campaign_name} — Multi-Dimensional Outcome Synergy",
        categories=["Primary Efficacy", "Organ Clearance", "Energy Balance", "Composite Benefit"],
        series_primary_values=[89.0, 93.0, 86.0, 92.0],
        series_primary_label=f"{campaign_name} Complementary Strategy",
        series_secondary_values=[64.0, 51.0, 48.0, 62.0],
        series_secondary_label="Single-Pathway Baseline",
        theme_prompt=theme_prompt,
        output_basename=f"{slug}_evidence_chart",
    )
    synergy_res = generate_pathway_synergy_svg_and_png(
        diagram_title=f"{campaign_name} — Complementary Dual-Pathway Architecture",
        central_outcome_title=master_strapline,
        theme_prompt=theme_prompt,
        output_basename=f"{slug}_synergy_diagram",
    )

    # 3. 4K Hero Key Visual + 3-Up Brand Look & Feel Comparison Board (with Single Strapline & Anchor)
    hero_kv_res = generate_4k_campaign_key_visual(
        campaign_name=campaign_name,
        headline=f"{campaign_name}: Complementary Strategy in Action",
        strapline=master_strapline,
        theme_prompt=theme_prompt,
        include_az_logo=include_az_logo,
        output_filename=f"{slug}_hero_key_visual_4k.png",
    )
    look_feel_res = generate_brand_look_and_feel_variations_4k(
        campaign_name=campaign_name,
        master_strapline=master_strapline,
        theme_prompt=theme_prompt,
        include_az_logo=include_az_logo,
        output_filename=f"{slug}_look_and_feel_3up_4k.png",
    )

    # 4. 4K Widescreen Slide Deck (PNGs + Widescreen PDF)
    slide_deck_res = generate_4k_slide_deck(
        campaign_name=campaign_name,
        theme_prompt=theme_prompt,
        include_az_logo=include_az_logo,
        output_pdf_filename=f"{slug}_slide_deck_4k.pdf",
    )

    # 5. Extended 4-Page A4 Information Pamphlet PDF + Page PNGs
    pamphlet_res = generate_extended_campaign_pamphlet_pdf(
        campaign_name=campaign_name,
        strapline=master_strapline,
        executive_summary=campaign_objective,
        theme_prompt=theme_prompt,
        include_az_logo=include_az_logo,
        hero_image_path=hero_kv_res["image_path"],
        output_filename=f"{slug}_information_pamphlet.pdf",
    )

    # 6. Short or Long 1080p HD Video (.mp4)
    video_res = generate_campaign_video_mp4(
        campaign_name=campaign_name,
        strapline=master_strapline,
        video_length_mode=video_length_mode,
        existing_frame_paths=slide_deck_res["slide_png_paths"],
        theme_prompt=theme_prompt,
        include_az_logo=include_az_logo,
        output_filename=f"{slug}_{video_length_mode}_video.mp4",
    )

    # 7. Editable Word (.docx) Campaign Brief
    docx_res = generate_campaign_brief_docx(
        campaign_name=campaign_name,
        master_strapline=master_strapline,
        executive_summary=campaign_objective,
        embedded_image_paths=[
            hero_kv_res["image_path"],
            look_feel_res["board_image_path"],
            chart_res["png_path"],
        ],
        theme_prompt=theme_prompt,
        output_filename=f"{slug}_campaign_brief.docx",
    )

    deliverables: Dict[str, Any] = {
        "hero_key_visual_4k_png": hero_kv_res["image_path"],
        "look_and_feel_3up_board_4k_png": look_feel_res["board_image_path"],
        "slide_deck_4k_pdf": slide_deck_res["pdf_deck_path"],
        "slide_deck_4k_pngs": slide_deck_res["slide_png_paths"],
        "information_pamphlet_pdf": pamphlet_res["pamphlet_pdf_path"],
        "information_pamphlet_page_pngs": pamphlet_res["pamphlet_page_pngs"],
        "evidence_chart_svg": chart_res["svg_path"],
        "evidence_chart_png": chart_res["png_path"],
        "synergy_diagram_svg": synergy_res["svg_path"],
        "synergy_diagram_png": synergy_res["png_path"],
        "custom_brand_crest_svg": logo_svg_res["svg_path"],
        "campaign_video_mp4": video_res["video_path"],
        "campaign_brief_docx": docx_res["docx_path"],
    }

    gcs_uploads: Dict[str, Dict[str, str]] = {}
    if upload_to_gcs:
        for key, val in deliverables.items():
            if isinstance(val, str):
                gcs_uploads[key] = upload_deliverable_to_gcs(val)

    return {
        "status": "success",
        "campaign_name": campaign_name,
        "master_strapline": master_strapline,
        "recommended_anchor": look_feel_res["recommended_anchor"],
        "anchor_rationale": look_feel_res["anchor_rationale"],
        "theme": {
            "theme_id": theme.theme_id,
            "theme_name": theme.theme_name,
            "background_hex": theme.background_hex,
            "text_primary_hex": theme.text_primary_hex,
            "palette_hex": theme.palette_hex,
            "include_az_logo": theme.include_az_logo,
        },
        "grounding": grounding_info,
        "attachment": attachment_info,
        "video_length_mode": video_res["video_length_mode"],
        "video_duration_seconds": video_res["duration_seconds"],
        "deliverables": deliverables,
        "gcs_uploads": gcs_uploads,
    }
