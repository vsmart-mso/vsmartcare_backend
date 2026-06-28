"""OCR routes with integration auth."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_session
from ...core.integration_auth import (
    mint_jwt,
    verify_credentials,
)
from ...models.ocr_result import OcrResult
from ...settings import settings
from .schemas import OcrResponse, OcrResultListResponse, OcrResultRead
from .service import run_ocr_pipeline

logger = logging.getLogger("ocr-service")

router = APIRouter(prefix="/v1/ocr", tags=["ocr"])
_bearer_scheme = HTTPBearer(auto_error=False)


class OcrLoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class OcrTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., ge=1)


class LinkOcrRequest(BaseModel):
    applicant_id: int


async def require_ocr_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> None:
    expected = settings.ocr_api_key
    if not expected:
        return
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="must_send_bearer_token",
        )
    token = credentials.credentials
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_ocr_api_key",
        )


@router.post(
    "/auth/login",
    response_model=OcrTokenResponse,
    summary="Login for OCR integration",
)
async def ocr_auth_login(body: OcrLoginBody) -> OcrTokenResponse:
    if not settings.ocr_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ocr_auth_disabled",
        )
    if not verify_credentials(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )
    token = mint_jwt(subject=body.username.strip())
    return OcrTokenResponse(
        access_token=token,
        expires_in=settings.ocr_jwt_expire_minutes * 60,
    )


@router.post(
    "/bank-book",
    response_model=OcrResponse,
    summary="OCR bank book and persist result",
)
async def ocr_bank_book(
    target_name: Annotated[str, Form(description="Target full name to compare against OCR result")],
    file: Annotated[UploadFile, File(description="Bank book image (JPEG/PNG/WebP)")],
    applicant_id: Annotated[int | None, Form(description="Optional applicant id")] = None,
    _auth: None = Depends(require_ocr_auth),
    session: AsyncSession = Depends(get_session),
) -> OcrResponse:
    logger.info(
        "OCR request: applicant_id=%s target_name=%r file=%s type=%s size=%s",
        applicant_id,
        target_name,
        file.filename,
        file.content_type,
        file.size,
    )

    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"unsupported_file_type:{file.content_type}",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="empty_file",
        )

    max_bytes = settings.max_upload_bytes
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file_too_large:{max_bytes}",
        )

    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = ext_map.get(file.content_type, ".jpg")
    pre_file_uuid = f"{uuid.uuid4().hex}{ext}"

    result = await run_ocr_pipeline(
        image_bytes=image_bytes,
        target_name=target_name.strip(),
        pre_file_uuid=pre_file_uuid,
        mime_type=file.content_type or "image/jpeg",
    )

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
    logger.info("OCR result persisted: id=%s applicant_id=%s", db_row.id, applicant_id)

    return OcrResponse(id=db_row.id, **result)


@router.patch(
    "/results/{ocr_result_id}/link",
    response_model=OcrResultRead,
    summary="Link OCR result to applicant id",
)
async def link_ocr_to_applicant(
    ocr_result_id: int,
    body: LinkOcrRequest,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_ocr_auth),
) -> OcrResultRead:
    stmt = select(OcrResult).where(OcrResult.id == ocr_result_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ocr_result_not_found")

    row.applicant_id = body.applicant_id
    await session.flush()
    logger.info("OCR result %s linked to applicant_id=%s", ocr_result_id, body.applicant_id)

    return OcrResultRead.model_validate(row)


@router.get(
    "/results/{applicant_id}",
    response_model=OcrResultListResponse,
    summary="Get OCR results by applicant id",
)
async def get_ocr_results(
    applicant_id: int,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_ocr_auth),
) -> OcrResultListResponse:
    stmt = (
        select(OcrResult)
        .where(OcrResult.applicant_id == applicant_id)
        .order_by(OcrResult.created_at.desc())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return OcrResultListResponse(
        applicant_id=applicant_id,
        results=[OcrResultRead.model_validate(row) for row in rows],
        count=len(rows),
    )
