"""Legacy public person delete routes — removed (CR-05).

Use instead:
  DELETE /v1/citizen/person       — citizen PDPA (require_citizen)
  DELETE /v1/admin/persons/by-cid — admin ops
  python -m app.admin_cli purge-all — dev reset only
"""

from fastapi import APIRouter

router = APIRouter(prefix="/v1/persons", tags=["persons"])
