"""Re-export ทุก ORM model เพื่อให้ Alembic autogenerate มองเห็น metadata ครบ."""

from .address import Address
from .applicant import Applicant
from .dependency import DependencyLoad
from .economic import EconomicIncomeSource, EconomicInfo
from .geo import District, Postcode, Province, SubDistrict, SubDistrictPostcode
from .intake import (
    AnnouncementRegulation,
    CaseHandling,
    CaseKtbCorporate,
    CasePayment,
    CaseRegulationChoice,
    KtbNotifyChannel,
    KtbRecipientCategory,
    PaymentMethod,
)
from .lookup import (
    AddressType,
    AttachmentType,
    BankName,
    CurrentStatus,
    DependencyType,
    HousingType,
    IncomeSourceType,
    MaritalStatusType,
    PrefixType,
    ReceivedWelfareType,
    RequesterRelationType,
    RequestType,
    TypeMoney,
    TypeMoneyCategory,
)
from .payment import ApproveCase, FilePayment, WelfareDdaRef, WelfarePayment
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
    "AnnouncementRegulation",
    "Applicant",
    "AttachmentType",
    "BankName",
    "CaseHandling",
    "CaseKtbCorporate",
    "CasePayment",
    "CaseRegulationChoice",
    "CurrentStatus",
    "DependencyLoad",
    "DependencyType",
    "District",
    "EconomicIncomeSource",
    "EconomicInfo",
    "HousingType",
    "IncomeSourceType",
    "KtbNotifyChannel",
    "KtbRecipientCategory",
    "MaritalStatusType",
    "PaymentMethod",
    "Person",
    "Postcode",
    "PrefixType",
    "Province",
    "ApproveCase",
    "FilePayment",
    "ReceivedWelfareType",
    "RequestType",
    "RequesterRelationType",
    "ScreeningLog",
    "SubDistrict",
    "SubDistrictPostcode",
    "TypeMoney",
    "TypeMoneyCategory",
    "WelfareDdaRef",
    "WelfareEvidence",
    "WelfareHistory",
    "WelfareHistoryDetail",
    "WelfarePayment",
    "WelfareRequestConsent",
    "WelfareRequestStatus",
    "WelfareRequestType",
]
