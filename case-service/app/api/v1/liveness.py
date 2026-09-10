"""Router `/v1/liveness` — ด่านยืนยันตัวตนด้วยใบหน้า ก่อนยื่นคำร้อง (AINU eKYC Web SDK).

ลำดับการเรียกจาก frontend
    1. POST /session                     → ได้ reference_id + config สำหรับ AinuEkyc.setup()
    2. POST /{reference_id}/transaction  → เมื่อ onReady() ให้ transactionId มา
    3. POST /{reference_id}/result       → เมื่อ onEkycResult() ส่งผลกลับ
       หรือ POST /{reference_id}/skip    → เมื่อ "เรา" สรุปเองว่าระบบใช้ไม่ได้

⚠️ **ยังไม่ใช่ security control** — ผลเดินทางผ่านเบราว์เซอร์ผู้ใช้ แก้ด้วย DevTools ได้
รอบนี้เก็บสถิติอย่างเดียว ไม่บล็อกการยื่นคำร้องไม่ว่ากรณีใด
จะเชื่อถือได้ต่อเมื่อ verify `signature` ในผลลัพธ์ฝั่งเซิร์ฟเวอร์ได้ (ยังรอคำตอบจาก AINU)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.citizen_security import CitizenClaims, require_citizen
from ...core.database import get_session
from ...models.liveness_attempt import (
    CLIENT_SKIP_REASONS,
    SKIP_NOT_CONFIGURED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    LivenessAttempt,
)
from ...schemas.liveness import (
    LivenessAttemptRead,
    LivenessResultRequest,
    LivenessSdkConfig,
    LivenessSessionResponse,
    LivenessSkipRequest,
    LivenessTransactionRequest,
)
from ...services.liveness_payload import parse_result, strip_images, warn_if_payload_large
from ...settings import settings

logger = logging.getLogger("case-service.liveness")

router = APIRouter(prefix="/v1/liveness", tags=["liveness"])


def _missing_ainu_config() -> list[str]:
    """ชื่อ env ที่ยังไม่ได้ตั้ง — ว่าง = ตั้งครบแล้ว"""
    return [
        name
        for name, value in (
            ("AINU_ACCOUNT_ID", settings.ainu_account_id),
            ("AINU_ACCOUNT_SECRET", settings.ainu_account_secret),
            ("AINU_FLOW_ID", settings.ainu_flow_id),
        )
        if not (value or "").strip()
    ]


async def _record_not_configured(
    session: AsyncSession,
    *,
    persons_id: int,
    reference_id: str,
    missing: list[str],
) -> None:
    """บันทึกแถว skipped/NOT_CONFIGURED ไว้ก่อนตอบ 503

    ถ้าไม่บันทึก คำร้องที่ยื่นตามมาจะได้แถว NO_ATTEMPT ซึ่งแปลว่า "ไม่มีการสแกน"
    แยกไม่ออกจากคนที่จงใจข้าม ทั้งที่สาเหตุจริงคือ **เราเองตั้งค่าไม่ครบ**

    ต้อง commit เองก่อน raise เพราะ get_session() จะ rollback เมื่อเจอ exception
    (HTTPException ก็นับ) แถวที่เพิ่ง add ไว้จะหายไปพร้อมกัน
    """
    logger.error("AINU config ไม่ครบ: %s", ", ".join(missing))
    session.add(
        LivenessAttempt(
            persons_id=persons_id,
            reference_id=reference_id,
            status=STATUS_SKIPPED,
            skip_reason=SKIP_NOT_CONFIGURED,
            completed_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()


async def _get_owned_attempt(
    session: AsyncSession,
    reference_id: str,
    claims: CitizenClaims,
) -> LivenessAttempt:
    """คืนแถวเฉพาะที่เป็นของ person ใน token — ของคนอื่นตอบ 404 เหมือนไม่มี

    แนวเดียวกับ get_owned_applicant() ใน core/citizen_security.py: ไม่แยก 403/404
    เพื่อไม่ให้เดาได้ว่า reference_id ไหนมีอยู่จริง
    """
    row = await session.scalar(
        select(LivenessAttempt).where(LivenessAttempt.reference_id == reference_id)
    )
    if row is None or row.persons_id != claims.person_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="liveness_attempt_not_found",
        )
    return row


def _assert_not_finalized(row: LivenessAttempt) -> None:
    """แถวที่จบแล้วห้ามเขียนทับ — ไม่งั้นผลที่ผูกกับคำร้องไปแล้วถูกแก้ย้อนหลังได้"""
    if row.status != STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="attempt_already_finalized",
        )


@router.post(
    "/session",
    response_model=LivenessSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="เปิด session ใหม่ + คืน config ให้ AinuEkyc.setup()",
)
async def create_session(
    claims: Annotated[CitizenClaims, Depends(require_citizen)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LivenessSessionResponse:
    """สร้าง reference_id ใหม่ทุกครั้งที่เริ่มสแกน

    ปุ่ม "เริ่มใหม่" ต้องเรียกตัวนี้ซ้ำ ไม่ใช่เรียก setup() ด้วย reference เดิม
    ไม่งั้นการสแกนหลายครั้งจะถูกยุบเป็นแถวเดียวและ reconcile กับ AINU ทีหลังไม่ได้
    """
    reference_id = str(uuid.uuid4())

    missing = _missing_ainu_config()
    if missing:
        await _record_not_configured(
            session,
            persons_id=claims.person_id,
            reference_id=reference_id,
            missing=missing,
        )
        # ส่ง reference_id กลับไปด้วย เพื่อให้ frontend แนบตอนยื่นคำร้องได้
        # คำร้องใบนั้นจะผูกกับแถว NOT_CONFIGURED แทนที่จะได้ NO_ATTEMPT ที่ตีความผิด
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "liveness_not_configured", "reference_id": reference_id},
        )

    session.add(
        LivenessAttempt(
            persons_id=claims.person_id,
            reference_id=reference_id,
            status=STATUS_PENDING,
        )
    )
    await session.flush()

    return LivenessSessionResponse(
        reference_id=reference_id,
        status=STATUS_PENDING,
        config=LivenessSdkConfig(
            account_id=settings.ainu_account_id,
            account_secret=settings.ainu_account_secret,
            flow_id=settings.ainu_flow_id,
            language=settings.ainu_language,
            reference_id=reference_id,
        ),
    )


@router.post(
    "/{reference_id}/transaction",
    response_model=LivenessAttemptRead,
    summary="บันทึก transaction_id จาก onReady()",
)
async def set_transaction(
    reference_id: str,
    body: LivenessTransactionRequest,
    claims: Annotated[CitizenClaims, Depends(require_citizen)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LivenessAttemptRead:
    """เก็บทันทีที่ได้มา ไม่รอผลจบ

    ผู้ใช้ที่เลิกกลางคันจะค้างเป็น pending และ transaction_id คือสิ่งเดียวที่ใช้ถาม AINU
    ได้ว่าเกิดอะไรขึ้นกับเขา
    """
    row = await _get_owned_attempt(session, reference_id, claims)
    _assert_not_finalized(row)
    row.transaction_id = body.transaction_id
    await session.flush()
    return LivenessAttemptRead.model_validate(row)


@router.post(
    "/{reference_id}/result",
    response_model=LivenessAttemptRead,
    summary="บันทึกผลจาก onEkycResult()",
)
async def set_result(
    reference_id: str,
    body: LivenessResultRequest,
    claims: Annotated[CitizenClaims, Depends(require_citizen)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LivenessAttemptRead:
    row = await _get_owned_attempt(session, reference_id, claims)
    _assert_not_finalized(row)

    # วัดขนาดจากก้อนเดิมก่อนตัดภาพ — ถ้าวัดหลังตัดจะไม่มีวันเกินเกณฑ์
    warn_if_payload_large(body.payload, reference_id=reference_id)
    parsed = parse_result(body.payload)

    row.status = parsed.status
    # มีค่าเฉพาะเคสที่ AINU บอก failed แต่จริง ๆ คือเปิดระบบไม่ได้ (INIT_FAILURE_REASONS)
    row.skip_reason = parsed.skip_reason
    row.liveness_reason = parsed.liveness_reason
    row.fail_reason = parsed.fail_reason
    row.description = parsed.description
    row.sdk_version = parsed.sdk_version
    row.device = parsed.device
    # transaction_id จาก onReady() มาก่อนและเชื่อถือได้กว่า — ทับเฉพาะเมื่อยังว่าง
    row.transaction_id = row.transaction_id or parsed.transaction_id
    row.completed_at = parsed.completed_at or datetime.now(timezone.utc)
    # เก็บทั้งก้อน **ยกเว้นภาพ** — ภาพใบหน้าเป็นข้อมูลชีวมิติ (PDPA ม.26) ที่ระบบนี้
    # ไม่เคยขอความยินยอมเพื่อเก็บ ส่วน signature/keyId/metadata ที่ใช้ verify ย้อนหลังรอดครบ
    # ตัดที่นี่ไม่ใช่ที่ frontend เพราะเป็นด่านที่ client ข้ามไม่ได้
    row.raw_payload = strip_images(body.payload)

    await session.flush()
    return LivenessAttemptRead.model_validate(row)


@router.post(
    "/{reference_id}/skip",
    response_model=LivenessAttemptRead,
    summary="บันทึกว่าข้ามด่านนี้เพราะระบบใช้ไม่ได้",
)
async def set_skipped(
    reference_id: str,
    body: LivenessSkipRequest,
    claims: Annotated[CitizenClaims, Depends(require_citizen)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LivenessAttemptRead:
    """แยก endpoint จาก /result โดยตั้งใจ

    /result คือ "AINU ตอบกลับมา" ส่วน /skip คือ "เราเองสรุปว่าใช้ไม่ได้"
    เส้นแบ่งเดียวกับที่แยก fail_reason (AINU พูด) ออกจาก skip_reason (เราพูด)
    ถ้ารวมเป็น endpoint เดียวจะแยกไม่ออกว่าใครเป็นคนสรุป
    """
    row = await _get_owned_attempt(session, reference_id, claims)
    _assert_not_finalized(row)

    if body.skip_reason not in CLIENT_SKIP_REASONS:
        # NO_ATTEMPT / REPLAYED เป็นรหัสที่เซิร์ฟเวอร์เขียนเอง frontend ส่งมาไม่ได้
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="unknown_skip_reason",
        )

    row.status = STATUS_SKIPPED
    row.skip_reason = body.skip_reason
    row.completed_at = datetime.now(timezone.utc)
    # raw_payload คงเป็น null — ไม่เคยคุยกับ AINU สำเร็จจึงไม่มีอะไรให้เก็บ

    await session.flush()
    return LivenessAttemptRead.model_validate(row)
