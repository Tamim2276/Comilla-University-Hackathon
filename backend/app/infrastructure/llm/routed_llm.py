"""LLM adapter for LLM_BACKEND=hybrid (FR-AGT-18).

FAST jobs (grading, rewriting, classification) go to the local model, so they cost no quota.
MAIN jobs (answer, verification) go to Gemini; if Gemini raises LLMUnavailable, the local model
answers instead, so a quota problem never ends the call.
"""

import logging
import threading
from collections.abc import Mapping
from typing import Any

from app.application.ports.llm import LLM, ModelRole
from app.domain.errors import LLMUnavailable
from app.infrastructure.llm.fallback_llm import provider_of

log = logging.getLogger(__name__)


class RoutedLLM:
    def __init__(self, main: LLM, local: LLM) -> None:
        self._main = main
        self._local = local
        self._last = threading.local()

    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        role: ModelRole = ModelRole.MAIN,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        self._last.name = None
        used = self._local
        if role is ModelRole.FAST:
            result = self._local.generate_json(prompt, schema, role, temperature)
        else:
            try:
                result = self._main.generate_json(prompt, schema, role, temperature)
                used = self._main
            except LLMUnavailable as exc:
                log.warning("main LLM unavailable (%s); using the local model", exc)
                result = self._local.generate_json(prompt, schema, role, temperature)
        self._last.name = provider_of(used)
        return result

    def generate_text(self, prompt: str, role: ModelRole = ModelRole.FAST) -> str:
        self._last.name = None
        used = self._local
        if role is ModelRole.FAST:
            result = self._local.generate_text(prompt, role)
        else:
            try:
                result = self._main.generate_text(prompt, role)
                used = self._main
            except LLMUnavailable as exc:
                log.warning("main LLM unavailable (%s); using the local model", exc)
                result = self._local.generate_text(prompt, role)
        self._last.name = provider_of(used)
        return result

    def last_provider(self) -> str | None:
        return getattr(self._last, "name", None)

    def check(self) -> bool:
        """Usable when at least one side works (the local model can cover for Gemini)."""
        return self._local.check() or self._main.check()
