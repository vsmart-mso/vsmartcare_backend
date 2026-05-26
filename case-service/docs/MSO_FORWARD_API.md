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

### case-service

```http
POST /v1/case_for_staff/applicant/{applicant_id}/mso-forward
```

### Request body

| ฟิลด์ | ชนิด | บังคับ | คำอธิบาย |
|--------|------|--------|----------|
| `send_channel` | `"ministry"` \| `"logbook"` | ใช่ | แยกช่องทางส่งต่อ |
| `send_by_sdshv` | string | ไม่ | รหัส/ชื่อผู้บันทึก (SDSHV) |
| `json_case` | object | ไม่ | payload ที่ส่งออก (audit) |
| `response_code` | string | ไม่ | รหัสตอบกลับจาก API ปลายทาง |
| `response_text` | string | ไม่ | ข้อความตอบกลับ / error |

### ตัวอย่าง — ส่งต่อ MSO logbook สำเร็จ

```json
{
  "send_channel": "logbook",
  "send_by_sdshv": "user-12345",
  "json_case": { "case_number": "case-202605-000001" },
  "response_code": "200",
  "response_text": "OK"
}
```

### ตัวอย่าง — ส่งต่อเข้าหระทรวง

```json
{
  "send_channel": "ministry",
  "send_by_sdshv": "user-12345",
  "response_code": "201"
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
  "response_text": "OK"
}
```

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

แนะนำ flow:

1. โหลดหน้าเคส → `GET mso-forward-status`
2. ผู้ใช้กดส่งต่อ → เรียก API ภายนอก (กระทรวง / logbook)
3. ถ้าปลายทางสำเร็จ → `POST mso-forward` ด้วย `send_channel` ที่ตรงกับปุ่ม
4. เรียก `GET mso-forward-status` อีกครั้ง (หรืออัปเดต state จาก `sent: true`)

---

## 3. ความสัมพันธ์กับตารางและ API เดิม

### ตาราง

```text
type_send (master)
  id=1  ส่งต่อเข้าหระทรวง
  id=2  ส่งต่อ mso logbook

send_data
  applicant_id → applicants.id
  type_send_id → type_send.id
  send_by_sdshv, json_case, response_code, response_text
```

### API เดิม (ยังใช้ได้)

| Method | Path | หมายเหตุ |
|--------|------|----------|
| GET | `/v1/case_for_staff/type-sends` | รายการ master |
| GET | `/v1/case_for_staff/applicant/{id}/send-data` | ประวัติทุกช่องทาง |
| POST | `/v1/case_for_staff/applicant/{id}/send-data` | รับ `type_send_id` โดยตรง (ไม่มีคีย์ `send_channel`) |

เส้น **mso-forward** / **mso-forward-status** เป็นชุดที่ออกแบบให้ระบบภายนอกใช้ง่าย — ผลลัพธ์ยังอยู่ใน `send_data` เดิม

### more_mso (ข้อมูล MSO เพิ่มเติม 1:1 case_handling)

ไม่เกี่ยวกับการบันทึกว่า “ส่งต่อแล้ว” — ใช้คนละจุดประสงค์:

| Method | Path |
|--------|------|
| GET/PUT | `/v1/case_for_staff/applicant/{id}/more-mso` |

---

## 4. อัปเดตสถานะคำร้อง (ตามช่องทางที่ส่ง)

ระบบจะอัปเดตสถานะเป็น **「ส่งต่อข้อมูลเรียบร้อยแล้ว」** (`current_status_id = 11`) **อัตโนมัติในกรณีที่ POST `mso-forward` ด้วย `send_channel = "ministry"`**

สำหรับ `send_channel = "logbook"`: ยัง **ไม่เปลี่ยนสถานะอัตโนมัติ** (ถ้าต้องการให้เปลี่ยนสถานะ ต้องเรียก API `welfare-request-status` แยกต่างหาก)

API สำหรับอัปเดตสถานะแยก (เฉพาะกรณีที่ต้องการ):

```http
POST /v1/case_for_staff/welfare-request-status
```

```json
{
  "applicant_id": 1001,
  "current_status_id": 11,
  "update_by_sdshv": "user-12345",
  "remarks": "ส่งต่อ MSO logbook สำเร็จ"
}
```

(ผ่าน BFF: `POST /api-vsmartcare/v1/case_for_staff/welfare-request-status`)

---

## 5. สรุปเส้นทาง BFF

| การทำงาน | Method | BFF path |
|----------|--------|----------|
| ตรวจส่งต่อแล้วหรือยัง | GET | `/v1/case_for_staff/applicant/{applicant_id}/mso-forward-status` |
| บันทึกการส่งต่อ | POST | `/v1/case_for_staff/applicant/{applicant_id}/mso-forward` |

---

## 6. หมายเหตุการ implement

- **ซ้ำช่องทาง:** ระบบอนุญาตบันทึก POST ซ้ำได้ (หลายแถว `send_data` ต่อ `type_send_id`) แต่ UI ควร disable หลัง `sent === true` ครั้งแรก
- **ไม่มี `created_at` ใน `send_data`:** ใช้ `latest_send_data_id` แล้วไปดูรายละเอียดจาก `GET …/send-data` ถ้าต้องการประวัติเต็ม
- **Migration สถานะ 11:** ต้องรัน Alembic `0048_current_status_id_11` ก่อนใช้ `current_status_id = 11`
