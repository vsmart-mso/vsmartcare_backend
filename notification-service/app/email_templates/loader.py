from __future__ import annotations

from pathlib import Path

_TEMPLATES_ROOT = Path(__file__).resolve().parent


def templates_dir() -> Path:
    return _TEMPLATES_ROOT


def load_html(relative_path: str) -> str:
    path = _TEMPLATES_ROOT / relative_path
    return path.read_text(encoding="utf-8")


def fill(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template
