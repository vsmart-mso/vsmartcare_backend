from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

# สีอ้างอิงจาก frontend (พม. CARE / vsmartcare)
COLOR_BRAND = "#BE185D"
COLOR_BRAND_DARK = "#9D174D"
COLOR_BRAND_LIGHT = "#FDF2F8"
COLOR_BRAND_BORDER = "#FBCFE8"

COLOR_PRIMARY = "#1A56DB"
COLOR_PRIMARY_LIGHT = "#EFF6FF"

COLOR_TEXT = "#334155"
COLOR_TEXT_HEADING = "#0F172A"
COLOR_TEXT_MUTED = "#64748B"
COLOR_BG = "#F8FAFC"
COLOR_BORDER = "#E2E8F0"
COLOR_SURFACE = "#FFFFFF"

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_LOGO_PATH = _STATIC_DIR / "Logo_origin.png"


@lru_cache(maxsize=1)
def msdhs_logo_data_uri() -> str:
    """Embed MSDHS logo for email clients (no public URL required)."""
    if not _LOGO_PATH.is_file():
        raise FileNotFoundError(f"email logo not found: {_LOGO_PATH}")
    encoded = base64.standard_b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
