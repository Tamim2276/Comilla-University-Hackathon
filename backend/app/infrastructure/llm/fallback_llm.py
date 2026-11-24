"""LLM adapter that tries a second LLM when the first one is unavailable (FR-AGT-16).

Used for Gemini first, Groq second: when Gemini raises LLMUnavailable (503 "high demand", every key
rate-limited, timeouts), the same request goes to the backup. Any other error is not caught, so real
bugs are not hidden. If the backup fails too, its LLMUnavailable reaches the caller as before.
"""

import logging
import threading
from collections.abc import Mapping
from typing import Any

from app.application.ports.llm import LLM, ModelRole, ReportsProvider
from app.domain.errors import LLMUnavailable

log = logging.getLogger(__name__)


def provider_of(llm: LLM) -> str | None:
    """The provider behind `llm` for its last call, or None when it cannot tell."""
    return llm.last_provider() if isinstance(llm, ReportsProvider) else None


class FallbackLLM:
    def __init__(self, primary: LLM, backup: LLM) -> None:
        self._primary = primary
        self._backup = backup
        self._last = threading.local()  # calls run on several threads (voice jobs, web requests)

    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        role: ModelRole = ModelRole.MAIN,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        self._last.name = None  # nothing stale if both sides fail
        try:
            result = self._primary.generate_json(prompt, schema, role, temperature)
            self._last.name = provider_of(self._primary)
        except LLMUnavailable as exc:
            log.warning("primary LLM unavailable (%s); using the fallback LLM", exc)
            result = self._backup.generate_json(prompt, schema, role, temperature)
            self._last.name = provider_of(self._backup)
        return result

    def generate_text(self, prompt: str, role: ModelRole = ModelRole.FAST) -> str:
        self._last.name = None  # nothing stale if both sides fail
        try:
            result = self._primary.generate_text(prompt, role)
            self._last.name = provider_of(self._primary)
        except LLMUnavailable as exc:
            log.warning("primary LLM unavailable (%s); using the fallback LLM", exc)
            result = self._backup.generate_text(prompt, role)
            self._last.name = provider_of(self._backup)
        return result

    def last_provider(self) -> str | None:
        """Which provider answered this thread's last call ("gemini", "groq", "openrouter")."""
        return getattr(self._last, "name", None)

    def check(self) -> bool:
        """Usable when either side works."""
        return self._primary.check() or self._backup.check()
