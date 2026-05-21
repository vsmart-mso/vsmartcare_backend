from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .types import InlineImage

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
MSDHS_LOGO_CONTENT_ID = "msdhs-logo"


@lru_cache(maxsize=1)
def _msdhs_logo_bytes() -> bytes:
    if not _LOGO_PATH.is_file():
        raise FileNotFoundError(f"email logo not found: {_LOGO_PATH}")
    return _LOGO_PATH.read_bytes()


def msdhs_logo_cid_src() -> str:
    """src สำหรับ <img> — Gmail/Outlook ไม่แสดง data: URI ต้องใช้ cid + inline attachment."""
    return f"cid:{MSDHS_LOGO_CONTENT_ID}"


def msdhs_logo_inline_image() -> InlineImage:
    return InlineImage(
        content_id=MSDHS_LOGO_CONTENT_ID,
        data=_msdhs_logo_bytes(),
        subtype="png",
        filename="Logo_origin.png",
    )
