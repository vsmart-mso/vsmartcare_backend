# Task ID

TASK-191

## Title

Staff Indicators API — สรุปเงินช่วยเหลือ พม Care (รายจังหวัดแยก 6 ประเภท / ทุกจังหวัดไม่แยกหมวด)

## Objective

เพิ่ม API สำหรับฝั่ง Staff เพื่อดึงตัวชี้วัดเงินช่วยเหลือของเคสที่ **ส่งต่อกระทรวงแล้ว** โดยกรองด้วย **จังหวัด (จาก Address)** + **ปีงบประมาณ (จากวันที่เปลี่ยนสถานะเป็นช่วยเหลือแล้ว)**

| เส้น | Method | ความหมาย |
|------|--------|----------|
| 1 | GET | ตัวชี้วัด **รายจังหวัด** — แสดงเงิน/จำนวนเคสแยกตามประเภทเงินทั้ง 6 ประเภท ของจังหวัดที่เลือก |
| 2 | GET | ตัวชี้วัด **ทุกจังหวัด** — แถวละจังหวัด (`case_count` + `total_money_amount` รวมทุกประเภทเงิน) ไม่แยกหมวด; ไม่ส่ง `province_id` = ครบทุกจังหวัดใน master |
| 3 | GET | **Export JSON แถวต่อเคส** — คืนรายการเคสที่เข้าเกณฑ์ให้ frontend map เข้าเทมเพลต Excel (ไม่สร้าง `.xlsx` ใน backend) |

## Background / Flow ที่เกี่ยวข้อง

### Domain ที่ใช้ซ้ำจากระบบปัจจุบัน

| หัวข้อ | แหล่งข้อมูลในระบบ | ค่า/ตารางสำคัญ |
|--------|-------------------|----------------|
| ส่งต่อกระทรวงแล้ว | `welfare_request_status` (สถานะล่าสุด) | `current_status_id = 11` (`CURRENT_STATUS_MSO_FORWARDED`) — ถูกตั้งอัตโนมัติเมื่อ `POST mso-forward` ด้วย `send_channel = "ministry"` |
| ช่วยเหลือแล้ว | `welfare_request_status` + `applicants.process_completed_at` | `current_status_id = 4` (`CURRENT_STATUS_AID_COMPLETED`) |
| ประเภทเงินพม Care (6) | `type_money_category` + `applicants.type_money_category_id` | id 1–6 (สป. / ดย. / พก. / ผส. / พส. / สค.) |
| จำนวนเงินที่ช่วยเหลือ | `case_regulation_choice.money_amount` | join ผ่าน `case_handling` (หน้า 11) |
| จังหวัด | Address → geo | `Address` (แถวแรกต่อ applicant) หรือ fallback `Person.sub_district_postcode_id` → จังหวัด — รูปแบบเดียวกับ `staff_digest_summary._province_applicants_subquery` |
| ปีงบประมาณไทย / รอบงบประมาณ | `app/utils/budget_year.py` | รอบงบ **1 ตุลาคม – 30 กันยายน** (Asia/Bangkok) — ดูรายละเอียดด้านล่าง |

### รอบงบประมาณ (ปีงบประมาณไทย)

ระบบใช้ **ปีงบประมาณไทย** ไม่ใช่ปีปฏิทิน (ม.ค.–ธ.ค.)

| รายการ | กำหนด |
|--------|--------|
| วันเริ่มรอบ | **1 ตุลาคม** เวลา `00:00:00` (Asia/Bangkok) |
| วันสิ้นรอบ | **30 กันยายน** เวลา `23:59:59.999999` (Asia/Bangkok) ของปีถัดไป |
| ค่าที่ส่งใน API | `budget_year` = ปี พ.ศ. ของรอบนั้น |
| แหล่งวันที่จัดเข้าปีงบ | `aided_at` = วันเปลี่ยนสถานะเป็น **ช่วยเหลือแล้ว** (status 4) |
| Utility ในระบบ | `thai_fiscal_year()`, `thai_fiscal_year_bounds()` ใน `app/utils/budget_year.py` |

#### กฎแปลงวันที่ → ปีงบ พ.ศ.

```
ถ้า month(aided_at) >= 10   # ต.ค. พ.ย. ธ.ค.
  → budget_year = ค.ศ. ของวันที่ + 544
ถ้า month(aided_at) <= 9    # ม.ค. … ก.ย.
  → budget_year = ค.ศ. ของวันที่ + 543
```

#### ตัวอย่างรอบงบ (อ้างอิงปีงบ 2568)

| รอบงบ พ.ศ. | เริ่ม (รวม) | สิ้นสุด (รวม) | ช่วงวันที่ `aided_at` ที่นับ |
|------------|-------------|---------------|------------------------------|
| **2568** | 1 ต.ค. 2024 | 30 ก.ย. 2025 | `[2024-10-01 00:00:00+07, 2025-09-30 23:59:59.999999+07]` |
| **2569** | 1 ต.ค. 2025 | 30 ก.ย. 2026 | `[2025-10-01 00:00:00+07, 2026-09-30 23:59:59.999999+07]` |
| **2567** | 1 ต.ค. 2023 | 30 ก.ย. 2024 | `[2023-10-01 00:00:00+07, 2024-09-30 23:59:59.999999+07]` |

#### ตัวอย่างขอบเขตวันที่ (boundary)

| `aided_at` (Bangkok) | ปีงบที่จัดเข้า | เหตุผล |
|----------------------|----------------|--------|
| 2024-09-30 23:59 | **2567** | ยังอยู่ก่อนเปิดรอบ 2568 |
| 2024-10-01 00:00 | **2568** | วันแรกของรอบ |
| 2025-01-15 12:00 | **2568** | อยู่ใน ม.ค.–ก.ย. ของปี ค.ศ. ถัดไป |
| 2025-09-30 23:59 | **2568** | วันสุดท้ายของรอบ |
| 2025-10-01 00:00 | **2569** | เปิดรอบใหม่ |

#### วิธี filter ใน SQL (แนะนำ)

อย่าคำนวณ `thai_fiscal_year()` ทีละแถว — แปลง `budget_year` เป็นช่วงวันที่แล้วเทียบครั้งเดียว:

```
budget_year = 2568
→ fiscal_start = 2024-10-01 00:00:00+07:00
→ fiscal_end   = 2025-09-30 23:59:59.999999+07:00

WHERE COALESCE(aided_at, process_completed_at)
      BETWEEN fiscal_start AND fiscal_end
```

สูตรหาขอบเขตจากปี พ.ศ. (สำหรับ helper ใหม่ใน `budget_year.py`):

```
# budget_year เป็น พ.ศ. เช่น 2568
start_ce_year = budget_year - 544   # 2568 → 2024
fiscal_start  = datetime(start_ce_year,     10, 1,  0, 0, 0, tzinfo=Asia/Bangkok)
fiscal_end    = datetime(start_ce_year + 1,  9, 30, 23, 59, 59, 999999, tzinfo=Asia/Bangkok)
```

#### สิ่งที่ต้องระวัง

- **ห้ามใช้ปีปฏิทิน** (1 ม.ค. – 31 ธ.ค.) ในการกรองตัวชี้วัดนี้  
- timezone ต้องเป็น **Asia/Bangkok** — วันที่เก็บเป็น UTC ต้องแปลงก่อนเทียบช่วง  
- เคสที่ `aided_at` อยู่คนละรอบกับวันส่งต่อกระทรวง (status 11) → **จัดปีงบตามวันช่วยเหลือแล้วเท่านั้น** ไม่ใช่วันส่งต่อกระทรวง  
- response ควรคืน `budget_year`, `fiscal_start`, `fiscal_end` ให้ frontend แสดงช่วงรอบชัดเจน

### ประเภทเงินพม Care ทั้ง 6 ประเภท

| id | ชื่อย่อ | ชื่อ |
|----|---------|------|
| 1 | สป. | เงินอุดหนุนเพื่อช่วยเหลือผู้ประสบปัญหาทางสังคมกรณีฉุกเฉิน |
| 2 | ดย. | เงินสงเคราะห์เด็กในครอบครัวยากจน |
| 3 | พก. | เงินสงเคราะห์และฟื้นฟูสมรรถภาพคนพิการ |
| 4 | ผส. | เงินสงเคราะห์ผู้สูงอายุในภาวะยากลำบาก |
| 5 | พส. | เงินอุดหนุนเงินสงเคราะห์ผู้มีรายได้น้อยและผู้ไร้ที่พึ่ง |
| 6 | สค. | เงินสงเคราะห์สตรีหรือครอบครัวที่ประสบปัญหาทางสังคม |

### Business rules ที่ตกลงใช้ในงานนี้

```
เคสที่นับได้ =
  สถานะล่าสุดตาม `case_status`:
    aided     → = 4 (ช่วยเหลือแล้ว)
    forwarded → = 11 (ส่งต่อกระทรวง)
  AND มีช่วงเวลา "ช่วยเหลือแล้ว" ที่อยู่ในปีงบประมาณที่ระบุ
  AND จังหวัดของเคสตรงกับ filter (effective_province — ดูกฎ สค. ด้านล่าง)

เงินที่ช่วยเหลือ =
  SUM(case_regulation_choice.money_amount)
  จัดกลุ่มด้วย applicants.type_money_category_id

ปีงบประมาณ =
  จัดเข้าตามรอบงบไทย 1 ตุลาคม – 30 กันยายน (Asia/Bangkok)
  จาก aided_at = เวลาที่เปลี่ยนสถานะเป็น ช่วยเหลือแล้ว (status 4)
  → ดูรายละเอียดในหัวข้อ "รอบงบประมาณ (ปีงบประมาณไทย)"
```

### กฎจัดจังหวัด สค. → จังหวัดแม่ (DWF)

ที่อยู่เคสยัง resolve จาก Address แถวแรก + Person fallback เหมือนเดิม จากนั้น:

| ประเภทเงิน | จังหวัดที่นับ (`effective_province`) |
|------------|--------------------------------------|
| 1–5 (สป. ดย. พก. ผส. พส.) | จังหวัดจากที่อยู่เคส (ไม่ remap) |
| 6 สค. | ถ้าที่อยู่ในกลุ่ม DWF → `default_province` / `mother_province_id` จาก `drpod_dwf.json`; นอกกลุ่ม → ที่อยู่เดิม |

- จังหวัดลูก **ไม่นับซ้ำ** เคส สค. ที่ remap ไปแม่  
- ใช้กับทั้ง `/by-province` และ `/nationwide` (filter / `GROUP BY` ใช้ `effective_province`)  
- nationwide left-fill ยังครบทุกจังหวัดใน master — แถวจังหวัดลูกได้เงิน สค. = 0 (เงินไปอยู่แถวแม่)

#### ตัวอย่างแม่–ลูก

| กลุ่ม | จังหวัดแม่ | จังหวัดลูก (ตัวอย่าง) |
|-------|------------|------------------------|
| บ้านสองแคว พิษณุโลก | **65** พิษณุโลก | **66** พิจิตร, 60 นครสวรรค์ |

- ที่อยู่พิจิตร (66) + สค. → นับที่พิษณุโลก (65)  
- ที่อยู่พิจิตร (66) + สป. → นับที่พิจิตร (66)  
- `by-province?province_id=66` → ไม่เห็นเคส สค. ที่อยู่พิจิตรในหมวด สค.

### แหล่ง `aided_at` (ปีงบประมาณ) — ลำดับความสำคัญ

1. **หลัก:** เวลาแถวแรกใน `welfare_request_status` ที่ `current_status_id = 4`  
   → ใช้ `MIN(created_at)` (หรือแถวแรกตาม id ASC) ของสถานะ 4 ต่อ applicant  
2. **Fallback:** `applicants.process_completed_at` (ถูกตั้งเมื่อเข้าสถานะช่วยเหลือแล้ว / หยุดนับ SLA)  
3. เคสที่ **ไม่มี** ทั้งสองค่า → **ไม่นับ** ในปีงบใด ๆ (หรือแยกเป็น `unknown_budget_year` ถ้าต้องการ audit — default: ไม่นับ)

> หมายเหตุ: ไม่ใช้ `COALESCE(process_completed_at, latest_status.created_at)` แบบ CARE history โดยตรง เพราะเมื่อสถานะล่าสุดเป็น 11 แล้ว `latest_status.created_at` จะเป็นวันส่งต่อกระทรวง ไม่ใช่วันช่วยเหลือแล้ว

### ขอบเขตเคสที่นับ

- นับเฉพาะเคสที่ **สถานะล่าสุด = 11** (ส่งต่อกระทรวงแล้ว)  
- ไม่นับเคสที่ยังอยู่สถานะ 4 (ช่วยเหลือแล้ว) แต่ยังไม่ส่งต่อกระทรวง  
- ไม่นับ `send_channel = "logbook"` ที่ไม่ได้เปลี่ยนสถานะเป็น 11  
- `money_amount` เป็น null → นับเคสได้ แต่เงินบวกเป็น 0 (หรือไม่บวกใน SUM — ใช้ `COALESCE(money_amount, 0)`)  
- เคสที่ไม่มี `type_money_category_id` → ไม่จัดเข้า 6 ประเภท (optional: รวมใน bucket `uncategorized` สำหรับ debug — default: ไม่รวมใน response หลัก แต่คืน `excluded_uncategorized_count` ได้)

### สิ่งที่มีอยู่แล้ว vs ยังไม่มี

| มีแล้ว | ยังไม่มี |
|--------|----------|
| master 6 ประเภทเงิน, status 4/11, money_amount, province join, `thai_fiscal_year` | API รวมตัวชี้วัดเงินตามจังหวัด/ปีงบ |
| `GET /v1/case_for_staff/status-summary` (นับ bucket สถานะ ไม่ใช่เงิน) | endpoint indicators ใน case-service / BFF |
| dashboard-service (จำนวนคำร้อง ไม่ใช่ SUM เงินช่วยเหลือหลังส่งกระทรวง) | — |

## Scope (ไฟล์ที่แก้ใน Phase นี้)

### case-service (แหล่งข้อมูลจริง)

| ชั้น | ไฟล์ (เสนอ) | งาน |
|------|-------------|-----|
| Service | `app/services/indicators_summary.py` (ใหม่) | query รวม + reuse province subquery pattern |
| Schema | `app/schemas/indicators.py` (ใหม่) | request/response DTO |
| API | `app/api/v1/indicators.py` (ใหม่) หรือเพิ่มใน `case_for_staff.py` | 2 endpoints |
| Router | `app/main.py` / register router | mount `/v1/indicators` |
| Utils | `app/utils/budget_year.py` | reuse `thai_fiscal_year` / `thai_fiscal_year_bounds` (อาจเพิ่ม helper จากปี พ.ศ. → start/end) |

### bff-vsmartcare (proxy ให้ Staff UI)

| ชั้น | ไฟล์ (เสนอ) | งาน |
|------|-------------|-----|
| Schema | `app/indicator_schema.py` (ใหม่) | mirror response จาก case-service |
| Routes | `app/main.py` | proxy 2 GET → case-service |
| Auth | `app/middleware.py` | ถ้าใช้ prefix ใหม่ `/v1/indicators` ต้องเพิ่มใน `_STAFF_COMPAT_PATH_PREFIXES` |
| OpenAPI | `_TAGS` ใน `main.py` | tag `indicators` |

### นอก scope (Phase นี้)

- ไม่แก้ dashboard-service  
- ไม่ทำ export Excel / chart  
- ไม่เปลี่ยน workflow สถานะหรือ MSO forward  
- ไม่ทำ cache/materialized view (ทำได้ใน phase ถัดไปถ้า query ช้า)

## Root cause / งานที่ต้องแก้

Staff ต้องการตัวเลขตัวชี้วัดเงินช่วยเหลือหลังส่งต่อกระทรวง แยกตามจังหวัด/ปีงบ (เส้น 1 แยก 6 ประเภทเงินในจังหวัดเดียว, เส้น 2 ทุกจังหวัดไม่แยกหมวด) แต่ระบบมีเฉพาะ:

1. list/detail เคส (`/v1/case_for_staff`) — ไม่ aggregate  
2. `status-summary` — นับจำนวนตาม bucket สถานะ ไม่เกี่ยวกับเงิน  
3. CARE history / regulations — นับต่อบุคคล ไม่ใช่ตัวชี้วัดระดับจังหวัด  

จึงต้องสร้าง **aggregate read API** ใหม่ที่ case-service เป็นแหล่งความจริง และ BFF เป็น pass-through ตาม pattern เดิม

## แนวทางที่เลือก

### สถาปัตยกรรม

```
Staff UI
  → BFF  GET /api-vsmartcare/v1/indicators/...
  → case-service  GET /v1/indicators/...
  → PostgreSQL (aggregate SQL)
```

- คำนวณทั้งหมดที่ **case-service** (BFF ไม่รวม logic)  
- pattern เดียวกับ `status-summary` / staff digest province join  
- เส้น 1 คืนครบ 6 ประเภทเงินเสมอ แม้เงินเป็น 0 (left-fill กับ master `type_money_category` id 1–6)  
- เส้น 2 คืนครบทุกจังหวัดเสมอ แม้เงินเป็น 0 (left-fill กับ master `province`) — **ไม่แยกหมวดเงิน**

### Endpoint design (เสนอ)

#### เส้นที่ 1 — รายจังหวัด

```
GET /v1/indicators/by-province
  ?province_id=<int>          # required
  &budget_year=<int>          # required — ปีงบ พ.ศ. เช่น 2568
  &case_status=aided|forwarded  # optional, default=aided
                                # aided=ช่วยเหลือแล้ว (4), forwarded=ส่งต่อแล้ว (11)
```

**Response (ร่าง):**

```json
{
  "province_id": 10,
  "province_name": "กรุงเทพมหานคร",
  "budget_year": 2568,
  "fiscal_start": "2024-10-01T00:00:00+07:00",
  "fiscal_end": "2025-09-30T23:59:59.999999+07:00",
  "filter": {
    "case_status": "aided",
    "latest_status_id": 4,
    "aided_status_id": 4
  },
  "items": [
    {
      "type_money_category_id": 2,
      "name": "เงินสงเคราะห์เด็กในครอบครัวยากจน",
      "name_acronym": "ดย.",
      "name_acrovym_eng": "dcy",
      "case_count": 3,
      "total_money_amount": "9000.00",
      "by_regulation": [
        {
          "regulation_id": 50,
          "regulation_name": "ระเบียบกรมประชาสงเคราะห์ ว่าด้วยการสงเคราะห์เด็ก...",
          "regulation_short_name": "เงินสงเคราะห์เด็กในครอบครัวยากจน",
          "case_count": 3,
          "total_money_amount": "9000.00",
          "by_approver_sdshv": [
            {
              "user_sdshv": "sw.user01",
              "case_count": 2,
              "total_money_amount": "6000.00"
            },
            {
              "user_sdshv": null,
              "case_count": 1,
              "total_money_amount": "3000.00"
            }
          ]
        }
      ]
    }
  ],
  "totals": {
    "case_count": 40,
    "total_money_amount": "520000.00"
  }
}
```

แต่ละประเภทเงินมี `by_regulation[]` (จาก `announcement_regulations`) และภายในมี `by_approver_sdshv[]` (จาก `approve_case.user_sdshv` แถวล่าสุดที่ `approve_status=true`; `null` = ไม่ระบุ) — ใช้ตรวจ DCY/ดย. และประเภทอื่นได้เช่นกัน

#### เส้นที่ 2 — ทุกจังหวัด (ไม่แยกหมวดเงิน)

```
GET /v1/indicators/nationwide
  ?budget_year=<int>          # required
  &province_id=<int>          # optional, ซ้ำได้หลายค่า — ถ้าระบุคืนเฉพาะจังหวัดที่เลือก; ไม่ส่ง = ครบทุกจังหวัด
```

**Response:**

```json
{
  "budget_year": 2568,
  "province_ids": null,
  "fiscal_start": "2024-10-01T00:00:00+07:00",
  "fiscal_end": "2025-09-30T23:59:59.999999+07:00",
  "filter": {
    "case_status": "aided",
    "latest_status_id": 4,
    "aided_status_id": 4
  },
  "items": [
    {
      "province_id": 10,
      "province_name": "กรุงเทพมหานคร",
      "case_count": 40,
      "total_money_amount": "520000.00"
    },
    {
      "province_id": 11,
      "province_name": "สมุทรปราการ",
      "case_count": 0,
      "total_money_amount": "0"
    }
  ],
  "totals": {
    "case_count": 40,
    "total_money_amount": "520000.00"
  }
}
```

กฎนับเคสของเส้น 2 เหมือนเส้น 1 (status ล่าสุด = 11, aided_at ในปีงบ, ประเภทเงิน id 1–6) แต่ **GROUP BY จังหวัด** แล้วรวมเงินทุกประเภทในแถวนั้น — ไม่คืน `type_money_category_id`

#### เส้นที่ 3 — Export JSON แถวต่อเคส

```
GET /v1/indicators/export
  ?budget_year=<int>                    # required พ.ศ.
  &province_id=<int>                    # optional, ซ้ำได้ — กรองด้วย effective_province
  &type_money_category_id=<int>         # optional, ซ้ำได้ — ไม่ส่ง = 1–6
  &regulation_id=<int>                  # optional, ซ้ำได้ — ไม่ส่ง = ทุกระเบียบ
```

BFF: `GET /api-vsmartcare/v1/indicators/export?...` proxy JSON แบบเส้น indicators อื่น

กฎนับเคสเหมือนเส้น 1–2 (status ล่าสุด = 11, `aided_at` ในปีงบ, ประเภทเงิน 1–6, สค. → `effective_province` ตาม DWF)  
เรียง `effective_province_id`, `applicant_id` — **ไม่มี pagination ใน phase นี้**

**คอลัมน์ที่คืนใน `items[]` (มีใน DB):**

| กลุ่ม | ฟิลด์ JSON | แหล่ง |
|-------|------------|--------|
| เคส | `applicant_id`, `case_number` | `applicants` |
| บุคคล | `first_name`, `last_name`, `cid`, `gender`, `birth_date`, `age` | `persons` + `applicants.age` |
| ติดต่อ | `mobile_phone` | `applicants.mobile_phone` |
| ที่อยู่ | `house_number`, `house_moo`, `alley`, `road`, `sub_district_name`, `district_name`, `address_province_id`, `address_province_name` | Address แถวแรก + geo |
| จังหวัดที่นับ | `effective_province_id`, `effective_province_name` | DWF remap สค. |
| เศรษฐกิจ | `occupation`, `monthly_income` | `economic_infos` แถวแรก (id ASC) |
| ปัญหา | `family_distress` | `applicants.family_distress` |
| หมวด/ระเบียบ | `type_money_category_id`, `type_money_name`, `type_money_name_acronym`, `regulation_id`, `regulation_name`, `regulation_short_name` | category + `announcement_regulations` |
| เงิน | `help_kind`, `money_amount`, `aided_at` | `case_regulation_choice` + aided_at |
| Staff | `sw_user_sdshv` | `case_handling.sw_user_sdshv` |

**ไม่คืน (FE ปล่อยว่างในเทมเพลต):** ลำดับ, รหัสหน่วยงาน, ชื่อหน่วยงาน, เลขที่รับ, วันที่รับ, ผลการพิจารณา, และฟิลด์อื่นที่ไม่มีใน DB

**Response (ร่าง):**

```json
{
  "budget_year": 2568,
  "fiscal_start": "...",
  "fiscal_end": "...",
  "filter": {
    "case_status": "forwarded",
    "latest_status_id": 11,
    "aided_status_id": 4,
    "province_ids": [65],
    "type_money_category_ids": [6],
    "regulation_ids": [12]
  },
  "items": [
    {
      "applicant_id": 1,
      "case_number": "...",
      "first_name": "...",
      "last_name": "...",
      "cid": "...",
      "gender": "...",
      "birth_date": "1990-01-01",
      "age": 35,
      "mobile_phone": "...",
      "house_number": "...",
      "house_moo": "...",
      "alley": null,
      "road": null,
      "sub_district_name": "...",
      "district_name": "...",
      "address_province_id": 66,
      "address_province_name": "พิจิตร",
      "effective_province_id": 65,
      "effective_province_name": "พิษณุโลก",
      "occupation": "...",
      "monthly_income": "5000.00",
      "family_distress": "...",
      "type_money_category_id": 6,
      "type_money_name": "...",
      "type_money_name_acronym": "สค.",
      "regulation_id": 12,
      "regulation_name": "...",
      "regulation_short_name": "...",
      "help_kind": "money",
      "money_amount": "5000.00",
      "aided_at": "2025-03-01T...",
      "sw_user_sdshv": "sw.user01"
    }
  ],
  "totals": { "case_count": 1, "total_money_amount": "5000.00" }
}
```

- `money_amount` null → นับเคสได้ แต่เงินใน totals บวกเป็น 0  
- ไม่มี `regulation_choice` → ยังโผล่ได้เมื่อไม่กรอง `regulation_id` (ฟิลด์ระเบียบ/เงินเป็น null)  
- ไม่มี `economic_infos` → `occupation` / `monthly_income` เป็น null  
- ตัวอย่าง สค. ลูก→แม่: ที่อยู่พิจิตร (66) + สค. → `address_province_id=66`, `effective_province_id=65`

### Query plan (ระดับ logic)

```
1) aided_at_sq =
     SELECT applicant_id,
            MIN(created_at) AS aided_at
     FROM welfare_request_status
     WHERE current_status_id = 4
     GROUP BY applicant_id

2) latest_status_sq =
     row_number() OVER (partition by applicant_id
                        ORDER BY updated_at DESC, id DESC)
     → rn = 1 และ current_status_id = 11

3) province_sq =
     Address แถวแรก (id ASC) COALESCE Person.sub_district_postcode_id
     → join geo → address_province_id
     → effective_province_id = CASE สค. (type 6) ใน DWF map แล้วใช้ mother นอกนั้นใช้ address

4) money_sq =
     Applicant
       JOIN CaseHandling ON ...
       JOIN CaseRegulationChoice ON case_handling_id
     → money_amount

5) WHERE
     latest_status = 11
     AND COALESCE(aided_at, process_completed_at) BETWEEN fiscal_start AND fiscal_end
     AND type_money_category_id IN (1..6)
     AND effective_province_id IN (...)   # ถ้ามี filter (ไม่ใช่ที่อยู่ดิบ)

6) เส้น 1: GROUP BY type_money_category_id → COUNT(*), SUM(COALESCE(money_amount, 0))
   เส้น 2: GROUP BY effective_province_id → COUNT(*), SUM(COALESCE(money_amount, 0))
           แล้ว left-fill กับ master province ให้ครบทุกจังหวัด
```

แนะนำ filter ปีงบด้วย **ช่วงวันที่** (`fiscal_start`/`fiscal_end`) ใน SQL แทนคำนวณ `thai_fiscal_year` ทีละแถว เพื่อใช้ index บน `created_at` / `process_completed_at` ได้ดีขึ้น

### BFF mapping

| BFF | case-service |
|-----|--------------|
| `GET /api-vsmartcare/v1/indicators/by-province` | `GET /v1/indicators/by-province` |
| `GET /api-vsmartcare/v1/indicators/nationwide` | `GET /v1/indicators/nationwide` |
| `GET /api-vsmartcare/v1/indicators/export` | `GET /v1/indicators/export` |

Auth: Bearer JWT หรือ trusted `X-API-Key` (pattern เดียว Staff routes อื่น) — **ไม่เช็ค role ที่ BFF**

### Dependency / ผลข้างเคียง

- อ่านอย่างเดียว — ไม่กระทบ workflow สถานะ / การจ่ายเงิน  
- Performance: aggregate ข้าม address + status log อาจช้าในจังหวัดใหญ่ → ควรมี index ที่มีอยู่แล้วบน `welfare_request_status(applicant_id)`, `applicants(type_money_category_id)`, และพิจารณา composite/index เพิ่มถ้าจำเป็นหลังวัด  
- ความถูกต้องของตัวเลขพึ่งพาข้อมูลครบ: ส่งต่อกระทรวงจริง (status 11), มี status 4 หรือ `process_completed_at`, มี address/จังหวัด, มี `money_amount`  
- Dashboard-service และ status-summary **ไม่ถูกแทนที่** — ใช้คนละ use case

## ขั้นตอนงาน (todos)

### Phase A — วิเคราะห์ยืนยัน (ก่อนโค้ด)

- [x] ยืนยันกับ Product: เส้น 2 คือ **nationwide ครบทุกจังหวัด ไม่แยกหมวดเงิน** (เส้น 1 ยังแยก 6 ประเภทในจังหวัดเดียว)  
- [ ] ยืนยัน `aided_at` = แถวแรกของ status 4 (ไม่ใช่ `process_completed_at` อย่างเดียว)  
- [ ] ยืนยันนับเฉพาะ status ล่าสุด = 11 (ไม่รวม status 4 ที่ยังไม่ส่งกระทรวง)  
- [ ] ยืนยันเงินมาจาก `case_regulation_choice.money_amount` เท่านั้น (ไม่รวมสิ่งของ / ไม่ใช้ payment อื่น)  
- [ ] ยืนยันจังหวัดใช้ Address แถวแรก + fallback Person (เหมือน digest) หรือระบุประเภทที่อยู่ (ทะเบียน/ปัจจุบัน)

### Phase B — case-service

- [ ] เพิ่ม helper ปีงบจากปี พ.ศ. → `(fiscal_start, fiscal_end)` ใน `budget_year.py`  
  - input: `budget_year` พ.ศ. เช่น 2568  
  - output: `fiscal_start = 1 ต.ค. (ค.ศ. = พ.ศ.-544)`, `fiscal_end = 30 ก.ย. ปีถัดไป`  
  - timezone Asia/Bangkok เสมอ  
- [ ] สร้าง `services/indicators_summary.py`  
  - reuse / extract province join จาก `staff_digest_summary` ถ้าเหมาะสม  
  - query aided_at จาก status 4  
  - filter latest status 11  
  - filter ปีงบด้วย `aided_at BETWEEN fiscal_start AND fiscal_end` (รอบ 1 ต.ค. – 30 ก.ย.)  
  - เส้น 1 group by `type_money_category_id`  
  - เส้น 2 group by `province_id` (ไม่แยกหมวดเงิน) แล้ว left-fill ครบทุกจังหวัด  
- [ ] สร้าง schemas response  
  - เส้น 1: `items` ครบ 6 ประเภท + `totals`  
  - เส้น 2: `items` ครบทุกจังหวัด (`province_id`, `province_name`, `case_count`, `total_money_amount`) + `totals`  
- [ ] สร้าง endpoints  
  - `GET /v1/indicators/by-province`  
  - `GET /v1/indicators/nationwide`  
- [ ] validate: province ไม่พบ → 404; `budget_year` ผิดรูปแบบ → 422  
- [ ] unit/integration test: seed เคสหลายสถานะ/หลายจังหวัด/ข้ามปีงบ แล้วตรวจ SUM

### Phase C — bff-vsmartcare

- [ ] เพิ่ม `indicator_schema.py`  
- [ ] proxy 2 routes ใน `main.py` + tag `indicators`  
- [ ] เพิ่ม `/v1/indicators` ใน staff auth path prefixes  
- [ ] smoke test ผ่าน BFF ด้วย Bearer

### Phase D — ตรวจรับ

- [ ] เทียบตัวเลขมือกับ SQL ตรง ๆ ใน staging  
- [ ] เคสขอบ: ไม่มีเงิน, ไม่มีประเภทเงิน, ไม่มี address, มี status 4 แต่ไม่มี 11, ส่ง logbook  
- [ ] เอกสาร OpenAPI / ตัวอย่าง response ให้ frontend

## การทดสอบ

| เคส | คาดหวัง |
|-----|---------|
| เคส status ล่าสุด = 11, มี status 4 ในปีงบ 2568, จังหวัด A, ประเภท 1, เงิน 10,000 | เส้น 1 จังหวัด A ปี 2568 → ประเภท 1 `case_count+1`, `total+10000` |
| เคสเดียวกัน เส้น 2 nationwide ปี 2568 | แถวจังหวัด A `case_count+1`, `total+10000` (ไม่แยกประเภทเงิน) |
| เคส status ล่าสุด = 4 (ยังไม่ส่งกระทรวง) | **ไม่นับ** |
| เคส status 11 แต่ aided_at อยู่นอกปีงบ | **ไม่นับ** ในปีนั้น |
| เคส status 11, aided_at ปี 2568, จังหวัด B | เส้น 1 จังหวัด A → **ไม่นับ**; nationwide → นับในแถวจังหวัด B (จังหวัด A ยังโชว์แถวเงิน 0) |
| `money_amount` null | นับเคส, เงิน +0 |
| ไม่มี `type_money_category_id` | ไม่เข้า 6 ประเภท (ตาม rule ที่ตกลง) |
| MSO `logbook` (ไม่เป็น status 11) | **ไม่นับ** |
| ปีงบขอบเขต 1 ต.ค. / 30 ก.ย. | aided_at 1 ต.ค. 2024 → ปี 2568; 30 ก.ย. 2025 → ปี 2568; 1 ต.ค. 2025 → ปี 2569 |
| aided_at = 2024-09-30 (ก่อนเปิดรอบ 2568) | query `budget_year=2568` → **ไม่นับ**; `budget_year=2567` → นับ |
| aided_at = 2025-09-30 23:59, status 11 | `budget_year=2568` → **นับ** (วันสุดท้ายของรอบ) |
| aided_at ปีงบ 2568 แต่ส่งต่อกระทรวง (status 11) หลัง 1 ต.ค. 2025 | ยังนับใน `budget_year=2568` (ยึดวันช่วยเหลือแล้ว ไม่ยึดวันส่งต่อ) |
| ที่อยู่ลูก (พิจิตร 66) + สค. | นับที่แม่ (พิษณุโลก 65); `by-province?province_id=66` → สค. ไม่รวมเคสนั้น |
| ที่อยู่ลูก (66) + สป. | นับที่ลูก (66) ตามเดิม |
| nationwide: สค. ที่อยู่ลูก | รวมเงินสค. ที่แถวแม่; แถวลูกได้ สค. ส่วนนี้ = 0 (ไม่นับซ้ำ) |
| export: สค. ที่อยู่พิจิตร (66) | แถวเคสมี `address_province_id=66`, `effective_province_id=65` |
| export: `money_amount` null | นับใน `totals.case_count`; `totals.total_money_amount` +0 |
| export: กรอง `type_money_category_id=6` | คืนเฉพาะเคส สค. |
| export: กรอง `regulation_id` | ไม่คืนเคสที่ไม่มี regulation_choice / คนละระเบียบ |

## Constraints

- อ่านอย่างเดียว — ไม่แก้ข้อมูลเคส  
- ใช้**รอบงบประมาณไทย 1 ตุลาคม – 30 กันยายน** (Asia/Bangkok) — **ห้าม**ใช้ปีปฏิทิน ม.ค.–ธ.ค.  
- `budget_year` ใน query = ปี พ.ศ.; filter จริงด้วยช่วง `fiscal_start`/`fiscal_end`  
- ประเภทเงิน = `type_money_category` id 1–6 เท่านั้น (ไม่ใช้ `type_money` อุดหนุน/เฉพาะกิจ)  
- Province resolution ต้องสอดคล้องกับ staff list/digest เพื่อไม่ให้ตัวเลขคลาดจากรายการเคส  
- BFF เป็น proxy บาง — ไม่คำนวณซ้ำ  
- ไม่ commit secrets / ไม่เปิด endpoint โดยไม่ผ่าน Staff auth pattern เดิม

## Expected Output

1. case-service: 2 GET endpoints ภายใต้ `/v1/indicators/...` พร้อม schema + service aggregate  
2. bff-vsmartcare: 2 GET proxy ภายใต้ `/api-vsmartcare/v1/indicators/...`  
3. เส้น 1 คืนครบ 6 ประเภทเงิน + totals; เส้น 2 คืนครบทุกจังหวัด (ไม่แยกหมวดเงิน) + totals  
4. Filter ทำงานตาม: จังหวัดจาก Address, ปีงบจากเวลาเข้าสถานะช่วยเหลือแล้วตามรอบ **1 ต.ค. – 30 ก.ย.**, เคสเฉพาะส่งต่อกระทรวง (status 11)  
5. Response คืน `budget_year` + `fiscal_start` + `fiscal_end` ให้ frontend แสดงช่วงรอบงบ  
6. เอกสาร/ตัวอย่าง response สำหรับ frontend Staff  
7. ชุดทดสอบครอบคลุมเคสขอบตามตารางด้านบน รวม boundary 1 ต.ค. / 30 ก.ย.

## Open questions (ต้องปิดก่อนลงมือ Phase B)

1. **เส้น 2:** ปิดแล้ว — nationwide ครบทุกจังหวัด ไม่แยกหมวดเงิน (ไม่บังคับ `province_id`)  
2. **ที่อยู่:** ใช้ Address แถวแรก + Person fallback หรือบังคับประเภทที่อยู่ (ปัจจุบัน/ทะเบียน)?  
3. **สิ่งของ (`help_kind = things`):** นับใน `case_count` หรือตัดออก / นับเฉพาะ `help_kind = money`?  
4. **เคสไม่มีประเภทเงิน:** ซ่อน หรือคืน bucket แยก?  
5. **สิทธิ์ Staff:** จำกัดดูได้เฉพาะจังหวัดของตน (`staff_users.province_id`) ที่ case-service หรือปล่อยให้ frontend ส่ง `province_id` อย่างเดียว?

## Suggested path names (สรุปสั้น)

```
case-service:
  GET /v1/indicators/by-province?province_id=&budget_year=&case_status=
  GET /v1/indicators/nationwide?budget_year=&province_id=&case_status=
  GET /v1/indicators/export?budget_year=&province_id=&type_money_category_id=&regulation_id=&case_status=

bff-vsmartcare:
  GET /api-vsmartcare/v1/indicators/by-province?...
  GET /api-vsmartcare/v1/indicators/nationwide?...
  GET /api-vsmartcare/v1/indicators/export?...
```
