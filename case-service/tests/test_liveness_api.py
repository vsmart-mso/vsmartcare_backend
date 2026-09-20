"""API tests — usage + security สำหรับ `/v1/liveness/*` (TestClient + dependency_overrides).

รัน: `python -m unittest tests.test_liveness_api -v`

นอกขอบเขต security รอบนี้: การปลอมผล `completed` จาก DevTools — ระบบยังรับได้โดยออกแบบ
จนกว่าจะมี verify signature (แผน backend ข้อ 8)

================================================================
Checklist การใช้งานจริง (มือ / staging) — ไม่ใส่ใน CI
ต้องรันบน stack จริง: BFF + case-service + frontend HTTPS

1. Login citizen → Step 5 → เปิด session → สแกนผ่าน → submit แนบ
   `liveness_reference_id` → DB แถว `completed` + `applicant_id` ไม่ว่าง
2. ปิดเฟรมกลางคันหลัง `onReady` → แถว `skipped`/`USER_SKIPPED` มี `transaction_id`
3. สแกนไม่ผ่าน → `/result` เป็น `failed` แล้วยังยื่นคำร้องได้หลังผ่านรอบใหม่
   (หรือตาม UI soft gate ปัจจุบัน)
4. 503 เมื่อยังไม่ตั้ง AINU → frontend ข้ามด่าน → submit ได้ `NO_ATTEMPT`
5. ยื่นผ่าน BFF แล้วตรวจว่าไม่เกิดแถว `completed` ค้าง + `NO_ATTEMPT` คู่กัน
   (regression บั๊ก BFF ตัด `liveness_reference_id`)
================================================================
"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models.liveness_attempt import (
    CLIENT_SKIP_REASONS,
    SKIP_NO_ATTEMPT,
    SKIP_REPLAYED,
    SKIP_USER_SKIPPED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SKIPPED,
)
from app.services.liveness_link import link_liveness_to_applicant
from tests.liveness_test_support import (
    AINU_TEST_ACCOUNT_SECRET,
    PERSON_A_ID,
    PERSON_B_ID,
    FakeAsyncSession,
    citizen_a,
    clear_overrides,
    get_liveness_app,
    install_overrides,
    json_keys,
    make_attempt,
    patch_ainu_settings,
    patch_thaid_jwt_secret,
)
from tests.test_liveness_payload import PAYLOAD_COMPLETED

_ONREADY_TXN = "txn-from-onready"
_PAYLOAD_TXN = "txn-from-payload-must-not-win"


def _completed_payload_with_other_txn() -> dict:
    payload = dict(PAYLOAD_COMPLETED)
    payload["transactionId"] = _PAYLOAD_TXN
    return payload


def _assert_no_raw_leak(test: unittest.TestCase, response) -> None:
    body = response.json()
    keys = json_keys(body)
    test.assertNotIn("raw_payload", keys)
    test.assertNotIn("signature", keys)
    blob = PAYLOAD_COMPLETED["liveness"]["signature"]
    test.assertNotIn(blob, response.text)


class LivenessApiUsageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = FakeAsyncSession()
        self.claims = citizen_a()
        install_overrides(db=self.db, claims=self.claims)
        self._ainu = patch_ainu_settings()
        self._ainu.__enter__()
        self.client = TestClient(get_liveness_app())

    def tearDown(self) -> None:
        self._ainu.__exit__(None, None, None)
        clear_overrides()

    def _open_session(self):
        response = self.client.post("/v1/liveness/session")
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_session_returns_201_with_account_secret(self) -> None:
        response = self.client.post("/v1/liveness/session")
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["status"], STATUS_PENDING)
        self.assertTrue(body["reference_id"])
        config = body["config"]
        secret = config.get("accountSecret") or config.get("account_secret")
        self.assertEqual(secret, AINU_TEST_ACCOUNT_SECRET)
        ref = config.get("referenceId") or config.get("reference_id")
        self.assertEqual(ref, body["reference_id"])
        self.assertEqual(len(self.db.attempts), 1)
        self.assertEqual(self.db.attempts[0].status, STATUS_PENDING)
        _assert_no_raw_leak(self, response)

    def test_happy_path_session_transaction_result_keeps_onready_transaction_id(self) -> None:
        ref = self._open_session()["reference_id"]

        txn = self.client.post(
            f"/v1/liveness/{ref}/transaction",
            json={"transaction_id": _ONREADY_TXN},
        )
        self.assertEqual(txn.status_code, 200, txn.text)
        self.assertEqual(txn.json()["transaction_id"], _ONREADY_TXN)

        result = self.client.post(
            f"/v1/liveness/{ref}/result",
            json={"payload": _completed_payload_with_other_txn()},
        )
        self.assertEqual(result.status_code, 200, result.text)
        body = result.json()
        self.assertEqual(body["status"], STATUS_COMPLETED)
        self.assertEqual(body["liveness_reason"], "PASS")
        self.assertEqual(body["transaction_id"], _ONREADY_TXN)
        self.assertNotEqual(body["transaction_id"], _PAYLOAD_TXN)
        _assert_no_raw_leak(self, result)

        row = self.db.attempts[0]
        self.assertEqual(row.transaction_id, _ONREADY_TXN)
        self.assertEqual(row.raw_payload["transactionId"], _PAYLOAD_TXN)
        self.assertEqual(row.sdk_version, "1.4.2")

        again = self.client.post(
            f"/v1/liveness/{ref}/result",
            json={"payload": PAYLOAD_COMPLETED},
        )
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["detail"], "attempt_already_finalized")

    def test_skip_user_skipped_on_pending(self) -> None:
        ref = self._open_session()["reference_id"]
        response = self.client.post(
            f"/v1/liveness/{ref}/skip",
            json={"skip_reason": SKIP_USER_SKIPPED},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], STATUS_SKIPPED)
        self.assertEqual(body["skip_reason"], SKIP_USER_SKIPPED)
        _assert_no_raw_leak(self, response)

    def test_all_client_skip_reasons_are_accepted(self) -> None:
        for reason in sorted(CLIENT_SKIP_REASONS):
            with self.subTest(skip_reason=reason):
                self.db.attempts.clear()
                ref = self._open_session()["reference_id"]
                response = self.client.post(
                    f"/v1/liveness/{ref}/skip",
                    json={"skip_reason": reason},
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["skip_reason"], reason)
                self.assertEqual(response.json()["status"], STATUS_SKIPPED)

    def test_malformed_payload_returns_200_failed_not_500(self) -> None:
        ref = self._open_session()["reference_id"]
        response = self.client.post(
            f"/v1/liveness/{ref}/result",
            json={"payload": {"not": "an-ainu-result", "liveness": "should-be-dict"}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], STATUS_FAILED)
        self.assertEqual(self.db.attempts[0].status, STATUS_FAILED)


class LivenessApiSecurityTests(unittest.IsolatedAsyncioTestCase):
    """S1–S7 ตามแผนเทสต์ — ไม่ครอบการปลอม completed จาก DevTools"""

    def setUp(self) -> None:
        self._ainu = None

    def tearDown(self) -> None:
        if self._ainu is not None:
            self._ainu.__exit__(None, None, None)
            self._ainu = None
        clear_overrides()

    def _client_as(self, claims, db: FakeAsyncSession, *, ainu: bool = True) -> TestClient:
        install_overrides(db=db, claims=claims)
        self._ainu = patch_ainu_settings() if ainu else patch_ainu_settings(
            account_id="",
            account_secret="",
            flow_id="",
        )
        self._ainu.__enter__()
        return TestClient(get_liveness_app())

    def test_s1_missing_or_invalid_bearer_is_401_on_every_endpoint(self) -> None:
        db = FakeAsyncSession()
        install_overrides(db=db, claims=None)
        self._ainu = patch_ainu_settings()
        self._ainu.__enter__()
        with patch_thaid_jwt_secret():
            client = TestClient(get_liveness_app())
            paths = (
                ("/v1/liveness/session", {}),
                ("/v1/liveness/any-ref/transaction", {"transaction_id": "x"}),
                ("/v1/liveness/any-ref/result", {"payload": {}}),
                ("/v1/liveness/any-ref/skip", {"skip_reason": SKIP_USER_SKIPPED}),
            )
            for path, body in paths:
                with self.subTest(path=path, auth="missing"):
                    response = client.post(path, json=body)
                    self.assertEqual(response.status_code, 401, response.text)
                    self.assertEqual(response.json()["detail"], "missing_bearer_token")
                with self.subTest(path=path, auth="invalid"):
                    response = client.post(
                        path,
                        json=body,
                        headers={"Authorization": "Bearer not-a-valid-jwt"},
                    )
                    self.assertEqual(response.status_code, 401, response.text)
                    self.assertEqual(response.json()["detail"], "invalid_token")

    def test_s2_cross_person_reference_is_404_not_403(self) -> None:
        db = FakeAsyncSession()
        db.attempts.append(
            make_attempt(reference_id="ref-of-b", persons_id=PERSON_B_ID),
        )
        client = self._client_as(citizen_a(), db)
        for path, body in (
            (f"/v1/liveness/ref-of-b/transaction", {"transaction_id": "x"}),
            (f"/v1/liveness/ref-of-b/result", {"payload": PAYLOAD_COMPLETED}),
            (f"/v1/liveness/ref-of-b/skip", {"skip_reason": SKIP_USER_SKIPPED}),
        ):
            with self.subTest(path=path):
                response = client.post(path, json=body)
                self.assertEqual(response.status_code, 404, response.text)
                self.assertNotEqual(response.status_code, 403)
                self.assertEqual(response.json()["detail"], "liveness_attempt_not_found")

        missing = client.post(
            "/v1/liveness/no-such-ref/skip",
            json={"skip_reason": SKIP_USER_SKIPPED},
        )
        self.assertEqual(missing.status_code, 404)

    def test_s3_reserved_skip_reasons_from_client_are_422(self) -> None:
        db = FakeAsyncSession()
        db.attempts.append(make_attempt(reference_id="ref-pending"))
        client = self._client_as(citizen_a(), db)
        for reason in (SKIP_NO_ATTEMPT, SKIP_REPLAYED):
            with self.subTest(skip_reason=reason):
                db.attempts[0].status = STATUS_PENDING
                response = client.post(
                    "/v1/liveness/ref-pending/skip",
                    json={"skip_reason": reason},
                )
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["detail"], "unknown_skip_reason")
                self.assertEqual(db.attempts[0].status, STATUS_PENDING)

    def test_s4_responses_do_not_include_raw_payload(self) -> None:
        db = FakeAsyncSession()
        client = self._client_as(citizen_a(), db)
        session = client.post("/v1/liveness/session")
        self.assertEqual(session.status_code, 201, session.text)
        _assert_no_raw_leak(self, session)
        ref = session.json()["reference_id"]

        result = client.post(
            f"/v1/liveness/{ref}/result",
            json={"payload": PAYLOAD_COMPLETED},
        )
        self.assertEqual(result.status_code, 200, result.text)
        _assert_no_raw_leak(self, result)
        self.assertIsNotNone(db.attempts[0].raw_payload)

        db.attempts.clear()
        skip_ref = client.post("/v1/liveness/session").json()["reference_id"]
        skipped = client.post(
            f"/v1/liveness/{skip_ref}/skip",
            json={"skip_reason": SKIP_USER_SKIPPED},
        )
        self.assertEqual(skipped.status_code, 200, skipped.text)
        _assert_no_raw_leak(self, skipped)

    def test_s5_session_without_ainu_config_is_503_and_does_not_insert(self) -> None:
        db = FakeAsyncSession()
        client = self._client_as(citizen_a(), db, ainu=False)
        response = client.post("/v1/liveness/session")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"], "liveness_not_configured")
        self.assertEqual(len(db.attempts), 0)

    async def test_s6_linking_someone_elses_reference_does_not_bind_their_row(self) -> None:
        foreign = make_attempt(
            reference_id="ref-b",
            persons_id=PERSON_B_ID,
            status=STATUS_COMPLETED,
        )
        db = FakeAsyncSession()
        db.attempts.append(foreign)

        await link_liveness_to_applicant(
            db,
            applicant_id=88,
            persons_id=PERSON_A_ID,
            reference_id="ref-b",
        )
        self.assertIsNone(foreign.applicant_id)
        extras = db.added_except(foreign)
        self.assertEqual(len(extras), 1)
        self.assertEqual(extras[0].skip_reason, SKIP_NO_ATTEMPT)
        self.assertEqual(extras[0].applicant_id, 88)
        self.assertEqual(extras[0].persons_id, PERSON_A_ID)

    async def test_s7_integrity_error_during_link_does_not_abort(self) -> None:
        db = FakeAsyncSession(
            flush_error=IntegrityError("INSERT", {}, Exception("duplicate key")),
        )
        with self.assertLogs("case-service.liveness", level="ERROR"):
            await link_liveness_to_applicant(
                db,
                applicant_id=99,
                persons_id=PERSON_A_ID,
                reference_id=None,
            )
        self.assertEqual(db.nested_calls, 1)


if __name__ == "__main__":
    unittest.main()
