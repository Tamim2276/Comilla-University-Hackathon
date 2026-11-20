"""GET /api/v1/admin/stats and /api/v1/admin/questions (FR-ADM-01, 02, 05, SRS 8).

Filled in step D2-R1, including the X-Admin-Token check that the clusters router reuses.
Registered in main.py already.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
