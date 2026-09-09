"""แตกฟิลด์จาก payload ของ AINU eKYC ลงคอลัมน์ของ `liveness_attempts`.

กฎเหล็กข้อเดียว: **ห้ามโยน exception ไม่ว่า payload จะหน้าตาอย่างไร**
ถ้าอ่านไม่ออกก็คืนค่าที่อ่านได้เท่าที่มี — payload ถูกเก็บไว้ครบ (ยกเว้นภาพ ดู strip_images)
จึงกลับมา re-parse ทีหลังได้เสมอเมื่อ AINU เปลี่ยน shape

เกณฑ์ว่าฟิลด์ไหนควรดึงออกมาเป็นคอลัมน์: ต้อง WHERE / GROUP BY / JOIN / INDEX กับมันไหม
ถ้าไม่ ปล่อยไว้ในก้อนดิบ (ไม่งั้นจะกลายเป็น 25 คอลัมน์ที่ mirror schema ของ vendor ที่เราคุมไม่ได้)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..models.liveness_attempt import STATUS_COMPLETED, STATUS_FAILED

logger = logging.getLogger("case-service.liveness")

#: payload จริงวันนี้ ≤ ~1.9 KB ส่วนภาพใบหน้า base64 ภาพเดียว ~270 KB
#: 8 KB จึงแยกสองกรณีนี้ขาดโดยไม่ปลุกเทียมเวลา AINU เพิ่มฟิลด์ metadata ธรรมดา
PAYLOAD_WARN_BYTES = 8 * 1024

#: ฟิลด์ที่ AINU ส่งภาพ base64 มา — ตัดออกก่อนเก็บลง DB (ดู strip_images)
#: ตัดตาม "ชื่อ key" อย่างเดียว ไม่ตัดตามความยาวสตริง จึงไม่กระทบ signature (684 ตัวอักษร)
#: ที่ต้องเก็บไว้ verify ย้อนหลัง
IMAGE_KEYS: frozenset[str] = frozenset(
    {
        "livenessImage",
        "fullFrontThaiCard",
        "fullFrontThaiCardSupport",
        "thaiIDPortrait",
    }
)

#: ค่าที่ AINU ส่งมาใน transactionStatus — `pending_DOPA` เกิดเฉพาะ workflow ที่มี dopa
#: flow ของเราเป็น liveness อย่างเดียวจึงไม่ควรเจอ แต่ AINU ปรับ flow ฝั่งเขาได้เอง
_VENDOR_STATUSES = frozenset({STATUS_COMPLETED, STATUS_FAILED, "pending_DOPA"})

_STATUS_MAX_LEN = 16


@dataclass(frozen=True)
class ParsedLiveness:
    """ค่าที่จะเขียนลงคอลัมน์ — ทุกตัวยกเว้น status เป็น None ได้"""

    status: str
    transaction_id: str | None = None
    liveness_reason: str | None = None
    fail_reason: str | None = None
    description: str | None = None
    sdk_version: str | None = None
    device: str | None = None
    completed_at: datetime | None = None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _pick(payload: dict[str, Any], key: str) -> Any:
    """อ่านค่าเผื่อทั้ง `result.<key>` และ `result.data.<key>`.

    เอกสาร AINU ขัดกันเองเรื่องตำแหน่งของ `transactionStatus`
    (ดู liveness_frontend_guide.md ข้อ 9) จึงอ่านสองที่กับทุกฟิลด์ ไม่ใช่เฉพาะตัวนั้น
    """
    if key in payload:
        return payload[key]
    return _as_dict(payload.get("data")).get(key)


def _text(value: Any, max_len: int) -> str | None:
    """บังคับเป็น str ที่ยาวไม่เกินคอลัมน์ — กัน DataError ตอน insert"""
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_len]


def _timestamp(value: Any) -> datetime | None:
    """ISO-8601 จาก AINU → datetime แบบมี timezone (naive ถือเป็น UTC)"""
    text = _text(value, 64)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _image_keys_present(payload: Any) -> set[str]:
    """ไล่หาว่ามี key ภาพอยู่ชั้นไหนบ้าง — ใช้ประกอบ warning เท่านั้น"""
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in IMAGE_KEYS and value:
                found.add(key)
            found |= _image_keys_present(value)
    elif isinstance(payload, list):
        for item in payload:
            found |= _image_keys_present(item)
    return found


#: แทนค่าภาพด้วย marker แทนการลบ key ทิ้ง — จะได้รู้ย้อนหลังว่า AINU เคยส่งภาพอะไรมาบ้าง
REDACTED_MARKER = "<stripped>"


def strip_images(payload: Any) -> Any:
    """คืน copy ของ payload ที่แทนค่าใน IMAGE_KEYS ด้วย marker (ไล่ลงทุกชั้น)

    ตัดก่อน insert เสมอ — ภาพใบหน้าประชาชนเป็นข้อมูลชีวมิติตาม PDPA ม.26
    ระบบนี้ไม่เคยขอความยินยอมเพื่อเก็บภาพ ขอแค่ผลผ่าน/ไม่ผ่าน

    ตัดตาม **ชื่อ key** เท่านั้น ไม่ตัดตามความยาวสตริง — `signature` (684 ตัวอักษร)
    `keyId` และ `metadata` จึงรอดครบ ซึ่งเป็นเหตุผลทั้งหมดที่เก็บ payload ไว้ตั้งแต่แรก

    ทำที่ backend เพราะเป็นด่านที่ frontend ข้ามไม่ได้ — ถ้าไปตัดฝั่ง client
    คนที่ยิง API ตรงยังส่งภาพเข้ามาได้อยู่ดี
    """
    if isinstance(payload, dict):
        return {
            key: (REDACTED_MARKER if key in IMAGE_KEYS and value else strip_images(value))
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [strip_images(item) for item in payload]
    return payload


def payload_size(payload: Any) -> int:
    """ขนาด payload เป็น bytes — คืน 0 เมื่อ serialize ไม่ได้ (ต้องไม่โยน)"""
    try:
        return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def warn_if_payload_large(payload: Any, *, reference_id: str) -> int:
    """เตือนเมื่อ payload ใหญ่ผิดปกติ — สัญญาณว่า AINU เริ่มส่งภาพใบหน้ามาแล้ว

    **ต้องเรียกกับ payload ก่อน strip_images()** ไม่งั้นจะวัดขนาดหลังตัดภาพแล้ว
    ซึ่งจะไม่มีวันเกินเกณฑ์ และเราจะไม่มีวันรู้ว่า AINU เปลี่ยนพฤติกรรม

    strip_images() กันภาพไม่ให้เข้า DB อยู่แล้ว ตัวนี้จึงไม่ใช่ด่านกัน แต่เป็น**สัญญาณเตือน**
    ว่าถึงเวลาทบทวนตาม PDPA มาตรา 26 และตรวจว่ารายชื่อ IMAGE_KEYS ยังครบไหม
    """
    size = payload_size(payload)
    if size <= PAYLOAD_WARN_BYTES:
        return size
    found = sorted(_image_keys_present(payload))
    logger.warning(
        "liveness payload ใหญ่ผิดปกติ: %d bytes (เกณฑ์ %d) reference_id=%s image_keys=%s "
        "— ตรวจว่า AINU เริ่มส่งภาพใบหน้ามาหรือไม่ (PDPA ม.26)",
        size,
        PAYLOAD_WARN_BYTES,
        reference_id,
        found or "ไม่พบ",
    )
    return size


def _normalize_status(raw_status: Any) -> str:
    """map transactionStatus ของ AINU → status ของเรา

    ค่าที่รู้จักเก็บตามเดิม (รวม `pending_DOPA` ยาว 12 ตัวอักษร พอดีคอลัมน์ 16)
    ค่าที่ไม่รู้จักถือเป็น failed แล้ว log ไว้ — ค่าดิบยังอยู่ใน raw_payload อ่านย้อนหลังได้
    """
    text = _text(raw_status, _STATUS_MAX_LEN)
    if text in _VENDOR_STATUSES:
        return text
    if text is not None:
        logger.warning(
            "transactionStatus ที่ไม่รู้จักจาก AINU: %r — บันทึกเป็น %s (ค่าดิบอยู่ใน raw_payload)",
            text,
            STATUS_FAILED,
        )
    return STATUS_FAILED


def parse_result(payload: Any) -> ParsedLiveness:
    """แตก payload จาก onEkycResult() — ไม่โยน exception ไม่ว่าจะได้อะไรมา"""
    data = _as_dict(payload)
    if not data:
        # ก้อนว่าง / None / ไม่ใช่ dict — ถือว่าล้มเหลว แต่ต้องไม่พัง
        return ParsedLiveness(status=STATUS_FAILED)

    liveness = _as_dict(_pick(data, "liveness"))

    return ParsedLiveness(
        status=_normalize_status(_pick(data, "transactionStatus")),
        transaction_id=_text(_pick(data, "transactionId"), 128),
        liveness_reason=_text(liveness.get("reason"), 64),
        fail_reason=_text(_pick(data, "failReason"), 64),
        description=_text(_pick(data, "description"), 512),
        # sdkVersion อยู่ได้ทั้งระดับบนสุดและใน liveness block (เอกสาร AINU ข้อ 1.1 กับ 1.4)
        sdk_version=_text(_pick(data, "sdkVersion") or liveness.get("sdkVersion"), 64),
        device=_text(_pick(data, "deviceInfo"), 255),
        completed_at=_timestamp(_pick(data, "completedAt")),
    )
