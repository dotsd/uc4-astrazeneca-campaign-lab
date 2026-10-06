"""Production Tools Package for AstraZeneca Campaign Lab (UC4)."""
from tools.logo_tools import (
    ensure_astrazeneca_logo_assets,
    generate_custom_brand_logo_svg,
    get_pil_logo_for_theme,
    draw_svg_on_reportlab_canvas,
)
from tools.grounding_tools import (
    search_with_google_grounding,
    extract_attached_document_or_image_context,
)
from tools.chart_tools import (
    generate_campaign_chart_svg_and_png,
    generate_pathway_synergy_svg_and_png,
)
from tools.image_tools import (
    generate_4k_campaign_key_visual,
    generate_brand_look_and_feel_variations_4k,
)
from tools.slide_deck_tools import generate_4k_slide_deck
from tools.pdf_tools import generate_extended_campaign_pamphlet_pdf
from tools.video_tools import generate_campaign_video_mp4
from tools.docx_tools import generate_campaign_brief_docx

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
