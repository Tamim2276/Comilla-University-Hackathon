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
    return {**old, **new}


class AgentState(TypedDict, total=False):
    question: str
    history: Sequence[Message]  # oldest first, without the current question
    channel: Channel
    pending_service_id: str | None  # set when the last assistant turn asked a follow-up (FR-AGT-17)
    candidates: list[tuple[str, float]]  # router top 3, best first
    service_id: str
    confidence: float
    router_source: RouterSource
    query: str  # what is sent to the retriever (rewritten in D1-T5)
    passages: list[Passage]
    relevant_ids: list[str]  # "P1", "P2"... (grading, D1-T5)
    retries: int
    draft: dict[str, Any]  # the generate step's JSON
    verified_claims: list[dict[str, Any]]  # (verify, D1-T5)
    answer: Answer
    timings: Annotated[dict[str, float], merge_timings]
    llm_calls: Annotated[int, operator.add]
