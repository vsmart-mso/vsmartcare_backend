from __future__ import annotations

import csv
import itertools
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from locust import HttpUser, between, task
from locust.clients import HttpSession
from locust.exception import StopUser


ROOT_DIR = Path(__file__).resolve().parent
DOTENV_PATH = ROOT_DIR / ".env"
PERSON_IDS_FILE_DEFAULT = ROOT_DIR / "person_ids.csv"
_ONE_BY_ONE_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
_DEFAULT_ATTACHMENT_TYPES = [1, 2, 3, 4, 5, 6, 7, 8]


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


_load_dotenv(DOTENV_PATH)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw is not None else default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw is not None else default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int_list(name: str, default: list[int]) -> list[int]:
    raw = _env(name)
    if raw is None:
        return list(default)
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            values.append(int(part))
    return values or list(default)


def _json_detail(response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:400]
    if isinstance(data, dict):
        detail = data.get("detail", data)
        return json.dumps(detail, ensure_ascii=False)[:400]
    return json.dumps(data, ensure_ascii=False)[:400]


@dataclass(frozen=True)
class LoadProfile:
    bff_host: str
    bff_api_prefix: str
    bff_api_key: str | None
    ocr_host: str
    ocr_bearer_token: str | None
    persons_id_cycle: tuple[int, ...]
    sub_district_postcode_id: int
    marital_status_id: int
    requester_relation_id: int
    bank_name_id: int
    bank_account_type_id: int
    housing_types_id: int
    address_type_id: int
    request_type_ids: tuple[int, ...]
    initial_current_status_id: int
    attachment_type_ids: tuple[int, ...]
    enable_ocr_link: bool
    target_name: str
    mobile_phone: str
    email_domain: str


class PersonIdPool:
    def __init__(self, values: tuple[int, ...]) -> None:
        if not values:
            raise ValueError("At least one persons_id is required")
        self._cycle = itertools.cycle(values)
        self._lock = Lock()

    def next(self) -> int:
        with self._lock:
            return next(self._cycle)


class SubmitRequestUser(HttpUser):
    host = _env("LOCUST_BFF_HOST", "http://localhost:8000") or "http://localhost:8000"
    wait_time = between(_env_float("LOCUST_WAIT_MIN_SECONDS", 1.0), _env_float("LOCUST_WAIT_MAX_SECONDS", 3.0))

    profile: LoadProfile
    person_ids: PersonIdPool
    ocr_client: HttpSession

    def on_start(self) -> None:
        self.profile = build_profile()
        self.person_ids = PersonIdPool(self.profile.persons_id_cycle)
        self.host = self.profile.bff_host.rstrip("/")
        self.client.base_url = self.profile.bff_host.rstrip("/")
        self.client.headers.update(self._bff_headers())
        self.ocr_client = HttpSession(
            base_url=self.profile.ocr_host.rstrip("/"),
            request_event=self.environment.events.request,
            user=self,
        )
        self.ocr_client.headers.update(self._ocr_headers())
        if not self.profile.persons_id_cycle:
            raise StopUser("No persons_id configured")

    def _bff_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.profile.bff_api_key:
            headers["X-API-Key"] = self.profile.bff_api_key
        return headers

    def _ocr_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.profile.ocr_bearer_token:
            headers["Authorization"] = f"Bearer {self.profile.ocr_bearer_token}"
        return headers

    def _next_persons_id(self) -> int:
        return self.person_ids.next()

    def _make_case_payload(self, persons_id: int) -> dict[str, Any]:
        suffix = f"{persons_id}{random.randint(100, 999)}"
        return {
            "applicant": {
                "persons_id": persons_id,
                "requester_relation_id": self.profile.requester_relation_id,
                "marital_status_id": self.profile.marital_status_id,
                "mobile_phone": self.profile.mobile_phone,
                "home_phone": None,
                "fax_number": None,
                "email_address": f"belemansimo@gmail.com",
                "problem_details": "locust submit request load test",
                "bank_name_id": self.profile.bank_name_id,
                "bank_account_no": f"{suffix:0>10}"[:10],
                "bank_account_type_id": self.profile.bank_account_type_id,
                "bank_branch_name": "load-test-branch",
                "age": random.randint(25, 80),
            },
            "addresses": [
                {
                    "sub_district_postcode_id": self.profile.sub_district_postcode_id,
                    "address_type_id": self.profile.address_type_id,
                    "alley": None,
                    "sub_lane": None,
                    "house_name": None,
                    "road": "load-test-road",
                    "house_moo": str(random.randint(1, 9)),
                    "house_number": f"{random.randint(1, 999)}/{random.randint(1, 99)}",
                    "latitude": None,
                    "longitude": None,
                }
            ],
            "dependency_loads": [],
            "economic_infos": [
                {
                    "housing_types_id": self.profile.housing_types_id,
                    "housing_types_rent": None,
                    "occupation": "load-test",
                    "monthly_income": 5000,
                    "household_members": 1,
                    "family_occupation": "load-test-family",
                    "income_sources": [],
                }
            ],
            "household_members": [],
            "request_type_ids": list(self.profile.request_type_ids),
            "request_other_text": None,
            "request_in_kind_text": None,
            "welfare_history": None,
            "initial_current_status_id": self.profile.initial_current_status_id,
        }

    def _make_consent_payload(self, persons_id: int) -> dict[str, Any]:
        return {
            "person_id": persons_id,
            "consent_type": "final",
            "initial_pdpa_accepted": False,
            "initial_terms_accepted": False,
            "initial_warning_accepted": False,
            "final_data_correct_accepted": True,
        }

    def _upload_png_file(self) -> tuple[str, bytes, str]:
        return ("loadtest.png", _ONE_BY_ONE_PNG, "image/png")

    def _eligibility(self, persons_id: int) -> bool:
        path = f"{self.profile.bff_api_prefix}/v1/cases/submission-eligibility"
        with self.client.get(
            path,
            params={"persons_id": persons_id},
            name="BFF GET /v1/cases/submission-eligibility",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}: {_json_detail(response)}")
                return False
            body = response.json()
            if body.get("can_submit") is True:
                response.success()
                return True
            response.failure(f"ineligible: {_json_detail(response)}")
            return False

    def _create_case(self, persons_id: int) -> int | None:
        path = f"{self.profile.bff_api_prefix}/v1/cases"
        payload = self._make_case_payload(persons_id)
        with self.client.post(
            path,
            json=payload,
            name="BFF POST /v1/cases",
            catch_response=True,
        ) as response:
            if response.status_code not in (200, 201):
                response.failure(f"HTTP {response.status_code}: {_json_detail(response)}")
                return None
            body = response.json()
            applicant = body.get("applicant") or {}
            applicant_id = applicant.get("id")
            if not applicant_id:
                response.failure(f"missing applicant.id: {json.dumps(body, ensure_ascii=False)[:400]}")
                return None
            response.success()
            return int(applicant_id)

    def _create_consent(self, persons_id: int) -> bool:
        path = f"{self.profile.bff_api_prefix}/v1/welfare-request-consents"
        with self.client.post(
            path,
            json=self._make_consent_payload(persons_id),
            name="BFF POST /v1/welfare-request-consents",
            catch_response=True,
        ) as response:
            if response.status_code not in (200, 201):
                response.failure(f"HTTP {response.status_code}: {_json_detail(response)}")
                return False
            response.success()
            return True

    def _upload_evidences(self, applicant_id: int) -> bool:
        path = f"{self.profile.bff_api_prefix}/v1/cases/{applicant_id}/evidences"
        ok = True
        for attachment_type_id in self.profile.attachment_type_ids:
            with self.client.post(
                path,
                data={"attachment_type_id": str(attachment_type_id)},
                files={"file": self._upload_png_file()},
                name="BFF POST /v1/cases/{applicant_id}/evidences",
                catch_response=True,
            ) as response:
                if response.status_code not in (200, 201):
                    response.failure(
                        f"attachment_type_id={attachment_type_id} HTTP {response.status_code}: {_json_detail(response)}"
                    )
                    ok = False
                else:
                    response.success()
        return ok

    def _ocr_then_link(self, applicant_id: int) -> bool:
        if not self.profile.enable_ocr_link:
            return True
        with self.ocr_client.post(
            "/v1/ocr/bank-book",
            data={"target_name": self.profile.target_name},
            files={"file": self._upload_png_file()},
            name="OCR POST /v1/ocr/bank-book",
            catch_response=True,
        ) as response:
            if response.status_code not in (200, 201):
                response.failure(f"HTTP {response.status_code}: {_json_detail(response)}")
                return False
            body = response.json()
            ocr_result_id = body.get("id")
            if not ocr_result_id:
                response.failure(f"missing id: {json.dumps(body, ensure_ascii=False)[:400]}")
                return False
            response.success()

        with self.ocr_client.patch(
            f"/v1/ocr/results/{ocr_result_id}/link",
            json={"applicant_id": applicant_id},
            name="OCR PATCH /v1/ocr/results/{ocr_result_id}/link",
            catch_response=True,
        ) as response:
            if response.status_code not in (200, 201):
                response.failure(f"HTTP {response.status_code}: {_json_detail(response)}")
                return False
            response.success()
            return True

    @task(_env_int("LOCUST_WEIGHT_FULL_FLOW", 3))
    def full_frontend_equivalent_flow(self) -> None:
        persons_id = self._next_persons_id()
        if not self._eligibility(persons_id):
            return
        applicant_id = self._create_case(persons_id)
        if not applicant_id:
            return
        if not self._create_consent(persons_id):
            return
        if not self._upload_evidences(applicant_id):
            return
        self._ocr_then_link(applicant_id)

    @task(_env_int("LOCUST_WEIGHT_CORE_ONLY", 2))
    def core_persistence_only(self) -> None:
        persons_id = self._next_persons_id()
        applicant_id = self._create_case(persons_id)
        if not applicant_id:
            return
        self._create_consent(persons_id)

    @task(_env_int("LOCUST_WEIGHT_UPLOAD_STRESS", 1))
    def file_upload_stress(self) -> None:
        persons_id = self._next_persons_id()
        applicant_id = self._create_case(persons_id)
        if not applicant_id:
            return
        self._upload_evidences(applicant_id)


def _load_person_ids_from_file(path: Path) -> list[int]:
    if not path.is_file():
        return []
    values: list[int] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            raw = row[0].strip()
            if not raw or raw.lower() == "persons_id":
                continue
            values.append(int(raw))
    return values


def build_profile() -> LoadProfile:
    person_ids_csv_path = Path(_env("LOCUST_PERSON_IDS_FILE", str(PERSON_IDS_FILE_DEFAULT)) or str(PERSON_IDS_FILE_DEFAULT))
    person_ids = _env_int_list("LOCUST_PERSON_IDS", [])
    if not person_ids:
        person_ids = _load_person_ids_from_file(person_ids_csv_path)
    if not person_ids:
        raise StopUser(
            "Set LOCUST_PERSON_IDS=1001,1002 or create load_tests/person_ids.csv with a persons_id column"
        )

    return LoadProfile(
        bff_host=_env("LOCUST_BFF_HOST", "http://localhost:8000") or "http://localhost:8000",
        bff_api_prefix=_env("LOCUST_BFF_API_PREFIX", "/api-vsmartcare") or "/api-vsmartcare",
        bff_api_key=_env("LOCUST_BFF_API_KEY", "1234567890"),
        ocr_host=_env("LOCUST_OCR_HOST", "http://localhost:8004") or "http://localhost:8004",
        ocr_bearer_token=_env("LOCUST_OCR_BEARER_TOKEN"),
        persons_id_cycle=tuple(person_ids),
        sub_district_postcode_id=_env_int("LOCUST_SUB_DISTRICT_POSTCODE_ID", 1),
        marital_status_id=_env_int("LOCUST_MARITAL_STATUS_ID", 2),
        requester_relation_id=_env_int("LOCUST_REQUESTER_RELATION_ID", 1),
        bank_name_id=_env_int("LOCUST_BANK_NAME_ID", 1),
        bank_account_type_id=_env_int("LOCUST_BANK_ACCOUNT_TYPE_ID", 1),
        housing_types_id=_env_int("LOCUST_HOUSING_TYPES_ID", 1),
        address_type_id=_env_int("LOCUST_ADDRESS_TYPE_ID", 1),
        request_type_ids=tuple(_env_int_list("LOCUST_REQUEST_TYPE_IDS", [1])),
        initial_current_status_id=_env_int("LOCUST_INITIAL_CURRENT_STATUS_ID", 1),
        attachment_type_ids=tuple(_env_int_list("LOCUST_ATTACHMENT_TYPE_IDS", _DEFAULT_ATTACHMENT_TYPES)),
        enable_ocr_link=_env_bool("LOCUST_ENABLE_OCR_LINK", False),
        target_name=_env("LOCUST_OCR_TARGET_NAME", "Load Test User") or "Load Test User",
        mobile_phone=_env("LOCUST_MOBILE_PHONE", "0811111111") or "0811111111",
        email_domain=_env("LOCUST_EMAIL_DOMAIN", "example.com") or "example.com",
    )
