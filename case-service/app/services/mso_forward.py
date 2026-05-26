"""บันทึกและตรวจสอบการส่งต่อ MSO (send_data + type_send)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.type_send import (
    CHANNEL_TO_TYPE_SEND_ID,
    TYPE_SEND_ID_TO_CHANNEL,
    TYPE_SEND_LOGBOOK,
    TYPE_SEND_MINISTRY,
    MsoForwardChannel,
)
from ..models.applicant import Applicant
from ..models.mso_send import SendData, TypeSend


def resolve_type_send_id(send_channel: MsoForwardChannel) -> int:
    return CHANNEL_TO_TYPE_SEND_ID[send_channel]


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
) -> SendData:
    applicant = await session.get(Applicant, applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    type_send_id = resolve_type_send_id(send_channel)
    type_send = await session.get(TypeSend, type_send_id)
    if type_send is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="type_send_not_found")

    row = SendData(
        applicant_id=applicant_id,
        type_send_id=type_send_id,
        send_by_sdshv=send_by_sdshv,
        json_case=json_case,
        response_code=response_code,
        response_text=response_text,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row, attribute_names=["type_send"])
    return row


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
