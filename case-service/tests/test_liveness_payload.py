"""Unit tests — แตกฟิลด์จาก payload ของ AINU eKYC.

ข้อกำหนดที่สำคัญที่สุดของงานนี้คือ **การแตกฟิลด์ต้องไม่ทำให้การสร้างคำร้องล้มเหลว**
เทสต์ส่วนใหญ่ในไฟล์นี้จึงยืนยันว่า parse_result() ไม่โยน exception กับ input ที่เพี้ยน
"""

from __future__ import annotations

import logging
import unittest
from datetime import datetime, timezone

from app.models.liveness_attempt import (
    SKIP_PROVIDER_UNAVAILABLE,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_SKIPPED,
)
from app.schemas.liveness import LivenessAttemptRead, LivenessSessionResponse
from app.services.liveness_payload import (
    INIT_FAILURE_REASONS,
    PAYLOAD_WARN_BYTES,
    REDACTED_MARKER,
    parse_result,
    payload_size,
    strip_images,
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
        self.assertEqual(parsed.transaction_id, "aa11bb22-cc33-dd44-ee55-ff6677889900")
        self.assertEqual(parsed.fail_reason, "EKYC_ERROR_008")
        self.assertEqual(parsed.liveness_reason, "FACE_NOT_FOUND")
        self.assertEqual(parsed.sdk_version, "1.4.2")
        self.assertEqual(parsed.description, "ตรวจไม่พบใบหน้าเกินจำนวนที่กำหนด")

    def test_sdk_version_from_top_level(self) -> None:
        parsed = parse_result(
            {"transactionStatus": "completed", "sdkVersion": "2.0.0"}
        )
        self.assertEqual(parsed.sdk_version, "2.0.0")

    def test_sdk_version_from_data_block(self) -> None:
        parsed = parse_result(
            {"data": {"transactionStatus": "completed", "sdkVersion": "2.1.0"}}
        )
        self.assertEqual(parsed.sdk_version, "2.1.0")

    def test_attempt_read_schema_excludes_raw_payload(self) -> None:
        self.assertNotIn("raw_payload", LivenessAttemptRead.model_fields)
        self.assertNotIn("signature", LivenessAttemptRead.model_fields)
        self.assertNotIn("raw_payload", LivenessSessionResponse.model_fields)

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


class InitFailureTests(unittest.TestCase):
    """AINU ส่ง "เปิดระบบไม่ได้" มาเป็น failed เหมือนสแกนไม่ผ่าน ต้องแยกออกจากกัน"""

    def test_init_error_becomes_skipped_not_failed(self) -> None:
        """เคสจริง: credential ผิด → handshake 401 → SDK คืน INIT_ERROR ผ่าน onEkycResult"""
        payload = {
            "transactionStatus": "failed",
            "failReason": "INIT_ERROR",
            "description": "[SDK INIT ERROR] Request failed with status code 401",
        }
        with self.assertLogs("case-service.liveness", level=logging.WARNING):
            parsed = parse_result(payload)
        self.assertEqual(parsed.status, STATUS_SKIPPED)
        self.assertEqual(parsed.skip_reason, SKIP_PROVIDER_UNAVAILABLE)
        # รหัสตัวจริงจาก AINU ต้องไม่หาย — ใช้สืบย้อนหลังได้
        self.assertEqual(parsed.fail_reason, "INIT_ERROR")

    def test_all_init_failure_reasons_are_skipped(self) -> None:
        for reason in sorted(INIT_FAILURE_REASONS):
            with self.subTest(reason=reason):
                with self.assertLogs("case-service.liveness", level=logging.WARNING):
                    parsed = parse_result({"transactionStatus": "failed", "failReason": reason})
                self.assertEqual(parsed.status, STATUS_SKIPPED)
                self.assertEqual(parsed.skip_reason, SKIP_PROVIDER_UNAVAILABLE)

    def test_real_scan_failures_stay_failed(self) -> None:
        """สแกนแล้วไม่ผ่านจริง ต้องคง failed ไว้ ไม่งั้นสถิติอัตราผ่านจะเพี้ยนอีกทาง"""
        for reason in ("EKYC_ERROR_007", "EKYC_ERROR_008", "EKYC_ERROR_009", "SESSION_TIMEOUT"):
            with self.subTest(reason=reason):
                parsed = parse_result({"transactionStatus": "failed", "failReason": reason})
                self.assertEqual(parsed.status, STATUS_FAILED)
                self.assertIsNone(parsed.skip_reason)

    def test_completed_never_becomes_skipped(self) -> None:
        parsed = parse_result({"transactionStatus": "completed", "failReason": "INIT_ERROR"})
        self.assertEqual(parsed.status, STATUS_COMPLETED)
        self.assertIsNone(parsed.skip_reason)


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


class StripImagesTests(unittest.TestCase):
    """ภาพใบหน้าเป็นข้อมูลชีวมิติ (PDPA ม.26) ต้องไม่เข้า DB — แต่ signature ต้องรอด"""

    def test_signature_survives(self) -> None:
        """เหตุผลทั้งหมดที่เก็บ payload ไว้คือ verify ย้อนหลัง — ห้ามตัด signature ทิ้ง

        ฟังก์ชัน redact ฝั่ง frontend ตัดสตริงที่ยาวเกิน 300 ตัวอักษรทุกตัว
        ซึ่งจะทำลาย signature (684) ตัวนี้จึงตัดตาม "ชื่อ key" อย่างเดียว
        """
        payload = {"liveness": {"signature": "A" * 684, "keyId": "kid-1", "reason": "PASS"}}
        out = strip_images(payload)
        self.assertEqual(out["liveness"]["signature"], "A" * 684)
        self.assertEqual(out["liveness"]["keyId"], "kid-1")

    def test_all_image_keys_are_stripped_at_any_depth(self) -> None:
        payload = {
            "images": {"livenessImage": "B" * 5000, "thaiIDPortrait": "C" * 5000},
            "nested": [{"fullFrontThaiCard": "D" * 5000}],
            "fullFrontThaiCardSupport": "E" * 5000,
        }
        out = strip_images(payload)
        self.assertEqual(out["images"]["livenessImage"], REDACTED_MARKER)
        self.assertEqual(out["images"]["thaiIDPortrait"], REDACTED_MARKER)
        self.assertEqual(out["nested"][0]["fullFrontThaiCard"], REDACTED_MARKER)
        self.assertEqual(out["fullFrontThaiCardSupport"], REDACTED_MARKER)

    def test_empty_image_value_is_left_alone(self) -> None:
        """ทุกวันนี้ AINU ส่ง {} ว่างมา — ต้องเก็บไว้ตามจริง ไม่แปลงเป็น marker

        ไม่งั้นจะแยกไม่ออกว่า "AINU ไม่ส่งภาพ" กับ "ส่งมาแล้วเราตัด"
        """
        out = strip_images({"images": {"livenessImage": {}}})
        self.assertEqual(out["images"]["livenessImage"], {})

    def test_does_not_mutate_input(self) -> None:
        payload = {"images": {"livenessImage": "B" * 100}}
        strip_images(payload)
        self.assertEqual(payload["images"]["livenessImage"], "B" * 100)

    def test_non_dict_inputs_pass_through(self) -> None:
        for value in (None, "", 0, [], "ข้อความ"):
            with self.subTest(value=value):
                self.assertEqual(strip_images(value), value)

    def test_real_payload_shape_keeps_everything_except_images(self) -> None:
        out = strip_images(PAYLOAD_COMPLETED)
        self.assertEqual(out["liveness"]["signature"], "A" * 684)
        self.assertEqual(out["transactionStatus"], "completed")
        self.assertEqual(out["summary"], PAYLOAD_COMPLETED["summary"])


if __name__ == "__main__":
    unittest.main()
