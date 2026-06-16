from __future__ import annotations

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .api.check_case import router as check_case_router
from .api.v1.admin import router as admin_router
from .api.v1.applicant import router as applicant_router
from .api.v1.person import router as person_router
from .api.v1.case_for_staff import router as case_for_staff_router
from .api.v1.cases import router as cases_router
from .api.v1.eligibility import router as eligibility_router
from .api.v1.geo import router as geo_router
from .api.v1.intake import router as intake_router
from .api.v1.satisfaction import router as satisfaction_router
from .api.v1.lookups import router as lookups_router
from .settings import settings

_REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status_code"],
)
_REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)
_IN_FLIGHT = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["service"],
)

app = FastAPI(title=settings.service_name, version="0.1.0")


def _route_path_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None:
        path = getattr(route, "path", None)
        if path:
            return str(path)
    return request.url.path


@app.middleware("http")
async def prometheus_http_metrics(request: Request, call_next):
    service_name = settings.service_name
    method = request.method
    path = _route_path_template(request)
    _IN_FLIGHT.labels(service=service_name).inc()
    try:
        with _REQUEST_LATENCY.labels(service=service_name, method=method, path=path).time():
            response = await call_next(request)
    finally:
        _IN_FLIGHT.labels(service=service_name).dec()

    _REQUEST_COUNT.labels(
        service=service_name,
        method=method,
        path=path,
        status_code=str(response.status_code),
    ).inc()
    return response

app.include_router(check_case_router)
app.include_router(applicant_router)
app.include_router(person_router)
app.include_router(lookups_router)
app.include_router(geo_router)
app.include_router(case_for_staff_router)
app.include_router(eligibility_router)
app.include_router(cases_router)
app.include_router(intake_router)
app.include_router(satisfaction_router)
app.include_router(admin_router)


@app.get("/")
def root():
    return {"service": settings.service_name, "ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz():
    return {"ok": True}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
