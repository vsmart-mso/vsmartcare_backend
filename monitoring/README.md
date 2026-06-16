# Monitoring Stack

ไฟล์นี้เพิ่ม monitoring stack สำหรับใช้งานคู่กับ load test:

- Prometheus: [http://localhost:9090](http://localhost:9090)
- Grafana: [http://localhost:3001](http://localhost:3001)
- cAdvisor: [http://localhost:8080](http://localhost:8080)
- Postgres Exporter: [http://localhost:9187/metrics](http://localhost:9187/metrics)

## Start

ใช้ร่วมกับ compose หลักของระบบ:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.monitoring.yml up -d
```

ถ้าไม่ต้องการ hot reload:

```powershell
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

## Default Grafana Login

- user: `admin`
- password: `admin`

override ได้ด้วย environment variables:

```powershell
$env:GRAFANA_ADMIN_USER="admin"
$env:GRAFANA_ADMIN_PASSWORD="change-me"
```

## What Is Collected

- Prometheus scrape `cadvisor:8080`
- Prometheus scrape `postgres-exporter:9187`
- Prometheus scrape `/metrics` จาก `bff-vsmartcare` และ `case-service`
- Grafana datasource ถูก provision ให้ชี้ไป Prometheus อัตโนมัติ
- Grafana dashboard ถูก provision อัตโนมัติจาก `monitoring/grafana/dashboards`

## Included Dashboard

Grafana จะมี dashboard ชื่อ `VSmartCare Monitoring Overview` ให้ทันที โดยรวม:

- service up/down
- CPU และ memory aggregate จาก cAdvisor
- PostgreSQL connections
- PostgreSQL transactions
- PostgreSQL row changes
- PostgreSQL cache hit ratio
- API request rate
- API latency p95 สำหรับ `bff` และ `case-service`
- submit-request flow request rate
- submit-request flow latency p95
- submit-request flow error rate
- submit-request flow status code breakdown

## Application Metrics Added

ตอนนี้มี Prometheus metrics ระดับ HTTP request ใน 2 service นี้แล้ว:

- `bff-vsmartcare`
- `case-service`

metrics หลักที่เพิ่ม:

- `http_requests_total`
- `http_request_duration_seconds`
- `http_requests_in_progress`

## Notes

- stack นี้ยังไม่มี application-level Prometheus metrics จาก FastAPI; ตอนนี้จึงเห็นเด่นที่ container metrics จาก cAdvisor และสถานะ up/down จาก health checks
- ตอนนี้ Prometheus ไม่ได้ scrape `/healthz` ที่ตอบ JSON แล้ว เพราะ Prometheus parse ค่าแบบ metrics เท่านั้น
- ถ้าต้องการ monitor health endpoint จริง ๆ ควรเพิ่ม `blackbox_exporter` ภายหลัง
- ใน environment นี้ cAdvisor ที่ expose ออกมาผ่าน Prometheus ยังให้ค่า aggregate เป็นหลัก ถ้ายังไม่เห็น per-container series ใน Grafana ให้ถือว่าเป็นข้อจำกัดของ metric source ปัจจุบัน ไม่ใช่ dashboard พัง
- `cAdvisor` ใช้ mount ฝั่ง Docker host; ถ้า Docker Desktop/Windows บางเครื่องมีข้อจำกัดเรื่อง mount path อาจต้องปรับตาม environment
