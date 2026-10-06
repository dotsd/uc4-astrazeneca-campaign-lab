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

"""Production Tools Package for AstraZeneca Campaign Lab (UC4)."""
from __future__ import annotations

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
    draw_svg_on_reportlab_canvas,
    ensure_astrazeneca_logo_assets,
    generate_custom_brand_logo_svg,
    get_pil_logo_for_theme,
)
from tools.pdf_tools import generate_extended_campaign_pamphlet_pdf
from tools.slide_deck_tools import generate_4k_slide_deck
from tools.video_tools import generate_campaign_video_mp4

__all__ = [
    "ensure_astrazeneca_logo_assets",
    "generate_custom_brand_logo_svg",
    "get_pil_logo_for_theme",
    "draw_svg_on_reportlab_canvas",
    "search_with_google_grounding",
    "extract_attached_document_or_image_context",
    "generate_campaign_chart_svg_and_png",
    "generate_pathway_synergy_svg_and_png",
    "generate_4k_campaign_key_visual",
    "generate_brand_look_and_feel_variations_4k",
    "generate_4k_slide_deck",
    "generate_extended_campaign_pamphlet_pdf",
    "generate_campaign_video_mp4",
    "generate_campaign_brief_docx",
]
