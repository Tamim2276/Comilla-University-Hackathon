"""Prompt templates and JSON schemas for the agent's LLM calls (SRS Appendix B, FR-AGT-03, 06 to 10).

Passages are shown as `[P1] title: text` so claims can cite `P1`. Instructions are in English
(models follow them best); everything the citizen sees must come back in Bangla.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from app.application.ports.retrieval import Passage
from app.domain.entities import Message, Service
from app.domain.messages_bn import DECISION_NOTE
from app.domain.policies import HISTORY_TURNS_FOR_PROMPT, MAX_SPEECH_WORDS
from app.domain.value_objects import Channel, Role

# ---------------------------------------------------------------- shared pieces


def passage_id(index: int) -> str:
    return f"P{index + 1}"


def format_passages(passages: Sequence[Passage]) -> str:
    return "\n\n".join(f"[{passage_id(i)}] {p.title}: {p.text}" for i, p in enumerate(passages))


def format_history(history: Sequence[Message], turns: int = HISTORY_TURNS_FOR_PROMPT) -> str:
    """The last `turns` question/answer pairs, oldest first, or "(none)"."""
    recent = list(history)[-2 * turns :]
    if not recent:
        return "(none)"
    who = {Role.USER: "Citizen", Role.ASSISTANT: "Ek Call"}
    return "\n".join(f"{who[m.role]}: {m.text}" for m in recent)


def format_services(services: Mapping[str, Service]) -> str:
    return "\n".join(f"- {s.id}: {s.name_bn} ({s.name_en})" for s in services.values())


# ---------------------------------------------------------------- llm_classify (FR-AGT-03)

CLASSIFY_PROMPT = """You route questions for "Ek Call", a Bangla phone helpline about Bangladesh
government services. Pick the ONE label the citizen's latest question is about.

Labels:
{labels}
Use `other` for anything that is not one of these services (other government services, land
disputes, health, weather, jokes...).

Hints from a small classifier (may be wrong): {hints}

Conversation so far (use it to understand short replies such as "হ্যাঁ" or "আর কী লাগে?"):
{history}

Latest question: {question}

Return JSON with `service_id` (one label), `confidence` (0 to 1) and `search_query`: the latest
question rewritten in Bangla as one complete question that makes sense without the conversation
(for example "আর কোথায় জমা দেবো?" after a widow allowance question -> "বিধবা ভাতার আবেদন কোথায়
জমা দিতে হয়?")."""


def classify_schema(labels: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "service_id": {"type": "string", "enum": list(labels)},
            "confidence": {"type": "number"},
            "search_query": {"type": "string"},
        },
        "required": ["service_id", "confidence"],
    }


def build_classify_prompt(
    question: str,
    services: Mapping[str, Service],
    hints: Sequence[tuple[str, float]] = (),
    history: Sequence[Message] = (),
) -> str:
    hint_text = ", ".join(f"{label} {score:.2f}" for label, score in hints[:3]) or "(none)"
    return CLASSIFY_PROMPT.format(
        labels=format_services(services),
        hints=hint_text,
        history=format_history(history),
        question=question,
    )


# ---------------------------------------------------------------- generate (FR-AGT-08, 09, 11)

GENERATE_PROMPT = """You are "Ek Call", a Bangla helpline that explains Bangladesh government
services to rural and elderly citizens. Service: {service_name}. Channel: {channel}.

Official passages (the ONLY allowed source of facts):
{passages}

Conversation so far:
{history}

Citizen's question: {question}

Rules:
1. Answer only from the passages above. If they do not answer the question, return
   "no_answer": true and leave the other text fields empty. A passage on a related topic is
   NOT an answer: if the citizen asks how to do something (for example how to file a court
   case or settle a boundary dispute) and the passages only describe a different procedure
   (for example how to check whether a case exists), return "no_answer": true.
2. Write everyday Bangla in short sentences for an elderly listener. In speech_text avoid
   English words unless there is no Bangla word. Write all numbers in Bangla digits (৬৫, not 65).
   Never assume facts the citizen did not say (gender, income, residence); state the rule instead.
3. speech_text: at most {max_words} words, the direct answer first. {channel_rule}
4. Never promise that the citizen will get the benefit. Explain the rules and who decides.
   The checklist field `decision` says who decides; if unsure, use: "{decision_note}"
5. display_text: Bangla markdown for a screen: a bold title line, then short bullet points.
6. checklist: who (who can apply), papers (list of documents), fee, where (office or website),
   decision. Use only facts from the passages; write "তথ্য পাওয়া যায়নি" for an unknown field.
7. claims: every fact you state, each with the passage_ids that support it (for example ["P1"])
   and core = true when the answer is wrong without it.
8. follow_up_question: almost always EMPTY. Conditions the citizen did not mention (gender,
   income, residence, documents) are explained in the answer as rules, never asked. Ask ONE
   short Bangla question only when the question cannot be answered usefully at all without one
   fact (for example: they ask "কী লাগবে?" for a correction but did not say what is wrong).
   Still fill every other field. Never ask about something already said in the conversation.
9. Output JSON only, matching the schema exactly."""

_VOICE_RULE = "End with a short sentence saying the details are coming by SMS."
_APP_RULE = "The citizen reads the answer on a screen."

GENERATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "no_answer": {"type": "boolean"},
        "speech_text": {"type": "string"},
        "display_text": {"type": "string"},
        "checklist": {
            "type": "object",
            "properties": {
                "who": {"type": "string"},
                "papers": {"type": "array", "items": {"type": "string"}},
                "fee": {"type": "string"},
                "where": {"type": "string"},
                "decision": {"type": "string"},
            },
            "required": ["who", "papers", "fee", "where", "decision"],
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "passage_ids": {"type": "array", "items": {"type": "string"}},
                    "core": {"type": "boolean"},
                },
                "required": ["text", "passage_ids", "core"],
            },
        },
        "follow_up_question": {"type": "string"},
    },
    "required": ["no_answer", "speech_text", "display_text", "checklist", "claims"],
}


def build_generate_prompt(
    question: str,
    service: Service,
    passages: Sequence[Passage],
    history: Sequence[Message],
    channel: Channel,
) -> str:
    return GENERATE_PROMPT.format(
        service_name=f"{service.name_bn} ({service.name_en})",
        channel="phone call" if channel is Channel.VOICE else "web app",
        passages=format_passages(passages),
        history=format_history(history),
        question=question,
        max_words=MAX_SPEECH_WORDS,
        channel_rule=_VOICE_RULE if channel is Channel.VOICE else _APP_RULE,
        decision_note=DECISION_NOTE,
    )


# ---------------------------------------------------------------- grade (FR-AGT-06)

GRADE_PROMPT = """You check search results for a Bangla helpline about Bangladesh government services.
Citizen's question: {question}

Passages:
{passages}

Return the IDs of the passages that contain information useful for answering the question
(rules, eligibility, papers, fees, offices, steps or amounts on the same topic). Be generous:
partly useful counts. Return an empty list only when none of them is about the question."""

GRADE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"relevant_ids": {"type": "array", "items": {"type": "string"}}},
    "required": ["relevant_ids"],
}


def build_grade_prompt(question: str, passages: Sequence[Passage]) -> str:
    return GRADE_PROMPT.format(question=question, passages=format_passages(passages))


# ---------------------------------------------------------------- rewrite_query (FR-AGT-07)

REWRITE_PROMPT = """A search over official Bangla documents about "{service_name}" found nothing useful
for the citizen's question. Rewrite it as one clear, formal Bangla search query (the words an
official document would use), keeping the meaning. Use the conversation to fill in what a short
reply refers to. Previous query: {query}

Conversation so far:
{history}

Citizen's question: {question}

Return JSON with `query`."""

REWRITE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
}


def build_rewrite_prompt(question: str, query: str, service: Service, history: Sequence[Message]) -> str:
    return REWRITE_PROMPT.format(
        service_name=f"{service.name_bn} ({service.name_en})",
        query=query,
        history=format_history(history),
        question=question,
    )


# ---------------------------------------------------------------- verify (FR-AGT-10)

VERIFY_PROMPT = """You are a strict fact checker for a Bangla helpline about government services.
Check every numbered claim, and the spoken answer, against the official passages ONLY.
A claim is supported when a passage states the same fact (other wording is fine). Numbers,
ages, amounts and fees must have the same value; Bangla digits, English digits and numbers
written as words are the same (৬৫ = 65 = পঁয়ষট্টি). Repeating what the citizen said about
themselves (for example their age), conditional wording ("পুরুষ হলে ...") and general advice
such as "contact the office" or "the office decides" count as supported.

Passages:
{passages}

Claims:
{claims}

Spoken answer: {speech}

Return JSON: `claims` = one item per claim with its `index` and `supported` (true/false), and
`speech_supported` = false if the spoken answer states any fact the passages do not support."""

VERIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"index": {"type": "integer"}, "supported": {"type": "boolean"}},
                "required": ["index", "supported"],
            },
        },
        "speech_supported": {"type": "boolean"},
    },
    "required": ["claims", "speech_supported"],
}


def build_verify_prompt(claims: Sequence[str], speech: str, passages: Sequence[Passage]) -> str:
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(claims)) or "(none)"
    return VERIFY_PROMPT.format(passages=format_passages(passages), claims=numbered, speech=speech)
