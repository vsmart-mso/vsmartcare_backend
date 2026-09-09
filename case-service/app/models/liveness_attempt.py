"""ตาราง `liveness_attempts` — บันทึกผลด่านยืนยันตัวตนด้วยใบหน้า (AINU eKYC).

แถวเกิดตอนเปิด session (ก่อนสแกน) ไม่ใช่ตอนยื่นคำร้อง จึงเห็นคนที่เลิกกลางคันด้วย
`applicant_id` เติมทีหลังตอนยื่นคำร้องสำเร็จ

⚠️ ยังไม่ใช่ security control — ผลเดินทางผ่านเบราว์เซอร์ผู้ใช้ ปลอมด้วย DevTools ได้
จนกว่าจะ verify `signature` ฝั่งเซิร์ฟเวอร์ได้ (ยังรอคำตอบจาก AINU)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.base import Base

# สถานะของเราเอง — ไม่ใช่ของ AINU (AINU ใช้ transactionStatus)
STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

# skip_reason — รหัสที่ "เรา" เป็นคนตัดสิน แยกจาก fail_reason ที่ AINU เป็นคนบอก
SKIP_SDK_LOAD_ERROR = "SDK_LOAD_ERROR"
SKIP_NOT_SECURE_CONTEXT = "NOT_SECURE_CONTEXT"
SKIP_PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
SKIP_AUTH_ERROR = "AUTH_ERROR"
SKIP_USER_SKIPPED = "USER_SKIPPED"
#: เซิร์ฟเวอร์เขียนเองตอนยื่นคำร้องโดยไม่มี reference_id แนบมา
SKIP_NO_ATTEMPT = "NO_ATTEMPT"
#: เซิร์ฟเวอร์เขียนเองเมื่อเอา reference_id ที่ผูกกับคำร้องอื่นแล้วมาใช้ซ้ำ
SKIP_REPLAYED = "REPLAYED"
#: เซิร์ฟเวอร์เขียนเองเมื่อ AINU credential ฝั่งเราตั้งไม่ครบ — แยกจาก PROVIDER_UNAVAILABLE
#: ที่แปลว่าระบบของ AINU เองมีปัญหา สองอย่างนี้คนละสาเหตุและคนละคนแก้
SKIP_NOT_CONFIGURED = "NOT_CONFIGURED"

#: รหัสที่ frontend ส่งมาได้ — NO_ATTEMPT / REPLAYED / NOT_CONFIGURED ไม่อยู่ในนี้
#: เพราะเซิร์ฟเวอร์เป็นคนเขียนเอง (client ส่งมาจะได้ 422)
CLIENT_SKIP_REASONS = frozenset(
    {
        SKIP_SDK_LOAD_ERROR,
        SKIP_NOT_SECURE_CONTEXT,
        SKIP_PROVIDER_UNAVAILABLE,
        SKIP_AUTH_ERROR,
        SKIP_USER_SKIPPED,
    }
)


class LivenessAttempt(Base):
    __tablename__ = "liveness_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: เจ้าของการสแกน — มาจาก JWT ตอนเปิด session (ยังไม่มี applicant ตอนนั้น)
    persons_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: correlation key ที่ backend สร้าง (uuid4) แล้วส่งให้ AINU ผ่าน start()
    reference_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    #: รหัสธุรกรรมที่ AINU สร้าง — มาจาก onReady() ใช้อ้างอิงเวลาถาม AINU
    transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_PENDING)
    #: liveness.reason จาก AINU — PASS / FAIL / TIMEOUT / FACE_NOT_FOUND / ...
    liveness_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: failReason จาก AINU — EKYC_ERROR_0xx / SESSION_TIMEOUT / CANT_START_EKYC
    fail_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: รหัสของเราเอง เมื่อ status = skipped
    skip_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sdk_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: deviceInfo จาก payload — มีเฉพาะแถวที่ AINU ตอบกลับมา
    #: แถว pending/skipped จึงเป็น null เสมอ สถิติ desktop vs mobile ครอบคลุมแค่ completed/failed
    device: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: payload จาก onEkycResult() เก็บทั้งก้อน **ยกเว้นภาพ base64 ที่ strip_images() ตัดออก**
    #: signature / keyId / metadata รอดครบเพื่อใช้ verify ย้อนหลัง
    #: ⚠️ ห้าม expose ผ่าน API · ห้าม log ทั้งก้อน · มี warning เฝ้าขนาดใน services/liveness_payload.py
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    #: เติมตอนยื่นคำร้องสำเร็จ · SET NULL ตาม pattern ของ ocr_results (แถวเกิดก่อน applicant)
    #: `applicant_id IS NOT NULL` = ถูกใช้ไปแล้ว ใช้กันการเอาสแกนเดียวไปยื่นหลายคำร้อง
    applicant_id: Mapped[int | None] = mapped_column(
        ForeignKey("applicants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    #: completedAt จาก payload
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
