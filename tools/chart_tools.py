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

"""Vector SVG & 450-DPI PNG Chart, Graph & Infographic Generator for AstraZeneca Campaign Lab (UC4).

Generates publication-grade vector `.svg` and high-resolution `.png` charts styled dynamically
in any user-specified brand palette (e.g., Google #4285F4/#EA4335/#FBBC04/#34A853, AstraZeneca
Corporate Mulberry/Gold/Navy/Teal, Dark Metabolic Plum, or custom hex codes).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

from config.brand_guidelines import BrandTheme, parse_brand_theme
from config.settings import get_settings


def generate_campaign_chart_svg_and_png(
    chart_title: str,
    categories: List[str],
    series_primary_values: List[float],
    series_primary_label: str = "Primary Strategy / Dual Mechanism",
    series_secondary_values: Optional[List[float]] = None,
    series_secondary_label: str = "Comparator / Standard Baseline",
    y_axis_label: str = "Relative Impact / Efficacy Score (%)",
    chart_type: str = "grouped_bar",
    theme_prompt: str = "astrazeneca_light",
    output_basename: str = "campaign_evidence_chart",
) -> Dict[str, Any]:
    """Generate both a scalable vector `.svg` and a `450-DPI .png` chart in the active brand theme.

    Args:
        chart_title: Title displayed at the top of the chart.
        categories: X-axis category labels (e.g. endpoints, organs, timepoints, KPIs).
        series_primary_values: Numeric values for the primary series.
        series_primary_label: Legend label for the primary series.
        series_secondary_values: Optional numeric values for a second comparison series.
        series_secondary_label: Legend label for the secondary series.
        y_axis_label: Label for the vertical axis.
        chart_type: 'grouped_bar', 'horizontal_bar', or 'line_trajectory'.
        theme_prompt: Preset name or custom hex color prompt (e.g., Google colors or AZ format).
        output_basename: Base filename without extension.

    Returns:
        Dictionary with `svg_path`, `png_path`, `theme_id`, and `palette_hex`.
    """
    settings = get_settings()
    theme: BrandTheme = parse_brand_theme(theme_prompt)

    if not categories:
        categories = ["Endpoint 1", "Endpoint 2", "Endpoint 3", "Endpoint 4"]
    if not series_primary_values or len(series_primary_values) != len(categories):
        series_primary_values = [82.0, 76.0, 88.0, 91.0][: len(categories)]

    out_svg = settings.output_dir / f"{output_basename}.svg"
    out_png = settings.output_dir / f"{output_basename}.png"

    fig, ax = plt.subplots(figsize=(10.5, 5.8), dpi=450)
    fig.patch.set_facecolor(theme.background_hex)
    ax.set_facecolor(theme.card_background_hex)

    x = np.arange(len(categories))
    c_prim = theme.primary_hex
    c_sec = theme.secondary_hex
    c_acc = theme.accent_hex
    txt_p = theme.text_primary_hex
    txt_s = theme.text_secondary_hex

    if chart_type == "line_trajectory":
        ax.plot(
            x,
            series_primary_values,
            marker="o",
             markersize=10,
            linewidth=4.0,
            color=c_prim,
            label=series_primary_label,
        )
        for xi, val in zip(x, series_primary_values):
            ax.annotate(
                f"{val:.1f}",
                (xi, val),
                textcoords="offset points",
                xytext=(0, 12),
                ha="center",
                fontsize=12,
                fontweight="bold",
                color=txt_p,
            )
        if series_secondary_values and len(series_secondary_values) == len(categories):
            ax.plot(
                x,
                series_secondary_values,
                marker="s",
                markersize=9,
                linewidth=3.2,
                linestyle="--",
                color=c_sec,
                label=series_secondary_label,
            )
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=13, fontweight="bold", color=txt_p)
    elif chart_type == "horizontal_bar":
        bars = ax.barh(
            x,
            series_primary_values,
            height=0.55,
            color=[
                theme.palette_hex[i % len(theme.palette_hex)]
                for i in range(len(categories))
            ],
            edgecolor="none",
        )
        ax.set_yticks(x)
        ax.set_yticklabels(categories, fontsize=13, fontweight="bold", color=txt_p)
        for bar in bars:
            w = bar.get_width()
            ax.text(
                w + max(series_primary_values) * 0.02,
                bar.get_y() + bar.get_height() / 2,
                f"{w:.1f}",
                va="center",
                ha="left",
                fontsize=12,
                fontweight="bold",
                color=txt_p,
            )
    else:
        if series_secondary_values and len(series_secondary_values) == len(categories):
            width = 0.36
            b1 = ax.bar(
                x - width / 2,
                series_primary_values,
                width,
                label=series_primary_label,
                color=c_prim,
                edgecolor="none",
            )
            b2 = ax.bar(
                x + width / 2,
                series_secondary_values,
                width,
                label=series_secondary_label,
                color=c_sec,
                edgecolor="none",
            )
            for bar in b1:
                h = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    h + max(series_primary_values) * 0.02,
                    f"{h:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=11,
                    fontweight="bold",
                    color=txt_p,
                )
            for bar in b2:
                h = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    h + max(series_primary_values) * 0.02,
                    f"{h:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=11,
                    fontweight="bold",
                    color=txt_s,
                )
        else:
            palette = theme.palette_hex or [c_prim, c_sec, c_acc, theme.success_hex]
            b1 = ax.bar(
                x,
                series_primary_values,
                width=0.52,
                label=series_primary_label,
                color=[palette[i % len(palette)] for i in range(len(categories))],
            )
            for bar in b1:
                h = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    h + max(series_primary_values) * 0.02,
                    f"{h:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=12,
                    fontweight="bold",
                    color=txt_p,
                )
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=13, fontweight="bold", color=txt_p)

    ax.set_title(
        chart_title,
        fontsize=17,
        fontweight="bold",
        color=txt_p,
        pad=18,
        loc="left",
    )
    ax.set_ylabel(y_axis_label, fontsize=13, fontweight="bold", color=txt_s)
    ax.tick_params(axis="both", colors=txt_s, labelsize=12)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color(txt_s)
        ax.spines[spine].set_linewidth(1.2)
    ax.grid(axis="y", linestyle="--", alpha=0.25, color=txt_s)

    if series_secondary_values:
        leg = ax.legend(frameon=True, facecolor=theme.background_hex, edgecolor=c_prim, fontsize=11)
        for text in leg.get_texts():
            text.set_color(txt_p)

    plt.tight_layout()
    fig.savefig(out_svg, format="svg", bbox_inches="tight")
    fig.savefig(out_png, format="png", dpi=450, bbox_inches="tight")
    plt.close(fig)

    return {
        "status": "success",
        "svg_path": str(out_svg),
        "png_path": str(out_png),
        "chart_title": chart_title,
        "theme_id": theme.theme_id,
        "palette_hex": theme.palette_hex,
    }


def generate_pathway_synergy_svg_and_png(
    diagram_title: str = "Complementary Mechanism & Strategic Synergy Architecture",
    left_pillar_title: str = "Pillar 1: Primary Pathway",
    left_pillar_bullets: Optional[List[str]] = None,
    right_pillar_title: str = "Pillar 2: Complementary Pathway",
    right_pillar_bullets: Optional[List[str]] = None,
    central_outcome_title: str = "Integrated Clinical & Commercial Outcome",
    theme_prompt: str = "astrazeneca_light",
    output_basename: str = "campaign_synergy_architecture",
) -> Dict[str, Any]:
    """Generate a vector `.svg` and `450-DPI .png` strategic/scientific synergy diagram."""
    settings = get_settings()
    theme = parse_brand_theme(theme_prompt)

    left_bullets = left_pillar_bullets or [
        "Targeted receptor engagement & signaling",
        "Systemic metabolic & satiety regulation",
        "Proven foundational clinical efficacy",
    ]
    right_bullets = right_pillar_bullets or [
        "Direct organ-specific energy expenditure",
        "Lipid oxidation & metabolic clearance",
        "Complementary multi-system protection",
    ]

    out_svg = settings.output_dir / f"{output_basename}.svg"
    out_png = settings.output_dir / f"{output_basename}.png"

    fig, ax = plt.subplots(figsize=(12, 6.2), dpi=450)
    fig.patch.set_facecolor(theme.background_hex)
    ax.set_facecolor(theme.background_hex)
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 62)
    ax.axis("off")

    # Title banner
    ax.text(
        60,
        57,
        diagram_title,
        fontsize=17,
        fontweight="bold",
        color=theme.text_primary_hex,
        ha="center",
        va="center",
    )

    # Left Pillar Card
    left_box = mpatches.FancyBboxPatch(
        (5, 22),
        46,
        29,
        boxstyle="round,pad=1.5,rounding_size=2.5",
        facecolor=theme.card_background_hex,
        edgecolor=theme.primary_hex,
        linewidth=3,
    )
    ax.add_patch(left_box)
    ax.text(
        28,
        46.5,
        left_pillar_title[:36],
        fontsize=14,
        fontweight="bold",
        color=theme.primary_hex,
        ha="center",
    )
    for idx, b in enumerate(left_bullets[:3]):
        ax.text(
            9,
            39.5 - idx * 6.5,
            f"•  {b[:48]}",
            fontsize=11.5,
            fontweight="bold",
            color=theme.text_primary_hex,
            va="center",
        )

    # Right Pillar Card
    right_box = mpatches.FancyBboxPatch(
        (69, 22),
        46,
        29,
        boxstyle="round,pad=1.5,rounding_size=2.5",
        facecolor=theme.card_background_hex,
        edgecolor=theme.secondary_hex,
        linewidth=3,
    )
    ax.add_patch(right_box)
    ax.text(
        92,
        46.5,
        right_pillar_title[:36],
        fontsize=14,
        fontweight="bold",
        color=theme.secondary_hex,
        ha="center",
    )
    for idx, b in enumerate(right_bullets[:3]):
        ax.text(
            73,
            39.5 - idx * 6.5,
            f"•  {b[:48]}",
            fontsize=11.5,
            fontweight="bold",
            color=theme.text_primary_hex,
            va="center",
        )

    # Plus / Synergy Hub
    hub = mpatches.Circle(
        (60, 36.5),
        5.5,
        facecolor=theme.accent_hex,
        edgecolor=theme.background_hex,
        linewidth=3,
    )
    ax.add_patch(hub)
    ax.text(
        60,
        36.5,
        "+",
        fontsize=22,
        fontweight="bold",
        color="#FFFFFF" if not theme.is_dark_mode else "#1E0514",
        ha="center",
        va="center",
    )

    # Bottom Integrated Outcome Banner
    bottom_box = mpatches.FancyBboxPatch(
        (16, 4.5),
        88,
        11.5,
        boxstyle="round,pad=1.2,rounding_size=2.5",
        facecolor=theme.primary_hex,
        edgecolor=theme.accent_hex,
        linewidth=2.5,
    )
    ax.add_patch(bottom_box)
    ax.text(
        60,
        10.2,
        central_outcome_title[:68],
        fontsize=14.5,
        fontweight="bold",
        color="#FFFFFF",
        ha="center",
        va="center",
    )

    fig.savefig(out_svg, format="svg", bbox_inches="tight")
    fig.savefig(out_png, format="png", dpi=450, bbox_inches="tight")
    plt.close(fig)

    return {
        "status": "success",
        "svg_path": str(out_svg),
        "png_path": str(out_png),
        "theme_id": theme.theme_id,
    }
