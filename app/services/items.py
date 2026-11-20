import json
from hashlib import sha256
from time import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import AdminItem, IdempotencyRecord
from app.repositories import page_by_id, write_session


def item_data(item):
    return {"id": item.id, "name": item.name, "description": item.description, "created_at": item.created_at, "updated_at": item.updated_at}


def list_items(engine, before, limit):
    with Session(engine) as session:
        rows, next_before = page_by_id(session, select(AdminItem), AdminItem, before, limit)
        return {"items": [item_data(item) for item in rows], "next_before": next_before}


def register(engine, admin_id, key, payload):
    request_hash = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with write_session(engine) as session:
        record = session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.admin_id == admin_id, IdempotencyRecord.idempotency_key == key))
        if record:
            if record.request_hash != request_hash:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "이 등록 키는 다른 내용에 사용되었습니다.")
            return json.loads(record.response_json), False
        now = int(time())
        item = AdminItem(created_by=admin_id, created_at=now, updated_at=now, **payload)
        session.add(item)
        session.flush()
        response = item_data(item)
        session.add(IdempotencyRecord(
            admin_id=admin_id, item_id=item.id, idempotency_key=key, request_hash=request_hash,
            response_json=json.dumps(response, ensure_ascii=False), created_at=now,
        ))
        return response, True


def update(engine, item_id, changes):
    with write_session(engine) as session:
        item = session.get(AdminItem, item_id)
        if item is None:
            raise ApiError(404, "ITEM_NOT_FOUND", "항목을 찾을 수 없습니다.")
        for name, value in changes.items():
            setattr(item, name, value)
        item.updated_at = max(item.updated_at, int(time()))
        return item_data(item)
