"""สร้างคำร้องสุ่มสำหรับ admin (dev/staging) — person + applicant + ตารางย่อย."""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.lookup_other import OTHER_TYPE_ID
from ..models.address import Address
from ..models.applicant import Applicant
from ..models.applicant_submission_audit import ApplicantSubmissionAudit
from ..models.dependency import DependencyLoad
from ..models.economic import EconomicIncomeSource, EconomicInfo, HouseholdMember
from ..models.geo import District, Province, SubDistrict, SubDistrictPostcode
from ..models.lookup import (
    AddressType,
    BankAccountType,
    BankName,
    DependencyType,
    HousingType,
    IncomeSourceType,
    MaritalStatusType,
    OccupationType,
    PrefixType,
    RequesterRelationType,
    RequestType,
)
from ..models.person import Person
from ..models.status_log import WelfareRequestStatus
from ..models.welfare import WelfareHistory, WelfareRequestType
from ..schemas.case_welfare import AddressInCase
from ..schemas.check_case import ExistingCaseCheckResult, SourceCheckResult
from ..services.case_number import allocate_case_number
from ..services.ktb_requirement import build_submission_audit_fields
from ..services.random_case_evidence import attach_random_case_placeholders

# เลขบัตรจำลองขึ้นต้น 99 — แยกจากบัตรจริง
_MOCK_CID_PREFIX = "99"

_MALE_FIRST = ("สมชาย", "วิชัย", "ประยุทธ์", "อนุชา", "ธนากร", "กิตติ", "สุรชัย", "พีระ")
_FEMALE_FIRST = ("สมหญิง", "มาลี", "สุดา", "วรรณา", "กานดา", "พิมพ์ใจ", "อรุณี", "นภา")
_LAST_NAMES = (
    "ใจดี",
    "รักไทย",
    "สุขใจ",
    "ทองดี",
    "มีสุข",
    "ศรีสุข",
    "บุญมี",
    "แสนดี",
    "พูนสุข",
    "เจริญสุข",
)
_PROBLEMS = (
    "ประสบปัญหาเศรษฐกิจ รายได้ไม่เพียงพอต่อการดำรงชีพ",
    "ถูกเลิกจ้างและยังหางานไม่ได้",
    "เจ็บป่วยเรื้อรัง ค่ารักษาพยาบาลสูง",
    "บ้านเรือนเสียหายจากภัยธรรมชาติ",
    "มีภาระเลี้ยงดูสมาชิกในครอบครัวหลายคน",
)


@dataclass(frozen=True)
class RandomCaseCreated:
    applicant_id: int
    case_number: str | None
    persons_id: int
    cid: str
    full_name: str
    province_id: int | None
    province_name: str | None


@dataclass
class _LookupPool:
    prefix_ids: list[int]
    marital_ids: list[int]
    relation_ids: list[int]
    address_type_ids: list[int]
    request_type_ids: list[int]
    dependency_ids: list[int]
    housing_ids: list[int]
    income_source_ids: list[int]
    occupation_ids: list[int]
    bank_name_ids: list[int]
    bank_account_type_ids: list[int]


def _thai_cid_checksum(body12: str) -> int:
    digits = [int(c) for c in body12]
    total = sum(d * (13 - i) for i, d in enumerate(digits))
    return (11 - total % 11) % 10


def _generate_mock_cid() -> str:
    body_len = 12 - len(_MOCK_CID_PREFIX)
    body = _MOCK_CID_PREFIX + "".join(str(secrets.randbelow(10)) for _ in range(body_len))
    return body + str(_thai_cid_checksum(body))


async def _unique_mock_cid(session: AsyncSession) -> str:
    for _ in range(10):
        cid = _generate_mock_cid()
        exists = await session.scalar(select(Person.id).where(Person.cid == cid))
        if exists is None:
            return cid
    raise ValueError("cid_collision")


def _pick(ids: list[int]) -> int:
    return random.choice(ids)


def _pick_non_other(ids: list[int]) -> int:
    filtered = [i for i in ids if i != OTHER_TYPE_ID]
    return random.choice(filtered or ids)


def _random_phone() -> str:
    return f"08{random.randint(1, 9)}{random.randint(1000000, 9999999)}"


def _random_birthdate(*, min_age: int = 25, max_age: int = 70) -> tuple[date, int]:
    age = random.randint(min_age, max_age)
    birth = date.today() - timedelta(days=age * 365 + random.randint(0, 364))
    return birth, age


async def _load_lookup_pool(session: AsyncSession) -> _LookupPool:
    async def ids(model) -> list[int]:  # noqa: ANN001
        return list((await session.scalars(select(model.id))).all())

    pool = _LookupPool(
        prefix_ids=await ids(PrefixType),
        marital_ids=await ids(MaritalStatusType),
        relation_ids=await ids(RequesterRelationType),
        address_type_ids=await ids(AddressType),
        request_type_ids=await ids(RequestType),
        dependency_ids=await ids(DependencyType),
        housing_ids=await ids(HousingType),
        income_source_ids=await ids(IncomeSourceType),
        occupation_ids=await ids(OccupationType),
        bank_name_ids=await ids(BankName),
        bank_account_type_ids=await ids(BankAccountType),
    )
    required = {
        "prefix_type": pool.prefix_ids,
        "marital_status_types": pool.marital_ids,
        "requester_relation_type": pool.relation_ids,
        "address_type": pool.address_type_ids,
        "request_types": pool.request_type_ids,
        "housing_types": pool.housing_ids,
        "income_source_types": pool.income_source_ids,
        "occupation_types": pool.occupation_ids,
    }
    missing = [name for name, vals in required.items() if not vals]
    if missing:
        raise ValueError(f"missing_lookup_data: {', '.join(missing)}")
    return pool


async def _random_postcode_row(
    session: AsyncSession,
    *,
    province_id: int | None,
) -> tuple[SubDistrictPostcode, int | None, str | None]:
    """คืน (sub_district_postcode, province_id, province_name)."""
    stmt = (
        select(SubDistrictPostcode, Province.id, Province.name)
        .join(SubDistrict, SubDistrict.id == SubDistrictPostcode.sub_district_id)
        .join(District, District.id == SubDistrict.district_id)
        .join(Province, Province.id == District.province_id)
        .order_by(func.random())
        .limit(1)
    )
    if province_id is not None:
        stmt = stmt.where(Province.id == province_id)

    row = (await session.execute(stmt)).first()
    if row is None:
        raise ValueError(
            "no_postcode_for_province" if province_id is not None else "no_postcode_data"
        )
    sdp, pid, pname = row
    return sdp, int(pid), str(pname)


async def create_random_case(
    session: AsyncSession,
    *,
    province_id: int | None = None,
    pool: _LookupPool | None = None,
) -> RandomCaseCreated:
    """สร้าง person + คำร้องสุ่ม 1 รายการ (ไม่ส่งอีเมลแจ้งเตือน)."""
    if pool is None:
        pool = await _load_lookup_pool(session)
    sdp, resolved_province_id, province_name = await _random_postcode_row(
        session, province_id=province_id
    )

    is_male = random.choice((True, False))
    # prefix: พยายามเลือกตามเพศถ้ามี id มาตรฐาน (1=นาย, 2=นาง, 3=นางสาว) ไม่เช่นนั้นสุ่ม
    if is_male and 1 in pool.prefix_ids:
        prefix_id = 1
        first_name = random.choice(_MALE_FIRST)
        gender = "ชาย"
    elif not is_male:
        female_prefixes = [i for i in (2, 3) if i in pool.prefix_ids]
        prefix_id = random.choice(female_prefixes) if female_prefixes else _pick(pool.prefix_ids)
        first_name = random.choice(_FEMALE_FIRST)
        gender = "หญิง"
    else:
        prefix_id = _pick(pool.prefix_ids)
        first_name = random.choice(_MALE_FIRST)
        gender = "ชาย"

    last_name = random.choice(_LAST_NAMES)
    birth_date, age = _random_birthdate()
    mobile = _random_phone()

    cid = await _unique_mock_cid(session)
    person = Person(
        prefix_id=prefix_id,
        first_name=first_name,
        last_name=last_name,
        cid=cid,
        birth_date=birth_date,
        sub_district_postcode_id=sdp.id,
        gender=gender,
        adr_moo=str(random.randint(1, 20)),
        adr_house_num=f"{random.randint(1, 200)}/{random.randint(1, 50)}",
    )
    session.add(person)
    await session.flush()

    bank_name_id = _pick(pool.bank_name_ids) if pool.bank_name_ids else None
    bank_account_type_id = (
        _pick(pool.bank_account_type_ids) if pool.bank_account_type_ids else None
    )
    bank_account_no = "".join(str(random.randint(0, 9)) for _ in range(10))

    address_payloads = [
        AddressInCase(
            sub_district_postcode_id=sdp.id,
            address_type_id=atype_id,
            house_moo=person.adr_moo,
            house_number=person.adr_house_num,
            mobile_phone=mobile,
            road=f"ถนนทดสอบ {random.randint(1, 99)}",
        )
        for atype_id in pool.address_type_ids[:2] or [_pick(pool.address_type_ids)]
    ]

    # ไม่เรียก external check — person ใหม่จาก admin ถือเป็นรายใหม่เสมอ
    existing_check = ExistingCaseCheckResult(
        cid=cid,
        is_existing_case=False,
        sources=[
            SourceCheckResult(
                source="vcare_main",
                found=False,
                available=True,
                message="admin_random",
            )
        ],
    )
    audit_fields = await build_submission_audit_fields(
        session,
        existing_check=existing_check,
        addresses=address_payloads,
        bank_account_no=bank_account_no,
    )

    applicant = Applicant(
        persons_id=person.id,
        requester_relation_id=_pick(pool.relation_ids),
        marital_status_id=_pick(pool.marital_ids),
        mobile_phone=mobile,
        email_address=f"mock.{cid}@example.com",
        problem_details=random.choice(_PROBLEMS),
        bank_name_id=bank_name_id,
        bank_account_no=bank_account_no,
        bank_account_type_id=bank_account_type_id,
        bank_branch_name=f"สาขาทดสอบ {random.randint(1, 50)}",
        age=age,
        is_existing_case=False,
    )
    session.add(applicant)
    await session.flush()

    applicant.case_number = await allocate_case_number(
        session, reference=applicant.created_at
    )
    await session.flush()
    aid = applicant.id

    session.add(ApplicantSubmissionAudit(applicant_id=aid, **audit_fields))

    for addr in address_payloads:
        session.add(
            Address(
                sub_district_postcode_id=addr.sub_district_postcode_id,
                applicant_id=aid,
                address_type_id=addr.address_type_id,
                road=addr.road,
                house_moo=addr.house_moo,
                house_number=addr.house_number,
                mobile_phone=addr.mobile_phone,
            )
        )

    if pool.dependency_ids:
        dep_id = _pick_non_other(pool.dependency_ids)
        session.add(
            DependencyLoad(applicant_id=aid, dependency_type_id=dep_id)
        )

    occupation_id = _pick_non_other(pool.occupation_ids)
    income_id = _pick_non_other(pool.income_source_ids)
    housing_id = _pick(pool.housing_ids)
    monthly_income = Decimal(random.randint(3000, 15000))

    econ = EconomicInfo(
        applicant_id=aid,
        housing_types_id=housing_id,
        occupation_type_id=occupation_id,
        occupation=None,
        monthly_income=monthly_income,
        household_members=0,
        family_occupation_type_id=occupation_id,
    )
    session.add(econ)
    await session.flush()
    session.add(
        EconomicIncomeSource(
            economic_id=econ.id,
            income_source_type_id=income_id,
        )
    )

    # สมาชิกครัวเรือน 0–2 คน
    member_count = random.randint(0, 2)
    household_member_ids: list[int] = []
    for seq in range(1, member_count + 1):
        m_male = random.choice((True, False))
        member = HouseholdMember(
            applicant_id=aid,
            seq=seq,
            prefix_id=1 if m_male and 1 in pool.prefix_ids else _pick(pool.prefix_ids),
            first_name=random.choice(_MALE_FIRST if m_male else _FEMALE_FIRST),
            last_name=last_name,
            date_of_birth=_random_birthdate(min_age=5, max_age=60)[0],
            occupation_type_id=_pick_non_other(pool.occupation_ids),
            monthly_income=Decimal(random.randint(0, 8000)),
            physical_condition="normal",
            self_care=True,
        )
        session.add(member)
        await session.flush()
        household_member_ids.append(member.id)
    econ.household_members = member_count

    # ประเภทคำร้อง 1–2 รายการ (หลีกเลี่ยง id=99 ถ้ามีตัวเลือกอื่น)
    req_candidates = [i for i in pool.request_type_ids if i != OTHER_TYPE_ID] or pool.request_type_ids
    k = min(len(req_candidates), random.randint(1, 2))
    req_ids = random.sample(req_candidates, k=k)
    for rt in req_ids:
        session.add(
            WelfareRequestType(
                applicant_id=aid,
                request_type_id=rt,
                request_other_text="ช่วยเหลือเรื่องอื่นๆ (สุ่ม)" if rt == 3 else None,
                request_in_kind_text="สิ่งของจำเป็น (สุ่ม)" if rt == 2 else None,
            )
        )

    has_welfare = random.choice((True, False))
    session.add(
        WelfareHistory(
            applicant_id=aid,
            has_received_welfare=has_welfare,
            received_count=random.randint(1, 3) if has_welfare else 0,
            total_received_amount=(
                Decimal(random.randint(1000, 10000)) if has_welfare else None
            ),
        )
    )

    session.add(
        WelfareRequestStatus(
            applicant_id=aid,
            current_status_id=1,
            remarks=None,
            update_by_sdshv=None,
        )
    )
    await session.flush()

    await attach_random_case_placeholders(
        session,
        applicant_id=aid,
        household_member_ids=household_member_ids,
    )

    return RandomCaseCreated(
        applicant_id=aid,
        case_number=applicant.case_number,
        persons_id=person.id,
        cid=cid,
        full_name=f"{first_name} {last_name}",
        province_id=resolved_province_id,
        province_name=province_name,
    )


async def create_random_cases(
    session: AsyncSession,
    *,
    count: int,
    province_id: int | None = None,
) -> list[RandomCaseCreated]:
    pool = await _load_lookup_pool(session)
    results: list[RandomCaseCreated] = []
    for _ in range(count):
        results.append(
            await create_random_case(session, province_id=province_id, pool=pool)
        )
    return results
