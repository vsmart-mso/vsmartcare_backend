"""บันทึก/อ่านลายเซ็นอิเล็กทรอนิกส์เป็นไฟล์แทน Base64 ใน DB."""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

from ..settings import resolved_upload_root


def save_esignature_base64(applicant_id: int, base64_str: str | None) -> str | None:
    """แปลง Base64 data URL เป็นไฟล์รูปภาพและคืน relative path."""
    if not base64_str or not base64_str.startswith("data:image/"):
        return base64_str

    try:
        header, encoded = base64_str.split(",", 1)
        ext = ".png"
        if "image/jpeg" in header:
            ext = ".jpg"
        elif "image/webp" in header:
            ext = ".webp"

        image_data = base64.b64decode(encoded)

        base_path = resolved_upload_root()
        dest_dir = (base_path / "signatures" / str(applicant_id)).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4().hex}{ext}"
        file_path = dest_dir / filename
        file_path.write_bytes(image_data)

        return f"signatures/{applicant_id}/{filename}"
    except Exception:
        return base64_str


def load_esignature_base64(esignature_path: str | None) -> str | None:
    """อ่านไฟล์ลายเซ็นและแปลงกลับเป็น Base64 data URL."""
    if not esignature_path or esignature_path.startswith("data:image/"):
        return esignature_path

    try:
        base_path = resolved_upload_root()
        full_path = (base_path / esignature_path).resolve()
        full_path.relative_to(base_path.resolve())

        if full_path.exists() and full_path.is_file():
            ext = full_path.suffix.lower()
            mime_type = "image/png"
            if ext in [".jpg", ".jpeg"]:
                mime_type = "image/jpeg"
            elif ext == ".webp":
                mime_type = "image/webp"

            binary_data = full_path.read_bytes()
            encoded = base64.b64encode(binary_data).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}"
    except Exception:
        pass
    return esignature_path
