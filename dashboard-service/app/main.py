from __future__ import annotations

from fastapi import FastAPI

from .api.v1.dashboard import router as dashboard_router
from .settings import settings

_TAGS = [
    {"name": "dashboard", "description": "สรุปจำนวนคำร้องรายจังหวัด/อำเภอ สำหรับหน้า dashboard"},
    {"name": "meta", "description": "ข้อมูล service และ health checks"},
]

app = FastAPI(title=settings.service_name, version="0.1.0", openapi_tags=_TAGS)

app.include_router(dashboard_router)


@app.get("/", tags=["meta"])
def root():
    return {"service": settings.service_name, "ok": True}


@app.get("/healthz", tags=["meta"])
def healthz():
    return {"ok": True}


@app.get("/readyz", tags=["meta"])
def readyz():
    return {"ok": True}
