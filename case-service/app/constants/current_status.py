"""รหัส current_status — ใช้ใน workflow ฝั่งเจ้าหน้าที่."""

# รอรับเรื่อง (vsmart_id=2) — สถานะตั้งต้นเมื่อ ยื่นคำร้อง ไม่ถือเป็น action ของเจ้าหน้าที่
CURRENT_STATUS_PENDING_INTAKE = 1

# อยู่ระหว่างการเบิก (vsmart_id=6) — หลังบันทึกผลจ่าย 037
CURRENT_STATUS_WITHDRAWING = 10
