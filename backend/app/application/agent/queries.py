"""Query expansion for retrieval (sprint T4, FR-AGT-20). Pure functions: domain + stdlib only.

Callers say "স্বামী মারা গেছেন"; the documents say "বিধবা". So each service is searched with
(a) the caller's words, (b) the service's official words from services.yaml and (c) the query
`understand` wrote, and the results are merged round-robin (see merge_best).
"""

from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar

from app.domain.entities import Service


class _Scored(Protocol):
    @property
    def chunk_id(self) -> str: ...

    @property
    def score(self) -> float: ...


P = TypeVar("P", bound=_Scored)


def build_queries(question: str, service: Service, llm_query: str = "", expansion: bool = True) -> list[str]:
    """[question, llm_query, "<name> <official words>"] without empty or repeated ones, in the
    order merge_best takes their hits: the caller's words first, the broad bag of words last.

    With expansion off only the caller's words are searched (the old behaviour).
    """
    if not expansion:
        return [question.strip()] if question.strip() else []
    official = f"{service.name_bn} {service.search_terms_bn}".strip()
    queries: list[str] = []
    for raw in (question, llm_query, official):
        query = " ".join((raw or "").split())
        if query and query.casefold() not in {q.casefold() for q in queries}:
            queries.append(query)
    return queries


def merge_best(results: Iterable[Sequence[P]], k: int) -> list[P]:
    """At most `k` chunks, round-robin: every query's 1st hit (in query order), then every 2nd hit...

    Raw scores are not compared across queries, and agreement between queries is not rewarded:
    a bag of official words and a broad query both touch generic passages (definitions, payment
    method), which would otherwise push out the caller's own best hit. Each chunk appears once,
    with its best raw score.
    """
    lists = [list(found) for found in results]
    best: dict[str, P] = {}
    for found in lists:
        for passage in found:
            kept = best.get(passage.chunk_id)
            if kept is None or passage.score > kept.score:
                best[passage.chunk_id] = passage
    order: list[str] = []
    for rank in range(max((len(found) for found in lists), default=0)):
        for found in lists:
            if rank < len(found) and found[rank].chunk_id not in order:
                order.append(found[rank].chunk_id)
    return [best[cid] for cid in order[:k]]
