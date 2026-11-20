"""Use case: answer one question from any channel (FR-APP-02, FR-CALL-02, NFR-PRIV-01).

v1 (D1-A2): history -> engine -> save messages, checklist and an anonymous log.
Added later: SMS after voice answers (D1-A4), answer cache inside the agent (D2-A2).
"""

import logging
import time
from collections.abc import Sequence

from app.application.dto import AskResult
from app.application.ports.engine import AnswerEngine
from app.application.ports.repositories import ChecklistRepo, ConversationRepo, QuestionLogRepo
from app.application.privacy import hash_phone
from app.domain.entities import Answer, Message, QuestionLog, Service
from app.domain.errors import DomainError
from app.domain.policies import HISTORY_MESSAGES_TO_LOAD
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, Role

log = logging.getLogger(__name__)


class AskQuestion:
    def __init__(
        self,
        engine: AnswerEngine,
        conversations: ConversationRepo,
        checklists: ChecklistRepo,
        question_logs: QuestionLogRepo,
        services: Sequence[Service],
        phone_hash_salt: str,
    ) -> None:
        self._engine = engine
        self._conversations = conversations
        self._checklists = checklists
        self._logs = question_logs
        self._services = {s.id: s for s in services}
        self._salt = phone_hash_salt

    def execute(self, phone: str, text: str, channel: Channel, call_sid: str | None = None) -> AskResult:
        number = PhoneNumber.parse(phone)  # raises InvalidPhone
        question = " ".join(text.split())
        if not question:
            raise ValueError("empty question")  # interfaces must not send empty text

        conversation_id = self._conversations.get_or_create(number)
        history = self._conversations.recent_messages(number, HISTORY_MESSAGES_TO_LOAD)
        self._conversations.add_message(
            conversation_id, Message(role=Role.USER, channel=channel, text=question), call_sid
        )

        started = time.perf_counter()
        try:
            answer = self._engine.answer(question, history, channel)
        except DomainError:
            latency_ms = _ms_since(started)
            self._log(number, channel, question, None, latency_ms, failed=True)
            log.warning("engine failed after %d ms (channel=%s)", latency_ms, channel)
            raise
        latency_ms = _ms_since(started)

        reply = answer.speech_text if channel is Channel.VOICE else answer.display_text
        self._conversations.add_message(
            conversation_id,
            Message(
                role=Role.ASSISTANT, channel=channel, text=reply,
                service_id=answer.service_id, status=answer.status,
            ),  # fmt: skip
            call_sid,
        )
        if answer.status is AnswerStatus.ANSWERED and answer.checklist is not None:
            self._checklists.save(
                number, answer.checklist, answer.citations, sms_sent=False, call_sid=call_sid
            )
        self._log(number, channel, question, answer, latency_ms)
        log.info(
            "answered status=%s service=%s latency_ms=%d llm_calls=%d channel=%s",
            answer.status, answer.service_id, latency_ms, answer.llm_calls, channel,
        )  # fmt: skip

        service = self._services.get(answer.service_id) if answer.service_id else None
        return AskResult(conversation_id, answer, service, latency_ms)

    def _log(
        self,
        number: PhoneNumber,
        channel: Channel,
        question: str,
        answer: Answer | None,
        latency_ms: int,
        failed: bool = False,
    ) -> None:
        self._logs.add(
            QuestionLog(
                phone_hash=hash_phone(number, self._salt),
                channel=channel,
                text=question,
                status=AnswerStatus.ERROR if failed or answer is None else answer.status,
                service_id=answer.service_id if answer else None,
                confidence=answer.confidence if answer else 0.0,
                router_source=answer.router_source if answer else None,
                latency_ms=latency_ms,
                llm_calls=answer.llm_calls if answer else 0,
                llm_backend=answer.llm_backend if answer else None,
            )
        )


def _ms_since(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
