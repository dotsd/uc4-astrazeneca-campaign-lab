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

"""Short & Long 1080p HD Campaign Video Generator (`.mp4`) for AstraZeneca Campaign Lab (UC4).

Supports:
- `video_length_mode="short"` (16–24 seconds, 4 scenes — ideal for congress social teasers,
  booth loops, and quick executive highlights)
- `video_length_mode="long"` (60–80 seconds, 8–10 scenes — ideal for comprehensive scientific
  mechanism walk-throughs, full slide deck narrations, and complementary strategy deep-dives)
- Dynamic brand theme bar and lower-third captions styled in the user's chosen palette
  (Google 4-color, AstraZeneca Light/Dark, or custom hex codes).
"""
from __future__ import annotations

import logging
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw

from config.brand_guidelines import BrandTheme, hex_to_rgb, parse_brand_theme
from config.settings import get_settings
from tools.image_tools import _load_font, _wrap_text, generate_4k_campaign_key_visual
from tools.logo_tools import get_pil_logo_for_theme

logger = logging.getLogger(__name__)


def _synthesize_ambient_chord_wav(wav_path: Path, duration_sec: float) -> Path:
    """Generate a warm, studio-grade ambient harmonic audio track (.wav) for guaranteed audio playback."""
    sample_rate = 24000
    n_samples = int(sample_rate * duration_sec)
    freqs = [130.81, 196.00, 246.94, 293.66, 392.00]  # Warm Cmaj9 cinematic chord

    with wave.open(str(wav_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            t = i / sample_rate
            env = 1.0
            if t < 1.5:
                env = t / 1.5
            elif t > duration_sec - 2.0:
                env = max(0.0, (duration_sec - t) / 2.0)
            lfo = 0.85 + 0.15 * math.sin(2.0 * math.pi * 0.25 * t)
            val = 0.0
            for idx, f in enumerate(freqs):
                val += (0.18 / (idx + 1)) * math.sin(2.0 * math.pi * f * t)
            sample = int(max(-32767, min(32767, val * env * lfo * 14000)))
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(frames)
    return wav_path


def generate_campaign_video_mp4(
    campaign_name: str,
    strapline: str = "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
    video_length_mode: str = "short",
    scene_captions: Optional[List[Dict[str, str]]] = None,
    existing_frame_paths: Optional[List[str]] = None,
    theme_prompt: str = "astrazeneca_dark",
    include_az_logo: Optional[bool] = None,
    output_filename: str = "campaign_strategy_video.mp4",
) -> Dict[str, Any]:
    """Generate a Short (`16s–24s`) or Long (`60s–80s`) 1080p HD `.mp4` campaign video.

    Args:
        campaign_name: Name of the drug, product, or campaign.
        strapline: Single master strapline displayed in the video.
        video_length_mode: Either `'short'` (16-24s, 4 scenes) or `'long'` (60-80s, 8 scenes).
        scene_captions: Optional list of dicts with `'title'` and `'subtitle'` per scene.
        existing_frame_paths: Optional list of 4K slide/key-visual PNGs to animate.
        theme_prompt: Preset name or custom hex color prompt (e.g., Google colors or AZ format).
        include_az_logo: Whether to overlay the official AstraZeneca vector logo.
        output_filename: Output `.mp4` filename.

    Returns:
        Dictionary with `video_path`, `duration_seconds`, `video_length_mode`, and `scene_count`.
    """
    settings = get_settings()
    theme: BrandTheme = parse_brand_theme(theme_prompt, include_az_logo=include_az_logo)
    mode = "long" if "long" in (video_length_mode or "").lower() else "short"

    if mode == "long":
        default_scenes = [
            {"title": f"{campaign_name}: Strategic Vision", "subtitle": strapline},
            {"title": "Addressing Complex Multi-System Disease", "subtitle": "Moving beyond single-pathway monotherapy limitations"},
            {"title": "Pillar 1: Central & Systemic Control", "subtitle": "Targeted receptor engagement driving foundational efficacy"},
            {"title": "Pillar 2: Direct Organ Energy Mobilization", "subtitle": "Unlocking hepatic lipid clearance and metabolic expenditure"},
            {"title": "Complementary Dual-Pathway Synergy", "subtitle": "Two distinct pathways working in synchronized balance"},
            {"title": "High-Quality Body Composition & Organ Health", "subtitle": "Deep fat reduction while preserving lean tissue integrity"},
            {"title": "Broad Cardiometabolic & Systemic Impact", "subtitle": "Addressing interconnected clinical priorities simultaneously"},
            {"title": f"{campaign_name} — Omnichannel Launch Ready", "subtitle": strapline},
        ]
        sec_per_scene = 8.0
    else:
        default_scenes = [
            {"title": f"{campaign_name}: Complementary Strategy", "subtitle": strapline},
            {"title": "Pillar 1 + Pillar 2 Working in Tandem", "subtitle": "Combining systemic regulation with direct organ mobilization"},
            {"title": "Superior Multi-System Clinical Impact", "subtitle": "Synchronized efficacy across weight, organ lipid clearance & metabolism"},
            {"title": strapline, "subtitle": f"{campaign_name}  ·  Scientific & Commercial Studio"},
        ]
        sec_per_scene = 5.0

    scenes = scene_captions if scene_captions else default_scenes
    total_duration = len(scenes) * sec_per_scene

    # Prepare 1920x1080 scene master frames
    vw, vh = (1920, 1080)
    palette = theme.palette_hex or [
        theme.primary_hex,
        theme.secondary_hex,
        theme.accent_hex,
        theme.success_hex,
    ]
    logo_img = get_pil_logo_for_theme(theme, max_height=54)
    f_title = _load_font(52, bold=True)
    f_sub = _load_font(34, bold=False)
    f_badge = _load_font(26, bold=True)

    valid_existing = [
        Path(p) for p in (existing_frame_paths or []) if p and Path(p).exists()
    ]
    if not valid_existing:
        kv_res = generate_4k_campaign_key_visual(
            campaign_name=campaign_name,
            headline=f"{campaign_name}: {strapline}",
            strapline=strapline,
            theme_prompt=theme_prompt,
            include_az_logo=include_az_logo,
            output_filename=f"{campaign_name.lower().replace(' ', '_')}_video_base_4k.png",
        )
        valid_existing = [Path(kv_res["image_path"])]

    scene_frame_paths: List[Path] = []
    for idx, sc in enumerate(scenes):
        src_img_path = valid_existing[idx % len(valid_existing)]
        base_img = Image.open(src_img_path).convert("RGBA").resize((vw, vh), Image.Resampling.LANCZOS)

        overlay = Image.new("RGBA", (vw, vh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")

        # Lower-third glassmorphic caption bar
        bg_r, bg_g, bg_b = theme.background_rgb
        draw.rounded_rectangle(
            (70, vh - 245, vw - 70, vh - 50),
            radius=24,
            fill=(bg_r, bg_g, bg_b, 232),
            outline=(*hex_to_rgb(palette[idx % len(palette)]), 255),
            width=4,
        )

        # Multi-color brand stripe on top of lower-third bar
        seg_w = (vw - 140) // len(palette)
        for p_i, hx in enumerate(palette):
            x0 = 70 + p_i * seg_w
            x1 = (vw - 70) if p_i == len(palette) - 1 else x0 + seg_w
            draw.rectangle((x0, vh - 245, x1, vh - 233), fill=(*hex_to_rgb(hx), 255))

        # Scene badge
        draw.rounded_rectangle(
            (105, vh - 215, 315, vh - 172),
            radius=10,
            fill=(*hex_to_rgb(palette[idx % len(palette)]), 255),
        )
        draw.text(
            (125, vh - 208),
            f"SCENE {idx + 1:02d} / {len(scenes):02d}",
            font=f_badge,
            fill=(255, 255, 255, 255),
        )

        # Scene Title & Subtitle
        draw.text(
            (340, vh - 216),
            sc.get("title", campaign_name)[:56],
            font=f_title,
            fill=(*theme.text_primary_rgb, 255),
        )
        for s_line in _wrap_text(draw, sc.get("subtitle", strapline), f_sub, vw - 480)[:1]:
            draw.text(
                (105, vh - 130),
                s_line,
                font=f_sub,
                fill=(*theme.text_secondary_rgb, 255),
            )

        composed = Image.alpha_composite(base_img, overlay)
        if logo_img is not None:
            composed.paste(logo_img, (vw - 105 - logo_img.width, vh - 135), logo_img)

        frame_file = settings.output_dir / f"_vid_scene_{idx:02d}.png"
        composed.convert("RGB").save(frame_file, format="PNG")
        scene_frame_paths.append(frame_file)

    wav_path = settings.output_dir / "_vid_soundtrack.wav"
    _synthesize_ambient_chord_wav(wav_path, total_duration)

    out_mp4 = settings.output_dir / output_filename
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        concat_file = settings.output_dir / "_vid_concat.txt"
        lines = []
        for fp in scene_frame_paths:
            lines.append(f"file '{fp.resolve()}'")
            lines.append(f"duration {sec_per_scene:.2f}")
        lines.append(f"file '{scene_frame_paths[-1].resolve()}'")
        concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cmd = [
            ffmpeg_bin,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-i",
            str(wav_path),
            "-c:v",
            "libx264",
            "-r",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(out_mp4),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return {
        "status": "success",
        "video_path": str(out_mp4),
        "video_length_mode": mode,
        "duration_seconds": total_duration,
        "scene_count": len(scenes),
        "resolution": "1920x1080 (Full HD)",
        "theme_id": theme.theme_id,
    }
