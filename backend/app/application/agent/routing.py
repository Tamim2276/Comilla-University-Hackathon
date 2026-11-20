"""Which step runs next (SRS 7.4). Pure functions of the state, so each branch is easy to test.

v1 (D1-T4): classify -> (llm_classify) -> retrieve -> generate -> finalize | finalize_follow_up,
and fallback for `other` or `no_answer`. D1-T5 adds grade, rewrite_query and verify.
"""

from app.application.agent.state import AgentState
from app.domain.value_objects import RouterSource

OTHER = "other"

CLASSIFY = "classify"
LLM_CLASSIFY = "llm_classify"
RETRIEVE = "retrieve"
GENERATE = "generate"
FINALIZE = "finalize"
FINALIZE_FOLLOW_UP = "finalize_follow_up"
FALLBACK = "fallback"


def after_classify(state: AgentState, threshold: float) -> str:
    if state.get("pending_service_id"):
        return RETRIEVE  # FR-AGT-17: keep the service of the pending follow-up
    label = state.get("service_id")
    confident = state.get("confidence", 0.0) >= threshold
    if confident or state.get("router_source") is RouterSource.LLM:  # the LLM router is not asked twice
        return FALLBACK if label == OTHER or not label else RETRIEVE
    return LLM_CLASSIFY  # FR-AGT-03


def after_llm_classify(state: AgentState) -> str:
    return FALLBACK if state.get("service_id") in (None, "", OTHER) else RETRIEVE  # FR-AGT-04


def after_generate(state: AgentState) -> str:
    draft = state.get("draft") or {}
    if draft.get("no_answer") or not str(draft.get("speech_text", "")).strip():
        return FALLBACK  # D1-T5: rewrite and retry first
    follow_up = str(draft.get("follow_up_question") or "").strip()
    if follow_up and not state.get("pending_service_id"):  # FR-AGT-09: at most one follow-up
        return FINALIZE_FOLLOW_UP
    return FINALIZE
