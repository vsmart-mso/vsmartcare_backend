"""Validate uploaded files by magic bytes (ME-05)."""

from __future__ import annotations

from fastapi import HTTPException, status

_IMAGE_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
    ".gif": (b"GIF87a", b"GIF89a"),
}

_PDF_SIGNATURE = b"%PDF"


def detect_image_extension(blob: bytes) -> str | None:
    """Return file extension including dot when blob matches a known image signature."""
    if len(blob) < 12:
        return None
    for ext, prefixes in _IMAGE_SIGNATURES.items():
        for prefix in prefixes:
            if ext == ".webp":
                if blob[:4] == prefix and blob[8:12] == b"WEBP":
                    return ext
            elif blob.startswith(prefix):
                return ext
    return None


def assert_image_magic_bytes(blob: bytes, *, allowed_exts: set[str] | None = None) -> str:
    ext = detect_image_extension(blob)
    allowed = allowed_exts or set(_IMAGE_SIGNATURES)
    if ext is None or ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported_file_content",
        )
    return ext


def assert_pdf_magic_bytes(blob: bytes) -> None:
    if not blob.startswith(_PDF_SIGNATURE):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported_file_content",
        )
