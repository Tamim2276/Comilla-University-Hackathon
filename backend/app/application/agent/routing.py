"""Which step runs next (SRS 7.4). Pure functions of the state, so each branch is easy to test.

classify -> (cache_lookup) | (llm_classify) -> retrieve -> grade -> generate -> verify -> finalize, with
rewrite_query -> retrieve loops sharing one `retries` counter, finalize_follow_up for a missing
fact, and fallback for `other` or when nothing reliable is left. Voice fast mode skips grade.
"""

from app.application.agent.state import AgentState
from app.domain.value_objects import RouterSource

OTHER = "other"

CLASSIFY = "classify"
CACHE_LOOKUP = "cache_lookup"
DONE = "done"  # the graph's end, used as a routing target
LLM_CLASSIFY = "llm_classify"
RETRIEVE = "retrieve"
GRADE = "grade"
REWRITE_QUERY = "rewrite_query"
GENERATE = "generate"
VERIFY = "verify"
FINALIZE = "finalize"
FINALIZE_FOLLOW_UP = "finalize_follow_up"
FALLBACK = "fallback"


def _retry_or_fallback(state: AgentState, max_retries: int) -> str:
    return REWRITE_QUERY if state.get("retries", 0) < max_retries else FALLBACK  # FR-AGT-07


def after_classify(state: AgentState, threshold: float) -> str:
    if state.get("pending_service_id"):
        return RETRIEVE  # FR-AGT-17: keep the service of the pending follow-up
    if state.get("needs_context") and state.get("router_source") is not RouterSource.LLM:
        return LLM_CLASSIFY  # a short follow-up question: the LLM reads the last turns
    label = state.get("service_id")
    confident = state.get("confidence", 0.0) >= threshold
    if confident or state.get("router_source") is RouterSource.LLM:  # the LLM router is not asked twice
        if label == OTHER or not label:
            return FALLBACK
        return CACHE_LOOKUP if state.get("cache_key") else RETRIEVE  # FR-AGT-15
    return LLM_CLASSIFY  # FR-AGT-03


def after_cache_lookup(state: AgentState) -> str:
    return DONE if state.get("answer") is not None else RETRIEVE


def after_llm_classify(state: AgentState) -> str:
    return FALLBACK if state.get("service_id") in (None, "", OTHER) else RETRIEVE  # FR-AGT-04


def after_retrieve(state: AgentState, fast_mode: bool) -> str:
    """Voice fast mode skips grading: generate itself says `no_answer` (FR-AGT-06)."""
    return GENERATE if fast_mode else GRADE


def after_grade(state: AgentState, max_retries: int) -> str:
    return GENERATE if state.get("relevant_ids") else _retry_or_fallback(state, max_retries)


def after_generate(state: AgentState, max_retries: int) -> str:
    draft = state.get("draft") or {}
    if draft.get("no_answer") or not str(draft.get("speech_text", "")).strip():
        return _retry_or_fallback(state, max_retries)
    follow_up = str(draft.get("follow_up_question") or "").strip()
    if follow_up and not state.get("pending_service_id"):  # FR-AGT-09: at most one follow-up
        return FINALIZE_FOLLOW_UP
    return VERIFY


def after_verify(state: AgentState, max_retries: int) -> str:
    """All core claims and the spoken answer supported -> finalize; else retry, then fall back (FR-AGT-10)."""
    if state.get("answers_question") is False:
        return FALLBACK  # true facts, but for another question: a retry would not change that
    claims = state.get("verified_claims") or []
    supported = [c for c in claims if c.get("supported")]
    core_failed = any(c.get("core") and not c.get("supported") for c in claims)
    if supported and not core_failed and state.get("speech_supported", True):
        return FINALIZE
    return _retry_or_fallback(state, max_retries)
