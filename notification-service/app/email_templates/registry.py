from __future__ import annotations

from typing import Any

from . import staff_case_status_digest, welfare_status_updated
from .types import EmailParts, EmailRenderer

_REGISTRY: dict[str, EmailRenderer] = {
    welfare_status_updated.TEMPLATE_CODE: welfare_status_updated.render,
    staff_case_status_digest.TEMPLATE_CODE: staff_case_status_digest.render,
}


def render_template(template_code: str, payload: dict[str, Any]) -> EmailParts:
    renderer = _REGISTRY.get(template_code)
    if renderer is None:
        raise ValueError(f"unknown_email_template:{template_code}")
    return renderer(payload)
