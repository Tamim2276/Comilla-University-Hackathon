"""The agent's steps (SRS 7.4): pure functions `(state, deps) -> the state keys they change`.

They only use ports, so unit tests run them with fakes, and the LangGraph wiring in
infrastructure/agent stays a thin layer around them.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.application.agent import prompts
from app.application.agent.cache_key import cache_key
from app.application.agent.routing import OTHER
from app.application.agent.state import AgentState
from app.application.formatting import limit_sentences, trim_speech
from app.application.ports.classifier import ServiceClassifier
from app.application.ports.llm import LLM, ModelRole, ReportsProvider
from app.application.ports.repositories import AnswerCache
from app.application.ports.retrieval import Passage, Retriever
from app.domain.entities import Answer, Checklist, Citation, Message, Service
from app.domain.errors import ClassifierUnavailable
from app.domain.messages_bn import DECISION_NOTE, FALLBACK
from app.domain.policies import MAX_RETRIEVAL_RETRIES, ROUTER_CONFIDENCE_THRESHOLD, TOP_K
from app.domain.value_objects import AnswerStatus, Channel, Role, RouterSource

log = logging.getLogger(__name__)

SNIPPET_WORDS = 30
FEE_QUERY = "ফি কত টাকা"
FEE_PASSAGES = 2  # fee passages added next to the top-k, see _with_fee_passages
AMOUNT_WORD = "টাকা"
SHORT_QUESTION_WORDS = 6  # a question this short, after an answer, may only make sense with the conversation
UNKNOWN_BN = "তথ্য পাওয়া যায়নি"
_BANGLA_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


@dataclass(frozen=True)
class AgentDeps:
    classifier: ServiceClassifier
    retriever: Retriever
    llm: LLM
    services: Mapping[str, Service]  # all 9 labels, `other` included
    confidence_threshold: float = ROUTER_CONFIDENCE_THRESHOLD
    top_k: int = TOP_K
    max_retries: int = MAX_RETRIEVAL_RETRIES
    cache: AnswerCache | None = None  # FR-AGT-15; None = no caching
    voice_fast_mode: bool = True  # calls skip `grade` (FR-AGT-06)
    llm_backend: str | None = None  # FR-AGT-18: recorded on every answer

    def fast_mode(self, channel: Channel | None) -> bool:
        return self.voice_fast_mode and channel is Channel.VOICE


# ---------------------------------------------------------------- small helpers


def to_bangla_digits(text: str) -> str:
    return text.translate(_BANGLA_DIGITS)


def pending_follow_up(history: Sequence[Message]) -> tuple[str | None, str | None]:
    """(service_id, the question that led to it) when the last assistant turn asked a follow-up."""
    for i in range(len(history) - 1, -1, -1):
        message = history[i]
        if message.role is Role.ASSISTANT:
            if message.status is AnswerStatus.FOLLOW_UP and message.service_id:
                earlier = [m.text for m in history[:i] if m.role is Role.USER]
                return message.service_id, earlier[-1] if earlier else None
            return None, None
    return None, None


def previous_service(history: Sequence[Message]) -> str | None:
    """The service of the last assistant turn (a real service, not `other`), if any."""
    for message in reversed(history):
        if message.role is Role.ASSISTANT:
            service = message.service_id
            return service if service and service != OTHER else None
    return None


def _clamp(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


# ---------------------------------------------------------------- steps


def classify(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Local router (FR-AGT-01), or the service of a pending follow-up (FR-AGT-17)."""
    question = state["question"]
    service_id, earlier_question = pending_follow_up(state.get("history", ()))
    if service_id in deps.services and service_id != OTHER:
        # A short reply such as "হ্যাঁ" finds nothing alone, so search with the earlier question too.
        query = f"{earlier_question} {question}" if earlier_question else question
        return {
            "pending_service_id": service_id, "service_id": service_id, "confidence": 1.0,
            "router_source": RouterSource.CONTEXT, "candidates": [], "query": query,
        }  # fmt: skip
    try:
        scores = deps.classifier.classify(question)
    except ClassifierUnavailable as exc:
        log.warning("router unavailable, asking the LLM instead: %s", exc)
        scores = []
    candidates = [(label, _clamp(score)) for label, score in scores[:3]]
    label, confidence = candidates[0] if candidates else (OTHER, 0.0)
    if label not in deps.services:
        label, confidence = OTHER, 0.0
    update: dict[str, Any] = {
        "pending_service_id": None, "candidates": candidates, "service_id": label,
        "confidence": confidence, "router_source": deps.classifier.source, "query": question,
    }  # fmt: skip
    local = deps.classifier.source is not RouterSource.LLM
    previous = previous_service(state.get("history", ()))
    if (
        local
        and previous in deps.services
        and label != previous
        and len(question.split()) <= SHORT_QUESTION_WORDS
    ):
        # "আর কোথায় জমা দেবো?" has no topic of its own: a local router guesses a wrong service, even
        # with high confidence. Let the LLM decide with the last turns, and never cache this question.
        update["needs_context"] = True
        return update
    # FR-AGT-15: cache only when the local router was sure, so short replies such as "হ্যাঁ"
    # (which depend on the conversation) are never served from the cache.
    if deps.cache is not None and local and label != OTHER and confidence >= deps.confidence_threshold:
        update["cache_key"] = cache_key(question, label, state["channel"])
    return update


def llm_classify(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Second opinion for unsure routers, with the top 3 hints and recent turns (FR-AGT-03)."""
    prompt = prompts.build_classify_prompt(
        state["question"], deps.services, state.get("candidates", []), state.get("history", ())
    )
    data = deps.llm.generate_json(
        prompt, prompts.classify_schema(list(deps.services)), role=ModelRole.FAST, temperature=0.0
    )
    label = _text(data.get("service_id"))
    if label not in deps.services:
        label = OTHER
    update: dict[str, Any] = {
        "service_id": label, "confidence": _clamp(data.get("confidence")),
        "router_source": RouterSource.LLM, "llm_calls": 1,
    }  # fmt: skip
    standalone = _text(data.get("search_query"))
    if standalone:  # "আর কোথায় জমা দেবো?" alone finds nothing; the full question does
        update["query"] = standalone
    return update


def cache_lookup(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """A repeated question within 24 hours is answered from the cache, with no LLM call (FR-AGT-15)."""
    key = state.get("cache_key")
    if not key or deps.cache is None:
        return {}
    try:
        hit = deps.cache.get(key)
    except Exception:  # a broken cache must never break answering
        log.exception("answer cache read failed")
        return {}
    return {"answer": hit} if hit is not None else {}


def retrieve(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Top-k official passages for the chosen service (FR-AGT-05; the merge fallback is in the adapter)."""
    query = state.get("query") or state["question"]
    service_id = state["service_id"]
    passages = deps.retriever.search(query, service_id, deps.top_k)
    fees = _fee_passages(service_id, deps)
    have = {p.chunk_id for p in passages}
    extra = [p for p in fees if p.chunk_id not in have]
    return {"query": query, "passages": [*passages, *extra], "fee_ids": [p.chunk_id for p in fees]}


def _fee_passages(service_id: str, deps: AgentDeps) -> list[Passage]:
    """The service's fee passages, so the checklist fee is filled even when the question is not
    about money ("how do I correct my name" still needs the fee table). `grade` keeps them.

    One more local search (no LLM call). Only passages that state an amount are kept.
    """
    fee_query = f"{deps.services[service_id].name_bn} {FEE_QUERY}"
    found = deps.retriever.search(fee_query, service_id, FEE_PASSAGES)
    return [p for p in found if AMOUNT_WORD in p.text]


def generate(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """One JSON answer from the passages only (FR-AGT-08, 09, 11)."""
    passages = state.get("passages") or []
    if not passages:
        return {"draft": {"no_answer": True}}
    prompt = prompts.build_generate_prompt(
        state["question"], deps.services[state["service_id"]], passages,
        state.get("history", ()), state["channel"],
    )  # fmt: skip
    data = deps.llm.generate_json(prompt, prompts.GENERATE_SCHEMA, role=ModelRole.MAIN, temperature=0.2)
    # A chain answers with whichever provider was available: record that one (FR-AGT-18).
    provider = deps.llm.last_provider() if isinstance(deps.llm, ReportsProvider) else None
    return {"draft": data, "llm_calls": 1, "llm_provider": provider}


def grade(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """One FAST call for all passages; keeps only the useful ones for `generate` (FR-AGT-06)."""
    passages = state.get("passages") or []
    if not passages:
        return {"relevant_ids": []}
    data = deps.llm.generate_json(
        prompts.build_grade_prompt(state["question"], passages),
        prompts.GRADE_SCHEMA,
        role=ModelRole.FAST,
        temperature=0.0,
    )
    raw = data.get("relevant_ids") if isinstance(data.get("relevant_ids"), list) else []
    wanted = {_text(pid).strip("[]").upper() for pid in raw}
    kept = [p for i, p in enumerate(passages) if prompts.passage_id(i) in wanted]
    if kept:  # the fee passages are not about the question, but the checklist card needs them
        fee_ids = set(state.get("fee_ids") or [])
        kept += [p for p in passages if p.chunk_id in fee_ids and p not in kept]
    return {
        "relevant_ids": [prompts.passage_id(i) for i in range(len(kept))],
        "passages": kept,
        "llm_calls": 1,
    }


def rewrite_query(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """A clearer, more formal search query, then retrieve again (FR-AGT-07). Counts one retry."""
    question = state["question"]
    data = deps.llm.generate_json(
        prompts.build_rewrite_prompt(
            question, state.get("query") or question, deps.services[state["service_id"]],
            state.get("history", ()),
        ),
        prompts.REWRITE_SCHEMA,
        role=ModelRole.FAST,
        temperature=0.3,
    )  # fmt: skip
    query = _text(data.get("query")) or question
    return {"query": query, "retries": state.get("retries", 0) + 1, "llm_calls": 1}


def verify(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """One MAIN call checks every claim and the spoken answer against the passages (FR-AGT-10)."""
    draft = state["draft"]
    claims = [c for c in draft.get("claims") or [] if isinstance(c, Mapping) and _text(c.get("text"))]
    if not claims:
        return {"verified_claims": [], "speech_supported": False}  # nothing checkable = not reliable
    checklist = draft.get("checklist") if isinstance(draft.get("checklist"), Mapping) else {}
    data = deps.llm.generate_json(
        prompts.build_verify_prompt(
            [_text(c.get("text")) for c in claims],
            _text(draft.get("speech_text")),
            state.get("passages") or [],
            display=_text(draft.get("display_text")),
            checklist=checklist,
            question=state.get("question", ""),
        ),
        prompts.VERIFY_SCHEMA,
        role=ModelRole.MAIN,
        temperature=0.0,
    )
    verdicts: dict[int, bool] = {}
    for item in data.get("claims") or []:
        if isinstance(item, Mapping) and isinstance(item.get("index"), int):
            verdicts[item["index"]] = bool(item.get("supported"))
    checked = [
        {**c, "core": bool(c.get("core")), "supported": verdicts.get(i, False)} for i, c in enumerate(claims)
    ]
    unsupported = [c["text"] for c in checked if not c["supported"]]
    if unsupported:
        log.info("verify: %d of %d claims unsupported", len(unsupported), len(checked))
    raw_fields = (
        data.get("unsupported_checklist") if isinstance(data.get("unsupported_checklist"), list) else []
    )
    bad_fields = [f for f in (_text(x) for x in raw_fields) if f in prompts.CHECKLIST_FIELDS]
    display_ok = bool(data.get("display_supported", True))
    if bad_fields or not display_ok:
        log.info("verify: checklist fields unsupported %s, screen text supported %s", bad_fields, display_ok)
    answers = bool(data.get("answers_question", True))
    if not answers:
        log.info("verify: the answer is about another question than the one asked")
    return {
        "verified_claims": checked,
        "answers_question": answers,
        "speech_supported": bool(data.get("speech_supported", True)),
        "display_supported": display_ok,
        "unsupported_checklist": bad_fields,
        "llm_calls": 1,
    }


def finalize(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Turns the checked draft into an `answered` Answer (FR-AGT-08, 12).

    Unsupported non-core claims are dropped, so only passages behind supported claims are cited.
    A screen text with an unsupported fact is replaced by the (verified) spoken answer, and
    unsupported checklist fields become "তথ্য পাওয়া যায়নি".
    """
    draft = state["draft"]
    service = deps.services[state["service_id"]]
    speech = trim_speech(_text(draft.get("speech_text")))
    if state.get("channel") is Channel.VOICE:
        speech = limit_sentences(speech)
    speech = to_bangla_digits(speech)
    display = _text(draft.get("display_text")) if state.get("display_supported", True) else ""
    display = display or speech
    if DECISION_NOTE not in display:
        display = f"{display}\n\n_{DECISION_NOTE}_"
    answer = Answer(
        status=AnswerStatus.ANSWERED,
        speech_text=speech,
        display_text=display,
        service_id=service.id,
        confidence=_clamp(state.get("confidence")),
        router_source=state.get("router_source"),
        checklist=build_checklist(draft.get("checklist"), service, state.get("unsupported_checklist") or ()),
        citations=build_citations(_supported_claims(state), state.get("passages") or []),
        llm_backend=state.get("llm_provider") or deps.llm_backend,
    )
    _store_in_cache(state, deps, answer)
    return {"answer": answer}


def _store_in_cache(state: AgentState, deps: AgentDeps, answer: Answer) -> None:
    """Only `answered` results are stored (FR-AGT-15), and only if a cache key was set."""
    key = state.get("cache_key")
    if not key or deps.cache is None or answer.status is not AnswerStatus.ANSWERED:
        return
    try:
        deps.cache.set(key, answer)
    except Exception:
        log.exception("answer cache write failed")


def _supported_claims(state: AgentState) -> list[dict[str, Any]]:
    verified = state.get("verified_claims")
    if verified is None:  # not verified (follow-up path, tests): use the draft's claims
        return list(state["draft"].get("claims") or [])
    return [c for c in verified if c.get("supported")]


def finalize_follow_up(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """Asks the one missing eligibility fact (FR-AGT-09); the next turn keeps this service."""
    question = to_bangla_digits(_text(state["draft"].get("follow_up_question")))
    answer = Answer(
        status=AnswerStatus.FOLLOW_UP,
        speech_text=question,
        display_text=question,
        service_id=state["service_id"],
        confidence=_clamp(state.get("confidence")),
        router_source=state.get("router_source"),
        follow_up_question=question,
        llm_backend=state.get("llm_provider") or deps.llm_backend,
    )
    return {"answer": answer}


def fallback(state: AgentState, deps: AgentDeps) -> dict[str, Any]:
    """The exact FALLBACK text (FR-AGT-04, FR-AGT-13)."""
    service_id = state.get("service_id")
    answer = Answer(
        status=AnswerStatus.FALLBACK,
        speech_text=FALLBACK,
        display_text=FALLBACK,
        service_id=service_id if service_id and service_id != OTHER else None,
        confidence=_clamp(state.get("confidence")),
        router_source=state.get("router_source"),
        llm_backend=state.get("llm_provider") or deps.llm_backend,
    )
    return {"answer": answer}


# ---------------------------------------------------------------- answer parts


def build_checklist(raw: Any, service: Service, unsupported: Sequence[str] = ()) -> Checklist:
    """The checklist card and SMS. Fields the verifier found unsupported are replaced, never shown."""
    data = dict(raw) if isinstance(raw, Mapping) else {}
    for field in unsupported:
        data[field] = [] if field == "papers" else ""
    papers = data.get("papers") if isinstance(data.get("papers"), list) else []
    where = _text(data.get("where")) or (UNKNOWN_BN if "where" in unsupported else service.office_bn)
    return Checklist(
        service_id=service.id,
        who=to_bangla_digits(_text(data.get("who")) or UNKNOWN_BN),
        papers=tuple(to_bangla_digits(_text(p)) for p in papers if _text(p)),
        fee=to_bangla_digits(_text(data.get("fee")) or UNKNOWN_BN),
        where=where,
        decision=_text(data.get("decision")) or DECISION_NOTE,
    )


def build_citations(claims: Any, passages: Sequence[Passage]) -> tuple[Citation, ...]:
    """The documents the claims cite, in order, one citation per document (source URL).

    If no claim cites a valid passage, the best passage is used, so an answer always has a source.
    """
    by_id = {prompts.passage_id(i): p for i, p in enumerate(passages)}
    cited: list[Passage] = []
    for claim in claims if isinstance(claims, list) else []:
        ids = claim.get("passage_ids", []) if isinstance(claim, Mapping) else []
        for pid in ids if isinstance(ids, list) else []:
            passage = by_id.get(_text(pid).strip("[]").upper())
            if passage is not None and all(p.source_url != passage.source_url for p in cited):
                cited.append(passage)
    if not cited and passages:
        cited = [passages[0]]
    return tuple(
        Citation(title=p.title, source_url=p.source_url, snippet=_snippet(p.text), chunk_id=p.chunk_id)
        for p in cited
    )


def _snippet(text: str) -> str:
    words = text.split()
    return " ".join(words[:SNIPPET_WORDS]) + (" …" if len(words) > SNIPPET_WORDS else "")
