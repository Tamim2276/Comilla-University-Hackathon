"""POST /api/v1/callback: "Call me" (FR-CALL-07, FR-APP-06, SRS 8).

Filled in step D2-A1. Registered in main.py already.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["callback"])
