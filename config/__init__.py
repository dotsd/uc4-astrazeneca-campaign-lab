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

"""Configuration package for AstraZeneca Campaign Lab (UC4).

Exposes runtime settings (`Settings`, `get_settings`) and the dynamic brand theme
and custom hex color palette engine (`BrandTheme`, `PRESET_THEMES`, `parse_brand_theme`).
"""

from config.brand_guidelines import (
    PRESET_THEMES,
    BrandTheme,
    hex_to_rgb,
    parse_brand_theme,
    rgb_to_hex,
)
from config.settings import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
    "BrandTheme",
    "PRESET_THEMES",
    "parse_brand_theme",
    "hex_to_rgb",
    "rgb_to_hex",
]
