"""GET / DELETE /api/v1/conversations/{phone} (FR-APP-05, NFR-PRIV-03)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.application.use_cases.history import DeleteHistory, GetHistory
from app.interfaces.api.deps import get_delete_history, get_get_history
from app.interfaces.api.schemas import DeleteResponse, HistoryResponse

router = APIRouter(prefix="/api/v1", tags=["history"])


@router.get("/conversations/{phone}", summary="Messages and checklists for a phone number")
def get_history(
    phone: str,
    use_case: Annotated[GetHistory, Depends(get_get_history)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> HistoryResponse:
    return HistoryResponse.of(use_case.execute(phone, limit))


@router.delete("/conversations/{phone}", summary="Delete all history for a phone number")
def delete_history(
    phone: str, use_case: Annotated[DeleteHistory, Depends(get_delete_history)]
) -> DeleteResponse:
    return DeleteResponse(deleted=use_case.execute(phone))
