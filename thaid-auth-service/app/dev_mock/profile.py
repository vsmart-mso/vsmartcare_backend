"""สุ่ม/สร้างโปรไฟล์จำลองสำหรับ mock OIDC (dev/test เท่านั้น)."""

from __future__ import annotations

import json
import random
import re
import secrets
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, TypedDict

from .. import ThaID

BirthdateScenario = Literal["full", "year_be", "year_month_no_day"]

_VALID_BIRTHDATE_SCENARIOS = frozenset({"full", "year_be", "year_month_no_day"})

# YYYY หรือ YYYY-MM-DD / YYYY-MM-00 (ปีอาจเป็น พ.ศ. ≥ 2400)
_PARTIAL_BIRTHDATE_RE = re.compile(
    r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$"
)

_DEFAULT_SEED_PATH = Path(__file__).resolve().parent / "seed" / "mock_profile_seed.json"


class _AddressTemplate(TypedDict):
    address: str
    address_postcode: str


class _AddressSeed(_AddressTemplate, total=False):
    province: str


@lru_cache(maxsize=1)
def load_mock_seed(seed_path: str | None = None) -> Dict[str, Any]:
    """โหลดชุดข้อมูล mock จาก JSON (cache ต่อ process)."""
    path = Path(seed_path) if seed_path else _DEFAULT_SEED_PATH
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"mock seed must be a JSON object: {path}")
    return data


def get_ocr_fixture() -> Dict[str, Any]:
    """อ่านบล็อก ocr_fixture จาก seed — ใช้โปรไฟล์คงที่สำหรับทดสอบ OCR สมุดบัญชี."""
    fixture = load_mock_seed().get("ocr_fixture")
    if not isinstance(fixture, dict):
        raise ValueError("mock_profile_seed.json: ocr_fixture must be an object")
    return fixture


def get_max_mock_age() -> int:
    return int(load_mock_seed().get("max_mock_age", 90))


# อายุสูงสุดของผู้ใช้จำลอง — อ่านจาก seed (ค่าเริ่มต้น 90)
MAX_MOCK_AGE = get_max_mock_age()


def get_mock_addresses() -> List[_AddressTemplate]:
    """ที่อยู่จำลองจาก seed file."""
    rows = load_mock_seed().get("addresses") or []
    out: List[_AddressTemplate] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        address = str(row.get("address") or "").strip()
        postcode = str(row.get("address_postcode") or "").strip()
        if address and postcode:
            out.append({"address": address, "address_postcode": postcode})
    if not out:
        raise ValueError("mock_profile_seed.json: addresses must not be empty")
    return out


def get_mock_provinces_from_seed() -> set[str]:
    """ชื่อจังหวัดจาก seed (ฟิลด์ province) — ใช้ใน unit test."""
    provinces: set[str] = set()
    for row in load_mock_seed().get("addresses") or []:
        if isinstance(row, dict):
            p = str(row.get("province") or "").strip()
            if p:
                provinces.add(p)
    return provinces


def _cid_prefix() -> str:
    raw = str(load_mock_seed().get("cid_prefix") or "99").strip()
    digits = re.sub(r"\D", "", raw)
    return (digits or "99")[:2].ljust(2, "9")


def _first_names(gender: str) -> List[str]:
    seed = load_mock_seed()
    bucket = (seed.get("first_names") or {}).get(gender) or []
    names = [str(n).strip() for n in bucket if str(n).strip()]
    if not names:
        raise ValueError(f"mock_profile_seed.json: first_names.{gender} must not be empty")
    return names


def _last_names() -> List[str]:
    names = [str(n).strip() for n in (load_mock_seed().get("last_names") or []) if str(n).strip()]
    if not names:
        raise ValueError("mock_profile_seed.json: last_names must not be empty")
    return names


def _titles(gender: str) -> List[str]:
    titles = [
        str(t).strip()
        for t in (load_mock_seed().get("titles") or {}).get(gender) or []
        if str(t).strip()
    ]
    if not titles:
        return ["นาย"] if gender == "M" else ["นาง"]
    return titles


def _birthdate_config() -> Dict[str, Any]:
    cfg = load_mock_seed().get("birthdate")
    return cfg if isinstance(cfg, dict) else {}


def _thai_cid_checksum(body12: str) -> int:
    digits = [int(c) for c in body12]
    total = sum(d * (13 - i) for i, d in enumerate(digits))
    return (11 - total % 11) % 10


def generate_mock_thai_cid() -> str:
    """สร้างเลขบัตร 13 หลัก — prefix จาก seed + checksum ถูกต้อง."""
    prefix = _cid_prefix()
    body_len = 12 - len(prefix)
    if body_len < 1:
        raise ValueError("mock_profile_seed.json: cid_prefix too long")
    body = prefix + "".join(str(secrets.randbelow(10)) for _ in range(body_len))
    check = _thai_cid_checksum(body)
    return body + str(check)


def validate_thai_cid(cid: str) -> bool:
    """ตรวจ checksum เลขบัตรไทย (ใช้ใน unit test)."""
    if len(cid) != 13 or not cid.isdigit():
        return False
    return _thai_cid_checksum(cid[:12]) == int(cid[12])


def _clamp_age_range(min_age: int, max_age: int) -> tuple[int, int]:
    cap = get_max_mock_age()
    max_age = min(max_age, cap)
    min_age = max(0, min(min_age, max_age))
    return min_age, max_age


def _age_range(key: str, default_min: int, default_max: int) -> tuple[int, int]:
    cfg = _birthdate_config().get(key) or _birthdate_config().get("age_range") or {}
    min_age = int(cfg.get("min", default_min))
    max_age = int(cfg.get("max", default_max))
    return _clamp_age_range(min_age, max_age)


def _be_year_for_age(age: int) -> int:
    return date.today().year - age + 543


def _parse_birthdate_to_date(raw: str) -> date | None:
    """แปลง birthdate จาก mock/ThaiD — ไม่ส่งเดือน+วัน → 1 ม.ค.; ไม่ส่งวัน → วันที่ 1."""
    text = (raw or "").strip()
    m = _PARTIAL_BIRTHDATE_RE.match(text) if text else None
    if not m:
        return None
    year = int(m.group(1))
    if year >= 2400:
        year -= 543

    def _sent_part(value: str | None) -> int | None:
        if value is None:
            return None
        n = int(value)
        return n if n > 0 else None

    month_sent = _sent_part(m.group(2))
    day_sent = _sent_part(m.group(3))
    if month_sent is None and day_sent is None:
        month, day = 1, 1
    elif month_sent is not None and day_sent is None:
        month, day = month_sent, 1
    elif month_sent is None and day_sent is not None:
        month, day = 1, day_sent
    else:
        month, day = month_sent, day_sent
    try:
        return date(year, month, day)
    except ValueError:
        return None


def estimate_age_years(birthdate: str, *, today: date | None = None) -> int | None:
    """ประมาณอายุจาก birthdate mock/ThaiD."""
    ref = today or date.today()
    born = _parse_birthdate_to_date(birthdate)
    if born is None:
        return None
    years = ref.year - born.year
    if (ref.month, ref.day) < (born.month, born.day):
        years -= 1
    return years


def _random_full_birthdate_ce(min_age: int = 25, max_age: int = 55) -> str:
    """วันเกิดครบรูปแบบ ISO (ค.ศ.) — อายุอยู่ในช่วงที่กำหนดและไม่เกิน max_mock_age."""
    min_age, max_age = _age_range("full_age_range", min_age, max_age)
    today = date.today()
    target_age = random.randint(min_age, max_age)
    birth_year = today.year - target_age
    for _ in range(32):
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        candidate = date(birth_year, month, day)
        age = estimate_age_years(candidate.isoformat(), today=today)
        if age is not None and min_age <= age <= max_age:
            return candidate.isoformat()
    return date(birth_year, today.month, min(today.day, 28)).isoformat()


def _random_year_only_be(min_age: int = 25, max_age: int | None = None) -> str:
    """ปีเกิดอย่างเดียว (พ.ศ. 4 หลัก) — ไม่มีเดือน/วัน."""
    cap = max_age if max_age is not None else get_max_mock_age()
    min_a, max_a = _age_range("year_be_age_range", min_age, cap)
    age = random.randint(min_a, max_a)
    return str(_be_year_for_age(age))


def _random_year_month_no_day_be(min_age: int = 25, max_age: int | None = None) -> str:
    """ปี+เดือน (พ.ศ.) — ไม่มีวัน (ส่งเป็น -00)."""
    cap = max_age if max_age is not None else get_max_mock_age()
    min_a, max_a = _age_range("year_be_age_range", min_age, cap)
    age = random.randint(min_a, max_a)
    be_year = _be_year_for_age(age)
    month = random.randint(1, 12)
    return f"{be_year}-{month:02d}-00"


def random_mock_birthdate() -> tuple[str, BirthdateScenario]:
    """
    สุ่มรูปแบบวันเกิดแบบ ThaiD — **ส่งปีเสมอ** (พ.ศ. หรือครบวัน ค.ศ.)
    เดือน/วันอาจไม่ส่งมา:
    - year_be: '2507'
    - year_month_no_day: '2507-05-00'
    - full: '1990-05-14' (ครบวัน ค.ศ.)
    """
    raw_scenarios = _birthdate_config().get("scenarios") or [
        "year_be",
        "year_month_no_day",
        "full",
    ]
    scenarios: List[BirthdateScenario] = [
        s for s in raw_scenarios if s in _VALID_BIRTHDATE_SCENARIOS
    ]
    if not scenarios:
        scenarios = ["year_be", "year_month_no_day", "full"]
    scenario: BirthdateScenario = random.choice(scenarios)  # type: ignore[arg-type]
    if scenario == "full":
        return _random_full_birthdate_ce(), scenario
    if scenario == "year_month_no_day":
        return _random_year_month_no_day_be(), scenario
    return _random_year_only_be(), scenario


def describe_birthdate_scenario(birthdate: str, scenario: BirthdateScenario | None = None) -> str:
    """คำอธิบายสั้น ๆ สำหรับหน้า dev preview."""
    text = (birthdate or "").strip()
    if not text:
        return "ไม่ส่งมา (ว่าง)"
    if scenario == "year_month_no_day" or re.fullmatch(r"\d{4}-\d{2}-00", text):
        return f"ปี+เดือน พ.ศ. ไม่มีวัน ({text})"
    if scenario == "year_be" or re.fullmatch(r"\d{4}", text):
        return f"ปี พ.ศ. เท่านั้น ({text})"
    return f"ครบวัน ค.ศ. ({text})"


def _address_from_fixture_index(index: int) -> _AddressTemplate:
    addresses = get_mock_addresses()
    if index < 0 or index >= len(addresses):
        raise ValueError(f"mock_profile_seed.json: ocr_fixture.address_index out of range: {index}")
    return addresses[index]


def generate_fixed_mock_profile() -> Dict[str, str]:
    """โปรไฟล์คงที่จาก ocr_fixture — สุ่มเฉพาะ pid (checksum ถูก)."""
    fixture = get_ocr_fixture()
    gender = str(fixture.get("gender") or "M").strip() or "M"
    title_th = str(fixture.get("title_th") or "").strip() or random.choice(_titles(gender))
    given_name = str(fixture.get("given_name") or "").strip()
    family_name = str(fixture.get("family_name") or "").strip()
    if not given_name or not family_name:
        raise ValueError("mock_profile_seed.json: ocr_fixture given_name and family_name required")

    address_index = int(fixture.get("address_index", 0))
    addr_tpl = _address_from_fixture_index(address_index)

    birthdate_raw = str(fixture.get("birthdate") or "").strip()
    if birthdate_raw:
        birthdate = birthdate_raw
        birthdate_scenario: BirthdateScenario = "full"
        if re.fullmatch(r"\d{4}", birthdate):
            birthdate_scenario = "year_be"
        elif re.fullmatch(r"\d{4}-\d{2}-00", birthdate):
            birthdate_scenario = "year_month_no_day"
    else:
        birthdate, birthdate_scenario = random_mock_birthdate()

    profile = {
        "pid": generate_mock_thai_cid(),
        "given_name": given_name,
        "family_name": family_name,
        "title_th": title_th,
        "birthdate": birthdate,
        "gender": gender,
        "address": addr_tpl["address"],
        "address_postcode": addr_tpl["address_postcode"],
    }
    profile["_birthdate_scenario"] = birthdate_scenario
    return profile


def generate_mock_profile() -> Dict[str, str]:
    """สุ่มโปรไฟล์ครบชุดสำหรับ mock login (ดึงชื่อ/ที่อยู่จาก seed JSON)."""
    gender = random.choice(["M", "F"])
    title_th = random.choice(_titles(gender))
    given_name = random.choice(_first_names(gender))

    addr_tpl = random.choice(get_mock_addresses())
    birthdate, birthdate_scenario = random_mock_birthdate()
    profile = {
        "pid": generate_mock_thai_cid(),
        "given_name": given_name,
        "family_name": random.choice(_last_names()),
        "title_th": title_th,
        "birthdate": birthdate,
        "gender": gender,
        "address": addr_tpl["address"],
        "address_postcode": addr_tpl["address_postcode"],
    }
    profile["_birthdate_scenario"] = birthdate_scenario
    return profile


def mock_profile_preview_fields(profile: Dict[str, str]) -> Dict[str, str]:
    """ฟิลด์ที่ส่งไป frontend ในหน้า dev preview."""
    scenario = profile.get("_birthdate_scenario", "")
    birthdate = profile.get("birthdate", "")
    out = {
        "pid": profile.get("pid", ""),
        "given_name": profile.get("given_name", ""),
        "family_name": profile.get("family_name", ""),
        "title_th": profile.get("title_th", ""),
        "birthdate": birthdate,
        "gender": profile.get("gender", ""),
        "address": profile.get("address", ""),
    }
    if scenario in _VALID_BIRTHDATE_SCENARIOS:
        out["birthdate_scenario"] = scenario
        out["birthdate_label"] = describe_birthdate_scenario(
            birthdate, scenario  # type: ignore[arg-type]
        )
    return out


def strip_internal_profile_keys(profile: Dict[str, str]) -> Dict[str, str]:
    """ตัดคีย์ภายใน (ขึ้นต้น _) ก่อนส่ง token / บันทึก persons."""
    return {k: v for k, v in profile.items() if not str(k).startswith("_")}


def parse_province_from_profile(profile: Dict[str, str]) -> str:
    """ดึงชื่อจังหวัดจากที่อยู่."""
    parts = ThaID.parse_thai_address_geo(profile.get("address") or "")
    return (parts.get("province") or "").strip()
