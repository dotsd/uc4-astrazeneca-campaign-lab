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

"""Dynamic Brand Theme & Custom Color Palette Engine for AstraZeneca Campaign Lab (UC4).

Supports:
1. Official AstraZeneca Formats (`astrazeneca_light` & `astrazeneca_dark`) with official
   Mulberry (#830051), Gold (#F0AB00), Navy (#003865), Teal (#00A082), Coral (#E40046),
   and official AstraZeneca vector logos/icons.
2. Google Brand Theme (`google_brand`) with white background (#FFFFFF), grey text (#5F6368),
   and exact Google brand colors:
   - Blue: Hex #4285F4, RGB (66, 133, 244)
   - Red: Hex #EA4335, RGB (234, 67, 53)
   - Yellow: Hex #FBBC04, RGB (251, 188, 4)
   - Green: Hex #34A853, RGB (52, 168, 83)
3. Arbitrary user-specified custom branding prompts (extracting Hex codes, RGB values,
   background color instructions, text color instructions, and logo preferences).
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert a hex color string like '#4285F4' to an (R, G, B) tuple."""
    clean = hex_color.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        return (131, 0, 81)
    return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert an (R, G, B) tuple to an uppercase '#RRGGBB' string."""
    r, g, b = [max(0, min(255, int(v))) for v in rgb]
    return f"#{r:02X}{g:02X}{b:02X}"


@dataclass
class BrandTheme:
    """Complete visual theme specification for slides, PDFs, SVG charts, and videos."""

    theme_id: str
    theme_name: str
    background_hex: str
    card_background_hex: str
    text_primary_hex: str
    text_secondary_hex: str
    primary_hex: str
    secondary_hex: str
    accent_hex: str
    success_hex: str
    palette_hex: List[str] = field(default_factory=list)
    include_az_logo: bool = True
    logo_variant: str = "colour"  # "colour", "gold", "white", "black", "custom", "none"
    font_family: str = "Helvetica"
    is_dark_mode: bool = False
    compliance_footer: str = (
        "AstraZeneca Campaign Lab  |  Scientific & Commercial Communications Studio"
    )

    @property
    def background_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.background_hex)

    @property
    def card_background_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.card_background_hex)

    @property
    def text_primary_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.text_primary_hex)

    @property
    def text_secondary_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.text_secondary_hex)

    @property
    def primary_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.primary_hex)

    @property
    def secondary_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.secondary_hex)

    @property
    def accent_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.accent_hex)

    @property
    def success_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.success_hex)


PRESET_THEMES: Dict[str, BrandTheme] = {
    "astrazeneca_light": BrandTheme(
        theme_id="astrazeneca_light",
        theme_name="AstraZeneca Corporate Light Executive",
        background_hex="#FFFFFF",
        card_background_hex="#F8F5F7",
        text_primary_hex="#1E293B",
        text_secondary_hex="#475569",
        primary_hex="#830051",    # AstraZeneca Mulberry
        secondary_hex="#003865",  # AstraZeneca Navy
        accent_hex="#F0AB00",     # AstraZeneca Gold
        success_hex="#00A082",    # AstraZeneca Teal
        palette_hex=["#830051", "#F0AB00", "#003865", "#00A082", "#E40046"],
        include_az_logo=True,
        logo_variant="colour",
        is_dark_mode=False,
        compliance_footer=(
            "AstraZeneca Campaign Lab  |  Corporate Scientific & Commercial Framework"
        ),
    ),
    "astrazeneca_dark": BrandTheme(
        theme_id="astrazeneca_dark",
        theme_name="AstraZeneca Dark Executive & Metabolic Plum",
        background_hex="#1E0514",
        card_background_hex="#2E0B20",
        text_primary_hex="#FFFFFF",
        text_secondary_hex="#E2E8F0",
        primary_hex="#F0AB00",    # AstraZeneca Gold
        secondary_hex="#00A082",  # AstraZeneca Teal
        accent_hex="#E40046",     # AstraZeneca Coral/Magenta
        success_hex="#00A082",    # AstraZeneca Teal
        palette_hex=["#F0AB00", "#00A082", "#E40046", "#830051", "#38BDF8"],
        include_az_logo=True,
        logo_variant="gold",
        is_dark_mode=True,
        compliance_footer=(
            "AstraZeneca Campaign Lab  |  Scientific & Commercial Communications"
        ),
    ),
    "google_brand": BrandTheme(
        theme_id="google_brand",
        theme_name="Google Clean White & 4-Color Brand System",
        background_hex="#FFFFFF",
        card_background_hex="#F8F9FA",
        text_primary_hex="#5F6368",    # Grey text as prompted
        text_secondary_hex="#70757A",  # Muted grey text
        primary_hex="#4285F4",         # Google Blue: RGB (66, 133, 244)
        secondary_hex="#EA4335",       # Google Red: RGB (234, 67, 53)
        accent_hex="#FBBC04",          # Google Yellow: RGB (251, 188, 4)
        success_hex="#34A853",         # Google Green: RGB (52, 168, 83)
        palette_hex=["#4285F4", "#EA4335", "#FBBC04", "#34A853"],
        include_az_logo=False,
        logo_variant="custom",
        is_dark_mode=False,
        compliance_footer=(
            "Campaign Lab Studio  |  Custom Brand Theme (#4285F4 · #EA4335 · #FBBC04 · #34A853)"
        ),
    ),
}


def parse_brand_theme(
    theme_prompt: str | None = None,
    include_az_logo: bool | None = None,
) -> BrandTheme:
    """Parse a preset name or free-text branding instruction into a BrandTheme.

    Examples of supported inputs:
    - "astrazeneca_light" or "AstraZeneca format"
    - "astrazeneca_dark"
    - "google_brand" or:
      "use white background for the slides, grey color for text and following branding colors below:
       Blue: Hex #4285F4, RGB (66, 133, 244)
       Red: Hex #EA4335, RGB (234, 67, 53)
       Yellow: Hex #FBBC04, RGB (251, 188, 4)
       Green: Hex #34A853, RGB (52, 168, 83)"
    - Any custom prompt with hex codes (#RRGGBB) or RGB (r, g, b) values.
    """
    if not theme_prompt or not theme_prompt.strip():
        theme = BrandTheme(**PRESET_THEMES["astrazeneca_light"].__dict__)
        theme.palette_hex = list(PRESET_THEMES["astrazeneca_light"].palette_hex)
        if include_az_logo is not None:
            theme.include_az_logo = include_az_logo
        return theme

    raw = theme_prompt.strip()
    lower = raw.lower()

    # Direct preset match
    if lower in PRESET_THEMES:
        base = PRESET_THEMES[lower]
        theme = BrandTheme(**base.__dict__)
        theme.palette_hex = list(base.palette_hex)
        if include_az_logo is not None:
            theme.include_az_logo = include_az_logo
        return theme

    # Check if Google colors or "google" keyword are present
    if (
        "google" in lower
        or ("#4285f4" in lower and "#ea4335" in lower)
    ):
        base = PRESET_THEMES["google_brand"]
        theme = BrandTheme(**base.__dict__)
        theme.palette_hex = list(base.palette_hex)
        if "astrazeneca logo" in lower or "az logo" in lower or include_az_logo is True:
            theme.include_az_logo = True
            theme.logo_variant = "colour"
        elif include_az_logo is False:
            theme.include_az_logo = False
        return theme

    # Check if user explicitly asked for dark AstraZeneca format
    if ("astrazeneca" in lower or "az " in lower) and (
        "dark" in lower or "plum" in lower or "mulberry background" in lower
    ):
        base = PRESET_THEMES["astrazeneca_dark"]
        theme = BrandTheme(**base.__dict__)
        theme.palette_hex = list(base.palette_hex)
        if include_az_logo is not None:
            theme.include_az_logo = include_az_logo
        return theme

    # Extract all hex codes (#RRGGBB) and RGB tuples from the prompt
    found_hex = [
        f"#{m.upper()}"
        for m in re.findall(r"#([0-9a-fA-F]{6})\b", raw)
    ]
    rgb_matches = re.findall(
        r"rgb\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)",
        lower,
    )
    for r_s, g_s, b_s in rgb_matches:
        hx = rgb_to_hex((int(r_s), int(g_s), int(b_s)))
        if hx not in found_hex:
            found_hex.append(hx)

    # Determine background color
    is_dark = False
    bg_hex = "#FFFFFF"
    card_bg_hex = "#F8FAFC"
    if "white background" in lower or "light background" in lower:
        bg_hex = "#FFFFFF"
        card_bg_hex = "#F8F9FA"
        is_dark = False
    elif "dark background" in lower or "black background" in lower or "navy background" in lower:
        bg_hex = "#0F172A"
        card_bg_hex = "#1E293B"
        is_dark = True

    # Determine text color
    if "grey color for text" in lower or "gray color for text" in lower or "grey text" in lower or "gray text" in lower:
        text_primary = "#5F6368"
        text_secondary = "#70757A"
    elif is_dark or "white text" in lower:
        text_primary = "#FFFFFF"
        text_secondary = "#CBD5E1"
    else:
        text_primary = "#1E293B"
        text_secondary = "#475569"

    # Filter out pure white/black from brand accent palette if they were meant as bg/text
    palette = [c for c in found_hex if c not in ("#FFFFFF", "#000000")]
    if not palette:
        palette = ["#830051", "#F0AB00", "#003865", "#00A082"]

    primary = palette[0]
    secondary = palette[1] if len(palette) > 1 else primary
    accent = palette[2] if len(palette) > 2 else secondary
    success = palette[3] if len(palette) > 3 else accent

    # Logo preference
    if include_az_logo is not None:
        use_az_logo = include_az_logo
    elif "no astrazeneca logo" in lower or "without astrazeneca logo" in lower or "no logo" in lower:
        use_az_logo = False
    elif "astrazeneca" in lower or "az logo" in lower:
        use_az_logo = True
    else:
        use_az_logo = True

    return BrandTheme(
        theme_id="custom_brand",
        theme_name="Custom User-Defined Brand Theme",
        background_hex=bg_hex,
        card_background_hex=card_bg_hex,
        text_primary_hex=text_primary,
        text_secondary_hex=text_secondary,
        primary_hex=primary,
        secondary_hex=secondary,
        accent_hex=accent,
        success_hex=success,
        palette_hex=palette,
        include_az_logo=use_az_logo,
        logo_variant="gold" if is_dark else "colour",
        is_dark_mode=is_dark,
        compliance_footer=(
            f"AstraZeneca Campaign Lab  |  Palette: {' · '.join(palette[:4])}"
        ),
    )


def load_scalable_font(size: int, bold: bool = False):
    """Load a TrueType font guaranteed to scale to `size` pixels on both Linux containers and macOS."""
    from pathlib import Path
    from PIL import ImageFont

    candidates: List[str] = []
    try:
        import matplotlib
        from matplotlib.font_manager import FontProperties, findfont

        mpl_ttf_dir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        if bold and (mpl_ttf_dir / "DejaVuSans-Bold.ttf").exists():
            candidates.append(str(mpl_ttf_dir / "DejaVuSans-Bold.ttf"))
        elif not bold and (mpl_ttf_dir / "DejaVuSans.ttf").exists():
            candidates.append(str(mpl_ttf_dir / "DejaVuSans.ttf"))

        fp = FontProperties(family="sans-serif", weight="bold" if bold else "normal")
        found = findfont(fp, fallback_to_default=True)
        if found:
            candidates.append(found)
    except Exception:
        pass

    if bold:
        candidates.extend([
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ])
    else:
        candidates.extend([
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ])

    for path in candidates:
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def resolve_gallery_image(key_or_prompt: str = "rowing"):
    """Resolve a curated 4K Nano Banana Pro photographic gallery asset from `assets/gallery/`."""
    from pathlib import Path

    gallery_dir = Path(__file__).resolve().parent.parent / "assets" / "gallery"
    q = (key_or_prompt or "").lower()

    mapping = [
        (("rowing_pair", "rowing", "row", "scull", "boat", "sunrise", "oars"), "rowing_pair_4k.jpg"),
        (("dual_helix", "helix", "crystal", "molecule", "molecular", "receptor"), "dual_helix_4k.jpg"),
        (("vitality_couple", "vitality", "couple", "walking", "stride", "patient", "horizon", "lifestyle"), "vitality_couple_4k.jpg"),
        (("badminton_tandem", "badminton", "court", "racket"), "badminton_tandem_4k.jpg"),
        (("sumo_equilibrium", "sumo", "equilibrium", "wrestl"), "sumo_equilibrium_4k.jpg"),
        (("glp1_pathway", "glp-1", "glp1", "satiety", "incretin", "pillar 1"), "glp1_pathway_4k.jpg"),
        (("gcg_liver", "glucagon", "gcg", "hepatic", "liver", "steatosis", "lipolysis", "pillar 2"), "gcg_liver_4k.jpg"),
        (("organ_synergy", "organ", "synergy", "systemic", "cardiometabolic"), "organ_synergy_4k.jpg"),
    ]
    for keywords, filename in mapping:
        if any(k in q for k in keywords):
            cand = gallery_dir / filename
            if cand.exists():
                return cand

    default_cand = gallery_dir / "rowing_pair_4k.jpg"
    if default_cand.exists():
        return default_cand
    for f in sorted(gallery_dir.glob("*.jpg")):
        return f
    return None

