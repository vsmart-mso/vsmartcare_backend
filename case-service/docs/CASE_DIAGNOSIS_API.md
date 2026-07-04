# คำวินิจฉัยหลายรายการ (Multi-user Diagnosis) — หน้า 11 รับเรื่อง

เอกสารสำหรับทีมที่พัฒนาระบบภายนอก (VSmart/vCare) และทีมดูแล case-service เพื่อทำความเข้าใจ
business rule, โครงสร้างข้อมูล, และ API ของฟีเจอร์ "คำวินิจฉัยของเจ้าหน้าที่ผู้วินิจฉัยในการช่วยเหลือ"
ที่รองรับการบันทึกได้หลายรายการต่อเคส (1 รายการต่อเจ้าหน้าที่ 1 คน)

อ้างอิงตาราง `case_diagnosis` และ `case_diagnosis_edit_history` — migration `0070_case_diagnosis`

---

## 1. ที่มา — Business Rules (BR-DIAG-01..06)

**หลักการ**: หน้า "รับเรื่อง" ต้องรองรับคำวินิจฉัยได้มากกว่า 1 รายการ โดยแต่ละรายการผูกกับเจ้าหน้าที่
ผู้บันทึกคนนั้น ๆ เจ้าหน้าที่คนอื่นที่มีสิทธิ์เข้าถึงเคสเดียวกันดูคำวินิจฉัยของคนอื่นได้ แต่แก้ไขได้เฉพาะของตัวเอง

**ตัวอย่าง**: เจ้าหน้าที่ A บันทึกคำวินิจฉัยครั้งที่ 1 → เจ้าหน้าที่ B เข้ามาทีหลังเห็นของ A แบบอ่านอย่างเดียว
และเพิ่มคำวินิจฉัยของตัวเองได้ (ครั้งที่ 2) → ถ้า A กลับมาอีกครั้งจะเห็นของ B แบบอ่านอย่างเดียวเช่นกัน
แก้ไขได้แค่ของตัวเอง

| Rule | รายละเอียด |
|------|------------|
| BR-DIAG-01 | แสดงคำวินิจฉัยทุก user ในเคสเดียวกัน เรียงตามวันเวลาบันทึก/แก้ไขล่าสุด |
| BR-DIAG-02 | เจ้าหน้าที่ที่มีสิทธิ์เข้าเคส เพิ่มคำวินิจฉัยของตนเองได้ |
| BR-DIAG-03 | บันทึกเจ้าของคำวินิจฉัย: User ID, ชื่อ, ตำแหน่ง/บทบาท, หน่วยงาน, วันเวลา, Case ID |
| BR-DIAG-04 | แก้ไขได้เฉพาะคำวินิจฉัยของตนเอง — ของคนอื่นแสดงเป็น read-only ไม่มีปุ่มแก้ไข |
| BR-DIAG-05 | ป้องกันการแก้ไขคำวินิจฉัยของผู้อื่นทั้ง frontend และ **backend** แม้เรียก API ตรง |
| BR-DIAG-06 | เก็บประวัติการแก้ไข: ข้อความก่อน/หลัง, ผู้แก้ไข, วันเวลา, เหตุผล (ถ้ามี) |

---

## 2. โครงสร้างข้อมูล

Migration: [`0070_case_diagnosis.py`](../alembic/versions/0070_case_diagnosis.py)
Models: [`app/models/diagnosis.py`](../app/models/diagnosis.py)

### ตาราง `case_diagnosis`

คำวินิจฉัย 1 แถวต่อ 1 เจ้าหน้าที่ต่อ 1 เคส (`UNIQUE(applicant_id, owner_user_id)`)

| คอลัมน์ | ชนิด | คำอธิบาย |
|---------|------|----------|
| `id` | int, PK | |
| `applicant_id` | int, FK → `applicants.id` ON DELETE CASCADE | ผูกกับเคสตรง ๆ (ไม่ผ่าน `case_handling`) เพื่อให้เพิ่มคำวินิจฉัยได้ก่อนที่ `case_handling` จะถูกสร้าง |
| `diagnosis_text` | text, NOT NULL | เนื้อหาคำวินิจฉัย |
| `owner_user_id` | int, NOT NULL, indexed | Django user id ฝั่ง VSmart — กุญแจของ ownership. **`0` สงวนไว้สำหรับแถวที่ migrate จาก `comment` เดิม (ไม่ทราบเจ้าของ) → แก้ไขไม่ได้ถาวร** |
| `owner_sdshv` | string(255), nullable | เลขที่ใบอนุญาต/รหัส SDSHV ของเจ้าของ (snapshot) |
| `owner_name` | string(255), nullable | ชื่อ-นามสกุลเจ้าของ (snapshot) |
| `owner_position` | string(255), nullable | ตำแหน่ง (snapshot) |
| `owner_organization` | string(255), nullable | หน่วยงาน (snapshot) |
| `created_at` / `updated_at` | datetime (UTC naive), server_default `now()` | ดูหมายเหตุ timezone ด้านล่าง |

> เก็บชื่อ/ตำแหน่ง/หน่วยงานเป็น **snapshot** ไม่ใช่ FK ไปยังระบบเจ้าหน้าที่ เพราะข้อมูลเจ้าหน้าที่อยู่คนละระบบ (VSmart)
> และถ้าเจ้าหน้าที่ย้ายตำแหน่งภายหลัง ประวัติของคำวินิจฉัยเดิมต้องไม่เปลี่ยนตาม

### ตาราง `case_diagnosis_edit_history`

Insert 1 แถวทุกครั้งที่ `diagnosis_text` เปลี่ยนจริงผ่าน PATCH (ดู §4.3)

| คอลัมน์ | ชนิด | คำอธิบาย |
|---------|------|----------|
| `id` | int, PK | |
| `diagnosis_id` | int, FK → `case_diagnosis.id` ON DELETE CASCADE, indexed | |
| `old_text` / `new_text` | text, NOT NULL | ข้อความก่อน/หลังแก้ไข |
| `edit_reason` | text, nullable | เหตุผล — **ไม่บังคับกรอก** (ตาม BR-DIAG-06 "หากมีการกำหนดให้บังคับ") |
| `edited_by_user_id` | int, NOT NULL | |
| `edited_by_name` | string(255), nullable | snapshot ชื่อผู้แก้ไข ณ ขณะนั้น |
| `created_at` | datetime (UTC naive) | |

### Data migration (ตอน upgrade 0070)

ย้าย `case_regulation_choice.comment` ที่มีอยู่เดิม (ระบบ 1:1 เก่า) มาเป็นคำวินิจฉัยแถวแรกของแต่ละเคส:

```sql
INSERT INTO case_diagnosis (applicant_id, diagnosis_text, owner_user_id, owner_sdshv, created_at, updated_at)
SELECT ch.applicant_id, crc.comment, 0,
       COALESCE(NULLIF(crc.signed_by_sdshv,''), NULLIF(ch.sw_user_sdshv,'')),
       crc.created_at, crc.updated_at
FROM case_regulation_choice crc
JOIN case_handling ch ON ch.id = crc.case_handling_id
WHERE crc.comment IS NOT NULL AND btrim(crc.comment) <> '';
```

`owner_user_id = 0` ทำให้แถวเหล่านี้แสดงได้แต่แก้ไขไม่ได้ถาวร (ผ่านการเช็คใน §4.3)

---

## 3. Ownership Model

Backend **ไม่มีบริบท session ของ Django user** — case-service ถูกเรียกผ่าน internal `X-API-Key`
(`require_staff` คืน `StaffClaims(is_internal=True)`) ไม่ผ่าน JWT ต่อ user เหมือน endpoint citizen

ดังนั้น **ownership ถูกยืนยันด้วย `owner_user_id` / `actor_user_id` ที่ส่งมาใน payload** ซึ่งฝั่ง Django
เติมจาก `request.user.id` (ยืนยันตัวตนแล้วในชั้น Django ก่อนหน้านั้น) — โมเดล trust นี้เหมือนกับฟิลด์
`sw_user_sdshv` / `edit_by_sdshv` ที่ใช้อยู่แล้วในระบบเดิม

การบังคับสิทธิ์เกิดที่ backend จริง (ไม่ใช่แค่ UI ซ่อนปุ่ม): PATCH เทียบ `actor_user_id` กับ
`row.owner_user_id` ตรง ๆ ก่อนแก้ไขทุกครั้ง (§4.3) — เรียก API ตรงข้าม Django ก็ถูกปฏิเสธเหมือนกัน

---

## 4. API Endpoints

Base path: `/v1/intake` (case-service) — ผ่าน BFF ที่ `/api-vsmartcare/v1/intake` (`X-API-Key` header)

### 4.1 GET รายการคำวินิจฉัยทั้งหมดของเคส

```http
GET /v1/intake/cases/{applicant_id}/diagnoses?actor_user_id={user_id}
```

`actor_user_id` เป็น query param ไม่บังคับ — ใส่มาเพื่อให้ backend คำนวณ `is_owner` ให้ ถ้าไม่ใส่
ทุกแถวจะได้ `is_owner: false`

**Response `200 OK`** (เรียง `updated_at DESC`):

```json
[
  {
    "id": 12,
    "applicant_id": 1001,
    "diagnosis_text": "เห็นควรให้ความช่วยเหลือ เนื่องจาก...",
    "owner_user_id": 1784,
    "owner_sdshv": "1775",
    "owner_name": "นาย ทดสอบ ระบบ",
    "owner_position": "นักสังคมสงเคราะห์",
    "owner_organization": "สำนักงานพัฒนาสังคมและความมั่นคงของมนุษย์จังหวัดพิษณุโลก",
    "created_at": "2026-07-02T19:18:40.255226",
    "updated_at": "2026-07-02T19:50:12.835853",
    "is_owner": true,
    "edit_count": 2
  }
]
```

| ฟิลด์ | ความหมาย |
|-------|----------|
| `is_owner` | `true` เมื่อ `actor_user_id` ตรงกับ `owner_user_id` (ใช้ตัดสินใจแสดงปุ่มแก้ไข/read-only) |
| `edit_count` | จำนวนแถวใน `case_diagnosis_edit_history` ของรายการนี้ |
| `owner_user_id = 0` | แถว migrate จากระบบเดิม — `is_owner` จะเป็น `false` เสมอไม่ว่า `actor_user_id` จะเป็นอะไร |

### 4.2 POST เพิ่มคำวินิจฉัยของตนเอง

```http
POST /v1/intake/cases/{applicant_id}/diagnoses
Content-Type: application/json
```

```json
{
  "diagnosis_text": "เห็นควรให้ความช่วยเหลือ 3,000 บาท",
  "owner_user_id": 1784,
  "owner_sdshv": "1775",
  "owner_name": "นาย ทดสอบ ระบบ",
  "owner_position": "นักสังคมสงเคราะห์",
  "owner_organization": "สำนักงานพัฒนาสังคมและความมั่นคงของมนุษย์จังหวัดพิษณุโลก"
}
```

`owner_user_id` บังคับและต้อง `> 0` (ป้องกันไม่ให้ใครส่ง `0` มาทับแถว legacy)

**Response `201 Created`** — รูปแบบเดียวกับ §4.1 (แถวเดียว)

**Errors**

| HTTP | `detail` | สาเหตุ |
|------|----------|--------|
| 404 | `applicant_not_found` | ไม่มี `applicant_id` นี้ |
| 409 | `diagnosis_already_exists` | user นี้เคยบันทึกคำวินิจฉัยของเคสนี้แล้ว — ให้เปลี่ยนไปเรียก PATCH แทน (รวมถึงกรณี 2 แท็บกด POST พร้อมกันชน unique constraint — จับด้วย `IntegrityError` แล้วแปลงเป็น 409 เดียวกัน) |
| 422 | validation error | ขาด field บังคับ หรือ `owner_user_id <= 0` |

### 4.3 PATCH แก้ไขคำวินิจฉัยของตนเอง

```http
PATCH /v1/intake/cases/{applicant_id}/diagnoses/{diagnosis_id}
Content-Type: application/json
```

```json
{
  "diagnosis_text": "เห็นควรให้ความช่วยเหลือ 2,000 บาท",
  "actor_user_id": 1784,
  "actor_name": "นาย ทดสอบ ระบบ",
  "edit_reason": "ปรับวงเงินตามระเบียบ",
  "owner_position": "นักสังคมสงเคราะห์",
  "owner_organization": "สำนักงานพัฒนาสังคมและความมั่นคงของมนุษย์จังหวัดพิษณุโลก"
}
```

**Logic การประมวลผล** (BR-DIAG-04, 05, 06):

1. หา `case_diagnosis` ด้วย `id` + `applicant_id` — ไม่พบ → `404 diagnosis_not_found`
2. **เช็ค ownership**: `row.owner_user_id <= 0 OR row.owner_user_id != body.actor_user_id` → `403 not_diagnosis_owner`
   (ครอบคลุมทั้งแก้ของคนอื่น และแก้แถว legacy ที่ `owner_user_id = 0`)
3. เทียบ `diagnosis_text` ใหม่กับของเดิม — **ถ้าไม่เปลี่ยน จะไม่สร้าง history แถวใหม่และ `edit_reason` ที่ส่งมาจะถูกทิ้ง** (ไม่บันทึกที่ไหนเลย)
4. ถ้าเปลี่ยนจริง → insert `case_diagnosis_edit_history` (`old_text`/`new_text`/`edit_reason`/ผู้แก้) แล้วอัปเดต `diagnosis_text`, `updated_at`
5. `owner_position` / `owner_organization` อัปเดตแบบ optional (ส่งมาก็อัปเดต snapshot ไม่ส่งมาก็คงค่าเดิม)

**Response `200 OK`** — รูปแบบเดียวกับ §4.1

**Errors**

| HTTP | `detail` | สาเหตุ |
|------|----------|--------|
| 404 | `diagnosis_not_found` | ไม่พบ diagnosis id นี้ในเคสนี้ |
| 403 | `not_diagnosis_owner` | ไม่ใช่เจ้าของ (รวมถึงพยายามแก้แถว legacy `owner_user_id=0`) |

### 4.4 GET ประวัติการแก้ไข

```http
GET /v1/intake/cases/{applicant_id}/diagnoses/{diagnosis_id}/history
```

**Response `200 OK`** (เรียงใหม่สุดก่อน):

```json
[
  {
    "id": 3,
    "diagnosis_id": 12,
    "old_text": "เห็นควรให้ความช่วยเหลือ 3,000 บาท",
    "new_text": "เห็นควรให้ความช่วยเหลือ 2,000 บาท",
    "edit_reason": "ปรับวงเงินตามระเบียบ",
    "edited_by_user_id": 1784,
    "edited_by_name": "นาย ทดสอบ ระบบ",
    "created_at": "2026-07-02T19:50:12.835853"
  }
]
```

---

## 5. BFF Proxy Routes

Pure passthrough (`bff-vsmartcare/app/main.py`) ไม่มีการแปลง field:

| Method | BFF Path |
|--------|----------|
| GET | `/v1/intake/cases/{applicant_id}/diagnoses?actor_user_id=` |
| POST | `/v1/intake/cases/{applicant_id}/diagnoses` |
| PATCH | `/v1/intake/cases/{applicant_id}/diagnoses/{diagnosis_id}` |
| GET | `/v1/intake/cases/{applicant_id}/diagnoses/{diagnosis_id}/history` |

Auth เหมือน endpoint intake อื่น ๆ — ต้องมี `Authorization: Bearer` หรือ `X-API-Key` ที่ตรง `bff_api_password`
(ดู `StaffRouteAuthMiddleware`, prefix `/v1/intake` อยู่ใน allowlist)

---

## 6. ความสัมพันธ์กับระบบเดิม (`case_regulation_choice.comment`)

`case_regulation_choice.comment` เป็นฟิลด์เดิม (1:1 ต่อเคส) ที่ใช้ก่อนฟีเจอร์นี้ ยังคง**อยู่และถูกเขียนต่อ**
(dual-write) จากฝั่ง Django ทุกครั้งที่ submit หน้า 11 — **ไม่ใช่ bug แต่เป็นการตัดสินใจรักษาความเข้ากันได้**

**เหตุผล**: มี consumer เดิมของ `comment` ที่ยังไม่ได้ย้ายมาอ่านจาก `case_diagnosis`:

| Consumer | อ่านจาก |
|----------|---------|
| PDF ปสค.1 (ฟังก์ชัน `_apply_intake_committee_to_vc` ฝั่ง Django) | `case_handling.regulation_choice.comment` |
| Flow บันทึกเรื่องแบบกลุ่ม (`multiple_social_worker`, รับเรื่องทีละหลายเคส) | เขียน `comment` ตรงผ่าน `POST/PATCH /v1/intake/cases/{id}` เดิม ไม่ผ่าน `/diagnoses` เลย |

---

## 7. ข้อจำกัดที่รับรู้แล้ว (Business Decision — ไม่ใช่ Bug)

รายการนี้เป็นขอบเขตที่ตัดสินใจไว้ตอนออกแบบรอบแรก ไม่ใช่สิ่งที่ตกหล่นโดยไม่ได้ตั้งใจ

1. **PDF ปสค.1 แสดงความเห็นของ "ผู้ submit ฟอร์มหน้า 11 ล่าสุด" เพียงคนเดียว** ไม่ได้รวมคำวินิจฉัยของ
   เจ้าหน้าที่ทุกคนที่บันทึกไว้ในเคสนั้น เพราะ PDF ยังอ่านจาก `case_regulation_choice.comment`
   (dual-write ค่าเดียว) ไม่ได้อ่านจาก `case_diagnosis` ทั้งชุด
   → ถ้าต้องการให้ ปสค.1 แสดงหลายความเห็น ต้องตัดสินใจ **format การแสดงผลกับฝ่าย business ก่อน**
   (แสดงทุกคน / แสดงเฉพาะคนเซ็นเอกสาร / อื่น ๆ) แล้วจึงแก้ทั้ง endpoint และ template

2. **Flow รับเรื่องแบบกลุ่ม (`multiple_social_worker`)** ยังไม่ได้ปรับให้ใช้ระบบคำวินิจฉัยหลายรายการ
   ยังคงเขียน `comment` แบบ 1:1 ต่อเคสเหมือนเดิม แม้ผู้ใช้จะรับเรื่องพร้อมกันหลายเคส — เจ้าหน้าที่คนอื่น
   ที่มาดูเคสที่รับผ่าน flow นี้จะยังเห็น "ความเห็นเดียว" ไม่มีการแยกเป็นรายบุคคล

3. **1 เจ้าหน้าที่บันทึกคำวินิจฉัยได้ 1 รายการต่อเคส** (ไม่ใช่หลายรายการอิสระ) — บันทึกครั้งที่ 2 ของคนเดิม
   จะกลายเป็นการ "แก้ไข" รายการเดิม (มี history) ไม่ใช่การสร้างรายการใหม่ ตรงกับตัวอย่างใน requirement
   เดิมที่อธิบายไว้ (`UNIQUE(applicant_id, owner_user_id)` ที่ตาราง)

4. **เหตุผลในการแก้ไข (`edit_reason`) ไม่บังคับกรอก** — ปล่อยว่างได้ ถ้าต้องการบังคับในอนาคตต้องเพิ่ม
   validation ทั้งฝั่ง `CaseDiagnosisUpdate` schema (backend) และฟอร์ม (frontend)

5. **แถวที่ migrate จาก `comment` เดิม (`owner_user_id = 0`) แก้ไขไม่ได้ถาวร** แม้เจ้าของตัวจริงจะกลับมา
   ใช้งานระบบใหม่ก็ตาม เพราะระบบเดิมไม่เคยเก็บ user id ไว้ให้ผูกย้อนหลังได้อย่างน่าเชื่อถือ (เก็บได้แค่
   `sw_user_sdshv`/`signed_by_sdshv` ซึ่งเป็น string อิสระ ไม่ใช่ FK ที่ตรวจสอบได้)

---

## 8. หมายเหตุ Timezone

`created_at` / `updated_at` ของทั้งสองตารางเก็บเป็น **UTC naive** (Postgres server timezone = UTC,
`server_default=func.now()` ไม่มี `timezone=True`) — **ไม่ใช่เวลาไทย** ฝั่งที่นำค่าไปแสดงผล (เช่น Django)
ต้องแปลงเป็น Asia/Bangkok เอง (+7 ชั่วโมง) ก่อนแสดงให้ผู้ใช้เห็น มิฉะนั้นเวลาจะช้ากว่าเวลาไทยจริง 7 ชั่วโมง

---

## 9. Deployment

1. รัน `alembic upgrade head` บน case-service ก่อน (ได้ migration `0070_case_diagnosis`) — Dockerfile
   ของ case-service รัน `alembic upgrade head` อัตโนมัติทุกครั้งที่ container start อยู่แล้ว
2. **แนะนำให้ backup ฐานข้อมูลก่อน** เพราะ migration มี data migration (`INSERT ... SELECT` จาก
   `case_regulation_choice.comment`) ที่เป็นการย้ายข้อมูลแบบ one-way ในทางปฏิบัติ
3. Deploy backend (case-service + BFF) ก่อน หรือ Django ก่อนก็ได้ — ระบบออกแบบให้ deploy สลับลำดับได้
   โดยไม่พัง: ถ้า Django รุ่นใหม่คุยกับ backend รุ่นเก่าที่ยังไม่มี endpoint `/diagnoses` (ตอบ 404 เปล่า ๆ)
   ฝั่ง Django จะข้ามการบันทึกคำวินิจฉัยแยกรายบุคคลไปเงียบ ๆ แล้วยังคงบันทึกผ่าน dual-write
   `comment` เดิมได้ตามปกติ ไม่บล็อกการรับเรื่อง
4. ไม่มี migration ฝั่ง Django (ไม่มี model ใหม่ในฝั่งนั้น เป็นแค่ HTTP client เพิ่ม)

---

## 10. สรุปการทดสอบที่ทำแล้ว

Smoke test ยิง HTTP ผ่าน FastAPI TestClient + SQLite in-memory (ไม่ได้อยู่ใน CI/test suite ถาวร
ของ repo — ควรย้ายเข้า `tests/` ถ้าต้องการ regression coverage) ครอบคลุม:

1. เพิ่มคำวินิจฉัยของ user A สำเร็จ (`201`)
2. POST ซ้ำโดย user เดิม → `409 diagnosis_already_exists`
3. เพิ่มคำวินิจฉัยของ user B สำเร็จ — ไม่ชนกับของ A
4. GET list มุมมอง user B เห็น 2 รายการ, `is_owner` ถูกต้องเฉพาะของตัวเอง
5. user B พยายามแก้ของ user A → `403 not_diagnosis_owner`
6. user A แก้ของตัวเอง พร้อมเหตุผล → `edit_count` เพิ่ม, บันทึก history
7. GET history คืน `old_text`/`new_text`/`edit_reason` ถูกต้อง
8. PATCH ด้วยข้อความเดิมซ้ำ (ไม่เปลี่ยน) → ไม่เพิ่ม history แถวใหม่
9. แถว legacy (`owner_user_id=0`) อ่านได้แต่แก้ไม่ได้ (`403`) แม้ actor เป็นใครก็ตาม

รวมถึงทดสอบ end-to-end จริงผ่าน docker (`case-service` + `bff-vsmartcare`) ยืนยัน route ครบ,
alembic ถึง head, และ PATCH→history ทำงานถูกต้องบนข้อมูลจริงในฐาน dev
