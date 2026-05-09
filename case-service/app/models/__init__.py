"""Re-export ทุก ORM model เพื่อให้ Alembic autogenerate มองเห็น metadata ครบ."""

from .address import Address
from .applicant import Applicant
from .dependency import DependencyLoad
from .economic import EconomicIncomeSource, EconomicInfo
from .geo import District, Postcode, Province, SubDistrict, SubDistrictPostcode
from .lookup import (
    AddressType,
    AttachmentType,
    CurrentStatus,
    DependencyType,
    HousingType,
    IncomeSourceType,
    MaritalStatusType,
    PrefixType,
    ReceivedWelfareType,
    RequestType,
)
from .person import Person
from .screening import ScreeningLog, WelfareRequestConsent
from .status_log import WelfareRequestStatus
from .welfare import (
    WelfareEvidence,
    WelfareHistory,
    WelfareHistoryDetail,
    WelfareRequestType,
)

__all__ = [
    "Address",
    "AddressType",
    "Applicant",
    "AttachmentType",
    "CurrentStatus",
    "DependencyLoad",
    "DependencyType",
    "District",
    "EconomicIncomeSource",
    "EconomicInfo",
    "HousingType",
    "IncomeSourceType",
    "MaritalStatusType",
    "Person",
    "Postcode",
    "PrefixType",
    "Province",
    "ReceivedWelfareType",
    "RequestType",
    "ScreeningLog",
    "SubDistrict",
    "SubDistrictPostcode",
    "WelfareEvidence",
    "WelfareHistory",
    "WelfareHistoryDetail",
    "WelfareRequestConsent",
    "WelfareRequestStatus",
    "WelfareRequestType",
]
