"""Unit tests — ผูก liveness attempt เข้ากับคำร้อง (แผนข้อ 5 / 5 เส้นทาง + SAVEPOINT).

link_liveness_to_applicant() ต้องไม่ทำให้การสร้างคำร้องล้มเหลว:
ครอบด้วย begin_nested() แล้วกลืนทุก exception
"""

from __future__ import annotations

import unittest

from sqlalchemy.exc import IntegrityError

from app.models.liveness_attempt import (
    SKIP_NO_ATTEMPT,
    SKIP_REPLAYED,
    STATUS_COMPLETED,
    STATUS_SKIPPED,
)
from app.services.liveness_link import link_liveness_to_applicant
from tests.liveness_test_support import (
    PERSON_A_ID,
    PERSON_B_ID,
    FakeAsyncSession,
    make_attempt,
)


class LinkLivenessToApplicantTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_reference_id_inserts_skipped_no_attempt(self) -> None:
        db = FakeAsyncSession()
        await link_liveness_to_applicant(
            db,
            applicant_id=50,
            persons_id=PERSON_A_ID,
            reference_id=None,
        )
        self.assertEqual(len(db.attempts), 1)
        row = db.attempts[0]
        self.assertEqual(row.status, STATUS_SKIPPED)
        self.assertEqual(row.skip_reason, SKIP_NO_ATTEMPT)
        self.assertEqual(row.applicant_id, 50)
        self.assertEqual(row.persons_id, PERSON_A_ID)
        self.assertTrue(row.reference_id)
        self.assertEqual(db.nested_calls, 1)
        self.assertGreaterEqual(db.flush_calls, 1)

    async def test_empty_reference_id_is_treated_as_missing(self) -> None:
        db = FakeAsyncSession()
        await link_liveness_to_applicant(
            db,
            applicant_id=51,
            persons_id=PERSON_A_ID,
            reference_id="",
        )
        self.assertEqual(db.attempts[0].skip_reason, SKIP_NO_ATTEMPT)

    async def test_valid_unlinked_reference_sets_applicant_id_on_existing_row(self) -> None:
        existing = make_attempt(reference_id="ref-ok", persons_id=PERSON_A_ID)
        db = FakeAsyncSession()
        db.attempts.append(existing)

        await link_liveness_to_applicant(
            db,
            applicant_id=77,
            persons_id=PERSON_A_ID,
            reference_id="ref-ok",
        )

        self.assertIs(db.attempts[0], existing)
        self.assertEqual(existing.applicant_id, 77)
        self.assertEqual(len(db.attempts), 1)

    async def test_already_used_reference_inserts_replayed_without_touching_original(self) -> None:
        existing = make_attempt(
            reference_id="ref-used",
            persons_id=PERSON_A_ID,
            applicant_id=10,
            status=STATUS_COMPLETED,
        )
        db = FakeAsyncSession()
        db.attempts.append(existing)

        await link_liveness_to_applicant(
            db,
            applicant_id=20,
            persons_id=PERSON_A_ID,
            reference_id="ref-used",
        )

        self.assertEqual(existing.applicant_id, 10)
        extras = db.added_except(existing)
        self.assertEqual(len(extras), 1)
        self.assertEqual(extras[0].skip_reason, SKIP_REPLAYED)
        self.assertEqual(extras[0].status, STATUS_SKIPPED)
        self.assertEqual(extras[0].applicant_id, 20)
        self.assertEqual(extras[0].persons_id, PERSON_A_ID)
        self.assertNotEqual(extras[0].reference_id, "ref-used")

    async def test_missing_row_inserts_no_attempt(self) -> None:
        db = FakeAsyncSession()
        await link_liveness_to_applicant(
            db,
            applicant_id=30,
            persons_id=PERSON_A_ID,
            reference_id="does-not-exist",
        )
        self.assertEqual(len(db.attempts), 1)
        self.assertEqual(db.attempts[0].skip_reason, SKIP_NO_ATTEMPT)
        self.assertEqual(db.attempts[0].applicant_id, 30)

    async def test_other_persons_id_inserts_no_attempt_and_does_not_touch_their_row(self) -> None:
        foreign = make_attempt(
            reference_id="ref-foreign",
            persons_id=PERSON_B_ID,
            status=STATUS_COMPLETED,
        )
        db = FakeAsyncSession()
        db.attempts.append(foreign)

        await link_liveness_to_applicant(
            db,
            applicant_id=40,
            persons_id=PERSON_A_ID,
            reference_id="ref-foreign",
        )

        self.assertIsNone(foreign.applicant_id)
        extras = db.added_except(foreign)
        self.assertEqual(len(extras), 1)
        self.assertEqual(extras[0].skip_reason, SKIP_NO_ATTEMPT)
        self.assertEqual(extras[0].persons_id, PERSON_A_ID)
        self.assertEqual(extras[0].applicant_id, 40)

    async def test_flush_integrity_error_is_swallowed_so_case_is_not_aborted(self) -> None:
        db = FakeAsyncSession(
            flush_error=IntegrityError("INSERT", {}, Exception("duplicate key")),
        )
        with self.assertLogs("case-service.liveness", level="ERROR"):
            await link_liveness_to_applicant(
                db,
                applicant_id=60,
                persons_id=PERSON_A_ID,
                reference_id=None,
            )
        self.assertEqual(db.nested_calls, 1)

    async def test_begin_nested_error_is_swallowed(self) -> None:
        db = FakeAsyncSession()
        db.begin_nested_error = RuntimeError("cannot open savepoint")
        with self.assertLogs("case-service.liveness", level="ERROR"):
            await link_liveness_to_applicant(
                db,
                applicant_id=61,
                persons_id=PERSON_A_ID,
                reference_id=None,
            )
        self.assertEqual(len(db.attempts), 0)


if __name__ == "__main__":
    unittest.main()
