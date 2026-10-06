#!/usr/bin/env python3
"""CLI Runner for AstraZeneca Campaign Lab (UC4).

Examples:
  # Run with AstraZeneca Corporate Light format:
  python run_campaign_lab.py --campaign "AZD9550 Dual Agonist" --theme "astrazeneca_light"

  # Run with Google Brand Theme (White background, Grey text, #4285F4/#EA4335/#FBBC04/#34A853):
  python run_campaign_lab.py --campaign "Cloud Health AI" --theme "use white background for the slides, grey color for text and following branding colors below: Blue: Hex #4285F4, Red: Hex #EA4335, Yellow: Hex #FBBC04, Green: Hex #34A853" --no-az-logo

  # Run with Long 64s Video and an attached PDF slide deck:
  python run_campaign_lab.py --campaign "AZD9550" --theme "astrazeneca_dark" --video-length long --attachment path/to/slides.pdf
"""
from __future__ import annotations

import argparse
import json
from agents.orchestrator_agent import run_full_campaign_lab_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AstraZeneca Campaign Lab (UC4) — Generic Multimodal Campaign Studio"
    )
    parser.add_argument(
        "--campaign",
        type=str,
        default="AZD9550 Complementary Strategy",
        help="Name of the campaign, molecule, or product.",
    )
    parser.add_argument(
        "--objective",
        type=str,
        default="Synthesize complementary dual-pathway mechanisms into executive slides, A4 pamphlet, 4K visuals, SVG charts, and video.",
        help="Campaign objective or brief summary.",
    )
    parser.add_argument(
        "--strapline",
        type=str,
        default="TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
        help="Single unifying master strapline.",
    )
    parser.add_argument(
        "--theme",
        type=str,
        default="astrazeneca_light",
        help="Brand preset ('astrazeneca_light', 'astrazeneca_dark', 'google_brand') or custom hex/RGB prompt.",
    )
    parser.add_argument(
        "--no-az-logo",
        action="store_true",
        help="Omit the official AstraZeneca logo from generated deliverables.",
    )
    parser.add_argument(
        "--video-length",
        type=str,
        choices=["short", "long"],
        default="short",
        help="Generate either a 'short' (20s) or 'long' (64s) 1080p HD MP4 video.",
    )
    parser.add_argument(
        "--attachment",
        type=str,
        default=None,
        help="Optional path to an attached PDF, DOCX, TXT, or Image file.",
    )
    parser.add_argument(
        "--upload-gcs",
        action="store_true",
        help="Upload generated deliverables to gs://astrazeneca-ge-pilot-usecase/UC4/.",
    )

    args = parser.parse_args()
    include_az = False if args.no_az_logo else None

    result = run_full_campaign_lab_pipeline(
        campaign_name=args.campaign,
        campaign_objective=args.objective,
        master_strapline=args.strapline,
        theme_prompt=args.theme,
        include_az_logo=include_az,
        video_length_mode=args.video_length,
        attached_file_path=args.attachment,
        upload_to_gcs=args.upload_gcs,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
