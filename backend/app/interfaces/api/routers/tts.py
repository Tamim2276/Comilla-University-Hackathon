"""POST /api/v1/tts: answer audio for the app (FR-APP-04, SRS 8).

Filled in step D2-R2. Registered in main.py already.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["tts"])
