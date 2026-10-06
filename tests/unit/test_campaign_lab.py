"""Comprehensive Unit & Integration Tests for AstraZeneca Campaign Lab (UC4)."""
from __future__ import annotations

from pathlib import Path
from PIL import Image
from pypdf import PdfReader

from config.brand_guidelines import parse_brand_theme
from config.settings import get_settings
from tools.chart_tools import (
    generate_campaign_chart_svg_and_png,
    generate_pathway_synergy_svg_and_png,
)
from tools.grounding_tools import extract_attached_document_or_image_context
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


def test_settings_are_generic_uc4() -> None:
    settings = get_settings()
    assert settings.service_name == "AstraZeneca Campaign Lab"
    assert settings.gcs_folder_prefix == "UC4"
    assert settings.enable_datastore is False
    assert settings.enable_google_grounding is True


def test_google_branding_prompt_parsing() -> None:
    prompt = (
        "use white background for the slides, grey color for text and following branding colors below: "
        "Blue: Hex #4285F4, RGB (66, 133, 244) "
        "Red: Hex #EA4335, RGB (234, 67, 53) "
        "Yellow: Hex #FBBC04, RGB (251, 188, 4) "
        "Green: Hex #34A853, RGB (52, 168, 83)"
    )
    theme = parse_brand_theme(prompt)
    assert theme.background_hex == "#FFFFFF"
    assert theme.text_primary_hex == "#5F6368"
    assert theme.palette_hex == ["#4285F4", "#EA4335", "#FBBC04", "#34A853"]
    assert theme.include_az_logo is False


def test_astrazeneca_presets_and_logos() -> None:
    az_light = parse_brand_theme("astrazeneca_light")
    assert az_light.primary_hex == "#830051"
    assert az_light.include_az_logo is True

    az_dark = parse_brand_theme("astrazeneca_dark")
    assert az_dark.background_hex == "#1E0514"
    assert az_dark.include_az_logo is True

    logos = ensure_astrazeneca_logo_assets()
    assert logos["svg_colour"].exists()
    assert logos["png_symbol_gold"].exists()


def test_svg_charts_and_custom_logo() -> None:
    crest = generate_custom_brand_logo_svg(
        brand_title="AZD9550",
        subtitle="DUAL AGONIST STUDIO",
        theme_prompt="google_brand",
        output_filename="test_google_crest.svg",
    )
    assert Path(crest["svg_path"]).exists()
    assert Path(crest["png_path"]).exists()

    chart = generate_campaign_chart_svg_and_png(
        chart_title="Test Google Palette Chart",
        categories=["A", "B", "C", "D"],
        series_primary_values=[80.0, 85.0, 90.0, 95.0],
        theme_prompt="google_brand",
        output_basename="test_google_chart",
    )
    assert Path(chart["svg_path"]).exists()
    assert Path(chart["png_path"]).exists()

    syn = generate_pathway_synergy_svg_and_png(
        theme_prompt="astrazeneca_dark",
        output_basename="test_az_synergy",
    )
    assert Path(syn["svg_path"]).exists()


def test_4k_slides_and_pamphlet_and_video() -> None:
    google_prompt = (
        "use white background for the slides, grey color for text and following branding colors below: "
        "Blue: Hex #4285F4, Red: Hex #EA4335, Yellow: Hex #FBBC04, Green: Hex #34A853"
    )
    deck = generate_4k_slide_deck(
        campaign_name="Test Generic Campaign",
        theme_prompt=google_prompt,
        output_pdf_filename="test_google_slides_4k.pdf",
    )
    assert Path(deck["pdf_deck_path"]).exists()
    assert deck["slide_count"] >= 4
    first_slide = Path(deck["slide_png_paths"][0])
    with Image.open(first_slide) as im:
        assert im.size == (3840, 2160)

    # Test attachment ingestion on generated PDF
    att = extract_attached_document_or_image_context(deck["pdf_deck_path"])
    assert att["status"] == "success"
    assert att["page_count"] == deck["slide_count"]

    # Test 3-Up Look & Feel Board with Single Strapline
    lf = generate_brand_look_and_feel_variations_4k(
        campaign_name="AZD9550",
        master_strapline="TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
        theme_prompt="astrazeneca_dark",
        output_filename="test_lf_board_4k.png",
    )
    assert Path(lf["board_image_path"]).exists()

    # Test Extended 4-page A4 Pamphlet PDF
    pamphlet = generate_extended_campaign_pamphlet_pdf(
        campaign_name="AZD9550",
        theme_prompt="astrazeneca_light",
        output_filename="test_pamphlet.pdf",
    )
    assert Path(pamphlet["pamphlet_pdf_path"]).exists()
    reader = PdfReader(pamphlet["pamphlet_pdf_path"])
    assert len(reader.pages) == 4

    # Test Short Video generation
    vid = generate_campaign_video_mp4(
        campaign_name="AZD9550",
        video_length_mode="short",
        existing_frame_paths=deck["slide_png_paths"],
        theme_prompt="astrazeneca_dark",
        output_filename="test_short_video.mp4",
    )
    assert Path(vid["video_path"]).exists()
    assert vid["video_length_mode"] == "short"
