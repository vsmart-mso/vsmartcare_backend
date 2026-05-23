# notification-service

บริการ FastAPI สำหรับ **คิวและส่งการแจ้งเตือน** (อีเมล / SMS / LINE) ในระบบ selfservice — เก็บข้อความในหน่วยความจำ (starter) และรองรับ **ส่งอีเมลจริงหรือ log** ผ่าน `EMAIL_MODE`

เอกสารนี้อธิบาย **โครงสร้างโฟลเดอร์**, **บทบาทแต่ละไฟล์**, และ **วิธีรัน/ขยาย** ให้สอดคล้องกับ service อื่นใน `service/`

---

## ภาพรวมในระบบ

```text
Frontend  →  bff-vsmartcare (:8000)  →  notification-service (:8002 ภายนอก / :8000 ใน container)
```

- Client **ไม่เรียก** notification-service โดยตรง — เรียกผ่าน BFF (`POST /v1/notifications` ที่ proxy ไป `NOTIFICATION_SERVICE_URL`)
- ใน Docker Compose ภายในเครือข่ายใช้ `http://notification-service:8000`

---

## โครงสร้างโฟลเดอร์

```text
notification-service/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, routes, in-memory store, auto-send
│   ├── settings.py      # EMAIL_MODE, SMTP_*, EMAIL_AUTO_SEND
│   ├── email_sender.py  # smtplib หรือ log JSON
│   ├── templates.py     # re-export render_email (backward compat)
│   └── email_templates/ # subject / plain / HTML แยกไฟล์ + registry
├── Dockerfile
├── requirements.txt
└── README.md
```

| ไฟล์ | หน้าที่ |
|------|--------|
| `app/settings.py` | `service_name`, `port`, `EMAIL_MODE`, SMTP, `EMAIL_AUTO_SEND` |
| `app/email_sender.py` | `send_email()` — โหมด `log` หรือ `smtp` |
| `app/email_templates/` | แปลง `template_code` + `payload` เป็น subject/plain/html |
| `app/templates.py` | re-export `render_email` (import เดิมยังใช้ได้) |
| `app/main.py` | API + auto-send หลัง `POST /v1/notifications` เมื่อ `channel=email` |

### โครงสร้าง `email_templates/`

```text
app/email_templates/
├── layout.html                    # กรอบ HTML ร่วม (header/footer)
├── loader.py                      # โหลดไฟล์ + แทนที่ {{placeholder}}
├── registry.py                    # map template_code → render()
├── welfare_status_updated/
│   ├── context.py                 # แปลง payload → dataclass
│   ├── subject.py                 # หัวข้ออีเมล
│   ├── plain.py                   # เนื้อหา plain text
│   ├── content.html               # เนื้อหาหลักใน HTML
│   ├── html.py                    # ประกอบ layout + fragments
│   └── fragments/                 # บล็อกเลือกแสดง (case_ref, remarks, CTA)
```

**เพิ่มเทมเพลตใหม่:** สร้างโฟลเดอร์ภายใต้ `email_templates/` แล้วลงทะเบียนใน `registry.py` ด้วย `TEMPLATE_CODE` ของตัวเอง

---

## วิธีสร้างโครงสร้างแบบนี้ (ขั้นตอน)

### 1. สร้างโฟลเดอร์และ dependencies

```bash
mkdir -p notification-service/app
touch notification-service/app/__init__.py
```

สร้าง `requirements.txt`:

```text
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
```

### 2. Settings (`app/settings.py`)

ใช้ `pydantic-settings` เพื่อให้ค่าตั้งค่ามาจาก environment โดยไม่ต้องมี `.env` ใน repo:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    service_name: str = "notification-service"
    port: int = 8000

settings = Settings()
```

### 3. แอปหลัก (`app/main.py`)

ลำดับที่แนะนำเมื่อขยาย service:

1. **Enum / constants** — `Channel`, `MessageStatus`
2. **Pydantic schemas** — request/response (เช่น `NotificationRequestCreate`, `NotificationMessage`)
3. **Store / repository** — ตอนนี้ใช้ `dict` ในหน่วยความจำ; production ควรเป็น DB + queue
4. **`FastAPI()` instance** — `title=settings.service_name`
5. **Health endpoints** — `/`, `/healthz`, `/readyz` สำหรับ probe
6. **Business API** — prefix `/v1/notifications`

### 4. Dockerfile

- Base: `python:3.11-slim`
- `WORKDIR /app`, `PYTHONPATH=/app`
- `COPY requirements.txt` → `pip install` → `COPY app ./app`
- `EXPOSE 8000`, CMD uvicorn ชี้ `app.main:app`

### 5. ลงทะเบียนใน Docker Compose

ใน `service/docker-compose.yml`:

- service ชื่อ `notification-service`
- `build.context: ./notification-service`
- map พอร์ต `8002:8000` (host → container)
- BFF ตั้ง `NOTIFICATION_SERVICE_URL=http://notification-service:8000`

ใน `service/docker-compose.dev.yml`:

- mount `./notification-service/app:/app/app`
- รัน uvicorn ด้วย `--reload` สำหรับพัฒนา

---

## API (เวอร์ชัน starter)

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `GET` | `/` | ข้อมูล service + `ok` |
| `GET` | `/healthz` | liveness |
| `GET` | `/readyz` | readiness |
| `POST` | `/v1/notifications` | สร้างข้อความในคิว (รองรับ idempotency) |
| `GET` | `/v1/notifications/{message_id}` | ดึงข้อความตาม id |
| `GET` | `/v1/notifications?limit=50` | รายการข้อความ (จำกัด 1–200) |
| `POST` | `/v1/notifications/{message_id}/send?succeed=true` | ส่ง/ส่งซ้ำ (email ใช้ `EMAIL_MODE`; channel อื่นยังจำลอง) |

### Body สร้างการแจ้งเตือน

```json
{
  "idempotency_key": "unique-key-min-8-chars",
  "channel": "email",
  "to": "user@example.com",
  "template_code": "WELFARE_STATUS_UPDATED",
  "payload": {
    "status_label": "อยู่ระหว่างการเบิก",
    "applicant_id": 1,
    "case_ref": "CASE-2026-001",
    "remarks": ""
  }
}
```

- **channel**: `email` | `sms` | `line`
- **idempotency_key**: ส่งซ้ำด้วย key เดิมจะได้ record เดิม (ไม่สร้างซ้ำ)
- เมื่อ `EMAIL_AUTO_SEND=true` และ `channel=email` จะส่งทันทีหลังสร้าง (ไม่ต้องเรียก `/send`)

### สถานะข้อความ (`MessageStatus`)

`queued` → `sending` → `sent` หรือ `failed`

---

## รันและทดสอบ

### ผ่าน Docker Compose (แนะนำ)

จากโฟลเดอร์ `service/`:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

- URL บนเครื่อง host: `http://localhost:8002`
- Swagger: `http://localhost:8002/docs`

### รันแบบ local (ไม่ใช้ Docker)

```bash
cd notification-service
pip install -r requirements.txt
set PYTHONPATH=.   # Windows CMD
# หรือ: $env:PYTHONPATH="."   # PowerShell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### ตัวอย่าง curl

```bash
curl -s -X POST http://localhost:8002/v1/notifications \
  -H "Content-Type: application/json" \
  -d "{\"idempotency_key\":\"demo-key-001\",\"channel\":\"email\",\"to\":\"a@b.c\",\"template_code\":\"CASE_CREATED\",\"payload\":{}}"

curl -s -X POST "http://localhost:8002/v1/notifications/{message_id}/send?succeed=true"
```

### ผ่าน BFF

BFF มี `POST /v1/notifications` ที่ส่งต่อ body ไป notification-service (ต้องมี API key ตามที่ BFF กำหนด) — ดู `bff-vsmartcare/app/main.py` คลาส `CreateNotificationRequest`

เอกสาร **อีเมลสรุปคำร้องรายวัน (staff digest)** สำหรับระบบภายนอก (เช่น VSmart cron): [`docs/STAFF_DIGEST.md`](docs/STAFF_DIGEST.md)

---

## Environment

| ตัวแปร | ค่าเริ่มต้น | หมายเหตุ |
|--------|-------------|----------|
| `PORT` | `8000` | พอร์ตใน container (compose map เป็น 8002 ภายนอก) |
| `EMAIL_MODE` | `log` | `log` \| `smtp` — เฟส 1 dev/beta ใช้ `log` |
| `EMAIL_AUTO_SEND` | `true` | ส่งทันทีหลังสร้าง notification (email) |
| `SMTP_HOST` | `localhost` | ใช้เมื่อ `EMAIL_MODE=smtp` |
| `SMTP_PORT` | `587` | Mailpit dev: `1025` |
| `SMTP_USER` / `SMTP_PASSWORD` | ว่าง | ถ้า relay ไม่ต้อง auth |
| `SMTP_FROM` | `noreply@localhost` | From header |
| `SMTP_USE_TLS` | `true` | port 587 |
| `SMTP_USE_SSL` | `false` | port 465 |

### Dev — ตัวเลือก A: log เท่านั้น (default ใน compose)

```env
EMAIL_MODE=log
EMAIL_AUTO_SEND=true
SMTP_FROM=dev-noreply@localhost
```

ดูผล: `docker compose logs -f notification-service`

### Dev — ตัวเลือก B: Mailpit

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile mailpit up -d
```

ใน `docker-compose.dev.yml` uncomment env `EMAIL_MODE=smtp` + `SMTP_HOST=mailpit` แล้วเปิด UI ที่ http://localhost:8025

### case-service (เรียก notification โดยตรง)

```env
NOTIFICATION_SERVICE_URL=http://notification-service:8000
STATUS_EMAIL_ENABLED=true
STATUS_EMAIL_TIMEOUT_SECONDS=5
```

Template สำหรับเปลี่ยนสถานะ: `WELFARE_STATUS_UPDATED` — payload มี `status_label`, `applicant_id`, `remarks`, `case_ref` (ถ้ามี). ยืนยันการยื่น/แก้ไข: `WELFARE_CASE_SUBMITTED` — `submission_kind`: `initial` | `correction`. เงื่อนไขการส่งฝั่งประชาชน: [`docs/CITIZEN_STATUS_EMAIL.md`](docs/CITIZEN_STATUS_EMAIL.md) ( logic ใน case-service )

อ้างอิง deploy Beta/Prod: [`../BETA_DEPLOYMENT.md`](../BETA_DEPLOYMENT.md)

---

## ข้อจำกัดของ starter และทิศทางขยาย

| ตอนนี้ | แนะนำเมื่อ production |
|--------|------------------------|
| เก็บข้อความใน `dict` (หายเมื่อ restart) | PostgreSQL / Redis + migration |
| ส่งแบบ sync ใน HTTP handler | Worker (Celery/RQ/ARQ) + message queue |
| ไม่มี retry/backoff จริง | นโยบาย retry + dead letter |
| อีเมลผ่าน SMTP/log แล้ว | SMS/LINE adapter, worker แยก |
| ไม่มี auth ที่ service เอง | เรียกเฉพาะภายใน cluster; BFF เป็นจุดเข้าสาธารณะ |

โครงสร้างที่ขยายได้โดยไม่เปลี่ยน contract API ภายนอก:

```text
app/
├── api/v1/notifications.py   # แยก router
├── schemas/                  # Pydantic models
├── services/                 # business logic + idempotency
├── repositories/             # DB access
└── workers/                  # async send tasks
```

---

## อ้างอิงใน repo

- Compose: [`../docker-compose.yml`](../docker-compose.yml), [`../docker-compose.dev.yml`](../docker-compose.dev.yml)
- รายการ services: [`../README.md`](../README.md)
- BFF proxy: `bff-vsmartcare` — `NOTIFICATION_SERVICE_URL`, `POST /v1/notifications`
