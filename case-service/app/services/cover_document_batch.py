"""CRUD service for cover_document_batch."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.applicant import Applicant
from ..models.article import Article
from ..models.cover_document_batch import CoverDocumentBatch
from ..services.article_approval import get_article_by_applicant_id, upsert_article

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


async def list_cover_document_batches(
    session: AsyncSession,
    *,
    province_id: int | None = None,
    pending: bool = False,
) -> list[CoverDocumentBatch]:
    stmt = (
        select(CoverDocumentBatch)
        .options(selectinload(CoverDocumentBatch.articles))
        .order_by(CoverDocumentBatch.created_at.desc(), CoverDocumentBatch.id.desc())
    )
    if province_id is not None:
        stmt = stmt.where(CoverDocumentBatch.province_id == province_id)
    batches = (await session.scalars(stmt)).all()
    if not pending:
        return list(batches)
    return [batch for batch in batches if batch.articles]


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
    }
