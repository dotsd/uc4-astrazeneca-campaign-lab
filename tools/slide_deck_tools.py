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

"""4K Slide Deck Generator (PNGs + Widescreen PDF) with Dynamic Brand Theme Engine (UC4).

Supports:
- Any user-specified custom theme prompt (e.g., Google white background + grey text +
  Blue #4285F4, Red #EA4335, Yellow #FBBC04, Green #34A853)
- AstraZeneca Corporate Light Executive or AstraZeneca Dark Metabolic Plum formats
- Official AstraZeneca vector SVG/PNG logos and icons when requested
- Extra-large executive typography (88px slide titles, 62px card headers, 54px body copy)
- Embedded charts, graphs, and 4K visual panels
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from config.brand_guidelines import BrandTheme, hex_to_rgb, parse_brand_theme
from config.settings import get_settings
from tools.chart_tools import generate_campaign_chart_svg_and_png
from tools.image_tools import _load_font, _wrap_text
from tools.logo_tools import get_pil_logo_for_theme


DEFAULT_GENERIC_SLIDES: List[Dict[str, Any]] = [
    {
        "kicker": "SLIDE 01  ·  EXECUTIVE OVERVIEW",
        "title": "Strategic Campaign Vision & Core Proposition",
        "subtitle": "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
        "cards": [
            {
                "header": "Unmet Clinical & Market Need",
                "bullets": [
                    "Addressing multi-system complexity beyond single-target monotherapy limitations.",
                    "Delivering clear, high-impact scientific differentiation for healthcare professionals.",
                ],
            },
            {
                "header": "Integrated Campaign Strategy",
                "bullets": [
                    "Unified visual metaphor and single master strapline across every touchpoint.",
                    "Grounded clinical evidence paired with executive-grade visual storytelling.",
                ],
            },
        ],
    },
    {
        "kicker": "SLIDE 02  ·  PRIMARY MECHANISM PILLAR",
        "title": "Pillar 1: Foundational Systemic Regulation",
        "subtitle": "Targeted central and peripheral signaling for proven baseline control",
        "cards": [
            {
                "header": "Core Pathway Activation",
                "bullets": [
                    "High-affinity receptor engagement driving sustained systemic control.",
                    "Robust reductions in primary disease burden and metabolic intake.",
                ],
            },
            {
                "header": "Clinical & Patient Impact",
                "bullets": [
                    "Predictable, well-characterized foundational efficacy profile.",
                    "Sets the stage for complementary second-pathway amplification.",
                ],
            },
        ],
    },
    {
        "kicker": "SLIDE 03  ·  COMPLEMENTARY MECHANISM PILLAR",
        "title": "Pillar 2: Direct Organ & Energy Mobilization",
        "subtitle": "Unlocking direct hepatic lipid oxidation and energy expenditure",
        "cards": [
            {
                "header": "Direct Organ Remodeling",
                "bullets": [
                    "Accelerates lipid clearance, β-oxidation, and metabolic rate.",
                    "Targets visceral and ectopic organ fat depots directly.",
                ],
            },
            {
                "header": "Synergistic Balance",
                "bullets": [
                    "Complements Pillar 1 to achieve deeper, more durable outcomes.",
                    "Designed to preserve lean tissue quality while maximizing fat loss.",
                ],
            },
        ],
    },
    {
        "kicker": "SLIDE 04  ·  QUANTITATIVE EVIDENCE & SYNERGY",
        "title": "Complementary Dual Strategy vs. Single-Pathway Baseline",
        "subtitle": "Multi-dimensional efficacy across primary and secondary endpoints",
        "include_chart": True,
        "cards": [
            {
                "header": "Key Quantitative Takeaways",
                "bullets": [
                    "Superior composite response across weight, hepatic lipid clearance, and glycemic control.",
                    "Balanced tolerability and sustained long-term trajectory.",
                ],
            }
        ],
    },
]


def generate_4k_slide_deck(
    campaign_name: str,
    theme_prompt: str = "astrazeneca_light",
    slides_data: Optional[List[Dict[str, Any]]] = None,
    include_az_logo: Optional[bool] = None,
    attached_image_path: Optional[str] = None,
    output_pdf_filename: str = "campaign_presentation_deck_4k.pdf",
) -> Dict[str, Any]:
    """Generate 4K (`3840 × 2160`) PNG slides and a compiled Widescreen PDF Slide Deck.

    Automatically follows user branding prompts — e.g., Google white background + grey text +
    #4285F4 / #EA4335 / #FBBC04 / #34A853, or AstraZeneca Light/Dark format with official AZ logos.
    """
    settings = get_settings()
    theme: BrandTheme = parse_brand_theme(theme_prompt, include_az_logo=include_az_logo)
    slides = slides_data if slides_data else DEFAULT_GENERIC_SLIDES

    # Generate an evidence chart in the active theme for chart slides
    chart_res = generate_campaign_chart_svg_and_png(
        chart_title=f"{campaign_name} — Complementary Multi-Endpoint Performance",
        categories=["Primary Efficacy", "Organ Clearance", "Metabolic Rate", "Composite Response"],
        series_primary_values=[88.0, 92.0, 84.0, 91.0],
        series_primary_label="Complementary Strategy",
        series_secondary_values=[64.0, 52.0, 49.0, 61.0],
        series_secondary_label="Single-Pathway Baseline",
        theme_prompt=theme_prompt,
        output_basename=f"{campaign_name.lower().replace(' ', '_')}_slide_chart",
    )
    chart_png_path = Path(chart_res["png_path"])

    w, h = (3840, 2160)
    f_kicker = _load_font(44, bold=True)
    f_title = _load_font(88, bold=True)
    f_sub = _load_font(52, bold=True)
    f_card_h = _load_font(62, bold=True)
    f_body = _load_font(54, bold=False)
    f_foot = _load_font(34, bold=False)

    palette = theme.palette_hex or [
        theme.primary_hex,
        theme.secondary_hex,
        theme.accent_hex,
        theme.success_hex,
    ]
    logo_img = get_pil_logo_for_theme(theme, max_height=88)

    slide_png_paths: List[str] = []

    for idx, s_spec in enumerate(slides, start=1):
        img = Image.new("RGBA", (w, h), (*theme.background_rgb, 255))
        draw = ImageDraw.Draw(img, "RGBA")

        # Top multi-color brand bar (renders 4-color Google bar or AstraZeneca bar)
        seg_w = w // len(palette)
        for p_i, hx in enumerate(palette):
            x0 = p_i * seg_w
            x1 = w if p_i == len(palette) - 1 else x0 + seg_w
            draw.rectangle((x0, 0, x1, 28), fill=(*hex_to_rgb(hx), 255))

        # Kicker
        kicker = s_spec.get("kicker") or f"SLIDE {idx:02d}  ·  {campaign_name.upper()}"
        draw.text((150, 95), kicker[:70], font=f_kicker, fill=(*theme.primary_rgb, 255))

        # Slide Number Badge
        badge_col = hex_to_rgb(palette[(idx - 1) % len(palette)])
        draw.rounded_rectangle((w - 310, 80, w - 140, 165), radius=20, fill=(*badge_col, 255))
        draw.text((w - 255, 96), f"{idx:02d}", font=_load_font(48, bold=True), fill=(255, 255, 255, 255))

        # Title (88px)
        title_txt = s_spec.get("title", f"{campaign_name} Key Insight {idx}")
        ty = 170
        for line in _wrap_text(draw, title_txt, f_title, w - 520)[:2]:
            draw.text((150, ty), line, font=f_title, fill=(*theme.text_primary_rgb, 255))
            ty += 102

        # Subtitle (52px)
        sub_txt = s_spec.get("subtitle", "")
        if sub_txt:
            draw.text((150, ty + 10), sub_txt[:85], font=f_sub, fill=(*theme.secondary_rgb, 255))
            ty += 90

        cards = s_spec.get("cards", [])
        include_chart = bool(s_spec.get("include_chart", False))

        card_top = max(470, ty + 30)
        card_bottom = h - 210

        if include_chart and chart_png_path.exists():
            # Left column card + Right column high-res chart
            left_x0, left_x1 = 150, 1780
            right_x0, right_x1 = 1840, w - 150
            c_rgb = hex_to_rgb(palette[0])
            draw.rounded_rectangle(
                (left_x0, card_top, left_x1, card_bottom),
                radius=34,
                fill=(*theme.card_background_rgb, 255),
                outline=(*c_rgb, 255),
                width=6,
            )
            if cards:
                c0 = cards[0]
                cy = card_top + 55
                draw.text((left_x0 + 55, cy), c0.get("header", "Key Findings")[:38], font=f_card_h, fill=(*c_rgb, 255))
                cy += 95
                for b in c0.get("bullets", [])[:4]:
                    for bline in _wrap_text(draw, f"•  {b}", f_body, (left_x1 - left_x0) - 110)[:3]:
                        draw.text((left_x0 + 55, cy), bline, font=f_body, fill=(*theme.text_primary_rgb, 255))
                        cy += 68
                    cy += 26

            c_img = Image.open(chart_png_path).convert("RGBA")
            target_cw = right_x1 - right_x0 - 40
            target_ch = card_bottom - card_top - 40
            c_img.thumbnail((target_cw, target_ch), Image.Resampling.LANCZOS)
            draw.rounded_rectangle(
                (right_x0, card_top, right_x1, card_bottom),
                radius=34,
                fill=(*theme.card_background_rgb, 255),
                outline=(*hex_to_rgb(palette[1 % len(palette)]), 255),
                width=6,
            )
            paste_x = right_x0 + ((right_x1 - right_x0) - c_img.width) // 2
            paste_y = card_top + ((card_bottom - card_top) - c_img.height) // 2
            img.paste(c_img, (paste_x, paste_y), c_img)
        else:
            num_cards = max(1, min(3, len(cards)))
            gap = 60
            total_w = w - 300
            cw = (total_w - gap * (num_cards - 1)) // num_cards
            for c_i, card in enumerate(cards[:num_cards]):
                x0 = 150 + c_i * (cw + gap)
                x1 = x0 + cw
                accent_col = hex_to_rgb(palette[c_i % len(palette)])
                draw.rounded_rectangle(
                    (x0, card_top, x1, card_bottom),
                    radius=34,
                    fill=(*theme.card_background_rgb, 255),
                    outline=(*accent_col, 255),
                    width=6,
                )
                draw.rounded_rectangle((x0, card_top, x1, card_top + 22), radius=10, fill=(*accent_col, 255))
                cy = card_top + 58
                hdr = card.get("header", f"Pillar {c_i + 1}")
                for hline in _wrap_text(draw, hdr, f_card_h, cw - 110)[:2]:
                    draw.text((x0 + 55, cy), hline, font=f_card_h, fill=(*accent_col, 255))
                    cy += 76
                cy += 24
                for b in card.get("bullets", [])[:4]:
                    for bline in _wrap_text(draw, f"•  {b}", f_body, cw - 110)[:3]:
                        draw.text((x0 + 55, cy), bline, font=f_body, fill=(*theme.text_primary_rgb, 255))
                        cy += 68
                    cy += 28

        # Optional user-attached image badge in top-right if provided on Slide 1
        if idx == 1 and attached_image_path and Path(attached_image_path).exists():
            try:
                att = Image.open(attached_image_path).convert("RGBA")
                att.thumbnail((420, 240), Image.Resampling.LANCZOS)
                img.paste(att, (w - 340 - att.width, 70), att)
            except Exception:
                pass

        # Footer & Official AstraZeneca Logo (if enabled)
        draw.line((150, h - 150, w - 150, h - 150), fill=(*theme.primary_rgb, 120), width=3)
        draw.text(
            (150, h - 115),
            f"{theme.compliance_footer}   |   {campaign_name}   |   Slide {idx} of {len(slides)}",
            font=f_foot,
            fill=(*theme.text_secondary_rgb, 255),
        )
        if logo_img is not None:
            img.paste(logo_img, (w - 150 - logo_img.width, h - 132), logo_img)

        s_path = settings.output_dir / f"{campaign_name.lower().replace(' ', '_')}_slide_{idx:02d}_4k.png"
        img.convert("RGB").save(s_path, format="PNG", optimize=True)
        slide_png_paths.append(str(s_path))

    # Compile Widescreen PDF Deck (1920 x 1080 pt)
    pdf_path = settings.output_dir / output_pdf_filename
    c = canvas.Canvas(str(pdf_path), pagesize=(1920, 1080))
    c.setTitle(f"{campaign_name} — 4K Presentation Deck")
    for sp in slide_png_paths:
        c.drawImage(ImageReader(sp), 0, 0, width=1920, height=1080)
        c.showPage()
    c.save()

    return {
        "status": "success",
        "pdf_deck_path": str(pdf_path),
        "slide_png_paths": slide_png_paths,
        "slide_count": len(slide_png_paths),
        "theme_id": theme.theme_id,
        "background_hex": theme.background_hex,
        "text_primary_hex": theme.text_primary_hex,
        "palette_hex": theme.palette_hex,
        "included_az_logo": theme.include_az_logo,
    }
