# OCR Service API Docs (Frontend)

> Base URL: `http://localhost:8004` (dev) / `http://ocr-service:8000` (docker)
> Service: `ocr-service`

## Authentication

- Dev: ถ้าไม่ตั้ง `OCR_API_KEY` เรียกได้โดยไม่ต้องส่ง token
- Prod: ต้องส่ง `Authorization: Bearer <OCR_API_KEY>`

```http
Authorization: Bearer your-ocr-api-key
```

## POST `/v1/ocr/bank-book`

OCR รูปสมุดบัญชีธนาคาร และคืนผลการอ่าน + สถานะเทียบชื่อ

### Request (multipart/form-data)

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | รูปสมุดบัญชี (`image/jpeg`, `image/png`, `image/webp`) |
| `target_name` | string | Yes | ชื่อ-นามสกุลสำหรับเทียบกับชื่อบัญชี |
| `applicant_id` | int | No | id ของใบคำร้อง |

### Response 200 (ตัวอย่าง)

```json
{
  "id": 15,
  "markdown": "## สมุดบัญชีธนาคาร\n...",
  "bank_info": {
    "account_number": "431-013603-2",
    "account_name": "นาย ภูริพัฒน ปัญญา",
    "bank_name": "ธนาคารไทยพาณิชย์",
    "deposit_type": "ออมทรัพย์",
    "branch_name": "เซ็นทรัลเวิลด์",
    "branch_code": "123",
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
| `id` | int | id ของ OCR result |
| `markdown` | string | ข้อความทั้งหมดที่ OCR อ่านได้ |
| `bank_info.account_number` | string \| null | เลขบัญชีที่ผ่าน validation |
| `bank_info.account_name` | string \| null | ชื่อบัญชีที่อ่านได้ |
| `bank_info.bank_name` | string \| null | ชื่อธนาคารที่อ่านได้ |
| `bank_info.deposit_type` | string \| null | ประเภทเงินฝากที่อ่านได้ |
| `bank_info.branch_name` | string \| null | ชื่อสาขาที่อ่านได้ |
| `bank_info.branch_code` | string \| null | รหัสสาขาที่ผ่าน validation |
| `bank_info.match_status` | MatchStatus | `match` \| `review` \| `mismatch` \| `blurry` \| `no_text` |
| `bank_info.fuzzy_score` | float | คะแนนความคล้ายชื่อ (0-100) |
| `target_name_checked` | string | ค่า `target_name` ที่ใช้เทียบ |
| `pre_file` | string | uuid ชื่อไฟล์ที่ระบบสร้าง |

## Validation Rules (สำคัญ)

### 1) Account Number

ระบบจะ validate หลัง OCR อีกชั้น:

- อนุญาตเฉพาะตัวเลข `0-9` และขีด `-`
- อักขระที่ไม่ใช่ `-` ต้องเป็นตัวเลขทั้งหมด
- ถ้ามีตัวอักษรหรือสัญลักษณ์อื่น (เช่น `X/x/*/#`) ถือว่าไม่ผ่าน
- ถ้าเป็นข้อความ mask เช่น `XXX`, `xxxxx`, `***` ถือว่าไม่ผ่าน
- ถ้าไม่ผ่าน validation จะคืน `account_number = null`

### 2) Branch Code

- ต้องเป็นตัวเลขล้วน ความยาว `2-6` หลัก
- ถ้าไม่ผ่าน validation จะคืน `branch_code = null`

### 3) Deposit Type / Branch Name

- ถ้าอ่านไม่ชัด, ถูกปิดบัง, หรือไม่พบ ให้คืน `null`

## Match Status

| Status | Meaning |
|---|---|
| `match` | ชื่อตรงตามเกณฑ์ match |
| `review` | ใกล้เคียง ต้องให้เจ้าหน้าที่ตรวจซ้ำ |
| `mismatch` | ไม่ตรง |
| `blurry` | ภาพเบลอเกิน threshold |
| `no_text` | ไม่พบข้อความในภาพ |

## Error Responses

| Status | Example Detail |
|---|---|
| `400` | `ไฟล์ว่างเปล่า` |
| `401` | `token ไม่ถูกต้อง` |
| `413` | `ขนาดไฟล์ต้องไม่เกิน 10 MB` |
| `415` | `รองรับเฉพาะ image/jpeg, image/png, image/webp` |
| `422` | validation error (input ไม่ครบ/รูปแบบผิด) |

## PATCH `/v1/ocr/results/{ocr_result_id}/link`

ผูกผล OCR กับ applicant_id ภายหลัง

Request body:

```json
{
  "applicant_id": 42
}
```

## GET `/v1/ocr/results/{applicant_id}`

ดึงรายการผล OCR ทั้งหมดของ applicant นั้น (เรียงล่าสุดก่อน)

Query:

- `limit` (default 10, min 1, max 50)

## TypeScript Types

```ts
type MatchStatus = "match" | "review" | "mismatch" | "blurry" | "no_text";

interface BankInfo {
  account_number: string | null;
  account_name: string | null;
  bank_name: string | null;
  deposit_type: string | null;
  branch_name: string | null;
  branch_code: string | null;
  match_status: MatchStatus;
  fuzzy_score: number;
}

interface OcrResponse {
  id: number;
  markdown: string;
  bank_info: BankInfo | null;
  target_name_checked: string;
  pre_file: string;
}
```