from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class InlineImage:
    """รูปฝังใน HTML — อ้างใน img ด้วย src=\"cid:{content_id}\"."""

    content_id: str
    data: bytes
    subtype: str = "png"
    filename: str = "logo.png"


@dataclass(frozen=True)
class EmailParts:
    subject: str
    plain_text: str
    html_body: str
    inline_images: tuple[InlineImage, ...] = ()


EmailRenderer = Callable[[dict[str, Any]], EmailParts]
