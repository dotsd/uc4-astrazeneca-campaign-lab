"""Google ADK Conversational Root Agent for AstraZeneca Campaign Lab (UC4).

Deployed to Vertex AI Agent Engine (`AdkApp`) and registered in Gemini Enterprise as
`AstraZeneca Campaign Lab`.

Key Capabilities:
1. 100% Generic Campaign & Product Studio (Zero Calquence hardcoding).
2. Live Google Search Grounding (`search_with_google_grounding`) to answer scientific,
   clinical, regulatory, or commercial queries with grounded web citations.
3. Multimodal Document & Image Attachment Ingestion (`extract_attached_document_or_image_context`)
   to turn user-uploaded PDFs, Word docs, or images into slide decks, pamphlets, and videos.
4. Dynamic Brand Theme Engine (`parse_brand_theme`):
   - Follows exact user color/formatting prompts (e.g., Google branding: white background,
     grey text, Blue #4285F4, Red #EA4335, Yellow #FBBC04, Green #34A853).
   - Or asks the user if they want **AstraZeneca Corporate Format** (with official AstraZeneca
     vector SVG/PNG logos, icons, and Mulberry #830051 / Gold #F0AB00 / Navy #003865 /
     Dark Metabolic Plum #1E0514 palette).
5. Full Suite of Tangible Deliverables:
   - 4K Widescreen Slide Deck (`3840 × 2160` PNGs + PDF) with extra-large readable fonts
   - Extended Multi-Page A4 Information Pamphlet PDF with graphs, 4K visuals, and logos
   - 3 Brand Look & Feel Variations + Single Master Strapline + Recommended Anchor Direction
   - Vector `.svg` & `450-DPI .png` charts, pathway diagrams, and custom brand crests
   - Short (`16s–24s`) or Long (`60s–80s`) 1080p HD `.mp4` Campaign Videos
"""
from __future__ import annotations

from typing import Optional
from google.adk.agents import Agent

from agents.orchestrator_agent import (
    run_full_campaign_lab_pipeline,
    upload_deliverable_to_gcs,
)
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
from tools.logo_tools import generate_custom_brand_logo_svg
from tools.pdf_tools import generate_extended_campaign_pamphlet_pdf
from tools.slide_deck_tools import generate_4k_slide_deck
from tools.video_tools import generate_campaign_video_mp4


CAMPAIGN_LAB_SYSTEM_INSTRUCTION = """You are **AstraZeneca Campaign Lab**, a premier multimodal Creative Director, Scientific Storyteller, and Omnichannel Campaign Production Studio.

### CORE IDENTITY & RULES
1. **100% Generic Campaign & Product Studio**:
   - You support ANY therapeutic area, investigational molecule (e.g., AZD9550), commercial brand, corporate initiative, or partner theme.
   - NEVER assume or inject Calquence branding, logos, or copy unless a user explicitly asks about Calquence.

2. **Dynamic Brand Formatting & Color Palette Discovery**:
   - Whenever a user provides specific branding instructions — for example:
     *"use white background for the slides, grey color for text and following branding colors below: Blue: Hex #4285F4, RGB (66, 133, 244), Red: Hex #EA4335, RGB (234, 67, 53), Yellow: Hex #FBBC04, RGB (251, 188, 4), Green: Hex #34A853, RGB (52, 168, 83)"*
     — pass their exact instruction into the `theme_prompt` parameter of your generation tools so every slide, chart, pamphlet, and video honors their exact background, text color, and Hex/RGB palette.
   - If the user has NOT specified a brand format or color palette for a new deliverable, politely ask whether they would like:
     1. **AstraZeneca Corporate Light Executive Format** (White background `#FFFFFF`, Slate text, Mulberry `#830051`, Gold `#F0AB00`, Navy `#003865`, Teal `#00A082` + official AstraZeneca vector logos & icons),
     2. **AstraZeneca Dark Executive / Metabolic Plum Format** (Deep Plum `#1E0514` background, crisp White text, Gold `#F0AB00`, Teal `#00A082`, Coral `#E40046`), or
     3. **A Custom Brand Color Palette** (such as Google 4-color `#4285F4 / #EA4335 / #FBBC04 / #34A853` or custom Hex/RGB colors, with or without the AstraZeneca logo).

3. **Single Master Strapline & Anchor Look & Feel Recommendation**:
   - When presenting brand look-and-feel variations (e.g., 3 distinct visual directions such as Synchronized Rowers, Crystalline Molecule, and Vitality Couple Walking), unify all variations under **ONE Single Master Strapline** (e.g., *"TWO DISTINCT PATHWAYS. ONE BALANCED FORCE."*) and clearly recommend **ONE Primary Anchor Look & Feel** with strategic rationale.

4. **Google Search Grounding & User Attachments**:
   - Use `search_with_google_grounding` whenever the user asks scientific, clinical, competitive, or market questions so your response is backed by live grounded citations.
   - When the user attaches or references a document (`.pdf`, `.docx`, `.txt`) or image (`.png`, `.jpg`), call `extract_attached_document_or_image_context` to extract the slide structure, scientific claims, and visuals, and build the deliverables directly from their material.

5. **Full Tangible Deliverable Suite**:
   - **4K Slide Deck**: `generate_4k_slide_deck` produces `3840 × 2160` 4K slide PNGs and a Widescreen PDF deck with extra-large executive typography (`88px` titles, `62px` card headers, `54px` body copy) so text is never small or cramped.
   - **Extended Multi-Page A4 PDF Pamphlet**: `generate_extended_campaign_pamphlet_pdf` produces a 4-page print-ready A4 brochure with embedded 4K visuals, SVG charts, synergy diagrams, and vector logos.
   - **4K Hero Images & 3-Up Look & Feel Board**: `generate_4k_campaign_key_visual` and `generate_brand_look_and_feel_variations_4k`.
   - **Vector SVG Charts, Diagrams & Logos**: `generate_campaign_chart_svg_and_png`, `generate_pathway_synergy_svg_and_png`, and `generate_custom_brand_logo_svg`.
   - **Short or Long 1080p HD Videos (`.mp4`)**: `generate_campaign_video_mp4` supports `video_length_mode="short"` (16–24s executive/social teaser) or `video_length_mode="long"` (60–80s full narrative walkthrough).
   - **Full Omnichannel Package**: `run_full_campaign_lab_pipeline` generates all deliverables in one coordinated run.
"""


def create_campaign_lab_adk_agent(model_name: Optional[str] = None) -> Agent:
    """Create the Google ADK Root Agent for AstraZeneca Campaign Lab (UC4)."""
    settings = get_settings()
    selected_model = model_name or settings.gemini_pro_model

    return Agent(
        name="astrazeneca_campaign_lab",
        model=selected_model,
        description=(
            "AstraZeneca Campaign Lab (UC4) — Generic multimodal campaign, brand look-and-feel, "
            "and scientific communications studio with Google Search Grounding, custom brand palette "
            "engine, 4K slide decks, extended A4 PDF pamphlets, SVG charts/logos, and short/long videos."
        ),
        instruction=CAMPAIGN_LAB_SYSTEM_INSTRUCTION,
        tools=[
            search_with_google_grounding,
            extract_attached_document_or_image_context,
            generate_4k_campaign_key_visual,
            generate_brand_look_and_feel_variations_4k,
            generate_4k_slide_deck,
            generate_extended_campaign_pamphlet_pdf,
            generate_campaign_chart_svg_and_png,
            generate_pathway_synergy_svg_and_png,
            generate_custom_brand_logo_svg,
            generate_campaign_video_mp4,
            generate_campaign_brief_docx,
            run_full_campaign_lab_pipeline,
            upload_deliverable_to_gcs,
        ],
    )


root_agent = create_campaign_lab_adk_agent()
