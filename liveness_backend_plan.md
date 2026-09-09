# แผนดำเนินการฝั่ง Backend — เก็บ log ผล liveness

**สถานะ: ทำเสร็จแล้ว** · อัปเดต 8 กันยายน 2026
ออกแบบตารางดูที่ `liveness_erd.md` · สเปกสำหรับ frontend ดูที่ `liveness_api_spec.md`

> เอกสารนี้ถูกเขียนใหม่ทั้งฉบับหลังลงมือทำ
> ฉบับแรก (7 ก.ย. ตอนเช้า) เสนอดีไซน์ที่ **ไม่ได้ถูกใช้** — ดูข้อ 2 ว่าเปลี่ยนอะไรและทำไม

---

## 0. สรุปงานในหนึ่งย่อหน้า

บันทึกผลการยืนยันตัวตนลงตาราง `liveness_attempts` โดย **แถวเกิดตั้งแต่ตอนเปิด session
ไม่ใช่ตอนยื่นคำร้อง** จึงเห็นการสแกนที่ไม่ผ่านและคนที่เลิกกลางคันด้วย
แล้วเติม `applicant_id` เข้าไปตอนผู้ใช้กดส่งคำร้อง · **รอบนี้ยังไม่บล็อกใคร** เก็บสถิติก่อน

---

## 1. สภาพแวดล้อม

| | |
|---|---|
| repo | `~/Documents/vcare-backend/vsmartcare_backend` branch **`livenessainu_care`** |
| ฐานข้อมูล | Postgres ตัวเดียว (`case_service`) ทุก service ใช้ร่วมกัน |
| **เจ้าของ migration** | **`case-service` เท่านั้น** |
| migration head | **`0081_liveness_attempts`** (เดิม `0080_send_data_audit_log`) |
| ORM | SQLAlchemy 2.0 async (`Mapped[...]`) + Alembic |
| convention | int PK ทุกตาราง · ไม่มี soft delete · `DateTime(timezone=True)` |
| เทสต์ | `case-service/tests/` ใช้ **`unittest` (stdlib ไม่ใช่ pytest)** มีอยู่แล้ว 2 ไฟล์ |

### แก้ข้อเท็จจริงจากฉบับแรก

- branch **ไม่ใช่ `dev`** — `dev` ไม่เคยมีอะไรเกี่ยวกับ liveness เลย
- **มี test framework อยู่แล้ว** (`unittest`) ฉบับแรกเขียนว่าไม่มี
- commit `6354067` บน branch `liveness-service` **ไม่ใช่แค่ migration ที่เลขชน** —
  เป็นโค้ด **1,148 บรรทัด 24 ไฟล์** ทั้ง service (main, settings, database, citizen auth,
  payload, model ทั้งสองฝั่ง, BFF proxy) **แต่ไม่เคยถูกต่อเข้า `docker-compose`** จึงไม่เคยรันจริง

---

## 2. การตัดสินใจ Q1–Q15 (ก่อนลงมือ)

### Q1 — โครงสร้างหลัก · **ลูกผสม (C)**

**ไม่สร้าง `liveness-service` แยก** (ฉบับแรกพูดถูกข้อนี้) แต่ **เก็บโครง session-based
ของ branch เดิมไว้** คือผูกกับ `persons_id` ตั้งแต่เปิด session แล้วเติม `applicant_id` ทีหลัง

**หลักฐานที่ใช้ตัดสิน:** ข้อมูลจริง 21 แถวใน DB dev (1–2 ก.ย.) — 17 `pending` · 4 `failed` ·
**0 `completed`** และ **ไม่มีแถวไหนมี `applicant_id` เลยสักแถว** ดีไซน์ "บันทึกตอน submit
อย่างเดียว" ของฉบับแรกจะบันทึกได้ **0 จาก 21 แถว**

**ความขัดแย้งในตัวฉบับแรก 2 จุดที่พบตอนทบทวน**

1. เขียนว่า "ต้องไม่บล็อกการสร้างคำร้องไม่ว่ากรณีใด" แต่สั่งให้ insert ในทรานแซกชันเดียวกัน
   `reference_id` เป็น UNIQUE และมาจาก frontend → ค่าซ้ำทำให้ `IntegrityError` ทำทรานแซกชัน
   เป็นพิษทั้งก้อน คำร้องหายไปด้วย · `try/except` เฉย ๆ ไม่พอ **ต้องมี SAVEPOINT**
2. เป้าหมายรอบนี้คือ "เก็บสถิติไปเสนอ senior ว่าควร gate ไหม" แต่ดีไซน์เดิมทิ้งสถิติที่
   จำเป็นต่อการตัดสินใจนั้นพอดี คือคนที่สแกนไม่ผ่านแล้วเลิก

### Q2–Q15 — สรุป

| # | เรื่อง | ตัดสิน | เหตุผล |
|---|---|---|---|
| Q2 | `raw_payload` | **เก็บดิบทั้งก้อน ไม่ตัดอะไร** | เก็บ `signature`+`keyId` ไว้ verify ย้อนหลังได้ |
| Q3 | `verified_by_webhook` | **ตัดคอลัมน์ทิ้ง** | เอกสาร AINU ไม่มีคำว่า webhook เลย · คอลัมน์ที่เป็น `false` ทุกแถวไม่ให้ข้อมูลอะไร · Q2 ทำให้ verify ย้อนหลังได้อยู่แล้ว |
| Q4 | เลข migration | **เขียนทับ `0081` เดิม** | ยังไม่เคย deploy ที่ไหน · migration ที่ไม่มีวันถูกรันคือขยะที่หลอกคนอ่าน |
| Q5 | `accountSecret` | **backend จ่ายผ่าน `/session`** | ย้ายพื้นที่เสี่ยงจาก "ทุกคนบนอินเทอร์เน็ต" เหลือ "พลเมืองที่ล็อกอินแล้ว" · หมุน key ได้โดยไม่ rebuild frontend |
| Q6 | ใครสร้างแถว `skipped` | **case-service สร้างตอน submit** | เป็นข้อเดียวที่แถวถูกเขียน ณ จุดที่ผู้ใช้เลี่ยงไม่ได้ → ค่าคงที่ "ทุก applicant มีแถวเสมอ" เป็นจริงโดยไม่ต้องเชื่อ frontend |
| Q7 | `device` / `is_mobile` | เก็บทั้งคู่ → **ภายหลัง senior สั่งเอา `is_mobile` ออก** | ดูข้อ 6 |
| Q8 | ตารางเก่า 21 แถว | **DROP แล้วสร้างใหม่** | เป็นข้อมูลทดสอบล้วน ไม่มี `applicant_id` สักแถว |
| Q9 | FK `applicant_id` | **`ON DELETE SET NULL`** | ตาม pattern `ocr_results` · `CASCADE` ผิดเพราะลบคำร้องแล้วสถิติการสแกนหายด้วย |
| Q10 | `consumed_at` | **ตัดทิ้ง ใช้ `applicant_id IS NOT NULL`** | ให้ผลเท่ากัน น้อยกว่าหนึ่งคอลัมน์ · ใช้ซ้ำ → แถวใหม่ `REPLAYED` ไม่แก้แถวเดิม |
| Q11 | เทสต์ | **เขียน `unittest`** | คุมข้อกำหนดสำคัญที่สุด ("แตกฟิลด์ต้องไม่ throw") ซึ่งตรวจมือซ้ำได้ยาก |
| Q12 | จำนวน endpoint | **4 ตัว (คง `/transaction` ไว้)** | ข้อมูลจริง: 9 ใน 17 แถว `pending` มี `transaction_id` = คนที่เลิกกลางคันหลัง `onReady()` ถ้ายุบเข้า `/result` จะไม่มีรหัสไปถาม AINU |
| Q13 | `skip_reason` เข้าทางไหน | **แยก endpoint `/skip`** | `/result` = AINU ตอบ · `/skip` = เราสรุปเอง เส้นแบ่งเดียวกับ `fail_reason` vs `skip_reason` |
| Q14 | alert ขนาด payload | **`logger.warning` ในโค้ด + SQL** | SQL ที่ต้องรอคนนึกได้จะไม่ถูกรัน |
| Q15 | ขอบเขต | **backend + สเปกให้ frontend** | ดีไซน์ C เปลี่ยนสัญญากับ frontend มากกว่าฉบับแรก ต้องเขียนไว้ |

---

## 3. สิ่งที่ทำจริง

### 3.1 ตาราง (migration `0081` — เขียนทับของเดิม)

15 คอลัมน์ · รายละเอียดเต็มใน `DATADICT.md`

| | |
|---|---|
| ผูกกับ | `persons_id` NOT NULL FK `CASCADE` (เจ้าของการสแกน) |
| เติมทีหลัง | `applicant_id` nullable FK **`SET NULL`** — `IS NOT NULL` = ถูกใช้แล้ว |
| `reference_id` | `String(64)` UNIQUE — **backend สร้าง `uuid4()`** |
| `status` | `pending` / `completed` / `failed` / `skipped` / `pending_DOPA` |
| `raw_payload` | `JSON` (ไม่ใช่ `JSONB` — `JSONB` เรียง key ใหม่ เสียความเป็นดิบ) |
| Index | `reference_id` (unique) · `persons_id` · `applicant_id` |

**ไม่มี guard `has_table()` โดยตั้งใจ** — DB บางเครื่องมีตารางเก่าค้างจาก branch
`liveness-service` โดย `alembic_version` ยังเป็น `0080` guard จะข้ามการสร้างแล้ว stamp
เป็น `0081` ได้ schema เก่าโดยเงียบ แล้วไปพังตอน runtime
เจอ `relation already exists` ให้ `DROP TABLE liveness_attempts;` แล้ว upgrade ใหม่

**ตัด index composite `(applicant_id, created_at)`** ที่ ERD ข้อ 4 ระบุไว้ —
query ทั้ง 6 ตัวใน ERD ข้อ 8 ไม่มีตัวไหน filter `applicant_id` แล้วเรียงตามเวลา

### 3.2 Endpoint (`case-service/app/api/v1/liveness.py`)

ทุกตัวผ่าน `require_citizen` · attempt ของคนอื่นตอบ **404 ไม่ใช่ 403**
(ตาม `get_owned_applicant`) · แถวที่จบแล้วเขียนทับไม่ได้ (**409**)

| | |
|---|---|
| `POST /v1/liveness/session` | สร้างแถว `pending` → คืน `reference_id` + config รวม `accountSecret` |
| `POST /{ref}/transaction` | เก็บ `transaction_id` จาก `onReady()` ทันที ไม่รอผลจบ |
| `POST /{ref}/result` | รับ payload ทั้งก้อน แตกฟิลด์ เก็บดิบ |
| `POST /{ref}/skip` | รับ `skip_reason` — ค่านอก 5 ตัวที่อนุญาตตอบ **422** |

BFF เพิ่ม proxy 4 route ตาม pattern `ocr_*_proxy`

### 3.3 ผูกกับคำร้อง (`create_welfare_case()`)

`WelfareCaseCreate` เพิ่ม **`liveness_reference_id` ฟิลด์เดียว** (ฉบับแรกเสนอ 3 ฟิลด์)

ครอบด้วย **`session.begin_nested()` (SAVEPOINT)** — นี่คือสิ่งที่ทำให้คำสัญญา
"ไม่บล็อกการสร้างคำร้อง" เป็นจริง

| กรณี | ผล |
|---|---|
| reference ถูกต้อง ยังไม่ถูกใช้ | เติม `applicant_id` ลงแถวเดิม |
| ไม่ส่ง reference มา | แถวใหม่ `skipped` / **`NO_ATTEMPT`** |
| reference ถูกใช้กับคำร้องอื่นแล้ว | แถวใหม่ `skipped` / **`REPLAYED`** (ไม่แก้แถวเดิม) |
| reference ของ person อื่น | แถวใหม่ `skipped` / `NO_ATTEMPT` + log warning |

### 3.4 แตกฟิลด์จาก payload (`services/liveness_payload.py`)

- **อ่านเผื่อทั้ง `result.*` และ `result.data.*`** — เอกสาร AINU ขัดกันเอง
  (`liveness_frontend_guide.md` ข้อ 9)
- `pending_DOPA` เก็บตามเดิม (ยาว 12 พอดีคอลัมน์ 16) · ค่าที่ไม่รู้จัก → `failed` + log
- ตัดความยาวทุกค่าให้พอดีคอลัมน์ กัน `DataError`
- **warning เมื่อ payload > 8 KB** พร้อมบอกว่าเจอ key ภาพตัวไหน — ด่านเดียวที่เฝ้า
  ไม่ให้ภาพชีวมิติเข้า DB โดยไม่มีใครรู้ (PDPA ม.26)

### 3.5 ไฟล์ที่แตะ

```
case-service/alembic/versions/0081_liveness_attempts.py   เขียนทับ
case-service/app/models/liveness_attempt.py               ใหม่
case-service/app/models/__init__.py                       เพิ่ม export
case-service/app/services/liveness_payload.py             ใหม่
case-service/app/services/liveness_link.py                ใหม่
case-service/app/api/v1/liveness.py                       ใหม่
case-service/app/schemas/liveness.py                      ใหม่
case-service/app/schemas/case_welfare.py                  +1 ฟิลด์
case-service/app/api/v1/cases.py                          +1 การเรียก
case-service/app/settings.py                              +4 ค่า AINU
case-service/app/main.py                                  register router
case-service/tests/test_liveness_payload.py               ใหม่ 13 เทสต์
bff-vsmartcare/app/main.py                                +4 proxy
bff-vsmartcare/app/welfare_case_schema.py                 +1 ฟิลด์
DATABASE.md · DATADICT.md · SECURITY_ENV.example          เอกสาร
```

**commit:** `e88dbb0` → `1be3844` → `cd3bf0c` → `fbea616` → `abe7b03` → `914942c` → `af47ff3`

---

## 4. บั๊กที่เจอหลังส่งมอบ (แก้แล้ว)

**BFF ตัด `liveness_reference_id` ทิ้งเงียบ ๆ** — `bff-vsmartcare` มี `WelfareCaseCreate`
เป็นสำเนาของตัวเองแยกจาก case-service และ `create_case()` ทำ `body.model_dump()`
ก่อน forward · pydantic ตัดฟิลด์ที่ schema ไม่รู้จักทิ้งโดยไม่มี error

ผล: frontend ส่งมาถูก แต่ case-service ไม่เคยได้รับ → การสแกนที่ผ่านค้างเป็นแถว
`completed` ที่ `applicant_id` เป็น null แล้วได้แถว `NO_ATTEMPT` เพิ่มมาแทน
**เกิดซ้ำ 2 รอบในการทดสอบจริง** ก่อนจะเจอสาเหตุ

แก้ที่ `914942c` และตรวจ schema ทั้งสองฝั่งเทียบกันแล้วว่าไม่มีฟิลด์อื่นหายอีก

> **บทเรียน:** เวลาแก้ทั้ง BFF และ case-service ในเรื่องเดียวกัน ต้องทดสอบ **ผ่าน BFF**
> ไม่ใช่ยิง case-service ตรง ๆ — จุดที่พังคือช่องว่างระหว่างสองฝั่งพอดี

---

## 5. Verification ที่รันจริงแล้ว

**Migration** — `alembic upgrade` → `downgrade -1` → `upgrade` ผ่านทั้งสองทาง ·
ตรวจ FK `CASCADE`/`SET NULL` และ index ครบ

**Unit test** — 13 ตัวผ่านหมด รวม payload พังรูปแบบ 12 แบบที่ต้องไม่ throw,
การอ่านฟิลด์ที่ซ้อนใน `data`, `pending_DOPA`, การตัดความยาว, threshold 8 KB

**Endpoint (8 เคส)** — session 201 · จ่าย `accountSecret` · `transaction_id` จาก
`onReady()` ไม่ถูก payload ทับ · `raw_payload` ไม่หลุดใน response · เขียนทับแถวที่จบแล้ว 409 ·
`skip_reason` ที่ server สงวนไว้ 422 · reference ไม่มีจริง 404 · payload shape ผิด 200 ไม่พัง

**ผูกตอน submit (5 เส้นทาง)** — ผูกสำเร็จ · `REPLAYED` · `NO_ATTEMPT` ·
reference ของคนอื่นไม่ยอมผูกและไม่แตะแถวเดิม · **INSERT ล้มแล้วทรานแซกชันยังใช้ต่อได้**

**Flow จริงผ่านเบราว์เซอร์** — ได้ 1 แถว `completed` `PASS` · `applicant_id` ผูกถูก ·
signature 684 ตัวอักษร · `persons_id` ของการสแกนกับของคำร้องตรงกัน · ไม่มีแถว `NO_ATTEMPT` เกิน

---

## 6. เปลี่ยนหลังส่งมอบ — `is_mobile` (คำสั่ง senior 8 ก.ย.)

Q7 ตัดสินให้เก็บทั้ง `device` และ `is_mobile` ต่อมา senior สั่งให้เอา `is_mobile` ออก
ทำแล้วที่ `af47ff3` (ลบครบทุกจุดรวมการ forward `User-Agent` ใน BFF ที่มีไว้เพื่อค่านี้)

**สิ่งที่แลกไป:** `device` มาจาก payload จึงมีเฉพาะแถว `completed`/`failed`
**แถว `pending`/`skipped` เป็น `null` เสมอ** → สถิติ desktop เทียบ mobile ครอบคลุมเฉพาะ
คนที่สแกนจนจบ · **คนที่เลิกกลางคันดูไม่ได้ว่าใช้เครื่องอะไร** ซึ่งเป็นกลุ่มที่คำถามข้อ 6
ที่ค้างกับ AINU ("ทำไม desktop ผ่านยากกว่ามือถือ") สนใจที่สุด

---

## 7. ไม่ทำในรอบนี้

- **ไม่ gate** ทั้ง hard และ soft — เก็บสถิติก่อน
- **ไม่ทำ webhook** — เอกสาร AINU ไม่มีเรื่องนี้เลย
- **ไม่แก้ frontend** — เขียนเป็นสเปกให้แทน (`liveness_api_spec.md`)
- **ไม่แตะ `docker-compose`** — ไม่มี service ใหม่
- **ไม่แตะ branch `liveness-service`** — ปล่อยไว้ให้เจ้าของจัดการ · **ไม่ควร merge**
  เพราะดีไซน์ถูกแทนที่แล้ว

---

## 8. ความเสี่ยงที่รับไว้แล้ว

| เรื่อง | สถานะ |
|---|---|
| **ผลปลอมได้จาก DevTools** | ยังปลอมได้ · ดีไซน์นี้กันได้แค่ "ข้ามแบบเงียบ ๆ" ผ่านแถว `NO_ATTEMPT` ที่เซิร์ฟเวอร์เขียนเอง · แก้จริงต้อง verify `signature` |
| **payload ดิบทั้งก้อน** | ถ้า AINU เริ่มส่งภาพ ข้อมูลชีวมิติเข้า DB ทันที · มีแค่ warning 8 KB ซึ่งเป็น "รู้ทีหลัง" |
| **frontend redact หรือไม่** | **ยังไม่มีใครตัดสิน** — `redactLivenessPayload()` ฝั่ง frontend ตัดภาพอยู่ การตัดไม่กระทบ `signature`/`keyId` เลย |
| **503 ตอน `/session`** | เกิดก่อนมี `reference_id` จึงไม่มีแถวให้ยิง `/skip` → ได้ `NO_ATTEMPT` แยกไม่ออกจากคนที่ไม่ได้สแกน · แก้ได้ ~10 บรรทัดถ้าต้องการ |

---

## 9. ที่ยังค้าง

1. **frontend แนบ `liveness_reference_id`** — โค้ดมีแล้ว ทำงานแล้วหลังแก้บั๊ก BFF
2. **`AUTH_ERROR` น่าจะดักไม่ได้** — `frame.ts:113` ใช้ regex `token|auth` แต่ traffic จริง
   ที่เห็นใน DevTools ชื่อ **`handshake`** ซึ่งไม่มีทั้งสองคำ **ยังไม่ได้ยืนยัน path เต็ม**
   (`/ekyc` ยืนยันแล้วว่าถูก และ 403 บน `/ekyc` คือปกติจริง)
3. **ถาม AINU เรื่อง verify `signature`** — ข้อมูลพร้อม มี `signature`+`keyId`+`metadata`
   ครบ **เฉพาะแถว `completed`** ซึ่งคือสิ่งที่ต้องการพอดี
4. **credential production + IP allowlist** — ตอนนี้รัน UAT (`uat.ainu.tech`, `appId: localhost`)
