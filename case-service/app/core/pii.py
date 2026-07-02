"""PII masking for logs and error messages (ME-08)."""

from __future__ import annotations

import re

_CID_RE = re.compile(r"\b\d{13}\b")


def mask_cid(value: str | None) -> str:
    raw = (value or "").strip()
    if len(raw) != 13 or not raw.isdigit():
        return "***"
    return f"{raw[:3]}****{raw[-4:]}"


def mask_pii_text(text: str) -> str:
    return _CID_RE.sub(lambda m: mask_cid(m.group(0)), text or "")
