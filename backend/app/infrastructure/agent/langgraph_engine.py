"""The real AnswerEngine: the agent steps wired as a LangGraph state graph (D1-T4, SRS 7.4).

The steps and routing rules live in application/agent (pure, unit tested); this file only
connects them, times each step (FR-AGT-14) and maps the final state to the domain Answer.
"""

import dataclasses
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.application.agent import routing, steps
from app.application.agent.state import AgentState
from app.application.agent.steps import AgentDeps
from app.domain.entities import Answer, Message
from app.domain.value_objects import Channel

log = logging.getLogger(__name__)

Step = Callable[[AgentState, AgentDeps], dict[str, Any]]


class LangGraphAnswerEngine:
    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps
        self._graph = self._build()  # compiled once, reused for every question

    def _timed(self, name: str, step: Step) -> Callable[[AgentState], dict[str, Any]]:
        def run(state: AgentState) -> dict[str, Any]:
            started = time.perf_counter()
            update = step(state, self._deps)
            return {**update, "timings": {name: round((time.perf_counter() - started) * 1000, 1)}}

        return run

    def _build(self) -> Any:
        graph = StateGraph(AgentState)
        nodes: dict[str, Step] = {
            routing.CLASSIFY: steps.classify,
            routing.LLM_CLASSIFY: steps.llm_classify,
            routing.RETRIEVE: steps.retrieve,
            routing.GENERATE: steps.generate,
            routing.FINALIZE: steps.finalize,
            routing.FINALIZE_FOLLOW_UP: steps.finalize_follow_up,
            routing.FALLBACK: steps.fallback,
        }
        for name, step in nodes.items():
            graph.add_node(name, self._timed(name, step))

        threshold = self._deps.confidence_threshold
        graph.add_edge(START, routing.CLASSIFY)
        graph.add_conditional_edges(
            routing.CLASSIFY,
            lambda state: routing.after_classify(state, threshold),
            [routing.RETRIEVE, routing.LLM_CLASSIFY, routing.FALLBACK],
        )
        graph.add_conditional_edges(
            routing.LLM_CLASSIFY, routing.after_llm_classify, [routing.RETRIEVE, routing.FALLBACK]
        )
        graph.add_edge(routing.RETRIEVE, routing.GENERATE)
        graph.add_conditional_edges(
            routing.GENERATE,
            routing.after_generate,
            [routing.FINALIZE, routing.FINALIZE_FOLLOW_UP, routing.FALLBACK],
        )
        for last in (routing.FINALIZE, routing.FINALIZE_FOLLOW_UP, routing.FALLBACK):
            graph.add_edge(last, END)
        return graph.compile()

    def answer(self, question: str, history: Sequence[Message], channel: Channel) -> Answer:
        started = time.perf_counter()
        initial: AgentState = {
            "question": question, "history": list(history), "channel": channel,
            "retries": 0, "timings": {}, "llm_calls": 0,
        }  # fmt: skip
        final = self._graph.invoke(initial)
        timings = {**final.get("timings", {}), "total": round((time.perf_counter() - started) * 1000, 1)}
        answer: Answer = final["answer"]
        log.info(
            "agent service=%s router=%s status=%s llm_calls=%d timings=%s",
            answer.service_id, answer.router_source, answer.status, final.get("llm_calls", 0), timings,
        )  # fmt: skip
        return dataclasses.replace(answer, timings=timings, llm_calls=final.get("llm_calls", 0))
