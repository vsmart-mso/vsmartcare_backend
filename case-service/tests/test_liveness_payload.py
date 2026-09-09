"""Unit tests — แตกฟิลด์จาก payload ของ AINU eKYC.

ข้อกำหนดที่สำคัญที่สุดของงานนี้คือ **การแตกฟิลด์ต้องไม่ทำให้การสร้างคำร้องล้มเหลว**
เทสต์ส่วนใหญ่ในไฟล์นี้จึงยืนยันว่า parse_result() ไม่โยน exception กับ input ที่เพี้ยน
"""

from __future__ import annotations

import logging
import unittest
from datetime import datetime, timezone

from app.models.liveness_attempt import STATUS_COMPLETED, STATUS_FAILED
from app.services.liveness_payload import (
    PAYLOAD_WARN_BYTES,
    parse_result,
    payload_size,
    warn_if_payload_large,
)

# payload สำเร็จ — ประกอบจากสเปก Return Data Fields ของ AINU (eKYC_Full_Spec.md ส่วนที่ 1)
PAYLOAD_COMPLETED = {
    "transactionId": "6f1d0c2e-6d1a-4f7e-9b3a-0c5a1d2e3f40",
    "transactionStatus": "completed",
    "createdAt": "2026-08-28T09:12:03.000Z",
    "completedAt": "2026-08-28T09:12:43.000Z",
    "workflow": ["liveness"],
    "accountId": "dga-pmcare",
    "appId": "https://care.example.go.th",
    "flowId": "DGA-PMCARE-001",
    "referenceId": "8b0f4a5c-1111-2222-3333-444455556666",
    "sdkVersion": "1.4.2",
    "deviceInfo": "Apple iPhone | iOS 26.6 | Mobile Safari 26.6",
    "liveness": {
        "isProcessCompleted": True,
        "livenessResultCode": "OK",
        "reason": "PASS",
        "elapsedMs": 40122,
        "keyId": "kid-2026-08",
        "signature": "A" * 684,
    },
    "summary": {"configuration": {"livenessFailedLimit": 5}},
    "images": {"livenessImage": {}},
}

# payload ล้มเหลว — transactionStatus ซ่อนอยู่ใน data ตามที่เอกสาร AINU ขัดกันเอง
PAYLOAD_FAILED_NESTED = {
    "data": {
        "transactionId": "aa11bb22-cc33-dd44-ee55-ff6677889900",
        "transactionStatus": "failed",
        "failReason": "EKYC_ERROR_008",
        "description": "ตรวจไม่พบใบหน้าเกินจำนวนที่กำหนด",
        "deviceInfo": "Apple Macintosh | macOS 26.5 | Chrome 140.0",
        "liveness": {"reason": "FACE_NOT_FOUND", "sdkVersion": "1.4.2"},
    }
}


class ParseResultTests(unittest.TestCase):
    def test_completed_payload(self) -> None:
        parsed = parse_result(PAYLOAD_COMPLETED)
        self.assertEqual(parsed.status, STATUS_COMPLETED)
        self.assertEqual(parsed.transaction_id, "6f1d0c2e-6d1a-4f7e-9b3a-0c5a1d2e3f40")
        self.assertEqual(parsed.liveness_reason, "PASS")
        self.assertIsNone(parsed.fail_reason)
        self.assertEqual(parsed.sdk_version, "1.4.2")
        self.assertEqual(parsed.device, "Apple iPhone | iOS 26.6 | Mobile Safari 26.6")
        self.assertEqual(
            parsed.completed_at,
            datetime(2026, 8, 28, 9, 12, 43, tzinfo=timezone.utc),
        )

    def test_reads_fields_nested_under_data(self) -> None:
        """เอกสาร AINU ขัดกันเองว่า transactionStatus อยู่ชั้นไหน — ต้องอ่านเผื่อทั้งสอง"""
        parsed = parse_result(PAYLOAD_FAILED_NESTED)
        self.assertEqual(parsed.status, STATUS_FAILED)
        self.assertEqual(parsed.fail_reason, "EKYC_ERROR_008")
        self.assertEqual(parsed.liveness_reason, "FACE_NOT_FOUND")
        self.assertEqual(parsed.sdk_version, "1.4.2")
        self.assertEqual(parsed.description, "ตรวจไม่พบใบหน้าเกินจำนวนที่กำหนด")

    def test_pending_dopa_is_kept_verbatim(self) -> None:
        """flow ของเราไม่มี dopa แต่ AINU ปรับ flow ฝั่งเขาได้เอง — ห้ามแปลงเป็น failed"""
        parsed = parse_result({"transactionStatus": "pending_DOPA"})
        self.assertEqual(parsed.status, "pending_DOPA")

    def test_unknown_status_becomes_failed(self) -> None:
        with self.assertLogs("case-service.liveness", level=logging.WARNING):
            parsed = parse_result({"transactionStatus": "teleported"})
        self.assertEqual(parsed.status, STATUS_FAILED)

    def test_status_too_long_for_column_becomes_failed(self) -> None:
        """คอลัมน์ status เป็น String(16) — ค่าที่ยาวกว่านั้นห้ามหลุดลงไปทำให้ insert พัง"""
        with self.assertLogs("case-service.liveness", level=logging.WARNING):
            parsed = parse_result({"transactionStatus": "x" * 200})
        self.assertEqual(parsed.status, STATUS_FAILED)
        self.assertLessEqual(len(parsed.status), 16)

    def test_long_values_are_truncated_to_column_width(self) -> None:
        parsed = parse_result(
            {
                "transactionStatus": "failed",
                "description": "ก" * 900,
                "deviceInfo": "d" * 900,
                "failReason": "f" * 900,
            }
        )
        self.assertEqual(len(parsed.description), 512)
        self.assertEqual(len(parsed.device), 255)
        self.assertEqual(len(parsed.fail_reason), 64)

    def test_malformed_inputs_never_raise(self) -> None:
        """กรณีที่เอกสารกำหนดไว้ว่า 'ต้องไม่ทำให้การสร้างคำร้องล้มเหลว'"""
        for bad in (
            None,
            {},
            [],
            "",
            "ไม่ใช่ json",
            0,
            {"transactionStatus": None},
            {"transactionStatus": {"เป็น": "dict"}},
            {"liveness": "ควรเป็น dict แต่เป็น str"},
            {"data": "ควรเป็น dict แต่เป็น str"},
            {"completedAt": "ไม่ใช่วันที่"},
            {"completedAt": 12345},
        ):
            with self.subTest(bad=bad):
                parsed = parse_result(bad)
                self.assertIsInstance(parsed.status, str)
                self.assertLessEqual(len(parsed.status), 16)

    def test_empty_payload_is_failed(self) -> None:
        self.assertEqual(parse_result({}).status, STATUS_FAILED)
        self.assertEqual(parse_result(None).status, STATUS_FAILED)

    def test_naive_timestamp_is_treated_as_utc(self) -> None:
        parsed = parse_result(
            {"transactionStatus": "completed", "completedAt": "2026-08-28T09:12:43"}
        )
        self.assertEqual(parsed.completed_at.tzinfo, timezone.utc)


class PayloadSizeWarningTests(unittest.TestCase):
    """เราเลือกเก็บ payload ดิบทั้งก้อน warning ตัวนี้จึงเป็นด่านเดียวที่เฝ้าภาพชีวมิติ"""

    def test_normal_payload_does_not_warn(self) -> None:
        logger = logging.getLogger("case-service.liveness")
        with self.assertNoLogs(logger, level=logging.WARNING):
            size = warn_if_payload_large(PAYLOAD_COMPLETED, reference_id="ref-1")
        self.assertLess(size, PAYLOAD_WARN_BYTES)

    def test_payload_with_face_image_warns_and_names_the_key(self) -> None:
        payload = dict(PAYLOAD_COMPLETED)
        payload["images"] = {"livenessImage": "B" * (PAYLOAD_WARN_BYTES + 1)}
        with self.assertLogs("case-service.liveness", level=logging.WARNING) as captured:
            size = warn_if_payload_large(payload, reference_id="ref-2")
        self.assertGreater(size, PAYLOAD_WARN_BYTES)
        self.assertIn("livenessImage", captured.output[0])
        self.assertIn("ref-2", captured.output[0])

    def test_size_counts_utf8_bytes_not_characters(self) -> None:
        """ข้อความไทยกินพื้นที่ 3 bytes ต่อตัว — ถ้านับเป็นตัวอักษรจะประเมินต่ำไป 3 เท่า"""
        self.assertEqual(payload_size({"a": "ก"}), len('{"a": "ก"}'.encode("utf-8")))

    def test_unserializable_payload_returns_zero(self) -> None:
        self.assertEqual(payload_size({"bad": object()}), 0)


if __name__ == "__main__":
    unittest.main()
