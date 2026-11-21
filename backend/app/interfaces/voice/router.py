"""Twilio voice webhooks: /voice/incoming, /voice/start, /voice/respond, /voice/result, /voice/status.

Filled in steps D1-A3, D1-A5, D2-A1, D2-A2 (FR-CALL-01 to 12, SRS 3.1). Registered in main.py already,
so adding routes here never needs a change in main.py.

D1-A3 (echo mode): /voice/respond repeats what the caller said. D1-A5 replaces the echo with AskQuestion.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response

from app.interfaces.api.deps import get_container
from app.interfaces.voice import twiml
from app.interfaces.voice.call_state import SilenceCounter

log = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

TWIML_MEDIA_TYPE = "application/xml"
MAX_SILENCES = 2  # SRS 3.1: REPROMPT once, GOODBYE on the second silence


def get_voice_config(request: Request) -> twiml.VoiceConfig:
    return twiml.VoiceConfig.from_settings(get_container(request).settings)


def get_silence_counter(request: Request) -> SilenceCounter:
    return get_container(request).silence_counter


def citizen_number(from_: str, to: str, direction: str) -> str:
    """The citizen is the caller on inbound calls and the called party on our call-backs."""
    return to if direction.startswith("outbound") else from_


def _twiml(xml: str) -> Response:
    return Response(content=xml, media_type=TWIML_MEDIA_TYPE)


Config = Annotated[twiml.VoiceConfig, Depends(get_voice_config)]
Silences = Annotated[SilenceCounter, Depends(get_silence_counter)]


@router.post("/incoming", response_class=Response)
def incoming(cfg: Config, call_sid: Annotated[str, Form(alias="CallSid")] = "") -> Response:
    """FR-CALL-01: a citizen called the Twilio number."""
    log.info("voice incoming call_sid=%s", call_sid)
    return _twiml(twiml.greet(cfg))


@router.post("/start", response_class=Response)
def start(cfg: Config, call_sid: Annotated[str, Form(alias="CallSid")] = "") -> Response:
    """FR-CALL-07: our outbound call (call-back) was answered; the same flow starts."""
    log.info("voice outbound answered call_sid=%s", call_sid)
    return _twiml(twiml.greet(cfg))


@router.post("/respond", response_class=Response)
def respond(
    cfg: Config,
    silences: Silences,
    call_sid: Annotated[str, Form(alias="CallSid")] = "",
    speech: Annotated[str, Form(alias="SpeechResult")] = "",
    from_: Annotated[str, Form(alias="From")] = "",
    to: Annotated[str, Form(alias="To")] = "",
    direction: Annotated[str, Form(alias="Direction")] = "inbound",
) -> Response:
    """FR-CALL-03, 04: one caller turn. Echo mode for now."""
    text = speech.strip()
    if not text:
        count = silences.silent(call_sid)
        log.info("voice silence call_sid=%s count=%d", call_sid, count)
        if count >= MAX_SILENCES:
            silences.forget(call_sid)
            return _twiml(twiml.goodbye(cfg))
        return _twiml(twiml.reprompt(cfg))

    silences.heard(call_sid)
    phone = citizen_number(from_, to, direction)
    log.info("voice heard call_sid=%s chars=%d phone_known=%s", call_sid, len(text), bool(phone))
    return _twiml(twiml.answer_and_listen(cfg, text))


@router.post("/status", status_code=204, response_class=Response)
def status(
    silences: Silences,
    call_sid: Annotated[str, Form(alias="CallSid")] = "",
    call_status: Annotated[str, Form(alias="CallStatus")] = "",
) -> Response:
    """Twilio status callback. D1-A5 stores the call row here (FR-CALL-11)."""
    log.info("voice status call_sid=%s status=%s", call_sid, call_status)
    if call_status in {"completed", "busy", "failed", "no-answer", "canceled"}:
        silences.forget(call_sid)
    return Response(status_code=204)
