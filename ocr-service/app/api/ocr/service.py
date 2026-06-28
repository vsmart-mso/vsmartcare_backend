"""Gemini OCR Service — เรียก Gemini API เพื่อทำ OCR จากรูปภาพ พร้อมสกัดข้อมูลบัญชีธนาคาร."""

from __future__ import annotations

import base64
import json
import re
from difflib import SequenceMatcher

from ...settings import settings
from .schemas import BankInfo, MatchStatus


def _image_to_base64(image_bytes: bytes) -> str:
    """แปลง bytes ของรูปเป็น base64 string สำหรับ Gemini API."""
    return base64.b64encode(image_bytes).decode("utf-8")


def _resize_image(image_bytes: bytes, max_dim: int) -> tuple[bytes, int, int]:
    """ปรับขนาดรูปให้ด้านยาวสุด ≤ max_dim px — คงสัดส่วนเดิม.

    Returns (resized_bytes, original_w, original_h).
    """
    import cv2
    import numpy as np

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes, 0, 0

    h, w = img.shape[:2]
    if max(h, w) <= max_dim:
        # ไม่ต้อง resize จริง แต่ encode กลับเป็น bytes ให้ format เดิม
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buf.tobytes(), w, h

    scale = max_dim / max(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    _, buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes(), w, h


def _detect_blur(image_bytes: bytes) -> bool:
    """ตรวจสอบว่ารูปเบลอเกิน BLUR_THRESHOLD หรือไม่ โดยใช้ variance of Laplacian.

    Returns True ถ้าเบลอเกิน threshold.
    """
    import cv2
    import numpy as np

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return False
        laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
        return laplacian_var < settings.blur_threshold
    except Exception:
        return False


def _normalize_text(text: str) -> str:
    """ลบ whitespace ซ้ำ, ตัดขอบ, เป็น lowercase."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _fuzzy_score(a: str, b: str) -> float:
    """คำนวณคะแนนความคล้ายของข้อความ (0-100)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio() * 100.0


def _clean_optional_text(value: object) -> str | None:
    """Normalize nullable text from model output."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_account_number(value: object) -> str | None:
    """Allow only digits and dashes for account number."""
    text = _clean_optional_text(value)
    if not text:
        return None
    if re.search(r"[A-Za-z*#]", text):
        return None
    if not re.fullmatch(r"[0-9-]+", text):
        return None
    if not re.search(r"[0-9]", text):
        return None
    return text


def _validate_branch_code(value: object) -> str | None:
    """Allow only numeric branch code."""
    text = _clean_optional_text(value)
    if not text:
        return None
    if not re.fullmatch(r"[0-9]{2,6}", text):
        return None
    return text


# คำนำหน้าที่ใช้เปรียบเทียบ
_TH_TITLES: set[str] = {
    "นาย", "นาง", "นางสาว", "เด็กชาย", "เด็กหญิง",
    "ว่าที่ร้อยตรี", "ว่าที่ร้อยโท", "ว่าที่ร้อยเอก",
    "ร้อยตรี", "ร้อยโท", "ร้อยเอก",
    "พันตรี", "พันโท", "พันเอก",
    "นาวาอากาศตรี", "นาวาอากาศโท", "นาวาอากาศเอก",
    "จ่าสิบตรี", "จ่าสิบโท", "จ่าสิบเอก",
    "สิบตรี", "สิบโท", "สิบเอก",
}

_TH_TITLE_ALIASES: dict[str, str] = {
    "น.ส.": "นางสาว",
    "นส.": "นางสาว",
    "นส": "นางสาว",
    "ด.ช.": "เด็กชาย",
    "ดช.": "เด็กชาย",
    "ดช": "เด็กชาย",
    "ด.ญ.": "เด็กหญิง",
    "ดญ.": "เด็กหญิง",
    "ดญ": "เด็กหญิง",
    "ว่าที่ ร.ต.": "ว่าที่ร้อยตรี",
    "ว่าที่ร.ต.": "ว่าที่ร้อยตรี",
    "ว่าที่ ร.ท.": "ว่าที่ร้อยโท",
    "ว่าที่ร.ท.": "ว่าที่ร้อยโท",
    "ว่าที่ ร.อ.": "ว่าที่ร้อยเอก",
    "ว่าที่ร.อ.": "ว่าที่ร้อยเอก",
    "ร.ต.": "ร้อยตรี",
    "ร.ท.": "ร้อยโท",
    "ร.อ.": "ร้อยเอก",
    "พ.ต.": "พันตรี",
    "พ.ท.": "พันโท",
    "พ.อ.": "พันเอก",
    "น.ต.": "นาวาอากาศตรี",
    "น.ท.": "นาวาอากาศโท",
    "น.อ.": "นาวาอากาศเอก",
    "จ.ส.ต.": "จ่าสิบตรี",
    "จ.ส.ท.": "จ่าสิบโท",
    "จ.ส.อ.": "จ่าสิบเอก",
    "ส.ต.": "สิบตรี",
    "ส.ท.": "สิบโท",
    "ส.อ.": "สิบเอก",
}


def _title_candidates() -> list[tuple[str, str]]:
    """Return (raw title/alias, canonical title), longest raw value first."""
    candidates = [(title, title) for title in _TH_TITLES]
    candidates.extend(_TH_TITLE_ALIASES.items())
    return sorted(candidates, key=lambda item: len(item[0]), reverse=True)


def _split_title_name(full_name: str) -> tuple[str, str]:
    """แยกคำนำหน้าออกจากชื่อ-นามสกุล.

    Returns (title, name_rest).
    - title="" ถ้าไม่มีคำนำหน้า
    - name_rest คือชื่อที่เหลือหลังตัดคำนำหน้าออก
    """
    full = _normalize_text(full_name)
    for raw_title, canonical_title in _title_candidates():
        if full == raw_title:
            return canonical_title, ""
        if full.startswith(raw_title):
            name_rest = full[len(raw_title):].strip()
            return canonical_title, name_rest
    # ไม่เจอคำนำหน้า → ทั้งหมดเป็นชื่อ
    return "", full


def _titles_compatible(title_a: str, title_b: str) -> bool:
    """ตรวจสอบว่าคำนำหน้าชื่อทั้งสองเข้ากันได้ (ไม่ขัดแย้ง)."""
    title_a = title_a.strip()
    title_b = title_b.strip()
    if not title_a or not title_b:
        return True
    if title_a == title_b:
        return True

    male_titles = {"นาย", "เด็กชาย"}
    female_titles = {"นาง", "นางสาว", "เด็กหญิง"}

    a_male = title_a in male_titles
    a_female = title_a in female_titles
    b_male = title_b in male_titles
    b_female = title_b in female_titles

    if (a_male and b_female) or (a_female and b_male):
        return False
    return True


def _determine_match_status(
    fuzzy_score: float,
    ocr_title: str,
    target_title: str,
    is_blurry: bool,
    has_text: bool,
) -> MatchStatus:
    """ตัดสิน match_status จากคะแนน fuzzy + title compatibility + image quality."""
    if is_blurry:
        return MatchStatus.blurry
    if not has_text:
        return MatchStatus.no_text

    if not _titles_compatible(ocr_title, target_title):
        return MatchStatus.mismatch

    if fuzzy_score >= settings.fuzzy_match_threshold:
        return MatchStatus.match
    if fuzzy_score >= settings.fuzzy_review_threshold:
        return MatchStatus.review
    return MatchStatus.mismatch


_OCR_PROMPT_TEMPLATE = """You are a precise OCR engine for Thai bank account book images.

Analyze the image and return ONLY a JSON object with the following structure.
Do NOT include markdown fences or any other text.

{
  "markdown": "full OCR text in markdown format, preserving structure",
  "bank_info": {
    "account_number": "account number as shown on the book (dashes are allowed)",
    "account_name": "full account holder name in Thai",
    "bank_name": "bank name in Thai",
    "deposit_type": "deposit product type (e.g. savings/current/fixed deposit)",
    "branch_name": "bank branch name in Thai",
    "branch_code": "numeric branch code"
  }
}

Rules:
- Read EVERY character carefully. Do not guess or hallucinate.
- For account_number: extract the full account number exactly as printed ONLY when it passes validation.
- account_number validation rules:
  - Allowed characters are digits (0-9) and optional dashes (-) only.
  - The account number may include dashes (-), but every non-dash character must be a digit (0-9).
  - If it contains any letters or other symbols (e.g. X/x/*/#), treat it as invalid.
  - If the number is masked/obfuscated (e.g. XXX, xxxxx, ***), treat it as invalid.
  - If invalid or uncertain, set account_number to null.
- For account_name: extract the FULL name including title (นาย/นาง/นางสาว).
- For bank_name: recognize the bank logo or printed bank name.
- For deposit_type: extract only real deposit type text. If unclear, masked, or not present, set to null.
- For branch_name: extract only real branch name text. If unclear, masked, or not present, set to null.
- For branch_code: extract only digits (0-9), length 2-6. If it contains non-digits, set to null.
- If any field cannot be read, set its value to null.
- The markdown field must contain ALL visible text on the page, formatted as markdown."""


async def _call_gemini_ocr(image_bytes: bytes, mime_type: str) -> dict:
    """เรียก Gemini API เพื่อทำ OCR จากรูป — ส่งเป็น base64 inline_data."""
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)

    b64 = _image_to_base64(image_bytes)

    response = await client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=[
            _OCR_PROMPT_TEMPLATE,
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64,
                }
            },
        ],
    )

    raw_text = response.text.strip()

    # Gemini อาจ wrap JSON ใน ```json ... ```
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

    return json.loads(raw_text)


async def run_ocr_pipeline(
    image_bytes: bytes,
    target_name: str,
    pre_file_uuid: str,
    mime_type: str = "image/jpeg",
) -> dict:
    """เรียก Gemini OCR + หลังประมวลผล (fuzzy match, bank info, blur check).

    Returns dict ที่ตรงกับ OcrResponse schema.
    """
    import logging
    logger = logging.getLogger("ocr-service")

    # 1. ตรวจจับภาพเบลอ (ใช้รูปต้นฉบับก่อน resize)
    is_blurry = _detect_blur(image_bytes)

    # 2. ปรับขนาดรูปก่อนส่ง Gemini (ลด base64 payload)
    resized_bytes, orig_w, orig_h = _resize_image(image_bytes, settings.max_image_dimension)
    if orig_w > 0:
        logger.info(f"Resize: {orig_w}x{orig_h} → max {settings.max_image_dimension}px, "
                     f"bytes: {len(image_bytes)} → {len(resized_bytes)} "
                     f"({len(resized_bytes) / max(len(image_bytes), 1) * 100:.0f}%)")

    # 3. เรียก Gemini (ใช้รูปที่ resize แล้ว — mime_type เป็น JPEG เสมอหลัง resize)
    result = await _call_gemini_ocr(resized_bytes, "image/jpeg")

    markdown = result.get("markdown", "")
    raw_bank = result.get("bank_info") or {}

    # 4. เช็กว่ามี text จริงหรือไม่
    has_text = bool(markdown.strip()) if markdown else False

    account_number = _validate_account_number(raw_bank.get("account_number"))
    account_name = _clean_optional_text(raw_bank.get("account_name"))
    bank_name = _clean_optional_text(raw_bank.get("bank_name"))
    deposit_type = _clean_optional_text(raw_bank.get("deposit_type"))
    branch_name = _clean_optional_text(raw_bank.get("branch_name"))
    branch_code = _validate_branch_code(raw_bank.get("branch_code"))

    # 5. Fuzzy match — แยกคำนำหน้าออกจากชื่อ และ normalize คำนำหน้าย่อก่อนเช็ก compatibility
    fuzzy_score = 0.0
    ocr_title = ""
    target_title = ""
    ocr_name_only = ""
    target_name_only = ""

    if account_name and target_name:
        # แยกคำนำหน้ากับชื่อ-นามสกุล
        ocr_title, ocr_name_only = _split_title_name(account_name)
        target_title, target_name_only = _split_title_name(target_name)

        # fuzzy match บนชื่อ-นามสกุลเท่านั้น; คำนำหน้าใช้เช็ก compatibility แยกต่างหาก
        fuzzy_score = _fuzzy_score(ocr_name_only, target_name_only)

        logger.info(
            f"Fuzzy: ocr_title={ocr_title!r} ocr_name={ocr_name_only!r} | "
            f"target_title={target_title!r} target_name={target_name_only!r} | "
            f"score={fuzzy_score:.2f}"
        )

    # 6. ตัดสิน match_status
    match_status = _determine_match_status(
        fuzzy_score=fuzzy_score,
        ocr_title=ocr_title,
        target_title=target_title,
        is_blurry=is_blurry,
        has_text=has_text,
    )

    return {
        "markdown": markdown,
        "bank_info": BankInfo(
            account_number=account_number,
            account_name=account_name,
            bank_name=bank_name,
            deposit_type=deposit_type,
            branch_name=branch_name,
            branch_code=branch_code,
            match_status=match_status,
            fuzzy_score=round(fuzzy_score, 2),
        ).model_dump(),
        "target_name_checked": target_name,
        "pre_file": pre_file_uuid,
    }


