from __future__ import annotations

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api.ocr import router as ocr_router
from .settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr-service")


def _validate_production_config() -> None:
    if (settings.app_env or "").strip().lower() not in {"production", "prod"}:
        return
    missing: list[str] = []
    if not settings.gemini_api_key.strip():
        missing.append("GEMINI_API_KEY")
    if not settings.ocr_api_key.strip():
        missing.append("OCR_API_KEY")
    if missing:
        raise RuntimeError(f"Production config incomplete: {', '.join(missing)}")


@asynccontextmanager
async def _lifespan(_: FastAPI):
    _validate_production_config()
    if not (settings.gemini_api_key or "").strip():
        logger.warning(
            "GEMINI_API_KEY is not set — OCR will return 503 until configured "
            "(create ocr-service/.env from .env.example)"
        )
    yield


_TAGS = [
    {"name": "ocr", "description": "OCR Pipeline — Gemini Flash"},
    {"name": "meta", "description": "Health checks"},
]

app = FastAPI(
    title=settings.service_name,
    version="0.1.0",
    openapi_tags=_TAGS,
    lifespan=_lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logging middleware ─────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"→ {request.method} {request.url.path} | origin={request.headers.get('origin', '-')}")
    response = await call_next(request)
    logger.info(f"← {request.method} {request.url.path} | status={response.status_code}")
    return response


@app.get("/", tags=["meta"])
def root():
    return {"service": settings.service_name, "ok": True}


@app.get("/healthz", tags=["meta"])
def healthz():
    return {"ok": True}


@app.get("/readyz", tags=["meta"])
def readyz():
    return {"ok": True}


app.include_router(ocr_router)
