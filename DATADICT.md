# Data Dictionary

## สารบัญตาราง

| กลุ่ม | ตาราง |
|-------|--------|
| [ตัวตน](#1-ตัวตน) | `persons` · `applicants` · `applicant_submission_audit` |
| [ที่อยู่และเศรษฐกิจ](#2-ที่อยู่และเศรษฐกิจ) | `address` · `economic_infos` · `economic_income_sources` · `dependency_loads` |
| [ครัวเรือน](#3-ครัวเรือน) | `household_members` |
| [สวัสดิการที่ยื่น](#4-สวัสดิการที่ยื่น) | `welfare_histories` · `welfare_histories_detail` · `welfare_request_types` · `welfare_evidences` |
| [สถานะและตีกลับ](#5-สถานะและตีกลับ) | `welfare_request_status` · `case_data_edit_logs` · `review_field` · `welfare_review_comment` |
| [รับเรื่อง](#6-รับเรื่อง-intake) | `case_handling` · `case_help_beneficiaries` · `case_regulation_choice` · `case_payment` · `case_ktb_corporate` · `announcement_regulations` · `payment_method` |
| [คำวินิจฉัย](#7-คำวินิจฉัย) | `case_diagnosis` · `case_diagnosis_edit_history` |
| [บทความและอนุมัติ](#8-บทความและอนุมัติ) | `article` · `cover_document_batch` · `approve_case` |
| [เบิกจ่าย](#9-เบิกจ่าย) | `welfare_dda_ref` · `welfare_payment` · `file_payment` |
| [MSO](#10-mso) | `more_mso` · `type_send` · `send_data` |
| [สิทธิ์ / OCR / สำรวจ](#11-สิทธิ์--ocr--สำรวจ) | `screening_logs` · `welfare_request_consents` · `ocr_results` · `satisfaction_surveys` |
| [ภูมิศาสตร์](#12-ภูมิศาสตร์) | `province` · `districts` · `sub_districts` · `postcode` · `sub_districts_postcode` |
| [Admin / Staff](#13-admin--staff) | `admin_users` · `province_access_config` · `staff_users` · `security_audit_log` |
| [Lookup / Master data](#14-lookup--master-data) | ตาราง master ทั้งหมด + ค่า seed |

---

<div style="page-break-before: always;"></div>

## 1. ตัวตน

### ตาราง persons

ตารางสำหรับเก็บข้อมูลผู้ที่เข้าสู่ระบบจาก ThaiD

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `created_at` | timestamp | NO | | default `now()` |
| `updated_at` | timestamp | NO | | default `now()` + trigger |
| `prefix_id` | int | NO | FK → `prefix_type.id` | คำนำหน้า |
| `first_name` | varchar(255) | NO | | ชื่อ |
| `last_name` | varchar(255) | NO | | นามสกุล |
| `cid` | varchar(13) | NO | UK, IX | เลขบัตรประชาชน 13 หลัก |
| `birth_date` | date | NO | | วันเกิด |
| `sub_district_postcode_id` | int | YES | FK → `sub_districts_postcode.id`, IX | ที่อยู่จาก ThaiD |
| `province_id` | int | YES | FK → `province.id`, IX | จังหวัดที่ resolve ตอน login — ใช้เป็น submit gate |
| `gender` | varchar(50) | YES | | เพศ |
| `adr_moo` | varchar(50) | YES | | หมู่ จาก ThaiD |
| `adr_house_num` | varchar(100) | YES | | บ้านเลขที่ จาก ThaiD |

<div style="page-break-before: always;"></div>

### ตาราง applicants

ตารางสำหรับเก็บคำร้องของผู้ที่ยื่นคำร้องระบบ พม CARE

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |
| `persons_id` | int | NO | FK → `persons.id`, IX | เจ้าของคำร้อง |
| `case_number` | varchar(100) | YES | | เลขที่เคส (รูปแบบ `CASE-…`) |
| `requester_relation_id` | int | NO | FK → `requester_relation_type.id`, IX | ความสัมพันธ์ผู้ยื่นกับผู้รับสิทธิ์ |
| `marital_status_id` | int | NO | FK → `marital_status_types.id` | สถานภาพสมรส |
| `mobile_phone` | varchar(20) | YES | | มือถือ |
| `home_phone` | varchar(20) | YES | | โทรบ้าน/ที่ทำงาน |
| `fax_number` | varchar(20) | YES | | โทรสาร |
| `email_address` | varchar(255) | YES | | อีเมล (optional) |
| `is_government_officer` | bool | NO | | default `false` — เป็นข้าราชการ |
| `problem_details` | text | YES | | รายละเอียดปัญหา |
| `family_distress` | text | YES | | สภาพปัญหาความเดือดร้อน |
| `bank_name_id` | int | YES | FK → `bank_name.id`, IX | ธนาคารรับเงิน |
| `bank_account_no` | varchar(50) | YES | | เลขบัญชี |
| `bank_account_type_id` | int | YES | FK → `bank_account_type.id`, IX | ประเภทเงินฝาก (จาก OCR) |
| `bank_branch_name` | varchar(255) | YES | | ชื่อสาขา (จาก OCR — ไม่ใช่ lookup) |
| `type_money_category_id` | int | YES | FK → `type_money_category.id`, IX | ประเภทเงินช่วยเหลือ (สป./ดย. ฯลฯ) |
| `sw_explorer_sdshv` | varchar(255) | YES | | รหัสเจ้าหน้าที่สำรวจ |
| `time_count_process` | int | YES | | นับรอบประมวลผล |
| `process_started_at` | timestamptz | YES | | เริ่มนับ SLA |
| `process_sla_days` | int | YES | | จำนวนวัน SLA |
| `process_completed_at` | timestamptz | YES | | ปิดกระบวนการ |
| `is_emergency` | bool | NO | | default `false` |
| `is_existing_case` | bool | NO | | default `false` — พบรายเดิม |
| `age` | int | YES | | อายุ ณ วันยื่น |

<div style="page-break-before: always;"></div>

### ตาราง applicant_submission_audit

ตารางสำหรับการเก็บข้อมูลเพื่อใช้สำหรับการเช็ค รายใหม่ หรือ รายเดิม

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `applicant_id` | int | NO | PK, FK → `applicants.id` CASCADE | |
| `computed_at` | timestamptz | NO | | เวลาคำนวณ/รีเฟรช |
| `existing_case_source` | varchar(16) | YES | | แหล่งรายเดิมสำหรับ KTB: `VCARE` / `Legacy` / `Welfare` |
| `existing_case_detected_sources` | json | YES | | แหล่งที่พบ เช่น `["vcare_main","vsmart_main"]` |
| `existing_case_ref_id` | int | YES | | อ้างอิงเคสเดิม |
| `existing_case_province_id` | int | YES | | จังหวัดเคสเดิม |
| `existing_case_province_name` | varchar(255) | YES | | ชื่อจังหวัดเคสเดิม |
| `submission_province_id` | int | YES | | จังหวัดตอนยื่น |
| `submission_province_name` | varchar(255) | YES | | ชื่อจังหวัดตอนยื่น |
| `is_account_changed` | bool | YES | | เปลี่ยนบัญชีหรือไม่ |
| `require_ktb_corporate` | bool | NO | | default `true` |
| `require_ktb_reason` | varchar(32) | NO | | `NEW_CASE` \| `NONE` \| `ACCOUNT_CHANGED` \| `PROVINCE_CHANGED` |

---

<div style="page-break-before: always;"></div>

## 2. ที่อยู่และเศรษฐกิจ

### ตาราง address

ตารางใช้สำหรับการเก็บข้อมูลที่อยู่ปัจจุบันของผู้ยื่นคำร้อง

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `sub_district_postcode_id` | int | NO | FK → `sub_districts_postcode.id`, IX | ตำบล+รหัสไปรษณีย์ |
| `applicant_id` | int | NO | FK → `applicants.id`, IX | |
| `address_type_id` | int | NO | FK → `address_type.id` | ประเภทที่อยู่ |
| `alley` | varchar(255) | YES | | ตรอก |
| `sub_lane` | varchar(255) | YES | | ซอย |
| `house_name` | varchar(255) | YES | | ชื่อหมู่บ้าน/อาคาร |
| `road` | varchar(255) | YES | | ถนน |
| `house_moo` | varchar(50) | YES | | หมู่ |
| `house_number` | varchar(50) | YES | | บ้านเลขที่ |
| `mobile_phone` | varchar(20) | YES | | เบอร์ตามที่อยู่นี้ |
| `latitude` | varchar(50) | YES | | GPS |
| `longitude` | varchar(50) | YES | | GPS |
| `nearby_landmark` | varchar(500) | YES | | สถานที่ใกล้เคียงที่มองเห็นง่าย |

<div style="page-break-before: always;"></div>

### ตาราง economic_infos

เก็บข้อมูลสถานะทางเศรษฐกิจ

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |
| `applicant_id` | int | NO | FK → `applicants.id`, IX | |
| `housing_types_id` | int | YES | FK → `housing_types.id` | ลักษณะที่อยู่อาศัย |
| `housing_shelter` | text | YES | | สภาพที่อยู่อาศัย |
| `housing_types_rent` | numeric(12,2) | YES | | ค่าเช่า/เดือน เมื่อเป็นบ้านเช่า |
| `occupation_type_id` | int | YES | FK → `occupation_types.id` | อาชีพผู้ยื่น |
| `occupation` | varchar(255) | YES | | ข้อความอาชีพ (เมื่อ type=99 อื่น ๆ) |
| `monthly_income` | numeric(12,2) | YES | | รายได้/เดือน |
| `household_members` | int | YES | | จำนวนสมาชิกในครัวเรือน (ตัวเลขสรุป) |
| `family_occupation_type_id` | int | YES | FK → `occupation_types.id` | อาชีพหลักของครอบครัว |
| `family_occupation` | varchar(255) | YES | | ข้อความอาชีพครอบครัว (เมื่อ type=99) |

<div style="page-break-before: always;"></div>

### ตาราง economic_income_sources

Junction: แหล่งรายได้ของ ตาราง economic_infos

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `economic_id` | int | NO | PK, FK → `economic_infos.id` | |
| `income_source_type_id` | int | NO | PK, FK → `income_source_types.id` | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |
| `other_details` | varchar(500) | YES | | กรอกเมื่อเลือก «อื่น ๆ» (id=99) |

<div style="page-break-before: always;"></div>

### ตาราง dependency_loads

Junction: ภาระอุปการะ ใช้สำหรับเก็บข้อมุลกรณีเลือกการอุปการะมากกว่า 1 รายการ

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `applicant_id` | int | NO | PK, FK → `applicants.id` | |
| `dependency_type_id` | int | NO | PK, FK → `dependency_types.id` | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |
| `dependency_other_text` | varchar(500) | YES | | กรอกเมื่อเลือก «อื่น ๆ» (id=99) |

---

<div style="page-break-before: always;"></div>

## 3. ครัวเรือน

### ตาราง household_members

ตารางสำหรับเก็บข้อมูลสมาชิกในครัวเรือน

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |
| `applicant_id` | int | NO | FK → `applicants.id` CASCADE, IX | UNIQUE คู่กับ `seq` |
| `seq` | int | NO | UK คู่ `applicant_id` | ลำดับใน UI |
| `national_id` | varchar(13) | YES | | เลขบัตร (ถ้ามี) |
| `prefix_id` | int | YES | FK → `prefix_type.id` | |
| `prefix_other` | varchar(50) | YES | | คำนำหน้าอื่น ๆ |
| `first_name` | varchar(255) | NO | | ชื่อ |
| `last_name` | varchar(255) | NO | | สกุล |
| `date_of_birth` | date | YES | | วันเกิด — อายุคำนวณจากฟิลด์นี้ |
| `relation_to_applicant_id` | int | YES | FK → `household_member_relation_types.id` | ความสัมพันธ์ |
| `occupation_type_id` | int | YES | FK → `occupation_types.id` | อาชีพ |
| `occupation` | varchar(255) | YES | | ข้อความอาชีพ เมื่อ type=99 |
| `monthly_income` | numeric(12,2) | YES | | รายได้/เดือน |
| `physical_condition` | varchar(20) | NO | | default `normal` — `normal` / `disabled` / `chronic_illness` |
| `self_care` | bool | NO | | default `true` — ช่วยเหลือตนเองได้ |

---

<div style="page-break-before: always;"></div>

## 4. สวัสดิการที่ยื่น

### ตาราง welfare_histories

ตารางสำหรับเก็บข้อมูล ประวัติรับสวัสดิการ

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `applicant_id` | int | NO | PK, FK → `applicants.id` | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |
| `received_count` | int | YES | | จำนวนครั้งที่เคยได้รับ |
| `has_received_welfare` | bool | NO | | default `false` |
| `total_received_amount` | numeric(12,2) | YES | | รวมเป็นเงิน |

<div style="page-break-before: always;"></div>

### ตาราง welfare_histories_detail

Junction: ประเภทสวัสดิการที่เคยได้รับ กรณีมากกว่า 1 รายการ

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `welfare_history_id` | int | NO | PK, FK → `welfare_histories.applicant_id` | |
| `received_welfare_type_id` | int | NO | PK, FK → `received_welfare_types.id` | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |
| `received_other` | varchar(500) | YES | | เมื่อเลือก «อื่น ๆ» (id=99) |

<div style="page-break-before: always;"></div>

### ตาราง welfare_request_types

Junction: ประเภทความช่วยเหลือที่ต้องการ กรณีมากกว่า 1 รายการ

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `applicant_id` | int | NO | PK, FK → `applicants.id` | |
| `request_type_id` | int | NO | PK, FK → `request_types.id` | 1=เงิน, 2=สิ่งของ, 3=อื่น ๆ |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |
| `request_other_text` | varchar(500) | YES | | เมื่อ id=3 |
| `request_in_kind_text` | varchar(500) | YES | | เมื่อ id=2 |

<div style="page-break-before: always;"></div>

### ตาราง welfare_evidences

ตารางสำหรับเก็บหลักฐานแนบ เก็บ path ไฟล์อยู่ filesystem

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |
| `attachment_type_id` | int | NO | FK → `attachment_types.id` | ประเภทเอกสาร |
| `applicant_id` | int | NO | FK → `applicants.id`, IX | |
| `file_path` | varchar(1024) | NO | | path ใน storage |
| `file_original_name` | varchar(255) | YES | | ชื่อไฟล์ต้นทาง |
| `file_stored_name` | varchar(255) | YES | | ชื่อที่เก็บ |
| `file_size` | bigint | YES | | ไบต์ |
| `file_width` | int | YES | | px |
| `file_height` | int | YES | | px |
| `file_other_type_name` | varchar(255) | YES | | ชื่อประเภทเมื่อเป็น «อื่น ๆ» |
| `household_member_id` | int | YES | FK → `household_members.id` CASCADE, IX | `NULL` = ของผู้ยื่น, มีค่า = ของสมาชิก |

---

<div style="page-break-before: always;"></div>

## 5. สถานะและตีกลับ

### ตาราง welfare_request_status

ตาราง Log การเปลี่ยนสถานะ — append-only, แถวล่าสุด = สถานะปัจจุบัน

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `created_at` | timestamp | NO | | |
| `applicant_id` | int | NO | FK → `applicants.id`, IX | |
| `current_status_id` | int | NO | FK → `current_status.id` | |
| `updated_at` | timestamp | NO | | |
| `update_by_sdshv` | varchar(255) | YES | | รหัสเจ้าหน้าที่ |
| `remarks` | text | YES | | หมายเหตุ |

<div style="page-break-before: always;"></div>

### ตาราง case_data_edit_logs

ตารางสำหรับเก็บการเเก้ไขข้อมูลจากทางนักสังคมสงเคราะห์หรือผู้ทีมีสิทธิ์เเก้ไขข้อมูล

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `created_at` | timestamp | NO | | |
| `applicant_id` | int | NO | FK → `applicants.id` CASCADE, IX | |
| `current_status_id_at_edit` | int | NO | FK → `current_status.id` | snapshot สถานะตอนแก้ |
| `edit_by_sdshv` | varchar(255) | YES | | ผู้แก้ |
| `event_type` | varchar(32) | NO | | `section_edit` \| `survey_edit` |
| `sections` | varchar(32) | YES | | เช่น `"2,4"` — section ปสค.1 ที่แก้ |
| `remarks` | text | YES | | คำอธิบาย |

<div style="page-break-before: always;"></div>

### ตาราง review_field

ตารางสำหรับการเก็บ Master หัวข้อที่ส่งกลับให้ประชาชนแก้

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `name` | varchar(100) | NO | UK | รหัส field (ตรง frontend/VSmart) |
| `label` | varchar(255) | NO | | ข้อความแสดง |
| `step` | int | NO | | ขั้นฟอร์ม (0 = standalone หมายเหตุ) |
| `display_order` | int | NO | | ลำดับในขั้น |
| `is_active` | bool | NO | | default `true` — false = legacy ไม่โชว์ |

<div style="page-break-before: always;"></div>

### ค่า seed `review_field` (สถานะปัจจุบัน)

| id | name | label | step | display_order | is_active |
|----|------|-------|------|---------------|-----------|
| 1 | `current_address_house_no` | บ้านเลขที่ | 1 | 1 | true |
| 2 | `current_address_moo` | หมู่ที่ | 1 | 2 | true |
| 3 | `current_address_village` | ชื่อหมู่บ้าน | 1 | 3 | true |
| 4 | `current_address_alley` | ตรอก | 1 | 4 | true |
| 5 | `current_address_soi` | ซอย | 1 | 5 | true |
| 6 | `current_address_road` | ถนน | 1 | 6 | true |
| 7 | `current_address_province` | จังหวัด | 1 | 7 | true |
| 8 | `current_address_district` | อำเภอ/เขต | 1 | 8 | true |
| 9 | `current_address_subdistrict` | ตำบล/แขวง | 1 | 9 | true |
| 10 | `current_address_gps` | ตำแหน่ง GPS | 1 | 10 | true |
| 11 | `contact_phone_home` | โทรศัพท์ (บ้าน/ที่ทำงาน) | 1 | 11 | true |
| 12 | `contact_fax` | โทรสาร | 1 | 12 | true |
| 13 | `contact_mobile` | โทรศัพท์มือถือ | 1 | 13 | true |
| 14 | `contact_email` | อีเมล | 1 | 14 | true |
| 15 | `marital_status` | สถานภาพสมรส | 1 | 15 | true |
| 16 | `housing_type` | ลักษณะที่อยู่อาศัย | 1 | 16 | true |
| 17 | `housing_rent` | ค่าเช่าต่อเดือน (บาท) | 1 | 17 | true |
| 18 | `household_members` | ข้อมูลสมาชิกในครัวเรือน | 1 | 18 | true |
| 19 | `family_occupation` | อาชีพหลักของครอบครัว | 2 | 1 | true |
| 20 | `family_income` | รายได้เฉลี่ยต่อเดือนของครอบครัว (บาท) | 2 | 2 | true |
| 21 | `income_sources` | ที่มาของรายได้ | 2 | 3 | true |
| 22 | `income_source_other` | ที่มาของรายได้ อื่น ๆ (ระบุ) | 2 | 4 | true |
| 23 | `dependents` | ภาระการอุปการะ | 2 | 5 | true |
| 24 | `dependents_other` | ภาระการอุปการะ อื่น ๆ (ระบุ) | 2 | 6 | true |
| 25 | `gov_aid_received` | ประวัติการได้รับความช่วยเหลือจากรัฐ | 2 | 7 | true |
| 26 | `gov_aid_count` | จำนวนครั้งที่ได้รับความช่วยเหลือในปีงบประมาณนี้ | 2 | 8 | true |
| 27 | `gov_aid_amount` | มูลค่าความช่วยเหลือ รวมเป็นเงิน (บาท) | 2 | 9 | true |
| 28 | `gov_aid_types` | ประเภทความช่วยเหลือที่เคยได้รับ | 2 | 10 | true |
| 29 | `gov_aid_type_detail` | รายละเอียดความช่วยเหลือที่เคยได้รับ (ระบุ) | 2 | 11 | true |
| 30 | `family_problems` | สภาพปัญหาความเดือดร้อนของครอบครัว | 3 | 1 | true |
| 31 | `requested_assistance_type` | ประเภทความช่วยเหลือที่ต้องการ | 3 | 2 | **false** |
| 32 | `bank_name` | ธนาคาร | 3 | 3 | **false** |
| 33 | `bank_account_number` | เลขที่บัญชีธนาคาร | 3 | 4 | **false** |
| 34 | `bank_book_photo` | รูปหน้าสมุดบัญชีธนาคาร | 4 | 9 | true |
| 35 | `evidence_house_exterior` | รูปสภาพบ้านภายนอก | 4 | 1 | true |
| 36 | `evidence_house_interior` | รูปสภาพบ้านภายใน | 4 | 2 | true |
| 37 | `evidence_person_photo` | รูปผู้ประสบปัญหาฯ | 4 | 3 | true |
| 38 | `evidence_problem_photo` | รูปสภาพปัญหาที่ต้องการให้ความช่วยเหลือ | 4 | 4 | true |
| 39 | `evidence_family_photo` | รูปสมาชิกในครอบครัว | 4 | 5 | true |
| 40 | `doc_house_registration_house` | รูปทะเบียนบ้าน (รายการเกี่ยวกับบ้าน) | 4 | 6 | true |
| 41 | `doc_house_registration_person` | รูปทะเบียนบ้าน (รายการเกี่ยวกับบุคคล) | 4 | 7 | true |
| 42 | `doc_other` | รูปอื่น ๆ (เอกสารแนบเพิ่มเติม) | 4 | 8 | true |
| 43 | `remarks` | หมายเหตุเพิ่มเติม | 0 | 99 | true |
| 44 | `requested_assistance_detail` | รายละเอียดการช่วยเหลือที่ต้องการ | 3 | 2 | **false** |
| 45 | `doc_ktb_corporate` | รูปแบบฟอร์ม KTB Corporate Online | 4 | 10 | **false** |
| 46 | `requested_assistance_money` | ช่วยเหลือเป็นเงิน | 3 | 2 | true |
| 47 | `requested_assistance_in_kind` | ช่วยเหลือเป็นสิ่งของ | 3 | 3 | true |
| 48 | `requested_assistance_other` | ช่วยเหลือเรื่องอื่นๆ | 3 | 4 | true |

<div style="page-break-before: always;"></div>

### ตาราง welfare_review_comment

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `welfare_request_status_id` | int | NO | FK → `welfare_request_status.id`, IX | ครั้งที่ตีกลับ |
| `review_field_id` | int | NO | FK → `review_field.id` | |
| `reason` | text | NO | | เหตุผลจากเจ้าหน้าที่ |
| `created_at` | timestamp | NO | | |
| `citizen_confirmed_at` | timestamptz | YES | | เวลายืนยันตอน `POST /resubmit` |
| `citizen_confirmation_type` | varchar(20) | YES | | `unchanged_ok` \| `edited` |

---

<div style="page-break-before: always;"></div>

## 6. รับเรื่อง

### ตาราง case_handling

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `applicant_id` | int | NO | FK → `applicants.id` CASCADE, UK, IX | |
| `vsmart_informer_id` | int | YES | | VSmart informer |
| `vsmart_social_worker_id` | int | YES | | VSmart social worker |
| `sw_user_sdshv` | varchar(255) | YES | | รหัสนักสังคม |
| `responsible_division_id` | int | YES | | หน่วยงานรับผิดชอบ = VSmart `Division.id` (ไม่มี FK) |
| `type_money_id` | int | YES | FK → `type_money.id`, IX | เงินอุดหนุน / เฉพาะกิจ |
| `intake_completed_at` | timestamp | YES | | ปิดรับเรื่อง |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |

<div style="page-break-before: always;"></div>

### ตาราง case_help_beneficiaries

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `case_handling_id` | int | NO | FK → `case_handling.id` CASCADE, IX | |
| `household_member_id` | int | YES | FK → `household_members.id` CASCADE, IX | `NULL` = ผู้ยื่น |
| `display_name` | varchar(255) | YES | | ชื่อแสดง |
| `national_id` | varchar(13) | YES | | เลขบัตร snapshot |
| `age_years` | int | YES | | อายุ snapshot |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |

Partial unique:

- `(case_handling_id, household_member_id)` เมื่อ member ไม่ NULL
- `(case_handling_id)` เมื่อ member เป็น NULL (ผู้ยื่นได้ 1 คนต่อเคส)

<div style="page-break-before: always;"></div>

### ตาราง case_regulation_choice

ตารางใช้เก็บข้อมูล ระเบียบที่เลือก + วงเงิน + ลายเซ็น

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `case_handling_id` | int | NO | FK → `case_handling.id` CASCADE, UK, IX | |
| `regulation_id` | int | NO | FK → `announcement_regulations.id`, IX | |
| `help_kind` | varchar(10) | NO | | default `money` — `money` \| `things` |
| `money_amount` | numeric(12,2) | YES | | จำนวนเงิน |
| `comment` | text | YES | | คำวินิจฉัยเก่า  |
| `esignature` | text | YES | | ลายเซ็น |
| `signed_by_sdshv` | varchar(255) | YES | | ผู้ลงนาม |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |

<div style="page-break-before: always;"></div>

### ตาราง announcement_regulations

Master ระเบียบ/ประกาศ — `id` ไม่ autoincrement (sync กับ VSmart)

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | กำหนดตรงจาก VSmart |
| `code` | varchar(50) | NO | UK | รหัสระเบียบ |
| `name` | text | NO | | ชื่อเต็ม |
| `short_name` | varchar(100) | YES | | ชื่อสั้น |
| `type_money_category_id` | int | NO | FK → `type_money_category.id`, IX | |
| `maximum_money` | numeric(12,2) | NO | | เพดานเงิน |
| `limit_per_budget_year` | int | NO | | จำกัดครั้งต่อปีงบ |
| `sort_order` | int | YES | | |
| `activate` | bool | NO | | default `true`  |
| `vsmart_legacy_id` | int | YES | | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |

<div style="page-break-before: always;"></div>

### ตาราง payment_method

ใช้เก็บข้อมูล Master data สำหรับวิธีการจ่ายเงิน

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `code` | varchar(30) | NO | UK | |
| `name_th` | varchar(255) | NO | | |
| `legacy_vsmart_value` | varchar(10) | YES | | `False`/`True`/`0`/`1`/`2`/`3` |
| `sort_order` | int | NO | | |
| `requires_ktb_form` | bool | NO | | default `false` |

| id | code | name_th | legacy | sort | requires_ktb_form |
|----|------|---------|--------|------|-------------------|
| 1 | `cash` | เงินสด | False | 1 | false |
| 2 | `cheque` | เช็ค | True | 2 | false |
| 3 | `bank_transfer` | โอนเงินเข้าบัญชี | 0 | 3 | false |
| 4 | `promptpay` | พร้อมเพย์ (Prompt Pay) | 1 | 4 | false |
| 5 | `ktb_corporate` | KTB Corporate Online | 2 | 5 | **true** |
| 6 | `epayment` | e-Payment | 3 | 6 | false |

<div style="page-break-before: always;"></div>

### ตาราง case_payment

ตารางใช้เก็บข้อมูล วิธีจ่ายตอนรับเรื่อง

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `case_handling_id` | int | NO | FK → `case_handling.id` CASCADE, UK, IX | |
| `payment_method_id` | int | NO | FK → `payment_method.id`, IX | |
| `receive_mode` | varchar(10) | YES | | `self` \| `agent` |
| `agent_person_id` | int | YES | FK → `persons.id`, IX | ผู้รับแทน |
| `payee_person_id` | int | YES | FK → `persons.id`, IX | ผู้รับเงิน |
| `bank_name_id` | int | YES | FK → `bank_name.id`, IX | |
| `bank_branch` | varchar(255) | YES | | สาขา |
| `bank_account_type_id` | int | YES | FK → `bank_account_type.id`, IX | |
| `account_number` | varchar(50) | YES | | |
| `account_name` | varchar(255) | YES | | |
| `cheque_reference` | varchar(100) | YES | | อ้างอิงเช็ค |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |

<div style="page-break-before: always;"></div>

### ตาราง case_ktb_corporate

ใช้เก็บข้อมูลกรณีเป็น KTB Corporate Online

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `case_handling_id` | int | NO | FK → `case_handling.id` CASCADE, UK, IX | |
| `form_number` | int | YES | | เลขแบบฟอร์ม |
| `director_division_ref` | varchar(500) | YES | | อ้างอิงกอง |
| `paying_division_ref` | varchar(500) | YES | | อ้างอิงหน่วยจ่าย |
| `recipient_category` | enum `ktb_recipient_category` | NO | | `payroll` / `gov_other` / `external` |
| `payroll_bank_name_id` | int | YES | FK → `bank_name.id`, IX | ข้อ 1.1 |
| `payroll_bank_branch` | varchar(255) | YES | | |
| `payroll_account_type` | varchar(100) | YES | | ข้อความ ไม่ใช่ FK |
| `payroll_account_number` | varchar(50) | YES | | |
| `other_bank_name_id` | int | YES | FK → `bank_name.id`, IX | ข้อ 1.2 |
| `other_bank_branch` | varchar(255) | YES | | |
| `other_account_type` | varchar(100) | YES | | |
| `other_account_number` | varchar(50) | YES | | |
| `notify_channel` | enum `ktb_notify_channel` | YES | | `sms` \| `email` |
| `notify_contact` | varchar(255) | YES | | เบอร์/อีเมลแจ้ง |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |

---

<div style="page-break-before: always;"></div>

## 7. คำวินิจฉัย

### ตาราง case_diagnosis

คำวินิจฉัย 1 คนต่อ 1 เคส — UNIQUE(`applicant_id`, `owner_user_id`)

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `applicant_id` | int | NO | FK → `applicants.id` CASCADE, IX | ไม่ผ่าน `case_handling` |
| `diagnosis_text` | text | NO | | ข้อความคำวินิจฉัย |
| `owner_user_id` | int | NO | IX | Django user id (VSmart)  |
| `owner_sdshv` | varchar(255) | YES | | snapshot รหัส |
| `owner_name` | varchar(255) | YES | | snapshot ชื่อ |
| `owner_position` | varchar(255) | YES | | snapshot ตำแหน่ง |
| `owner_organization` | varchar(255) | YES | | snapshot หน่วยงาน |
| `created_at` | timestamp | NO | | UTC naive |
| `updated_at` | timestamp | NO | | UTC naive |

<div style="page-break-before: always;"></div>

### ตาราง case_diagnosis_edit_history

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `diagnosis_id` | int | NO | FK → `case_diagnosis.id` CASCADE, IX | |
| `old_text` | text | NO | | |
| `new_text` | text | NO | | |
| `edit_reason` | text | YES | | ไม่บังคับ |
| `edited_by_user_id` | int | NO | | |
| `edited_by_name` | varchar(255) | YES | | snapshot |
| `created_at` | timestamp | NO | | UTC naive |

---

<div style="page-break-before: always;"></div>

## 8. บทความและอนุมัติ

### ตาราง article

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `applicant_id` | int | NO | FK → `applicants.id` CASCADE, UK, IX | |
| `batch_id` | int | YES | FK → `cover_document_batch.id` SET NULL, IX | หนังสือนำส่ง |
| `service_vsmart_id` | varchar(255) | YES | | |
| `approver_sdhsv_id` | varchar(64) | YES | | ผู้อนุมัติที่ขอ |
| `phone_service` | varchar(255) | YES | | |
| `at` | varchar(255) | YES | | ที่ |
| `date_at` | date | YES | | วันที่ |
| `title` | varchar(255) | YES | | เรื่อง |
| `refer_vsmart_id` | varchar(255) | YES | | คอลัมน์จริงของ `director_vsmart_id` ใน ORM |
| `original_story` | text | YES | | ความเป็นมา |
| `fact_story` | text | YES | | ข้อเท็จจริง |
| `laws` | text | YES | | กฎหมาย |
| `consider` | text | YES | | พิจารณา |
| `suggestion` | text | YES | | ข้อเสนอ |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |

<div style="page-break-before: always;"></div>

### ตาราง cover_document_batch

ใช้เก็บข้อมูลของการนำเรียนสำหรับการอนุมัติ

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `type_money_id` | int | YES | FK → `type_money_category.id`, IX | ชื่อคอลัมน์ชี้ **หมวดเงิน** ไม่ใช่ `type_money` |
| `province_id` | int | YES | FK → `province.id`, IX | |
| `approver_sdhsv` | varchar(64) | YES | | |
| `service_vsmart_id` | varchar(255) | YES | | |
| `phone_service` | varchar(255) | YES | | |
| `at` | varchar(255) | YES | | |
| `date_at` | date | YES | | |
| `title` | varchar(255) | YES | | |
| `refer_vsmart_id` | varchar(255) | YES | | ORM: `director_vsmart_id` |
| `original_story` | text | YES | | |
| `fact_story` | text | YES | | |
| `laws` | text | YES | | |
| `consider` | text | YES | | |
| `suggestion` | text | YES | | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |

<div style="page-break-before: always;"></div>

### ตาราง approve_case

ใช้เก็บข้อมูลการอนุมัติ ประวัติอนุมัติ หรือ ปฎิเสธ

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `applicant_id` | int | NO | FK → `applicants.id`, IX | |
| `article_id` | int | YES | FK → `article.id` SET NULL, IX | |
| `approve_status` | bool | NO | | `true` = อนุมัติ, `false` = PMJ reject |
| `esignature` | text | YES | | ลายเซ็น |
| `user_sdshv` | varchar(255) | YES | | ผู้ดำเนินการ |
| `reject_reason` | text | YES | | บังคับเมื่อ `approve_status=false` |
| `reject_resolved_at` | timestamptz | YES | | วันที่นักสังคมฯ ดำเนินการต่อหลัง reject |

---

<div style="page-break-before: always;"></div>

## 9. เบิกจ่าย

### ตาราง welfare_dda_ref

ตารางสำหรับใช้เก็บข้อมูล dda ref

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `dda_ref` | varchar(255) | NO | | เลขอ้างอิง |
| `user_sdshv` | varchar(255) | YES | | ผู้สร้าง |

<div style="page-break-before: always;"></div>

### ตาราง welfare_payment

ตารางสำหรับใช้เก็บข้อมูลรอบจ่ายจริง (037 / 038)

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `applicant_id` | int | NO | FK → `applicants.id`, IX | |
| `is_037_or_038` | bool | YES | | `NULL` = รอบเปิด, `false` = 037, `true` = 038 |
| `dda_ref_id` | int | NO | FK → `welfare_dda_ref.id`, IX | |
| `payment_number` | varchar(255) | YES | | เลขที่จ่าย |
| `payment_038_reason` | varchar(255) | YES | | เหตุผล 038 |
| `user_sdshv` | varchar(255) | YES | | |
| `transaction_date` | date | YES | | |
| `effective_date` | date | YES | | |
| `created_at` | timestamptz | NO | | |
| `upload_batch_id` | uuid | YES | IX | กลุ่มไฟล์อัปโหลดรอบเดียวกัน |

<div style="page-break-before: always;"></div>

### ตาราง file_payment

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `welfare_dda_ref_id` | int | NO | FK → `welfare_dda_ref.id`, IX | |
| `file_original_name` | varchar(255) | YES | | |
| `file_stored_name` | varchar(255) | YES | | |
| `file_path` | varchar(1024) | NO | | |
| `file_size` | bigint | YES | | |
| `file_width` | int | YES | | |
| `file_height` | int | YES | | |
| `attachment_type_id` | int | NO | FK → `attachment_types.id`, IX | 9=037, 10=038, 13–15=หลักฐานเงินสด/เช็ค |
| `welfare_payment_id` | int | YES | FK → `welfare_payment.id`, IX | |
| `upload_batch_id` | uuid | YES | IX | |

---

<div style="page-break-before: always;"></div>

## 10. MSO

### ตาราง more_mso

ตารางสำหรับการเก็บข้อมูลสถานะ ช่วยเหลือเเล้ว

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `case_handling_id` | int | NO | FK → `case_handling.id` CASCADE, UK, IX | |
| `follow_date` | varchar(255) | YES | | |
| `help_number` | varchar(255) | YES | | เลขที่ช่วยเหลือ |
| `help_date` | date | YES | | |
| `approve_name` | varchar(255) | YES | |  |
| `approve_number` | varchar(255) | YES | | |
| `approve_date` | date | YES | | |
| `receive_date` | date | YES | | |
| `cashier` | varchar(255) | YES | | |
| `cashier_name` | varchar(255) | YES | | |
| `follower_name` | varchar(255) | YES | | ผู้ติดตาม |
| `follower_position_vsmart_id` | varchar(255) | YES | | |
| `follower_department_vsmart_id` | varchar(255) | YES | | |
| `follower_tel` | varchar(255) | YES | | |
| `follower_date` | date | YES | | |
| `follower_result` | text | YES | | |
| `follower_method` | int | YES | | |
| `follower_type` | int | YES | | |

<div style="page-break-before: always;"></div>

### ตาราง type_send

 ตารางเก็บข้อมูล Master Data ประเภทการส่งข้อมูล

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `name` | varchar(255) | NO | | |
| `detail` | text | YES | | |

| id | name |
|----|------|
| 1 | ส่งต่อเข้าหระทรวง |
| 2 | ส่งต่อ mso logbook |

<div style="page-break-before: always;"></div>

### ตาราง send_data

บันทึกการส่งข้อมูลคำร้อง

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `send_by_sdshv` | varchar(255) | YES | | ผู้ส่ง |
| `applicant_id` | int | NO | FK → `applicants.id` CASCADE, IX | |
| `type_send_id` | int | NO | FK → `type_send.id`, IX | |
| `json_case` | json | YES | | payload |
| `response_code` | varchar(255) | YES | | |
| `response_text` | text | YES | | |

---

<div style="page-break-before: always;"></div>

## 11. สิทธิ์ / OCR / สำรวจ

### ตาราง screening_logs

ผลตรวจสิทธิ์เบื้องต้น CheckSelf

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `person_id` | int | NO | FK → `persons.id`, IX | |
| `criteria_version` | varchar(255) | YES | | เวอร์ชันเกณฑ์ |
| `failure_reason_code` | varchar(255) | YES | | รหัสเหตุผลไม่ผ่าน |
| `screening_status` | bool | NO | | default `false` — ผ่าน/ไม่ผ่าน |
| `input_data_snapshot` | json | YES | | ข้อมูลที่กรอกตอนตรวจ |
| `hardship_status_ids` | json | YES | | list ของ id จาก `hardship_status_types` เช่น `[1,2]` |
| `ip_address` | varchar(255) | YES | | |
| `user_agent` | varchar(500) | YES | | |

<div style="page-break-before: always;"></div>

### ตาราง welfare_request_consents

ตารางสำหรับการเก็บ ความยินยอม PDPA / ข้อตกลง

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `created_at` | timestamp | NO | | |
| `updated_at` | timestamp | NO | | |
| `person_id` | int | NO | FK → `persons.id`, IX | |
| `consent_type` | varchar(100) | YES | | |
| `initial_pdpa_accepted` | bool | NO | | default `false` |
| `initial_terms_accepted` | bool | NO | | default `false` |
| `initial_warning_accepted` | bool | NO | | default `false` |
| `final_data_correct_accepted` | bool | NO | | default `false` — ยืนยันข้อมูลถูกต้องตอนส่ง |

<div style="page-break-before: always;"></div>

### ตาราง ocr_results

ผล OCR สมุดบัญชี เก็บผลสมุดบัญชี

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `applicant_id` | int | YES | FK → `applicants.id` SET NULL, IX | |
| `target_name_checked` | text | NO | | ชื่อที่ใช้เทียบ |
| `pre_file` | varchar(255) | NO | | ไฟล์ต้นทาง |
| `markdown` | text | NO | | default `''` — ข้อความที่อ่านได้ |
| `account_number` | varchar(50) | YES | | |
| `account_name` | text | YES | | |
| `bank_name` | text | YES | | |
| `deposit_type` | text | YES | | ประเภทเงินฝาก |
| `branch_name` | text | YES | | |
| `branch_code` | varchar(20) | YES | | |
| `match_status` | varchar(20) | NO | | default `no_text` |
| `fuzzy_score` | float | NO | | default `0` |
| `created_at` | timestamptz | NO | | |
| `updated_at` | timestamptz | NO | | |

<div style="page-break-before: always;"></div>

### ตาราง satisfaction_surveys

แบบประเมินความพึงพอใจ

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `applicant_id` | int | NO | FK → `applicants.id` CASCADE, IX | |
| `survey_type` | varchar(50) | NO | | `system_usage` = หลังยื่น, `aid_received` = หลังเบิกจ่าย |
| `rating` | int | NO | | 1–5 |
| `comment` | text | YES | | |
| `created_at` | timestamp | NO | | |

---

<div style="page-break-before: always;"></div>

## 12. ภูมิศาสตร์

### ตาราง province

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `code` | varchar(10) | YES | IX | รหัสจังหวัด |
| `name` | varchar(255) | NO | | ชื่อจังหวัด |

<div style="page-break-before: always;"></div>

### ตาราง districts

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `code` | varchar(50) | YES | IX | |
| `name` | varchar(255) | NO | | |
| `province_id` | int | NO | FK → `province.id`, IX | |

<div style="page-break-before: always;"></div>

### ตาราง sub_districts

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `code` | varchar(50) | YES | IX | |
| `name` | varchar(255) | NO | | |
| `district_id` | int | NO | FK → `districts.id`, IX | |

<div style="page-break-before: always;"></div>

### ตาราง postcode

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `name` | varchar(10) | NO | IX | รหัสไปรษณีย์ 5 หลัก |

<div style="page-break-before: always;"></div>

### ตาราง sub_districts_postcode

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `sub_district_id` | int | NO | FK → `sub_districts.id`, IX | |
| `postcode_id` | int | NO | FK → `postcode.id`, IX | |

---

<div style="page-break-before: always;"></div>

## 13. Admin / Staff

### ตาราง admin_users

ใช้สำหรับการเก็บข้อมูลเเอดมิน

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `username` | varchar(100) | NO | UK | |
| `password_hash` | varchar(255) | NO | | bcrypt — ไม่เก็บ plain text |
| `is_active` | bool | NO | | default `true` |
| `created_at` | timestamptz | NO | | |

<div style="page-break-before: always;"></div>

### ตาราง province_access_config 

เก็บข้อมูลการ เปิด/ปิดบริการรายจังหวัด

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `province_id` | int | NO | FK → `province.id`, UK, IX | |
| `is_enabled` | bool | NO | | default `false` |
| `updated_by_admin_id` | int | YES | FK → `admin_users.id` | |
| `updated_at` | timestamptz | NO | | |

<div style="page-break-before: always;"></div>

### ตาราง staff_users

บัญชีเจ้าหน้าที่ SDSHV (HI-01) — แยกจากประชาชนและ admin

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `username` | varchar(100) | NO | UK | |
| `password_hash` | varchar(255) | NO | | bcrypt |
| `display_name` | varchar(200) | NO | | default `''` |
| `province_id` | int | NO | FK → `province.id`, IX | จังหวัดรับผิดชอบ |
| `is_active` | bool | NO | | default `true` |
| `created_at` | timestamptz | NO | | |

<div style="page-break-before: always;"></div>

### ตาราง security_audit_log

ใช้สำหรับการเก็บ log Audit การลบข้อมูลและ ops

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `action` | varchar(64) | NO | IX | ประเภท action |
| `actor_type` | varchar(32) | NO | | ประเภทผู้กระทำ |
| `actor_id` | varchar(64) | NO | | รหัสผู้กระทำ |
| `target_cid` | varchar(13) | YES | IX | CID ที่ถูกกระทำ |
| `detail` | varchar(500) | YES | | |
| `created_at` | timestamptz | NO | | |

---

<div style="page-break-before: always;"></div>

## 14. Lookup / Master data

### ตาราง prefix_type

ใช้สำหรับเก็บข้อมูลคำนำหน้า

| id | name |
|----|------|
| 1 | นาย |
| 2 | นาง |
| 3 | นางสาว |
| 4 | เด็กหญิง |
| 5 | เด็กชาย |

<div style="page-break-before: always;"></div>

### ตาราง marital_status_types

ใช้สำหรับเก็บข้อมูล master data สถานะของผู้ยื่น

| id | name |
|----|------|
| 1 | โสด |
| 2 | สมรสอยู่ด้วยกัน |
| 3 | หย่าร้าง |
| 4 | ไม่ได้สมรสเเต่อยู่ด้วยกัน |
| 5 | หม้าย (คู่สมรสเสียชีวิต) |
| 6 | สมรสเเยกกันอยู่ |

<div style="page-break-before: always;"></div>

### ตาราง requester_relation_type

ความสัมพันธ์ผู้ยื่นกับผู้รับสิทธิ์

| id | name |
|----|------|
| 1 | ตนเอง |

<div style="page-break-before: always;"></div>

### ตาราง request_types

รูปเเบบการให้ความช่วยเหลือ

| id | name |
|----|------|
| 1 | ช่วยเหลือเป็นเงิน |
| 2 | ช่วยเหลือเป็นสิ่งของ |
| 3 | ช่วยเหลือเรื่องอื่นๆ |

<div style="page-break-before: always;"></div>

### ตาราง attachment_types

ตารางใช้เก็บรูปเเบบประเภทสมัดบัญชีธนาคาร

| id | name | ใช้กับ |
|----|------|--------|
| 1 | รูปหน้าสมุดบัญชีธนาคาร | evidence |
| 2 | รูปสภาพบ้านภายนอก | evidence |
| 3 | รูปสภาพบ้านภายใน | evidence |
| 4 | รูปผู้ประสบปัญหา | evidence |
| 5 | รูปสภาพปัญหาที่ต้องการให้ความช่วยเหลือ | evidence |
| 6 | รูปทะเบียนบ้าน (รายการเกี่ยวกับบ้าน) | evidence |
| 7 | รูปทะเบียนบ้าน (รายการเกี่ยวกับบุคคล) | evidence |
| 8 | รูปสมาชิกในครอบครัว | evidence |
| 9 | PDF 037 | file_payment |
| 10 | PDF 038 | file_payment |
| 11 | รูปแบบแจ้งข้อมูลการรับเงินโอนผ่านระบบ KTB Corporate Online | evidence |
| 12 | id_card | บัตรประชาชนสมาชิก |
| 13 | ใบสำคัญรับเงิน | file_payment เงินสด/เช็ค |
| 14 | หลักฐานการจ่ายเงิน | file_payment เงินสด/เช็ค |
| 15 | หลักฐานเช็ค | file_payment เงินสด/เช็ค |
| 99 | รูปอื่น ๆ | evidence |

<div style="page-break-before: always;"></div>

### ตาราง received_welfare_types

| id | name |
|----|------|
| 1 | เงินสงเคราะห์ |
| 2 | เงินทุนประกอบอาชีพ |
| 3 | เงิน/เบี้ยผู้สูงอายุ (เบี้ยยังชีพผู้สูงอายุ) |
| 4 | เงิน/เบี้ยคนพิการ (เบี้ยความพิการ) |
| 5 | เงิน/เบี้ยเด็กแรกเกิด (เงินอุดหนุนเพื่อการเลี้ยงดูเด็กแรกเกิด) |
| 6 | บัตรคนจน (สวัสดิการที่ได้จากการลงทะเบียนโครงการเพื่อสวัสดิการแห่งรัฐ) |
| 7 | การซ่อมบ้าน (เงินซ่อมแซมบ้าน) |
| 8 | ความช่วยเหลืออื่นจากภาครัฐ |
| 9 | ความช่วยเหลืออื่นจากภาคเอกชน |
| 10 | เงินกู้ |
| 11 | เครื่องช่วยความพิการ |
| 99 | อื่น ๆ |

<div style="page-break-before: always;"></div>

### ตาราง dependency_types

ตารางใช้เก็บข้อมูลสำหรับประเภทการอุปการะ

| id | name |
|----|------|
| 1 | อุปการะเลี้ยงดูบิดามารดา |
| 2 | อุปการะเลี้ยงดูบุตร |
| 3 | อุปการะเลี้ยงดูผู้สูงอายุ |
| 4 | อุปการะเลี้ยงดูคนพิการหรือคนทุพพลภาพ |
| 99 | อื่น ๆ |

<div style="page-break-before: always;"></div>

### ตาราง housing_types

ตารางสำหรับใช้เก็บข้อมูลสภาพทีอยู่อาศัย

| id | name |
|----|------|
| 1 | มีที่อยู่อาศัยเป็นของตนเองและมั่นคงถาวร |
| 2 | มีที่อยู่อาศัยเป็นของตนเองแต่ไม่มั่นคงถาวร |
| 3 | อยู่ที่ดินบุคคลอื่น |
| 99 | บ้านเช่า |

<div style="page-break-before: always;"></div>

### ตาราง income_source_types

| id | name |
|----|------|
| 1 | การประกอบอาชีพ |
| 2 | บุตร/ผู้อุปการะ |
| 3 | สวัสดิการของรัฐ |
| 99 | อื่น ๆ |

<div style="page-break-before: always;"></div>

### ตาราง address_type

| id | name |
|----|------|
| 1 | ที่อยู่ปัจจุบัน |

<div style="page-break-before: always;"></div>

### ตาราง type_money

ตารางสำหรับเก็บประเภท คือ เงินอุดหนุน หรือ เงินอุดหนุนเฉพาะกิจ

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `name` | varchar(255) | NO | | |

| id | name |
|----|------|
| 1 | เงินอุดหนุน |
| 2 | เงินอุดหนุนเฉพาะกิจ |

<div style="page-break-before: always;"></div>

### ตาราง type_money_category

หมวดเงินช่วยเหลือของคำร้อง / ระเบียบ / หนังสือนำส่ง

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `name` | varchar(255) | NO | | ชื่อเต็ม |
| `name_acronym` | varchar(255) | NO | | ตัวย่อไทย |
| `color` | varchar(32) | NO | | สี UI |
| `name_acrovym_eng` | varchar(255) | NO | | ตัวย่ออังกฤษ (สะกดตามคอลัมน์จริง) |
| `activate` | bool | NO | | default `true` |

| id | name_acronym | name | eng | color |
|----|--------------|------|-----|-------|
| 1 | สป. | เงินอุดหนุนเพื่อช่วยเหลือผู้ประสบปัญหาทางสังคมกรณีฉุกเฉิน | mso | `#ff4d79` |
| 2 | ดย. | เงินสงเคราะห์เด็กในครอบครัวยากจน | dcy | `#fa6400` |
| 3 | พก. | เงินสงเคราะห์และฟื้นฟูสมรรถภาพคนพิการ | dep | `#14b1ff` |
| 4 | ผส. | เงินสงเคราะห์ผู้สูงอายุในภาวะยากลำบาก | dop | `#ffc800` |
| 5 | พส. | เงินอุดหนุนเงินสงเคราะห์ผู้มีรายได้น้อยและผู้ไร้ที่พึ่ง | dsdw | `#00b300` |
| 6 | สค. | เงินสงเคราะห์สตรีหรือครอบครัวที่ประสบปัญหาทางสังคม | dwf | `#ff94f2` |

<div style="page-break-before: always;"></div>

### ตาราง bank_account_type

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `name` | varchar(100) | NO | | |
| `sort_order` | int | YES | | |

| id | name | sort_order |
|----|------|------------|
| 1 | เงินฝากออมทรัพย์ | 1 |
| 2 | เงินฝากประจำ | 2 |
| 3 | เงินฝากกระแสรายวัน | 3 |

<div style="page-break-before: always;"></div>

### ตาราง bank_name

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `name` | varchar(255) | NO | | |
| `bank_id_mso` | int | NO | | รหัส MSO |
| `bank_code` | varchar(10) | NO | | รหัสธนาคาร |
| `order` | int | NO | | ลำดับแสดง (คอลัมน์ชื่อ `order`) |

| id | name | bank_code | order |
|----|------|-----------|-------|
| 1 | ธนาคารเพื่อการเกษตรและสหกรณ์การเกษตร | 034 | 1 |
| 2 | ธนาคารออมสิน | 030 | 2 |
| 3 | ธนาคารกรุงไทย | 006 | 3 |
| 4 | ธนาคารไทยพาณิชย์ | 014 | 4 |
| 7 | ธนาคารกสิกรไทย | 004 | 5 |
| 5 | ธนาคารกรุงเทพ | 002 | 6 |
| 6 | ธนาคารกรุงศรีอยุธยา | 025 | 7 |
| 24 | ธนาคารทหารไทย | 011 | 8 |
| 33 | ธนาคารทหารไทยธนชาติ จำกัด | 011 | 8 |
| 26 | ธนาคารธนชาต | 065 | 9 |
| 10 | ธนาคารสแตนดาร์ดชาร์เตอร์ด (ไทย) | 020 | 10 |
| 11 | ธนาคารยูโอบี | 024 | 11 |
| 12 | ธนาคารทิสโก้ | 067 | 12 |
| 21 | ธนาคารแห่งประเทศไทย | 000 | 13 |
| 22 | ธนาคารเกียรตินาคิน | 069 | 14 |
| 23 | ธนาคารซีไอเอ็มบีไทย | 022 | 15 |
| 25 | ธนาคารไทยเครดิตเพื่อรายย่อย | 071 | 16 |
| 27 | ธนาคารแลนด์ แอนด์ เฮาส์ | 073 | 17 |
| 28 | ธนาคารพัฒนาวิสาหกิจขนาดกลางและขนาดย่อมแห่งประเทศไทย | 098 | 18 |
| 29 | ธนาคารเพื่อการส่งออกและนำเข้าแห่งประเทศไทย | 035 | 19 |
| 30 | ธนาคารอาคารสงเคราะห์ | 033 | 20 |
| 31 | ธนาคารอิสลามแห่งประเทศไทย | 066 | 21 |
| 32 | ธนาคารไอซีบีซี (ไทย) | 070 | 22 |

<div style="page-break-before: always;"></div>

### ตาราง household_member_relation_types

| id | name |
|----|------|
| 1 | บิดา/มารดา |
| 2 | ญาติพี่น้อง |
| 3 | บุตร |
| 4 | คู่สมรส |
| 5 | เจ้าหน้าที่จาก อบต. |
| 6 | ผู้ใหญ่บ้าน |
| 7 | เหลน |
| 8 | หลาน |
| 9 | ทวด |

<div style="page-break-before: always;"></div>

### ตาราง hardship_status_types

| id | name |
|----|------|
| 1 | ประสบปัญหาความเดือดร้อน |
| 2 | ครอบครัวประสบปัญหาความเดือดร้อน |

<div style="page-break-before: always;"></div>

### ตาราง occupation_types

ตารางสำหรับการเก็บข้อมูลอาชีพสำหรับใช้ใน Dropdown

| id | name |
|----|------|
| 1 | นักเรียน/นักศึกษา |
| 2 | ค้าขาย/ธุรกิจส่วนตัว |
| 3 | ภิกษุ/สามเณร/แม่ชี |
| 4 | เกษตรกร (ทำไร่/นา/สวน/เลี้ยงสัตว์/ประมง) |
| 5 | รับจ้าง |
| 6 | ข้าราชการ/พนักงานของรัฐ |
| 7 | พนักงานรัฐวิสาหกิจ |
| 8 | พนักงานบริษัท |
| 99 | อื่น ๆ ระบุ (เพิ่มระบุอื่นๆ) |

<div style="page-break-before: always;"></div>

### ตาราง current_status

ตารางสำหรับเก็บ สถานะคำร้อง

| คอลัมน์ | ชนิด | Null | Key | คำอธิบาย |
|---------|------|------|-----|----------|
| `id` | int | NO | PK | |
| `description_public` | text | NO | | ข้อความที่ประชาชนเห็น |
| `description_staff` | text | NO | | ข้อความที่เจ้าหน้าที่เห็น |
| `color` | varchar(32) | NO | | สี UI |
| `dropdown_to_change` | varchar(255) | NO | | ป้ายใน dropdown เปลี่ยนสถานะ |
| `dropdown_order` | int | NO | | |
| `dropdown_activate` | bool | NO | | โชว์ใน dropdown |
| `filter_order` | int | NO | | |
| `filter_activate` | bool | NO | | โชว์ในตัวกรอง |
| `vsmart_id` | int | NO | | แมปสถานะ VSmart |

| id | ประชาชนเห็น | เจ้าหน้าที่เห็น | vsmart_id | dropdown | filter | ค่าคงที่ในโค้ด |
|----|-------------|-----------------|-----------|----------|--------|----------------|
| 1 | รอรับเรื่อง | รอรับเรื่อง | 2 | ไม่ | ใช่ | `CURRENT_STATUS_PENDING_INTAKE` |
| 2 | รับเรื่องเรียบร้อย | รับเรื่องเรียบร้อย | 3 | ใช่ | ใช่ | `CURRENT_STATUS_RECEIVED` |
| 3 | อยู่ระหว่างการเบิก | อยู่ระหว่างการเบิก | 15 | ใช่ | ใช่ | `CURRENT_STATUS_WITHDRAWING_APPROVED` |
| 4 | เบิกจ่ายสำเร็จ | ช่วยเหลือเเล้ว | 7 | ใช่ | ใช่ | `CURRENT_STATUS_AID_COMPLETED` |
| 5 | คุณสมบัติไม่ตรงตามหลักเกณฑ์ | คุณสมบัติไม่ตรงตามหลักเกณฑ์ | 12 | ใช่ | ใช่ | `CURRENT_STATUS_INELIGIBLE` |
| 6 | อยู่ระหว่างการพิจารณาของคณะกรรมการ | อยู่ระหว่างการพิจารณาของคณะกรรมการ | 5 | ไม่ | ไม่ |  |
| 7 | อยู่ระหว่างรอจัดสรรงบประมาณ | อยู่ระหว่างรอจัดสรรงบประมาณ | 13 | ไม่ | ไม่ |  |
| 8 | เเก้ไขข้อมูล | ดำเนินการแก้ไขข้อมูล | 8 | ใช่ | ใช่ | `CURRENT_STATUS_EDIT_REQUESTED` |
| 9 | อยู่ระหว่างการหาข้อมูลเพิ่มเติม | อยู่ระหว่างการหาข้อมูลเพิ่มเติม | 9 | ใช่ | ใช่ | `CURRENT_STATUS_GATHERING_ADDITIONAL_INFO` |
| 10 | เบิกจ่ายสำเร็จ | อยู่ระหว่างการเบิก | 6 | ใช่ | ใช่ | `CURRENT_STATUS_WITHDRAWING` |
| 11 | ส่งต่อข้อมูลเรียบร้อยแล้ว | ส่งต่อข้อมูลเรียบร้อยแล้ว | 14 | ไม่ | ใช่ | `CURRENT_STATUS_MSO_FORWARDED` |

---
