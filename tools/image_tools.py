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

"""4K Key Visuals, Single-Page Brand Look & Feel Variations, and Master Strapline Engine.

Generates:
1. 4K Ultra-HD Hero Key Visuals (`3840 × 2160` 16:9 widescreen) using curated 4K Nano Banana Pro
   photographic assets and live Vertex AI image generation.
2. 3-Up Brand Look & Feel Comparison Board (`3840 × 2160` 4K) comparing 3 distinct creative directions
   (Synchronized Rowing Pair, Crystalline Dual Agonist Molecule, Vitality Couple Walking) under a
   Single Master Strapline with an Anchor Look & Feel Recommendation.
3. 4-Up Single-Page Look & Feel Variations Board (`3840 × 2160` 4K) demonstrating how a single page
   layout swaps metaphors (Rowing Anchor, Badminton Tandem, Sumo Equilibrium, Vitality Horizon).
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageOps

from config.brand_guidelines import (
    BrandTheme,
    hex_to_rgb,
    load_scalable_font,
    parse_brand_theme,
    resolve_gallery_image,
)
from config.settings import get_settings
from tools.logo_tools import get_pil_logo_for_theme

logger = logging.getLogger(__name__)


def _load_font(size: int, bold: bool = False):
    """Load a guaranteed scalable TrueType font at `size` pixels on both Linux and macOS."""
    return load_scalable_font(size=size, bold=bold)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: Any, max_width: int) -> List[str]:
    """Wrap text to fit within `max_width` pixels."""
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
    prefer_gallery: bool = True,
) -> Image.Image:
    """Resolve a 4K photographic visual from the curated Nano Banana Pro gallery or live Vertex AI."""
    if prefer_gallery:
        gallery_path = resolve_gallery_image(prompt)
        if gallery_path and gallery_path.exists():
            try:
                img = Image.open(gallery_path).convert("RGB")
                return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)
            except Exception as exc:
                logger.debug("Gallery load note for %s: %s", gallery_path, exc)

    settings = get_settings()
    try:
        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.vertex_global_location,
        )
        for img_model_name in settings.image_model_candidates:
            try:
                result = client.models.generate_content(
                    model=img_model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"]
                    ),
                )
                if (
                    result.candidates
                    and result.candidates[0].content
                    and result.candidates[0].content.parts
                ):
                    for part in result.candidates[0].content.parts:
                        if getattr(part, "inline_data", None) and part.inline_data.data:
                            img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
                            return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)
            except Exception as model_exc:
                logger.debug("Image model %s fallback (%s)", img_model_name, model_exc)
                continue
    except Exception as exc:
        logger.debug("Live image model fallback to gallery (%s)", exc)

    gallery_path = resolve_gallery_image(prompt)
    if gallery_path and gallery_path.exists():
        img = Image.open(gallery_path).convert("RGB")
        return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)

    return Image.new("RGB", size, theme.background_rgb)


def generate_4k_campaign_key_visual(
    campaign_name: str = "Complementary Dual-Pathway Campaign",
    headline: str = "Complementary Strategies for the Next Era of Weight Management",
    strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
    visual_metaphor_prompt: str = "rowing pair synchronized sunrise water",
    key_callouts: Optional[List[str]] = None,
    theme_prompt: str = "astrazeneca_dark",
    include_az_logo: Optional[bool] = None,
    reference_image_path: Optional[str] = None,
    output_filename: str = "campaign_hero_key_visual_4k.png",
) -> Dict[str, Any]:
    """Generate a 4K (`3840 × 2160`) Hero Key Visual with extra-large executive typography and single strapline."""
    settings = get_settings()
    theme = parse_brand_theme(theme_prompt, include_az_logo=include_az_logo)
    w, h = (3840, 2160)

    if reference_image_path and Path(reference_image_path).exists():
        art_img = ImageOps.fit(
            Image.open(reference_image_path).convert("RGB"),
            (w, h),
            method=Image.Resampling.LANCZOS,
        )
    else:
        art_img = _generate_artistic_4k_canvas(visual_metaphor_prompt, theme, size=(w, h))

    canvas_img = art_img.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    # Left editorial scrim for crisp, high-contrast executive typography
    bg_r, bg_g, bg_b = theme.background_rgb
    scrim_alpha = 238 if not theme.is_dark_mode else 224
    draw.rounded_rectangle(
        (100, 100, 1980, h - 100),
        radius=44,
        fill=(bg_r, bg_g, bg_b, scrim_alpha),
        outline=(*theme.primary_rgb, 255),
        width=8,
    )

    # Top accent colour bar (supports 4-color Google bar or AstraZeneca bar)
    palette = theme.palette_hex or [
        theme.primary_hex,
        theme.secondary_hex,
        theme.accent_hex,
        theme.success_hex,
    ]
    seg_w = (1980 - 100) // len(palette)
    for idx, hx in enumerate(palette):
        x0 = 100 + idx * seg_w
        x1 = 1980 if idx == len(palette) - 1 else x0 + seg_w
        draw.rectangle((x0, 100, x1, 132), fill=(*hex_to_rgb(hx), 255))

    f_kicker = _load_font(48, bold=True)
    f_head = _load_font(86, bold=True)
    f_strap = _load_font(48, bold=True)
    f_body = _load_font(46, bold=False)
    f_foot = _load_font(34, bold=False)

    # Campaign Kicker
    draw.text(
        (170, 185),
        f"{campaign_name.upper()}  ·  ANCHOR KEY VISUAL"[:54],
        font=f_kicker,
        fill=(*theme.primary_rgb, 255),
    )

    # Headline
    y_cur = 275
    for line in _wrap_text(draw, headline, f_head, 1700)[:3]:
        draw.text((170, y_cur), line, font=f_head, fill=(*theme.text_primary_rgb, 255))
        y_cur += 104

    # Single Master Strapline Pill
    y_cur += 28
    draw.rounded_rectangle(
        (170, y_cur, 1900, y_cur + 114),
        radius=26,
        fill=(*theme.primary_rgb, 255),
    )
    draw.text(
        (215, y_cur + 28),
        strapline[:58],
        font=f_strap,
        fill=(255, 255, 255, 255),
    )
    y_cur += 165

    # Key Callout Bullets
    callouts = key_callouts or [
        "GLP-1 Receptor Pathway: Central satiety, glycemic control & reduced caloric intake",
        "Glucagon Receptor Pathway: Increased energy expenditure, lipolysis & hepatic fat clearance",
        "Complementary Dual Agonism: Superior weight loss quality & multi-organ cardiometabolic benefit",
    ]
    for idx, item in enumerate(callouts[:4]):
        col_hex = palette[idx % len(palette)]
        dot_rgb = hex_to_rgb(col_hex)
        draw.ellipse((175, y_cur + 12, 215, y_cur + 52), fill=(*dot_rgb, 255))
        for b_line in _wrap_text(draw, item, f_body, 1620)[:2]:
            draw.text((245, y_cur), b_line, font=f_body, fill=(*theme.text_primary_rgb, 255))
            y_cur += 60
        y_cur += 32

    # Compliance footer
    draw.text(
        (170, h - 180),
        theme.compliance_footer,
        font=f_foot,
        fill=(*theme.text_secondary_rgb, 255),
    )

    composed = Image.alpha_composite(canvas_img, overlay)

    logo_img = get_pil_logo_for_theme(theme, max_height=96)
    if logo_img is not None:
        composed.paste(logo_img, (1900 - logo_img.width, h - 225), logo_img)

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
    campaign_name: str = "AZD9550 Complementary Dual Agonist",
    master_strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
    variation_1_title: str = "Look & Feel 1 (Recommended Anchor): Synchronized Rowing Pair",
    variation_1_subtitle: str = "Two rowers moving in precision synchrony across glass-calm water at sunrise—instantly communicating complementary dual action.",
    variation_2_title: str = "Look & Feel 2: Crystalline Dual-Receptor Helix",
    variation_2_subtitle: str = "Two luminous molecular ribbons (Gold GLP-1 & Teal Glucagon) converging into a single balanced therapeutic structure.",
    variation_3_title: str = "Look & Feel 3: Vitality Couple Walking",
    variation_3_subtitle: str = "Sustained real-world patient freedom, energy balance, and multi-organ cardiometabolic well-being.",
    anchor_recommendation_rationale: str = (
        "Look & Feel 1 (Synchronized Rowing Pair) is recommended as the Primary Anchor Look & Feel "
        "because it immediately communicates complementary dual action in a single human glance, "
        "while allowing seamless single-page metaphor swaps (Rowing, Badminton Tandem, Sumo Equilibrium, Vitality Couple)."
    ),
    theme_prompt: str = "astrazeneca_light",
    include_az_logo: Optional[bool] = None,
    output_filename: str = "brand_look_and_feel_comparison_4k.png",
) -> Dict[str, Any]:
    """Generate both the 3-Up Brand Look & Feel Board (4K) and the 4-Up Single-Page Metaphor Variations Board (4K)."""
    settings = get_settings()
    theme = parse_brand_theme(theme_prompt, include_az_logo=include_az_logo)
    w, h = (3840, 2160)

    board = Image.new("RGBA", (w, h), (*theme.background_rgb, 255))
    draw = ImageDraw.Draw(board, "RGBA")

    f_title = _load_font(74, bold=True)
    f_strap = _load_font(46, bold=True)
    f_card_h = _load_font(46, bold=True)
    f_card_b = _load_font(38, bold=False)
    f_rec = _load_font(40, bold=True)

    # Header
    draw.text(
        (140, 85),
        f"{campaign_name.upper()} — 3 BRAND LOOK & FEEL DIRECTIONS",
        font=f_title,
        fill=(*theme.text_primary_rgb, 255),
    )

    # Single Master Strapline Banner across top
    draw.rounded_rectangle(
        (140, 195, w - 140, 298),
        radius=22,
        fill=(*theme.primary_rgb, 255),
    )
    draw.text(
        (185, 220),
        f"SINGLE MASTER STRAPLINE:  \"{master_strapline}\"",
        font=f_strap,
        fill=(255, 255, 255, 255),
    )

    variations = [
        (variation_1_title, variation_1_subtitle, "rowing pair sunrise", theme.primary_hex, True),
        (variation_2_title, variation_2_subtitle, "dual_helix molecule crystal", theme.secondary_hex, False),
        (variation_3_title, variation_3_subtitle, "vitality couple walking", theme.accent_hex, False),
    ]

    card_w = 1120
    gap = 60
    start_x = 140
    card_top = 340
    card_bottom = 1725

    for idx, (v_title, v_sub, img_key, accent_hx, is_anchor) in enumerate(variations):
        x0 = start_x + idx * (card_w + gap)
        x1 = x0 + card_w
        acc_rgb = hex_to_rgb(accent_hx)

        draw.rounded_rectangle(
            (x0, card_top, x1, card_bottom),
            radius=34,
            fill=(*theme.card_background_rgb, 255),
            outline=(*acc_rgb, 255),
            width=10 if is_anchor else 5,
        )

        # Photographic 4K visual preview inside card
        art_preview = _generate_artistic_4k_canvas(
            img_key + " " + v_title,
            theme,
            size=(card_w - 40, 620),
            prefer_gallery=True,
        )
        board.paste(art_preview.convert("RGBA"), (x0 + 20, card_top + 20))

        if is_anchor:
            draw.rounded_rectangle(
                (x0 + 45, card_top + 45, x0 + 660, card_top + 120),
                radius=18,
                fill=(*acc_rgb, 255),
            )
            draw.text(
                (x0 + 70, card_top + 60),
                "★ RECOMMENDED ANCHOR",
                font=_load_font(36, bold=True),
                fill=(255, 255, 255, 255),
            )

        # Card Title
        ty = card_top + 665
        for line in _wrap_text(draw, v_title, f_card_h, card_w - 90)[:2]:
            draw.text((x0 + 45, ty), line, font=f_card_h, fill=(*theme.text_primary_rgb, 255))
            ty += 58

        # Single Master Strapline badge on each card
        ty += 18
        draw.rounded_rectangle(
            (x0 + 45, ty, x1 - 45, ty + 86),
            radius=16,
            fill=(*acc_rgb, 255),
        )
        draw.text(
            (x0 + 70, ty + 22),
            master_strapline[:44],
            font=_load_font(34, bold=True),
            fill=(255, 255, 255, 255),
        )
        ty += 115

        # Description
        for line in _wrap_text(draw, v_sub, f_card_b, card_w - 90)[:4]:
            draw.text((x0 + 45, ty), line, font=f_card_b, fill=(*theme.text_secondary_rgb, 255))
            ty += 50

    # Bottom Anchor Recommendation Box
    draw.rounded_rectangle(
        (140, 1765, w - 140, 2050),
        radius=28,
        fill=(*theme.card_background_rgb, 255),
        outline=(*theme.primary_rgb, 255),
        width=6,
    )
    ry = 1800
    for line in _wrap_text(
        draw,
        f"RECOMMENDED ANCHOR LOOK & FEEL: {anchor_recommendation_rationale}",
        f_rec,
        w - 380,
    )[:3]:
        draw.text((185, ry), line, font=f_rec, fill=(*theme.text_primary_rgb, 255))
        ry += 56

    logo_img = get_pil_logo_for_theme(theme, max_height=84)
    if logo_img is not None:
        board.paste(logo_img, (w - 160 - logo_img.width, 85), logo_img)

    out_path = settings.output_dir / output_filename
    board.convert("RGB").save(out_path, format="PNG", optimize=True)

    # Also generate the 4-Up Single-Page Look & Feel Metaphor Swap Board (Rowing, Badminton, Sumo, Vitality)
    sp_res = generate_single_page_metaphor_swap_board_4k(
        campaign_name=campaign_name,
        master_strapline=master_strapline,
        theme=theme,
    )
    sp_path = sp_res["swap_board_image_path"]

    return {
        "status": "success",
        "board_image_path": str(out_path),
        "single_page_variations_board_path": str(sp_path),
        "dimensions": "3840x2160 (4K UHD)",
        "campaign_name": campaign_name,
        "master_strapline": master_strapline,
        "recommended_anchor": variation_1_title,
        "anchor_rationale": anchor_recommendation_rationale,
        "theme_id": theme.theme_id,
    }


def generate_single_page_metaphor_swap_board_4k(
    campaign_name: str = "AZD9550",
    master_strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
    theme_prompt: str = "astrazeneca_light",
    theme: Optional[BrandTheme] = None,
    include_az_logo: Optional[bool] = None,
    output_filename: str = "single_page_look_and_feel_variations_4k.png",
) -> Dict[str, Any]:
    """Generate a 4-Up Single-Page Look & Feel Variations Board showing Rowing, Badminton, Sumo, and Vitality swaps."""
    settings = get_settings()
    if theme is None:
        theme = parse_brand_theme(theme_prompt, include_az_logo=include_az_logo)
    w, h = (3840, 2160)
    board = Image.new("RGBA", (w, h), (*theme.background_rgb, 255))
    draw = ImageDraw.Draw(board, "RGBA")

    f_title = _load_font(68, bold=True)
    f_sub = _load_font(42, bold=True)
    f_card_h = _load_font(42, bold=True)
    f_card_b = _load_font(34, bold=False)

    draw.text(
        (120, 75),
        f"{campaign_name.upper()} — SINGLE-PAGE LOOK & FEEL METAPHOR VARIATIONS",
        font=f_title,
        fill=(*theme.text_primary_rgb, 255),
    )
    draw.text(
        (120, 165),
        f"Unified Layout & Single Master Strapline (\"{master_strapline}\") Across Interchangeable Visual Metaphors",
        font=f_sub,
        fill=(*theme.primary_rgb, 255),
    )

    swaps = [
        (
            "Variation A (Anchor): Rowing Pair",
            "Synchronized sculling pair—precision dual-pathway propulsion",
            "rowing pair sunrise",
            theme.primary_hex,
            True,
        ),
        (
            "Variation B: Badminton Tandem",
            "Mixed-doubles court agility—complementary front & back-court coverage",
            "badminton tandem court",
            theme.secondary_hex,
            False,
        ),
        (
            "Variation C: Sumo Equilibrium",
            "Balanced opposing forces—power & metabolic counter-equilibrium",
            "sumo equilibrium balance",
            theme.accent_hex,
            False,
        ),
        (
            "Variation D: Vitality Couple",
            "Shared real-world patient stride—durable cardiometabolic freedom",
            "vitality couple walking",
            theme.success_hex,
            False,
        ),
    ]

    card_w = 840
    gap = 45
    start_x = 120
    card_top = 260
    card_bottom = 2020

    for idx, (title, desc, img_key, hx, is_anchor) in enumerate(swaps):
        x0 = start_x + idx * (card_w + gap)
        x1 = x0 + card_w
        col = hex_to_rgb(hx)

        draw.rounded_rectangle(
            (x0, card_top, x1, card_bottom),
            radius=30,
            fill=(*theme.card_background_rgb, 255),
            outline=(*col, 255),
            width=9 if is_anchor else 4,
        )
        # Top color bar inside each single-page mockup
        draw.rectangle((x0 + 20, card_top + 20, x1 - 20, card_top + 46), fill=(*col, 255))

        photo = _generate_artistic_4k_canvas(
            img_key,
            theme,
            size=(card_w - 40, 880),
            prefer_gallery=True,
        )
        board.paste(photo.convert("RGBA"), (x0 + 20, card_top + 56))

        if is_anchor:
            draw.rounded_rectangle(
                (x0 + 40, card_top + 80, x0 + 520, card_top + 148),
                radius=14,
                fill=(*col, 255),
            )
            draw.text(
                (x0 + 60, card_top + 92),
                "★ ANCHOR LOOK & FEEL",
                font=_load_font(32, bold=True),
                fill=(255, 255, 255, 255),
            )

        ty = card_top + 965
        for line in _wrap_text(draw, title, f_card_h, card_w - 70)[:2]:
            draw.text((x0 + 35, ty), line, font=f_card_h, fill=(*theme.text_primary_rgb, 255))
            ty += 52

        ty += 16
        draw.rounded_rectangle(
            (x0 + 35, ty, x1 - 35, ty + 90),
            radius=14,
            fill=(*col, 255),
        )
        for s_line in _wrap_text(draw, master_strapline, _load_font(30, bold=True), card_w - 100)[:2]:
            draw.text((x0 + 55, ty + 14), s_line, font=_load_font(30, bold=True), fill=(255, 255, 255, 255))
            ty += 34
        ty += 75

        for line in _wrap_text(draw, desc, f_card_b, card_w - 70)[:4]:
            draw.text((x0 + 35, ty), line, font=f_card_b, fill=(*theme.text_secondary_rgb, 255))
            ty += 46

        # Mini Dual-Pathway Footer Pill inside each single-page preview
        draw.rounded_rectangle(
            (x0 + 35, card_bottom - 140, x1 - 35, card_bottom - 45),
            radius=14,
            fill=(*theme.background_rgb, 255),
            outline=(*col, 255),
            width=3,
        )
        draw.text(
            (x0 + 50, card_bottom - 110),
            "Pillar 1 (Satiety & Glycemia) + Pillar 2 (Energy & Liver)",
            font=_load_font(23, bold=True),
            fill=(*theme.text_primary_rgb, 255),
        )

    logo_img = get_pil_logo_for_theme(theme, max_height=80)
    if logo_img is not None:
        board.paste(logo_img, (w - 140 - logo_img.width, 75), logo_img)

    out_path = settings.output_dir / output_filename
    board.convert("RGB").save(out_path, format="PNG", optimize=True)
    return {
        "status": "success",
        "swap_board_image_path": str(out_path),
        "dimensions": "3840x2160 (4K UHD)",
        "campaign_name": campaign_name,
        "master_strapline": master_strapline,
        "theme_id": theme.theme_id,
    }
