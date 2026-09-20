"""Helpers for liveness unit/API tests — mock citizen claims, fake session, AINU settings.

ไม่ต่อ Postgres จริง: FakeAsyncSession เก็บแถวในหน่วยความจำและตอบ scalar() จาก WHERE reference_id
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

os.environ.setdefault("SERVICE_NAME", "case-service-test")
os.environ.setdefault("PORT", "8000")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@127.0.0.1:5432/test",
)
os.environ.setdefault("THAID_JWT_SECRET", "test-thaid-jwt-secret")

from app.core.citizen_security import CitizenClaims, require_citizen
from app.core.database import get_session
from app.models.liveness_attempt import STATUS_PENDING, LivenessAttempt

PERSON_A_ID = 101
PERSON_B_ID = 202
PERSON_A_CID = "1100700000001"
PERSON_B_CID = "1100700000002"

AINU_TEST_ACCOUNT_ID = "test-account-id"
AINU_TEST_ACCOUNT_SECRET = "test-account-secret"
AINU_TEST_FLOW_ID = "test-flow-id"


def citizen_a() -> CitizenClaims:
    return CitizenClaims(person_id=PERSON_A_ID, pid=PERSON_A_CID, sub=PERSON_A_CID)


def citizen_b() -> CitizenClaims:
    return CitizenClaims(person_id=PERSON_B_ID, pid=PERSON_B_CID, sub=PERSON_B_CID)


def make_attempt(
    *,
    persons_id: int = PERSON_A_ID,
    reference_id: str = "ref-pending",
    status: str = STATUS_PENDING,
    applicant_id: int | None = None,
    transaction_id: str | None = None,
    skip_reason: str | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> LivenessAttempt:
    """สร้างแถว ORM ในหน่วยความจำ — ไม่ต้องมี Postgres / server_default"""
    return LivenessAttempt(
        persons_id=persons_id,
        reference_id=reference_id,
        status=status,
        applicant_id=applicant_id,
        transaction_id=transaction_id,
        skip_reason=skip_reason,
        raw_payload=raw_payload,
        created_at=datetime.now(timezone.utc),
    )


class _FakeNestedTransaction:
    """async context manager แทน session.begin_nested() (SAVEPOINT)"""

    async def __aenter__(self) -> _FakeNestedTransaction:
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> bool:
        return False


class FakeAsyncSession:
    """AsyncSession ปลอมพอสำหรับ liveness router + link_liveness_to_applicant"""

    def __init__(self, *, flush_error: BaseException | None = None) -> None:
        self.attempts: list[LivenessAttempt] = []
        self.flush_error = flush_error
        self.flush_calls = 0
        self.nested_calls = 0
        self.begin_nested_error: BaseException | None = None

    def add(self, obj: object) -> None:
        if isinstance(obj, LivenessAttempt):
            self.attempts.append(obj)

    def begin_nested(self) -> _FakeNestedTransaction:
        if self.begin_nested_error is not None:
            raise self.begin_nested_error
        self.nested_calls += 1
        return _FakeNestedTransaction()

    async def flush(self) -> None:
        self.flush_calls += 1
        if self.flush_error is not None:
            raise self.flush_error
        now = datetime.now(timezone.utc)
        for row in self.attempts:
            if getattr(row, "created_at", None) is None:
                row.created_at = now

    async def scalar(self, statement: Any) -> LivenessAttempt | None:
        ref = _reference_id_from_statement(statement)
        if ref is None:
            return None
        for row in self.attempts:
            if row.reference_id == ref:
                return row
        return None

    def added_except(self, original: LivenessAttempt) -> list[LivenessAttempt]:
        return [row for row in self.attempts if row is not original]


def _reference_id_from_statement(statement: Any) -> str | None:
    compiled = statement.compile()
    for key, value in compiled.params.items():
        if "reference_id" in str(key):
            return value
    values = list(compiled.params.values())
    if len(values) == 1:
        return values[0]
    return None


@contextmanager
def patch_ainu_settings(
    *,
    account_id: str = AINU_TEST_ACCOUNT_ID,
    account_secret: str = AINU_TEST_ACCOUNT_SECRET,
    flow_id: str = AINU_TEST_FLOW_ID,
    language: str = "TH",
) -> Iterator[None]:
    from app.settings import settings

    with patch.multiple(
        settings,
        ainu_account_id=account_id,
        ainu_account_secret=account_secret,
        ainu_flow_id=flow_id,
        ainu_language=language,
    ):
        yield


@contextmanager
def patch_thaid_jwt_secret(secret: str = "test-thaid-jwt-secret") -> Iterator[None]:
    from app.settings import settings

    with patch.object(settings, "thaid_jwt_secret", secret):
        yield


_liveness_app = None


def get_liveness_app():
    """FastAPI app เฉพาะ router liveness — เลี่ยง import ทุก router ของ case-service"""
    global _liveness_app
    if _liveness_app is None:
        from fastapi import FastAPI

        from app.api.v1.liveness import router

        app = FastAPI(title="liveness-test")
        app.include_router(router)
        _liveness_app = app
    return _liveness_app


def install_overrides(
    *,
    db: FakeAsyncSession,
    claims: CitizenClaims | None,
) -> None:
    """dependency_overrides สำหรับ get_session และ (ถ้ามี) require_citizen"""
    app = get_liveness_app()

    async def _override_session() -> AsyncIterator[FakeAsyncSession]:
        yield db

    app.dependency_overrides[get_session] = _override_session
    if claims is not None:
        captured = claims

        async def _override_citizen() -> CitizenClaims:
            return captured

        app.dependency_overrides[require_citizen] = _override_citizen
    else:
        app.dependency_overrides.pop(require_citizen, None)


def clear_overrides() -> None:
    get_liveness_app().dependency_overrides.clear()


def json_keys(payload: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        found.update(payload.keys())
        for value in payload.values():
            found |= json_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            found |= json_keys(item)
    return found
