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

"""Full Extended Multi-Page A4 PDF Pamphlet / Brochure Generator for AstraZeneca Campaign Lab (UC4).

Generates:
1. High-resolution A4 Print-Ready Multi-Page Scientific/Commercial Information Pamphlet PDF
   with extra-large legible typography, embedded 4K Hero Visuals, publication-grade charts/graphs,
   synergy architecture diagrams, and vector SVG AstraZeneca or custom brand logos.
2. Individual high-res PNG previews of every pamphlet page for instant chat inspection.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from config.brand_guidelines import BrandTheme, hex_to_rgb, parse_brand_theme
from config.settings import get_settings
from tools.chart_tools import (
    generate_campaign_chart_svg_and_png,
    generate_pathway_synergy_svg_and_png,
)
from tools.image_tools import (
    _load_font,
    _wrap_text,
    generate_4k_campaign_key_visual,
)
from tools.logo_tools import (
    draw_svg_on_reportlab_canvas,
    ensure_astrazeneca_logo_assets,
    get_pil_logo_for_theme,
)


def generate_extended_campaign_pamphlet_pdf(
    campaign_name: str,
    strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
    executive_summary: str = (
        "An integrated scientific and commercial overview synthesizing complementary mechanisms, "
        "quantitative multi-system outcomes, and patient-centered value propositions."
    ),
    pillar_1_title: str = "Pillar 1: Central & Systemic Regulation",
    pillar_1_points: Optional[List[str]] = None,
    pillar_2_title: str = "Pillar 2: Direct Organ & Metabolic Action",
    pillar_2_points: Optional[List[str]] = None,
    synergy_takeaways: Optional[List[str]] = None,
    references: Optional[List[str]] = None,
    theme_prompt: str = "astrazeneca_light",
    include_az_logo: Optional[bool] = None,
    hero_image_path: Optional[str] = None,
    output_filename: str = "campaign_information_pamphlet.pdf",
) -> Dict[str, Any]:
    """Generate a full 4-page extended A4 PDF Information Pamphlet + 4 high-res page PNGs.

    Follows the user's brand theme prompt (e.g., Google white background + grey text +
    #4285F4/#EA4335/#FBBC04/#34A853, or AstraZeneca Light/Dark format with official AZ logos).
    """
    settings = get_settings()
    theme: BrandTheme = parse_brand_theme(theme_prompt, include_az_logo=include_az_logo)

    p1_pts = pillar_1_points or [
        "Drives robust baseline control through targeted primary receptor signaling.",
        "Reduces systemic metabolic overload and improves foundational biomarkers.",
        "Well-characterized clinical profile across broad patient populations.",
    ]
    p2_pts = pillar_2_points or [
        "Activates direct organ-level lipid oxidation and energy expenditure.",
        "Clears ectopic and hepatic lipid stores to restore organ resilience.",
        "Complements Pillar 1 without duplicating single-pathway saturation.",
    ]
    syn_pts = synergy_takeaways or [
        "Synchronized Dual Action: Combines intake regulation with direct energy expenditure.",
        "Body Composition Quality: Preserves lean mass while achieving deep fat mass reduction.",
        "Multi-Organ Protection: Addresses interconnected cardiometabolic, hepatic, and renal priorities.",
        "Executive Visual Clarity: Unified under a single memorable campaign strapline.",
    ]
    refs = references or [
        "1. Campaign Lab Grounded Scientific Synthesis & Provided Slide Deck Evidence.",
        "2. Dual-Agonist & Complementary Pathway Preclinical and Clinical Trial Literature.",
        "3. Global Cardiometabolic & Multi-Organ Disease Management Guidelines (2025–2026).",
    ]

    # Ensure we have a 4K hero visual, a chart, and a synergy diagram in the active theme
    if hero_image_path and Path(hero_image_path).exists():
        kv_path = Path(hero_image_path)
    else:
        kv_res = generate_4k_campaign_key_visual(
            campaign_name=campaign_name,
            headline=f"{campaign_name}: Complementary Strategy Overview",
            strapline=strapline,
            theme_prompt=theme_prompt,
            include_az_logo=include_az_logo,
            output_filename=f"{campaign_name.lower().replace(' ', '_')}_pamphlet_hero_4k.png",
        )
        kv_path = Path(kv_res["image_path"])

    chart_res = generate_campaign_chart_svg_and_png(
        chart_title=f"{campaign_name} — Multi-System Outcome Comparison",
        categories=["Weight / Primary", "Hepatic Clearance", "Energy Expenditure", "Glycemic / Systemic"],
        series_primary_values=[89.0, 93.0, 86.0, 91.0],
        series_primary_label="Complementary Dual Strategy",
        series_secondary_values=[65.0, 51.0, 48.0, 68.0],
        series_secondary_label="Single-Pathway Monotherapy",
        theme_prompt=theme_prompt,
        output_basename=f"{campaign_name.lower().replace(' ', '_')}_pamphlet_chart",
    )
    synergy_res = generate_pathway_synergy_svg_and_png(
        diagram_title=f"{campaign_name} — Complementary Dual-Pathway Architecture",
        left_pillar_title=pillar_1_title,
        left_pillar_bullets=p1_pts,
        right_pillar_title=pillar_2_title,
        right_pillar_bullets=p2_pts,
        central_outcome_title=strapline,
        theme_prompt=theme_prompt,
        output_basename=f"{campaign_name.lower().replace(' ', '_')}_pamphlet_synergy",
    )

    # Render 4 high-resolution A4 page PNGs (2480 x 3508) with extra-large readable fonts
    pw, ph = (2480, 3508)
    f_kicker = _load_font(42, bold=True)
    f_h1 = _load_font(82, bold=True)
    f_h2 = _load_font(60, bold=True)
    f_body = _load_font(46, bold=False)
    f_bold = _load_font(48, bold=True)
    f_foot = _load_font(32, bold=False)

    palette = theme.palette_hex or [
        theme.primary_hex,
        theme.secondary_hex,
        theme.accent_hex,
        theme.success_hex,
    ]
    logo_img = get_pil_logo_for_theme(theme, max_height=85)
    page_png_paths: List[str] = []

    def _new_a4_page(page_num: int, page_kicker: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        p_img = Image.new("RGBA", (pw, ph), (*theme.background_rgb, 255))
        p_draw = ImageDraw.Draw(p_img, "RGBA")
        seg_w = pw // len(palette)
        for i_c, hx in enumerate(palette):
            x0 = i_c * seg_w
            x1 = pw if i_c == len(palette) - 1 else x0 + seg_w
            p_draw.rectangle((x0, 0, x1, 28), fill=(*hex_to_rgb(hx), 255))
        p_draw.text((140, 85), page_kicker, font=f_kicker, fill=(*theme.primary_rgb, 255))
        p_draw.line((140, ph - 160, pw - 140, ph - 160), fill=(*theme.primary_rgb, 120), width=3)
        p_draw.text(
            (140, ph - 120),
            f"{theme.compliance_footer}   |   Page {page_num} of 4",
            font=f_foot,
            fill=(*theme.text_secondary_rgb, 255),
        )
        if logo_img is not None:
            p_img.paste(logo_img, (pw - 140 - logo_img.width, ph - 138), logo_img)
        return p_img, p_draw

    # --- PAGE 1: Cover & Executive Summary ---
    p1, d1 = _new_a4_page(1, f"{campaign_name.upper()}  ·  INFORMATION PAMPHLET & EXECUTIVE SUMMARY")
    y = 165
    for line in _wrap_text(d1, f"{campaign_name}: Executive Campaign Summary", f_h1, pw - 280)[:2]:
        d1.text((140, y), line, font=f_h1, fill=(*theme.text_primary_rgb, 255))
        y += 98

    y += 20
    d1.rounded_rectangle((140, y, pw - 140, y + 108), radius=24, fill=(*theme.primary_rgb, 255))
    d1.text((185, y + 26), strapline[:56], font=f_bold, fill=(255, 255, 255, 255))
    y += 150

    if kv_path.exists():
        hero = Image.open(kv_path).convert("RGBA")
        hero.thumbnail((pw - 280, 1180), Image.Resampling.LANCZOS)
        p1.paste(hero, (140, y), hero)
        y += hero.height + 55

    d1.rounded_rectangle(
        (140, y, pw - 140, ph - 220),
        radius=32,
        fill=(*theme.card_background_rgb, 255),
        outline=(*theme.primary_rgb, 255),
        width=5,
    )
    cy = y + 50
    d1.text((195, cy), "Executive Summary & Core Value Proposition", font=f_h2, fill=(*theme.primary_rgb, 255))
    cy += 88
    for line in _wrap_text(d1, executive_summary, f_body, pw - 390)[:6]:
        d1.text((195, cy), line, font=f_body, fill=(*theme.text_primary_rgb, 255))
        cy += 62
    cy += 30
    for item in syn_pts[:3]:
        for line in _wrap_text(d1, f"•  {item}", f_body, pw - 390)[:2]:
            d1.text((195, cy), line, font=f_body, fill=(*theme.text_primary_rgb, 255))
            cy += 60
        cy += 20

    p1_file = settings.output_dir / f"{campaign_name.lower().replace(' ', '_')}_pamphlet_page_1.png"
    p1.convert("RGB").save(p1_file, format="PNG")
    page_png_paths.append(str(p1_file))

    # --- PAGE 2: Complementary Pathways Architecture ---
    p2, d2 = _new_a4_page(2, f"{campaign_name.upper()}  ·  COMPLEMENTARY MECHANISM ARCHITECTURE")
    y = 165
    for line in _wrap_text(d2, "Two Distinct Mechanisms Working in Tandem", f_h1, pw - 280)[:2]:
        d2.text((140, y), line, font=f_h1, fill=(*theme.text_primary_rgb, 255))
        y += 98
    y += 25

    syn_img_path = Path(synergy_res["png_path"])
    if syn_img_path.exists():
        s_img = Image.open(syn_img_path).convert("RGBA")
        s_img.thumbnail((pw - 280, 1120), Image.Resampling.LANCZOS)
        p2.paste(s_img, (140 + ((pw - 280) - s_img.width) // 2, y), s_img)
        y += s_img.height + 55

    for idx_p, (p_title, p_list, col_hx) in enumerate(
        [(pillar_1_title, p1_pts, theme.primary_hex), (pillar_2_title, p2_pts, theme.secondary_hex)]
    ):
        box_h = 780
        c_rgb = hex_to_rgb(col_hx)
        d2.rounded_rectangle(
            (140, y, pw - 140, y + box_h),
            radius=30,
            fill=(*theme.card_background_rgb, 255),
            outline=(*c_rgb, 255),
            width=6,
        )
        cy = y + 48
        d2.text((195, cy), p_title[:48], font=f_h2, fill=(*c_rgb, 255))
        cy += 88
        for pt in p_list[:4]:
            for line in _wrap_text(d2, f"•  {pt}", f_body, pw - 390)[:3]:
                d2.text((195, cy), line, font=f_body, fill=(*theme.text_primary_rgb, 255))
                cy += 62
            cy += 22
        y += box_h + 45

    p2_file = settings.output_dir / f"{campaign_name.lower().replace(' ', '_')}_pamphlet_page_2.png"
    p2.convert("RGB").save(p2_file, format="PNG")
    page_png_paths.append(str(p2_file))

    # --- PAGE 3: Quantitative Evidence & Comparative Matrix ---
    p3, d3 = _new_a4_page(3, f"{campaign_name.upper()}  ·  QUANTITATIVE EVIDENCE & SYNERGY MATRIX")
    y = 165
    for line in _wrap_text(d3, "Quantitative Impact & Multi-System Differentiation", f_h1, pw - 280)[:2]:
        d3.text((140, y), line, font=f_h1, fill=(*theme.text_primary_rgb, 255))
        y += 98
    y += 25

    ch_img_path = Path(chart_res["png_path"])
    if ch_img_path.exists():
        c_img = Image.open(ch_img_path).convert("RGBA")
        c_img.thumbnail((pw - 280, 1260), Image.Resampling.LANCZOS)
        p3.paste(c_img, (140 + ((pw - 280) - c_img.width) // 2, y), c_img)
        y += c_img.height + 55

    d3.rounded_rectangle(
        (140, y, pw - 140, ph - 220),
        radius=30,
        fill=(*theme.card_background_rgb, 255),
        outline=(*theme.primary_rgb, 255),
        width=5,
    )
    cy = y + 50
    d3.text((195, cy), "Complementary Strategic Advantages", font=f_h2, fill=(*theme.primary_rgb, 255))
    cy += 90
    for item in syn_pts:
        for line in _wrap_text(d3, f"✓  {item}", f_body, pw - 390)[:3]:
            d3.text((195, cy), line, font=f_body, fill=(*theme.text_primary_rgb, 255))
            cy += 62
        cy += 24

    p3_file = settings.output_dir / f"{campaign_name.lower().replace(' ', '_')}_pamphlet_page_3.png"
    p3.convert("RGB").save(p3_file, format="PNG")
    page_png_paths.append(str(p3_file))

    # --- PAGE 4: Omnichannel Implementation & Grounded References ---
    p4, d4 = _new_a4_page(4, f"{campaign_name.upper()}  ·  IMPLEMENTATION & SCIENTIFIC REFERENCES")
    y = 165
    for line in _wrap_text(d4, "Omnichannel Execution & Grounded References", f_h1, pw - 280)[:2]:
        d4.text((140, y), line, font=f_h1, fill=(*theme.text_primary_rgb, 255))
        y += 98
    y += 30

    # Brand Theme Swatch Card
    d4.rounded_rectangle(
        (140, y, pw - 140, y + 720),
        radius=30,
        fill=(*theme.card_background_rgb, 255),
        outline=(*theme.primary_rgb, 255),
        width=5,
    )
    d4.text((195, y + 48), f"Active Brand System: {theme.theme_name}", font=f_h2, fill=(*theme.primary_rgb, 255))
    sw_w = (pw - 420) // len(palette)
    for s_i, hx in enumerate(palette):
        sx0 = 195 + s_i * sw_w
        sx1 = sx0 + sw_w - 30
        d4.rounded_rectangle((sx0, y + 150, sx1, y + 420), radius=22, fill=(*hex_to_rgb(hx), 255))
        d4.text((sx0 + 20, y + 445), hx, font=f_bold, fill=(*theme.text_primary_rgb, 255))
    d4.text(
        (195, y + 545),
        f"Background: {theme.background_hex}   |   Text: {theme.text_primary_hex}   |   AZ Logo Included: {theme.include_az_logo}",
        font=f_body,
        fill=(*theme.text_secondary_rgb, 255),
    )
    y += 780

    # References Card
    d4.rounded_rectangle(
        (140, y, pw - 140, ph - 220),
        radius=30,
        fill=(*theme.card_background_rgb, 255),
        outline=(*theme.secondary_rgb, 255),
        width=5,
    )
    cy = y + 50
    d4.text((195, cy), "Grounded Evidence & References", font=f_h2, fill=(*theme.secondary_rgb, 255))
    cy += 90
    for ref in refs:
        for line in _wrap_text(d4, ref, f_body, pw - 390)[:3]:
            d4.text((195, cy), line, font=f_body, fill=(*theme.text_primary_rgb, 255))
            cy += 60
        cy += 24

    p4_file = settings.output_dir / f"{campaign_name.lower().replace(' ', '_')}_pamphlet_page_4.png"
    p4.convert("RGB").save(p4_file, format="PNG")
    page_png_paths.append(str(p4_file))

    # Compile into Multi-Page A4 PDF with native vector AstraZeneca SVG Bezier overlay when enabled
    pdf_path = settings.output_dir / output_filename
    a4_w, a4_h = A4
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.setTitle(f"{campaign_name} — Information Pamphlet")
    logos = ensure_astrazeneca_logo_assets()
    for p_png in page_png_paths:
        c.drawImage(ImageReader(p_png), 0, 0, width=a4_w, height=a4_h)
        if theme.include_az_logo and logos["svg_colour"].exists():
            draw_svg_on_reportlab_canvas(
                c,
                logos["svg_colour"],
                x=a4_w - 135,
                y=12,
                target_width=95,
                light_version=theme.is_dark_mode,
            )
        c.showPage()
    c.save()

    return {
        "status": "success",
        "pamphlet_pdf_path": str(pdf_path),
        "pamphlet_page_pngs": page_png_paths,
        "chart_svg_path": chart_res["svg_path"],
        "synergy_svg_path": synergy_res["svg_path"],
        "page_count": len(page_png_paths),
        "theme_id": theme.theme_id,
        "included_az_logo": theme.include_az_logo,
    }
