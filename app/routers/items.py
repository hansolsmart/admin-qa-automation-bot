from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request, Response

from app.routers.dependencies import CurrentUser, VerifiedUser
from app.schemas import ItemInput, ItemPatch
from app.services import items

router = APIRouter(prefix="/api/items")
Cursor = Annotated[int | None, Query(ge=1, le=2**63 - 1)]
Limit = Annotated[int, Query(ge=1, le=100)]
RecordId = Annotated[int, Path(ge=1, le=2**63 - 1)]
ItemKey = Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")]


@router.get("")
def list_items(request: Request, user: CurrentUser, before: Cursor = None, limit: Limit = 25):
    return items.list_items(request.app.state.engine, before, limit)


@router.post("", status_code=201, responses={200: {"description": "Replayed creation response"}})
def create_item(request: Request, response: Response, user: VerifiedUser, payload: ItemInput, idempotency_key: ItemKey):
    item, created = items.register(request.app.state.engine, user.admin_id, idempotency_key, payload.model_dump())
    if not created:
        response.status_code = 200
    return item


@router.patch("/{id}")
def update_item(id: RecordId, request: Request, user: VerifiedUser, payload: ItemPatch):
    return items.update(request.app.state.engine, id, payload.model_dump(exclude_unset=True))
