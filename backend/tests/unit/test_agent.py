"""Agent v1 (D1-T4): routing branches, steps and the whole LangGraph flow with fakes. No network.

FR-AGT-01 to 05, 08, 12, 13, 17.
"""

import dataclasses
from typing import Any

import pytest

from app.application.agent import prompts, routing, steps
from app.application.agent.state import AgentState
from app.application.agent.steps import AgentDeps
from app.application.ports.retrieval import Passage
from app.domain.entities import Message, Service
from app.domain.errors import ClassifierUnavailable, LLMUnavailable
from app.domain.messages_bn import DECISION_NOTE, FALLBACK
from app.domain.value_objects import AnswerStatus, Channel, Role, RouterSource
from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
from app.infrastructure.ml.llm_classifier import LLMClassifier
from tests.fakes import FakeClassifier, FakeLLM, FakeRetriever

SERVICES = {
    sid: Service(id=sid, name_bn=name, name_en=sid, office_bn="উপজেলা অফিস", sms_name=name)
    for sid, name in [("old_age_allowance", "বয়স্ক ভাতা"), ("widow_allowance", "বিধবা ভাতা"), ("other", "অন্যান্য")]
}
PASSAGES = [
    Passage("old_age_allowance-001", "old_age_allowance", "বয়স্ক ভাতা", "https://dss.gov.bd/a",
            "পুরুষের ক্ষেত্রে সর্বনিম্ন 65 বছর বয়স হতে হবে।", 0.9),
    Passage("old_age_allowance-002", "old_age_allowance", "বয়স্ক ভাতা", "https://dss.gov.bd/a",
            "জাতীয় পরিচয়পত্র লাগবে।", 0.88),
    Passage("old_age_allowance-003", "old_age_allowance", "নীতিমালা", "https://dss.gov.bd/b",
            "বাছাই কমিটি চূড়ান্ত করবে।", 0.85),
]  # fmt: skip

GOOD_DRAFT: dict[str, Any] = {
    "no_answer": False,
    "speech_text": "পুরুষের 65 বছর হলে আবেদন করা যায়।",
    "display_text": "**বয়স্ক ভাতা**\n- বয়স 65+",
    "checklist": {"who": "পুরুষ 65+", "papers": ["জাতীয় পরিচয়পত্র", " "], "fee": "", "where": "", "decision": ""},
    "claims": [
        {"text": "বয়স 65", "passage_ids": ["P1"], "core": True},
        {"text": "এনআইডি", "passage_ids": ["[P2]", "P9"], "core": True},
        {"text": "কমিটি", "passage_ids": ["P3"], "core": False},
    ],
    "follow_up_question": "",
}


def deps(
    scores: dict[str, float] | None = None,
    llm: FakeLLM | None = None,
    passages: list[Passage] | None = None,
    classifier: Any = None,
) -> AgentDeps:
    return AgentDeps(
        classifier=classifier or FakeClassifier(scores or {"old_age_allowance": 0.95, "other": 0.05}),
        retriever=FakeRetriever(PASSAGES if passages is None else passages),
        llm=llm or FakeLLM([GOOD_DRAFT]),
        services=SERVICES,
        confidence_threshold=0.7,
        llm_backend="gemini",
    )


def user(text: str) -> Message:
    return Message(role=Role.USER, channel=Channel.APP, text=text)


def bot(text: str, status: AnswerStatus, service_id: str | None = "widow_allowance") -> Message:
    return Message(role=Role.ASSISTANT, channel=Channel.APP, text=text, service_id=service_id, status=status)


# ---------------------------------------------------------------- routing (SRS 7.4)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"pending_service_id": "widow_allowance", "service_id": "widow_allowance"}, routing.RETRIEVE),
        ({"service_id": "old_age_allowance", "confidence": 0.9}, routing.RETRIEVE),
        ({"service_id": "other", "confidence": 0.9}, routing.FALLBACK),  # FR-AGT-04
        ({"service_id": "old_age_allowance", "confidence": 0.5}, routing.LLM_CLASSIFY),  # FR-AGT-03
        ({"service_id": "other", "confidence": 0.5}, routing.LLM_CLASSIFY),
        ({"service_id": "old_age_allowance", "confidence": 0.3, "router_source": RouterSource.LLM},
         routing.RETRIEVE),  # the LLM router is never asked twice
    ],
)  # fmt: skip
def test_after_classify(state: AgentState, expected: str) -> None:
    assert routing.after_classify(state, threshold=0.7) == expected


def test_after_llm_classify() -> None:
    assert routing.after_llm_classify({"service_id": "other"}) == routing.FALLBACK
    assert routing.after_llm_classify({"service_id": "widow_allowance"}) == routing.RETRIEVE


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"draft": {"no_answer": True}}, routing.FALLBACK),
        ({"draft": {"no_answer": False, "speech_text": "  "}}, routing.FALLBACK),
        ({"draft": GOOD_DRAFT}, routing.FINALIZE),
        ({"draft": {**GOOD_DRAFT, "follow_up_question": "আপনি কি স্থায়ী বাসিন্দা?"}}, routing.FINALIZE_FOLLOW_UP),
        ({"draft": {**GOOD_DRAFT, "follow_up_question": "আবার?"}, "pending_service_id": "widow_allowance"},
         routing.FINALIZE),  # FR-AGT-09: only one follow-up
    ],
)  # fmt: skip
def test_after_generate(state: AgentState, expected: str) -> None:
    assert routing.after_generate(state) == expected


# ---------------------------------------------------------------- steps


def test_classify_uses_the_router_and_keeps_the_top_3() -> None:
    d = deps(scores={"old_age_allowance": 0.6, "widow_allowance": 0.3, "other": 0.08, "x": 0.02})
    out = steps.classify({"question": "ভাতা", "history": []}, d)
    assert out["service_id"] == "old_age_allowance" and out["confidence"] == 0.6
    assert out["router_source"] is RouterSource.TFIDF
    assert [label for label, _ in out["candidates"]] == ["old_age_allowance", "widow_allowance", "other"]


def test_classify_keeps_the_service_of_a_pending_follow_up() -> None:  # FR-AGT-17
    history = [user("বিধবা ভাতার জন্য কী লাগে?"), bot("আপনি কি স্থায়ী বাসিন্দা?", AnswerStatus.FOLLOW_UP)]
    d = deps()
    out = steps.classify({"question": "হ্যাঁ", "history": history}, d)
    assert out["service_id"] == "widow_allowance" and out["router_source"] is RouterSource.CONTEXT
    assert out["query"] == "বিধবা ভাতার জন্য কী লাগে? হ্যাঁ"  # the short reply alone finds nothing
    assert d.classifier.texts == []  # type: ignore[attr-defined]


def test_an_answered_last_turn_is_not_a_pending_follow_up() -> None:
    history = [user("বিধবা ভাতা?"), bot("উত্তর", AnswerStatus.ANSWERED)]
    out = steps.classify({"question": "হ্যাঁ", "history": history}, deps())
    assert out["router_source"] is RouterSource.TFIDF


def test_classify_survives_a_missing_router_model() -> None:
    class Broken(FakeClassifier):
        def classify(self, text: str) -> list[tuple[str, float]]:
            raise ClassifierUnavailable("no model")

    out = steps.classify({"question": "ভাতা", "history": []}, deps(classifier=Broken({})))
    assert out["confidence"] == 0.0  # -> llm_classify decides
    assert routing.after_classify(out, 0.7) == routing.LLM_CLASSIFY  # type: ignore[arg-type]


def test_llm_classify_gets_hints_and_history_and_rejects_unknown_labels() -> None:
    llm = FakeLLM(
        [
            {"service_id": "widow_allowance", "confidence": 0.9},
            {"service_id": "nope", "confidence": 2},
        ]
    )
    d = deps(llm=llm)
    state: AgentState = {
        "question": "আর কী লাগে?", "history": [user("বিধবা ভাতা কী?")],
        "candidates": [("old_age_allowance", 0.4), ("widow_allowance", 0.35)],
    }  # fmt: skip
    out = steps.llm_classify(state, d)
    assert out == {"service_id": "widow_allowance", "confidence": 0.9,
                   "router_source": RouterSource.LLM, "llm_calls": 1}  # fmt: skip
    assert "old_age_allowance 0.40" in llm.prompts[0] and "বিধবা ভাতা কী?" in llm.prompts[0]
    assert steps.llm_classify(state, d)["service_id"] == "other"


def test_retrieve_searches_the_chosen_service() -> None:
    d = deps()
    out = steps.retrieve({"question": "q", "query": "rewritten", "service_id": "old_age_allowance"}, d)
    assert len(out["passages"]) == 3
    assert d.retriever.searches == [("rewritten", "old_age_allowance", 5)]  # type: ignore[attr-defined]


def test_generate_without_passages_skips_the_llm() -> None:
    d = deps(llm=FakeLLM(fail=True))
    assert steps.generate({"question": "q", "passages": []}, d) == {"draft": {"no_answer": True}}


def test_generate_prompt_numbers_passages_and_mentions_sms_on_voice() -> None:
    llm = FakeLLM([GOOD_DRAFT])
    state: AgentState = {"question": "বয়স?", "service_id": "old_age_allowance", "passages": PASSAGES,
                         "history": [], "channel": Channel.VOICE}  # fmt: skip
    assert steps.generate(state, deps(llm=llm))["llm_calls"] == 1
    assert "[P1] বয়স্ক ভাতা:" in llm.prompts[0] and "[P3] নীতিমালা:" in llm.prompts[0]
    assert "SMS" in llm.prompts[0]


def test_finalize_builds_a_valid_answer() -> None:  # FR-AGT-08, 11, 12
    state: AgentState = {"draft": GOOD_DRAFT, "service_id": "old_age_allowance", "confidence": 0.95,
                         "router_source": RouterSource.TFIDF, "passages": PASSAGES}  # fmt: skip
    answer = steps.finalize(state, deps())["answer"]
    assert answer.status is AnswerStatus.ANSWERED
    assert answer.speech_text == "পুরুষের ৬৫ বছর হলে আবেদন করা যায়।"  # Bangla digits for speech
    assert DECISION_NOTE in answer.display_text
    assert answer.checklist.papers == ("জাতীয় পরিচয়পত্র",)
    assert answer.checklist.fee == steps.UNKNOWN_BN and answer.checklist.where == "উপজেলা অফিস"
    assert answer.checklist.decision == DECISION_NOTE
    # P1 and P2 are the same document -> one citation; P3 is another document; P9 does not exist.
    assert [c.source_url for c in answer.citations] == ["https://dss.gov.bd/a", "https://dss.gov.bd/b"]
    assert answer.llm_backend == "gemini"


def test_finalize_cites_the_best_passage_when_claims_cite_nothing() -> None:
    draft = {**GOOD_DRAFT, "claims": []}
    state: AgentState = {"draft": draft, "service_id": "old_age_allowance", "passages": PASSAGES}
    citations = steps.finalize(state, deps())["answer"].citations
    assert [c.chunk_id for c in citations] == ["old_age_allowance-001"]


def test_fallback_uses_the_exact_text_and_hides_other() -> None:  # FR-AGT-13
    answer = steps.fallback({"service_id": "other", "confidence": 0.9}, deps())["answer"]
    assert answer.status is AnswerStatus.FALLBACK
    assert answer.speech_text == FALLBACK == answer.display_text
    assert answer.service_id is None


# ---------------------------------------------------------------- the whole graph


def test_engine_answers_a_confident_question_with_one_llm_call() -> None:
    engine = LangGraphAnswerEngine(deps())
    answer = engine.answer("আমার বয়স ৬৭, বয়স্ক ভাতা পাবো?", [], Channel.APP)
    assert answer.status is AnswerStatus.ANSWERED and answer.service_id == "old_age_allowance"
    assert answer.router_source is RouterSource.TFIDF and answer.llm_calls == 1
    assert set(answer.timings) == {"classify", "retrieve", "generate", "finalize", "total"}  # FR-AGT-14


def test_engine_sends_other_to_fallback_without_rag() -> None:
    d = deps(scores={"other": 0.9, "old_age_allowance": 0.1}, llm=FakeLLM(fail=True))
    answer = LangGraphAnswerEngine(d).answer("আজ বৃষ্টি হবে?", [], Channel.APP)
    assert answer.status is AnswerStatus.FALLBACK and answer.llm_calls == 0
    assert d.retriever.searches == []  # type: ignore[attr-defined]


def test_engine_asks_the_llm_when_the_router_is_unsure() -> None:
    llm = FakeLLM([{"service_id": "old_age_allowance", "confidence": 0.8}, GOOD_DRAFT])
    d = deps(scores={"old_age_allowance": 0.4, "other": 0.35}, llm=llm)
    answer = LangGraphAnswerEngine(d).answer("ভাতা নিয়ে জানতে চাই", [], Channel.VOICE)
    assert answer.router_source is RouterSource.LLM and answer.llm_calls == 2
    assert "llm_classify" in answer.timings


def test_engine_falls_back_when_the_passages_do_not_answer() -> None:
    d = deps(llm=FakeLLM([{"no_answer": True, "speech_text": "", "display_text": "", "claims": []}]))
    answer = LangGraphAnswerEngine(d).answer("বয়স্ক ভাতার অফিস কখন খোলে?", [], Channel.APP)
    assert answer.status is AnswerStatus.FALLBACK and answer.service_id == "old_age_allowance"


def test_engine_follow_up_then_answer_keeps_the_service() -> None:  # S2
    follow = {**GOOD_DRAFT, "follow_up_question": "আপনি কি এই এলাকার স্থায়ী বাসিন্দা?"}
    llm = FakeLLM([follow, GOOD_DRAFT])
    widow_passage = dataclasses.replace(PASSAGES[0], service_id="widow_allowance")
    engine = LangGraphAnswerEngine(
        deps(scores={"widow_allowance": 0.9, "other": 0.1}, llm=llm, passages=[widow_passage])
    )
    first = engine.answer("বিধবা ভাতার জন্য কী লাগে?", [], Channel.VOICE)
    assert first.status is AnswerStatus.FOLLOW_UP and first.follow_up_question
    history = [user("বিধবা ভাতার জন্য কী লাগে?"), bot(first.speech_text, first.status)]
    second = engine.answer("হ্যাঁ", history, Channel.VOICE)
    assert second.status is AnswerStatus.ANSWERED and second.service_id == "widow_allowance"
    assert second.router_source is RouterSource.CONTEXT


def test_engine_lets_llm_errors_reach_the_caller() -> None:  # S9: the API turns it into the ERROR text
    with pytest.raises(LLMUnavailable):
        LangGraphAnswerEngine(deps(llm=FakeLLM(fail=True))).answer("বয়স্ক ভাতা?", [], Channel.APP)


# ---------------------------------------------------------------- LLM router (ROUTER_BACKEND=llm)


def test_llm_classifier_returns_all_labels_sorted() -> None:
    clf = LLMClassifier(FakeLLM([{"service_id": "widow_allowance", "confidence": 0.8}]), SERVICES)
    scores = clf.classify("স্বামী মারা গেছে, ভাতা পাবো?")
    assert clf.source is RouterSource.LLM
    assert scores[0] == ("widow_allowance", 0.8)
    assert {label for label, _ in scores} == set(SERVICES)
    assert sum(score for _, score in scores) == pytest.approx(1.0)


def test_classify_prompt_lists_every_label() -> None:
    prompt = prompts.build_classify_prompt("প্রশ্ন", SERVICES)
    assert all(f"- {sid}:" in prompt for sid in SERVICES)
