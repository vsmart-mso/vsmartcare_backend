"""Master lookup APIs — แยกเส้นตาม resource และชื่อ path parameter ตามความหมาย (ไม่ใช้ id กลาง).

Client เรียก URL ของ master นั้น ๆ โดยตรง ไม่ต้องส่ง query/body เพื่อบอกประเภทข้อมูล
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_session
from ...models.lookup import (
    AddressType,
    AttachmentType,
    BankName,
    CurrentStatus,
    DependencyType,
    HousingType,
    IncomeSourceType,
    MaritalStatusType,
    PrefixType,
    ReceivedWelfareType,
    RequesterRelationType,
    RequestType,
)
from ...schemas.lookup import (
    AddressTypeRead,
    AttachmentTypeRead,
    BankNameRead,
    CurrentStatusRead,
    DependencyTypeRead,
    HousingTypeRead,
    IncomeSourceTypeRead,
    MaritalStatusTypeRead,
    PrefixTypeRead,
    ReceivedWelfareTypeRead,
    RequesterRelationTypeRead,
    RequestTypeRead,
)

router = APIRouter(prefix="/v1/lookups", tags=["lookups"])


async def _list_rows(session: AsyncSession, model: Any, read_cls: Any) -> list[Any]:
    result = await session.execute(select(model).order_by(model.id))
    return [read_cls.model_validate(r) for r in result.scalars().all()]


async def _get_row(
    session: AsyncSession,
    model: Any,
    read_cls: Any,
    row_id: int,
    not_found_detail: str,
) -> Any:
    result = await session.execute(select(model).where(model.id == row_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return read_cls.model_validate(row)


# --- prefix-types ---


@router.get("/prefix-types", response_model=list[PrefixTypeRead])
async def list_prefix_types(session: AsyncSession = Depends(get_session)) -> list[PrefixTypeRead]:
    return await _list_rows(session, PrefixType, PrefixTypeRead)


@router.get("/prefix-types/{prefix_type_id}", response_model=PrefixTypeRead)
async def get_prefix_type(
    prefix_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> PrefixTypeRead:
    return await _get_row(
        session, PrefixType, PrefixTypeRead, prefix_type_id, "prefix_type_not_found"
    )


# --- received-welfare-types ---


@router.get("/received-welfare-types", response_model=list[ReceivedWelfareTypeRead])
async def list_received_welfare_types(
    session: AsyncSession = Depends(get_session),
) -> list[ReceivedWelfareTypeRead]:
    return await _list_rows(session, ReceivedWelfareType, ReceivedWelfareTypeRead)


@router.get(
    "/received-welfare-types/{received_welfare_type_id}",
    response_model=ReceivedWelfareTypeRead,
)
async def get_received_welfare_type(
    received_welfare_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> ReceivedWelfareTypeRead:
    return await _get_row(
        session,
        ReceivedWelfareType,
        ReceivedWelfareTypeRead,
        received_welfare_type_id,
        "received_welfare_type_not_found",
    )


# --- attachment-types ---


@router.get("/attachment-types", response_model=list[AttachmentTypeRead])
async def list_attachment_types(
    session: AsyncSession = Depends(get_session),
) -> list[AttachmentTypeRead]:
    return await _list_rows(session, AttachmentType, AttachmentTypeRead)


@router.get("/attachment-types/{attachment_type_id}", response_model=AttachmentTypeRead)
async def get_attachment_type(
    attachment_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> AttachmentTypeRead:
    return await _get_row(
        session,
        AttachmentType,
        AttachmentTypeRead,
        attachment_type_id,
        "attachment_type_not_found",
    )


# alias ชื่อตาราง attachment_types (underscore) — พฤติกรรมเดียวกับ attachment-types
@router.get("/attachment_types", response_model=list[AttachmentTypeRead])
async def list_attachment_types_table_name(
    session: AsyncSession = Depends(get_session),
) -> list[AttachmentTypeRead]:
    return await _list_rows(session, AttachmentType, AttachmentTypeRead)


@router.get("/attachment_types/{attachment_type_id}", response_model=AttachmentTypeRead)
async def get_attachment_type_table_name(
    attachment_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> AttachmentTypeRead:
    return await _get_row(
        session,
        AttachmentType,
        AttachmentTypeRead,
        attachment_type_id,
        "attachment_type_not_found",
    )


# --- current-status ---


@router.get("/current-status", response_model=list[CurrentStatusRead])
async def list_current_status(session: AsyncSession = Depends(get_session)) -> list[CurrentStatusRead]:
    result = await session.execute(
        select(CurrentStatus).order_by(CurrentStatus.filter_order.asc(), CurrentStatus.id.asc()),
    )
    return [CurrentStatusRead.model_validate(r) for r in result.scalars().all()]


@router.get("/current-status/{current_status_id}", response_model=CurrentStatusRead)
async def get_current_status(
    current_status_id: int,
    session: AsyncSession = Depends(get_session),
) -> CurrentStatusRead:
    return await _get_row(
        session,
        CurrentStatus,
        CurrentStatusRead,
        current_status_id,
        "current_status_not_found",
    )


# --- request-types ---


@router.get("/request-types", response_model=list[RequestTypeRead])
async def list_request_types(session: AsyncSession = Depends(get_session)) -> list[RequestTypeRead]:
    return await _list_rows(session, RequestType, RequestTypeRead)


@router.get("/request-types/{request_type_id}", response_model=RequestTypeRead)
async def get_request_type(
    request_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> RequestTypeRead:
    return await _get_row(
        session, RequestType, RequestTypeRead, request_type_id, "request_type_not_found"
    )


# --- requester-relation-types ---


@router.get("/requester-relation-types", response_model=list[RequesterRelationTypeRead])
async def list_requester_relation_types(
    session: AsyncSession = Depends(get_session),
) -> list[RequesterRelationTypeRead]:
    return await _list_rows(session, RequesterRelationType, RequesterRelationTypeRead)


@router.get(
    "/requester-relation-types/{requester_relation_type_id}",
    response_model=RequesterRelationTypeRead,
)
async def get_requester_relation_type(
    requester_relation_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> RequesterRelationTypeRead:
    return await _get_row(
        session,
        RequesterRelationType,
        RequesterRelationTypeRead,
        requester_relation_type_id,
        "requester_relation_type_not_found",
    )


# --- marital-status-types ---


@router.get("/marital-status-types", response_model=list[MaritalStatusTypeRead])
async def list_marital_status_types(
    session: AsyncSession = Depends(get_session),
) -> list[MaritalStatusTypeRead]:
    return await _list_rows(session, MaritalStatusType, MaritalStatusTypeRead)


@router.get(
    "/marital-status-types/{marital_status_type_id}",
    response_model=MaritalStatusTypeRead,
)
async def get_marital_status_type(
    marital_status_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> MaritalStatusTypeRead:
    return await _get_row(
        session,
        MaritalStatusType,
        MaritalStatusTypeRead,
        marital_status_type_id,
        "marital_status_type_not_found",
    )


# --- housing-types ---


@router.get("/housing-types", response_model=list[HousingTypeRead])
async def list_housing_types(session: AsyncSession = Depends(get_session)) -> list[HousingTypeRead]:
    return await _list_rows(session, HousingType, HousingTypeRead)


@router.get("/housing-types/{housing_type_id}", response_model=HousingTypeRead)
async def get_housing_type(
    housing_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> HousingTypeRead:
    return await _get_row(
        session, HousingType, HousingTypeRead, housing_type_id, "housing_type_not_found"
    )


# --- income-source-types ---


@router.get("/income-source-types", response_model=list[IncomeSourceTypeRead])
async def list_income_source_types(
    session: AsyncSession = Depends(get_session),
) -> list[IncomeSourceTypeRead]:
    return await _list_rows(session, IncomeSourceType, IncomeSourceTypeRead)


@router.get(
    "/income-source-types/{income_source_type_id}",
    response_model=IncomeSourceTypeRead,
)
async def get_income_source_type(
    income_source_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> IncomeSourceTypeRead:
    return await _get_row(
        session,
        IncomeSourceType,
        IncomeSourceTypeRead,
        income_source_type_id,
        "income_source_type_not_found",
    )


# --- dependency-types ---


@router.get("/dependency-types", response_model=list[DependencyTypeRead])
async def list_dependency_types(
    session: AsyncSession = Depends(get_session),
) -> list[DependencyTypeRead]:
    return await _list_rows(session, DependencyType, DependencyTypeRead)


@router.get("/dependency-types/{dependency_type_id}", response_model=DependencyTypeRead)
async def get_dependency_type(
    dependency_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> DependencyTypeRead:
    return await _get_row(
        session,
        DependencyType,
        DependencyTypeRead,
        dependency_type_id,
        "dependency_type_not_found",
    )


# --- bank-names ---


@router.get("/bank-names", response_model=list[BankNameRead])
async def list_bank_names(session: AsyncSession = Depends(get_session)) -> list[BankNameRead]:
    return await _list_rows(session, BankName, BankNameRead)


@router.get("/bank-names/{bank_name_id}", response_model=BankNameRead)
async def get_bank_name(
    bank_name_id: int,
    session: AsyncSession = Depends(get_session),
) -> BankNameRead:
    return await _get_row(
        session, BankName, BankNameRead, bank_name_id, "bank_name_not_found"
    )


# --- address-types ---


@router.get("/address-types", response_model=list[AddressTypeRead])
async def list_address_types(session: AsyncSession = Depends(get_session)) -> list[AddressTypeRead]:
    return await _list_rows(session, AddressType, AddressTypeRead)


@router.get("/address-types/{address_type_id}", response_model=AddressTypeRead)
async def get_address_type(
    address_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> AddressTypeRead:
    return await _get_row(
        session, AddressType, AddressTypeRead, address_type_id, "address_type_not_found"
    )
