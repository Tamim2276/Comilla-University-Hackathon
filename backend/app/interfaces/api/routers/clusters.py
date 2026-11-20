"""POST /api/v1/admin/clusters/rebuild and GET /api/v1/admin/clusters (FR-ADM-03, 04, SRS 8).

Filled in step D2-T2; uses the admin token check from admin.py (D2-R1). Registered in main.py already.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
