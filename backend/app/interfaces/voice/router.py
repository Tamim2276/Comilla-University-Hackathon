"""Twilio voice webhooks: /voice/incoming, /voice/start, /voice/respond, /voice/result, /voice/status.

Filled in steps D1-A3, D1-A5, D2-A1, D2-A2 (FR-CALL-01 to 12, SRS 3.1). Registered in main.py already,
so adding routes here never needs a change in main.py.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/voice", tags=["voice"])
