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
| `digest_date` | `string` (date) | ใช่ | วันที่แสดงในอีเมล — ส่ง `YYYY-MM-DD`; ในอีเมลแสดงเป็น **วันที่ DD เดือนไทย ปี พ.ศ.** เช่น `วันที่ 23 พฤษภาคม 2569` |
| `idempotency_bucket` | `string` | ไม่ | **อ้างอิงรอบจากระบบต้นทาง** (คืนใน response) — **ไม่ใช้กันส่งซ้ำ**; ไม่ส่ง则ใช้ `digest_date` |
| `skip_if_all_zero` | `boolean` | ไม่ | ค่าเริ่มต้น `false` — ส่งอีเมลทุกครั้งที่เรียก API; ตั้ง `true` ถ้าต้องการข้ามเมื่อตัวเลข role เป็น 0 ทั้งหมด |
| `recipients` | `array` | ใช่ | รายการผู้รับอย่างน้อย 1 คน |

#### แต่ละรายการใน `recipients`

| ฟิลด์ | ชนิด | บังคับ | คำอธิบาย |
|--------|------|--------|----------|
| `external_user_id` | `string` | ใช่ | รหัสผู้ใช้จากระบบต้นทาง (ไม่ซ้ำภายในคำขอเดียวกัน) |
| `email` | `string` | ใช่ | ที่อยู่อีเมลผู้รับ |
| `full_name` | `string` | ใช่ | ชื่อ-สกุลในอีเมล |
| `position` | `string` | ไม่ | ตำแหน่ง (แสดงในอีเมลเท่านั้น — **ไม่กำหนด** bucket รอรับเรื่อง/รออนุมัติ) |
| `province_id` | `integer` | ใช่ | รหัสจังหวัด — ใช้ดึงตัวเลขสรุป |
| `role` | `string` | ไม่ | บทบาทหลัก (แนะนำ): `social_worker` \| `pmj` \| `finance` หรือ `พมจ` / `นักสังคม` / `การเงิน` |
| `roles` | `array` | ไม่* | รายการบทบาท — รับชื่อไทยได้; ถ้าไม่ส่ง `role` ใช้รายการนี้หรือเดาจาก `position` |

\* ต้องมีอย่างน้อยหนึ่งใน: `role`, `roles` (ไม่ว่าง), หรือ `position` ที่ระบุตำแหน่งชัด (เช่น พมจ)

**สำคัญ:** ส่ง **`role`: `"pmj"`** (หรือ `"roles": ["พมจ"]`) — อย่าส่งแค่ `position: "พมจ"` โดย `roles: ["social_worker"]` (เดิมจะได้อีเมลนักสังคม; ตอนนี้ระบบเดาจากตำแหน่งถ้าขัดกัน)

### `idempotency_bucket` และการส่งซ้ำ

- **ไม่จำกัดรอบการส่ง** — ทุกครั้งที่ระบบต้นทางเรียก `POST staff-digest` จะส่งอีเมลจริง (idempotency ต่อคำขอเป็น UUID ใหม่)
- **`idempotency_bucket`** ใช้บันทึกใน response / audit เท่านั้น (เช่น `2026-05-22`, `2026-05-22T08`) — **ควบคุมความถี่ด้วย cron ฝั่ง VSmart**
- **ไม่ส่งฟิลด์นี้** → ค่าใน response = `digest_date`

### ตัวอย่าง request — รายวัน (ไม่ส่ง bucket)

```json
{
  "digest_date": "2026-05-21",
  "skip_if_all_zero": false,
  "recipients": [ { "...": "..." } ]
}
```

→ `idempotency_bucket` ที่ใช้จริง = `2026-05-21`

### ตัวอย่าง request — รายชั่วโมง (VSmart ส่ง bucket)

```json
{
  "digest_date": "2026-05-21",
  "idempotency_bucket": "2026-05-21T14",
  "skip_if_all_zero": false,
  "recipients": [ { "...": "..." } ]
}
```

→ ส่งซ้ำใน `T14` ไม่ได้ · ชั่วโมง `T15` ส่งใหม่ได้

### ตัวอย่าง request (dev — 3 บทบาท)

```json
{
  "digest_date": "2026-05-21",
  "idempotency_bucket": "2026-05-21",
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
  "idempotency_bucket": "2026-05-21",
  "sent": [
    {
      "external_user_id": "dev-sw-1",
      "email": "social.worker@example.test",
      "role": "social_worker",
      "highlight_count": 5,
      "idempotency_key": "staff-digest-2026-05-21-dev-sw-1-10",
      "notification": { }
    }
  ],
  "skipped": [
    {
      "external_user_id": "dev-xxx",
      "email": "user@example.test",
      "province_id": 65,
      "reason": "province_no_pending_cases"
    },
    {
      "external_user_id": "dev-pmj-1",
      "email": "pmj@example.test",
      "province_id": 10,
      "reason": "recipient_role_counts_zero"
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
| `skipped` | ไม่ส่งเพราะ `skip_if_all_zero=true` — `province_no_pending_cases` (จังหวัดไม่มีข้อมูลหรือ 0 ทั้งหมด) หรือ `recipient_role_counts_zero` (role ของผู้รับเป็น 0 แต่จังหวัดอื่น bucket ยังมีงาน) |
| `errors` | ล้มเหลวรายคน (เช่น province ไม่มี, notification ล้มเหลว) |

### Idempotency (รายละเอียด)

1. BFF คำนวณ `idempotency_bucket` = ค่าจาก request หรือ `digest_date`
2. สร้างคีย์ `staff-digest-{bucket}-{external_user_id}-{province_id}`
3. notification-service จำคีย์ในหน่วยความำ (dev) — คีย์เดิมคืน record เดิม **ไม่ส่ง SMTP ซ้ำ**

| เปลี่ยนค่า | ส่งเมลใหม่? |
|-----------|-------------|
| `idempotency_bucket` เดิม | ไม่ |
| `idempotency_bucket` ใหม่ (รอบใหม่ที่ VSmart กำหนด) | ใช่ |
| `external_user_id` ใหม่ | ใช่ |
| `province_id` ใหม่ | ใช่ |
| restart notification-service (dev) | ใช่ (ล้าง index) |

Response มี `idempotency_bucket` (ค่าที่ใช้จริง) และใน `sent[]` มี `idempotency_key` ต่อคน

**หมายเหตุ production:** index ใน RAM โตตามจำนวนคีย์ — แนะนำ Redis/DB + TTL ตามโหมดรอบ (ดู [หน่วยความจำ](#หน่วยความจำ-idempotency-dev))

### Production (VSmart cron)

- กำหนด **`idempotency_bucket` ตามตาราง cron** (รายวัน / รายชั่วโมง ฯลฯ)
- `digest_date` = วันที่แสดงในอีเมล (มักตรงกับวันรัน cron)
- แทนที่ `email`, `full_name`, `position`, `province_id`, `external_user_id` ด้วยข้อมูลผู้ใช้จริง
- `skip_if_all_zero: true` (ค่าเริ่มต้น) — จังหวัดที่ `total_applicants = 0` หรือตัวเลขรอรับเรื่อง/รออนุมัติ/รอเบิกจ่ายเป็น 0 ทั้งหมด จะไม่ส่งอีเมลให้ทุกคนในจังหวัดนั้น
- ผู้รับหลาย role → **คนละ `external_user_id`** (เช่น `user-123-sw`, `user-123-pmj`) หรือหลายแถวใน `recipients`

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
  "withdrawing_in_progress": 11,
  "pmj_pending_approve": 3,
  "finance_pending": 8,
  "social_worker_emergency": 2,
  "pmj_emergency": 1,
  "finance_emergency": 0
}
```

### กฎนับตัวเลข (case-service)

| ฟิลด์ใน response | แสดงในอีเมล | เงื่อนไข |
|------------------|-------------|----------|
| `social_worker_pending` | รอรับเรื่อง | สถานะล่าสุด **รอรับเรื่อง** (`current_status_id = 1`) |
| `withdrawing_in_progress` | *(ไม่แสดง)* | สถานะล่าสุด **อยู่ระหว่างการเบิก** (`current_status_id` = 3 หรือ 10) — มีใน API เพื่อ debug |
| `pmj_pending_approve` | รออนุมัติ | อยู่ระหว่างการเบิก **และ** ยังไม่มี `approve_case.approve_status = true` |
| `finance_pending` | รอการเบิกจ่าย | อยู่ระหว่างการเบิก **และ** มี `approve_case.approve_status = true` |
| `social_worker_emergency` | *(ตาม role)* | รอรับเรื่อง **และ** `applicants.is_emergency = true` |
| `pmj_emergency` | *(ตาม role)* | รออนุมัติ **และ** `is_emergency = true` |
| `finance_emergency` | *(ตาม role)* | รอการเบิกจ่าย **และ** `is_emergency = true` |
| `total_applicants` | แสดงในอีเมล | นับทุก applicant ในจังหวัด (ที่อยู่หลัก) — ข้อความ "คำร้องทั้งหมดในจังหวัด…" |

- `current_status_id = 3` — หลังพมจ.อนุมัติ (workflow `approve_case`)
- `current_status_id = 10` — หลังบันทึกผลจ่าย 037 (สถานะเดียวกัน `description_staff`: อยู่ระหว่างการเบิก)
- รออนุมัติ + รอการเบิกจ่าย = แยกย่อยจากกลุ่มอยู่ระหว่างการเบิก (`pmj` + `finance` ≤ `withdrawing_in_progress`)

สถานะล่าสุด = แถวล่าสุดใน `welfare_request_status` ต่อ applicant (เรียง `updated_at`, `id` desc)

---

## บทบาท (`roles`) และตัวเลขในอีเมล

อีเมลแสดง **เฉพาะ bucket ของ role ผู้รับ** (2 กล่อง) — ไม่แสดงตัวเลขของ role อื่น

| `roles` | กล่องที่ 1 (รอดำเนินการ) | ฟิลด์ | กล่องที่ 2 (เร่งด่วน) | ฟิลด์ |
|---------|--------------------------|--------|------------------------|--------|
| `social_worker` | รอรับเรื่อง | `social_worker_pending` | คำร้องเร่งด่วน (รอรับเรื่อง) | `social_worker_emergency` |
| `pmj` | รออนุมัติ | `pmj_pending_approve` | คำร้องเร่งด่วน (รออนุมัติ) | `pmj_emergency` |
| `finance` | รอการเบิกจ่าย | `finance_pending` | คำร้องเร่งด่วน (รอการเบิกจ่าย) | `finance_emergency` |

**คำร้องเร่งด่วน:** นับจาก `applicants.is_emergency = true` ภายใน bucket เดียวกับกล่องที่ 1 (ไม่ใช่ทั้งจังหวัดข้าม role)

---

## เทมเพลต `STAFF_CASE_STATUS_DIGEST`

BFF สร้าง payload ด้านล่างแล้วเรียก notification-service อัตโนมัติ — บันทึกไว้สำหรับทีมที่ต้อง debug หรือเรียก `POST /v1/notifications` โดยตรง

### `POST /v1/notifications` (notification-service)

```json
{
  "idempotency_key": "staff-digest-2026-05-21T08-dev-sw-1-65",
  "channel": "email",
  "to": "social.worker@example.test",
  "template_code": "STAFF_CASE_STATUS_DIGEST",
  "payload": {
    "staff_name": "นายทดสอบ นักสังคม",
    "full_name": "นายทดสอบ นักสังคม",
    "position": "นักสังคมสงเคมชนชั้นกลาง",
    "province_name": "กรุงเทพมหานคร",
    "total_applicants": 120,
    "digest_date": "2026-05-21",
    "highlight_label": "รอรับเรื่อง",
    "highlight_count": 5,
    "emergency_label": "คำร้องเร่งด่วน (รอรับเรื่อง)",
    "emergency_count": 2,
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
| `total_applicants` | แนะนำ | จำนวนคำร้องทั้งหมดในจังหวัด — แสดงในอีเมล |
| `digest_date` | แนะนำ | วันที่สรุป — ส่ง `YYYY-MM-DD`; แสดงในอีเมลเป็น `วันที่ DD เดือนไทย ปี พ.ศ.` |
| `highlight_label` | แนะนำ | ข้อความกล่องรอดำเนินการ (ตาม role) |
| `highlight_count` | แนะนำ | จำนวนรอดำเนินการ |
| `emergency_label` | แนะนำ | ข้อความกล่องเร่งด่วน (ตาม role) |
| `emergency_count` | แนะนำ | จำนวน `is_emergency` ใน bucket เดียวกัน |
| `role` | แนะนำ | `social_worker` \| `pmj` \| `finance` |
| `tracking_url` | ไม่ | ลิงก์ พม. CARE — ถ้าไม่ส่งใช้ `FRONTEND_URL` ของ notification-service |

**หัวข้ออีเมล (ตัวอย่าง):** `สรุปคำร้องรายวัน (วันที่ 21 พฤษภาคม 2569) — กรุงเทพมหานคร`

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

**Swagger:** เปิด `http://localhost:8000/api-vsmartcare/docs` → Authorize → **BffApiKey** `1234567890` → `POST .../staff-digest` → **Example Value** แล้ว Execute

**สำคัญ:** ในกล่อง Request body ต้องเห็น `digest_date`, `idempotency_bucket` (optional), `skip_if_all_zero`, `recipients` — **ห้าม** มี `summary` หรือ `value` (ถ้าเห็น แปลว่าคัดลอกผิดจาก schema เก่า; รีเฟรช `/docs` หลัง deploy)

**หมายเหตุ:** `GET /serviceworker.js` 404 ไม่เกี่ยวกับ API นี้ (เบราว์เซอร์พยายามโหลด service worker ที่ root ของพอร์ต 8000)

| อาการ | สาเหตุที่เป็นไปได้ |
|--------|-------------------|
| `401` จาก BFF | ไม่ส่ง `X-API-Key` หรือไม่ตรง `BFF_API_PASSWORD` |
| `404` จาก status-summary | `province_id` ไม่มีใน master จังหวัด |
| อยู่ใน `skipped` | `skip_if_all_zero=true` — จังหวัด 0 ทั้งหมด (`province_no_pending_cases`) หรือ role ผู้รับเป็น 0 (`recipient_role_counts_zero`) |
| อีเมลไม่เข้า Mailpit | ไม่ได้รัน dev compose / `EMAIL_MODE` ยังเป็น `log` |
| ส่งซ้ำแล้วไม่มีเมลใหม่ | คีย์เดิม — เปลี่ยน `idempotency_bucket` / user / จังหวัด หรือ restart service (dev) |

---

## หน่วยความจำ idempotency (dev)

notification-service เก็บ `idempotency_index` ใน RAM (ไม่มี TTL ในรอบนี้)

| โหมด VSmart | คีย์ต่อวัน (โดยประมาณ) |
|------------|------------------------|
| รายวัน | ~ (จำนวนผู้รับ × จังหวัด) ต่อวัน |
| รายชั่วโมง | × 24 ต่อวัน ถ้าไม่ restart |

**แนะนำ production:** Redis/DB + TTL (รายวัน ~48 ชม., รายชั่วโมง ~2 ชม.) — งานแยกจาก staff-digest API

---

## ไฟล์อ้างอิงใน repo

| ส่วน | path |
|------|------|
| BFF endpoint + proxy summary | `bff-vsmartcare/app/main.py` |
| Logic ส่ง batch | `bff-vsmartcare/app/services/staff_digest_dispatch.py` |
| สรุปตัวเลข | `case-service/app/services/staff_digest_summary.py` |
| ค่าคงที่ role / status | `case-service/app/constants/staff_digest.py` |
| เทมเพลตอีเมล | `notification-service/app/email_templates/staff_case_status_digest/` |
