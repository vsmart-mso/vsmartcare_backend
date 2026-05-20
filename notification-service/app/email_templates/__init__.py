from __future__ import annotations

from typing import Any

from .registry import render_template


def render_email(template_code: str, payload: dict[str, Any]) -> tuple[str, str, str]:
    """Return (subject, plain_text_body, html_body) for a template_code."""
    parts = render_template(template_code, payload)
    return parts.subject, parts.plain_text, parts.html_body
