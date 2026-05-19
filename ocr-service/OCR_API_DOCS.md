# OCR Service — API Documentation สำหรับ Frontend

> **Base URL:** `http://localhost:8004` (dev) / `http://ocr-service:8000` (docker)  
> **Service:** `ocr-service`  
> **Engine:** Gemini 2.5 Flash  
> **Protocol:** รับ `multipart/form-data` → ส่ง base64 ให้ Gemini ภายใน  

---

## 🔐 Authentication

ส่ง header `Authorization: Bearer <token>` ทุก request

| สภาพแวดล้อม | วิธี |
|---|---|
| **Dev** (ไม่ตั้ง `OCR_API_KEY`) | ไม่ต้องส่ง token — เรียกได้เลย |
| **Production** (ตั้ง `OCR_API_KEY`) | ส่ง `Authorization: Bearer <OCR_API_KEY>` |

```http
Authorization: Bearer your-ocr-api-key
```

---

## 🛡️ Validation ทั้งหมด

| ลำดับ | จุดตรวจ | รายละเอียด | Error |
|---|---|---|---|
| 1 | **Auth** | `OCR_API_KEY` ถูกตั้ง → ต้องส่ง `Bearer` token ตรงกัน | `401` |
| 2 | **Required Fields** | `target_name` + `file` ต้องส่งมา (FastAPI auto) | `422` |
| 3 | **File Type** | content-type ต้องเป็น `image/jpeg`, `image/png`, `image/webp` | `415` |
| 4 | **File Empty** | `file.read()` ต้องไม่เป็น bytes เปล่า | `400` |
| 5 | **File Size** | ≤ `max_upload_bytes` (default 10 MB) | `413` |
| 6 | **Blur Check** | คำนวณ Laplacian variance — ถ้าต่ำกว่า `BLUR_THRESHOLD` → `blurry` | ใน response |
| 7 | **No Text Check** | Gemini คืน markdown ว่าง → `no_text` | ใน response |
| 8 | **Name Match** | Fuzzy match ชื่อ OCR vs `target_name` + ตรวจคำนำหน้าชื่อ | ใน response |

---

## 📤 `POST /v1/ocr/bank-book`

OCR สมุดบัญชีธนาคาร — อัปโหลดรูป แล้วได้ข้อมูลบัญชี + คะแนนเทียบชื่อกลับมา

### Request (`multipart/form-data`)

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | `File` | ✅ | รูปสมุดบัญชี (JPEG / PNG / WebP) สูงสุด 10 MB |
| `target_name` | `string` | ✅ | ชื่อ-นามสกุลที่ต้องการเทียบ (เช่น `"นาย ภูริพัฒน ปัญญา"`) |
| `applicant_id` | `int` | ❌ | ID ของ applicant (ใบคำร้อง) — ส่งทีหลังผ่าน `PATCH` ได้ |

### cURL ตัวอย่าง

```bash
curl -X POST http://localhost:8004/v1/ocr/bank-book \
  -H "Authorization: Bearer your-ocr-api-key" \
  -F "applicant_id=42" \
  -F "target_name=นาย ภูริพัฒน ปัญญา" \
  -F "file=@bank_book.jpg"
```

### TypeScript / Axios ตัวอย่าง

```ts
const form = new FormData();
form.append("applicant_id", "42");     // ID ของใบคำร้อง
form.append("file", file);              // File object จาก <input type="file">
form.append("target_name", "นาย ภูริพัฒน ปัญญา");

const { data } = await axios.post<OcrResponse>(
  "http://localhost:8004/v1/ocr/bank-book",
  form,
  {
    headers: {
      "Authorization": `Bearer ${apiKey}`,
      "Content-Type": "multipart/form-data",
    },
  }
);
```

---

## 📥 Response

### Success `200`

```json
{
  "markdown": "## สมุดบัญชีธนาคาร\n\n**ธนาคารไทยพาณิชย์**\n...",
  "bank_info": {
    "account_number": "431-013603-2",
    "account_name": "นาย ภูริพัฒน ปัญญา",
    "bank_name": "ธนาคารไทยพาณิชย์",
    "match_status": "match",
    "fuzzy_score": 95.23
  },
  "target_name_checked": "นาย ภูริพัฒน ปัญญา",
  "pre_file": "a1b2c3d4e5f6.jpg"
}
```

### Response Fields

| Field | Type | Description |
|---|---|---|
| `markdown` | `string` | ข้อความทั้งหมดจาก OCR ในรูปแบบ Markdown |
| `bank_info.account_number` | `string \| null` | หมายเลขบัญชีที่อ่านได้ |
| `bank_info.account_name` | `string \| null` | ชื่อเจ้าของบัญชีที่อ่านได้ |
| `bank_info.bank_name` | `string \| null` | ชื่อธนาคารที่อ่านได้ |
| `bank_info.match_status` | `MatchStatus` | สถานะการจับคู่ (ดูตารางด้านล่าง) |
| `bank_info.fuzzy_score` | `float` | คะแนนความคล้ายระหว่างชื่อ OCR กับ target_name (0–100) |
| `target_name_checked` | `string` | ชื่อเป้าหมายที่ใช้เทียบ (echo กลับ) |
| `pre_file` | `string` | UUID ของไฟล์ต้นฉบับ (`uuid.jpg`) |

---

## 🏷️ Match Status

| Status | ความหมาย | Fuzzy Score |
|---|---|---|
| `match` | ✅ ตรง — ชื่อคล้าย ≥ 90% และคำนำหน้าชื่อเข้ากันได้ | ≥ 90 |
| `review` | ⚠️ ต้องตรวจสอบด้วยคน — ชื่อคล้าย 75–89% | 75–89 |
| `mismatch` | ❌ ไม่ตรง — ชื่อคล้าย < 75% หรือคำนำหน้าขัดแย้ง (ชาย/หญิง) | < 75 |
| `blurry` | 🔍 ภาพเบลอเกิน threshold — ต้องถ่ายใหม่ | — |
| `no_text` | 📄 ตรวจไม่พบข้อความในรูป | — |

### กฎการตัดสิน Match Status

```
1. ภาพเบลอเกิน BLUR_THRESHOLD   → blurry
2. ไม่พบข้อความในรูป              → no_text
3. คำนำหน้าขัดแย้ง (นาย vs นาง)   → mismatch
4. Fuzzy ≥ 90%                   → match
5. Fuzzy 75–89%                  → review
6. Fuzzy < 75%                   → mismatch
```

---

## ⚠️ Error Responses

| Status | Detail | สาเหตุ |
|---|---|---|
| `401` | `ต้องส่ง header Authorization: Bearer <token>` | ไม่ได้ส่ง token (production) |
| `401` | `token ไม่ถูกต้อง` | token ไม่ตรงกับ `OCR_API_KEY` |
| `400` | `ไฟล์ว่างเปล่า` | อัปโหลดไฟล์เปล่า |
| `413` | `ขนาดไฟล์ต้องไม่เกิน 10 MB` | ไฟล์ใหญ่เกิน |
| `415` | `รองรับเฉพาะ image/jpeg, image/png, image/webp` | ไฟล์ไม่ใช่รูป |
| `422` | Validation error | `applicant_id`, `target_name` หรือ `file` ไม่ถูกส่งมา |

---

## � `PATCH /v1/ocr/results/{ocr_result_id}/link`

ผูกผล OCR กับ `applicant_id` ทีหลัง — ใช้หลังจากสร้างใบคำร้องสำเร็จแล้ว

### Request (`application/json`)

```json
{
  "applicant_id": 42
}
```

### Response `200`

```json
{
  "id": 5,
  "applicant_id": 42,
  ...
}
```

### cURL

```bash
curl -X PATCH http://localhost:8004/v1/ocr/results/5/link \
  -H "Authorization: Bearer your-ocr-api-key" \
  -H "Content-Type: application/json" \
  -d '{"applicant_id": 42}'
```

---

## �📥 `GET /v1/ocr/results/{applicant_id}`

ดึงผล OCR ทั้งหมดของใบคำร้อง — คืนค่าตาม `applicant_id` เรียงจากล่าสุดขึ้นก่อน

### Query Parameters

| Field | Type | Default | Description |
|---|---|---|---|
| `limit` | `int` | `10` | จำนวนผลลัพธ์สูงสุด (1–50) |

### Response `200`

```json
{
  "applicant_id": 42,
  "results": [
    {
      "id": 5,
      "applicant_id": 42,
      "target_name_checked": "นาย ภูริพัฒน ปัญญา",
      "pre_file": "a1b2c3d4e5f6.jpg",
      "markdown": "## สมุดบัญชีธนาคาร\n\n...",
      "account_number": "431-013603-2",
      "account_name": "นาย ภูริพัฒน ปัญญา",
      "bank_name": "ธนาคารไทยพาณิชย์",
      "match_status": "match",
      "fuzzy_score": 95.23,
      "created_at": "2026-05-19T10:30:00Z",
      "updated_at": "2026-05-19T10:30:00Z"
    }
  ],
  "count": 1
}
```

### cURL ตัวอย่าง

```bash
curl http://localhost:8004/v1/ocr/results/42?limit=5 \
  -H "Authorization: Bearer your-ocr-api-key"
```

---

## 🗄️ การเก็บข้อมูล (Persistence)

ทุกครั้งที่เรียก `POST /v1/ocr/bank-book` ผล OCR จะถูกบันทึกลง SQLite (`ocr_results.db`) โดยอัตโนมัติ พร้อม `applicant_id` ที่อ้างอิงไปยัง `case-service.applicant.id`

| ข้อ | รายละเอียด |
|---|---|
| 🔗 **FK Concept** | `ocr_results.applicant_id` → `case_service.applicant.id` (logic FK — database เดียวกัน) |
| 📦 **Storage** | PostgreSQL database `case_service` — แชร์ database เดียวกับ case-service |
| 🔍 **Query** | `GET /v1/ocr/results/{applicant_id}` ดึงผลย้อนหลังได้ |
| 🗑️ **Cleanup** | เมื่อลบ applicant ใน case-service → ควรลบ OCR results ตาม (manual หรือผ่าน API ในอนาคต) |

---

## 🎨 UI Flow แนะนำ

```
1. ผู้ใช้ถ่ายรูป / เลือกรูปสมุดบัญชี
       ↓
2. เรียก POST /v1/ocr/bank-book
       ↓
3. ได้ response กลับมา
       ↓
┌─ match_status = "match" ──────► แสดงข้อมูลบัญชีอัตโนมัติ (สีเขียว)
│
├─ match_status = "review" ─────► แสดงข้อมูล + แจ้งเตือน "กรุณาตรวจสอบ" (สีเหลือง)
│
├─ match_status = "mismatch" ───► แจ้งว่าไม่ตรง ให้ผู้ใช้แก้ไขเอง (สีแดง)
│
├─ match_status = "blurry" ─────► แจ้งให้ถ่ายรูปใหม่ (ภาพไม่ชัด)
│
└─ match_status = "no_text" ────► แจ้งว่าไม่พบข้อความในรูป
```

---

## 🐳 Docker Compose

```yaml
ocr-service:
  image: service-ocr-service:latest
  build:
    context: ./ocr-service
  env_file:
    - ./ocr-service/.env
  ports:
    - "8004:8000"
```

ภายใน compose network เรียกผ่าน `http://ocr-service:8000`

---

## ⚙️ Environment Variables (`.env`)

```env
# Required — Gemini API Key จาก Google AI Studio
GEMINI_API_KEY=AIza...

# Optional — ค่า default ด้านล่าง
GEMINI_MODEL=gemini-2.5-flash          # โมเดล Gemini ที่ใช้
BLUR_THRESHOLD=100                      # ค่า Laplacian variance ขั้นต่ำ
FUZZY_MATCH_THRESHOLD=90.0              # คะแนนขั้นต่ำสำหรับ match
FUZZY_REVIEW_THRESHOLD=75.0             # คะแนนขั้นต่ำสำหรับ review
OCR_API_KEY=                            # เว้นว่าง = dev mode (ไม่ตรวจ auth)
```

---

## 🔧 Pipeline ภายใน (สรุป)

```
Frontend (multipart)         OCR Service                  Gemini API
─────────────────────       ──────────────              ───────────
  file + target_name   →    1. validate auth/type/size
                             2. blur detection (cv2)
                             3. file → base64          →  inline_data
                             4.                          ←  JSON {markdown, bank_info}
                             5. fuzzy match ชื่อ
                             6. ตัดสิน match_status
                             7. ตอบ OcrResponse       ←
```

---

## 📝 TypeScript Types

```ts
type MatchStatus = "match" | "review" | "mismatch" | "blurry" | "no_text";

interface BankInfo {
  account_number: string | null;
  account_name: string | null;
  bank_name: string | null;
  match_status: MatchStatus;
  fuzzy_score: number;
}

interface OcrResponse {
  markdown: string;
  bank_info: BankInfo | null;
  target_name_checked: string;
  pre_file: string;
}
```
