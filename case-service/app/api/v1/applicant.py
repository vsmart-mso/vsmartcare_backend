"""เส้น CRUD applicant แยก — การบันทึกคำร้องหลักใช้ `api.v1.cases` (`POST /v1/cases`).

ไฟล์นี้เก็บ router ว่างไว้เพื่อไม่ให้ import จากโฟลเดอร์เสีย; ถ้าต้องการ list/get applicant ให้เพิ่มที่นี่หรือใช้ GET case
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/v1/applicants", tags=["applicants"])
