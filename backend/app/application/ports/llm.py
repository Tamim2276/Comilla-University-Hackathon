"""Port: a large language model that returns JSON (FR-AGT-06 to 10, FR-AGT-16)."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class ModelRole(StrEnum):
    MAIN = "main"  # generation and verification
    FAST = "fast"  # grading, rewriting, classification


@runtime_checkable
class LLM(Protocol):
    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        role: ModelRole = ModelRole.MAIN,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Returns an object matching `schema`. Raises LLMUnavailable when it cannot."""
        ...

    def generate_text(self, prompt: str, role: ModelRole = ModelRole.FAST) -> str: ...

    def check(self) -> bool:
        """Cheap key check for /health (no generation)."""
        ...


@runtime_checkable
class ReportsProvider(Protocol):
    """Optional for LLMs: which provider answered the last call made from this thread (FR-AGT-18).

    A chain (Gemini, then Groq, then OpenRouter) answers with whichever provider was available, so the
    agent asks this right after its call to record the real one, not just the LLM_BACKEND setting.
    """

    def last_provider(self) -> str | None: ...
