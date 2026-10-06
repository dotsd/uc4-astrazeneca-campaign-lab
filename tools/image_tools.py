"""4K Key Visuals, Single-Page Brand Look & Feel Variations, and Master Strapline Engine (UC4).

Generates:
1. 4K Ultra-HD Hero Key Visuals (`3840 × 2160` 16:9 widescreen or `2480 × 3508` A4 poster)
   using `gemini-3-pro-image` (with deterministic high-res artistic fallback if offline).
2. Single-Page Brand Look & Feel Variations (e.g., 3 distinct metaphors such as Synchronized Rowers,
   Crystalline Molecule, Couple Walking / Vitality Horizon, or custom metaphors) with a Single Master
   Strapline and Anchor Look & Feel Recommendation.
3. 3-Up Brand Look & Feel Comparison Board (`3840 × 2160` 4K).
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config.brand_guidelines import BrandTheme, parse_brand_theme
from config.settings import get_settings
from tools.logo_tools import get_pil_logo_for_theme

logger = logging.getLogger(__name__)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load clean system sans-serif font at the requested pixel size."""
    candidates = (
        [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    )
    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: Any, max_width: int) -> List[str]:
    """Wrap text to fit within max_width pixels."""
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _generate_artistic_4k_canvas(
    prompt: str,
    theme: BrandTheme,
    size: Tuple[int, int] = (3840, 2160),
) -> Image.Image:
    """Generate a 4K artistic base image via Gemini Image model or high-craft gradient/geometric studio."""
    settings = get_settings()
    try:
        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.vertex_global_location,
        )
        resp = client.models.generate_images(
            model=settings.gemini_image_model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9" if size[0] >= size[1] else "3:4",
                safety_filter_level="BLOCK_MEDIUM_AND_ABOVE",
            ),
        )
        if resp.generated_images:
            raw_bytes = resp.generated_images[0].image.image_bytes
            img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            return img.resize(size, Image.Resampling.LANCZOS)
    except Exception as exc:
        logger.info("Using deterministic 4K studio canvas for prompt (%s)", exc)

    # High-craft deterministic 4K studio background
    w, h = size
    base = Image.new("RGB", (w, h), theme.background_rgb)
    draw = ImageDraw.Draw(base, "RGBA")

    p_r, p_g, p_b = theme.primary_rgb
    s_r, s_g, s_b = theme.secondary_rgb
    a_r, a_g, a_b = theme.accent_rgb

    # Smooth diagonal luminous ribbons
    for i in range(18):
        alpha = int(28 + (i % 5) * 8)
        offset = i * (w // 16)
        draw.polygon(
            [
                (offset - 400, 0),
                (offset + 260, 0),
                (offset - 200, h),
                (offset - 860, h),
            ],
            fill=(p_r, p_g, p_b, alpha if i % 2 == 0 else alpha // 2),
        )
    # Glowing orbs
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay, "RGBA")
    odraw.ellipse((int(w * 0.52), int(h * 0.12), int(w * 0.94), int(h * 0.88)), fill=(s_r, s_g, s_b, 85))
    odraw.ellipse((int(w * 0.60), int(h * 0.22), int(w * 0.88), int(h * 0.78)), fill=(a_r, a_g, a_b, 95))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=65))
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    return base


def generate_4k_campaign_key_visual(
    campaign_name: str,
    headline: str,
    strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
    visual_metaphor_prompt: str = "Synchronized coastal rowing pair at golden sunrise over glass-calm teal water, ultra-detailed 4K commercial photography",
    key_callouts: Optional[List[str]] = None,
    theme_prompt: str = "astrazeneca_dark",
    include_az_logo: Optional[bool] = None,
    reference_image_path: Optional[str] = None,
    output_filename: str = "campaign_hero_key_visual_4k.png",
) -> Dict[str, Any]:
    """Generate a 4K (`3840 × 2160`) Hero Key Visual with strapline, callouts, and optional logo."""
    settings = get_settings()
    theme = parse_brand_theme(theme_prompt, include_az_logo=include_az_logo)
    w, h = (3840, 2160)

    if reference_image_path and Path(reference_image_path).exists():
        art_img = Image.open(reference_image_path).convert("RGB").resize((w, h), Image.Resampling.LANCZOS)
    else:
        art_img = _generate_artistic_4k_canvas(visual_metaphor_prompt, theme, size=(w, h))

    canvas_img = art_img.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    # Left editorial scrim for crisp typography
    bg_r, bg_g, bg_b = theme.background_rgb
    scrim_alpha = 235 if not theme.is_dark_mode else 220
    draw.rounded_rectangle(
        (110, 110, 1980, h - 110),
        radius=44,
        fill=(bg_r, bg_g, bg_b, scrim_alpha),
        outline=(*theme.primary_rgb, 255),
        width=6,
    )

    # Top accent colour bar (supports 4-color Google bar or AstraZeneca bar)
    palette = theme.palette_hex or [theme.primary_hex, theme.secondary_hex, theme.accent_hex, theme.success_hex]
    seg_w = (1980 - 110) // len(palette)
    for idx, hx in enumerate(palette):
        x0 = 110 + idx * seg_w
        x1 = 1980 if idx == len(palette) - 1 else x0 + seg_w
        from config.brand_guidelines import hex_to_rgb
        draw.rectangle((x0, 110, x1, 134), fill=(*hex_to_rgb(hx), 255))

    f_kicker = _load_font(44, bold=True)
    f_head = _load_font(86, bold=True)
    f_strap = _load_font(48, bold=True)
    f_body = _load_font(44, bold=False)
    f_foot = _load_font(32, bold=False)

    # Campaign Kicker
    draw.text(
        (190, 195),
        campaign_name.upper()[:52],
        font=f_kicker,
        fill=(*theme.primary_rgb, 255),
    )

    # Headline
    y_cur = 285
    for line in _wrap_text(draw, headline, f_head, 1680)[:3]:
        draw.text((190, y_cur), line, font=f_head, fill=(*theme.text_primary_rgb, 255))
        y_cur += 104

    # Single Master Strapline Pill
    y_cur += 28
    draw.rounded_rectangle(
        (190, y_cur, 1880, y_cur + 108),
        radius=24,
        fill=(*theme.primary_rgb, 255),
    )
    draw.text(
        (235, y_cur + 26),
        strapline[:58],
        font=f_strap,
        fill=(255, 255, 255, 255),
    )
    y_cur += 160

    # Key Callout Bullets
    callouts = key_callouts or [
        "Complementary dual-pathway synergy driving durable outcomes",
        "High-contrast executive typography & custom brand palette adherence",
        "Grounded clinical & commercial narrative ready for omnichannel launch",
    ]
    for idx, item in enumerate(callouts[:4]):
        col_hex = palette[idx % len(palette)]
        from config.brand_guidelines import hex_to_rgb
        dot_rgb = hex_to_rgb(col_hex)
        draw.ellipse((195, y_cur + 12, 231, y_cur + 48), fill=(*dot_rgb, 255))
        for b_line in _wrap_text(draw, item, f_body, 1580)[:2]:
            draw.text((260, y_cur), b_line, font=f_body, fill=(*theme.text_primary_rgb, 255))
            y_cur += 58
        y_cur += 28

    # Compliance footer
    draw.text(
        (190, h - 185),
        theme.compliance_footer,
        font=f_foot,
        fill=(*theme.text_secondary_rgb, 255),
    )

    composed = Image.alpha_composite(canvas_img, overlay)

    # Paste official AstraZeneca logo if enabled in theme
    logo_img = get_pil_logo_for_theme(theme, max_height=96)
    if logo_img is not None:
        composed.paste(logo_img, (1880 - logo_img.width, h - 225), logo_img)

    out_path = settings.output_dir / output_filename
    composed.convert("RGB").save(out_path, format="PNG", optimize=True)

    return {
        "status": "success",
        "image_path": str(out_path),
        "dimensions": "3840x2160 (4K UHD)",
        "campaign_name": campaign_name,
        "strapline": strapline,
        "theme_id": theme.theme_id,
        "included_az_logo": theme.include_az_logo,
    }


def generate_brand_look_and_feel_variations_4k(
    campaign_name: str,
    master_strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
    variation_1_title: str = "Look & Feel 1 (Recommended Anchor): Synchronized Tandem",
    variation_1_subtitle: str = "Two distinct forces moving in precision harmony toward one shared horizon",
    variation_2_title: str = "Look & Feel 2: Crystalline Molecular Convergence",
    variation_2_subtitle: str = "Dual-receptor structural brilliance fusing gold and teal pathways",
    variation_3_title: str = "Look & Feel 3: Human Vitality & Shared Stride",
    variation_3_subtitle: str = "Sustained real-world patient freedom and multi-organ systemic well-being",
    anchor_recommendation_rationale: str = (
        "Look & Feel 1 (Synchronized Tandem) is recommended as the Primary Anchor Look & Feel "
        "because it immediately communicates complementary dual action in a single human glance, "
        "while scaling effortlessly across congress booths, digital slides, and print brochures."
    ),
    theme_prompt: str = "astrazeneca_dark",
    include_az_logo: Optional[bool] = None,
    output_filename: str = "brand_look_and_feel_comparison_4k.png",
) -> Dict[str, Any]:
    """Generate a 4K (`3840 × 2160`) 3-Up Brand Look & Feel Comparison Board with a Single Master Strapline."""
    settings = get_settings()
    theme = parse_brand_theme(theme_prompt, include_az_logo=include_az_logo)
    w, h = (3840, 2160)

    board = Image.new("RGBA", (w, h), (*theme.background_rgb, 255))
    draw = ImageDraw.Draw(board, "RGBA")

    f_title = _load_font(76, bold=True)
    f_strap = _load_font(46, bold=True)
    f_card_h = _load_font(48, bold=True)
    f_card_b = _load_font(38, bold=False)
    f_rec = _load_font(40, bold=True)

    # Header
    draw.text(
        (140, 95),
        f"{campaign_name.upper()} — 3 BRAND LOOK & FEEL DIRECTIONS",
        font=f_title,
        fill=(*theme.text_primary_rgb, 255),
    )

    # Single Master Strapline Banner across top
    draw.rounded_rectangle(
        (140, 205, w - 140, 305),
        radius=22,
        fill=(*theme.primary_rgb, 255),
    )
    draw.text(
        (185, 228),
        f"SINGLE MASTER STRAPLINE:  \"{master_strapline}\"",
        font=f_strap,
        fill=(255, 255, 255, 255),
    )

    variations = [
        (variation_1_title, variation_1_subtitle, theme.primary_hex, True),
        (variation_2_title, variation_2_subtitle, theme.secondary_hex, False),
        (variation_3_title, variation_3_subtitle, theme.accent_hex, False),
    ]

    card_w = 1120
    gap = 60
    start_x = 140
    card_top = 355
    card_bottom = 1720

    from config.brand_guidelines import hex_to_rgb

    for idx, (v_title, v_sub, accent_hx, is_anchor) in enumerate(variations):
        x0 = start_x + idx * (card_w + gap)
        x1 = x0 + card_w
        acc_rgb = hex_to_rgb(accent_hx)

        draw.rounded_rectangle(
            (x0, card_top, x1, card_bottom),
            radius=34,
            fill=(*theme.card_background_rgb, 255),
            outline=(*acc_rgb, 255),
            width=8 if is_anchor else 4,
        )

        # Visual preview header inside card
        art_preview = _generate_artistic_4k_canvas(v_title + " " + v_sub, theme, size=(card_w - 40, 560))
        board.paste(art_preview.convert("RGBA"), (x0 + 20, card_top + 20))

        if is_anchor:
            draw.rounded_rectangle(
                (x0 + 45, card_top + 45, x0 + 620, card_top + 115),
                radius=16,
                fill=(*acc_rgb, 255),
            )
            draw.text(
                (x0 + 70, card_top + 58),
                "★ RECOMMENDED ANCHOR",
                font=_load_font(34, bold=True),
                fill=(255, 255, 255, 255),
            )

        # Card Title
        ty = card_top + 620
        for line in _wrap_text(draw, v_title, f_card_h, card_w - 90)[:2]:
            draw.text((x0 + 45, ty), line, font=f_card_h, fill=(*theme.text_primary_rgb, 255))
            ty += 58

        # Strapline lockup on each card
        ty += 20
        draw.rounded_rectangle(
            (x0 + 45, ty, x1 - 45, ty + 82),
            radius=16,
            fill=(*acc_rgb, 45),
            outline=(*acc_rgb, 255),
            width=3,
        )
        draw.text(
            (x0 + 70, ty + 20),
            master_strapline[:42],
            font=_load_font(34, bold=True),
            fill=(*theme.text_primary_rgb, 255),
        )
        ty += 115

        # Description
        for line in _wrap_text(draw, v_sub, f_card_b, card_w - 90)[:4]:
            draw.text((x0 + 45, ty), line, font=f_card_b, fill=(*theme.text_secondary_rgb, 255))
            ty += 50

    # Bottom Anchor Recommendation Box
    draw.rounded_rectangle(
        (140, 1765, w - 140, 2040),
        radius=28,
        fill=(*theme.card_background_rgb, 255),
        outline=(*theme.primary_rgb, 255),
        width=5,
    )
    ry = 1800
    for line in _wrap_text(draw, f"AGENCY RECOMMENDATION: {anchor_recommendation_rationale}", f_rec, w - 380)[:3]:
        draw.text((185, ry), line, font=f_rec, fill=(*theme.text_primary_rgb, 255))
        ry += 54

    logo_img = get_pil_logo_for_theme(theme, max_height=82)
    if logo_img is not None:
        board.paste(logo_img, (w - 160 - logo_img.width, 95), logo_img)

    out_path = settings.output_dir / output_filename
    board.convert("RGB").save(out_path, format="PNG", optimize=True)

    return {
        "status": "success",
        "board_image_path": str(out_path),
        "master_strapline": master_strapline,
        "recommended_anchor": variation_1_title,
        "anchor_rationale": anchor_recommendation_rationale,
        "theme_id": theme.theme_id,
    }
