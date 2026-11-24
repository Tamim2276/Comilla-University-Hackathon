"""GEMINI_BUDGET_S: one Gemini request never takes longer than its budget, so the fallback LLM can answer.

A fake clock makes "a call that takes 8 s" instant: each scripted call moves the clock forward.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from app.application.ports.llm import ModelRole
from app.config import Settings
from app.container import Container
from app.domain.errors import LLMUnavailable
from app.infrastructure.llm.fallback_llm import FallbackLLM
from app.infrastructure.llm.gemini_llm import GeminiLLM
from tests.integration.test_llm_adapters import SCHEMA, server_error


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def slow(seconds: float, outcome: Any) -> tuple[float, Any]:
    """A scripted call that takes `seconds` and then returns or raises `outcome`."""
    return (seconds, outcome)


def gemini(
    script: list[tuple[float, Any]], budget: float, fallback: str = "", timeout: float = 20.0
) -> tuple[GeminiLLM, list[tuple[str, dict[str, Any]]], Clock]:
    clock = Clock()
    calls: list[tuple[str, dict[str, Any]]] = []

    class Models:
        def generate_content(self, *, model: str, contents: str, config: dict[str, Any]) -> Any:
            calls.append((model, config))
            seconds, outcome = script.pop(0)
            clock.now += seconds
            if isinstance(outcome, Exception):
                raise outcome
            return type("Response", (), {"text": outcome})()

    class Client:
        def __init__(self, key: str) -> None:
            self.models = Models()

    def sleep(seconds: float) -> None:
        clock.now += seconds

    llm = GeminiLLM(
        ["k1"], "main-model", "fast-model", timeout_s=timeout, client_factory=Client,
        sleep=sleep, clock=clock, fallback_model=fallback, budget_s=budget,
    )  # fmt: skip
    return llm, calls, clock


def timeout_ms(config: dict[str, Any]) -> int | None:
    return config.get("http_options", {}).get("timeout")


def test_without_a_budget_nothing_changes() -> None:
    llm, calls, _ = gemini([slow(30, server_error()), slow(30, '{"x": "ok"}')], budget=0)
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    assert len(calls) == 2
    assert all("http_options" not in config for _, config in calls)  # request config as before


def test_a_fast_answer_is_not_affected() -> None:
    llm, calls, _ = gemini([slow(2, '{"x": "ok"}')], budget=10)
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    assert timeout_ms(calls[0][1]) == 10_000  # the first attempt may use the whole budget


def test_attempt_timeout_never_exceeds_the_normal_timeout() -> None:
    llm, calls, _ = gemini([slow(1, '{"x": "ok"}')], budget=60, timeout=20)
    llm.generate_json("p", SCHEMA)
    assert timeout_ms(calls[0][1]) == 20_000


def test_retry_gets_only_the_time_that_is_left() -> None:
    llm, calls, _ = gemini([slow(5, server_error()), slow(3, '{"x": "ok"}')], budget=20)
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    assert timeout_ms(calls[1][1]) == 14_000  # 20 s - 5 s for the failed call - 1 s wait


def test_no_retry_when_too_little_time_is_left() -> None:
    llm, calls, clock = gemini([slow(8, server_error())], budget=10)
    with pytest.raises(LLMUnavailable, match="time budget"):
        llm.generate_json("p", SCHEMA)
    assert len(calls) == 1
    assert clock.now - 1000.0 == 8  # gave up at once, no wait for a retry


def test_fallback_model_is_skipped_when_the_budget_is_used_up() -> None:
    llm, calls, _ = gemini(
        [slow(4, server_error()), slow(4, server_error())], budget=18, fallback="backup-model"
    )
    with pytest.raises(LLMUnavailable, match="time budget"):
        llm.generate_json("p", SCHEMA, role=ModelRole.FAST)
    assert [model for model, _ in calls] == ["fast-model", "fast-model"]  # 18-4-1-4 = 9 s: too little


def test_never_sends_a_deadline_under_gemini_minimum_of_10_s() -> None:
    # The bug seen in a real call: 7 s left -> "Manually set deadline 7s is too short" (HTTP 400).
    llm, calls, _ = gemini([slow(2.4, server_error())], budget=10)
    with pytest.raises(LLMUnavailable, match="time budget"):
        llm.generate_json("p", SCHEMA)
    assert len(calls) == 1  # 10 - 2.4 - 1 = 6.6 s left: no retry with a too-short deadline


def test_every_deadline_sent_is_at_least_10_s() -> None:
    llm, calls, _ = gemini(
        [slow(1, server_error()), slow(1, server_error()), slow(1, server_error()), slow(1, server_error())],
        budget=25,
        fallback="backup-model",
    )
    with pytest.raises(LLMUnavailable):
        llm.generate_json("p", SCHEMA)
    assert calls and all(timeout_ms(config) >= 10_000 for _, config in calls)


def test_fallback_model_still_runs_when_time_is_left() -> None:
    llm, calls, _ = gemini(
        [slow(1, server_error()), slow(1, server_error()), slow(1, '{"x": "ok"}')],
        budget=20,
        fallback="backup-model",
    )
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    assert [model for model, _ in calls] == ["main-model", "main-model", "backup-model"]
    assert timeout_ms(calls[2][1]) == 17_000  # 20 - 1 - 1 (wait) - 1


def test_a_slow_gemini_hands_over_to_the_fallback_llm_within_the_budget() -> None:
    llm, _, clock = gemini([slow(9, server_error())], budget=10)

    class Groq:
        def generate_json(self, prompt: str, schema: Any, role: Any = None, temperature: float = 0.2) -> Any:
            return {"x": "groq"}

        def generate_text(self, prompt: str, role: Any = None) -> str:
            return "groq"

        def check(self) -> bool:
            return True

    assert FallbackLLM(llm, Groq()).generate_json("p", SCHEMA) == {"x": "groq"}
    assert clock.now - 1000.0 <= 10  # Gemini used at most its budget before Groq answered


def test_budget_setting_reaches_the_adapter() -> None:
    c = Container(Settings(_env_file=None, database_url="sqlite://", gemini_budget_s=8))
    assert c.gemini._budget_s == 8


def test_negative_budget_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, gemini_budget_s=-1)
