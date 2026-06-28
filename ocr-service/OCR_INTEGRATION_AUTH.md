# OCR Integration Login

เส้นสำหรับ VSmart ภายนอกที่เพิ่มเข้ามา มีเพียง login ตาม credential ที่กำหนดใน env เท่านั้น

## Env

```text
OCR_AUTH_ENABLED=true
OCR_API_KEY=0gMhLbXJPeFEhWV4qZK69ErdWTxmzvfp
OCR_API_USERNAME=vsmart
OCR_API_PASSWORD_HASH=<bcrypt-hash>
OCR_JWT_SECRET=ocr-jwt-vsmart-2026-9f7c2a1b6d4e8h3k5m1p7r9t2w4y6z8
OCR_JWT_EXPIRE_MINUTES=60
```

`OCR_API_PASSWORD_HASH` ต้องเป็น bcrypt hash ของ password จริง ไม่ใช่ plain text

ตัวอย่าง ถ้าเลือก password จริงเป็น:

```text
Vsmart@2026!
```

ให้สร้าง hash ด้วย:

```python
import bcrypt
print(bcrypt.hashpw(b"Vsmart@2026!", bcrypt.gensalt()).decode())
```

หรือ one-liner:

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'Vsmart@2026!', bcrypt.gensalt()).decode())"
```

เอาค่าที่ได้ไปใส่แทน:

```text
OCR_API_PASSWORD_HASH=$2b$12$...
```

## Login

```http
POST /v1/ocr/auth/login
Content-Type: application/json
```

```json
{
  "username": "vsmart",
  "password": "Vsmart@2026!"
}
```

response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

## ขอบเขตของเส้นนี้

- เส้นนี้ใช้ตรวจ `username/password` จาก env และออก JWT
- ไม่ได้สร้าง external business routes เพิ่มเติมนอกเหนือจาก login
- OCR business endpoints เดิมของ service ยังใช้ auth เดิมของ `ocr-service`

## OCR business endpoints เดิม

ถ้าตั้ง `OCR_API_KEY` อยู่แล้ว เส้น OCR เดิมจะยังคงใช้:

```http
Authorization: Bearer 0gMhLbXJPeFEhWV4qZK69ErdWTxmzvfp
```

เช่น:
- `POST /v1/ocr/bank-book`
- `PATCH /v1/ocr/results/{ocr_result_id}/link`
- `GET /v1/ocr/results/{applicant_id}`

## Error หลักของ login

- `401 invalid_credentials`
- `503 ocr_auth_disabled`
- `503 ocr_auth_config_incomplete`
