# คู่มือ Deploy Beta — `vsmart-demo.m-society.go.th`

เอกสารนี้สำหรับทีมที่นำ backend ใน [`service/`](.) ขึ้น Beta  
โดเมนตัวอย่าง: **`https://vsmart-demo.m-society.go.th`**

**อ่านส่วนไหนก่อน**

| ถ้าคุณต้องการ… | ไปที่ |
|----------------|--------|
| คำสั่งรันบนเซิร์ฟเวอร์ Beta | [คำสั่งบน Beta](#คำสั่งบน-beta) |
| ลำดับงานทั้งหมด | [ขั้นตอน deploy](#ขั้นตอน-deploy-ตามลำดับ) |
| ตั้งค่า env ต่อ service | [ตัวแปรแวดล้อม](#ตัวแปรแวดล้อม-ต่อ-service) |
| ตั้ง nginx / TLS | [Reverse proxy](#reverse-proxy-แบบ-a-ที่แนะนำ) |
| build frontend | [Frontend](#frontend) |
| ตรวจหลัง deploy | [ตรวจสอบหลัง deploy](#ตรวจสอบหลัง-deploy) |

---

## ภาพรวมสั้นๆ

- **ผู้ใช้** เปิดเว็บที่โดเมน Beta แล้วเรียก API ผ่าน **BFF** (`bff-vsmartcare`) เป็นจุดเข้าเดียว
- **BFF** ส่งต่อไป `case-service`, `notification-service`, `thaid-auth-service` ภายในเครือข่าย (Docker/K8s) — **ไม่เปิดพอร์ตเหล่านี้สู่สาธารณะโดยตรง**
- BFF รับ path สาธารณะใต้ **`/api-vsmartcare`** (เช่น `/api-vsmartcare/v1/...`, `/api-vsmartcare/healthz`) — nginx ควร proxy **`/api-vsmartcare/`** ไป BFF **โดยไม่ strip** prefix (ดู [ทางเลือก URL อื่น](#ทางเลือก-url-อื่น-ถ้าไม่ใช้แบบ-a))

```mermaid
flowchart LR
  browser[Browser]
  nginx[Nginx_TLS]
  spa[SPA_static]
  bff[BFF]
  case[case_service]
  notify[notification_service]
  thaid[thaid_auth_service]
  pg[(PostgreSQL)]

  browser --> nginx
  nginx --> spa
  nginx -->|"/api-vsmartcare/"| bff
  bff --> case
  bff --> notify
  bff --> thaid
  case --> pg
  thaid --> pg
```

---

## สิ่งที่ต้องมีก่อนเริ่ม

- Docker หรือ orchestrator ที่รัน image จาก [`docker-compose.yml`](docker-compose.yml) (หรือ build แยกตาม Dockerfile แต่ละ service)
- **PostgreSQL** พร้อม database (ชื่อตาม `DATABASE_URL` เช่น `case_service`)
- **TLS** บนโดเมน `vsmart-demo.m-society.go.th` (ถ้ายังเห็นหน้า Welcome nginx แปลว่ายังไม่ได้ชี้มาที่แอป — [ตัวอย่าง](https://vsmart-demo.m-society.go.th/))
- ค่า **ThaiD** (client id/secret, metadata URL) และสิทธิ์ลงทะเบียน **Redirect URI**
- ที่เก็บ **ไฟล์อัปโหลด** สำหรับ `UPLOAD_ROOT` (volume/disk)
- ค่าลับผ่าน secret store / CI — **อย่า commit** `.env`

---

## ขั้นตอน deploy (ตามลำดับ)

ทำตามลำดับนี้ แล้วติ๊กเมื่อเสร็จ

### 1. เลือกรูปแบบ URL

**แนะนำแบบ A (same origin):** SPA ที่ `/` และ proxy **`/api-vsmartcare/` → BFF** บนโดเมนเดียวกัน

- หน้าเว็บ: `https://vsmart-demo.m-society.go.th`
- API จากเบราว์เซอร์: `https://vsmart-demo.m-society.go.th/api-vsmartcare/v1/...`

ถ้าใช้ subdomain API หรือ prefix `/api` ดู [ทางเลือก URL อื่น](#ทางเลือก-url-อื่น-ถ้าไม่ใช้แบบ-a) แล้วปรับ `VITE_API_URL`, CORS, `THAID_REDIRECT_URI` ให้ตรง

### 2. ฐานข้อมูลและ migration

- [ ] สร้าง PostgreSQL + database
- [ ] ตั้ง `DATABASE_URL` ให้ **case-service** และ **thaid-auth-service** (ถ้าต้องการบันทึก `persons` หลังล็อกอิน)
- [ ] รัน **`alembic upgrade head`** ของ case-service **ก่อน**เปิดรับ traffic (ใน dev มีตัวอย่างใน [`docker-compose.dev.yml`](docker-compose.dev.yml))

### 3. รัน backend (ภายในเครือข่าย)

- [ ] รัน `case-service`, `notification-service`, `thaid-auth-service`, `bff-vsmartcare`
- [ ] ตั้ง env ตาม [ตารางด้านล่าง](#ตัวแปรแวดล้อม-ต่อ-service) — URL ระหว่าง service ใช้ชื่อภายใน (เช่น `http://case-service:8000`) **ไม่ใช่** `localhost` ของเครื่อง host
- [ ] mount volume สำหรับ `UPLOAD_ROOT` ของ case-service

### 4. Reverse proxy + TLS

- [ ] ใส่ certificate ให้ `vsmart-demo.m-society.go.th`
- [ ] เสิร์ฟ static SPA + proxy `/api-vsmartcare/` ไป BFF — ดู [ตัวอย่าง nginx](#reverse-proxy-แบบ-a-ที่แนะนำ)

### 5. ThaiD

- [ ] ตั้ง `THAID_*` บน thaid-auth-service (`THAID_USE_MOCK=false` บน Beta จริง)
- [ ] ลงทะเบียน **Redirect URI** ใน ThaiD ให้ตรง **`THAID_REDIRECT_URI` ทุกอักขระ** (แบบ A มักเป็น `https://vsmart-demo.m-society.go.th/api-vsmartcare/v1/auth/thaid/callback` เมื่อ BFF รับ path นี้สาธารณะ)

### 6. Frontend

- [ ] build จาก [`frontend/`](../frontend) ด้วย `VITE_API_URL` ตาม [Frontend](#frontend) (**ไม่ตั้ง** `VITE_BFF_API_KEY` — CR-02)
- [ ] deploy ไฟล์ static ไป path ที่ nginx เสิร์ฟ

### 7. ตรวจสอบ

- [ ] ทำตาม [ตรวจสอบหลัง deploy](#ตรวจสอบหลัง-deploy)

---

## Reverse proxy (แบบ A ที่แนะนำ)

```nginx
# SPA
location / {
    root /var/www/vsmart-demo;
    try_files $uri $uri/ /index.html;
}

# BFF — ส่ง path /api-vsmartcare/ ไป upstream โดยไม่ strip prefix
location /api-vsmartcare/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

ปรับ `proxy_pass` และพอร์ตให้ตรงกับที่ BFF ฟังจริง

---

## ตัวแปรแวดล้อม ต่อ service

ค่าตัวอย่างด้านล่างอ้าง **แบบ A** (same origin, HTTPS, BFF ใต้ `/api-vsmartcare`)

**สัญลักษณ์:** จำเป็น = ต้องตั้งบน Beta | แนะนำ = ควรตั้ง | ไม่บังคับ = มี default หรือใช้เมื่อต้องการฟีเจอร์นั้น

### BFF — `bff-vsmartcare`

อ้างอิง [`bff-vsmartcare/app/settings.py`](bff-vsmartcare/app/settings.py)

| ตัวแปร | จำเป็น | ตัวอย่าง Beta (แบบ A) | หมายเหตุ |
|--------|--------|------------------------|----------|
| `PORT` | จำเป็น | `8000` | พอร์ตใน container |
| `BFF_API_PREFIX` | ไม่บังคับ | `/api-vsmartcare` | prefix สาธารณะของ BFF (default ในโค้ด) |
| `CASE_SERVICE_URL` | จำเป็น | `http://case-service:8000` | URL ภายใน cluster |
| `NOTIFICATION_SERVICE_URL` | จำเป็น | `http://notification-service:8000` | URL ภายใน cluster |
| `THAID_AUTH_SERVICE_URL` | จำเป็น | `http://thaid-auth-service:8000` | URL ภายใน cluster |
| `BFF_CORS_ORIGINS` | แนะนำ | `https://vsmart-demo.m-society.go.th` | origin ของ SPA คั่นจุลภาค |
| `BFF_API_PASSWORD` | บังคับ (beta/prod) | ค่าลับ | trusted server clients (`volunteer_smart`) — ต้องตรงกับ `STAFF_INTERNAL_API_KEY` |

### case-service

อ้างอิง [`case-service/app/settings.py`](case-service/app/settings.py)

| ตัวแปร | จำเป็น | ตัวอย่าง Beta | หมายเหตุ |
|--------|--------|----------------|----------|
| `SERVICE_NAME` | จำเป็น | `case-service` | |
| `PORT` | จำเป็น | `8000` | |
| `DATABASE_URL` | จำเป็น | `postgresql+asyncpg://USER:PASS@host:5432/case_service` | asyncpg |
| `UPLOAD_ROOT` | แนะนำ | path ใน volume | เก็บไฟล์หลักฐาน |
| `MAX_UPLOAD_BYTES` | ไม่บังคับ | `10485760` | default 10 MiB |
| `NOTIFICATION_SERVICE_URL` | จำเป็น | `http://notification-service:8000` | case-service เรียกส่งอีเมลเมื่อเจ้าหน้าที่เปลี่ยนสถานะ (ไม่ผ่าน BFF) |
| `STATUS_EMAIL_ENABLED` | ไม่บังคับ | `true` | `false` = ข้ามการแจ้งเตือน |
| `STATUS_EMAIL_TIMEOUT_SECONDS` | ไม่บังคับ | `5` | timeout เรียก notification-service |

### thaid-auth-service

อ้างอิง [`thaid-auth-service/app/settings.py`](thaid-auth-service/app/settings.py)

| ตัวแปร | จำเป็น | ตัวอย่าง Beta (แบบ A) | หมายเหตุ |
|--------|--------|------------------------|----------|
| `DATABASE_URL` | แนะนำ | เหมือน case-service | ว่าง = ล็อกอินได้แต่ไม่ insert `persons` |
| `THAID_CLIENT_ID` | จำเป็น (OIDC จริง) | จาก portal ThaiD | |
| `THAID_CLIENT_SECRET` | จำเป็น (OIDC จริง) | จาก portal | ลับ |
| `THAID_SERVER_METADATA_URL` | จำเป็น (OIDC จริง) | URL `.well-known/openid-configuration` | |
| `THAID_REDIRECT_URI` | จำเป็น | `https://vsmart-demo.m-society.go.th/api-vsmartcare/v1/auth/thaid/callback` | ต้องตรงกับที่ลงทะเบียนใน ThaiD |
| `THAID_SCOPE` | ไม่บังคับ | ตาม default ในโค้ด | |
| `THAID_PUBLIC_BASE_URL` | แนะนำ | `https://vsmart-demo.m-society.go.th` | ลิงก์ OAuth/mock ต้องตรง URL ที่ user เห็น |
| `THAID_CORS_ORIGINS` | แนะนำ | `https://vsmart-demo.m-society.go.th` | |
| `THAID_POST_LOGIN_REDIRECT` | ไม่บังคับ | URL หน้า SPA หลังล็อกอิน | ว่าง = คืน JSON |
| `THAID_JWT_SECRET` | ไม่บังคับ | สตริงลับยาว | ว่าง = opaque token ใน memory |
| `THAID_USE_MOCK` | จำเป็น | `false` | Beta จริงไม่ใช้ mock |

โค้ดใช้ `THAID_REDIRECT_URI` เป็นหลัก ไม่พึ่ง `request.base_url` ของ container — ดู [`thaid-auth-service/app/main.py`](thaid-auth-service/app/main.py)

### notification-service

อ้างอิง [`notification-service/app/settings.py`](notification-service/app/settings.py)

| ตัวแปร | จำเป็น | ตัวอย่าง Beta (เฟส 1) | ตัวอย่าง Prod (เฟส 2) | หมายเหตุ |
|--------|--------|------------------------|------------------------|----------|
| `PORT` | จำเป็น | `8000` | `8000` | |
| `EMAIL_MODE` | จำเป็น | `log` | `smtp` | `log` = พิมพ์ JSON ใน log ไม่ส่งออกเน็ต |
| `EMAIL_AUTO_SEND` | ไม่บังคับ | `true` | `true` | ส่งทันทีหลัง `POST /v1/notifications` |
| `SMTP_FROM` | แนะนำ | `noreply@vsmart-demo.m-society.go.th` | `noreply@m-society.go.th` | |
| `SMTP_HOST` | เมื่อ `smtp` | — | relay องค์กร | |
| `SMTP_PORT` | เมื่อ `smtp` | — | `587` | |
| `SMTP_USER` / `SMTP_PASSWORD` | เมื่อ relay ต้อง auth | — | จาก secret store | อย่า commit |
| `SMTP_USE_TLS` | เมื่อ `smtp` | — | `true` (port 587) | |
| `SMTP_USE_SSL` | เมื่อ `smtp` | — | `false` | ใช้ `true` กับ port 465 |

**Beta เฟส 1 (แนะนำก่อน UAT SMTP):** `EMAIL_MODE=log`, `EMAIL_AUTO_SEND=true` — ตรวจ `docker logs notification-service` หลังเจ้าหน้าที่เปลี่ยนสถานะ

**case-service บน Beta:** ตั้ง `NOTIFICATION_SERVICE_URL` และ `STATUS_EMAIL_ENABLED=true` เหมือนตาราง case-service ด้านบน

---

## Frontend

Build จาก [`frontend/`](../frontend) **ก่อน** `npm run build` (หรือคำสั่ง build ของโปรเจกต์):

| ตัวแปร | ตัวอย่างแบบ A | หมายเหตุ |
|--------|----------------|----------|
| `VITE_API_URL` | `https://vsmart-demo.m-society.go.th/api-vsmartcare` | ฐาน URL ที่ client เรียก BFF (รวม prefix `/api-vsmartcare`) |

**CR-02:** ไม่ตั้ง `VITE_BFF_API_KEY` ใน beta/prod — browser ใช้ Bearer JWT หลัง ThaiD/admin login เท่านั้น

การแนบ header: [`frontend/src/api/client.ts`](../frontend/src/api/client.ts) (Bearer เท่านั้น)

---

## ความปลอดภัย (สรุป)

1. Redirect URI ใน ThaiD = `THAID_REDIRECT_URI` ตรงทุกตัวอักษร (`https`, path `/api-vsmartcare/v1/auth/thaid/callback` หรือตาม topology ที่เลือก)
2. TLS บนโดเมนสาธารณะ
3. ไม่ commit secret / `.env`
4. `BFF_API_PASSWORD` = `STAFF_INTERNAL_API_KEY` (ค่าเดียวกัน) สำหรับ `volunteer_smart` — **ไม่** build ลง frontend

---

## ตรวจสอบหลัง deploy

| ตรวจ | วิธี / ผลที่คาด |
|------|----------------|
| TLS + SPA | เปิด `https://vsmart-demo.m-society.go.th` ได้หน้าแอป ไม่ใช่หน้า nginx default |
| BFF ผ่าน proxy | `GET https://vsmart-demo.m-society.go.th/api-vsmartcare/healthz` ได้ `{"ok":true}` |
| API ผ่าน BFF | เรียก lookup ใต้ `/api-vsmartcare/v1/...` ได้ (ถ้าเปิด API key ต้องส่ง `X-API-Key`) |
| DB + migration | case-service บันทึก/อ่านข้อมูลได้ ไม่ error connection |
| อัปโหลด | path `UPLOAD_ROOT` เขียนได้หลังอัปโหลดหลักฐาน |
| ThaiD | ล็อกอิน redirect กลับ callback URL ที่ลงทะเบียน ไม่ mismatch |
| CORS | เรียก API จาก origin ของ SPA ไม่ถูกบล็อก |

Health ภายใน service: `/healthz`, `/readyz` (ดู [`case-service/app/main.py`](case-service/app/main.py) และ service อื่น)

---

## ทางเลือก URL อื่น (ถ้าไม่ใช้แบบ A)

### แบบ B — API แยก subdomain

- SPA: `https://vsmart-demo.m-society.go.th`
- BFF สาธารณะ: เช่น `https://api.vsmart-demo.m-society.go.th`
- ตั้ง `VITE_API_URL` = URL ของ BFF
- ตั้ง `BFF_CORS_ORIGINS` และ `THAID_CORS_ORIGINS` รวม origin ของ SPA
- `THAID_REDIRECT_URI` = URL callback สาธารณะที่ ThaiD redirect ได้ (มักอยู่ใต้โดเมน API ถ้า flow ผ่าน BFF)

### แบบ C — prefix อื่นหรือ strip ที่ proxy

BFF ตั้ง prefix ผ่าน `BFF_API_PREFIX` (default `/api-vsmartcare`) — nginx ควร proxy path นั้น **โดยไม่ strip**  
ถ้าต้องการ prefix อื่น ตั้ง `BFF_API_PREFIX`, `VITE_API_URL`, `THAID_REDIRECT_URI` และ config proxy ให้ตรงกัน

---

## คำสั่งบน Beta

รันจากโฟลเดอร์ **`service/`** บนเซิร์ฟเวอร์ Beta  
ใช้เฉพาะ [`docker-compose.yml`](docker-compose.yml) — **ไม่ใช้** [`docker-compose.dev.yml`](docker-compose.dev.yml) (ไฟล์นั้นสำหรับ dev บนเครื่อง: hot-reload, mount โค้ด)

ก่อน `up` ตั้ง env บนเซิร์ฟเวอร์แล้ว (อย่างน้อย [`case-service/.env`](case-service/.env), [`thaid-auth-service/.env`](thaid-auth-service/.env), `BFF_API_PASSWORD` ฯลฯ) ตาม [ตัวแปรแวดล้อม](#ตัวแปรแวดล้อม-ต่อ-service)

### Docker Compose (ใช้ประจำ)

| งาน | คำสั่ง |
|-----|--------|
| build image แล้ว start (detached) | `docker compose -f docker-compose.yml up -d --build` |
| start โดยไม่ rebuild | `docker compose -f docker-compose.yml up -d` |
| หยุดและลบ container | `docker compose -f docker-compose.yml down` |
| ดูสถานะ | `docker compose -f docker-compose.yml ps` |
| ดู log ทุก service | `docker compose -f docker-compose.yml logs -f` |
| ดู log service เดียว | `docker compose -f docker-compose.yml logs -f bff-vsmartcare` |

เปลี่ยนชื่อ service ใน `logs -f` ได้: `case-service`, `thaid-auth-service`, `notification-service`, `postgres`

### Migration (case-service)

[`case-service/Dockerfile`](case-service/Dockerfile) รัน `alembic upgrade head` ก่อน uvicorn ทุกครั้งที่ container เริ่ม  
ถ้าต้องการรัน migration เอง (ก่อนเปิด traffic หรือหลังอัปเดต schema):

```bash
docker compose -f docker-compose.yml run --rm case-service alembic upgrade head
```

หรือ container รันอยู่แล้ว:

```bash
docker compose -f docker-compose.yml exec case-service alembic upgrade head
```

### ตรวจ health บนเซิร์ฟเวอร์ (ก่อน/หลังเปิด nginx)

จากเครื่องที่เข้าถึงพอร์ตที่ compose map (ค่า default ใน compose):

```bash
curl -sS http://127.0.0.1:8000/api-vsmartcare/healthz
curl -sS http://127.0.0.1:8001/healthz
curl -sS http://127.0.0.1:8002/healthz
curl -sS http://127.0.0.1:8003/healthz
```

ผู้ใช้ปลายทางผ่านโดเมน Beta มักเรียก BFF ผ่าน HTTPS/nginx เช่น `https://vsmart-demo.m-society.go.th/api-vsmartcare/healthz` และ API ใต้ `/api-vsmartcare/v1/...` — ดู [ตรวจสอบหลัง deploy](#ตรวจสอบหลัง-deploy)

### Frontend (build บนเครื่อง CI หรือเซิร์ฟเวอร์ build)

จากโฟลเดอร์ [`frontend/`](../frontend) ตั้ง `VITE_API_URL` ตาม [Frontend](#frontend) แล้ว build (คำสั่งตาม stack ของโปรเจกต์ เช่น `npm ci` แล้ว `npm run build`) นำผลลัพธ์ไป path ที่ nginx เสิร์ฟ static — **ไม่ตั้ง** `VITE_BFF_API_KEY`

### Nginx (หลังแก้ config)

```bash
sudo nginx -t
sudo systemctl reload nginx
```

ค่า `proxy_pass` และ TLS ดู [Reverse proxy](#reverse-proxy-แบบ-a-ที่แนะนำ)

### คำสั่ง dev บนเครื่อง (ไม่ใช้บน Beta)

ใช้คู่ไฟล์ compose + dev overlay — ดู [README.md](README.md)

---

## Dev บนเครื่อง vs Beta

| | Dev ([`docker-compose.yml`](docker-compose.yml)) | Beta |
|--|--------------------------------------------------|------|
| Postgres | ใน compose | managed / แยกเซิร์ฟเวอร์ |
| พอร์ตสาธารณะ | 8000–8003 บน host | มักมีแค่ 443 ผ่าน nginx |
| env | `.env` ใน repo (ไม่ commit ลับ) | secret store / orchestrator |
| compose | `docker compose -f docker-compose.yml -f docker-compose.dev.yml …` | `docker compose -f docker-compose.yml …` (ดู [คำสั่งบน Beta](#คำสั่งบน-beta)) |
| migration | dev overlay รัน alembic ก่อน uvicorn | case-service image รัน alembic ตอน start; รัน `alembic upgrade head` เองได้เมื่อต้องการ |

---

## อ้างอิงไฟล์ใน repo

| หัวข้อ | ไฟล์ |
|--------|------|
| BFF env | [`bff-vsmartcare/app/settings.py`](bff-vsmartcare/app/settings.py) |
| case-service env | [`case-service/app/settings.py`](case-service/app/settings.py) |
| ThaiD env | [`thaid-auth-service/app/settings.py`](thaid-auth-service/app/settings.py) |
| Compose | [`docker-compose.yml`](docker-compose.yml) |
| README ทั่วไป | [`README.md`](README.md) |
