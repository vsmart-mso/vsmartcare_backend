from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api.ocr import router as ocr_router
from .core.database import engine
from .models.ocr_result import Base
from .settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr-service")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """สร้างตารางตอน startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created (if not exist)")
    yield


_TAGS = [
    {"name": "ocr", "description": "OCR Pipeline — Gemini Flash"},
    {"name": "meta", "description": "Health checks"},
]

app = FastAPI(
    title=settings.service_name,
    version="0.1.0",
    openapi_tags=_TAGS,
    lifespan=lifespan,
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
