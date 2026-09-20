"""Self-hosted Swagger UI / ReDoc files — หน้า /docs ไม่พึ่ง cdn.jsdelivr.net."""

from __future__ import annotations

import urllib.request
from pathlib import Path

DOCS_ASSETS_DIR = Path(__file__).resolve().parent / "static" / "docs"

SWAGGER_UI_VERSION = "5.17.14"
REDOC_VERSION = "2.5.0"

ASSET_URLS: dict[str, str] = {
    "swagger-ui-bundle.js": (
        f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}/swagger-ui-bundle.js"
    ),
    "swagger-ui.css": (
        f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}/swagger-ui.css"
    ),
    "redoc.standalone.js": (
        f"https://cdn.jsdelivr.net/npm/redoc@{REDOC_VERSION}/bundles/redoc.standalone.js"
    ),
}

REQUIRED_ASSETS = tuple(ASSET_URLS.keys())


def docs_asset_path(name: str) -> Path:
    return DOCS_ASSETS_DIR / name


def missing_docs_assets() -> list[str]:
    return [name for name in REQUIRED_ASSETS if not docs_asset_path(name).is_file()]


def ensure_docs_assets() -> None:
    """Download Swagger UI / ReDoc files if absent (used at image build)."""
    DOCS_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in ASSET_URLS.items():
        dest = docs_asset_path(name)
        if dest.is_file() and dest.stat().st_size > 0:
            continue
        urllib.request.urlretrieve(url, dest)


if __name__ == "__main__":
    ensure_docs_assets()
    leftover = missing_docs_assets()
    if leftover:
        raise SystemExit(f"failed to fetch: {', '.join(leftover)}")
    print(f"docs assets ready in {DOCS_ASSETS_DIR}")
