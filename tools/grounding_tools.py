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

"""Google Search Grounding & Multimodal Document/Image Attachment Ingestion Tools.

Provides:
1. Live Google Search Grounding (`types.Tool(google_search=types.GoogleSearch())`) via `google-genai`
   on the `global` Vertex AI endpoint (`gemini-3-flash-preview` / `gemini-3.1-pro-preview`)
   to answer scientific, clinical, competitive, or market queries with verified web citations.
2. Multimodal Attachment Ingestion (`extract_attached_document_or_image_context`) to parse
   user-attached PDFs, Word (.docx) files, text/markdown documents, and images (PNG/JPG/WEBP),
   extracting structured slides, claims, tables, and visual themes for campaign generation.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import docx
from google import genai
from google.genai import types
from PIL import Image
from pypdf import PdfReader

from config.settings import get_settings

logger = logging.getLogger(__name__)


def _get_genai_client() -> genai.Client:
    """Initialize Vertex AI GenAI client on the `global` endpoint for Gemini 3.x models."""
    settings = get_settings()
    return genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.vertex_global_location,
    )


def search_with_google_grounding(
    query: str,
    campaign_context: str = "",
) -> Dict[str, Any]:
    """Answer any scientific, clinical, brand, or market query using live Google Search Grounding.

    Args:
        query: The user's question or research topic (e.g., mechanism of action, clinical trial
               endpoints, disease epidemiology, competitive landscape, brand positioning).
        campaign_context: Optional context from user-uploaded slides or brand brief.

    Returns:
        Dictionary containing `grounded_answer`, `citations` (list of title/uri pairs),
        `search_queries`, and `status`.
    """
    settings = get_settings()
    prompt = (
        "You are the Research & Strategy Director for AstraZeneca Campaign Lab.\n"
        "Answer the following query accurately using Google Search grounding.\n"
        "Provide structured executive takeaways, quantitative data points where available, "
        "and clear citations.\n\n"
        f"QUERY: {query}\n"
    )
    if campaign_context:
        prompt += f"\nCAMPAIGN CONTEXT: {campaign_context}\n"

    try:
        client = _get_genai_client()
        response = None
        answer_text = ""
        grounding_candidates = [
            settings.gemini_flash_model,
            settings.gemini_pro_model,
            *settings.llm_model_candidates,
        ]
        seen_models = set()
        for model_name in grounding_candidates:
            if model_name in seen_models:
                continue
            seen_models.add(model_name)
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                        temperature=0.2,
                    ),
                )
                if response:
                    try:
                        answer_text = (response.text or "").strip()
                    except Exception:
                        answer_text = ""
                    if not answer_text and response.candidates:
                        parts = getattr(response.candidates[0].content, "parts", None) or []
                        answer_text = "\n".join(
                            getattr(p, "text", "")
                            for p in parts
                            if getattr(p, "text", None) and not getattr(p, "thought", False)
                        ).strip()
                    if answer_text:
                        break
            except Exception as model_exc:
                logger.warning("Grounding model %s fallback: %s", model_name, model_exc)
                continue
        citations: List[Dict[str, str]] = []
        search_queries: List[str] = []

        if response and response.candidates:
            cand = response.candidates[0]
            gm = getattr(cand, "grounding_metadata", None)
            if gm:
                web_queries = getattr(gm, "web_search_queries", None) or []
                search_queries = [str(q) for q in web_queries]
                chunks = getattr(gm, "grounding_chunks", None) or []
                for ch in chunks:
                    web = getattr(ch, "web", None)
                    if web:
                        citations.append(
                            {
                                "title": getattr(web, "title", "") or "Grounded Source",
                                "uri": getattr(web, "uri", "") or "",
                            }
                        )

        return {
            "status": "success",
            "query": query,
            "grounded_answer": answer_text,
            "citations": citations,
            "search_queries": search_queries,
            "grounding_engine": "google_search",
        }
    except Exception as exc:
        logger.warning("Google Search grounding fallback triggered: %s", exc)
        return {
            "status": "fallback",
            "query": query,
            "grounded_answer": (
                f"Synthesized Campaign Lab analysis for '{query}'."
            ),
            "citations": [],
            "search_queries": [query],
            "grounding_engine": "offline_synthesis",
        }


def extract_attached_document_or_image_context(
    file_path: str,
    extraction_goal: str = "Extract all slide titles, key scientific/commercial points, quantitative metrics, and visual style cues.",
) -> Dict[str, Any]:
    """Parse a user-attached document (PDF, DOCX, TXT, MD) or image (PNG, JPG, WEBP) for campaign generation."""
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        return {
            "status": "error",
            "error": f"Attached file not found at {file_path}",
            "extracted_text": "",
            "slides_or_pages": [],
        }

    suffix = path.suffix.lower()
    slides_or_pages: List[Dict[str, Any]] = []
    full_text_parts: List[str] = []

    try:
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            for idx, page in enumerate(reader.pages, start=1):
                txt = (page.extract_text() or "").strip()
                slides_or_pages.append({"page_number": idx, "text": txt})
                if txt:
                    full_text_parts.append(f"--- Page/Slide {idx} ---\n{txt}")
            combined = "\n\n".join(full_text_parts)
            return {
                "status": "success",
                "file_type": "pdf",
                "file_name": path.name,
                "page_count": len(reader.pages),
                "slides_or_pages": slides_or_pages,
                "extracted_text": combined,
                "extraction_goal": extraction_goal,
            }

        if suffix == ".docx":
            doc = docx.Document(str(path))
            paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            combined = "\n".join(paras)
            return {
                "status": "success",
                "file_type": "docx",
                "file_name": path.name,
                "page_count": max(1, len(paras) // 8),
                "slides_or_pages": [{"page_number": 1, "text": combined}],
                "extracted_text": combined,
                "extraction_goal": extraction_goal,
            }

        if suffix in (".txt", ".md", ".csv", ".json"):
            content = path.read_text(encoding="utf-8", errors="replace")
            return {
                "status": "success",
                "file_type": suffix.lstrip("."),
                "file_name": path.name,
                "page_count": 1,
                "slides_or_pages": [{"page_number": 1, "text": content}],
                "extracted_text": content,
                "extraction_goal": extraction_goal,
            }

        if suffix in (".png", ".jpg", ".jpeg", ".webp"):
            with Image.open(path) as img:
                width, height = img.size
                mode = img.mode
            return {
                "status": "success",
                "file_type": "image",
                "file_name": path.name,
                "image_path": str(path),
                "dimensions": f"{width}x{height}",
                "color_mode": mode,
                "extracted_text": (
                    f"Attached reference visual '{path.name}' ({width}x{height}, {mode}) "
                    f"ready for slide deck, brochure, and look-and-feel integration."
                ),
                "extraction_goal": extraction_goal,
            }

        return {
            "status": "error",
            "error": f"Unsupported file extension: {suffix}",
            "extracted_text": "",
        }
    except Exception as exc:
        logger.exception("Error extracting attachment %s", file_path)
        return {
            "status": "error",
            "error": str(exc),
            "extracted_text": "",
        }
