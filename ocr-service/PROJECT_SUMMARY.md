# OCR Service — Project Summary

> **สำหรับ:** Presentation & ClickUp  
> **Date:** 2026-05-19  
> **Service:** ocr-service (Microservice ใหม่)

---

## 📋 Overview

สร้าง **OCR Service** แยกเป็น microservice ใหม่ ใช้ **Gemini 2.5 Flash** (Google AI) อ่านรูปสมุดบัญชีธนาคาร ตรวจสอบชื่อเจ้าของบัญชีเทียบกับชื่อผู้ยื่นคำขอ และแจ้งผล match / review / mismatch

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Frontend (Vue 3)                                        │
│    Step3Problem.vue  →  POST /v1/ocr/bank-book (multipart)│
│    SubmitRequestPage  →  PATCH /v1/ocr/results/{id}/link │
└──────────────────────┬───────────────────────────────────┘
                       │ localhost:8004
┌──────────────────────▼───────────────────────────────────┐
│  ocr-service (FastAPI)  —  Port 8004                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │ /v1/ocr/bank-book          POST   OCR + persist    │  │
│  │ /v1/ocr/results/{id}/link  PATCH  link applicant   │  │
│  │ /v1/ocr/results/{app_id}   GET    query results    │  │
│  └────────────────────────────────────────────────────┘  │
│  Pipeline: blur detect → resize → base64 → Gemini →     │
│            fuzzy match → match_status → persist          │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│  PostgreSQL (shared)     Database: case_service           │
│  ├─ applicants          ← case-service                   │
│  ├─ persons             ← case-service                   │
│  └─ ocr_results         ← ocr-service  [NEW TABLE]       │
│       └─ applicant_id ── FK → applicants.id              │
└──────────────────────────────────────────────────────────┘
```

---

## 📁 ไฟล์ทั้งหมด

### ✨ ocr-service/ (ใหม่)

```
ocr-service/
├── Dockerfile
├── requirements.txt          ← google-genai, asyncpg
├── .env                      ← GEMINI_API_KEY, thresholds
├── OCR_API_DOCS.md           ← เอกสารสำหรับหน้าบ้าน
└── app/
    ├── main.py               ← FastAPI app + CORS + logging
    ├── settings.py           ← env config (gemini, blur, fuzzy, DB)
    ├── core/
    │   └── database.py       ← async Postgres engine + session
    ├── models/
    │   └── ocr_result.py     ← ORM model (query อย่างเดียว)
    └── api/ocr/
        ├── __init__.py       ← Router (POST, PATCH, GET) + auth
        ├── schemas.py        ← Pydantic: OcrResponse, BankInfo, MatchStatus
        └── service.py        ← Gemini OCR pipeline + blur + fuzzy
```

### 🔧 case-service/ (แก้ไข)

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `app/models/ocr_result.py` | ✨ Model ต้นทาง — FK จริงไปยัง applicants.id |
| `app/models/__init__.py` | ➕ register OcrResult ใน exports |
| `alembic/versions/0034_ocr_results.py` | ✨ Migration: CREATE TABLE ocr_results |

### 🔧 bff-vsmartcare/ (แก้ไข)

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `app/settings.py` | ➕ `ocr_service_url` |

### 🔧 docker-compose.yml (แก้ไข)

| บริการ | Port |
|---|---|
| `ocr-service` | ➕ 8004:8000 — depends_on postgres |

---

## 🔌 API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/ocr/bank-book` | OCR สมุดบัญชี + เก็บผล (applicant_id optional) |
| `PATCH` | `/v1/ocr/results/{id}/link` | ผูกผล OCR กับ applicant_id ทีหลัง |
| `GET` | `/v1/ocr/results/{applicant_id}` | ดึงผล OCR ทั้งหมดของใบคำร้อง |

### `POST /v1/ocr/bank-book`

```
Request:  multipart/form-data
  file:          รูปสมุดบัญชี (JPEG/PNG/WebP, ≤ 10 MB)
  target_name:   "นาย ภูริพัฒน ปัญญา"
  applicant_id:  42 (optional)

Response: 200
{
  "markdown": "## สมุดบัญชีธนาคาร\n...",
  "bank_info": {
    "account_number": "431-013603-2",
    "account_name": "นาย ภูริพัฒน ปัญญา",
    "bank_name": "ธนาคารไทยพาณิชย์",
    "match_status": "match",
    "fuzzy_score": 95.23
  },
  "target_name_checked": "นาย ภูริพัฒน ปัญญา",
  "pre_file": "a1b2c3d4.jpg"
}
```

---

## 🏷️ Match Status

| Status | ความหมาย | Fuzzy Score | UI สี |
|---|---|---|---|
| `match` | ✅ ชื่อตรง — auto-fill ได้เลย | ≥ 90% | เขียว |
| `review` | ⚠️ ต้องตรวจสอบด้วยคน | 75–89% | เหลือง |
| `mismatch` | ❌ ชื่อไม่ตรง / คำนำหน้าขัดแย้ง | < 75% | แดง |
| `blurry` | 🔍 ภาพเบลอ — ถ่ายใหม่ | — | แดง |
| `no_text` | 📄 ไม่พบข้อความในรูป | — | แดง |

---

## 🛡️ Validation & Security

### ฝั่ง Backend (8 จุด)

| # | จุดตรวจ | Error |
|---|---|---|
| 1 | Auth: `Bearer <OCR_API_KEY>` (production only) | `401` |
| 2 | Required fields: `target_name` + `file` | `422` |
| 3 | File type: `image/jpeg`, `image/png`, `image/webp` | `415` |
| 4 | File empty | `400` |
| 5 | File size ≤ 10 MB | `413` |
| 6 | Blur detection (Laplacian variance) | ใน response |
| 7 | No text detection | ใน response |
| 8 | Name match (fuzzy + title check) | ใน response |

### ฝั่งส่งให้ Gemini

- Resize รูปก่อน → max 1600px ด้านยาว, JPEG Q=85%
- ส่งเป็น **base64** ใน JSON body (ไม่ใช่ multipart → ป้องกัน leak ใน log)
- ใช้ `google-genai` SDK ใหม่ (ไม่ใช่ deprecated `google-generativeai`)

---

## 🗄️ Database

### `ocr_results` table (ใหม่)

```sql
CREATE TABLE ocr_results (
    id               SERIAL PRIMARY KEY,
    applicant_id     INT REFERENCES applicants(id) ON DELETE SET NULL,
    target_name_checked  TEXT NOT NULL,
    pre_file         VARCHAR(255) NOT NULL,
    markdown         TEXT NOT NULL,
    account_number   VARCHAR(50),
    account_name     TEXT,
    bank_name        TEXT,
    match_status     VARCHAR(20) NOT NULL DEFAULT 'no_text',
    fuzzy_score      FLOAT NOT NULL DEFAULT 0.0,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);
```

### Migration

```
case-service/alembic/versions/0034_ocr_results.py
```

รันอัตโนมัติผ่าน `alembic upgrade head` ตอน case-service startup

---

## 🧪 Pipeline ภายใน

```
User uploads image
       ↓
1. validate (auth, type, size, empty)
       ↓
2. blur detection (cv2.Laplacian)
       ↓
3. resize (max 1600px, JPEG Q=85%)
       ↓
4. base64 encode
       ↓
5. POST to Gemini Flash (inline_data)
       ↓
6. parse JSON response
       ↓
7. fuzzy match account_name vs target_name
       ↓
8. title compatibility check (นาย/นาง)
       ↓
9. determine match_status
       ↓
10. persist to ocr_results
       ↓
11. return OcrResponse
       ↓
(หลังสร้าง case)
12. PATCH /link ← bind applicant_id
```

---

## 🔑 Environment Variables (`.env`)

```env
GEMINI_API_KEY=AIza...            # Required
GEMINI_MODEL=gemini-2.5-flash     # default
BLUR_THRESHOLD=100                # default
FUZZY_MATCH_THRESHOLD=90.0        # default
FUZZY_REVIEW_THRESHOLD=75.0       # default
MAX_IMAGE_DIMENSION=1600          # default
OCR_API_KEY=                      # เว้นว่าง = dev mode
MAX_UPLOAD_BYTES=10485760         # 10 MB default
DATABASE_URL=postgresql+asyncpg://...
```

---

## 🚀 Run

```bash
# Full stack
docker compose build ocr-service
docker compose up -d

# Dev hot-reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# OCR only (local)
cd ocr-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8004
```

---

## 📝 ClickUp Tasks

- [x] สร้าง ocr-service microservice (FastAPI + Docker)
- [x] Gemini 2.5 Flash OCR pipeline
- [x] Blur detection + Image resize
- [x] Base64 inline_data (security)
- [x] Fuzzy name matching + title compatibility
- [x] Match status: match / review / mismatch / blurry / no_text
- [x] auto-fill bank_name + account_number เมื่อ OCR match
- [x] FK ocr_results.applicant_id → applicants.id
- [x] Alembic migration 0034
- [x] CORS + Request logging
- [x] Auth: OCR_API_KEY (Bearer token)
- [x] Swagger docs
- [x] Frontend API docs (OCR_API_DOCS.md)
- [x] docker-compose integration
