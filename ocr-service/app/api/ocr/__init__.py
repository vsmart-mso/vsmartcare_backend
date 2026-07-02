"""OCR Pipeline Router — รับภาพสมุดบัญชีธนาคาร ส่ง Gemini OCR + เทียบชื่อ."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_session
from ...models.ocr_result import OcrResult
from ...settings import settings
from .schemas import OcrResponse, OcrResultListResponse, OcrResultRead
from .service import run_ocr_pipeline

logger = logging.getLogger("ocr-service")

router = APIRouter(prefix="/v1/ocr", tags=["ocr"])

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_ocr_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> None:
    """ตรวจสอบการ login เบื้องต้น — รองรับทั้ง Bearer token และ OCR_API_KEY.

    - ถ้าตั้ง OCR_API_KEY ใน env → ต้องส่งตรงกับค่าใน header Authorization: Bearer <key>
    - ถ้าไม่ตั้ง OCR_API_KEY → อนุญาตทุก request (dev mode)
    """
    expected = settings.ocr_api_key
    if not expected:
        return

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ต้องส่ง header Authorization: Bearer <token>",
        )

    token = credentials.credentials
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token ไม่ถูกต้อง",
        )


@router.post(
    "/bank-book",
    response_model=OcrResponse,
    summary="OCR สมุดบัญชีธนาคาร และบันทึกผลลง DB",
    description=(
        "อัปโหลดรูปสมุดบัญชีธนาคาร แล้วเรียก Gemini Flash เพื่อทำ OCR "
        "พร้อมสกัดข้อมูลบัญชี เทียบชื่อกับ `target_name` และบันทึกผลผูกกับ `applicant_id`"
    ),
)
async def ocr_bank_book(
    target_name: Annotated[str, Form(description="ชื่อ-นามสกุลเป้าหมายสำหรับเทียบบัญชี")],
    file: Annotated[UploadFile, File(description="รูปสมุดบัญชี (JPEG/PNG/WebP)")],
    applicant_id: Annotated[int | None, Form(description="ID ของ applicant (ใบคำร้อง) — ส่งทีหลังได้")] = None,
    _auth: None = Depends(require_ocr_auth),
    session: AsyncSession = Depends(get_session),
) -> OcrResponse:
    logger.info(
        f"OCR request: applicant_id={applicant_id} | "
        f"target_name={target_name!r} | file={file.filename}, type={file.content_type}, size={file.size}"
    )

    # Validate file type
    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"รองรับเฉพาะ {', '.join(allowed_types)} — ได้ {file.content_type}",
        )

    # Read file bytes
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ไฟล์ว่างเปล่า",
        )

    if image_bytes[:4] == b"\xff\xd8\xff" or image_bytes.startswith(b"\x89PNG") or (
        image_bytes[:4] == b"RIFF" and len(image_bytes) > 12 and image_bytes[8:12] == b"WEBP"
    ):
        pass
    else:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported_file_content")

    # Limit file size
    max_bytes = settings.max_upload_bytes
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"ขนาดไฟล์ต้องไม่เกิน {max_bytes // (1024 * 1024)} MB",
        )

    # Generate UUID for pre_file
    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = ext_map.get(file.content_type, ".jpg")
    pre_file_uuid = f"{uuid.uuid4().hex}{ext}"

    if not (settings.gemini_api_key or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="gemini_api_key_not_configured",
        )

    # Run OCR pipeline
    try:
        result = await run_ocr_pipeline(
            image_bytes=image_bytes,
            target_name=target_name.strip(),
            pre_file_uuid=pre_file_uuid,
            mime_type=file.content_type or "image/jpeg",
        )
    except ValueError as exc:
        if "api key" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="gemini_api_key_not_configured",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ocr_pipeline_failed",
        ) from exc
    except Exception as exc:
        detail = "gemini_api_error"
        err_text = str(exc).lower()
        if "leaked" in err_text or "permission_denied" in err_text:
            detail = "gemini_api_key_leaked"
        elif "api key" in err_text:
            detail = "gemini_api_key_invalid"
        err_name = type(exc).__name__
        if err_name == "ClientError" or "genai" in type(exc).__module__:
            logger.error("Gemini API error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=detail,
            ) from exc
        raise

    logger.info(
        f"OCR done: applicant_id={applicant_id} | target={target_name!r} | "
        f"match_status={result['bank_info']['match_status']} | "
        f"fuzzy_score={result['bank_info']['fuzzy_score']}"
    )

    # ── Persist OCR result ลง DB ──────────────────────────────────────────
    bi = result["bank_info"]
    db_row = OcrResult(
        applicant_id=applicant_id,
        target_name_checked=target_name.strip(),
        pre_file=pre_file_uuid,
        markdown=result["markdown"],
        account_number=bi.get("account_number"),
        account_name=bi.get("account_name"),
        bank_name=bi.get("bank_name"),
        deposit_type=bi.get("deposit_type"),
        branch_name=bi.get("branch_name"),
        branch_code=bi.get("branch_code"),
        match_status=bi["match_status"].value if hasattr(bi["match_status"], "value") else bi["match_status"],
        fuzzy_score=bi["fuzzy_score"],
    )
    session.add(db_row)
    await session.flush()
    logger.info(f"OCR result persisted: id={db_row.id}, applicant_id={applicant_id}")

    return OcrResponse(id=db_row.id, **result)


# ── PATCH: ผูกผล OCR กับ applicant_id ทีหลัง (หลังสร้างใบคำร้องแล้ว) ──────────

from pydantic import BaseModel as PydanticBaseModel


class LinkOcrRequest(PydanticBaseModel):
    applicant_id: int


@router.patch(
    "/results/{ocr_result_id}/link",
    response_model=OcrResultRead,
    summary="ผูกผล OCR กับ applicant_id (ใบคำร้อง)",
    description="ใช้หลังสร้างใบคำร้องสำเร็จแล้ว — อัปเดต applicant_id ในผล OCR ที่เคยบันทึกไว้",
)
async def link_ocr_to_applicant(
    ocr_result_id: int,
    body: LinkOcrRequest,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_ocr_auth),
) -> OcrResultRead:
    stmt = select(OcrResult).where(OcrResult.id == ocr_result_id)
    r = await session.execute(stmt)
    row = r.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ocr_result_not_found")

    row.applicant_id = body.applicant_id
    await session.flush()
    logger.info(f"OCR result {ocr_result_id} linked to applicant_id={body.applicant_id}")

    return OcrResultRead.model_validate(row)


# ── GET: ดึงผล OCR ตาม applicant_id ──────────────────────────────────────────

@router.get(
    "/results/{applicant_id}",
    response_model=OcrResultListResponse,
    summary="ดึงผล OCR ทั้งหมดของ applicant (ใบคำร้อง)",
    description="คืนค่าผล OCR ทั้งหมดที่เคยทำกับ applicant_id นี้ เรียงจากล่าสุดขึ้นก่อน",
)
async def get_ocr_results(
    applicant_id: int,
    limit: Annotated[int, Query(ge=1, le=50, description="จำนวนผลลัพธ์สูงสุด")] = 10,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_ocr_auth),
) -> OcrResultListResponse:
    stmt = (
        select(OcrResult)
        .where(OcrResult.applicant_id == applicant_id)
        .order_by(OcrResult.created_at.desc())
        .limit(limit)
    )
    r = await session.execute(stmt)
    rows = list(r.scalars().all())

    return OcrResultListResponse(
        applicant_id=applicant_id,
        results=[OcrResultRead.model_validate(row) for row in rows],
        count=len(rows),
    )
