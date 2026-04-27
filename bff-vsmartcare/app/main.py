from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .settings import settings


app = FastAPI(title=settings.service_name, version="0.1.0")


@app.get("/")
def root():
    return {"service": settings.service_name, "ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz():
    return {"ok": True}


async def _post(url: str, json: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=json)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _get(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers=headers)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


class CreateCaseRequest(BaseModel):
    type: str
    title: str
    description: Optional[str] = None
    requester_user_id: Optional[str] = None
    payload: Dict[str, Any] = {}


@app.post("/v1/cases")
async def create_case(body: CreateCaseRequest):
    return await _post(f"{settings.case_service_url}/v1/cases", json=body.model_dump())


@app.get("/v1/cases/{case_id}")
async def get_case(case_id: str):
    return await _get(f"{settings.case_service_url}/v1/cases/{case_id}")


class CreateNotificationRequest(BaseModel):
    idempotency_key: str
    channel: str
    to: str
    template_code: str
    payload: Dict[str, Any] = {}


@app.post("/v1/notifications")
async def create_notification(body: CreateNotificationRequest):
    return await _post(f"{settings.notification_service_url}/v1/notifications", json=body.model_dump())


@app.post("/v1/auth/thaid/login")
async def thaid_login():
    return await _post(f"{settings.thaid_auth_service_url}/v1/auth/thaid/login", json={})


@app.get("/v1/me")
async def me(authorization: Optional[str] = None):
    headers = {}
    if authorization:
        headers["Authorization"] = authorization
    return await _get(f"{settings.thaid_auth_service_url}/v1/me", headers=headers)

