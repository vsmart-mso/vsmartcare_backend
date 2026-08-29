# MSO Forward API — ส่งต่อกระทรวง / MSO Logbook

เอกสารสำหรับทีมที่พัฒนาระบบภายนอก (เช่น VSmart / หน้าจอ MSO) เพื่อบันทึกและตรวจสอบการส่งต่อข้อมูลคำร้อง โดยอ้างอิงตาราง `type_send` และ `send_data` ใน case-service

---

## ภาพรวม

| ช่องทาง | คีย์ `send_channel` | `type_send.id` | ชื่อใน master |
|--------|---------------------|----------------|---------------|
| ส่งต่อเข้าหระทรวง | `ministry` | 1 | ส่งต่อเข้าหระทรวง |
| ส่งต่อ MSO logbook | `logbook` | 2 | ส่งต่อ mso logbook |

- แต่ละครั้งที่ส่งต่อสำเร็จ ให้เรียก **POST** เพื่อสร้างแถวใน `send_data` (เก็บประวัติได้หลายครั้งต่อช่องทาง)
- ก่อนแสดงปุ่มส่งต่อ ให้เรียก **GET** เพื่อดูว่าช่องทางนั้นส่งไปแล้วหรือยัง → ใช้ `disabled` ปุ่มเมื่อ `sent === true`
- ดูประวัติแบบตาราง (ทุกช่องทางรวมกัน) ผ่าน **GET mso-forward-logs**
- ดึง `json_case` ของแถวหนึ่งผ่าน **GET mso-forward-logs/{send_data_id}**

**Base URL (แนะนำผ่าน BFF):**

```text
https://<bff-host>/api-vsmartcare
```

**Authentication:** header `X-API-Key` (ตามที่ BFF กำหนด)

**เรียก case-service โดยตรง (ภายในเครือข่าย):**

```text
http://case-service:8000/v1/case_for_staff/applicant/{applicant_id}/...
```

---

## 1. บันทึกการส่งต่อ — POST

### BFF

```http
POST /v1/case_for_staff/applicant/{applicant_id}/mso-forward
Content-Type: application/json
X-API-Key: <key>
```

BFF จะ inject อัตโนมัติเฉพาะ:

| ฟิลด์ | แหล่ง |
|--------|------|
| `ip_address` | `X-Forwarded-For` หรือ client IP ของ hop ที่เข้า BFF |

**`user_agent` และ `request_url` ต้องส่งจาก frontend (เบราว์เซอร์)** — ห้ามให้ backend/proxy ใส่ค่าของตัวเอง:

```js
{
  send_channel: "logbook",
  send_by_sdshv: "...",
  user_agent: navigator.userAgent,
  request_url: window.location.href,  // หน้าจอที่กดส่งต่อ ไม่ใช่ URL ของ API
}
```

ถ้าไม่ส่งมา ฟิลด์เหล่านี้จะเป็น `null` (BFF **ไม่** ดึงจาก header `User-Agent` หรือ `request.url` ของ API เพราะ hop ฝั่ง server มักเป็น `python-requests` / URL ของ BFF)

### case-service

```http
POST /v1/case_for_staff/applicant/{applicant_id}/mso-forward
```

### Request body

| ฟิลด์ | ชนิด | บังคับ | คำอธิบาย |
|--------|------|--------|----------|
| `send_channel` | `"ministry"` \| `"logbook"` | ใช่ | แยกช่องทางส่งต่อ |
| `send_by_sdshv` | string | ไม่ | รหัสผู้บันทึก (SDSHV) — **ผู้ส่ง** |
| `json_case` | object | ไม่ | payload ที่ส่งออก (audit) |
| `response_code` | string | ไม่ | รหัสตอบกลับจาก API ปลายทาง (เช่น `"200"`) — ไม่ใช่ HTTP status ของ POST นี้ |
| `response_text` | string | ไม่ | ไม่ต้องส่ง — ระบบเขียน `{ "status": "OK", "id": <send_data.id>, "applicant_id": <id> }` เองหลังได้ id |
| `ip_address` | string | ไม่ | IP (BFF inject) |
| `user_agent` | string | ไม่ | `navigator.userAgent` จากเบราว์เซอร์ |
| `request_url` | string | ไม่ | `window.location.href` ของหน้าจอที่กดส่งต่อ |

**หมายเหตุ:** ไม่มี `sender_name` / `sender_phone` — ผู้ส่ง = `send_by_sdshv` เท่านั้น

### ตัวอย่าง — ส่งต่อ MSO logbook สำเร็จ

```json
{
  "send_channel": "logbook",
  "send_by_sdshv": "user-12345",
  "json_case": { "case_number": "case-202605-000001" },
  "response_code": "200",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "request_url": "https://vsmart.example/cases/1001"
}
```

### Response `201 Created`

```json
{
  "id": 42,
  "applicant_id": 1001,
  "send_channel": "logbook",
  "type_send_id": 2,
  "send_by_sdshv": "user-12345",
  "json_case": { "case_number": "case-202605-000001" },
  "response_code": "200",
  "response_text": { "status": "OK", "id": 42, "applicant_id": 1001 },
  "created_at": "2026-08-29T10:15:00+00:00",
  "updated_at": "2026-08-29T10:15:00+00:00",
  "ip_address": "203.0.113.10",
  "user_agent": "Mozilla/5.0 ...",
  "request_url": "https://vsmart.example/cases/1001",
  "device": null,
  "browser": "Chrome",
  "browser_version": "120.0.0.0",
  "os": "Windows",
  "os_version": "10",
  "type_money_category_id": 1,
  "type_money_name": "เงินช่วยเหลือ ...",
  "type_money_acronym": "สป.",
  "province_id": 10,
  "province_name": "กรุงเทพมหานคร",
  "affected_person_name": "นาย ทดสอบ ระบบ",
  "affected_person_cid": "1234567890123"
}
```

ตอนบันทึก ระบบ snapshot ประเภทเงิน (`type_money_category`), จังหวัดเคส, ชื่อ/เลขบัตรผู้ประสบปัญหา และ parse User-Agent เป็น `device` / `browser` / `os`

### ข้อผิดพลาด

| HTTP | `detail` | สาเหตุ |
|------|----------|--------|
| 404 | `applicant_not_found` | ไม่มี `applicant_id` |
| 404 | `type_send_not_found` | master `type_send` ไม่ครบ (ควรมี id 1, 2) |
| 422 | validation error | `send_channel` ไม่ใช่ `ministry` หรือ `logbook` |

---

## 2. ตรวจสถานะการส่งต่อ — GET

### BFF

```http
GET /v1/case_for_staff/applicant/{applicant_id}/mso-forward-status
X-API-Key: <key>
```

### case-service

```http
GET /v1/case_for_staff/applicant/{applicant_id}/mso-forward-status
```

### Response `200 OK`

```json
{
  "applicant_id": 1001,
  "ministry": {
    "send_channel": "ministry",
    "type_send_id": 1,
    "sent": false,
    "latest_send_data_id": null
  },
  "logbook": {
    "send_channel": "logbook",
    "type_send_id": 2,
    "sent": true,
    "latest_send_data_id": 42
  }
}
```

| ฟิลด์ | ความหมาย |
|--------|----------|
| `*.sent` | `true` ถ้ามีแถว `send_data` ของช่องทางนั้นอย่างน้อย 1 ครั้ง |
| `*.latest_send_data_id` | `id` แถวล่าสุดของช่องทางนั้น (ใช้เปิดดูประวัติ / audit) |

### Logic ปุ่มส่งต่อ (ฝั่ง UI / ระบบอื่น)

```text
ปุ่ม "ส่งต่อเข้าหระทรวง"  disabled  ←  response.ministry.sent === true
ปุ่ม "ส่งต่อ MSO logbook"   disabled  ←  response.logbook.sent === true
```

---

## 3. รายการ log แบบตาราง — GET mso-forward-logs

### BFF

```http
GET /v1/case_for_staff/mso-forward-logs?limit=50
GET /v1/case_for_staff/mso-forward-logs?province_id=10&limit=50
GET /v1/case_for_staff/mso-forward-logs?province_id=10&province_id=20
X-API-Key: <key>
```

### case-service

```http
GET /v1/case_for_staff/mso-forward-logs
GET /v1/case_for_staff/mso-forward-logs?province_id=10
GET /v1/case_for_staff/mso-forward-logs?province_id=10&province_id=20
```

### Query parameters

Filter เดิม (`case_number`, `cid`, `send_channel`, `type_money_id`, `date_from`/`date_to`, `response_code`, `skip`/`limit`) ยังทำงานเหมือนเดิม

| Param | บังคับ | คำอธิบาย |
|-------|--------|----------|
| `province_id` | ไม่ | กรองตามจังหวัด — ส่งซ้ำได้หลายค่า; ไม่ส่ง = ตามสิทธิ์ (internal = ทั้งระบบ, staff JWT = จังหวัดของตนเองเท่านั้น) |
| `case_number` | ไม่ | ค้นหาเลข case บางส่วน (ILIKE) |
| `cid` | ไม่ | เลขบัตรผู้ประสบปัญหา |
| `send_channel` | ไม่ | `ministry` \| `logbook` |
| `type_money_id` | ไม่ | `type_money_category.id` |
| `date_from`, `date_to` | ไม่ | ช่วง `created_at` (YYYY-MM-DD) |
| `response_code` | ไม่ | กรองรหัสตอบกลับ |
| `ip_address` | ไม่ | ILIKE บางส่วนบน `send_data.ip_address` (ค่าที่เก็บใน DB) |
| `user_agent` | ไม่ | ILIKE บางส่วนบน `send_data.user_agent` |
| `device` | ไม่ | ILIKE บางส่วนบน `send_data.device` |
| `browser` | ไม่ | ILIKE บางส่วนบน `send_data.browser` |
| `browser_version` | ไม่ | ILIKE บางส่วนบน `send_data.browser_version` |
| `os` | ไม่ | ILIKE บางส่วนบน `send_data.os` |
| `os_version` | ไม่ | ILIKE บางส่วนบน `send_data.os_version` |
| `request_url` | ไม่ | ILIKE บางส่วนบน `send_data.request_url` |
| `skip`, `limit` | ไม่ | pagination (default `limit=50`, max `200`) |

Audit filters กรองคอลัมน์ใน DB โดยตรง (ไม่ re-parse UA). GET list ยัง sanitize ตอนแสดง (`Python Requests` → null) แต่กรอง `browser=Python Requests` ยังเจอแถวเก่าที่บันทึกไว้

ถ้า staff JWT ส่ง `province_id` ที่ไม่อยู่ใน scope → `403 province_scope_denied`

### Response `200 OK`

```json
{
  "province_ids": [10],
  "total": 1,
  "items": [
    {
      "id": 42,
      "case_number": "case-202605-000001",
      "type_money_name": "เงินช่วยเหลือ ...",
      "type_money_acronym": "สป.",
      "target_group_label": "สป. — เงินช่วยเหลือ ...",
      "timestamp": "2026-08-29T10:15:00+00:00",
      "response_code": "200",
      "response_text": { "status": "OK", "id": 42, "applicant_id": 1001 },
      "sender_sdshv": "user-12345",
      "sender_phone": null,
      "affected_person_name": "นาย ทดสอบ ระบบ",
      "affected_person_cid": "1234567890123",
      "province_name": "กรุงเทพมหานคร",
      "ip_address": "203.0.113.10",
      "user_agent": "Mozilla/5.0 ...",
      "device": null,
      "browser": "Chrome",
      "browser_version": "120.0.0.0",
      "os": "Windows",
      "os_version": "10",
      "url": "https://vsmart.example/cases/1001",
      "send_channel": "logbook",
      "applicant_id": 1001
    }
  ]
}
```

`province_ids` ว่าง (`[]`) = ไม่ได้กรองจังหวัด / ดูทั้งหมดตามสิทธิ์ (internal API key ที่ไม่ส่ง `province_id`)

### Mapping คอลัมน์ UI → API

| คอลัมน์ UI | ฟิลด์ API |
|------------|-----------|
| id | `id` |
| case_number | `case_number` |
| กลุ่มเป้าหมาย ตัวย่อ และ เงิน | `target_group_label` หรือแยก `type_money_acronym` + `type_money_name` |
| timestamp | `timestamp` |
| response_code / response_text | ตรงชื่อ — `response_text` ของแถวใหม่เป็น object `{status, id, applicant_id}` |
| ผู้ส่ง | `sender_sdshv` |
| เบอร์โทรฯ ผู้ส่ง | `sender_phone` (**null เสมอ** — ไม่มีแหล่งข้อมูล) |
| ผู้ประสบปัญหา | `affected_person_name` |
| เลขบัตรฯ ผู้ประสบปัญหา | `affected_person_cid` |
| จังหวัด | `province_name` |
| ip_address … url | ตรงชื่อ |

แถวเก่าก่อน migration 0080: ไม่มี snapshot/audit — API ยังแสดงได้จาก join fallback (จังหวัด, ประเภทเงิน, บุคคลจากเคสปัจจุบัน)

---

## 4. ดึง json_case ตาม send_data.id — GET mso-forward-logs/{send_data_id}

### BFF

```http
GET /v1/case_for_staff/mso-forward-logs/42
X-API-Key: <key>
```

### case-service

```http
GET /v1/case_for_staff/mso-forward-logs/42
```

### Response `200 OK`

```json
{
  "id": 42,
  "applicant_id": 1001,
  "json_case": {"case_number": "case-202605-000001"}
}
```

| สถานะ | เงื่อนไข |
|--------|----------|
| `404 send_data_not_found` | ไม่มีแถว `send_data.id` |
| `403 province_scope_denied` | staff JWT ที่จังหวัดของแถว (snapshot `province_id` หรือ fallback join แบบ list) ไม่อยู่ใน scope |

---

## 5. ความสัมพันธ์กับตารางและ API เดิม

### ตาราง `send_data` (หลัง migration 0080)

```text
send_data
  applicant_id → applicants.id
  type_send_id → type_send.id
  send_by_sdshv, json_case, response_code, response_text
  created_at, updated_at
  ip_address, user_agent, request_url
  device, browser, browser_version, os, os_version
  type_money_category_id, type_money_name, type_money_acronym  (snapshot)
  province_id, province_name                                 (snapshot)
  affected_person_name, affected_person_cid                  (snapshot)
```

### API เดิม (ยังใช้ได้)

| Method | Path | หมายเหตุ |
|--------|------|----------|
| GET | `/v1/case_for_staff/type-sends` | รายการ master |
| GET | `/v1/case_for_staff/applicant/{id}/send-data` | ประวัติทุกช่องทาง |
| POST | `/v1/case_for_staff/applicant/{id}/send-data` | รับ `type_send_id` โดยตรง — ใช้ logic snapshot เดียวกับ mso-forward |

---

## 6. อัปเดตสถานะคำร้อง (ตามช่องทางที่ส่ง)

ระบบจะอัปเดตสถานะเป็น **「ส่งต่อข้อมูลเรียบร้อยแล้ว」** (`current_status_id = 11`) **อัตโนมัติในกรณีที่ POST `mso-forward` ด้วย `send_channel = "ministry"`**

สำหรับ `send_channel = "logbook"`: ยัง **ไม่เปลี่ยนสถานะอัตโนมัติ**

---

## 7. สรุปเส้นทาง BFF

| การทำงาน | Method | BFF path |
|----------|--------|----------|
| ตรวจส่งต่อแล้วหรือยัง | GET | `/v1/case_for_staff/applicant/{applicant_id}/mso-forward-status` |
| บันทึกการส่งต่อ | POST | `/v1/case_for_staff/applicant/{applicant_id}/mso-forward` |
| รายการ log แบบตาราง | GET | `/v1/case_for_staff/mso-forward-logs` |
| ดึง json_case ตาม id | GET | `/v1/case_for_staff/mso-forward-logs/{send_data_id}` |

---

## 8. หมายเหตุการ implement

- **ซ้ำช่องทาง:** ระบบอนุญาตบันทึก POST ซ้ำได้ แต่ UI ควร disable หลัง `sent === true` ครั้งแรก
- **แถวเก่า:** `created_at` backfill เป็น `now()` ตอน migrate — timestamp อาจไม่ตรงเวลาส่งจริง
- **Log เก่าที่ POST ก่อน deploy:** ไม่มี IP/UA/URL จนกว่าจะส่งต่อครั้งใหม่
- **Province scope:** staff JWT ไม่ส่ง `province_id` = เห็นเฉพาะจังหวัดของตนเอง; ส่งหลายค่าที่อยู่นอก scope → `403`; internal API key ไม่ส่งจังหวัด = ทั้งระบบ
- **Migration:** ต้องรัน Alembic `0080_send_data_audit_log` ก่อนใช้ฟิลด์ audit/snapshot
