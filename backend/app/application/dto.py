"""Results that use cases return to the interfaces layer."""

from dataclasses import dataclass

from app.application.ports.repositories import ChecklistRecord
from app.domain.entities import Answer, Message, Service


@dataclass(frozen=True)
class AskResult:
    conversation_id: str
    answer: Answer
    service: Service | None
    latency_ms: int


@dataclass(frozen=True)
class HistoryResult:
    phone: str
    messages: tuple[Message, ...]
    checklists: tuple[ChecklistRecord, ...]
