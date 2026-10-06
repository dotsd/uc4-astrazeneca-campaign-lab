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

"""Google ADK Conversational Agent & Artifact Delivery Engine for AstraZeneca Campaign Lab (UC4).

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
5. Full Suite of Tangible Deliverables with 7-Day V4 Signed URLs & Native In-Chat Previews:
   - 4K Widescreen Slide Deck (`3840 × 2160` PNGs + PDF) with extra-large readable fonts
   - Extended Multi-Page A4 Information Pamphlet PDF with graphs, 4K visuals, and logos
   - 3 Brand Look & Feel Variations + Single Master Strapline + Recommended Anchor Direction
   - Vector `.svg` & `450-DPI .png` charts, pathway diagrams, and custom brand crests
   - Short (`16s–24s`) or Long (`60s–80s`) 1080p HD `.mp4` Campaign Videos
"""
from __future__ import annotations

import io
import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional

from google.adk.agents import Agent
from google.cloud import storage

from agents.orchestrator_agent import (
    generate_v4_signed_url,
    run_full_campaign_lab_pipeline,
    upload_deliverable_to_gcs,
    verify_signed_url_preflight,
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

logger = logging.getLogger(__name__)

MAX_INLINE_ARTIFACT_BYTES: int = 5_500_000  # < 5.5 MB inline stream preview cap


def _infer_mime_type(file_path: Path) -> str:
    """Infer canonical MIME type for a generated deliverable."""
    suffix = file_path.suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".mp4": "video/mp4",
        ".json": "application/json",
        ".txt": "text/plain",
    }
    if suffix in mime_map:
        return mime_map[suffix]
    guessed, _ = mimetypes.guess_type(str(file_path))
    return guessed or "application/octet-stream"


def prepare_inline_preview_bytes(file_path: Path) -> bytes:
    """Prepare artifact bytes for in-chat preview, ensuring large videos/images stay < 5.5 MB."""
    raw_bytes = file_path.read_bytes()
    if len(raw_bytes) <= MAX_INLINE_ARTIFACT_BYTES:
        return raw_bytes

    suffix = file_path.suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg"):
        try:
            from PIL import Image

            with Image.open(io.BytesIO(raw_bytes)) as img:
                preview = img.convert("RGB")
                preview.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                preview.save(buf, format="JPEG", quality=85, optimize=True)
                if buf.tell() <= MAX_INLINE_ARTIFACT_BYTES:
                    return buf.getvalue()
        except Exception as img_err:
            logger.debug("Inline image preview compression note: %s", img_err)

    if suffix == ".mp4":
        return raw_bytes[:MAX_INLINE_ARTIFACT_BYTES]

    return raw_bytes


def backfill_gcs_native_artifact(
    payload_bytes: bytes,
    content_type: str,
    filename: str,
    version: int = 0,
    session_id: str = "default",
    user_id: str = "default_user",
    app_name: str = "app",
) -> None:
    """Ensure ADK native artifacts in gs://astrazeneca-ge-pilot-usecase/app/... are never 0-byte placeholders."""
    if not payload_bytes:
        return
    settings = get_settings()
    bucket_name = (
        settings.gcs_assets_bucket.replace("gs://", "").strip("/").split("/")[0]
    )
    try:
        client = storage.Client(project=settings.google_cloud_project)
        bucket = client.bucket(bucket_name)
        candidate_prefixes = ["app"]
        if app_name and app_name not in candidate_prefixes:
            candidate_prefixes.append(app_name)

        for prefix in candidate_prefixes:
            blob_name = f"{prefix}/{user_id}/{session_id}/{filename}/{version}"
            blob = bucket.blob(blob_name)
            needs_upload = True
            try:
                if blob.exists():
                    blob.reload()
                    if (blob.size or 0) > 0:
                        needs_upload = False
            except Exception:
                needs_upload = True

            if needs_upload:
                blob.upload_from_string(
                    data=payload_bytes,
                    content_type=content_type,
                )
                logger.info(
                    "Backfilled non-zero ADK native artifact (%d bytes) -> gs://%s/%s",
                    len(payload_bytes),
                    bucket_name,
                    blob_name,
                )
    except Exception as exc:
        logger.debug("GCS native artifact backfill note: %s", exc)


def upload_to_gcs(
    local_file_path: Path | str,
    session_id: str = "global",
    folder_prefix: str = "deliverables",
) -> str:
    """Upload a local file to `gs://astrazeneca-ge-pilot-usecase/UC4/` and return its 7-day V4 Signed URL."""
    res = upload_deliverable_to_gcs(
        str(local_file_path),
        subfolder=folder_prefix,
        session_id=session_id,
    )
    return res.get("signed_url") or res.get("authenticated_url") or ""


def preserve_verified_signed_urls_callback(
    callback_context: Optional[Any] = None,
    llm_response: Optional[Any] = None,
    **kwargs: Any,
) -> Optional[Any]:
    """Post-model callback hook preserving verified V4 Signed URLs in LLM responses."""
    return llm_response


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
   - **Full Omnichannel Package**: `run_full_campaign_lab_pipeline` generates all deliverables in one coordinated run and uploads them to `gs://astrazeneca-ge-pilot-usecase/UC4/` with 7-day V4 Signed URLs.
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


class AstraZenecaCampaignLabADKAgent:
    """Session-aware conversational orchestrator wrapper for direct Python SDK & ADK invocations."""

    def __init__(
        self,
        session_id: str = "default",
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.session_id = session_id
        self.state: Dict[str, Any] = dict(initial_state or {})
        self.state.setdefault("campaign_name", "New Campaign")
        self.state.setdefault("theme_prompt", "astrazeneca_light")
        self.state.setdefault(
            "master_strapline", "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE."
        )

    def chat(self, prompt: str) -> Dict[str, Any]:
        """Process a synchronous prompt and return response + generated deliverables."""
        lower = prompt.lower()
        theme_prompt = self.state.get("theme_prompt", "astrazeneca_light")
        if "#4285f4" in lower or "google" in lower or "hex #" in lower:
            theme_prompt = prompt
            self.state["theme_prompt"] = theme_prompt
        elif "dark" in lower or "plum" in lower:
            theme_prompt = "astrazeneca_dark"
            self.state["theme_prompt"] = theme_prompt

        video_mode = "long" if "long" in lower and "video" in lower else "short"

        if any(
            k in lower
            for k in ("slide", "pamphlet", "brochure", "video", "look and feel", "campaign")
        ):
            res = run_full_campaign_lab_pipeline(
                campaign_name=self.state.get("campaign_name", "Strategic Campaign"),
                campaign_objective=prompt,
                master_strapline=self.state.get(
                    "master_strapline", "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE."
                ),
                theme_prompt=theme_prompt,
                video_length_mode=video_mode,
                upload_to_gcs=True,
            )
            return {
                "response": (
                    f"Generated the complete **{res['campaign_name']}** deliverables package "
                    f"using theme **{res['theme']['theme_name']}** (`{res['theme']['palette_hex']}`) "
                    f"and Single Master Strapline **\"{res['master_strapline']}\"**."
                ),
                "deliverables": res["deliverables"],
                "gcs_uploads": res["gcs_uploads"],
                "state": self.state,
            }

        grounded = search_with_google_grounding(query=prompt)
        return {
            "response": grounded.get("grounded_answer", ""),
            "citations": grounded.get("citations", []),
            "deliverables": {},
            "state": self.state,
        }


root_agent = create_campaign_lab_adk_agent()
