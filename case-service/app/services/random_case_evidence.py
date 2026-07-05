"""สร้างรูปหลักฐานจำลองสำหรับเคสสุ่ม (admin dev/staging).

รวม: สมุดบัญชี, รูปเยี่ยมบ้าน (5 รูป), ทะเบียนบ้าน, บัตรสมาชิก
ยกเว้น: KTB (11), อื่น ๆ (99)
"""

from __future__ import annotations

import struct
import uuid
import zlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.attachment_types import (
    ATTACHMENT_TYPE_KTB_CORPORATE,
    ATTACHMENT_TYPE_OTHER,
)
from ..models.lookup import AttachmentType
from ..models.welfare import WelfareEvidence
from ..settings import resolved_upload_root

# หลักฐานระดับผู้ยื่น — รวมรูปเยี่ยมบ้าน (หน้าดูข้อมูล staff แสดงส่วนนี้เป็นหลัก)
_APPLICANT_PLACEHOLDER_TYPES: tuple[tuple[int, str, tuple[int, int, int]], ...] = (
    (1, "bank_book", (59, 130, 246)),    # blue
    (2, "exterior", (34, 197, 94)),      # green
    (3, "interior", (234, 179, 8)),      # amber
    (4, "person", (168, 85, 247)),       # purple
    (5, "problem", (239, 68, 68)),       # red
    (8, "family", (20, 184, 166)),       # teal
    (6, "house_home", (249, 115, 22)),   # orange
    (7, "house_person", (236, 72, 153)), # pink
)

# หลักฐานระดับสมาชิกครัวเรือน
_MEMBER_PLACEHOLDER_TYPES: tuple[tuple[int, str, tuple[int, int, int]], ...] = (
    (12, "id_card", (14, 165, 233)),
    (6, "house_home", (249, 115, 22)),
    (7, "house_person", (236, 72, 153)),
)

_EXCLUDED_ATTACHMENT_IDS = frozenset({
    ATTACHMENT_TYPE_KTB_CORPORATE,
    ATTACHMENT_TYPE_OTHER,
})

_PLACEHOLDER_SIZE = 64


def _png_rgb(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """สร้าง PNG สีทึบ — มองเห็นได้ชัดในหน้าดูข้อมูล."""
    r, g, b = rgb
    row = bytes([r, g, b] * width)
    raw = b"".join(b"\x00" + row for _ in range(height))
    compressed = zlib.compress(raw, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


def _placeholder_blob(rgb: tuple[int, int, int]) -> bytes:
    return _png_rgb(_PLACEHOLDER_SIZE, _PLACEHOLDER_SIZE, rgb)


async def _existing_attachment_type_ids(session: AsyncSession) -> set[int]:
    rows = await session.scalars(select(AttachmentType.id))
    return set(rows.all())


def _write_placeholder_file(
    applicant_id: int,
    *,
    suffix: str,
    rgb: tuple[int, int, int],
) -> tuple[str, str, int]:
    """บันทึกไฟล์ PNG จำลองลง upload root — คืน (relative_path, stored_name, size)."""
    blob = _placeholder_blob(rgb)
    base = resolved_upload_root()
    dest_dir = (base / str(applicant_id)).resolve()
    try:
        dest_dir.relative_to(base.resolve())
    except ValueError as exc:
        raise RuntimeError("upload_path_invalid") from exc

    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}_{suffix}.png"
    full_path: Path = dest_dir / stored
    full_path.write_bytes(blob)
    return f"{applicant_id}/{stored}", stored, len(blob)


def _add_evidence_row(
    session: AsyncSession,
    *,
    applicant_id: int,
    attachment_type_id: int,
    label: str,
    household_member_id: int | None,
    file_path: str,
    stored_name: str,
    file_size: int,
) -> None:
    session.add(
        WelfareEvidence(
            attachment_type_id=attachment_type_id,
            applicant_id=applicant_id,
            file_path=file_path,
            file_original_name=f"mock_{label}.png",
            file_stored_name=stored_name,
            file_size=file_size,
            file_other_type_name=None,
            household_member_id=household_member_id,
        )
    )


async def attach_random_case_placeholders(
    session: AsyncSession,
    *,
    applicant_id: int,
    household_member_ids: list[int],
) -> int:
    """แนบรูปจำลอง — คืนจำนวนแถว welfare_evidences ที่สร้าง."""
    available = await _existing_attachment_type_ids(session)
    created = 0

    for type_id, label, rgb in _APPLICANT_PLACEHOLDER_TYPES:
        if type_id not in available or type_id in _EXCLUDED_ATTACHMENT_IDS:
            continue
        file_path, stored_name, file_size = _write_placeholder_file(
            applicant_id, suffix=label, rgb=rgb
        )
        _add_evidence_row(
            session,
            applicant_id=applicant_id,
            attachment_type_id=type_id,
            label=label,
            household_member_id=None,
            file_path=file_path,
            stored_name=stored_name,
            file_size=file_size,
        )
        created += 1

    for member_id in household_member_ids:
        for type_id, label, rgb in _MEMBER_PLACEHOLDER_TYPES:
            if type_id not in available or type_id in _EXCLUDED_ATTACHMENT_IDS:
                continue
            member_label = f"member_{member_id}_{label}"
            file_path, stored_name, file_size = _write_placeholder_file(
                applicant_id, suffix=member_label, rgb=rgb
            )
            _add_evidence_row(
                session,
                applicant_id=applicant_id,
                attachment_type_id=type_id,
                label=member_label,
                household_member_id=member_id,
                file_path=file_path,
                stored_name=stored_name,
                file_size=file_size,
            )
            created += 1

    if created:
        await session.flush()
    return created
