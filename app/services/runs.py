import json
from dataclasses import dataclass
from time import time
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import QAResult, QARun
from app.repositories import page_by_id, write_session
from app.schemas import VERDICTS

LEASE_SECONDS = 30


@dataclass(frozen=True)
class Claim:
    id: int
    token: str
    scenarios: list[str]


def submit(engine, admin_id, scenarios):
    with write_session(engine) as session:
        run = QARun(requested_by=admin_id, selected_scenarios=json.dumps(scenarios), requested_at=int(time()))
        session.add(run)
        session.flush()
        return {"id": run.id, "status": run.status}


def run_data(run):
    return {
        "id": run.id, "status": run.status, "scenarios": json.loads(run.selected_scenarios),
        "requested_at": run.requested_at, "started_at": run.started_at,
        "finished_at": run.finished_at, "error_code": run.error_code,
    }


def metrics(session):
    base = select(QAResult.status, func.count(), func.sum(QAResult.duration_ms)).join(QARun, QARun.id == QAResult.run_id).where(QARun.status == "COMPLETED")
    rows = session.execute(base.group_by(QAResult.status)).all()
    counts = {status: 0 for status in VERDICTS}
    total_ms = 0
    for status, count, duration in rows:
        counts[status] = count
        total_ms += duration
    exceptions = dict(session.execute(base.with_only_columns(QAResult.status, func.count()).where(QAResult.scenario_id.like("TC-EX-%")).group_by(QAResult.status)).all())
    total = sum(counts.values())
    exception_total = sum(exceptions.values())
    return {
        "counts": counts, "pass_rate": counts["PASS"] / total if total else None,
        "mean_duration_ms": total_ms / total if total else None,
        "exception_pass_rate": exceptions.get("PASS", 0) / exception_total if exception_total else None,
    }


def list_runs(engine, before, limit):
    with Session(engine) as session:
        rows, next_before = page_by_id(session, select(QARun), QARun, before, limit)
        return {"runs": [run_data(row) for row in rows], "next_before": next_before, "metrics": metrics(session)}


def detail(engine, run_id):
    with Session(engine) as session:
        run = session.get(QARun, run_id)
        if run is None:
            raise ApiError(404, "RUN_NOT_FOUND", "실행을 찾을 수 없습니다.")
        results = session.scalars(select(QAResult).where(QAResult.run_id == run_id)).all()
        by_scenario = {row.scenario_id: row for row in results}
        data = {**run_data(run), "log_url": evidence_url(run_id, "log") if run.log_path else None, "results": []}
        for scenario in data["scenarios"]:
            row = by_scenario.get(scenario)
            if row:
                data["results"].append({
                    "scenario_id": scenario, "status": row.status, "duration_ms": row.duration_ms, "detail": row.detail,
                    "screenshot_url": evidence_url(run_id, scenario) if row.screenshot_path else None,
                })
        return data


def evidence_url(run_id, artifact):
    return f"/api/qa/runs/{run_id}/evidence/{artifact}"


def evidence_path(engine, root, run_id, artifact):
    with Session(engine) as session:
        if artifact == "log":
            stored_path = session.scalar(select(QARun.log_path).where(QARun.id == run_id))
            name = "worker.log"
        else:
            stored_path = session.scalar(select(QAResult.screenshot_path).where(QAResult.run_id == run_id, QAResult.scenario_id == artifact))
            name = f"{artifact}.png"
    if stored_path:
        path = (root / stored_path).resolve()
        if path.is_relative_to(root) and path.parent.parent == root and path.parent.name.startswith(f"run-{run_id}-") and path.name == name and path.is_file():
            return path
    raise ApiError(404, "EVIDENCE_NOT_FOUND", "증거 파일을 찾을 수 없습니다.")


def claim_next(engine, now=None):
    with write_session(engine) as session:
        now = int(time()) if now is None else now
        session.execute(update(QARun).where(QARun.status == "RUNNING", QARun.lease_expires_at <= now).values(
            status="FAILED", error_code="LEASE_EXPIRED", finished_at=now, lease_token=None, lease_expires_at=None,
        ))
        run = session.scalar(select(QARun).where(QARun.status == "PENDING").order_by(QARun.id).limit(1))
        if run is None:
            return None
        run.status = "RUNNING"
        run.started_at = run.heartbeat_at = max(now, run.requested_at)
        run.lease_expires_at = run.heartbeat_at + LEASE_SECONDS
        run.lease_token = uuid4().hex
        return Claim(run.id, run.lease_token, json.loads(run.selected_scenarios))


def active_claim(session, claim, now):
    return session.scalar(select(QARun).where(
        QARun.id == claim.id, QARun.status == "RUNNING", QARun.lease_token == claim.token, QARun.lease_expires_at > now,
    ))


def heartbeat(engine, claim, now=None):
    with write_session(engine) as session:
        now = int(time()) if now is None else now
        run = active_claim(session, claim, now)
        if run is None:
            return False
        run.heartbeat_at = max(now, run.heartbeat_at)
        run.lease_expires_at = run.heartbeat_at + LEASE_SECONDS
        return True


def finish(engine, claim, results, log_path=None, error_code=None, now=None):
    with write_session(engine) as session:
        now = int(time()) if now is None else now
        run = active_claim(session, claim, now)
        if run is None:
            return False
        for result in results:
            session.add(QAResult(run_id=run.id, **result))
        run.status = "FAILED" if error_code else "COMPLETED"
        run.error_code = error_code
        run.log_path = log_path
        run.finished_at = max(now, run.heartbeat_at)
        run.lease_token = run.lease_expires_at = None
        return True
