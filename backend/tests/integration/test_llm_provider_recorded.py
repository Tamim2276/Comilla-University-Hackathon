"""The answer records the provider that really wrote it (FR-AGT-18), and the LLM setup is described once.

With a chain (Gemini, then Groq, then OpenRouter) the answer may come from any of them; before this,
every answer said "gemini" because it copied the LLM_BACKEND setting.
"""

import threading
from collections.abc import Mapping
from typing import Any

import pytest

from app.application.agent import steps
from app.application.agent.state import AgentState
from app.application.ports.llm import ModelRole, ReportsProvider
from app.config import Settings
from app.domain.errors import LLMUnavailable
from app.domain.value_objects import Channel, RouterSource
from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
from app.infrastructure.llm.fallback_llm import FallbackLLM
from app.infrastructure.llm.gemini_llm import GeminiLLM
from app.infrastructure.llm.ollama_llm import OllamaLLM
from app.infrastructure.llm.openai_compat_llm import OpenAICompatLLM
from app.infrastructure.llm.routed_llm import RoutedLLM
from tests.fakes import FakeLLM
from tests.unit.test_agent import ALL_SUPPORTED, GOOD_DRAFT, PASSAGES, StepLLM, deps


class Named(FakeLLM):
    """A FakeLLM that reports a provider name, like the real adapters."""

    def __init__(self, name: str, fails: bool = False, inner: FakeLLM | None = None) -> None:
        super().__init__(responses=[{"answer": name}] * 50, fail=fails)
        self.name, self.inner = name, inner

    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        role: ModelRole = ModelRole.MAIN,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        if self.fail:
            raise LLMUnavailable(f"{self.name} down")
        if self.inner is not None:
            return self.inner.generate_json(prompt, schema, role, temperature)
        return {"answer": self.name}

    def last_provider(self) -> str | None:
        return self.name


# ------------------------------------------------------------------ every adapter can say who it is


def test_real_adapters_report_their_name() -> None:
    assert GeminiLLM(["k"], "m", "m").last_provider() == "gemini"
    assert OllamaLLM("http://localhost:1", "m").last_provider() == "ollama"
    assert OpenAICompatLLM("k", "m").last_provider() == "groq"
    assert OpenAICompatLLM("k", "m", name="openrouter").last_provider() == "openrouter"
    for llm in (GeminiLLM(["k"], "m", "m"), OpenAICompatLLM("k", "m"), FallbackLLM(Named("a"), Named("b"))):
        assert isinstance(llm, ReportsProvider)


# ------------------------------------------------------------------ the chain remembers who answered


def test_chain_reports_the_primary_when_it_answers() -> None:
    llm = FallbackLLM(Named("gemini"), Named("groq"))
    llm.generate_json("q", {})
    assert llm.last_provider() == "gemini"


def test_chain_reports_the_backup_when_the_primary_is_down() -> None:
    first_two = FallbackLLM(Named("gemini", fails=True), Named("groq", fails=True))
    llm = FallbackLLM(first_two, Named("openrouter"))
    llm.generate_text("q")
    assert llm.last_provider() == "openrouter"


def test_no_stale_name_when_everything_fails() -> None:
    llm = FallbackLLM(Named("gemini"), Named("groq"))
    llm.generate_json("q", {})
    llm._primary.fail = llm._backup.fail = True  # type: ignore[attr-defined]
    with pytest.raises(LLMUnavailable):
        llm.generate_json("q", {})
    assert llm.last_provider() is None


def test_each_thread_sees_its_own_provider() -> None:
    primary = Named("gemini")
    llm = FallbackLLM(primary, Named("groq"))
    seen: dict[str, str | None] = {}

    def other_thread() -> None:
        llm.generate_json("q", {})
        seen["other"] = llm.last_provider()

    llm.generate_json("q", {})  # this thread: Gemini answers
    primary.fail = True  # from now on Gemini is down
    other = threading.Thread(target=other_thread)
    other.start()
    other.join()
    assert seen["other"] == "groq"  # the other thread found Gemini down
    assert llm.last_provider() == "gemini"  # this thread's last call is not overwritten


def test_hybrid_reports_ollama_or_the_cloud_provider() -> None:
    llm = RoutedLLM(main=FallbackLLM(Named("gemini", fails=True), Named("groq")), local=Named("ollama"))
    llm.generate_json("q", {}, role=ModelRole.FAST)
    assert llm.last_provider() == "ollama"
    llm.generate_json("q", {}, role=ModelRole.MAIN)
    assert llm.last_provider() == "groq"


# ------------------------------------------------------------------ the agent records it


def test_generate_step_records_the_provider() -> None:
    llm = Named("groq", inner=FakeLLM([GOOD_DRAFT]))
    state: AgentState = {"question": "বয়স?", "service_id": "old_age_allowance", "passages": PASSAGES,
                         "history": [], "channel": Channel.APP}  # fmt: skip
    assert steps.generate(state, deps(llm=llm))["llm_provider"] == "groq"


def test_finalize_uses_the_recorded_provider_and_the_setting_only_as_backup() -> None:
    state: AgentState = {"draft": GOOD_DRAFT, "service_id": "old_age_allowance", "confidence": 0.95,
                         "router_source": RouterSource.TFIDF, "passages": PASSAGES}  # fmt: skip
    recorded = steps.finalize({**state, "llm_provider": "openrouter"}, deps())["answer"]
    assert recorded.llm_backend == "openrouter"
    assert steps.finalize(state, deps())["answer"].llm_backend == "gemini"  # LLM without a name: the setting


def test_a_whole_answer_written_by_groq_says_groq() -> None:
    inner = StepLLM(generate=[GOOD_DRAFT], verify=[ALL_SUPPORTED])
    chain = FallbackLLM(Named("gemini", fails=True), Named("groq", inner=inner))
    answer = LangGraphAnswerEngine(deps(llm=chain)).answer("বয়স্ক ভাতা?", [], Channel.VOICE)
    assert answer.llm_backend == "groq"


# ------------------------------------------------------------------ one description of the setup


def test_summary_lists_configured_providers_in_order() -> None:
    s = Settings(
        _env_file=None, llm_order="groq,gemini,openrouter", groq_api_keys="g", gemini_api_keys="k",
        gemini_model_main="main-m", gemini_model_fast="fast-m", gemini_model_fallback="",
    )  # fmt: skip
    assert s.llm_summary == "groq (openai/gpt-oss-120b) -> gemini (main-m, fast fast-m)"  # no OpenRouter key


def test_summary_for_ollama_hybrid_and_nothing() -> None:
    assert Settings(_env_file=None, llm_backend="ollama").llm_summary == "ollama (qwen2.5:7b)"
    hybrid = Settings(_env_file=None, llm_backend="hybrid", openrouter_api_keys="o").llm_summary
    assert hybrid == (
        "hybrid: fast jobs on ollama (qwen2.5:7b), main jobs on openrouter (google/gemma-4-31b-it:free)"
    )
    assert Settings(_env_file=None).llm_summary == "none configured"


def test_container_logs_the_chain_once_built(caplog: pytest.LogCaptureFixture) -> None:
    from app.container import Container

    caplog.set_level("INFO", logger="app.container")
    Container(Settings(_env_file=None, database_url="sqlite://", groq_api_keys="g")).llm  # noqa: B018
    assert "cloud LLMs in order: groq (openai/gpt-oss-120b)" in caplog.text
