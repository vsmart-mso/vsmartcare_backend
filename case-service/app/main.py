from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .api.v1.eligibility import router as eligibility_router
from .api.v1.geo import router as geo_router
from .api.v1.lookups import router as lookups_router
from .settings import settings


class CaseStatus(str, Enum):
    submitted = "submitted"
    in_progress = "in_progress"
    done = "done"
    rejected = "rejected"


class CaseCreate(BaseModel):
    type: str = Field(..., examples=["change_service"])
    title: str = Field(..., min_length=3)
    description: Optional[str] = None
    requester_user_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class Case(BaseModel):
    id: str
    type: str
    title: str
    description: Optional[str] = None
    requester_user_id: Optional[str] = None
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    events: List[Dict[str, Any]] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)


db: Dict[str, Case] = {}

app = FastAPI(title=settings.service_name, version="0.1.0")

app.include_router(lookups_router)
app.include_router(geo_router)
app.include_router(eligibility_router)


@app.get("/")
def root():
    return {"service": settings.service_name, "ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz():
    return {"ok": True}


@app.post("/v1/cases", response_model=Case)
def create_case(body: CaseCreate):
    now = datetime.utcnow()
    case_id = str(uuid4())
    case = Case(
        id=case_id,
        type=body.type,
        title=body.title,
        description=body.description,
        requester_user_id=body.requester_user_id,
        status=CaseStatus.submitted,
        created_at=now,
        updated_at=now,
        events=[{"at": now.isoformat() + "Z", "type": "CaseCreated"}],
        payload=body.payload,
    )
    db[case_id] = case
    return case


@app.get("/v1/cases/{case_id}", response_model=Case)
def get_case(case_id: str):
    case = db.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case_not_found")
    return case


class CaseStatusUpdate(BaseModel):
    status: CaseStatus
    note: Optional[str] = None


@app.post("/v1/cases/{case_id}/status", response_model=Case)
def update_case_status(case_id: str, body: CaseStatusUpdate):
    case = db.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case_not_found")

    now = datetime.utcnow()
    case.status = body.status
    case.updated_at = now
    case.events.append(
        {"at": now.isoformat() + "Z", "type": "StatusChanged", "status": body.status, "note": body.note}
    )
    db[case_id] = case
    return case


@app.get("/v1/cases", response_model=List[Case])
def list_cases(limit: int = 50):
    return list(db.values())[: max(1, min(limit, 200))]

