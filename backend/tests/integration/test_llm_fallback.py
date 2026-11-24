"""Groq (OpenAI-compatible) adapter and the Gemini -> Groq fallback, without network (FR-AGT-16)."""

import json
from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from app.application.ports.llm import LLM, ModelRole
from app.config import Settings
from app.container import Container
from app.domain.errors import LLMUnavailable
from app.infrastructure.llm.fallback_llm import FallbackLLM
from app.infrastructure.llm.gemini_llm import GeminiLLM
from app.infrastructure.llm.openai_compat_llm import OpenAICompatLLM
from app.infrastructure.llm.routed_llm import RoutedLLM

SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}


def groq_with(handler) -> tuple[OpenAICompatLLM, list[httpx.Request]]:  # type: ignore[no-untyped-def]
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.Client(base_url="https://groq.test/v1", transport=httpx.MockTransport(record))
    return OpenAICompatLLM("gsk_test", "openai/gpt-oss-120b", client=client), seen


def reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


# ------------------------------------------------------------------ the Groq adapter


def test_fits_the_llm_port() -> None:
    llm, _ = groq_with(lambda r: reply("{}"))
    assert isinstance(llm, LLM)


def test_json_reply_with_schema_and_json_mode() -> None:
    llm, seen = groq_with(lambda r: reply('{"answer": "২০০ টাকা"}'))
    assert llm.generate_json("ফি কত?", SCHEMA) == {"answer": "২০০ টাকা"}
    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/v1/chat/completions"
    assert seen[0].headers["Authorization"] == "Bearer gsk_test"
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["response_format"] == {"type": "json_object"}
    assert '"required"' in body["messages"][0]["content"]  # the schema is sent to the model
    assert body["messages"][1] == {"role": "user", "content": "ফি কত?"}


def test_json_in_a_code_fence_is_accepted() -> None:
    llm, _ = groq_with(lambda r: reply('```json\n{"answer": "x"}\n```'))
    assert llm.generate_json("q", SCHEMA) == {"answer": "x"}


def test_text_reply_without_json_mode() -> None:
    llm, seen = groq_with(lambda r: reply("  নতুন প্রশ্ন  "))
    assert llm.generate_text("rewrite") == "নতুন প্রশ্ন"
    assert "response_format" not in json.loads(seen[0].content)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": {"message": "rate limit"}}),
        httpx.Response(503, text="overloaded"),
        httpx.Response(401, json={"error": {"message": "invalid key"}}),
        reply("not json"),
        reply(""),
        httpx.Response(200, json={"choices": []}),
    ],
)
def test_failures_become_llm_unavailable(response: httpx.Response) -> None:
    llm, _ = groq_with(lambda r: response)
    with pytest.raises(LLMUnavailable):
        llm.generate_json("q", SCHEMA)


def test_network_error_becomes_llm_unavailable() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    llm, _ = groq_with(boom)
    with pytest.raises(LLMUnavailable):
        llm.generate_text("q")


def test_without_a_key_it_is_off_and_sends_nothing() -> None:
    llm = OpenAICompatLLM("", "openai/gpt-oss-120b", client=httpx.Client(transport=httpx.MockTransport(
        lambda r: pytest.fail("no request may be sent without a key"))))
    assert not llm.configured
    assert llm.check() is False
    with pytest.raises(LLMUnavailable):
        llm.generate_text("q")


def test_check_lists_models_and_spends_no_quota() -> None:
    llm, seen = groq_with(lambda r: httpx.Response(200, json={"data": []}))
    assert llm.check() is True
    assert seen[0].method == "GET" and seen[0].url.path == "/v1/models"


# ------------------------------------------------------------------ the fallback


class Scripted:
    """An LLM that fails or answers as told and counts its calls."""

    configured = True  # stands in for an adapter whose key is set

    def __init__(self, fails: bool, answer: str = "ok", healthy: bool = True) -> None:
        self.fails, self.answer, self.healthy, self.calls = fails, answer, healthy, 0

    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        role: ModelRole = ModelRole.MAIN,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        self.calls += 1
        if self.fails:
            raise LLMUnavailable("503 high demand")
        return {"answer": self.answer}

    def generate_text(self, prompt: str, role: ModelRole = ModelRole.FAST) -> str:
        self.calls += 1
        if self.fails:
            raise LLMUnavailable("503 high demand")
        return self.answer

    def check(self) -> bool:
        return self.healthy


def test_primary_answers_and_backup_is_not_used() -> None:
    gemini, groq = Scripted(fails=False, answer="gemini"), Scripted(fails=False, answer="groq")
    llm = FallbackLLM(gemini, groq)
    assert llm.generate_json("q", SCHEMA) == {"answer": "gemini"}
    assert llm.generate_text("q") == "gemini"
    assert groq.calls == 0


def test_backup_answers_when_primary_is_unavailable() -> None:
    gemini, groq = Scripted(fails=True), Scripted(fails=False, answer="groq")
    llm = FallbackLLM(gemini, groq)
    assert llm.generate_json("q", SCHEMA, ModelRole.MAIN) == {"answer": "groq"}
    assert llm.generate_text("q", ModelRole.FAST) == "groq"
    assert (gemini.calls, groq.calls) == (2, 2)


def test_both_unavailable_raises_like_before() -> None:
    llm = FallbackLLM(Scripted(fails=True), Scripted(fails=True))
    with pytest.raises(LLMUnavailable):
        llm.generate_json("q", SCHEMA)


def test_real_bugs_are_not_hidden() -> None:
    class Broken(Scripted):
        def generate_text(self, prompt: str, role: ModelRole = ModelRole.FAST) -> str:
            raise KeyError("bug")

    backup = Scripted(fails=False)
    with pytest.raises(KeyError):
        FallbackLLM(Broken(fails=False), backup).generate_text("q")
    assert backup.calls == 0


def test_check_is_ok_when_either_side_works() -> None:
    assert FallbackLLM(Scripted(False, healthy=False), Scripted(False, healthy=True)).check()
    assert not FallbackLLM(Scripted(False, healthy=False), Scripted(False, healthy=False)).check()


# ------------------------------------------------------------------ wiring in the container


GEMINI_SET = {"gemini_api_keys": "k", "gemini_model_main": "m", "gemini_model_fast": "m"}


def container(**overrides: Any) -> Container:
    return Container(Settings(_env_file=None, database_url="sqlite://", **overrides))


def test_without_groq_key_the_llm_is_plain_gemini() -> None:
    assert isinstance(container(llm_backend="gemini").llm, GeminiLLM)


def test_with_groq_key_gemini_falls_back_to_groq() -> None:
    c = container(llm_backend="gemini", groq_api_keys="gsk_test", **GEMINI_SET)
    assert isinstance(c.llm, FallbackLLM)
    assert c.groq.configured


def test_hybrid_keeps_the_local_model_and_adds_groq_behind_gemini() -> None:
    c = container(llm_backend="hybrid", groq_api_keys="gsk_test", **GEMINI_SET)
    assert isinstance(c.llm, RoutedLLM)
    assert isinstance(c.cloud_llm, FallbackLLM)


def test_health_is_not_not_configured_when_only_groq_has_a_key() -> None:
    c = container(llm_backend="gemini", groq_api_keys="gsk_test")
    c.__dict__["groq"] = OpenAICompatLLM(
        "gsk_test", "m", client=httpx.Client(base_url="https://groq.test/v1",
                                             transport=httpx.MockTransport(lambda r: httpx.Response(200))))
    assert c.check_llm() == "ok"


# ------------------------------------------------------------------ second fallback: OpenRouter


def chain_with(gemini: Scripted, groq: Scripted | None, openrouter: Scripted | None) -> LLM:
    """The container's fallback chain built from stand-ins (None: that fallback has no key)."""
    c = container(
        llm_backend="gemini",
        groq_api_keys="gsk_test" if groq else "",
        openrouter_api_keys="sk-or-test" if openrouter else "",
    )
    c.__dict__["gemini"] = gemini
    if groq:
        c.__dict__["groq"] = groq
    if openrouter:
        c.__dict__["openrouter"] = openrouter
    return c.cloud_llm


def test_order_is_gemini_then_groq_then_openrouter() -> None:
    llm = chain_with(Scripted(True), Scripted(True, "groq"), Scripted(False, "openrouter"))
    assert llm.generate_text("q") == "openrouter"
    llm = chain_with(Scripted(True), Scripted(False, "groq"), Scripted(False, "openrouter"))
    assert llm.generate_text("q") == "groq"  # OpenRouter is not asked while Groq answers
    llm = chain_with(Scripted(False, "gemini"), Scripted(False, "groq"), Scripted(False, "openrouter"))
    assert llm.generate_text("q") == "gemini"


def test_openrouter_alone_without_groq() -> None:
    llm = chain_with(Scripted(True), None, Scripted(False, "openrouter"))
    assert llm.generate_json("q", SCHEMA) == {"answer": "openrouter"}


def test_all_unavailable_raises_like_before() -> None:
    llm = chain_with(Scripted(True), Scripted(True), Scripted(True))
    with pytest.raises(LLMUnavailable):
        llm.generate_text("q")


def test_without_any_fallback_key_it_stays_plain_gemini() -> None:
    c = container(llm_backend="gemini")
    assert isinstance(c.cloud_llm, GeminiLLM)
    assert not c.openrouter.configured


def test_openrouter_requests_go_to_openrouter_with_its_model() -> None:
    c = container(llm_backend="gemini", openrouter_api_keys="sk-or-test")
    assert c.openrouter.configured
    assert c.openrouter._http.base_url == httpx.URL("https://openrouter.ai/api/v1/")
    assert c.openrouter._model == "google/gemma-4-31b-it:free"
    assert c.openrouter._name == "openrouter"


# ------------------------------------------------------------------ LLM_ORDER


def ordered(order: str, **fails: bool) -> LLM:
    """Chain from LLM_ORDER with stand-ins; each stand-in answers with its own name unless it fails."""
    c = container(llm_backend="gemini", llm_order=order, groq_api_keys="g", openrouter_api_keys="o")
    for name in ("gemini", "groq", "openrouter"):
        c.__dict__[name] = Scripted(fails.get(name, False), answer=name)
    return c.cloud_llm


def test_default_order_puts_gemini_first() -> None:
    assert ordered("gemini,groq,openrouter").generate_text("q") == "gemini"


def test_groq_first_answers_before_gemini() -> None:
    assert ordered("groq,gemini,openrouter").generate_text("q") == "groq"


def test_groq_first_falls_back_to_gemini_then_openrouter() -> None:
    assert ordered("groq,gemini,openrouter", groq=True).generate_text("q") == "gemini"
    assert ordered("groq,gemini,openrouter", groq=True, gemini=True).generate_text("q") == "openrouter"


def test_names_left_out_of_the_order_are_not_used() -> None:
    llm = ordered("groq,gemini", groq=True, gemini=True)
    with pytest.raises(LLMUnavailable):
        llm.generate_text("q")  # openrouter is configured but not in LLM_ORDER


def test_order_ignores_case_spaces_duplicates_and_unknown_names() -> None:
    assert ordered(" Groq , groq, chatgpt, GEMINI ").generate_text("q") == "groq"


def test_unknown_names_are_reported_at_startup() -> None:
    warnings = Settings(_env_file=None, llm_order="groq,chatgpt").config_warnings()
    assert any("LLM_ORDER" in w and "chatgpt" in w for w in warnings)


def test_a_provider_without_key_is_skipped_even_when_first() -> None:
    c = container(llm_backend="gemini", llm_order="groq,gemini")  # no Groq key
    assert isinstance(c.cloud_llm, GeminiLLM)


def test_gemini_without_key_is_left_out_so_groq_answers_directly() -> None:
    c = container(llm_backend="gemini", groq_api_keys="gsk_test")  # no Gemini key
    assert isinstance(c.cloud_llm, OpenAICompatLLM)


# ------------------------------------------------------------------ several keys per provider


def keyed(responses: dict[str, list[httpx.Response]]) -> tuple[OpenAICompatLLM, list[str]]:
    """An adapter with keys k1, k2, k3; each key answers with its own scripted responses."""
    used: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        key = request.headers["Authorization"].removeprefix("Bearer ")
        used.append(key)
        return responses[key].pop(0)

    client = httpx.Client(base_url="https://groq.test/v1", transport=httpx.MockTransport(handle))
    return OpenAICompatLLM(["k1", "k2", "k3"], "m", client=client), used


RATE_LIMITED = httpx.Response(429, json={"error": {"message": "rate limit"}})


def test_rate_limited_key_hands_over_to_the_next_key() -> None:
    llm, used = keyed({"k1": [RATE_LIMITED], "k2": [reply('{"answer": "ok"}')]})
    assert llm.generate_json("q", SCHEMA) == {"answer": "ok"}
    assert used == ["k1", "k2"]


def test_invalid_key_is_skipped_too() -> None:
    llm, used = keyed({"k1": [httpx.Response(401)], "k2": [httpx.Response(403)], "k3": [reply("hi")]})
    assert llm.generate_text("q") == "hi"
    assert used == ["k1", "k2", "k3"]


def test_the_working_key_is_used_first_next_time() -> None:
    llm, used = keyed({"k1": [RATE_LIMITED], "k2": [reply("a"), reply("b")]})
    llm.generate_text("q")
    llm.generate_text("q")
    assert used == ["k1", "k2", "k2"]


def test_every_key_limited_gives_llm_unavailable_after_one_try_each() -> None:
    llm, used = keyed({"k1": [RATE_LIMITED], "k2": [RATE_LIMITED], "k3": [RATE_LIMITED]})
    with pytest.raises(LLMUnavailable, match="every groq key"):
        llm.generate_text("q")
    assert used == ["k1", "k2", "k3"]
    assert llm.stats.failures == 1


def test_server_error_does_not_burn_the_other_keys() -> None:
    llm, used = keyed({"k1": [httpx.Response(503)]})
    with pytest.raises(LLMUnavailable, match="HTTP 503"):
        llm.generate_text("q")
    assert used == ["k1"]  # the next LLM in the chain answers instead


def test_empty_keys_in_the_list_are_ignored() -> None:
    llm = OpenAICompatLLM(["", " ", "k1"], "m")
    assert llm.configured and llm._keys == ["k1"]


def test_settings_split_the_key_lists() -> None:
    s = Settings(_env_file=None, groq_api_keys="a, b,,c", openrouter_api_keys="x")
    assert s.groq_key_list == ["a", "b", "c"]
    assert s.openrouter_key_list == ["x"]
    c = Container(s)
    assert c.groq._keys == ["a", "b", "c"] and c.openrouter._keys == ["x"]
