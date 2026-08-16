"""CRUD service for cover_document_batch."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.applicant import Applicant
from ..models.article import Article
from ..models.cover_document_batch import CoverDocumentBatch
from ..models.geo import District, Postcode, Province, SubDistrict, SubDistrictPostcode
from ..models.payment import ApproveCase
from ..models.person import Person
from ..models.address import Address
from ..services.article_approval import get_article_by_applicant_id, upsert_article
from ..services.dwf_scope import SOR_KOR_TYPE_MONEY_ID

_BATCH_HEADER_FIELDS = (
    "service_vsmart_id",
    "phone_service",
    "at",
    "date_at",
    "title",
    "director_vsmart_id",
    "original_story",
    "fact_story",
    "laws",
    "consider",
    "suggestion",
    "type_money_id",
    "province_id",
    "approver_sdhsv",
)


def _header_from_payload(payload: dict) -> dict:
    data = {k: payload[k] for k in _BATCH_HEADER_FIELDS if k in payload}
    if "director_vsmart_id" in data:
        data["director_vsmart_id"] = data["director_vsmart_id"]
    return data


def _article_fields_from_batch(batch: CoverDocumentBatch) -> dict:
    return {
        "service_vsmart_id": batch.service_vsmart_id,
        "approver_sdhsv_id": batch.approver_sdhsv,
        "phone_service": batch.phone_service,
        "at": batch.at,
        "date_at": batch.date_at,
        "title": batch.title,
        "director_vsmart_id": batch.director_vsmart_id,
        "original_story": batch.original_story,
        "fact_story": batch.fact_story,
        "laws": batch.laws,
        "consider": batch.consider,
        "suggestion": batch.suggestion,
    }


async def _sync_member_articles(session: AsyncSession, batch: CoverDocumentBatch) -> None:
    article_fields = _article_fields_from_batch(batch)
    for article in batch.articles:
        for key, value in article_fields.items():
            setattr(article, key, value)
        article.updated_at = datetime.now()


async def create_cover_document_batch(
    session: AsyncSession,
    payload: dict,
) -> CoverDocumentBatch:
    applicant_ids = list(dict.fromkeys(payload.get("applicant_ids") or []))
    if not (1 <= len(applicant_ids) <= 30):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_applicant_ids")

    applicants = (
        await session.scalars(select(Applicant).where(Applicant.id.in_(applicant_ids)))
    ).all()
    if len(applicants) != len(applicant_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    type_money_ids = {a.type_money_category_id for a in applicants if a.type_money_category_id}
    if len(type_money_ids) > 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mixed_type_money")

    batch = CoverDocumentBatch(**_header_from_payload(payload))
    if batch.type_money_id is None and type_money_ids:
        batch.type_money_id = next(iter(type_money_ids))
    session.add(batch)
    await session.flush()

    for applicant_id in applicant_ids:
        article = await get_article_by_applicant_id(session, applicant_id)
        fields = _article_fields_from_batch(batch)
        if article is None:
            article = await upsert_article(session, applicant_id, fields)
        else:
            for key, value in fields.items():
                setattr(article, key, value)
            article.updated_at = datetime.now()
        article.batch_id = batch.id

    await session.flush()
    return batch


async def update_cover_document_batch(
    session: AsyncSession,
    batch_id: int,
    payload: dict,
) -> CoverDocumentBatch:
    batch = await session.scalar(
        select(CoverDocumentBatch)
        .options(selectinload(CoverDocumentBatch.articles))
        .where(CoverDocumentBatch.id == batch_id)
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch_not_found")

    for key, value in _header_from_payload(payload).items():
        setattr(batch, key, value)
    batch.updated_at = datetime.now()
    await _sync_member_articles(session, batch)
    await session.flush()
    return batch


async def get_cover_document_batch(
    session: AsyncSession,
    batch_id: int,
) -> CoverDocumentBatch:
    batch = await session.scalar(
        select(CoverDocumentBatch)
        .options(selectinload(CoverDocumentBatch.articles))
        .where(CoverDocumentBatch.id == batch_id)
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch_not_found")
    return batch


def _applicant_is_approved_exists():
    return (
        select(ApproveCase.id)
        .where(
            ApproveCase.applicant_id == Applicant.id,
            ApproveCase.approve_status.is_(True),
        )
        .exists()
    )


def _build_active_pmj_reject_sq():
    return (
        select(
            ApproveCase.applicant_id.label("applicant_id"),
            func.row_number()
            .over(
                partition_by=ApproveCase.applicant_id,
                order_by=ApproveCase.id.desc(),
            )
            .label("rn"),
        )
        .where(
            ApproveCase.approve_status.is_(False),
            ApproveCase.reject_reason.is_not(None),
            ApproveCase.reject_resolved_at.is_(None),
        )
        .subquery()
    )


async def _approval_status_by_applicant_ids(
    session: AsyncSession,
    applicant_ids: list[int],
) -> dict[int, str]:
    """Return applicant_id → 'approved' | 'rejected' | 'pending'."""
    if not applicant_ids:
        return {}
    is_approved = _applicant_is_approved_exists()
    active_pmj_reject_sq = _build_active_pmj_reject_sq()
    stmt = (
        select(
            Applicant.id.label("applicant_id"),
            is_approved.label("is_approved"),
            case(
                (
                    and_(
                        active_pmj_reject_sq.c.applicant_id.is_not(None),
                        ~is_approved,
                    ),
                    True,
                ),
                else_=False,
            ).label("is_pmj_rejected"),
        )
        .outerjoin(
            active_pmj_reject_sq,
            and_(
                active_pmj_reject_sq.c.applicant_id == Applicant.id,
                active_pmj_reject_sq.c.rn == 1,
            ),
        )
        .where(Applicant.id.in_(applicant_ids))
    )
    rows = (await session.execute(stmt)).mappings().all()
    status_map: dict[int, str] = {}
    for row in rows:
        aid = int(row["applicant_id"])
        if row["is_approved"]:
            status_map[aid] = "approved"
        elif row["is_pmj_rejected"]:
            status_map[aid] = "rejected"
        else:
            status_map[aid] = "pending"
    for aid in applicant_ids:
        status_map.setdefault(aid, "pending")
    return status_map


def _article_document_date_at(article: Article, batch: CoverDocumentBatch) -> date | None:
    """document_key date — ใช้ article.date_at ก่อน แล้ว fallback หัวชุด (ไม่ backfill DB)."""
    if article.date_at is not None:
        return article.date_at
    return batch.date_at


def _document_date_in_range(
    doc_date: date,
    *,
    date_at: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> bool:
    if date_at is not None and doc_date != date_at:
        return False
    if from_date is not None and doc_date < from_date:
        return False
    if to_date is not None and doc_date > to_date:
        return False
    return True


def _bucket_document_rows(rows: list[dict]) -> dict[tuple[date, int | None], dict]:
    """Group applicant rows into document_key buckets (date_at, type_money_id)."""
    groups: dict[tuple[date, int | None], dict] = defaultdict(
        lambda: {
            "ordered_ids": [],
            "seen": set(),
            "batch_id_seen": set(),
            "batch_ids": [],
            "ats": [],
        }
    )
    for row in rows:
        doc_date = row.get("date_at")
        if doc_date is None:
            continue
        key = (doc_date, row.get("type_money_id"))
        bucket = groups[key]
        batch_id = row.get("batch_id")
        if batch_id is not None and batch_id not in bucket["batch_id_seen"]:
            bucket["batch_id_seen"].add(batch_id)
            bucket["batch_ids"].append(batch_id)
        at_label = (row.get("at") or "").strip()
        if at_label and at_label not in bucket["ats"]:
            bucket["ats"].append(at_label)
        aid = row.get("applicant_id")
        if aid is None or aid in bucket["seen"]:
            continue
        bucket["seen"].add(aid)
        bucket["ordered_ids"].append(aid)
    return groups


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


def _article_scope_filter(
    *,
    province_col,
    type_money_col,
    province_id: int | None,
    type_money_id: int | None,
    sor_kor_province_ids: tuple[int, ...] | None,
    sor_kor_type_money_id: int,
):
    if province_id is None:
        return None
    if type_money_id == sor_kor_type_money_id and sor_kor_province_ids:
        return province_col.in_(sor_kor_province_ids)
    if type_money_id is not None:
        return province_col == province_id
    if sor_kor_province_ids:
        return or_(
            and_(
                type_money_col == sor_kor_type_money_id,
                province_col.in_(sor_kor_province_ids),
            ),
            and_(
                or_(
                    type_money_col.is_(None),
                    type_money_col != sor_kor_type_money_id,
                ),
                province_col == province_id,
            ),
        )
    return province_col == province_id


async def _list_document_article_rows(
    session: AsyncSession,
    *,
    province_id: int | None = None,
    type_money_id: int | None = None,
    date_at: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    sor_kor_province_ids: tuple[int, ...] | None = None,
    sor_kor_type_money_id: int = SOR_KOR_TYPE_MONEY_ID,
) -> list[dict]:
    """Read-only: article.date_at เป็น document_key รวมเคสที่ยังไม่ผูก cover_document_batch."""
    primary_address_sq = _primary_address_subquery()
    location_subdistrict_postcode_id = func.coalesce(
        primary_address_sq.c.sub_district_postcode_id,
        Person.sub_district_postcode_id,
    )
    doc_date = func.coalesce(Article.date_at, CoverDocumentBatch.date_at)
    type_money_col = func.coalesce(
        Applicant.type_money_category_id,
        CoverDocumentBatch.type_money_id,
    )
    stmt = (
        select(
            Article.applicant_id.label("applicant_id"),
            doc_date.label("date_at"),
            type_money_col.label("type_money_id"),
            Article.batch_id.label("batch_id"),
            func.coalesce(Article.at, CoverDocumentBatch.at).label("at"),
        )
        .select_from(Article)
        .join(Applicant, Applicant.id == Article.applicant_id)
        .outerjoin(CoverDocumentBatch, CoverDocumentBatch.id == Article.batch_id)
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(
            primary_address_sq,
            and_(
                primary_address_sq.c.applicant_id == Applicant.id,
                primary_address_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            SubDistrictPostcode,
            SubDistrictPostcode.id == location_subdistrict_postcode_id,
        )
        .outerjoin(Postcode, Postcode.id == SubDistrictPostcode.postcode_id)
        .outerjoin(SubDistrict, SubDistrict.id == SubDistrictPostcode.sub_district_id)
        .outerjoin(District, District.id == SubDistrict.district_id)
        .outerjoin(Province, Province.id == District.province_id)
        .where(doc_date.is_not(None))
        .order_by(Article.updated_at.desc(), Article.id.desc())
    )
    if type_money_id is not None:
        stmt = stmt.where(type_money_col == type_money_id)
    if date_at is not None:
        stmt = stmt.where(doc_date == date_at)
    if from_date is not None:
        stmt = stmt.where(doc_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(doc_date <= to_date)
    scope = _article_scope_filter(
        province_col=Province.id,
        type_money_col=type_money_col,
        province_id=province_id,
        type_money_id=type_money_id,
        sor_kor_province_ids=sor_kor_province_ids,
        sor_kor_type_money_id=sor_kor_type_money_id,
    )
    if scope is not None:
        stmt = stmt.where(scope)
    rows = (await session.execute(stmt)).mappings().all()
    return [
        {
            "applicant_id": int(row["applicant_id"]),
            "date_at": row["date_at"],
            "type_money_id": row["type_money_id"],
            "batch_id": row["batch_id"],
            "at": row["at"],
        }
        for row in rows
        if row["applicant_id"] is not None
    ]


def _partition_ids_by_status(
    applicant_ids: list[int],
    status_map: dict[int, str],
) -> tuple[list[int], list[int], list[int]]:
    pending: list[int] = []
    approved: list[int] = []
    rejected: list[int] = []
    seen: set[int] = set()
    for aid in applicant_ids:
        if aid in seen:
            continue
        seen.add(aid)
        st = status_map.get(aid, "pending")
        if st == "approved":
            approved.append(aid)
        elif st == "rejected":
            rejected.append(aid)
        else:
            pending.append(aid)
    return pending, approved, rejected


def _batch_scope_filter(
    *,
    province_id: int | None,
    sor_kor_province_ids: tuple[int, ...] | None,
    sor_kor_type_money_id: int,
):
    if province_id is None:
        return None
    if sor_kor_province_ids:
        return or_(
            and_(
                CoverDocumentBatch.type_money_id == sor_kor_type_money_id,
                CoverDocumentBatch.province_id.in_(sor_kor_province_ids),
            ),
            and_(
                or_(
                    CoverDocumentBatch.type_money_id.is_(None),
                    CoverDocumentBatch.type_money_id != sor_kor_type_money_id,
                ),
                CoverDocumentBatch.province_id == province_id,
            ),
        )
    return CoverDocumentBatch.province_id == province_id


async def list_cover_document_batches(
    session: AsyncSession,
    *,
    province_id: int | None = None,
    pending: bool = False,
    date_at: date | None = None,
    type_money_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    by_document: bool = False,
    sor_kor_province_ids: tuple[int, ...] | None = None,
    sor_kor_type_money_id: int = SOR_KOR_TYPE_MONEY_ID,
) -> list[CoverDocumentBatch] | list[dict]:
    stmt = (
        select(CoverDocumentBatch)
        .options(selectinload(CoverDocumentBatch.articles))
        .order_by(CoverDocumentBatch.created_at.desc(), CoverDocumentBatch.id.desc())
    )
    scope = _batch_scope_filter(
        province_id=province_id,
        sor_kor_province_ids=sor_kor_province_ids,
        sor_kor_type_money_id=sor_kor_type_money_id,
    )
    if scope is not None:
        stmt = stmt.where(scope)
    # by_document=true groups on article.date_at — date filters apply after aggregate
    if not by_document:
        if date_at is not None:
            stmt = stmt.where(CoverDocumentBatch.date_at == date_at)
        if from_date is not None:
            stmt = stmt.where(CoverDocumentBatch.date_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(CoverDocumentBatch.date_at <= to_date)
    if type_money_id is not None:
        stmt = stmt.where(CoverDocumentBatch.type_money_id == type_money_id)

    if by_document:
        return await _aggregate_batches_by_document(
            session,
            pending=pending,
            caller_province_id=province_id,
            date_at=date_at,
            from_date=from_date,
            to_date=to_date,
            type_money_id=type_money_id,
            sor_kor_province_ids=sor_kor_province_ids,
            sor_kor_type_money_id=sor_kor_type_money_id,
        )

    batches = list(await session.scalars(stmt))

    if not pending:
        return batches

    # pending=true: real CARE pending (not merely "has articles")
    all_ids: list[int] = []
    for batch in batches:
        all_ids.extend(article.applicant_id for article in batch.articles)
    status_map = await _approval_status_by_applicant_ids(session, list(dict.fromkeys(all_ids)))
    result: list[CoverDocumentBatch] = []
    for batch in batches:
        ids = [article.applicant_id for article in batch.articles]
        pending_ids, _, _ = _partition_ids_by_status(ids, status_map)
        if pending_ids:
            result.append(batch)
    return result


async def _aggregate_batches_by_document(
    session: AsyncSession,
    *,
    pending: bool,
    caller_province_id: int | None,
    date_at: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    type_money_id: int | None = None,
    sor_kor_province_ids: tuple[int, ...] | None = None,
    sor_kor_type_money_id: int = SOR_KOR_TYPE_MONEY_ID,
) -> list[dict]:
    """Merge into one item per (article.date_at, type_money_id), including unbatched articles."""
    rows = await _list_document_article_rows(
        session,
        province_id=caller_province_id,
        type_money_id=type_money_id,
        date_at=date_at,
        from_date=from_date,
        to_date=to_date,
        sor_kor_province_ids=sor_kor_province_ids,
        sor_kor_type_money_id=sor_kor_type_money_id,
    )
    groups = _bucket_document_rows(rows)

    all_ids: list[int] = []
    for bucket in groups.values():
        all_ids.extend(bucket["ordered_ids"])
    status_map = await _approval_status_by_applicant_ids(session, list(dict.fromkeys(all_ids)))

    items: list[dict] = []
    for (doc_date, tm_id), bucket in sorted(
        groups.items(),
        key=lambda kv: (kv[0][0], kv[0][1] or 0),
        reverse=True,
    ):
        ordered_ids = bucket["ordered_ids"]
        pending_ids, approved_ids, rejected_ids = _partition_ids_by_status(ordered_ids, status_map)
        if pending and not pending_ids:
            continue

        items.append(
            {
                "date_at": doc_date,
                "type_money_id": tm_id,
                "province_id": caller_province_id,
                "at": bucket["ats"][0] if bucket["ats"] else None,
                "pending_count": len(pending_ids),
                "approved_count": len(approved_ids),
                "rejected_count": len(rejected_ids),
                "applicant_ids": pending_ids,
                "pending_applicant_ids": pending_ids,
                "approved_applicant_ids": approved_ids,
                "all_applicant_ids": ordered_ids,
                "batch_ids": bucket["batch_ids"],
                "mode": "document",
            }
        )
    return items


async def list_cover_document_batch_members(
    session: AsyncSession,
    *,
    province_id: int,
    date_at: date,
    type_money_id: int,
    pending_only: bool = True,
    sor_kor_province_ids: tuple[int, ...] | None = None,
    sor_kor_type_money_id: int = SOR_KOR_TYPE_MONEY_ID,
) -> list[dict]:
    """Members of one document set (date_at + type_money_id) in province / สค. scope."""
    rows = await _list_document_article_rows(
        session,
        province_id=province_id,
        type_money_id=type_money_id,
        date_at=date_at,
        sor_kor_province_ids=sor_kor_province_ids,
        sor_kor_type_money_id=sor_kor_type_money_id,
    )
    applicant_ids: list[int] = []
    seen: set[int] = set()
    for row in rows:
        aid = row["applicant_id"]
        if aid in seen:
            continue
        seen.add(aid)
        applicant_ids.append(aid)

    if not applicant_ids:
        return []

    status_map = await _approval_status_by_applicant_ids(session, applicant_ids)
    if pending_only:
        applicant_ids = [aid for aid in applicant_ids if status_map.get(aid) == "pending"]
        if not applicant_ids:
            return []

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

    stmt_members = (
        select(
            Applicant.id.label("applicant_id"),
            Applicant.case_number.label("case_number"),
            Applicant.type_money_category_id.label("type_money_id"),
            Person.first_name.label("firstname"),
            Person.last_name.label("lastname"),
            Person.cid.label("cid"),
            Province.id.label("province_id"),
        )
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(
            primary_address_sq,
            and_(
                primary_address_sq.c.applicant_id == Applicant.id,
                primary_address_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            SubDistrictPostcode,
            SubDistrictPostcode.id == location_subdistrict_postcode_id,
        )
        .outerjoin(Postcode, Postcode.id == SubDistrictPostcode.postcode_id)
        .outerjoin(SubDistrict, SubDistrict.id == SubDistrictPostcode.sub_district_id)
        .outerjoin(District, District.id == SubDistrict.district_id)
        .outerjoin(Province, Province.id == District.province_id)
        .where(Applicant.id.in_(applicant_ids))
    )
    rows_by_id = {
        row["applicant_id"]: row
        for row in (await session.execute(stmt_members)).mappings().all()
    }

    items: list[dict] = []
    for aid in applicant_ids:
        row = rows_by_id.get(aid)
        st = status_map.get(aid, "pending")
        if row is None:
            items.append(
                {
                    "applicant_id": aid,
                    "type_money_id": type_money_id,
                    "exists": False,
                    "is_approved": st == "approved",
                    "is_pmj_rejected": st == "rejected",
                }
            )
            continue
        first = (row["firstname"] or "").strip()
        last = (row["lastname"] or "").strip()
        name = f"{first} {last}".strip() or None
        items.append(
            {
                "applicant_id": aid,
                "type_money_id": row["type_money_id"] if row["type_money_id"] is not None else type_money_id,
                "case_number": row["case_number"],
                "applicant_name": name,
                "is_approved": st == "approved",
                "is_pmj_rejected": st == "rejected",
                "exists": True,
                "province_id": row["province_id"],
                "cid": row["cid"],
            }
        )
    return items


def batch_to_read(batch: CoverDocumentBatch) -> dict:
    return {
        "id": batch.id,
        "service_vsmart_id": batch.service_vsmart_id,
        "phone_service": batch.phone_service,
        "at": batch.at,
        "date_at": batch.date_at,
        "title": batch.title,
        "director_vsmart_id": batch.director_vsmart_id,
        "original_story": batch.original_story,
        "fact_story": batch.fact_story,
        "laws": batch.laws,
        "consider": batch.consider,
        "suggestion": batch.suggestion,
        "type_money_id": batch.type_money_id,
        "province_id": batch.province_id,
        "approver_sdhsv": batch.approver_sdhsv,
        "applicant_ids": [article.applicant_id for article in batch.articles],
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
        "mode": "batch",
    }


def enrich_batch_read_with_counts(
    batch_dict: dict,
    status_map: dict[int, str],
) -> dict:
    ids = list(batch_dict.get("applicant_ids") or [])
    pending_ids, approved_ids, rejected_ids = _partition_ids_by_status(ids, status_map)
    batch_dict["pending_count"] = len(pending_ids)
    batch_dict["approved_count"] = len(approved_ids)
    batch_dict["rejected_count"] = len(rejected_ids)
    batch_dict["pending_applicant_ids"] = pending_ids
    batch_dict["approved_applicant_ids"] = approved_ids
    batch_dict["all_applicant_ids"] = ids
    return batch_dict
