"""Query MSO forward logs for staff table view."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.type_send import CHANNEL_TO_TYPE_SEND_ID, TYPE_SEND_ID_TO_CHANNEL, MsoForwardChannel
from ..models.address import Address
from ..models.applicant import Applicant
from ..models.geo import District, Province, SubDistrict, SubDistrictPostcode
from ..models.lookup import PrefixType, TypeMoneyCategory
from ..models.mso_send import SendData
from ..models.person import Person
from .user_agent_parse import client_display_fields
from ..schemas.case_for_staff import MsoForwardLogItem, MsoForwardLogListResponse


def _target_group_label(acronym: str | None, name: str | None) -> str | None:
    acronym = (acronym or "").strip()
    name = (name or "").strip()
    if acronym and name:
        return f"{acronym} — {name}"
    return acronym or name or None


def _primary_address_subquery():
    return (
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


def _log_query_columns(primary_address_sq):
    location_subdistrict_postcode_id = func.coalesce(
        primary_address_sq.c.sub_district_postcode_id,
        Person.sub_district_postcode_id,
    )
    fallback_province_id = District.province_id
    fallback_province_name = Province.name
    fallback_type_money_name = TypeMoneyCategory.name
    fallback_type_money_acronym = TypeMoneyCategory.name_acronym
    fallback_person_name = func.trim(
        func.concat(
            func.coalesce(PrefixType.name, ""),
            " ",
            func.coalesce(Person.first_name, ""),
            " ",
            func.coalesce(Person.last_name, ""),
        )
    )
    effective_province_id = func.coalesce(SendData.province_id, fallback_province_id)
    effective_province_name = func.coalesce(SendData.province_name, fallback_province_name)
    effective_type_money_name = func.coalesce(SendData.type_money_name, fallback_type_money_name)
    effective_type_money_acronym = func.coalesce(
        SendData.type_money_acronym,
        fallback_type_money_acronym,
    )
    effective_person_name = func.coalesce(SendData.affected_person_name, fallback_person_name)
    effective_person_cid = func.coalesce(SendData.affected_person_cid, Person.cid)

    return {
        "effective_province_id": effective_province_id,
        "effective_province_name": effective_province_name,
        "effective_type_money_name": effective_type_money_name,
        "effective_type_money_acronym": effective_type_money_acronym,
        "effective_person_name": effective_person_name,
        "effective_person_cid": effective_person_cid,
        "location_subdistrict_postcode_id": location_subdistrict_postcode_id,
    }


def _base_from_clause(primary_address_sq, cols):
    return (
        select(
            SendData,
            Applicant.case_number.label("case_number"),
            cols["effective_province_id"].label("effective_province_id"),
            cols["effective_province_name"].label("effective_province_name"),
            cols["effective_type_money_name"].label("effective_type_money_name"),
            cols["effective_type_money_acronym"].label("effective_type_money_acronym"),
            cols["effective_person_name"].label("effective_person_name"),
            cols["effective_person_cid"].label("effective_person_cid"),
        )
        .select_from(SendData)
        .join(Applicant, Applicant.id == SendData.applicant_id)
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(PrefixType, PrefixType.id == Person.prefix_id)
        .outerjoin(TypeMoneyCategory, TypeMoneyCategory.id == Applicant.type_money_category_id)
        .outerjoin(
            primary_address_sq,
            and_(
                primary_address_sq.c.applicant_id == Applicant.id,
                primary_address_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            SubDistrictPostcode,
            SubDistrictPostcode.id == cols["location_subdistrict_postcode_id"],
        )
        .outerjoin(SubDistrict, SubDistrict.id == SubDistrictPostcode.sub_district_id)
        .outerjoin(District, District.id == SubDistrict.district_id)
        .outerjoin(Province, Province.id == District.province_id)
    )


def _apply_audit_ilike(stmt, **filters: str | None):
    columns = {
        "ip_address": SendData.ip_address,
        "user_agent": SendData.user_agent,
        "device": SendData.device,
        "browser": SendData.browser,
        "browser_version": SendData.browser_version,
        "os": SendData.os,
        "os_version": SendData.os_version,
        "request_url": SendData.request_url,
    }
    for key, column in columns.items():
        value = filters.get(key)
        if value:
            stmt = stmt.where(column.ilike(f"%{value}%"))
    return stmt


def _apply_filters(
    stmt,
    *,
    province_ids: list[int] | None,
    cols,
    case_number: str | None,
    cid: str | None,
    send_channel: MsoForwardChannel | None,
    type_money_id: int | None,
    date_from: date | None,
    date_to: date | None,
    response_code: str | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    device: str | None = None,
    browser: str | None = None,
    browser_version: str | None = None,
    os: str | None = None,
    os_version: str | None = None,
    request_url: str | None = None,
):
    if province_ids:
        stmt = stmt.where(cols["effective_province_id"].in_(province_ids))

    if case_number:
        stmt = stmt.where(Applicant.case_number.ilike(f"%{case_number}%"))
    if cid:
        stmt = stmt.where(cols["effective_person_cid"] == cid)
    if send_channel is not None:
        stmt = stmt.where(SendData.type_send_id == CHANNEL_TO_TYPE_SEND_ID[send_channel])
    if type_money_id is not None:
        stmt = stmt.where(
            func.coalesce(SendData.type_money_category_id, Applicant.type_money_category_id)
            == type_money_id
        )
    if date_from is not None:
        start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        stmt = stmt.where(SendData.created_at >= start)
    if date_to is not None:
        end = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        stmt = stmt.where(SendData.created_at <= end)
    if response_code:
        stmt = stmt.where(
            or_(
                SendData.response_code == response_code,
                SendData.response_code.ilike(f"%{response_code}%"),
            )
        )
    return _apply_audit_ilike(
        stmt,
        ip_address=ip_address,
        user_agent=user_agent,
        device=device,
        browser=browser,
        browser_version=browser_version,
        os=os,
        os_version=os_version,
        request_url=request_url,
    )


def _row_to_log_item(
    row: SendData,
    *,
    case_number: str | None,
    effective_province_name: str | None,
    effective_type_money_name: str | None,
    effective_type_money_acronym: str | None,
    effective_person_name: str | None,
    effective_person_cid: str | None,
) -> MsoForwardLogItem:
    send_channel = TYPE_SEND_ID_TO_CHANNEL.get(row.type_send_id)
    person_name = (effective_person_name or "").strip() or None
    client = client_display_fields(
        user_agent=row.user_agent,
        request_url=row.request_url,
        device=row.device,
        browser=row.browser,
        browser_version=row.browser_version,
        os=row.os,
        os_version=row.os_version,
    )
    return MsoForwardLogItem(
        id=row.id,
        case_number=case_number,
        type_money_name=effective_type_money_name,
        type_money_acronym=effective_type_money_acronym,
        target_group_label=_target_group_label(
            effective_type_money_acronym,
            effective_type_money_name,
        ),
        timestamp=row.created_at,
        response_code=row.response_code,
        response_text=row.response_text,
        sender_sdshv=row.send_by_sdshv,
        sender_phone=None,
        affected_person_name=person_name,
        affected_person_cid=effective_person_cid,
        province_name=effective_province_name,
        ip_address=row.ip_address,
        user_agent=client["user_agent"],
        device=client["device"],
        browser=client["browser"],
        browser_version=client["browser_version"],
        os=client["os"],
        os_version=client["os_version"],
        url=client["url"],
        send_channel=send_channel,
        applicant_id=row.applicant_id,
    )


async def get_mso_forward_json_log(
    session: AsyncSession,
    send_data_id: int,
) -> tuple[SendData, int | None] | None:
    """Return (send_data, effective_province_id) or None when the row is missing."""
    row = await session.get(SendData, send_data_id)
    if row is None:
        return None
    if row.province_id is not None:
        return row, int(row.province_id)

    primary_address_sq = _primary_address_subquery()
    cols = _log_query_columns(primary_address_sq)
    stmt = (
        _base_from_clause(primary_address_sq, cols)
        .where(SendData.id == send_data_id)
        .limit(1)
    )
    result = await session.execute(stmt)
    joined = result.one_or_none()
    if joined is None:
        return row, None
    return row, joined[2]


async def list_mso_forward_logs(
    session: AsyncSession,
    *,
    province_ids: list[int] | None = None,
    case_number: str | None = None,
    cid: str | None = None,
    send_channel: MsoForwardChannel | None = None,
    type_money_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    response_code: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    device: str | None = None,
    browser: str | None = None,
    browser_version: str | None = None,
    os: str | None = None,
    os_version: str | None = None,
    request_url: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> MsoForwardLogListResponse:
    scoped_province_ids = list(dict.fromkeys(province_ids or []))
    primary_address_sq = _primary_address_subquery()
    cols = _log_query_columns(primary_address_sq)
    base_stmt = _base_from_clause(primary_address_sq, cols)
    filtered_stmt = _apply_filters(
        base_stmt,
        province_ids=scoped_province_ids,
        cols=cols,
        case_number=case_number,
        cid=cid,
        send_channel=send_channel,
        type_money_id=type_money_id,
        date_from=date_from,
        date_to=date_to,
        response_code=response_code,
        ip_address=ip_address,
        user_agent=user_agent,
        device=device,
        browser=browser,
        browser_version=browser_version,
        os=os,
        os_version=os_version,
        request_url=request_url,
    )

    count_stmt = select(func.count()).select_from(filtered_stmt.subquery())
    total = int(await session.scalar(count_stmt) or 0)

    page_stmt = (
        filtered_stmt.order_by(SendData.created_at.desc(), SendData.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(page_stmt)
    items = [
        _row_to_log_item(
            row,
            case_number=case_number_val,
            effective_province_name=province_name_val,
            effective_type_money_name=type_money_name_val,
            effective_type_money_acronym=type_money_acronym_val,
            effective_person_name=person_name_val,
            effective_person_cid=person_cid_val,
        )
        for (
            row,
            case_number_val,
            _province_id_val,
            province_name_val,
            type_money_name_val,
            type_money_acronym_val,
            person_name_val,
            person_cid_val,
        ) in result.all()
    ]

    return MsoForwardLogListResponse(
        province_ids=scoped_province_ids,
        total=total,
        items=items,
    )
