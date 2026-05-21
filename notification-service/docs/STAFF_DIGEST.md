# Staff digest — คู่มือเชื่อมต่อสำหรับระบบภายนอก

เอกสารนี้อธิบายการส่ง **อีเมลสรุปคำร้องสวัสดิการรายวัน** ให้เจ้าหน้าที่ (นักสังคม / พมจ. / การเงิน) เพื่อให้ระบบอื่น (เช่น **VSmart cron**) สร้างฟังก์ชันเรียก API ได้โดยไม่ต้องอ่านโค้ดทั้ง stack

---

## สรุปสถาปัตยกรรม

```text
ระบบภายนอก (VSmart cron)
    │
    │  POST /api-vsmartcare/v1/notifications/staff-digest
    │  Header: X-API-Key
    ▼
bff-vsmartcare
    ├── GET case-service /v1/case_for_staff/status-summary?province_id=
    └── POST notification-service /v1/notifications
            template_code: STAFF_CASE_STATUS_DIGEST
            ▼
        SMTP → Mailpit (dev) / relay จริง (production)
```

- **จุดเชื่อมต่อหลัก:** BFF `POST /v1/notifications/staff-digest` — ส่งรายชื่อผู้รับ + วันที่ ระบบจะดึงตัวเลขจาก case-service และส่งอีเมลให้เอง
- **ไม่ต้อง** เรียก notification-service โดยตรง ยกเว้นทดสอบเทมเพลตแยก (ดู [เทมเพลตอีเมล](#เทมเพลต-staff_case_status_digest) ด้านล่าง)

| สภาพแวดล้อม | Base URL BFF (ตัวอย่าง) |
|-------------|-------------------------|
| Docker Compose (host) | `http://localhost:8000/api-vsmartcare` |
| ภายใน compose network | `http://bff-vsmartcare:8000` + prefix ตาม `BFF_API_PREFIX` |

Swagger BFF: `{base}/docs`

---

## การยืนยันตัวตน

ทุก endpoint ใต้ `/v1/*` ของ BFF ต้องส่ง header:

```http
X-API-Key: {ค่าเดียวกับ BFF_API_PASSWORD}
```

ค่า default ใน `docker-compose.yml`: `1234567890` (ปรับใน env ของ deployment จริง)

---

## 1. ส่งอีเมลสรุปรายวัน (endpoint หลัก)

### `POST /v1/notifications/staff-digest`

**Content-Type:** `application/json`

### Request body

| ฟิลด์ | ชนิด | บังคับ | คำอธิบาย |
|--------|------|--------|----------|
| `digest_date` | `string` (date) | ใช่ | วันที่สรุป รูปแบบ `YYYY-MM-DD` (ใช้ใน idempotency และหัวอีเมล) |
| `skip_if_all_zero` | `boolean` | ไม่ | ค่าเริ่มต้น `true` — ข้ามผู้รับถ้าตัวเลขของ **ทุก role ใน `roles`** เป็น 0 |
| `recipients` | `array` | ใช่ | รายการผู้รับอย่างน้อย 1 คน |

#### แต่ละรายการใน `recipients`

| ฟิลด์ | ชนิด | บังคับ | คำอธิบาย |
|--------|------|--------|----------|
| `external_user_id` | `string` | ใช่ | รหัสผู้ใช้จากระบบต้นทาง (ไม่ซ้ำภายในคำขอเดียวกัน) — ใช้ใน idempotency |
| `email` | `string` | ใช่ | ที่อยู่อีเมลผู้รับ |
| `full_name` | `string` | ใช่ | ชื่อ-สกุลในอีเมล |
| `position` | `string` | ไม่ | ตำแหน่ง (แสดงในอีเมล) |
| `province_id` | `integer` | ใช่ | รหัสจังหวัด — ใช้ดึงตัวเลขสรุป |
| `roles` | `array` | ใช่ | อย่างน้อย 1 ค่า — ดู [บทบาท](#บทบาท-roles-และตัวเลขในอีเมล) |

**หมายเหตุ:** ปัจจุบัน BFF ใช้ **role แรก** ใน `roles` เป็นตัวกำหนด highlight หลักในอีเมล (หนึ่งอีเมลต่อหนึ่ง recipient)

### ตัวอย่าง request (dev — 3 บทบาท)

```json
{
  "digest_date": "2026-05-21",
  "skip_if_all_zero": false,
  "recipients": [
    {
      "external_user_id": "dev-sw-1",
      "email": "social.worker@example.test",
      "full_name": "นายทดสอบ นักสังคม",
      "position": "นักสังคมสงเคมชนชั้นกลาง",
      "province_id": 10,
      "roles": ["social_worker"]
    },
    {
      "external_user_id": "dev-pmj-1",
      "email": "pmj@example.test",
      "full_name": "นางทดสอบ พมจ",
      "position": "พมจ.",
      "province_id": 10,
      "roles": ["pmj"]
    },
    {
      "external_user_id": "dev-fin-1",
      "email": "finance@example.test",
      "full_name": "นายทดสอบ การเงิน",
      "position": "เจ้าหน้าที่การเงิน",
      "province_id": 10,
      "roles": ["finance"]
    }
  ]
}
```

### ตัวอย่าง curl (Windows)

```bash
curl.exe -s -X POST "http://localhost:8000/api-vsmartcare/v1/notifications/staff-digest" ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: 1234567890" ^
  -d @staff-digest-request.json
```

### Response (`200`)

```json
{
  "digest_date": "2026-05-21",
  "sent": [
    {
      "external_user_id": "dev-sw-1",
      "email": "social.worker@example.test",
      "role": "social_worker",
      "highlight_count": 5,
      "notification": { }
    }
  ],
  "skipped": [
    {
      "external_user_id": "dev-xxx",
      "email": "user@example.test",
      "reason": "all_role_counts_zero"
    }
  ],
  "errors": [
    {
      "external_user_id": "dev-yyy",
      "email": "bad@example.test",
      "status_code": 502,
      "detail": "..."
    }
  ]
}
```

| ส่วน | ความหมาย |
|------|----------|
| `sent` | ส่งอีเมลสำเร็จ (หรือ idempotency คืน record เดิม) — มี `notification` จาก notification-service |
| `skipped` | ไม่ส่งเพราะ `skip_if_all_zero=true` และตัวเลขของ role ที่ระบุเป็น 0 ทั้งหมด |
| `errors` | ล้มเหลวรายคน (เช่น province ไม่มี, notification ล้มเหลว) |

### Idempotency

- คีย์ต่อผู้รับ: `staff-digest-{digest_date}-{external_user_id}`
- ส่งคำขอซ้ำด้วย `digest_date` + `external_user_id` เดิม → ได้ notification record เดิม **ไม่ส่ง SMTP ซ้ำ**

### Production (VSmart cron)

- ใช้ body **รูปแบบเดียวกับ dev**
- แทนที่ `email`, `full_name`, `position`, `province_id`, `external_user_id` ด้วยข้อมูลผู้ใช้จริงจากระบบต้นทาง
- ตั้ง `skip_if_all_zero: true` ได้ถ้าไม่ต้องการแจ้งเมื่อไม่มีงานค้าง

---

## 2. ตรวจตัวเลขสรุป (ทางเลือก)

### `GET /v1/case_for_staff/status-summary?province_id={id}`

ใช้ตรวจว่าตัวเลขในอีเมลตรงกับที่ระบบคำนวณ (หรือ debug ก่อนส่ง digest)

**Response:**

```json
{
  "province_id": 10,
  "province_name": "กรุงเทพมหานคร",
  "total_applicants": 120,
  "social_worker_pending": 5,
  "pmj_pending_approve": 3,
  "finance_pending": 8
}
```

### กฎนับตัวเลข (case-service)

| ฟิลด์ใน response | เงื่อนไข |
|------------------|----------|
| `social_worker_pending` | สถานะล่าสุด `current_status_id = 1` |
| `pmj_pending_approve` | `current_status_id = 2` **และ** ยังไม่มี `approve_case.approve_status = true` |
| `finance_pending` | สถานะล่าสุด `current_status_id = 3` |
| `total_applicants` | จำนวนคำร้องทั้งหมดในจังหวัด (ตามที่อยู่หลักของผู้ยื่น) |

สถานะล่าสุด = แถวล่าสุดใน `welfare_request_status` ต่อ applicant (เรียง `updated_at`, `id` desc)

---

## บทบาท (`roles`) และตัวเลขในอีเมล

| `roles` | ข้อความ highlight ในอีเมล | ฟิลด์ตัวเลขที่ใช้ |
|---------|---------------------------|-------------------|
| `social_worker` | รอรับเรื่อง | `social_worker_pending` |
| `pmj` | รออนุมัติ | `pmj_pending_approve` |
| `finance` | รอเบิก | `finance_pending` |

อีเมลแสดงตัวเลข highlight ของ role หลัก พร้อมตารางสรุปทั้งสาม bucket + `total_applicants`

---

## เทมเพลต `STAFF_CASE_STATUS_DIGEST`

BFF สร้าง payload ด้านล่างแล้วเรียก notification-service อัตโนมัติ — บันทึกไว้สำหรับทีมที่ต้อง debug หรือเรียก `POST /v1/notifications` โดยตรง

### `POST /v1/notifications` (notification-service)

```json
{
  "idempotency_key": "staff-digest-2026-05-21-dev-sw-1",
  "channel": "email",
  "to": "social.worker@example.test",
  "template_code": "STAFF_CASE_STATUS_DIGEST",
  "payload": {
    "staff_name": "นายทดสอบ นักสังคม",
    "full_name": "นายทดสอบ นักสังคม",
    "position": "นักสังคมสงเคมชนชั้นกลาง",
    "province_name": "กรุงเทพมหานคร",
    "digest_date": "2026-05-21",
    "highlight_label": "รอรับเรื่อง",
    "highlight_count": 5,
    "social_worker_pending": 5,
    "pmj_pending_approve": 3,
    "finance_pending": 8,
    "total_applicants": 120,
    "tracking_url": "http://localhost:5173/",
    "role": "social_worker"
  }
}
```

| ฟิลด์ payload | บังคับ | คำอธิบาย |
|---------------|--------|----------|
| `staff_name` หรือ `full_name` | แนะนำ | ชื่อในการทักทาย |
| `position` | ไม่ | ตำแหน่ง |
| `province_name` | แนะนำ | ชื่อจังหวัด |
| `digest_date` | แนะนำ | วันที่สรุป (`YYYY-MM-DD`) |
| `highlight_label` | แนะนำ | ข้อความกล่องตัวเลขใหญ่ |
| `highlight_count` | แนะนำ | จำนวนในกล่อง highlight |
| `social_worker_pending` | ไม่ | ตัวเลขในตาราง |
| `pmj_pending_approve` | ไม่ | ตัวเลขในตาราง |
| `finance_pending` | ไม่ | ตัวเลขในตาราง |
| `total_applicants` | ไม่ | รวมทั้งจังหวัด |
| `tracking_url` | ไม่ | ลิงก์ พม. CARE — ถ้าไม่ส่งใช้ `FRONTEND_URL` ของ notification-service |

**หัวข้ออีเมล (ตัวอย่าง):** `สรุปคำร้องรายวัน (2026-05-21) — กรุงเทพมหานคร`

---

## Dev — Mailpit

จากโฟลเดอร์ `service/`:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

ค่า env ของ notification-service ใน `docker-compose.dev.yml`:

| ตัวแปร | ค่า |
|--------|-----|
| `EMAIL_MODE` | `smtp` |
| `EMAIL_AUTO_SEND` | `true` |
| `SMTP_HOST` | `mailpit` |
| `SMTP_PORT` | `1025` |
| `SMTP_USE_TLS` | `false` |

- ดู inbox: **http://localhost:8025**
- หลัง `POST staff-digest` ควรเห็นอีเมล 1 ฉบับต่อ 1 recipient ใน `sent`

---

## ข้อผิดพลาดที่พบบ่อย

### `422 Unprocessable Entity`

แปลว่า **body JSON ไม่ผ่าน validation** — ดูรายละเอียดใน response `detail` (Swagger แสดงใต้ Response body)

| สาเหตุ | วิธีแก้ |
|--------|--------|
| ส่ง body ว่าง / ไม่กด Example ใน Swagger | ใส่ JSON ครบ `digest_date` + `recipients` อย่างน้อย 1 คน — ใน Swagger กด **Try it out** แล้วเลือก **Example Value** จาก schema |
| `digest_date` ผิดรูปแบบ | ใช้ **`YYYY-MM-DD`** เท่านั้น เช่น `"2026-05-21"` — **ไม่ใช่** `21/05/2026` |
| `roles` ผิดค่า | ต้องเป็น **`social_worker`**, **`pmj`**, **`finance`** เท่านั้น (ภาษาอังกฤษ snake_case) |
| `roles` เป็น array ว่าง | ต้องมีอย่างน้อย 1 role ต่อ recipient |
| `email` สั้นเกินไป | อย่างน้อย 3 ตัวอักษร |
| JSON พัง (คอมม่าเกิน, ไม่มี quote) | ตรวจด้วย JSON validator หรือส่งจากไฟล์ `.json` |

ตัวอย่าง response เมื่อขาดฟิลด์:

```json
{
  "detail": [
    {"type": "missing", "loc": ["body", "digest_date"], "msg": "Field required"},
    {"type": "missing", "loc": ["body", "recipients"], "msg": "Field required"}
  ]
}
```

**Swagger:** เปิด `http://localhost:8000/api-vsmartcare/docs` → Authorize → เลือก **BffApiKey** ใส่ `1234567890` → endpoint `POST .../staff-digest` → Example Value แล้ว Execute

**หมายเหตุ:** `GET /serviceworker.js` 404 ไม่เกี่ยวกับ API นี้ (เบราว์เซอร์พยายามโหลด service worker ที่ root ของพอร์ต 8000)

| อาการ | สาเหตุที่เป็นไปได้ |
|--------|-------------------|
| `401` จาก BFF | ไม่ส่ง `X-API-Key` หรือไม่ตรง `BFF_API_PASSWORD` |
| `404` จาก status-summary | `province_id` ไม่มีใน master จังหวัด |
| อยู่ใน `skipped` | `skip_if_all_zero=true` และตัวเลข role เป็น 0 |
| อีเมลไม่เข้า Mailpit | ไม่ได้รัน dev compose / `EMAIL_MODE` ยังเป็น `log` |
| ส่งซ้ำแล้วไม่มีเมลใหม่ | พฤติกรรม idempotency ปกติ — ใช้ `digest_date` หรือ `external_user_id` ใหม่ถ้าต้องการฉบับใหม่ |

---

## ไฟล์อ้างอิงใน repo

| ส่วน | path |
|------|------|
| BFF endpoint + proxy summary | `bff-vsmartcare/app/main.py` |
| Logic ส่ง batch | `bff-vsmartcare/app/services/staff_digest_dispatch.py` |
| สรุปตัวเลข | `case-service/app/services/staff_digest_summary.py` |
| ค่าคงที่ role / status | `case-service/app/constants/staff_digest.py` |
| เทมเพลตอีเมล | `notification-service/app/email_templates/staff_case_status_digest/` |
