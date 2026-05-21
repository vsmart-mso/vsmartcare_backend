from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class EmailParts:
    subject: str
    plain_text: str
    html_body: str


EmailRenderer = Callable[[dict[str, Any]], EmailParts]
