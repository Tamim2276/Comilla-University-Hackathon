"""Core business objects (SRS 6.1). Frozen dataclasses: once created, they cannot change."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.value_objects import AnswerStatus, Channel, Role, RouterSource


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Service:
    """One government service, or the `other` label (from data/services.yaml)."""

    id: str
    name_bn: str
    name_en: str
    office_bn: str
    sms_name: str


@dataclass(frozen=True)
class Citation:
    """Where a fact came from: an official document passage."""

    title: str
    source_url: str
    snippet: str
    chunk_id: str


@dataclass(frozen=True)
class Checklist:
    """The short summary sent by SMS and shown as the checklist card."""

    service_id: str
    who: str
    papers: tuple[str, ...]
    fee: str
    where: str
    decision: str


@dataclass(frozen=True)
class Answer:
    """The agent's full reply to one question, used by every channel."""

    status: AnswerStatus
    speech_text: str
    display_text: str
    service_id: str | None = None
    confidence: float = 0.0
    router_source: RouterSource | None = None
    checklist: Checklist | None = None
    citations: tuple[Citation, ...] = ()
    follow_up_question: str | None = None
    timings: Mapping[str, float] = field(default_factory=dict)
    llm_calls: int = 0
    llm_backend: str | None = None  # FR-AGT-18

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0 and 1, got {self.confidence}")
        if self.status is AnswerStatus.ANSWERED:
            # FR-AGT-12: every answered response has a service, a checklist and sources.
            if not self.service_id or self.checklist is None or not self.citations:
                raise ValueError("an answered Answer needs service_id, checklist and at least one citation")
        if self.status is AnswerStatus.FOLLOW_UP and not self.follow_up_question:
            raise ValueError("a follow_up Answer needs follow_up_question")


@dataclass(frozen=True)
class Message:
    """One line in a conversation (shared between phone and app)."""

    role: Role
    channel: Channel
    text: str
    service_id: str | None = None
    status: AnswerStatus | None = None
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class QuestionLog:
    """One logged question for the admin dashboard. Holds a salted hash, never the raw phone."""

    phone_hash: str
    channel: Channel
    text: str
    status: AnswerStatus
    service_id: str | None = None
    confidence: float = 0.0
    router_source: RouterSource | None = None
    latency_ms: int = 0
    llm_calls: int = 0
    llm_backend: str | None = None  # FR-AGT-18: which LLM produced the answer
    cluster_id: int | None = None
    is_demo: bool = False
    created_at: datetime = field(default_factory=_now)
