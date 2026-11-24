"""LLM adapter for any OpenAI-compatible chat API; used for Groq as the fallback LLM (FR-AGT-16).

POST {base_url}/chat/completions with a bearer key. For JSON, the reply is forced into a JSON object
(`response_format: json_object`) and our JSON schema is given in a system message, since the agent's
steps expect one exact shape. One model serves both roles, so `role` is ignored.

Several keys (GROQ_API_KEYS=key1,key2), like Gemini: when a key is rate-limited (429) or refused
(401, 403), the next key is tried; each key gets one chance per request, and the key that worked is
used first next time. Server errors, timeouts and bad replies raise LLMUnavailable at once, so the
next LLM in the chain answers instead of this one retrying. Keys are named by position, never shown.
"""

import json
import logging
import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.application.ports.llm import ModelRole
from app.domain.errors import LLMUnavailable
from app.infrastructure.llm.common import LLMStats, parse_json_object

log = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
KEY_PROBLEMS = (401, 403, 429)  # this key is refused or rate-limited; another key may still work


class OpenAICompatLLM:
    def __init__(
        self,
        api_keys: Sequence[str] | str,
        model: str,
        base_url: str = GROQ_BASE_URL,
        timeout_s: float = 20.0,
        name: str = "groq",
        client: httpx.Client | None = None,
    ) -> None:
        raw = [api_keys] if isinstance(api_keys, str) else list(api_keys)
        self._keys = [k.strip() for k in raw if k and k.strip()]
        self._key_index = 0
        self._lock = threading.Lock()
        self._model = model
        self._name = name
        self._http = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s)
        self.stats = LLMStats()

    @property
    def configured(self) -> bool:
        return bool(self._keys and self._model)

    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        role: ModelRole = ModelRole.MAIN,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        rules = "Reply with one JSON object only, no other text."
        if schema:
            rules += " It must match this JSON Schema:\n" + json.dumps(schema, ensure_ascii=False)
        messages = [{"role": "system", "content": rules}, {"role": "user", "content": prompt}]
        return parse_json_object(self._chat(messages, temperature, {"type": "json_object"}))

    def generate_text(self, prompt: str, role: ModelRole = ModelRole.FAST) -> str:
        return self._chat([{"role": "user", "content": prompt}], 0.2, None).strip()

    def last_provider(self) -> str | None:
        return self._name

    def check(self) -> bool:
        """True when the key is accepted (lists the models; no generation, no quota used)."""
        if not self.configured:
            return False
        try:
            response = self._http.get("/models", headers=self._headers(self._key_index), timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("%s check failed: %s", self._name, type(exc).__name__)
            return False
        return True

    def _headers(self, index: int) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._keys[index]}"}

    def _chat(self, messages: list[dict[str, str]], temperature: float, fmt: dict[str, str] | None) -> str:
        if not self.configured:
            raise LLMUnavailable(f"{self._name} is not configured")
        body: dict[str, Any] = {"model": self._model, "messages": messages, "temperature": temperature}
        if fmt is not None:
            body["response_format"] = fmt
        started = time.perf_counter()
        try:
            content = self._post_with_key_rotation(body)
        except LLMUnavailable:
            self.stats.record(time.perf_counter() - started, ok=False)
            raise
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            self.stats.record(time.perf_counter() - started, ok=False)
            reason = type(exc).__name__
            raise LLMUnavailable(f"{self._name} is not reachable or replied badly ({reason})") from exc
        if not isinstance(content, str) or not content.strip():
            self.stats.record(time.perf_counter() - started, ok=False)
            raise LLMUnavailable(f"{self._name} returned an empty reply")
        elapsed = time.perf_counter() - started
        self.stats.record(elapsed, ok=True)
        log.info("%s call %.2fs", self._name, elapsed)
        return content

    def _post_with_key_rotation(self, body: dict[str, Any]) -> Any:
        """The reply's text, trying the next key on 401/403/429; each key once per request."""
        last: httpx.HTTPStatusError | None = None
        for _ in range(len(self._keys)):
            index = self._key_index
            response = self._http.post("/chat/completions", json=body, headers=self._headers(index))
            if response.status_code in KEY_PROBLEMS:
                code = response.status_code
                log.warning("%s key #%d unusable (HTTP %d); trying the next key", self._name, index + 1, code)
                with self._lock:
                    if self._key_index == index:
                        self._key_index = (index + 1) % len(self._keys)
                last = httpx.HTTPStatusError("key problem", request=response.request, response=response)
                continue
            if response.status_code >= 400:
                raise LLMUnavailable(f"{self._name} returned HTTP {response.status_code}")
            return response.json()["choices"][0]["message"]["content"]
        code = last.response.status_code if last is not None else 0
        raise LLMUnavailable(f"every {self._name} key is rate-limited or refused (last HTTP {code})")

    def close(self) -> None:
        self._http.close()
