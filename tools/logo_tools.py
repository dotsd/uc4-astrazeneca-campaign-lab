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

"""Vector SVG Parser, Official AstraZeneca Logo Renderer & Custom SVG Badge Generator (UC4)."""

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.path as mpath
import matplotlib.pyplot as plt
from PIL import Image
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from config.brand_guidelines import BrandTheme, parse_brand_theme
from config.settings import get_settings

_TOKEN_RE = re.compile(
    r"([MmLlHhVvCcSsQqTtAaZz])|([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)"
)


def _arc_to_beziers(
    x1: float,
    y1: float,
    rx: float,
    ry: float,
    phi: float,
    large_arc: int,
    sweep: int,
    x2: float,
    y2: float,
) -> List[Tuple[float, float, float, float, float, float]]:
    """Approximate an SVG elliptical arc with cubic Bezier segments."""
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [(x1, y1, x2, y2, x2, y2)]

    rx = abs(rx)
    ry = abs(ry)
    phi_rad = math.radians(phi % 360.0)
    cos_phi = math.cos(phi_rad)
    sin_phi = math.sin(phi_rad)

    dx2 = (x1 - x2) / 2.0
    dy2 = (y1 - y2) / 2.0
    x1p = cos_phi * dx2 + sin_phi * dy2
    y1p = -sin_phi * dx2 + cos_phi * dy2

    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1.0:
        scale = math.sqrt(lam)
        rx *= scale
        ry *= scale

    rx2 = rx * rx
    ry2 = ry * ry
    x1p2 = x1p * x1p
    y1p2 = y1p * y1p

    denom = rx2 * y1p2 + ry2 * x1p2
    radicand = max(0.0, (rx2 * ry2 - denom) / denom) if denom != 0 else 0.0
    factor = math.sqrt(radicand)
    if large_arc == sweep:
        factor = -factor

    cxp = factor * (rx * y1p / ry)
    cyp = factor * (-ry * x1p / rx)

    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2.0
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2.0

    def _angle(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        mag = math.hypot(ux, uy) * math.hypot(vx, vy)
        val = max(-1.0, min(1.0, dot / mag)) if mag else 1.0
        ang = math.acos(val)
        return -ang if (ux * vy - uy * vx) < 0 else ang

    vx1 = (x1p - cxp) / rx
    vy1 = (y1p - cyp) / ry
    vx2 = (-x1p - cxp) / rx
    vy2 = (-y1p - cyp) / ry

    theta1 = _angle(1.0, 0.0, vx1, vy1)
    dtheta = _angle(vx1, vy1, vx2, vy2)
    if sweep == 0 and dtheta > 0:
        dtheta -= 2.0 * math.pi
    elif sweep == 1 and dtheta < 0:
        dtheta += 2.0 * math.pi

    segments = max(1, int(math.ceil(abs(dtheta) / (math.pi / 2.0))))
    delta = dtheta / segments
    alpha = (4.0 / 3.0) * math.tan(delta / 4.0)

    beziers: List[Tuple[float, float, float, float, float, float]] = []
    t = theta1
    for _ in range(segments):
        cos_t1, sin_t1 = math.cos(t), math.sin(t)
        cos_t2, sin_t2 = math.cos(t + delta), math.sin(t + delta)

        qx1 = cos_t1 - alpha * sin_t1
        qy1 = sin_t1 + alpha * cos_t1
        qx2 = cos_t2 + alpha * sin_t2
        qy2 = sin_t2 - alpha * cos_t2
        qx3 = cos_t2
        qy3 = sin_t2

        def _map_pt(px: float, py: float) -> Tuple[float, float]:
            sx = px * rx
            sy = py * ry
            return (
                cos_phi * sx - sin_phi * sy + cx,
                sin_phi * sx + cos_phi * sy + cy,
            )

        c1 = _map_pt(qx1, qy1)
        c2 = _map_pt(qx2, qy2)
        ep = _map_pt(qx3, qy3)
        beziers.append((c1[0], c1[1], c2[0], c2[1], ep[0], ep[1]))
        t += delta

    return beziers


def parse_svg_path_commands(d_attr: str) -> List[Tuple[str, Tuple[float, ...]]]:
    """Parse an SVG path `d` string into normalized absolute M, L, C, Z commands."""
    tokens = [
        m.group(1) or float(m.group(2)) for m in _TOKEN_RE.finditer(d_attr)
    ]
    cmds: List[Tuple[str, Tuple[float, ...]]] = []
    idx = 0
    cur_x = 0.0
    cur_y = 0.0
    start_x = 0.0
    start_y = 0.0
    last_ctrl_x = 0.0
    last_ctrl_y = 0.0
    last_cmd = ""

    while idx < len(tokens):
        tok = tokens[idx]
        if isinstance(tok, str):
            cmd = tok
            idx += 1
        else:
            cmd = last_cmd

        if cmd in ("M", "m"):
            x = float(tokens[idx])
            y = float(tokens[idx + 1])
            idx += 2
            if cmd == "m":
                x += cur_x
                y += cur_y
            cur_x, cur_y = x, y
            start_x, start_y = x, y
            cmds.append(("M", (cur_x, cur_y)))
            last_cmd = "L" if cmd == "M" else "l"
            last_ctrl_x, last_ctrl_y = cur_x, cur_y
        elif cmd in ("L", "l"):
            x = float(tokens[idx])
            y = float(tokens[idx + 1])
            idx += 2
            if cmd == "l":
                x += cur_x
                y += cur_y
            cur_x, cur_y = x, y
            cmds.append(("L", (cur_x, cur_y)))
            last_cmd = cmd
            last_ctrl_x, last_ctrl_y = cur_x, cur_y
        elif cmd in ("H", "h"):
            x = float(tokens[idx])
            idx += 1
            cur_x = cur_x + x if cmd == "h" else x
            cmds.append(("L", (cur_x, cur_y)))
            last_cmd = cmd
            last_ctrl_x, last_ctrl_y = cur_x, cur_y
        elif cmd in ("V", "v"):
            y = float(tokens[idx])
            idx += 1
            cur_y = cur_y + y if cmd == "v" else y
            cmds.append(("L", (cur_x, cur_y)))
            last_cmd = cmd
            last_ctrl_x, last_ctrl_y = cur_x, cur_y
        elif cmd in ("C", "c"):
            x1 = float(tokens[idx])
            y1 = float(tokens[idx + 1])
            x2 = float(tokens[idx + 2])
            y2 = float(tokens[idx + 3])
            x = float(tokens[idx + 4])
            y = float(tokens[idx + 5])
            idx += 6
            if cmd == "c":
                x1 += cur_x
                y1 += cur_y
                x2 += cur_x
                y2 += cur_y
                x += cur_x
                y += cur_y
            cmds.append(("C", (x1, y1, x2, y2, x, y)))
            cur_x, cur_y = x, y
            last_ctrl_x, last_ctrl_y = x2, y2
            last_cmd = cmd
        elif cmd in ("S", "s"):
            x2 = float(tokens[idx])
            y2 = float(tokens[idx + 1])
            x = float(tokens[idx + 2])
            y = float(tokens[idx + 3])
            idx += 4
            if last_cmd in ("C", "c", "S", "s"):
                x1 = 2.0 * cur_x - last_ctrl_x
                y1 = 2.0 * cur_y - last_ctrl_y
            else:
                x1, y1 = cur_x, cur_y
            if cmd == "s":
                x2 += cur_x
                y2 += cur_y
                x += cur_x
                y += cur_y
            cmds.append(("C", (x1, y1, x2, y2, x, y)))
            cur_x, cur_y = x, y
            last_ctrl_x, last_ctrl_y = x2, y2
            last_cmd = cmd
        elif cmd in ("A", "a"):
            rx = float(tokens[idx])
            ry = float(tokens[idx + 1])
            rot = float(tokens[idx + 2])
            large_arc = int(float(tokens[idx + 3]))
            sweep = int(float(tokens[idx + 4]))
            x = float(tokens[idx + 5])
            y = float(tokens[idx + 6])
            idx += 7
            if cmd == "a":
                x += cur_x
                y += cur_y
            for c1x, c1y, c2x, c2y, ex, ey in _arc_to_beziers(
                cur_x, cur_y, rx, ry, rot, large_arc, sweep, x, y
            ):
                cmds.append(("C", (c1x, c1y, c2x, c2y, ex, ey)))
            cur_x, cur_y = x, y
            last_ctrl_x, last_ctrl_y = cur_x, cur_y
            last_cmd = cmd
        elif cmd in ("Z", "z"):
            cmds.append(("Z", ()))
            cur_x, cur_y = start_x, start_y
            last_ctrl_x, last_ctrl_y = cur_x, cur_y
            last_cmd = cmd
        else:
            idx += 1

    return cmds


def load_svg_paths(svg_file: Path) -> Tuple[float, float, List[Dict[str, Any]]]:
    """Extract viewBox dimensions and path elements with CSS fill colors from an SVG file."""
    tree = ET.parse(svg_file)
    root = tree.getroot()
    vb = root.attrib.get("viewBox", "0 0 284.79 70.77").split()
    vw = float(vb[2]) if len(vb) >= 4 else 284.79
    vh = float(vb[3]) if len(vb) >= 4 else 70.77

    css_fills: Dict[str, str] = {}
    for elem in root.iter():
        if elem.tag.endswith("style") and elem.text:
            for cls_name, hex_col in re.findall(
                r"\.([a-zA-Z0-9_-]+)\s*\{\s*fill\s*:\s*(#[0-9a-fA-F]{3,6})",
                elem.text,
            ):
                css_fills[cls_name] = hex_col

    paths: List[Dict[str, Any]] = []
    for elem in root.iter():
        if elem.tag.endswith("path") and "d" in elem.attrib:
            cls_attr = elem.attrib.get("class", "")
            fill_col = elem.attrib.get("fill") or css_fills.get(cls_attr, "#000000")
            paths.append(
                {
                    "class": cls_attr,
                    "fill": fill_col,
                    "commands": parse_svg_path_commands(elem.attrib["d"]),
                }
            )
    return vw, vh, paths


def draw_svg_on_reportlab_canvas(
    c: canvas.Canvas,
    svg_file: Path,
    x: float,
    y: float,
    target_width: float,
    light_version: bool = False,
) -> Tuple[float, float]:
    """Draw an SVG file onto a ReportLab canvas as native resolution-independent vector Bezier curves."""
    if not svg_file.exists():
        return (0.0, 0.0)
    vw, vh, paths = load_svg_paths(svg_file)
    scale = target_width / vw
    target_height = vh * scale

    c.saveState()
    c.translate(x, y)
    c.scale(scale, scale)

    for idx, p_info in enumerate(paths):
        fill_hex = p_info["fill"]
        if light_version:
            fill_hex = "#ffffff" if idx == 0 and len(paths) > 1 else "#f0ab00"
        c.setFillColor(colors.HexColor(fill_hex))
        rp = c.beginPath()
        for cmd, args in p_info["commands"]:
            if cmd == "M":
                rp.moveTo(args[0], vh - args[1])
            elif cmd == "L":
                rp.lineTo(args[0], vh - args[1])
            elif cmd == "C":
                rp.curveTo(
                    args[0],
                    vh - args[1],
                    args[2],
                    vh - args[3],
                    args[4],
                    vh - args[5],
                )
            elif cmd == "Z":
                rp.close()
        c.drawPath(rp, fill=1, stroke=0)

    c.restoreState()
    return (target_width, target_height)


def render_svg_to_png(
    svg_file: Path,
    png_path: Path,
    dpi: int = 600,
    color_overrides: Optional[List[str]] = None,
) -> Path:
    """Render an SVG file to an ultra-high-resolution transparent PNG using Matplotlib PathPatch."""
    vw, vh, paths = load_svg_paths(svg_file)
    scale = max(2.0 / max(vw, 1.0), 2.0 / max(vh, 1.0))
    fig_w = max(0.8, vw * scale)
    fig_h = max(0.8, vh * scale)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)

    for idx, p_info in enumerate(paths):
        fill_hex = (
            color_overrides[idx]
            if color_overrides and idx < len(color_overrides)
            else p_info["fill"]
        )
        verts: List[Tuple[float, float]] = []
        codes: List[int] = []
        for cmd, args in p_info["commands"]:
            if cmd == "M":
                verts.append((args[0], vh - args[1]))
                codes.append(mpath.Path.MOVETO)
            elif cmd == "L":
                verts.append((args[0], vh - args[1]))
                codes.append(mpath.Path.LINETO)
            elif cmd == "C":
                verts.append((args[0], vh - args[1]))
                codes.append(mpath.Path.CURVE4)
                verts.append((args[2], vh - args[3]))
                codes.append(mpath.Path.CURVE4)
                verts.append((args[4], vh - args[5]))
                codes.append(mpath.Path.CURVE4)
            elif cmd == "Z":
                verts.append((0.0, 0.0))
                codes.append(mpath.Path.CLOSEPOLY)
        if verts:
            patch = mpatches.PathPatch(
                mpath.Path(verts, codes),
                facecolor=fill_hex,
                edgecolor="none",
                lw=0,
            )
            ax.add_patch(patch)

    ax.set_xlim(0, vw)
    ax.set_ylim(0, vh)
    ax.set_aspect("equal")
    ax.axis("off")
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        png_path,
        format="png",
        dpi=dpi,
        transparent=True,
        bbox_inches="tight",
        pad_inches=0.02,
    )
    plt.close(fig)
    return png_path


def ensure_astrazeneca_logo_assets() -> Dict[str, Path]:
    """Ensure all vector SVG and 4K PNG AstraZeneca logos exist in assets/astrazeneca_logos_svg."""
    settings = get_settings()
    logo_dir = settings.logos_dir
    svg_colour = logo_dir / "AstraZeneca logo colour.svg"
    svg_symbol = logo_dir / "AstraZeneca symbol.svg"
    svg_black = logo_dir / "AstraZeneca logo black.svg"

    png_colour = logo_dir / "astrazeneca_logo_colour.png"
    png_white = logo_dir / "astrazeneca_logo_white.png"
    png_black = logo_dir / "astrazeneca_logo_black.png"
    png_symbol_gold = logo_dir / "astrazeneca_symbol_gold.png"

    if svg_symbol.exists() and not png_symbol_gold.exists():
        render_svg_to_png(svg_symbol, png_symbol_gold, dpi=600, color_overrides=["#f0ab00"])
    if svg_colour.exists() and not png_colour.exists():
        render_svg_to_png(svg_colour, png_colour, dpi=600)
    if svg_colour.exists() and not png_white.exists():
        render_svg_to_png(
            svg_colour, png_white, dpi=600, color_overrides=["#ffffff", "#f0ab00"]
        )
    if svg_black.exists() and not png_black.exists():
        render_svg_to_png(
            svg_black, png_black, dpi=600, color_overrides=["#000000", "#000000"]
        )

    return {
        "svg_colour": svg_colour,
        "svg_symbol": svg_symbol,
        "svg_black": svg_black,
        "png_colour": png_colour,
        "png_white": png_white,
        "png_black": png_black,
        "png_symbol_gold": png_symbol_gold,
    }


def get_pil_logo_for_theme(theme: BrandTheme, max_height: int = 80) -> Optional[Image.Image]:
    """Return a high-resolution RGBA PIL Image of the official AstraZeneca logo for a given theme."""
    if not theme.include_az_logo:
        return None
    logos = ensure_astrazeneca_logo_assets()
    if theme.is_dark_mode:
        target = logos["png_white"] if logos["png_white"].exists() else logos["png_symbol_gold"]
    else:
        target = logos["png_colour"]
    if not target.exists():
        return None
    img = Image.open(target).convert("RGBA")
    ratio = max_height / max(1, img.height)
    new_w = max(1, int(img.width * ratio))
    return img.resize((new_w, max_height), Image.Resampling.LANCZOS)


def generate_custom_brand_logo_svg(
    brand_title: str,
    subtitle: str = "CAMPAIGN LAB",
    theme_prompt: str = "astrazeneca_light",
    output_filename: str = "campaign_brand_crest.svg",
) -> Dict[str, str]:
    """Generate a scalable vector SVG emblem/crest and high-DPI PNG for any campaign or custom palette."""
    settings = get_settings()
    theme = parse_brand_theme(theme_prompt)
    out_svg = settings.output_dir / output_filename
    if not out_svg.name.endswith(".svg"):
        out_svg = out_svg.with_suffix(".svg")
    out_png = out_svg.with_suffix(".png")

    c1 = theme.primary_hex
    c2 = theme.secondary_hex
    c3 = theme.accent_hex
    c4 = theme.success_hex
    txt_col = theme.text_primary_hex
    bg_col = theme.background_hex

    svg_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 180" width="640" height="180">
  <defs>
    <linearGradient id="crestGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c1}" />
      <stop offset="100%" stop-color="{c2}" />
    </linearGradient>
    <linearGradient id="crestGrad2" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{c3}" />
      <stop offset="100%" stop-color="{c4}" />
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="632" height="172" rx="22" fill="{bg_col}" stroke="{c1}" stroke-width="3"/>
  <circle cx="95" cy="90" r="56" fill="url(#crestGrad1)" opacity="0.92"/>
  <path d="M 60 112 C 75 52, 115 52, 130 112" fill="none" stroke="{c3}" stroke-width="8" stroke-linecap="round"/>
  <path d="M 68 72 C 88 122, 108 122, 124 72" fill="none" stroke="#FFFFFF" stroke-width="6" stroke-linecap="round"/>
  <circle cx="95" cy="90" r="10" fill="{c4}"/>
  <text x="178" y="88" font-family="Helvetica, Arial, sans-serif" font-size="38" font-weight="bold" fill="{txt_col}">{brand_title[:24]}</text>
  <text x="180" y="126" font-family="Helvetica, Arial, sans-serif" font-size="18" font-weight="bold" letter-spacing="3" fill="{c1}">{subtitle[:36]}</text>
  <rect x="178" y="140" width="85" height="6" rx="3" fill="{c1}"/>
  <rect x="271" y="140" width="85" height="6" rx="3" fill="{c2}"/>
  <rect x="364" y="140" width="85" height="6" rx="3" fill="{c3}"/>
  <rect x="457" y="140" width="85" height="6" rx="3" fill="{c4}"/>
</svg>
"""
    out_svg.write_text(svg_xml, encoding="utf-8")

    # Also render a crisp PNG version for embedding in slides/videos
    fig, ax = plt.subplots(figsize=(6.4, 1.8), dpi=300)
    fig.patch.set_facecolor(bg_col)
    ax.set_facecolor(bg_col)
    ax.set_xlim(0, 640)
    ax.set_ylim(0, 180)
    ax.axis("off")
    circle = mpatches.Circle((95, 90), 54, facecolor=c1, edgecolor=c3, linewidth=4)
    ax.add_patch(circle)
    inner = mpatches.Circle((95, 90), 22, facecolor=c4, edgecolor="#FFFFFF", linewidth=2.5)
    ax.add_patch(inner)
    ax.text(178, 98, brand_title[:24], fontsize=22, fontweight="bold", color=txt_col, va="center")
    ax.text(178, 56, subtitle[:36], fontsize=11, fontweight="bold", color=c1, va="center")
    for idx, col in enumerate([c1, c2, c3, c4]):
        ax.add_patch(mpatches.Rectangle((178 + idx * 92, 24), 82, 8, facecolor=col))
    fig.savefig(out_png, dpi=300, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)

    return {
        "status": "success",
        "svg_path": str(out_svg),
        "png_path": str(out_png),
        "theme_id": theme.theme_id,
        "palette_hex": theme.palette_hex,
    }
