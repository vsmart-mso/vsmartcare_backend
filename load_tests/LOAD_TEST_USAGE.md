# Locust Load Test Usage

เอกสารนี้สรุปการรันระบบด้วย Docker และการใช้งาน load test สำหรับ flow `submit request` ใน [locustfile.py](/D:/pm_care_backend/vsmartcare_backend/load_tests/locustfile.py)

## Scope

สคริปต์นี้ใช้ทดสอบ flow หลักฝั่ง backend ตามลำดับนี้

1. `GET /v1/cases/submission-eligibility`
2. `POST /v1/cases`
3. `POST /v1/welfare-request-consents`
4. `POST /v1/cases/{applicant_id}/evidences`
5. `POST /v1/ocr/bank-book` และ `PATCH /v1/ocr/results/{ocr_result_id}/link` ถ้าเปิด OCR

## Scenarios

ใน `locustfile.py` มี 3 scenario

- `full_frontend_equivalent_flow`
  ยิงครบ eligibility, create case, final consent, upload หลักฐาน, และ OCR link ถ้าเปิด
- `core_persistence_only`
  ยิงเฉพาะ `create case` และ `final consent`
- `file_upload_stress`
  สร้าง case แล้ววัดโหลดที่การ upload หลักฐาน

## Default Endpoints

- BFF host: `http://localhost:8000`
- BFF API prefix: `/api-vsmartcare`
- OCR host: `http://localhost:8004`
- BFF API key: `1234567890`

## Prerequisites

ก่อนรันควรมีเงื่อนไขดังนี้

- service ที่เกี่ยวข้องต้องรันอยู่แล้ว
- มี `persons_id` จริงในฐานข้อมูล
- มี lookup IDs ที่ตรงกับ environment จริง
- ถ้า environment เปิด auth OCR ต้องมี `LOCUST_OCR_BEARER_TOKEN`

ข้อควรระวัง:

- ถ้า `persons_id` มีน้อยและถูกใช้ซ้ำ ระบบอาจตอบ `active_case_exists` หรือ `submission_cooldown_active`
- OCR ปิดไว้เป็นค่า default ด้วย `LOCUST_ENABLE_OCR_LINK=false`
- upload ใช้ไฟล์ PNG 1x1 ที่สร้างใน memory ไม่ต้องเตรียมรูปจริงเพิ่ม

## Docker Commands

### 1. รัน backend แบบ dev hot reload

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

ถ้า build ไว้แล้วและต้องการแค่ start:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### 2. รัน backend พร้อม monitoring

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.monitoring.yml up -d --build
```

ถ้า image พร้อมแล้ว:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.monitoring.yml up -d
```

### 3. หยุดระบบ

หยุด backend dev:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

หยุด backend + monitoring:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.monitoring.yml down
```

### 4. เช็กสถานะ container

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
```

หรือถ้ามี monitoring:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.monitoring.yml ps
```

### 5. ดู logs

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f
```

หรือดูเฉพาะบาง service:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f bff-vsmartcare case-service ocr-service
```

## Monitoring URLs

ถ้ารัน `docker-compose.monitoring.yml` เพิ่ม จะมี service ต่อไปนี้

- Prometheus: [http://localhost:9090](http://localhost:9090)
- Grafana: [http://localhost:3001](http://localhost:3001)
- cAdvisor: [http://localhost:8080](http://localhost:8080)
- Postgres Exporter: [http://localhost:9187/metrics](http://localhost:9187/metrics)

Grafana default login:

- user: `admin`
- password: `admin`

## Install Locust

```powershell
pip install locust
```

## Quick Setup With `.env`

copy [load_tests/.env.example](/D:/pm_care_backend/vsmartcare_backend/load_tests/.env.example) เป็น `load_tests/.env` แล้วแก้ค่าให้ตรงกับ environment

```powershell
Copy-Item .\load_tests\.env.example .\load_tests\.env
```

`locustfile.py` จะโหลด `load_tests/.env` อัตโนมัติ และถ้ามี environment variable จาก shell ซ้ำกัน ค่าจาก shell จะมี priority สูงกว่า

## Prepare `persons_id`

ระบุได้ 3 แบบ

แบบ env:

```powershell
$env:LOCUST_PERSON_IDS="100001,100002,100003"
```

แบบ `.env`:

```env
LOCUST_PERSON_IDS=100001,100002,100003
```

แบบไฟล์ CSV:

สร้างไฟล์ [person_ids.csv](/D:/pm_care_backend/vsmartcare_backend/load_tests/person_ids.csv) โดยดูตัวอย่างจาก [person_ids.example.csv](/D:/pm_care_backend/vsmartcare_backend/load_tests/person_ids.example.csv)

```csv
persons_id
100001
100002
100003
```

## Environment Variables

### Hosts

- `LOCUST_BFF_HOST`
  base URL ของ BFF เช่น `http://localhost:8000`
- `LOCUST_BFF_API_PREFIX`
  path prefix ของ API เช่น `/api-vsmartcare`
- `LOCUST_OCR_HOST`
  base URL ของ OCR service เช่น `http://localhost:8004`

### Auth / headers

- `LOCUST_BFF_API_KEY`
  ค่า `X-API-Key` ที่ BFF ต้องใช้
- `LOCUST_OCR_BEARER_TOKEN`
  token สำหรับ OCR service ถ้า environment นั้นเปิด auth

### Core lookup data

- `LOCUST_PERSON_IDS`
  รายการ `persons_id` ที่มีอยู่จริงในฐานข้อมูล
- `LOCUST_SUB_DISTRICT_POSTCODE_ID`
  ค่า `sub_district_postcode_id`
- `LOCUST_MARITAL_STATUS_ID`
  ค่า `marital_status_id`
- `LOCUST_REQUESTER_RELATION_ID`
  ค่า `requester_relation_id`
- `LOCUST_BANK_NAME_ID`
  ค่า `bank_name_id`
- `LOCUST_BANK_ACCOUNT_TYPE_ID`
  ค่า `bank_account_type_id`
- `LOCUST_HOUSING_TYPES_ID`
  ค่า `housing_types_id`
- `LOCUST_ADDRESS_TYPE_ID`
  ค่า `address_type_id`
- `LOCUST_REQUEST_TYPE_IDS`
  รายการ `request_type_ids`
- `LOCUST_INITIAL_CURRENT_STATUS_ID`
  ค่า `initial_current_status_id` ตอนสร้าง case

### Upload / OCR

- `LOCUST_ATTACHMENT_TYPE_IDS`
  รายการ `attachment_type_id` ที่จะ upload
- `LOCUST_ENABLE_OCR_LINK`
  `true/false` ว่าจะยิง OCR ด้วยหรือไม่
- `LOCUST_OCR_TARGET_NAME`
  ค่า `target_name` ที่ส่งไป OCR

### Applicant defaults

- `LOCUST_MOBILE_PHONE`
  เบอร์โทรใน payload
- `LOCUST_EMAIL_DOMAIN`
  domain สำหรับสร้าง email ทดสอบ

### Scenario weights

- `LOCUST_WEIGHT_FULL_FLOW`
  น้ำหนักของ `full_frontend_equivalent_flow`
- `LOCUST_WEIGHT_CORE_ONLY`
  น้ำหนักของ `core_persistence_only`
- `LOCUST_WEIGHT_UPLOAD_STRESS`
  น้ำหนักของ `file_upload_stress`

### Wait time

- `LOCUST_WAIT_MIN_SECONDS`
  เวลารอขั้นต่ำระหว่าง task
- `LOCUST_WAIT_MAX_SECONDS`
  เวลารอสูงสุดระหว่าง task

## Business Rule During Load Test

`POST /v1/cases` ไม่ได้เชื่อแค่ Locust ฝั่งเดียว

ตัว endpoint ใน `case-service` จะตรวจ `submission-eligibility` ซ้ำอีกครั้งก่อนสร้างเคสจริง

ดังนั้นถ้า `persons_id` เดิมมี applicant ล่าสุดที่อยู่ในสถานะ active หรือยังติด cooldown อยู่ ระบบจะตอบ:

- `409 active_case_exists`
- หรือ `409 submission_cooldown_active`

สรุปคือ ถ้าใช้ `persons_id` เดิมวนซ้ำไปเรื่อย ๆ แม้ Locust จะยิงได้ แต่ธุรกิจจะบล็อกเอง ไม่ได้ปล่อยให้สร้างเคสใหม่ไม่จำกัด

## Recommended Test Modes

### Mode 1: ทดสอบแบบตรง business rule จริง

เหมาะกับการตรวจว่า flow จริงผ่านหรือไม่

- ใช้ `persons.id` ที่ยังไม่เคยมี applicant
- หรือใช้ข้อมูลที่พ้น cooldown แล้ว
- ไม่ต้องแก้โค้ด backend

### Mode 2: ทดสอบ load/stress ของ persistence และ upload

เหมาะกับการวัดแรงกดระบบ แม้มี `persons_id` จำกัด

เปิด flag ใน `case-service/.env`:

```env
BYPASS_SUBMISSION_ELIGIBILITY=true
```

แล้ว restart `case-service`

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart case-service
```

ผลของ flag นี้:

- `POST /v1/cases` จะข้ามการบล็อก `active_case` และ `cooldown`
- `GET /v1/cases/submission-eligibility` ยังตอบตาม business rule เดิม
- เหมาะสำหรับ stress test เฉพาะการ create case, consent, upload evidence

ข้อจำกัด:

- ไม่ควรเปิดค้างใน environment ที่ใช้ทดสอบ business flow จริง
- ถ้าจะวัด behavior ตามกฎธุรกิจจริง ให้ปิดกลับเป็น `false`

## If You Want Only 5 Attempts

ถ้าต้องการแค่ลองยิงสั้น ๆ 5 รอบโดยประมาณ:

- ใช้ `-u 1 -r 1 -t 15s`
- ปิด scenario อื่นให้เหลือตัวเดียว
- เพิ่ม wait time ให้ยาวขึ้นถ้าต้องการลดจำนวนรอบ

ตัวอย่าง:

```env
LOCUST_WEIGHT_FULL_FLOW=0
LOCUST_WEIGHT_CORE_ONLY=1
LOCUST_WEIGHT_UPLOAD_STRESS=0
LOCUST_WAIT_MIN_SECONDS=2
LOCUST_WAIT_MAX_SECONDS=3
```

## Recommended `.env` For Only 3 `persons_id`

ถ้ามี `persons_id` แค่ 3 ชุด ควรเริ่มแบบเบา ๆ

```env
LOCUST_PERSON_IDS=100001,100002,100003

LOCUST_WEIGHT_FULL_FLOW=0
LOCUST_WEIGHT_CORE_ONLY=1
LOCUST_WEIGHT_UPLOAD_STRESS=0

LOCUST_WAIT_MIN_SECONDS=3
LOCUST_WAIT_MAX_SECONDS=5
LOCUST_ENABLE_OCR_LINK=false
```

## Run Locust With UI

```powershell
locust -f .\load_tests\locustfile.py
```

แล้วเปิด [http://localhost:8089](http://localhost:8089)

## Run Locust Headless

ตัวอย่างทั่วไป:

```powershell
locust -f .\load_tests\locustfile.py --headless -u 20 -r 2 -t 5m
```

ตัวอย่างสำหรับ `persons_id` มีน้อย:

```powershell
locust -f .\load_tests\locustfile.py --headless -u 1 -r 1 -t 1m
```

ตัวอย่างเปิด OCR:

```powershell
$env:LOCUST_ENABLE_OCR_LINK="true"
locust -f .\load_tests\locustfile.py --headless -u 5 -r 1 -t 2m
```

## Metrics To Watch

ดูทั้งฝั่ง Locust และ Monitoring

### Locust

- `BFF GET /v1/cases/submission-eligibility`
- `BFF POST /v1/cases`
- `BFF POST /v1/welfare-request-consents`
- `BFF POST /v1/cases/{applicant_id}/evidences`
- `OCR POST /v1/ocr/bank-book`
- `OCR PATCH /v1/ocr/results/{ocr_result_id}/link`

### Grafana / Prometheus

- service up/down
- CPU และ memory ของ containers
- PostgreSQL connections / transactions / row changes / cache hit ratio
- API request rate
- API latency p95 ของ `bff` และ `case-service`

## How To Read Grafana Panels

### API Request Rate

ดูปริมาณ request ต่อวินาทีของ endpoint ทั้งหมดที่มี metrics

ใช้ดู:

- endpoint ไหนถูกเรียกบ่อย
- มี traffic แปลกจาก browser, devtools, metrics endpoint หรือไม่
- ช่วงไหนระบบมี request เพิ่มขึ้น

### API Latency P95

ดูเวลาตอบสนองของกลุ่มช้าที่สุด 5% ของทุก endpoint

ใช้ดู:

- endpoint ไหนเริ่มช้า
- ช่วงที่ request rate เพิ่มขึ้น latency ขยับตามหรือไม่
- เทียบ endpoint เบากับ endpoint ที่เป็น transaction จริง

### Submit Request Flow Rate

ดูเฉพาะ endpoint ใน flow submit request

ใช้ดู:

- flow นี้ถูกยิงจริงหรือยัง
- ตอนนี้กำลังมีแค่ `GET submission-eligibility` หรือเริ่มมี `POST /v1/cases` แล้ว
- browser refresh กระทบ flow หลักตรงไหน

### Submit Request Flow Latency P95

ดู p95 latency ของ endpoint ใน flow submit request เท่านั้น

ใช้ดู:

- `submission-eligibility` เร็วหรือช้า
- `create case` หนักกว่าจุดอื่นหรือไม่
- `evidences` ช้าจาก I/O หรือ upload หรือไม่

### Submit Request Flow Error Rate

ดูสัดส่วน error ของ flow นี้

ใช้ดู:

- มี 4xx/5xx หรือยัง
- พอเพิ่มโหลดแล้ว fail เพิ่มตามหรือไม่
- ข้อมูลทดสอบไม่พอจนชน business rule หรือเปล่า

### Submit Request Flow Status Codes

ดูจำนวน request แยกตาม status code ของ flow นี้

ใช้ดู:

- `200/201` เป็นหลักหรือไม่
- มี `401`, `409`, `422`, `500` หรือไม่
- ถ้า error rate ขึ้น ให้ใช้ panel นี้หาสาเหตุต่อ

### Postgres Panels

- `Postgres Connections`
  ดูจำนวน connection ปัจจุบัน
- `Postgres Transactions`
  ดู transaction rate ว่าขยับตาม load หรือไม่
- `Postgres Row Changes`
  ดู insert/update/delete ต่อวินาที
- `Postgres Cache Hit Ratio`
  ถ้าต่ำลงมากอาจเริ่มมีแรงกดที่ I/O หรือ query pattern

### CPU / Memory Panels

ใน environment นี้ cAdvisor ที่ scrape ได้เป็น aggregate เป็นหลัก

ใช้ดู:

- ตอนยิง load test แล้ว CPU รวมขยับไหม
- memory รวมโตต่อเนื่องไหม

ถ้ายังไม่เห็น per-container series ให้ถือว่าเป็นข้อจำกัดของ source metrics ตอนนี้

## First Load Test Plan

ถ้ามี `persons_id` น้อย เช่น 3 ชุด ให้เริ่มแบบนี้ก่อน

### Step 1: รันระบบ

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.monitoring.yml up -d --build
```

### Step 2: เตรียม `load_tests/.env`

```powershell
Copy-Item .\load_tests\.env.example .\load_tests\.env
```

ใส่ค่าแบบเบา ๆ:

```env
LOCUST_PERSON_IDS=100001,100002,100003
LOCUST_WEIGHT_FULL_FLOW=0
LOCUST_WEIGHT_CORE_ONLY=1
LOCUST_WEIGHT_UPLOAD_STRESS=0
LOCUST_WAIT_MIN_SECONDS=3
LOCUST_WAIT_MAX_SECONDS=5
LOCUST_ENABLE_OCR_LINK=false
```

### Step 3: ยิงรอบแรกแบบเบา

```powershell
locust -f .\load_tests\locustfile.py --headless -u 1 -r 1 -t 1m
```

### Step 4: ดู Grafana พร้อมกัน

ให้ดู 4 panel นี้เป็นหลัก

- `Submit Request Flow Rate`
- `Submit Request Flow Latency P95`
- `Submit Request Flow Error Rate`
- `Submit Request Flow Status Codes`

ถ้าทั้ง 4 ตัวดูปกติ ค่อยขยับเป็น:

```powershell
locust -f .\load_tests\locustfile.py --headless -u 2 -r 1 -t 2m
```

และถ้า `persons_id` ยังมีแค่ 3 ชุด ไม่ควรข้ามไปจำนวน user สูงทันที

## Recommended First Run

เริ่มจาก backend + monitoring ก่อน

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.monitoring.yml up -d --build
```

จากนั้นรัน Locust แบบเบา ๆ

```powershell
locust -f .\load_tests\locustfile.py --headless -u 1 -r 1 -t 1m
```

ถ้าผ่านค่อยเพิ่มจำนวน user, เพิ่มเวลา, หรือเปิด full flow
