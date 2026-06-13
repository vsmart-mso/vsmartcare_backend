"""รหัส current_status — ใช้ใน workflow ฝั่งเจ้าหน้าที่และอีเมลแจ้งประชาชน."""

from typing import Final

# รอรับเรื่อง
CURRENT_STATUS_PENDING_INTAKE: Final[int] = 1
# รับเรื่องเรียบร้อย
CURRENT_STATUS_RECEIVED: Final[int] = 2
# อยู่ระหว่างการเบิก (หลังอนุมัติพมจ.)
CURRENT_STATUS_WITHDRAWING_APPROVED: Final[int] = 3
# ช่วยเหลือแล้ว (ฝั่งเจ้าหน้าที่) — ประชาชนเห็น "เบิกจ่ายสำเร็จ" เมื่ออัปโหลด 037
CURRENT_STATUS_AID_COMPLETED: Final[int] = 4
# คุณสมบัติไม่ตรงตามหลักเกณฑ์
CURRENT_STATUS_INELIGIBLE: Final[int] = 5
# ดำเนินการแก้ไขข้อมูล
CURRENT_STATUS_EDIT_REQUESTED: Final[int] = 8
# อยู่ระหว่างการเบิก (หลังบันทึกผลจ่าย 037) — ประชาชนเห็น "เบิกจ่ายสำเร็จ"
CURRENT_STATUS_WITHDRAWING = 10

# ส่งต่อข้อมูลเรียบร้อยแล้ว (ฝั่งกระทรวง) — ใช้ใน workflow MSO forward
CURRENT_STATUS_MSO_FORWARDED: Final[int] = 11

# ข้อความสถานะสาธารณะสำหรับอีเมล "เบิกจ่ายสำเร็จ" (id 10 และ ช่วยเหลือแล้ว+037)
PUBLIC_STATUS_PAYMENT_SUCCESS: Final[str] = "เบิกจ่ายสำเร็จ"

# คำขอยังดำเนินการ — เข้าพอร์ทัลได้ แต่ยื่นใหม่ไม่ได้
ACTIVE_CASE_STATUS_IDS: Final[frozenset[int]] = frozenset({
    CURRENT_STATUS_PENDING_INTAKE,
    CURRENT_STATUS_RECEIVED,
    CURRENT_STATUS_WITHDRAWING_APPROVED,
    CURRENT_STATUS_EDIT_REQUESTED,
})

# นักสังคมฯ แก้ไขส่วนที่ 2–4 ปสค.1 โดยตรงได้ (default = active cases)
STAFF_CASE_SECTION_EDIT_STATUS_IDS: Final[frozenset[int]] = ACTIVE_CASE_STATUS_IDS

# สถานะสิ้นสุด — รอ cooldown 30 วันปฏิทินจากวันส่งคำขอ
COOLDOWN_STATUS_IDS: Final[frozenset[int]] = frozenset({
    CURRENT_STATUS_AID_COMPLETED,
    CURRENT_STATUS_INELIGIBLE,
    CURRENT_STATUS_WITHDRAWING,
    CURRENT_STATUS_MSO_FORWARDED,
})
