"""What the agent knows while it works on one question (SRS 7.4).

Each step returns only the keys it changes. `timings` and `llm_calls` are merged across steps
(the Annotated reducers tell the graph how), everything else is replaced.
"""

import operator
from collections.abc import Mapping, Sequence
from typing import Annotated, Any, TypedDict

from app.application.ports.retrieval import Passage
from app.domain.entities import Answer, Message
from app.domain.value_objects import Channel, RouterSource


def merge_timings(old: Mapping[str, float], new: Mapping[str, float]) -> dict[str, float]:
    """A step that runs again (retrieve after a rewrite) adds to its earlier time."""
    merged = dict(old)
    for step, ms in new.items():
        merged[step] = round(merged.get(step, 0.0) + ms, 1)
    return merged


class AgentState(TypedDict, total=False):
    question: str
    history: Sequence[Message]  # oldest first, without the current question
    channel: Channel
    pending_service_id: str | None  # set when the last assistant turn asked a follow-up (FR-AGT-17)
    candidates: list[tuple[str, float]]  # router top 3, best first
    service_id: str
    confidence: float
    router_source: RouterSource
    query: str  # what is sent to the retriever (rewrite_query changes it)
    passages: list[Passage]
    relevant_ids: list[str]  # "P1", "P2"... chosen by grade
    retries: int  # one counter for the grade, generate and verify loops (max MAX_RETRIEVAL_RETRIES)
    draft: dict[str, Any]  # the generate step's JSON
    verified_claims: list[dict[str, Any]]  # draft claims, each with `supported` added by verify
    speech_supported: bool
    answer: Answer
    timings: Annotated[dict[str, float], merge_timings]
    llm_calls: Annotated[int, operator.add]
