"""Re-export ทุก ORM model เพื่อให้ Alembic autogenerate มองเห็น metadata ครบ."""

from .address import Address
from .admin import AdminUser, ProvinceAccessConfig
from .staff import SecurityAuditLog, StaffUser
from .applicant import Applicant
from .article import Article
from .cover_document_batch import CoverDocumentBatch
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
from .mso_send import MoreMso, SendData, TypeSend
from .lookup import (
    AddressType,
    AttachmentType,
    BankAccountType,
    BankName,
    CurrentStatus,
    DependencyType,
    HardshipStatusType,
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
from .ocr_result import OcrResult
from .payment import ApproveCase, FilePayment, WelfareDdaRef, WelfarePayment
from .person import Person
from .screening import ScreeningLog, WelfareRequestConsent
from .review import ReviewField, WelfareReviewComment
from .satisfaction import SatisfactionSurvey
from .case_data_edit_log import CaseDataEditLog
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
    "AdminUser",
    "AnnouncementRegulation",
    "Applicant",
    "Article",
    "CoverDocumentBatch",
    "AttachmentType",
    "BankAccountType",
    "BankName",
    "CaseDataEditLog",
    "CaseHandling",
    "CaseKtbCorporate",
    "CasePayment",
    "CaseRegulationChoice",
    "CurrentStatus",
    "DependencyLoad",
    "DependencyType",
    "District",
    "HardshipStatusType",
    "EconomicIncomeSource",
    "EconomicInfo",
    "HousingType",
    "IncomeSourceType",
    "KtbNotifyChannel",
    "KtbRecipientCategory",
    "MaritalStatusType",
    "MoreMso",
    "OcrResult",
    "PaymentMethod",
    "Person",
    "Postcode",
    "PrefixType",
    "Province",
    "ProvinceAccessConfig",
    "ApproveCase",
    "FilePayment",
    "ReceivedWelfareType",
    "RequestType",
    "RequesterRelationType",
    "ScreeningLog",
    "SendData",
    "SubDistrict",
    "SubDistrictPostcode",
    "TypeMoney",
    "TypeMoneyCategory",
    "TypeSend",
    "WelfareDdaRef",
    "WelfareEvidence",
    "WelfareHistory",
    "WelfareHistoryDetail",
    "WelfarePayment",
    "WelfareRequestConsent",
    "WelfareRequestStatus",
    "WelfareRequestType",
    "ReviewField",
    "SatisfactionSurvey",
    "WelfareReviewComment",
]
