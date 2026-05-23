from __future__ import annotations

from typing import Any

from ..branding import msdhs_logo_inline_image
from ..types import EmailParts
from .context import parse_payload
from .html import build_html_body
from .plain import build_plain_text
from .subject import build_subject

TEMPLATE_CODE = "STAFF_CASE_STATUS_DIGEST"


def render(payload: dict[str, Any]) -> EmailParts:
    ctx = parse_payload(payload)
    subject = build_subject(ctx)
    return EmailParts(
        subject=subject,
        plain_text=build_plain_text(ctx),
        html_body=build_html_body(ctx, subject),
        inline_images=(msdhs_logo_inline_image(),),
    )
