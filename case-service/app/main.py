from __future__ import annotations

from fastapi import FastAPI

from .api.check_case import router as check_case_router
from .api.v1.applicant import router as applicant_router
from .api.v1.case_for_staff import router as case_for_staff_router
from .api.v1.cases import router as cases_router
from .api.v1.eligibility import router as eligibility_router
from .api.v1.geo import router as geo_router
from .api.v1.lookups import router as lookups_router
from .settings import settings

app = FastAPI(title=settings.service_name, version="0.1.0")

app.include_router(check_case_router)
app.include_router(applicant_router)
app.include_router(lookups_router)
app.include_router(geo_router)
app.include_router(case_for_staff_router)
app.include_router(eligibility_router)
app.include_router(cases_router)


@app.get("/")
def root():
    return {"service": settings.service_name, "ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz():
    return {"ok": True}
