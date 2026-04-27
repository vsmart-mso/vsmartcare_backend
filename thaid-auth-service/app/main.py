from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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


class LoginStartResponse(BaseModel):
    authorization_url: str
    state: str


states: Dict[str, datetime] = {}
sessions: Dict[str, Dict[str, str]] = {}


@app.post("/v1/auth/thaid/login", response_model=LoginStartResponse)
def start_login():
    """
    Starter/mock endpoint.
    In production: redirect user to ThaiD authorization endpoint (OIDC/OAuth2).
    """
    state = str(uuid4())
    states[state] = datetime.utcnow()
    # Mock URL for now (front-end can open it or use it as info)
    authorization_url = f"https://thaid.example/authorize?client_id={settings.thaid_client_id}&state={state}"
    return LoginStartResponse(authorization_url=authorization_url, state=state)


class CallbackResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


@app.get("/v1/auth/thaid/callback", response_model=CallbackResponse)
def callback(state: str, code: Optional[str] = None):
    """
    Starter/mock callback.
    In production: exchange `code` for tokens with ThaiD, validate, then issue internal token.
    """
    created_at = states.get(state)
    if not created_at:
        raise HTTPException(status_code=400, detail="invalid_state")
    if datetime.utcnow() - created_at > timedelta(minutes=10):
        raise HTTPException(status_code=400, detail="state_expired")

    token = str(uuid4())
    sessions[token] = {"user_id": "mock-user", "provider": "thaid"}
    return CallbackResponse(access_token=token)


class MeResponse(BaseModel):
    user_id: str
    provider: str


@app.get("/v1/me", response_model=MeResponse)
def me(authorization: Optional[str] = None):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    token = authorization.split(" ", 1)[1].strip()
    s = sessions.get(token)
    if not s:
        raise HTTPException(status_code=401, detail="invalid_token")
    return MeResponse(user_id=s["user_id"], provider=s["provider"])

