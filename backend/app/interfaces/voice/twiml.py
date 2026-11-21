"""TwiML builders for the phone call flow (SRS 3.1, FR-CALL-01, 03, 04).

Pure functions: text in, TwiML (XML string) out. No state, no I/O.
Every reply that listens wraps <Say> inside <Gather>, so the caller can interrupt (barge-in).
"""

from dataclasses import dataclass

from twilio.twiml.voice_response import Gather, VoiceResponse

from app.config import Settings
from app.domain import messages_bn

RESPOND_PATH = "/voice/respond"


@dataclass(frozen=True)
class VoiceConfig:
    """The speech settings the builders need (taken from config.py)."""

    stt_language: str
    tts_voice: str
    tts_language: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "VoiceConfig":
        return cls(settings.stt_language, settings.tts_voice, settings.tts_language)


def greet(cfg: VoiceConfig) -> str:
    """FR-CALL-01: greeting with the AI disclosure, then listen."""
    return _say_and_listen(cfg, messages_bn.GREETING)


def answer_and_listen(cfg: VoiceConfig, text: str) -> str:
    """FR-CALL-03: speak the answer, then the CONTINUE prompt, inside the next Gather."""
    return _say_and_listen(cfg, text, messages_bn.CONTINUE)


def reprompt(cfg: VoiceConfig) -> str:
    """FR-CALL-04: first silence, ask again and listen."""
    return _say_and_listen(cfg, messages_bn.REPROMPT)


def goodbye(cfg: VoiceConfig) -> str:
    """Say GOODBYE and hang up (second silence, goodbye intent, turn limit)."""
    response = VoiceResponse()
    response.say(messages_bn.GOODBYE, voice=cfg.tts_voice, language=cfg.tts_language)
    response.hangup()
    return str(response)


def _say_and_listen(cfg: VoiceConfig, *texts: str) -> str:
    gather = Gather(
        input="speech",
        language=cfg.stt_language,
        speech_timeout="auto",
        action=RESPOND_PATH,
        method="POST",
        action_on_empty_result=True,  # silence also reaches /voice/respond, which counts it
    )
    for text in texts:
        gather.say(text, voice=cfg.tts_voice, language=cfg.tts_language)
    response = VoiceResponse()
    response.append(gather)
    return str(response)
