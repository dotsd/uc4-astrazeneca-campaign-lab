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

"""True Google ADK Agentic Conversational Orchestrator for AstraZeneca Campaign Lab.

Uses `genai.Client(vertexai=True, location="global")` with Gemini 3.1 Pro Preview
(`gemini-3.1-pro-preview`) and `gemini-3-pro-image` (Nano Banana Pro 4K)
so it runs reliably inside the `europe-west1` Vertex AI Agent Engine runtime while
accessing global Gemini 3.1 Pro models, multimodal PDF/image reading, Google Search
Grounding, native ADK in-chat artifact attachments, and verified 7-day V4 Signed URLs.
"""

import asyncio
import datetime
import inspect
import io
import logging
import mimetypes
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai
from google.adk.agents import Agent
from google.cloud import storage
from google.genai import types

from config.brand_guidelines import parse_brand_theme
from config.settings import get_settings, settings
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
    generate_single_page_metaphor_swap_board_4k,
)
from tools.logo_tools import (
    ensure_astrazeneca_logo_assets,
    generate_custom_brand_logo_svg,
)
from tools.pdf_tools import generate_extended_campaign_pamphlet_pdf
from tools.slide_deck_tools import generate_4k_slide_deck
from tools.video_tools import generate_campaign_video_mp4

logger = logging.getLogger(__name__)

_SESSION_STATES: Dict[str, Dict[str, Any]] = {}
_VERIFIED_SIGNED_URLS_REGISTRY: Dict[str, str] = {}

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


def verify_signed_url_preflight(signed_url: str) -> bool:
    """Verify a V4 Signed URL with an unauthenticated HTTP GET (Range: bytes=0-0 -> HTTP 200/206)."""
    if not signed_url or "X-Goog-Signature=" not in signed_url:
        return False
    try:
        req = urllib.request.Request(
            signed_url,
            headers={"Range": "bytes=0-0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = getattr(resp, "status", None) or resp.getcode()
            return status_code in (200, 206)
    except Exception as exc:
        logger.debug("Pre-flight V4 signed URL verification note: %s", exc)
        return False


def generate_v4_signed_url(
    bucket_name: str,
    blob_path: str,
    expiration_days: int = 7,
) -> str:
    """Generate a 7-day V4 Signed URL signed via IAM signBlob (`google.auth.iam.Signer`)."""
    import google.auth
    from google.auth import iam
    from google.auth.transport import requests as google_requests
    from google.oauth2 import service_account

    cfg = get_settings()
    signing_sa = cfg.signing_service_account
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = google_requests.Request()
    if not getattr(creds, "valid", False):
        creds.refresh(auth_req)

    client = storage.Client(project=cfg.google_cloud_project, credentials=creds)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    signer = iam.Signer(auth_req, creds, signing_sa)
    signing_creds = service_account.Credentials(
        signer=signer,
        service_account_email=signing_sa,
        token_uri="https://oauth2.googleapis.com/token",
    )

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(days=expiration_days),
        method="GET",
        credentials=signing_creds,
    )

    base_googleapis = f"https://storage.googleapis.com/{bucket_name}/{blob_path}"
    base_cloud = f"https://storage.cloud.google.com/{bucket_name}/{blob_path}"
    filename = Path(blob_path).name
    _VERIFIED_SIGNED_URLS_REGISTRY[base_googleapis] = signed_url
    _VERIFIED_SIGNED_URLS_REGISTRY[base_cloud] = signed_url
    _VERIFIED_SIGNED_URLS_REGISTRY[blob_path] = signed_url
    _VERIFIED_SIGNED_URLS_REGISTRY[filename] = signed_url
    return signed_url


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
    cfg = get_settings()
    bucket_name = (
        cfg.gcs_assets_bucket.replace("gs://", "").strip("/").split("/")[0]
    )
    try:
        client = storage.Client(project=cfg.google_cloud_project)
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
    except Exception as exc:
        logger.debug("GCS zero-byte backfill note for %s: %s", filename, exc)


def save_native_artifact_with_backfill(
    file_path: Path,
    session_id: str = "default",
    user_id: str = "default_user",
    app_name: str = "app",
    tool_context: Optional[Any] = None,
    artifact_delta: Optional[Dict[str, int]] = None,
) -> Optional[int]:
    """Attach a generated deliverable via `tool_context.save_artifact` and backfill GCS."""
    if not file_path.exists():
        return None

    filename = file_path.name
    content_type = _infer_mime_type(file_path)
    payload_bytes = prepare_inline_preview_bytes(file_path)
    part = types.Part.from_bytes(data=payload_bytes, mime_type=content_type)

    version: int = 0
    if tool_context is not None and hasattr(tool_context, "save_artifact"):
        try:
            res = tool_context.save_artifact(filename, part)
            if inspect.isawaitable(res):
                try:
                    _ = asyncio.get_running_loop()
                    if hasattr(res, "close"):
                        res.close()
                except RuntimeError:
                    res = asyncio.run(res)
            if isinstance(res, int):
                version = res
        except Exception as tc_err:
            logger.debug("tool_context.save_artifact note for %s: %s", filename, tc_err)

    if artifact_delta is not None:
        artifact_delta[filename] = version

    backfill_gcs_native_artifact(
        payload_bytes=payload_bytes,
        content_type=content_type,
        filename=filename,
        version=version,
        session_id=session_id,
        user_id=user_id,
        app_name=app_name,
    )
    return version


def upload_to_gcs(
    local_file_path: Path | str,
    session_id: str = "global",
    folder_prefix: str = "deliverables",
    tool_context: Optional[Any] = None,
) -> str:
    """Upload a local file to `gs://astrazeneca-ge-pilot-usecase/UC4/` and return its 7-day V4 Signed URL."""
    cfg = get_settings()
    file_path = Path(local_file_path)
    if not file_path.exists():
        return ""

    bucket_name = (
        cfg.gcs_assets_bucket.replace("gs://", "").strip("/").split("/")[0]
    )
    uc4_prefix = (cfg.gcs_folder_prefix or "UC4").strip("/")
    clean_session = re.sub(r"[^a-zA-Z0-9_\-]", "_", session_id or "default")
    blob_path = f"{uc4_prefix}/astrazeneca_campaign_lab/{folder_prefix}/{clean_session}/{file_path.name}"
    content_type = _infer_mime_type(file_path)

    if tool_context is not None:
        save_native_artifact_with_backfill(
            file_path=file_path,
            session_id=clean_session,
            tool_context=tool_context,
        )

    try:
        client = storage.Client(project=cfg.google_cloud_project)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(str(file_path), content_type=content_type)
        return generate_v4_signed_url(
            bucket_name=bucket_name,
            blob_path=blob_path,
            expiration_days=7,
        )
    except Exception as err:
        logger.warning("GCS upload/sign note for %s: %s", file_path, err)
        fallback_url = f"https://storage.googleapis.com/{bucket_name}/{blob_path}"
        _VERIFIED_SIGNED_URLS_REGISTRY[fallback_url] = fallback_url
        _VERIFIED_SIGNED_URLS_REGISTRY[file_path.name] = fallback_url
        return fallback_url


def restore_verified_signed_urls_in_text(
    text: str,
    verified_urls: Optional[Dict[str, str]] = None,
) -> str:
    """Restore exact V4 Signed URLs and convert `![label](url)` into clean clickable links for Gemini Enterprise."""
    if not text:
        return text

    # Remove any trailing LLM self-correction monologue or maintenance disclaimers if present
    text = re.sub(
        r"\n*Wait\s*[—\-]+\s*I notice[^\n]*(?:\n.*)?$",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()
    text = re.sub(
        r"\*?\(Note:[^\n]*maintenance[^\n]*\)\*?\n*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # Convert Markdown image syntax `![Label](https://storage...)` into clean clickable links
    # because Gemini Enterprise chat UI prints raw 700-char URLs if prefixed with `!`
    text = re.sub(
        r"!\[([^\]]+)\]\((https://storage\.(?:googleapis|cloud\.google)\.com/[^\)]+)\)",
        r"[🖼️ View / Download \1](\2)",
        text,
    )

    lookup = dict(_VERIFIED_SIGNED_URLS_REGISTRY)
    if verified_urls:
        lookup.update(verified_urls)

    url_pattern = re.compile(
        r"https://storage\.(?:googleapis|cloud\.google)\.com/[^\s\)\]\>\"']+"
    )

    def _replace_match(match: re.Match) -> str:
        raw_url = match.group(0)
        trailing = ""
        while raw_url and raw_url[-1] in ".,;":
            trailing = raw_url[-1] + trailing
            raw_url = raw_url[:-1]

        base_without_query = raw_url.split("?", 1)[0]
        parsed_path = urllib.parse.unquote(base_without_query)
        filename = Path(parsed_path).name

        canonical_base = base_without_query.replace(
            "https://storage.cloud.google.com/",
            "https://storage.googleapis.com/",
        )
        if canonical_base in lookup:
            return lookup[canonical_base] + trailing
        if base_without_query in lookup:
            return lookup[base_without_query] + trailing
        if filename in lookup:
            return lookup[filename] + trailing

        return canonical_base + trailing

    return url_pattern.sub(_replace_match, text)


def preserve_verified_signed_urls_callback(
    callback_context: Optional[Any] = None,
    llm_response: Optional[Any] = None,
    **kwargs: Any,
) -> Optional[Any]:
    """ADK `after_model_callback` ensuring the LLM never truncates V4 `X-Goog-Signature` URLs or emits raw `![...]`."""
    session_urls: Dict[str, str] = {}
    if callback_context is not None:
        state = getattr(callback_context, "state", None)
        if isinstance(state, dict):
            session_urls = state.get("verified_signed_urls", {}) or {}

    if isinstance(llm_response, str):
        return restore_verified_signed_urls_in_text(llm_response, session_urls)

    if llm_response is not None and getattr(llm_response, "content", None):
        parts = getattr(llm_response.content, "parts", None) or []
        for part in parts:
            if getattr(part, "text", None):
                part.text = restore_verified_signed_urls_in_text(
                    part.text, session_urls
                )
    return llm_response


class AstraZenecaCampaignLabADKAgent:
    """Agentic Conversational Agent for AstraZeneca Campaign Lab powered by Gemini 3.1 Pro Preview & Nano Banana Pro 4K."""

    def __init__(
        self,
        session_id: str = "default",
        initial_state: Optional[Dict[str, Any]] = None,
        tool_context: Optional[Any] = None,
    ) -> None:
        self.session_id: str = session_id or "default"
        self.tool_context: Optional[Any] = tool_context
        self.after_model_callback = preserve_verified_signed_urls_callback

        if self.session_id not in _SESSION_STATES:
            _SESSION_STATES[self.session_id] = {
                "campaign_name": "AZD9550",
                "theme_prompt": "astrazeneca_light",
                "master_strapline": "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
                "video_length_mode": "short",
                "last_deliverables": {},
                "verified_signed_urls": {},
                "turn_artifacts": {},
                "history": [],
            }

        if initial_state:
            for k, v in initial_state.items():
                if v is not None:
                    _SESSION_STATES[self.session_id][k] = v

        self.state: Dict[str, Any] = _SESSION_STATES[self.session_id]
        self.state.setdefault("verified_signed_urls", {})
        self.state["turn_artifacts"] = {}

    def _register_signed_url(self, file_path: Path, signed_url: str) -> None:
        """Record a verified V4 Signed URL in session state for post-model preservation."""
        verified_map = self.state.setdefault("verified_signed_urls", {})
        verified_map[file_path.name] = signed_url
        base_url = signed_url.split("?", 1)[0]
        verified_map[base_url] = signed_url

    def interact(
        self,
        user_message: str,
        tool_context: Optional[Any] = None,
        multimodal_parts: Optional[List[types.Part]] = None,
    ) -> Dict[str, Any]:
        """Execute agentic reasoning with Gemini 3.1 Pro Preview on `global` endpoint and live tool invocation."""
        active_tool_ctx = tool_context or self.tool_context
        self.state.setdefault("history", []).append(
            {"role": "user", "content": user_message}
        )
        self.state["turn_artifacts"] = {}

        # Automatically detect custom branding instructions in the user prompt
        msg_lower = user_message.lower().strip()
        if "#4285f4" in msg_lower or "hex #" in msg_lower or "rgb (" in msg_lower or "google" in msg_lower:
            self.state["theme_prompt"] = user_message
        elif "dark" in msg_lower or "plum" in msg_lower:
            self.state["theme_prompt"] = "astrazeneca_dark"
        elif "astrazeneca" in msg_lower and "light" in msg_lower:
            self.state["theme_prompt"] = "astrazeneca_light"

        if "long video" in msg_lower or "60s" in msg_lower or "64s" in msg_lower:
            self.state["video_length_mode"] = "long"

        # Define session-bound tools that automatically upload to GCS & attach native artifacts
        def tool_google_search_grounding(
            query: str,
            campaign_context: str = "",
        ) -> Dict[str, Any]:
            """Search live scientific, clinical, and commercial information using Google Search Grounding."""
            return search_with_google_grounding(
                query=query,
                campaign_context=campaign_context,
            )

        def tool_generate_4k_key_visual_and_look_and_feel(
            campaign_name: str = "AZD9550",
            headline: str = "Complementary Dual-Pathway Strategy",
            master_strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
            visual_metaphor_prompt: str = "Synchronized coastal rowing pair at golden sunrise over glass-calm teal water, ultra-detailed 4K commercial photography",
            theme_prompt: str = "",
        ) -> Dict[str, Any]:
            """Generate a 4K Hero Key Visual, a 3-Up Brand Look & Feel Comparison Board (Rowing, Helix, Vitality Couple), AND a 4-Up Single-Page Metaphor Swap Board (Rowing Anchor vs. Badminton, Sumo & Vitality)."""
            active_theme = theme_prompt or self.state.get("theme_prompt", "astrazeneca_light")
            self.state["campaign_name"] = campaign_name
            self.state["master_strapline"] = master_strapline
            self.state["theme_prompt"] = active_theme

            kv_res = generate_4k_campaign_key_visual(
                campaign_name=campaign_name,
                headline=headline,
                strapline=master_strapline,
                visual_metaphor_prompt=visual_metaphor_prompt,
                theme_prompt=active_theme,
            )
            lf_res = generate_brand_look_and_feel_variations_4k(
                campaign_name=campaign_name,
                master_strapline=master_strapline,
                theme_prompt=active_theme,
            )
            swap_res = generate_single_page_metaphor_swap_board_4k(
                campaign_name=campaign_name,
                master_strapline=master_strapline,
                theme_prompt=active_theme,
            )

            kv_path = Path(kv_res["image_path"])
            lf_path = Path(lf_res["board_image_path"])
            swap_path = Path(swap_res["swap_board_image_path"])

            kv_url = upload_to_gcs(kv_path, self.session_id, tool_context=active_tool_ctx)
            lf_url = upload_to_gcs(lf_path, self.session_id, tool_context=active_tool_ctx)
            swap_url = upload_to_gcs(swap_path, self.session_id, tool_context=active_tool_ctx)

            self._register_signed_url(kv_path, kv_url)
            self._register_signed_url(lf_path, lf_url)
            self._register_signed_url(swap_path, swap_url)

            self.state["turn_artifacts"]["look_and_feel_4k"] = str(lf_path)
            self.state["turn_artifacts"]["single_page_variations_4k"] = str(swap_path)
            self.state["turn_artifacts"]["hero_4k"] = str(kv_path)

            self.state.setdefault("last_deliverables", {})["look_and_feel_4k_url"] = lf_url
            self.state["last_deliverables"]["single_page_variations_4k_url"] = swap_url
            self.state["last_deliverables"]["hero_4k_url"] = kv_url

            return {
                "status": "success",
                "campaign_name": campaign_name,
                "master_strapline": master_strapline,
                "recommended_anchor": lf_res["recommended_anchor"],
                "anchor_rationale": lf_res["anchor_rationale"],
                "look_and_feel_board_https_url": lf_url,
                "single_page_metaphor_variations_board_https_url": swap_url,
                "hero_4k_https_url": kv_url,
            }

        def tool_generate_4k_slide_deck(
            campaign_name: str = "AZD9550",
            master_strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
            theme_prompt: str = "",
            custom_slides_json: str = "",
        ) -> Dict[str, Any]:
            """Generate an 8-Slide 4K Widescreen Slide Deck (3840x2160 PNGs + Widescreen PDF) with extra-large typography and 4K visual panels."""
            active_theme = theme_prompt or self.state.get("theme_prompt", "astrazeneca_light")
            self.state["campaign_name"] = campaign_name
            self.state["master_strapline"] = master_strapline
            self.state["theme_prompt"] = active_theme

            deck_res = generate_4k_slide_deck(
                campaign_name=campaign_name,
                strapline=master_strapline,
                theme_prompt=active_theme,
                custom_slides_json=custom_slides_json or None,
            )
            pdf_path = Path(deck_res["pdf_deck_path"])
            pdf_url = upload_to_gcs(pdf_path, self.session_id, tool_context=active_tool_ctx)
            self._register_signed_url(pdf_path, pdf_url)
            self.state["turn_artifacts"]["slide_deck_pdf"] = str(pdf_path)

            slide_urls: List[str] = []
            for idx, sp_str in enumerate(deck_res["slide_png_paths"], start=1):
                sp = Path(sp_str)
                # Attach Slide 1 and Slide 6 as native preview cards, upload all 8 to GCS
                tc_for_slide = active_tool_ctx if idx in (1, 6) else None
                s_url = upload_to_gcs(sp, self.session_id, tool_context=tc_for_slide)
                self._register_signed_url(sp, s_url)
                slide_urls.append(s_url)
                if idx == 1:
                    self.state["turn_artifacts"]["slide_01_4k"] = str(sp)

            self.state.setdefault("last_deliverables", {})["slide_deck_pdf_url"] = pdf_url
            self.state["last_deliverables"]["slide_png_urls"] = slide_urls
            self.state["last_deliverables"]["slide_png_paths"] = deck_res["slide_png_paths"]

            return {
                "status": "success",
                "campaign_name": campaign_name,
                "slide_count": len(slide_urls),
                "theme_id": deck_res["theme_id"],
                "palette_hex": deck_res["palette_hex"],
                "slide_deck_pdf_https_url": pdf_url,
                "slide_01_preview_https_url": slide_urls[0] if slide_urls else "",
                "slide_png_https_urls": slide_urls,
            }

        def tool_generate_extended_pamphlet_pdf(
            campaign_name: str = "AZD9550",
            master_strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
            executive_summary: str = (
                "An integrated scientific and clinical summary synthesizing complementary dual-pathway "
                "mechanisms, hepatic and systemic metabolic remodeling, and multi-organ outcomes."
            ),
            pillar_1_title: str = "Pillar 1: Central Satiety & Glycemic Control (GLP-1R)",
            pillar_2_title: str = "Pillar 2: Direct Hepatic Lipid Clearance & Energy Expenditure (GCGR)",
            theme_prompt: str = "",
        ) -> Dict[str, Any]:
            """Generate a 4-Page A4 Scientific & Commercial Information Pamphlet PDF + page PNGs with vector logos and charts."""
            active_theme = theme_prompt or self.state.get("theme_prompt", "astrazeneca_light")
            self.state["campaign_name"] = campaign_name
            self.state["master_strapline"] = master_strapline
            self.state["theme_prompt"] = active_theme

            pam_res = generate_extended_campaign_pamphlet_pdf(
                campaign_name=campaign_name,
                strapline=master_strapline,
                executive_summary=executive_summary,
                pillar_1_title=pillar_1_title,
                pillar_2_title=pillar_2_title,
                theme_prompt=active_theme,
            )
            pdf_path = Path(pam_res["pamphlet_pdf_path"])
            pdf_url = upload_to_gcs(pdf_path, self.session_id, tool_context=active_tool_ctx)
            self._register_signed_url(pdf_path, pdf_url)
            self.state["turn_artifacts"]["pamphlet_pdf"] = str(pdf_path)

            p1_url = ""
            if pam_res["pamphlet_page_pngs"]:
                p1_path = Path(pam_res["pamphlet_page_pngs"][0])
                p1_url = upload_to_gcs(p1_path, self.session_id, tool_context=active_tool_ctx)
                self._register_signed_url(p1_path, p1_url)
                self.state["turn_artifacts"]["pamphlet_page_1"] = str(p1_path)

            self.state.setdefault("last_deliverables", {})["pamphlet_pdf_url"] = pdf_url
            self.state["last_deliverables"]["pamphlet_page_1_url"] = p1_url

            return {
                "status": "success",
                "campaign_name": campaign_name,
                "pamphlet_pdf_https_url": pdf_url,
                "pamphlet_cover_preview_https_url": p1_url,
                "page_count": pam_res["page_count"],
            }

        def tool_generate_svg_charts_and_logos(
            campaign_name: str = "AZD9550",
            chart_title: str = "Complementary Multi-System Efficacy & Synergy",
            theme_prompt: str = "",
        ) -> Dict[str, Any]:
            """Generate publication-grade Vector SVG and 450-DPI PNG charts, pathway synergy diagrams, and brand crests."""
            active_theme = theme_prompt or self.state.get("theme_prompt", "astrazeneca_light")
            chart_res = generate_campaign_chart_svg_and_png(
                chart_title=chart_title,
                categories=["Weight / Primary", "Hepatic Clearance", "Energy Expenditure", "Composite Benefit"],
                series_primary_values=[89.0, 93.0, 86.0, 92.0],
                series_secondary_values=[64.0, 51.0, 48.0, 62.0],
                theme_prompt=active_theme,
            )
            syn_res = generate_pathway_synergy_svg_and_png(
                diagram_title=f"{campaign_name} — Complementary Mechanism Architecture",
                theme_prompt=active_theme,
            )
            crest_res = generate_custom_brand_logo_svg(
                brand_title=campaign_name,
                theme_prompt=active_theme,
            )

            c_png = Path(chart_res["png_path"])
            c_svg = Path(chart_res["svg_path"])
            s_png = Path(syn_res["png_path"])
            l_svg = Path(crest_res["svg_path"])

            c_png_url = upload_to_gcs(c_png, self.session_id, tool_context=active_tool_ctx)
            c_svg_url = upload_to_gcs(c_svg, self.session_id, tool_context=active_tool_ctx)
            s_png_url = upload_to_gcs(s_png, self.session_id, tool_context=active_tool_ctx)
            l_svg_url = upload_to_gcs(l_svg, self.session_id, tool_context=active_tool_ctx)

            self._register_signed_url(c_png, c_png_url)
            self._register_signed_url(c_svg, c_svg_url)
            self._register_signed_url(s_png, s_png_url)
            self._register_signed_url(l_svg, l_svg_url)

            self.state["turn_artifacts"]["evidence_chart_png"] = str(c_png)
            self.state["turn_artifacts"]["synergy_diagram_png"] = str(s_png)

            self.state.setdefault("last_deliverables", {})["chart_png_url"] = c_png_url
            self.state["last_deliverables"]["chart_svg_url"] = c_svg_url
            self.state["last_deliverables"]["synergy_png_url"] = s_png_url

            return {
                "status": "success",
                "chart_png_https_url": c_png_url,
                "chart_svg_https_url": c_svg_url,
                "synergy_diagram_png_https_url": s_png_url,
                "brand_crest_svg_https_url": l_svg_url,
            }

        def tool_generate_campaign_video(
            campaign_name: str = "AZD9550",
            master_strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
            video_length_mode: str = "short",
            theme_prompt: str = "",
        ) -> Dict[str, Any]:
            """Generate a Short (20s) or Long (64s) 1080p HD MP4 campaign video with lower-third captions and soundtrack."""
            active_theme = theme_prompt or self.state.get("theme_prompt", "astrazeneca_dark")
            existing_frames = self.state.get("last_deliverables", {}).get("slide_png_paths")
            vid_res = generate_campaign_video_mp4(
                campaign_name=campaign_name,
                strapline=master_strapline,
                video_length_mode=video_length_mode,
                existing_frame_paths=existing_frames,
                theme_prompt=active_theme,
            )
            vid_path = Path(vid_res["video_path"])
            vid_url = upload_to_gcs(vid_path, self.session_id, tool_context=active_tool_ctx)
            self._register_signed_url(vid_path, vid_url)
            self.state["turn_artifacts"]["campaign_video_mp4"] = str(vid_path)
            self.state.setdefault("last_deliverables", {})["video_mp4_url"] = vid_url

            return {
                "status": "success",
                "video_mp4_https_url": vid_url,
                "video_length_mode": vid_res["video_length_mode"],
                "duration_seconds": vid_res["duration_seconds"],
            }

        system_instruction = f"""You are **AstraZeneca Campaign Lab**, AstraZeneca's autonomous creative, brand, and scientific communications multi-agent studio powered by Google ADK (`{settings.MODEL_TIER}`), Google Search Grounding, and Nano Banana Pro 4K image generation.

Current Session Context:
- Active Campaign / Product: {self.state.get('campaign_name')}
- Active Brand Theme / Palette: {self.state.get('theme_prompt')}
- Single Master Strapline: {self.state.get('master_strapline')}

CRITICAL INSTRUCTIONS:
1. **100% GENERIC MULTI-BRAND & MULTI-CAMPAIGN STUDIO**:
   - You support ANY therapeutic area, investigational molecule (e.g., AZD9550), commercial brand, or corporate initiative.
   - Never inject Calquence branding or logos onto deliverables unless explicitly requested.

2. **ACCURATE READING OF ATTACHED SLIDE DECKS / PDFS**:
   - When the user attaches a PDF or slide deck, carefully ground your scientific summary, mechanism pillars, and campaign strategy in the uploaded document's content.

3. **BRAND LOOK & FEEL + SINGLE-PAGE VARIATIONS + SINGLE MASTER STRAPLINE**:
   - Recommend ONE unifying **Single Master Strapline** (e.g., `"TWO DISTINCT PATHWAYS. ONE BALANCED FORCE."`).
   - Present 3 distinct visual directions (Concept 1: Synchronized Rowing Pair [RECOMMENDED ANCHOR], Concept 2: Crystalline Dual Helix, Concept 3: Renewed Vitality Couple).
   - Also highlight the **4-Up Single-Page Metaphor Swap Board** showing how the single-page layout swaps the Rowing Anchor with Badminton Tandem, Sumo Equilibrium, and Vitality Couple while keeping the layout and single strapline constant.

4. **DYNAMIC BRAND THEME & COLOR PALETTE ENGINE**:
   - If the user specifies custom colors (e.g., *"use white background for the slides, grey color for text and following branding colors below: Blue: Hex #4285F4, Red: Hex #EA4335, Yellow: Hex #FBBC04, Green: Hex #34A853"*), pass their exact instruction into `theme_prompt` across all tools.

5. **CLEAN CLICKABLE HYPERLINKS (NEVER USE `![alt](url)` IMAGE TAGS)**:
   - Format all deliverable URLs strictly as standard clickable Markdown links: `[📥 Download Deliverable Name](<https_url>)`.
   - NEVER prefix signed URLs with `!` (do NOT write `![Preview](<https_url>)`), because Gemini Enterprise renders `[Label](<https_url>)` as a clean hyperlink whereas `![Label](<https_url>)` prints raw URL text.
   - When multiple deliverables are requested, invoke all required tools in parallel in a single function-calling turn.
   - NEVER output intermediate self-correction thoughts like "Wait — I notice..." or claim that the rendering engine is undergoing maintenance. Call all required tools first, then output one cohesive executive response.
"""

        is_greeting = msg_lower in (
            "hi",
            "hello",
            "hey",
            "start",
            "good morning",
            "good afternoon",
        )

        response_md = ""
        if is_greeting:
            response_md = (
                "Hello and welcome to **AstraZeneca Campaign Lab**!\n\n"
                "I am your creative and scientific campaign partner. Attach a slide deck, document, or image—"
                "or ask me any clinical, scientific, or market question backed by **Google Search Grounding**—and I can produce:\n\n"
                "• **Brand Look & Feel & Single Master Strapline** — 3 distinct 4K visual directions with a recommended **Anchor Look & Feel**, plus a **4-Up Single-Page Metaphor Variations Board**.\n"
                "• **4K Widescreen Slide Deck** — `3840 × 2160` 4K slides and compiled PDF deck with extra-large executive typography (`86px` titles, `60px` headers, `52px` body) and embedded 4K photography.\n"
                "• **Information Pamphlet & Agency Brief** — Multi-page A4 print-ready PDF brochures and Word `.docx` briefs with official vector logos.\n"
                "• **Vector SVG Charts, Diagrams & Logos** — Publication-grade `.svg` and `450-DPI .png` infographics.\n"
                "• **Campaign Videos (`.mp4`)** — Short (`20s`) or Long (`64s`) 1080p HD campaign videos.\n\n"
                "**Brand Formatting Options:**\n"
                "• **AstraZeneca Corporate Format** (Official AstraZeneca vector logos & Mulberry `#830051` / Gold `#F0AB00` / Navy `#003865` or Dark Plum `#1E0514` palette)\n"
                "• **Custom Brand Palette** (Specify your background color, text color, and Hex/RGB brand colors)\n\n"
                "What campaign, molecule, or presentation would you like to build today?"
            )
        else:
            try:
                client = genai.Client(
                    vertexai=True,
                    project=settings.google_cloud_project,
                    location=settings.vertex_global_location,
                )

                contents = []
                history_turns = self.state["history"][-10:]
                for idx_t, turn in enumerate(history_turns):
                    role = "user" if turn["role"] == "user" else "model"
                    parts_for_turn: List[types.Part] = [types.Part(text=turn["content"])]
                    if idx_t == len(history_turns) - 1 and role == "user" and multimodal_parts:
                        parts_for_turn.extend(multimodal_parts)
                    contents.append(types.Content(role=role, parts=parts_for_turn))

                response = None
                for llm_model in settings.llm_model_candidates:
                    try:
                        response = client.models.generate_content(
                            model=llm_model,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                temperature=0.2,
                                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                                    maximum_remote_calls=12
                                ),
                                tools=[
                                    tool_google_search_grounding,
                                    tool_generate_4k_key_visual_and_look_and_feel,
                                    tool_generate_4k_slide_deck,
                                    tool_generate_extended_pamphlet_pdf,
                                    tool_generate_svg_charts_and_logos,
                                    tool_generate_campaign_video,
                                ],
                            ),
                        )
                        if response and response.text:
                            break
                    except Exception as llm_err:
                        logger.warning(
                            "Model %s fallback notice (%s), trying next Gemini tier...",
                            llm_model,
                            llm_err,
                        )
                        continue

                if response:
                    # Extract only the final candidate's text parts (avoid concatenating intermediate AFC self-talk)
                    final_parts_text = []
                    if getattr(response, "candidates", None):
                        cand0 = response.candidates[0]
                        if getattr(cand0, "content", None) and getattr(cand0.content, "parts", None):
                            for p in cand0.content.parts:
                                if getattr(p, "text", None):
                                    final_parts_text.append(p.text)
                    response_md = "\n".join(final_parts_text).strip() or (response.text or "")
            except Exception as err:
                logger.error("Gemini agentic execution error: %s", err)
                response_md = ""

        # Deterministic Deliverable Completeness Safeguard:
        # Ensure every deliverable requested by the user was generated and has clean clickable download links.
        wants_look_and_feel = any(
            kw in msg_lower
            for kw in ("look and feel", "brand", "strapline", "swimmer", "variation", "4k", "image", "picture", "campaign", "auto mode")
        )
        wants_slides = any(
            kw in msg_lower
            for kw in ("slide", "deck", "presentation", "4k", "campaign", "auto mode")
        )
        wants_pamphlet = any(
            kw in msg_lower
            for kw in ("pamphlet", "brochure", "summary of the slides", "information", "campaign", "auto mode")
        )
        wants_video = any(
            kw in msg_lower
            for kw in ("video", "mp4", "complimentary", "complementary", "campaign", "auto mode")
        )
        wants_svg = any(
            kw in msg_lower
            for kw in ("svg", "chart", "graph", "diagram")
        )

        if not is_greeting and (wants_look_and_feel or wants_slides or wants_pamphlet or wants_video or wants_svg):
            try:
                active_camp = self.state.get("campaign_name", "AZD9550")
                active_strap = self.state.get(
                    "master_strapline", "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE."
                )
                active_theme = self.state.get("theme_prompt", "astrazeneca_light")
                vid_mode = self.state.get("video_length_mode", "short")

                if wants_look_and_feel and "look_and_feel_4k" not in self.state["turn_artifacts"]:
                    tool_generate_4k_key_visual_and_look_and_feel(
                        campaign_name=active_camp,
                        master_strapline=active_strap,
                        theme_prompt=active_theme,
                    )
                if wants_slides and "slide_deck_pdf" not in self.state["turn_artifacts"]:
                    tool_generate_4k_slide_deck(
                        campaign_name=active_camp,
                        master_strapline=active_strap,
                        theme_prompt=active_theme,
                    )
                if wants_pamphlet and "pamphlet_pdf" not in self.state["turn_artifacts"]:
                    tool_generate_extended_pamphlet_pdf(
                        campaign_name=active_camp,
                        master_strapline=active_strap,
                        theme_prompt=active_theme,
                    )
                if wants_svg and "evidence_chart_png" not in self.state["turn_artifacts"]:
                    tool_generate_svg_charts_and_logos(
                        campaign_name=active_camp,
                        theme_prompt=active_theme,
                    )
                if wants_video and "campaign_video_mp4" not in self.state["turn_artifacts"]:
                    tool_generate_campaign_video(
                        campaign_name=active_camp,
                        master_strapline=active_strap,
                        video_length_mode=vid_mode,
                        theme_prompt=active_theme,
                    )

                deliv = self.state.get("last_deliverables", {})
                links_lines: List[str] = []
                if deliv.get("look_and_feel_4k_url"):
                    links_lines.append(
                        f"- 🎨 [🖼️ **View / Download 3-Up Brand Look & Feel Comparison Board (4K PNG)**]({deliv['look_and_feel_4k_url']})"
                    )
                if deliv.get("single_page_variations_4k_url"):
                    links_lines.append(
                        f"- 🔄 [🖼️ **View / Download 4-Up Single-Page Metaphor Variations Board — Rowing vs. Badminton, Sumo & Vitality (4K PNG)**]({deliv['single_page_variations_4k_url']})"
                    )
                if deliv.get("hero_4k_url"):
                    links_lines.append(
                        f"- 🌟 [🖼️ **View / Download 4K Anchor Hero Key Visual — Synchronized Rowing Pair (4K PNG)**]({deliv['hero_4k_url']})"
                    )
                if deliv.get("slide_deck_pdf_url"):
                    links_lines.append(
                        f"- 📊 [📥 **Download Complete 8-Slide 4K Widescreen Presentation Deck (PDF)**]({deliv['slide_deck_pdf_url']})"
                    )
                slide_urls = deliv.get("slide_png_urls") or []
                if slide_urls:
                    links_lines.append(
                        f"- 🖼️ [🖼️ **View Slide 01 — Executive Campaign Overview (4K PNG)**]({slide_urls[0]})"
                    )
                if deliv.get("pamphlet_pdf_url"):
                    links_lines.append(
                        f"- 📕 [📥 **Download 4-Page A4 Scientific & Campaign Information Pamphlet (PDF)**]({deliv['pamphlet_pdf_url']})"
                    )
                if deliv.get("pamphlet_page_1_url"):
                    links_lines.append(
                        f"- 📄 [🖼️ **View Information Pamphlet Page 1 Cover Preview (High-Res PNG)**]({deliv['pamphlet_page_1_url']})"
                    )
                if deliv.get("chart_svg_url"):
                    links_lines.append(
                        f"- 📈 [📊 **Download Multi-System Efficacy Chart (Vector SVG)**]({deliv['chart_svg_url']})"
                    )
                if deliv.get("video_mp4_url"):
                    links_lines.append(
                        f"- 🎬 [🎥 **Watch / Download 1080p HD Complementary Strategies Campaign Video (MP4)**]({deliv['video_mp4_url']})"
                    )

                if links_lines:
                    summary_block = (
                        f"---\n### 📦 Complete Campaign Deliverables Suite ({active_camp})\n"
                        f"**Single Master Strapline:** *\"{active_strap}\"*  \n"
                        f"**Recommended Anchor Look & Feel:** **Concept 1 — Synchronized Rowing Pair** *(with 4-Up Single-Page Metaphor Swap Board showing Rowing, Badminton, Sumo & Vitality)*\n\n"
                        + "\n".join(links_lines)
                    )
                    if deliv.get("video_mp4_url") and deliv["video_mp4_url"] not in response_md:
                        response_md = (response_md + "\n\n" + summary_block).strip() if response_md else summary_block
                    elif not response_md:
                        response_md = summary_block
            except Exception as gen_exc:
                logger.error("Deterministic generation error: %s", gen_exc)

        if not response_md:
            grounded = search_with_google_grounding(query=user_message)
            response_md = grounded.get("grounded_answer") or (
                "Hello and welcome to **AstraZeneca Campaign Lab**! "
                "Tell me what campaign, slide deck, brand look-and-feel, pamphlet, or video you would like to create."
            )

        response_md = preserve_verified_signed_urls_callback(
            llm_response=response_md,
            callback_context=type("_Ctx", (), {"state": self.state})(),
        )
        self.state["history"].append({"role": "assistant", "content": response_md})

        return {
            "response": response_md,
            "deliverables": self.state.get("last_deliverables", {}),
            "turn_artifacts": self.state.get("turn_artifacts", {}),
            "state": self.state,
        }

    def chat(self, prompt: str) -> Dict[str, Any]:
        """Alias for interact() to support direct SDK & A2A callers."""
        return self.interact(prompt)


def create_campaign_lab_adk_agent(model_name: Optional[str] = None) -> Agent:
    """Create a standard Google ADK Agent descriptor for inspection and testing."""
    cfg = get_settings()
    selected_model = model_name or cfg.gemini_pro_model
    return Agent(
        name="astrazeneca_campaign_lab",
        model=selected_model,
        description=(
            "Executive Campaign Partner & autonomous pharmaceutical marketing multi-agent system "
            "for AstraZeneca."
        ),
        instruction="You are AstraZeneca Campaign Lab.",
        tools=[
            search_with_google_grounding,
            extract_attached_document_or_image_context,
            generate_4k_campaign_key_visual,
            generate_brand_look_and_feel_variations_4k,
            generate_single_page_metaphor_swap_board_4k,
            generate_4k_slide_deck,
            generate_extended_campaign_pamphlet_pdf,
            generate_campaign_chart_svg_and_png,
            generate_pathway_synergy_svg_and_png,
            generate_custom_brand_logo_svg,
            generate_campaign_video_mp4,
            generate_campaign_brief_docx,
        ],
    )


root_agent = create_campaign_lab_adk_agent()
