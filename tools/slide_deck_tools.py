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
- Embedded 4K photographic gallery visuals and high-resolution charts on every slide
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from config.brand_guidelines import (
    BrandTheme,
    hex_to_rgb,
    parse_brand_theme,
    resolve_gallery_image,
)
from config.settings import get_settings
from tools.chart_tools import (
    generate_campaign_chart_svg_and_png,
    generate_pathway_synergy_svg_and_png,
)
from tools.image_tools import _load_font, _wrap_text
from tools.logo_tools import get_pil_logo_for_theme


DEFAULT_GENERIC_SLIDES: List[Dict[str, Any]] = [
    {
        "kicker": "SLIDE 01  ·  EXECUTIVE CAMPAIGN OVERVIEW",
        "title": "Complementary Dual-Pathway Strategy & Brand Vision",
        "subtitle": "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
        "image_key": "rowing_pair_4k",
        "visual_caption": "ANCHOR METAPHOR  ·  SYNCHRONIZED ROWING PAIR",
        "cards": [
            {
                "header": "Unmet Multi-System Clinical Need",
                "bullets": [
                    "Moving beyond single-target monotherapy limitations in complex cardiometabolic disease.",
                    "Addressing interconnected weight, hepatic lipid overload, and glycemic priorities simultaneously.",
                ],
            },
            {
                "header": "Anchor Campaign Look & Feel",
                "bullets": [
                    "Unified under a single master strapline: 'TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.'",
                    "Synchronized rowing pair metaphor: two independent oars driving one balanced vessel.",
                ],
            },
        ],
    },
    {
        "kicker": "SLIDE 02  ·  SINGLE-PAGE METAPHOR VARIATIONS",
        "title": "Flexible Visual Metaphor System Across Markets",
        "subtitle": "How the Rowing Anchor swaps seamlessly with Badminton, Sumo & Vitality",
        "image_key": "badminton_tandem_4k",
        "visual_caption": "VARIATION A  ·  MIXED DOUBLES BADMINTON TANDEM",
        "cards": [
            {
                "header": "Recommended Anchor: Synchronized Rowing",
                "bullets": [
                    "Captures dual mechanical propulsion and hydrodynamic stability at dawn.",
                    "Clear non-oncology differentiation vs. single-athlete monotherapy campaigns.",
                ],
            },
            {
                "header": "Interchangeable Single-Page Variations",
                "bullets": [
                    "Badminton Tandem (Agility & Reflex), Sumo Equilibrium (Grounded Force), Vitality Couple (Patient Outcome).",
                    "All variations preserve the identical layout grid, typography, and single strapline.",
                ],
            },
        ],
    },
    {
        "kicker": "SLIDE 03  ·  PILLAR 1 MECHANISM OF ACTION",
        "title": "Pillar 1: Central Satiety & Systemic Glycemic Control",
        "subtitle": "Targeted hypothalamic satiety signaling and insulinotropic baseline regulation",
        "image_key": "glp1_pathway_4k",
        "visual_caption": "PILLAR 1  ·  CENTRAL SATIETY & PANCREATIC SIGNALING",
        "cards": [
            {
                "header": "Central Appetite & Intake Regulation",
                "bullets": [
                    "Engages central satiety centers to reduce caloric intake and cravings.",
                    "Delivers predictable, well-characterized foundational weight and glycemic control.",
                ],
            },
            {
                "header": "Systemic Cardiometabolic Foundation",
                "bullets": [
                    "Improves glucose-dependent insulin secretion and systemic metabolic homeostasis.",
                    "Creates the clinical foundation for complementary organ-level amplification.",
                ],
            },
        ],
    },
    {
        "kicker": "SLIDE 04  ·  PILLAR 2 COMPLEMENTARY MECHANISM",
        "title": "Pillar 2: Direct Hepatic Lipid Oxidation & Energy Expenditure",
        "subtitle": "Unlocking direct liver fat clearance, lipolysis, and thermogenic expenditure",
        "image_key": "gcg_liver_4k",
        "visual_caption": "PILLAR 2  ·  HEPATIC LIPID OXIDATION & EXPENDITURE",
        "cards": [
            {
                "header": "Direct Hepatic & Organ Remodeling",
                "bullets": [
                    "Stimulates hepatic β-oxidation and rapid mobilization of ectopic liver lipids.",
                    "Directly targets steatotic and visceral fat depots beyond caloric restriction alone.",
                ],
            },
            {
                "header": "Resting Energy Expenditure Amplification",
                "bullets": [
                    "Counteracts metabolic adaptation by sustaining whole-body energy expenditure.",
                    "Works in concert with Pillar 1 to deepen total fat mass reduction.",
                ],
            },
        ],
    },
    {
        "kicker": "SLIDE 05  ·  COMPLEMENTARY DUAL-PATHWAY SYNERGY",
        "title": "Why Complementary Balance Outperforms Single-Target Saturation",
        "subtitle": "Calibrated receptor ratio engineered for efficacy and tolerability",
        "image_key": "dual_helix_4k",
        "visual_caption": "MOLECULAR ARCHITECTURE  ·  CALIBRATED DUAL AGONISM",
        "cards": [
            {
                "header": "Avoiding Single-Pathway Dose Ceiling",
                "bullets": [
                    "Pushing a single receptor to maximum saturation increases GI intolerance with diminishing returns.",
                    "Balancing two complementary pathways achieves superior efficacy at better-tolerated receptor occupancy.",
                ],
            },
            {
                "header": "Glycemic Equilibrium by Design",
                "bullets": [
                    "Pillar 1 insulinotropic action buffers Pillar 2 hepatic glucose output.",
                    "Delivers deep lipid clearance while maintaining robust HbA1c improvements.",
                ],
            },
        ],
    },
    {
        "kicker": "SLIDE 06  ·  QUANTITATIVE MULTI-ENDPOINT EVIDENCE",
        "title": "Complementary Dual Strategy vs. Single-Pathway Baseline",
        "subtitle": "Multi-dimensional efficacy across weight, hepatic lipid clearance & metabolic rate",
        "include_chart": True,
        "cards": [
            {
                "header": "Key Quantitative Differentiators",
                "bullets": [
                    "Superior composite response across total weight loss, hepatic fat fraction reduction, and glycemic control.",
                    "High-quality body composition: preserves lean muscle mass while clearing visceral and liver fat.",
                ],
            },
        ],
    },
    {
        "kicker": "SLIDE 07  ·  MULTI-ORGAN & SYSTEMIC PROTECTION",
        "title": "Interconnected Cardiometabolic, Hepatic & Renal Impact",
        "subtitle": "Treating the whole metabolic ecosystem across MASH, obesity, T2D & CV risk",
        "image_key": "organ_synergy_4k",
        "visual_caption": "MULTI-ORGAN ECOSYSTEM  ·  BRAIN, LIVER, HEART & KIDNEY",
        "cards": [
            {
                "header": "Cross-Organ Disease Modification",
                "bullets": [
                    "Simultaneously addresses central appetite, hepatic steatosis (MASH), and cardiovascular risk factors.",
                    "Reduces lipotoxicity and systemic inflammation across target organ systems.",
                ],
            },
            {
                "header": "Combination & Pipeline Readiness",
                "bullets": [
                    "Engineered as both a best-in-class standalone therapy and a foundational combination backbone.",
                    "Supports tailored patient segmentation across obesity, T2D, and metabolic liver disease.",
                ],
            },
        ],
    },
    {
        "kicker": "SLIDE 08  ·  PATIENT OUTCOMES & OMNICHANNEL SUMMARY",
        "title": "Restoring Whole-Body Metabolic Vitality & Balance",
        "subtitle": "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
        "image_key": "vitality_couple_4k",
        "visual_caption": "PATIENT OUTCOME  ·  SUSTAINED METABOLIC VITALITY",
        "cards": [
            {
                "header": "Patient-Centered Clinical Value",
                "bullets": [
                    "Translates dual molecular pharmacology into tangible daily energy, mobility, and organ resilience.",
                    "Clear, memorable scientific narrative for endocrinologists, hepatologists, and cardiologists.",
                ],
            },
            {
                "header": "Omnichannel Campaign Deliverables Ready",
                "bullets": [
                    "3-Up Brand Look & Feel Board + 4-Up Single-Page Metaphor Swap Board (4K PNGs).",
                    "8-Slide 4K Widescreen Deck, 4-Page A4 Scientific Pamphlet PDF, and 1080p HD Video (.mp4).",
                ],
            },
        ],
    },
]


def generate_4k_slide_deck(
    campaign_name: str,
    theme_prompt: str = "astrazeneca_light",
    strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
    slides_data: Optional[List[Dict[str, Any]]] = None,
    custom_slides_json: Optional[str] = None,
    include_az_logo: Optional[bool] = None,
    attached_image_path: Optional[str] = None,
    output_pdf_filename: str = "campaign_presentation_deck_4k.pdf",
) -> Dict[str, Any]:
    """Generate 4K (`3840 × 2160`) PNG slides and a compiled Widescreen PDF Slide Deck.

    Automatically follows user branding prompts — e.g., Google white background + grey text +
    #4285F4 / #EA4335 / #FBBC04 / #34A853, or AstraZeneca Light/Dark format with official AZ logos.
    Every slide includes extra-large executive typography (`88px` titles, `62px` card headers,
    `54px` body bullets) paired with a 4K photographic visual panel or high-res chart.
    """
    settings = get_settings()
    theme: BrandTheme = parse_brand_theme(theme_prompt, include_az_logo=include_az_logo)

    parsed_custom: Optional[List[Dict[str, Any]]] = None
    if custom_slides_json:
        try:
            loaded = json.loads(custom_slides_json)
            if isinstance(loaded, list) and loaded:
                parsed_custom = loaded
        except Exception:
            parsed_custom = None

    slides = slides_data or parsed_custom or DEFAULT_GENERIC_SLIDES

    # Generate an evidence chart and synergy diagram in the active theme
    chart_res = generate_campaign_chart_svg_and_png(
        chart_title=f"{campaign_name} — Complementary Multi-Endpoint Performance",
        categories=["Weight / Primary", "Hepatic Clearance", "Metabolic Rate", "Composite Response"],
        series_primary_values=[89.0, 93.0, 85.0, 92.0],
        series_primary_label="Complementary Strategy",
        series_secondary_values=[64.0, 51.0, 48.0, 62.0],
        series_secondary_label="Single-Pathway Baseline",
        theme_prompt=theme_prompt,
        output_basename=f"{campaign_name.lower().replace(' ', '_')}_slide_chart",
    )
    chart_png_path = Path(chart_res["png_path"])

    w, h = (3840, 2160)
    f_kicker = _load_font(44, bold=True)
    f_title = _load_font(86, bold=True)
    f_sub = _load_font(50, bold=True)
    f_card_h = _load_font(60, bold=True)
    f_body = _load_font(52, bold=False)
    f_cap = _load_font(36, bold=True)
    f_foot = _load_font(34, bold=False)

    palette = theme.palette_hex or [
        theme.primary_hex,
        theme.secondary_hex,
        theme.accent_hex,
        theme.success_hex,
    ]
    logo_img = get_pil_logo_for_theme(theme, max_height=88)

    default_image_keys = [
        "rowing_pair_4k",
        "badminton_tandem_4k",
        "glp1_pathway_4k",
        "gcg_liver_4k",
        "dual_helix_4k",
        "organ_synergy_4k",
        "vitality_couple_4k",
        "sumo_equilibrium_4k",
    ]

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
        draw.text((150, 88), kicker[:72], font=f_kicker, fill=(*theme.primary_rgb, 255))

        # Slide Number Badge
        badge_col = hex_to_rgb(palette[(idx - 1) % len(palette)])
        draw.rounded_rectangle((w - 310, 75, w - 140, 160), radius=20, fill=(*badge_col, 255))
        draw.text((w - 255, 91), f"{idx:02d}", font=_load_font(48, bold=True), fill=(255, 255, 255, 255))

        # Title (86px)
        title_txt = s_spec.get("title", f"{campaign_name} Key Insight {idx}")
        ty = 160
        for line in _wrap_text(draw, title_txt, f_title, w - 500)[:2]:
            draw.text((150, ty), line, font=f_title, fill=(*theme.text_primary_rgb, 255))
            ty += 98

        # Subtitle (50px)
        sub_txt = s_spec.get("subtitle") or strapline
        if sub_txt:
            draw.text((150, ty + 8), sub_txt[:90], font=f_sub, fill=(*theme.secondary_rgb, 255))
            ty += 84

        cards = s_spec.get("cards", [])
        include_chart = bool(s_spec.get("include_chart", False))

        card_top = max(445, ty + 24)
        card_bottom = h - 205

        # Left column: 1 or 2 stacked executive cards; Right column: 4K photographic visual or chart
        left_x0, left_x1 = 150, 2140
        right_x0, right_x1 = 2200, w - 150
        left_w = left_x1 - left_x0

        if include_chart and chart_png_path.exists():
            c_rgb = hex_to_rgb(palette[0])
            draw.rounded_rectangle(
                (left_x0, card_top, left_x1, card_bottom),
                radius=34,
                fill=(*theme.card_background_rgb, 255),
                outline=(*c_rgb, 255),
                width=6,
            )
            draw.rounded_rectangle((left_x0, card_top, left_x1, card_top + 22), radius=10, fill=(*c_rgb, 255))
            if cards:
                c0 = cards[0]
                cy = card_top + 55
                for hline in _wrap_text(draw, c0.get("header", "Key Findings"), f_card_h, left_w - 110)[:2]:
                    draw.text((left_x0 + 55, cy), hline, font=f_card_h, fill=(*c_rgb, 255))
                    cy += 74
                cy += 24
                for b in c0.get("bullets", [])[:4]:
                    for bline in _wrap_text(draw, f"•  {b}", f_body, left_w - 110)[:3]:
                        draw.text((left_x0 + 55, cy), bline, font=f_body, fill=(*theme.text_primary_rgb, 255))
                        cy += 66
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
            # Render stacked cards on the left (up to 2 cards) so text is wide, large, and uncluttered
            num_cards = max(1, min(2, len(cards)))
            gap_y = 44
            avail_h = card_bottom - card_top
            card_h = (avail_h - gap_y * (num_cards - 1)) // num_cards

            for c_i, card in enumerate(cards[:num_cards]):
                cy0 = card_top + c_i * (card_h + gap_y)
                cy1 = cy0 + card_h
                accent_col = hex_to_rgb(palette[(idx + c_i - 1) % len(palette)])
                draw.rounded_rectangle(
                    (left_x0, cy0, left_x1, cy1),
                    radius=32,
                    fill=(*theme.card_background_rgb, 255),
                    outline=(*accent_col, 255),
                    width=6,
                )
                draw.rounded_rectangle((left_x0, cy0, left_x1, cy0 + 20), radius=10, fill=(*accent_col, 255))
                cy = cy0 + 46
                hdr = card.get("header", f"Strategic Pillar {c_i + 1}")
                for hline in _wrap_text(draw, hdr, f_card_h, left_w - 110)[:2]:
                    draw.text((left_x0 + 55, cy), hline, font=f_card_h, fill=(*accent_col, 255))
                    cy += 72
                cy += 18
                for b in card.get("bullets", [])[:3]:
                    for bline in _wrap_text(draw, f"•  {b}", f_body, left_w - 110)[:3]:
                        if cy + 64 < cy1 - 24:
                            draw.text((left_x0 + 55, cy), bline, font=f_body, fill=(*theme.text_primary_rgb, 255))
                            cy += 64
                    cy += 20

            # Right column: 4K photographic visual panel from gallery
            img_key = (
                s_spec.get("image_key")
                or f"{s_spec.get('title', '')} {s_spec.get('subtitle', '')}"
            )
            gal_path = resolve_gallery_image(str(img_key))
            if gal_path is None:
                gal_path = resolve_gallery_image(default_image_keys[(idx - 1) % len(default_image_keys)])

            panel_w = right_x1 - right_x0
            panel_h = card_bottom - card_top
            accent_right = hex_to_rgb(palette[idx % len(palette)])
            draw.rounded_rectangle(
                (right_x0, card_top, right_x1, card_bottom),
                radius=34,
                fill=(*theme.card_background_rgb, 255),
                outline=(*accent_right, 255),
                width=6,
            )
            if gal_path and gal_path.exists():
                photo = Image.open(gal_path).convert("RGBA")
                img_box_h = panel_h - 130
                photo_resized = photo.resize((panel_w - 24, img_box_h), Image.Resampling.LANCZOS)
                img.paste(photo_resized, (right_x0 + 12, card_top + 12))

                cap_txt = s_spec.get("visual_caption") or f"4K CAMPAIGN VISUAL  ·  SLIDE {idx:02d}"
                draw.rounded_rectangle(
                    (right_x0 + 12, card_bottom - 110, right_x1 - 12, card_bottom - 12),
                    radius=20,
                    fill=(*accent_right, 255),
                )
                draw.text(
                    (right_x0 + 40, card_bottom - 82),
                    cap_txt[:46],
                    font=f_cap,
                    fill=(255, 255, 255, 255),
                )

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
            f"{theme.compliance_footer}   |   {campaign_name}   |   {strapline[:48]}   |   Slide {idx} of {len(slides)}",
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
