# Submit Request Load Test with Locust

โฟลเดอร์นี้ใช้ยิง load test ตาม flow ใน `SUBMIT_REQUEST_API_SUMMARY.md` ผ่าน `locust`

## สิ่งที่สคริปต์ทำ

- ยิง BFF ที่ `POST /v1/cases`, `POST /v1/welfare-request-consents`, `GET /v1/cases/submission-eligibility`
- ยิง upload หลักฐานที่ `POST /v1/cases/{applicant_id}/evidences`
- รองรับ OCR ที่ `POST /v1/ocr/bank-book` และ `PATCH /v1/ocr/results/{id}/link`
- มี 3 scenario ตามเอกสาร:
  - `full_frontend_equivalent_flow`
  - `core_persistence_only`
  - `file_upload_stress`

ค่า default ถูกตั้งไว้ให้ตรงกับ `docker-compose.yml` ใน repo นี้:

- BFF: `http://localhost:8000/api-vsmartcare`
- OCR: `http://localhost:8004`
- BFF API key: `1234567890`

## ข้อควรรู้ก่อนรัน

1. ต้องมี `persons_id` จริงในฐานข้อมูลหลายค่า
2. ต้องมี lookup IDs ที่ตรงกับ environment จริง
3. ถ้าใช้ `persons_id` ซ้ำ ระบบอาจตอบ `active_case_exists` หรือ `submission_cooldown_active`
4. OCR ถูกปิดไว้เป็น default ด้วย `LOCUST_ENABLE_OCR_LINK=false`
5. สคริปต์สร้างไฟล์ PNG 1x1 ใน memory เอง ไม่ต้องเตรียมรูปสำหรับ multipart เพิ่ม

## ติดตั้ง

```powershell
pip install locust
```

ถ้าต้องการแยก dependency:

```powershell
pip install locust python-dotenv
```

`python-dotenv` ไม่จำเป็นกับสคริปต์นี้

## เตรียม persons_id

สร้างไฟล์ [person_ids.csv](/D:/pm_care_backend/vsmartcare_backend/load_tests/person_ids.csv) หรือใช้ env `LOCUST_PERSON_IDS`

ตัวอย่างไฟล์:

```csv
persons_id
100001
100002
100003
```

## Environment Variables สำคัญ

```powershell
$env:LOCUST_PERSON_IDS="100001,100002,100003"
$env:LOCUST_SUB_DISTRICT_POSTCODE_ID="1"
$env:LOCUST_MARITAL_STATUS_ID="2"
$env:LOCUST_REQUESTER_RELATION_ID="1"
$env:LOCUST_BANK_NAME_ID="1"
$env:LOCUST_BANK_ACCOUNT_TYPE_ID="1"
$env:LOCUST_HOUSING_TYPES_ID="1"
$env:LOCUST_ADDRESS_TYPE_ID="1"
$env:LOCUST_REQUEST_TYPE_IDS="1"
```

ปรับ endpoint/headers ได้:

```powershell
$env:LOCUST_BFF_HOST="http://localhost:8000"
$env:LOCUST_BFF_API_PREFIX="/api-vsmartcare"
$env:LOCUST_BFF_API_KEY="1234567890"
$env:LOCUST_OCR_HOST="http://localhost:8004"
$env:LOCUST_OCR_BEARER_TOKEN=""
$env:LOCUST_ENABLE_OCR_LINK="false"
```

ปรับน้ำหนักแต่ละ scenario ได้:

```powershell
$env:LOCUST_WEIGHT_FULL_FLOW="3"
$env:LOCUST_WEIGHT_CORE_ONLY="2"
$env:LOCUST_WEIGHT_UPLOAD_STRESS="1"
```

## รันแบบมี UI

```powershell
locust -f .\load_tests\locustfile.py
```

จากนั้นเปิด [http://localhost:8089](http://localhost:8089)

## รันแบบ headless

```powershell
locust -f .\load_tests\locustfile.py --headless -u 20 -r 2 -t 5m
```

ตัวอย่างแยกเฉพาะ core flow:

```powershell
$env:LOCUST_WEIGHT_FULL_FLOW="0"
$env:LOCUST_WEIGHT_CORE_ONLY="1"
$env:LOCUST_WEIGHT_UPLOAD_STRESS="0"
locust -f .\load_tests\locustfile.py --headless -u 20 -r 2 -t 5m
```

ตัวอย่างเปิด OCR:

```powershell
$env:LOCUST_ENABLE_OCR_LINK="true"
locust -f .\load_tests\locustfile.py --headless -u 5 -r 1 -t 2m
```

## Metrics ที่ควรดู

- `BFF GET /v1/cases/submission-eligibility`
- `BFF POST /v1/cases`
- `BFF POST /v1/welfare-request-consents`
- `BFF POST /v1/cases/{applicant_id}/evidences`
- `OCR POST /v1/ocr/bank-book`
- `OCR PATCH /v1/ocr/results/{ocr_result_id}/link`

ถ้า eligibility ไม่ผ่าน สคริปต์จะ mark request เป็น failure พร้อม detail เพื่อแยกจาก error transport
