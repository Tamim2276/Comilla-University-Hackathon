"""GET /api/v1/admin/stats and /api/v1/admin/questions (D2-R1: FR-ADM-01, 02, 05, SRS 8).

`require_admin_token` is the shared admin check: routers/clusters.py uses it too.
No ADMIN_TOKEN configured -> open (development); otherwise the X-Admin-Token header must match,
or the request gets 401 in the usual error JSON. Registered in main.py already.
"""

import hmac
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from app.application.use_cases.admin import AdminQuestion, AdminStats, GetAdminStats, ListQuestions
from app.domain.value_objects import AnswerStatus
from app.interfaces.api.deps import get_container


def require_admin_token(request: Request, x_admin_token: Annotated[str | None, Header()] = None) -> None:
    """FR-ADM-05: no ADMIN_TOKEN set -> open; otherwise the header must match (constant-time compare)."""
    expected = get_container(request).settings.admin_token.get_secret_value()
    if expected and not hmac.compare_digest(x_admin_token or "", expected):
        raise HTTPException(status_code=401, detail="Admin token missing or wrong.")


router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin_token)])


# ------------------------------------------------------------------ response models


class ServiceCountOut(BaseModel):
    id: str
    name_bn: str
    count: int


class AdminStatsOut(BaseModel):
    total_questions: int
    answered_pct: float
    fallback_pct: float
    avg_latency_ms: int
    calls_today: int
    by_service: list[ServiceCountOut]
    by_channel: dict[str, int]
    by_status: dict[str, int]

    @classmethod
    def of(cls, s: AdminStats) -> "AdminStatsOut":
        return cls(
            total_questions=s.total_questions,
            answered_pct=s.answered_pct,
            fallback_pct=s.fallback_pct,
            avg_latency_ms=s.avg_latency_ms,
            calls_today=s.calls_today,
            by_service=[
                ServiceCountOut(id=c.service_id, name_bn=c.name_bn, count=c.count) for c in s.by_service
            ],
            by_channel=dict(s.by_channel),
            by_status=dict(s.by_status),
        )


class AdminQuestionOut(BaseModel):
    text: str
    status: str
    channel: str
    service_id: str | None
    service_name_bn: str | None
    router: str | None
    latency_ms: int
    is_demo: bool
    created_at: datetime

    @classmethod
    def of(cls, q: AdminQuestion) -> "AdminQuestionOut":
        return cls(
            text=q.text,
            status=q.status.value,
            channel=q.channel.value,
            service_id=q.service_id,
            service_name_bn=q.service_name_bn,
            router=q.router_source.value if q.router_source else None,
            latency_ms=q.latency_ms,
            is_demo=q.is_demo,
            created_at=q.created_at,
        )


class AdminQuestionsOut(BaseModel):
    questions: list[AdminQuestionOut]


# ------------------------------------------------------------------ routes


def get_admin_stats(request: Request) -> GetAdminStats:
    return get_container(request).get_admin_stats


def get_list_questions(request: Request) -> ListQuestions:
    return get_container(request).list_questions


StatusFilter = Literal["answered", "follow_up", "fallback", "error"]


@router.get("/stats", summary="KPI numbers, questions per service and per channel, calls today")
def stats(use_case: Annotated[GetAdminStats, Depends(get_admin_stats)]) -> AdminStatsOut:
    return AdminStatsOut.of(use_case.execute())


@router.get("/questions", summary="Newest logged questions; ?status=fallback lists the unanswered ones")
def questions(
    use_case: Annotated[ListQuestions, Depends(get_list_questions)],
    status: Annotated[StatusFilter | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AdminQuestionsOut:
    rows = use_case.execute(AnswerStatus(status) if status else None, limit)
    return AdminQuestionsOut(questions=[AdminQuestionOut.of(q) for q in rows])
