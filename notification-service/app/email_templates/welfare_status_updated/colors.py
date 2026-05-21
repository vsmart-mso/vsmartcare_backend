from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatusBoxStyle:
    background: str
    border: str
    accent: str
    label: str


_DEFAULT = StatusBoxStyle(
    background="#FDF2F8",
    border="#FBCFE8",
    accent="#BE185D",
    label="#9D174D",
)


def _parse_hex(hex_color: str) -> tuple[int, int, int] | None:
    raw = hex_color.strip()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return None
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return None


def _to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02X}{max(0, min(255, g)):02X}{max(0, min(255, b)):02X}"


def _mix_toward(r: int, g: int, b: int, target: int, amount: float) -> tuple[int, int, int]:
    return (
        int(r + (target - r) * amount),
        int(g + (target - g) * amount),
        int(b + (target - b) * amount),
    )


def resolve_status_box_style(hex_color: str | None) -> StatusBoxStyle:
    """สร้างสีกล่องสถานะจาก current_status.color (hex)."""
    if not hex_color:
        return _DEFAULT
    rgb = _parse_hex(hex_color)
    if rgb is None:
        return _DEFAULT
    r, g, b = rgb
    bg = _mix_toward(r, g, b, 255, 0.92)
    border = _mix_toward(r, g, b, 255, 0.78)
    label = _mix_toward(r, g, b, 0, 0.28)
    return StatusBoxStyle(
        background=_to_hex(*bg),
        border=_to_hex(*border),
        accent=_to_hex(r, g, b),
        label=_to_hex(*label),
    )
