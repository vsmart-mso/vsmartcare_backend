"""บันทึกและตรวจสอบการส่งต่อ MSO (send_data + type_send)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.type_send import (
    CHANNEL_TO_TYPE_SEND_ID,
    TYPE_SEND_ID_TO_CHANNEL,
    TYPE_SEND_LOGBOOK,
    TYPE_SEND_MINISTRY,
    MsoForwardChannel,
)
from ..models.address import Address
from ..models.applicant import Applicant
from ..models.geo import District, Province, SubDistrict, SubDistrictPostcode
from ..models.lookup import PrefixType, TypeMoneyCategory
from ..models.mso_send import SendData, TypeSend
from ..models.person import Person
from .user_agent_parse import parse_user_agent, sanitize_client_request_url, sanitize_client_user_agent


def build_mso_ack_response_text(*, send_data_id: int, applicant_id: int) -> str:
    """JSON string stored in send_data.response_text after a successful insert."""
    return json.dumps(
        {"status": "OK", "id": send_data_id, "applicant_id": applicant_id},
        ensure_ascii=False,
    )


def resolve_type_send_id(send_channel: MsoForwardChannel) -> int:
    return CHANNEL_TO_TYPE_SEND_ID[send_channel]


async def _resolve_applicant_province(
    session: AsyncSession,
    applicant_id: int,
) -> tuple[int | None, str | None]:
    primary_address_sq = (
        select(
            Address.applicant_id.label("applicant_id"),
            Address.sub_district_postcode_id.label("sub_district_postcode_id"),
            func.row_number()
            .over(
                partition_by=Address.applicant_id,
                order_by=[Address.id.asc()],
            )
            .label("rn"),
        )
        .subquery()
    )
    location_subdistrict_postcode_id = func.coalesce(
        primary_address_sq.c.sub_district_postcode_id,
        Person.sub_district_postcode_id,
    )
    row = await session.execute(
        select(Province.id, Province.name)
        .select_from(Applicant)
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(
            primary_address_sq,
            and_(
                primary_address_sq.c.applicant_id == Applicant.id,
                primary_address_sq.c.rn == 1,
            ),
        )
        .join(SubDistrictPostcode, SubDistrictPostcode.id == location_subdistrict_postcode_id)
        .join(SubDistrict, SubDistrict.id == SubDistrictPostcode.sub_district_id)
        .join(District, District.id == SubDistrict.district_id)
        .join(Province, Province.id == District.province_id)
        .where(Applicant.id == applicant_id)
        .limit(1)
    )
    data = row.one_or_none()
    if data is None:
        return None, None
    return int(data[0]), data[1]


async def _resolve_affected_person(
    session: AsyncSession,
    applicant_id: int,
) -> tuple[str | None, str | None]:
    row = await session.execute(
        select(PrefixType.name, Person.first_name, Person.last_name, Person.cid)
        .select_from(Applicant)
        .join(Person, Person.id == Applicant.persons_id)
        .join(PrefixType, PrefixType.id == Person.prefix_id)
        .where(Applicant.id == applicant_id)
        .limit(1)
    )
    data = row.one_or_none()
    if data is None:
        return None, None
    prefix_name, first_name, last_name, cid = data
    prefix = (prefix_name or "").strip()
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    parts = [p for p in (prefix, first, last) if p]
    return (" ".join(parts) if parts else None), cid


async def _build_send_data_snapshot(
    session: AsyncSession,
    applicant: Applicant,
) -> dict:
    type_money_name: str | None = None
    type_money_acronym: str | None = None
    type_money_category_id = applicant.type_money_category_id
    if type_money_category_id is not None:
        tmc = await session.get(TypeMoneyCategory, type_money_category_id)
        if tmc is not None:
            type_money_name = tmc.name
            type_money_acronym = tmc.name_acronym

    province_id, province_name = await _resolve_applicant_province(session, applicant.id)
    affected_person_name, affected_person_cid = await _resolve_affected_person(
        session,
        applicant.id,
    )

    return {
        "type_money_category_id": type_money_category_id,
        "type_money_name": type_money_name,
        "type_money_acronym": type_money_acronym,
        "province_id": province_id,
        "province_name": province_name,
        "affected_person_name": affected_person_name,
        "affected_person_cid": affected_person_cid,
    }


async def _create_send_data_row(
    session: AsyncSession,
    *,
    applicant_id: int,
    type_send_id: int,
    send_by_sdshv: str | None,
    json_case: dict | None,
    response_code: str | None,
    response_text: str | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_url: str | None = None,
) -> SendData:
    applicant = await session.get(Applicant, applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    type_send = await session.get(TypeSend, type_send_id)
    if type_send is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="type_send_not_found")

    snapshot = await _build_send_data_snapshot(session, applicant)
    client_ua = sanitize_client_user_agent(user_agent)
    ua_fields = parse_user_agent(client_ua)
    now = datetime.now(timezone.utc)

    row = SendData(
        applicant_id=applicant_id,
        type_send_id=type_send_id,
        send_by_sdshv=send_by_sdshv,
        json_case=json_case,
        response_code=response_code,
        response_text=None,
        created_at=now,
        updated_at=now,
        ip_address=ip_address,
        user_agent=client_ua,
        request_url=sanitize_client_request_url(request_url),
        device=ua_fields["device"],
        browser=ua_fields["browser"],
        browser_version=ua_fields["browser_version"],
        os=ua_fields["os"],
        os_version=ua_fields["os_version"],
        **snapshot,
    )
    session.add(row)
    await session.flush()
    if row.id is not None:
        row.response_text = build_mso_ack_response_text(
            send_data_id=int(row.id),
            applicant_id=int(row.applicant_id),
        )
    await session.refresh(row, attribute_names=["type_send"])
    return row


async def _latest_send_data_for_type(
    session: AsyncSession,
    *,
    applicant_id: int,
    type_send_id: int,
) -> SendData | None:
    return await session.scalar(
        select(SendData)
        .where(
            SendData.applicant_id == applicant_id,
            SendData.type_send_id == type_send_id,
        )
        .order_by(SendData.id.desc())
        .limit(1)
    )


async def record_mso_forward(
    session: AsyncSession,
    *,
    applicant_id: int,
    send_channel: MsoForwardChannel,
    send_by_sdshv: str | None,
    json_case: dict | None,
    response_code: str | None,
    response_text: str | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_url: str | None = None,
) -> SendData:
    type_send_id = resolve_type_send_id(send_channel)
    return await _create_send_data_row(
        session,
        applicant_id=applicant_id,
        type_send_id=type_send_id,
        send_by_sdshv=send_by_sdshv,
        json_case=json_case,
        response_code=response_code,
        response_text=response_text,
        ip_address=ip_address,
        user_agent=user_agent,
        request_url=request_url,
    )


async def record_send_data(
    session: AsyncSession,
    *,
    applicant_id: int,
    type_send_id: int,
    send_by_sdshv: str | None,
    json_case: dict | None,
    response_code: str | None,
    response_text: str | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_url: str | None = None,
) -> SendData:
    return await _create_send_data_row(
        session,
        applicant_id=applicant_id,
        type_send_id=type_send_id,
        send_by_sdshv=send_by_sdshv,
        json_case=json_case,
        response_code=response_code,
        response_text=response_text,
        ip_address=ip_address,
        user_agent=user_agent,
        request_url=request_url,
    )


async def fetch_mso_forward_status(
    session: AsyncSession,
    applicant_id: int,
) -> dict:
    applicant = await session.get(Applicant, applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    ministry_row = await _latest_send_data_for_type(
        session,
        applicant_id=applicant_id,
        type_send_id=TYPE_SEND_MINISTRY,
    )
    logbook_row = await _latest_send_data_for_type(
        session,
        applicant_id=applicant_id,
        type_send_id=TYPE_SEND_LOGBOOK,
    )

    def _channel_block(type_send_id: int, latest: SendData | None) -> dict:
        return {
            "send_channel": TYPE_SEND_ID_TO_CHANNEL[type_send_id],
            "type_send_id": type_send_id,
            "sent": latest is not None,
            "latest_send_data_id": latest.id if latest is not None else None,
        }

    return {
        "applicant_id": applicant_id,
        "ministry": _channel_block(TYPE_SEND_MINISTRY, ministry_row),
        "logbook": _channel_block(TYPE_SEND_LOGBOOK, logbook_row),
    }
