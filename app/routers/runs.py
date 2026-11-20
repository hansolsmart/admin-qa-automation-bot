from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.routers.dependencies import CurrentUser, VerifiedUser
from app.routers.items import Cursor, Limit, RecordId
from app.schemas import QARunInput, Scenario
from app.services import runs

router = APIRouter(prefix="/api/qa/runs")


@router.post("", status_code=202)
def submit_run(request: Request, user: VerifiedUser, payload: QARunInput):
    result = runs.submit(request.app.state.engine, user.admin_id, payload.scenarios)
    request.state.run_id = result["id"]
    return result


@router.get("")
def list_runs(request: Request, user: CurrentUser, before: Cursor = None, limit: Limit = 25):
    return runs.list_runs(request.app.state.engine, before, limit)


@router.get("/{id}")
def get_run(id: RecordId, request: Request, user: CurrentUser):
    request.state.run_id = id
    return runs.detail(request.app.state.engine, id)


@router.get("/{id}/evidence/{artifact}")
def evidence(id: RecordId, artifact: Literal["log"] | Scenario, request: Request, user: CurrentUser):
    request.state.run_id = id
    path = runs.evidence_path(request.app.state.engine, request.app.state.reports, id, artifact)
    return FileResponse(path, media_type="text/plain" if artifact == "log" else "image/png", filename=path.name, content_disposition_type="inline")
