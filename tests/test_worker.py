import json
from concurrent.futures import ThreadPoolExecutor
from time import time

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.bootstrap import create_admin, migrate
from app.database import create_database_engine
from app.models import AdminUser, QAResult
from app.services import runs
from qa.helpers import PASSWORD, USERNAME
from worker.service import read_results


@pytest.fixture
def pending(tmp_path):
    path = tmp_path / "worker.sqlite3"
    migrate(path)
    create_admin(path, USERNAME, PASSWORD)
    engine = create_database_engine(path)
    with Session(engine) as session:
        admin_id = session.scalar(select(AdminUser.id))
    run_id = runs.submit(engine, admin_id, ["TC-N-01", "TC-N-02"])["id"]
    try:
        yield engine, run_id, admin_id
    finally:
        engine.dispose()


def test_only_one_worker_claims_and_expired_worker_cannot_finish(pending):
    engine, run_id, admin_id = pending
    now = int(time())
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: runs.claim_next(engine, now), range(4)))
    assert sum(claim is not None for claim in claims) == 1
    claim = next(claim for claim in claims if claim)
    assert runs.heartbeat(engine, claim, now + 10)
    assert not runs.finish(engine, claim, [], now=now + 40)
    assert runs.claim_next(engine, now + 40) is None
    expired = runs.detail(engine, run_id)
    assert (expired["status"], expired["error_code"], expired["results"]) == ("FAILED", "LEASE_EXPIRED", [])
    retry = runs.submit(engine, admin_id, claim.scenarios)
    assert retry["id"] != run_id and runs.claim_next(engine, now + 40).id == retry["id"]


def test_results_validation_screenshot_and_atomicity(tmp_path, pending):
    engine, run_id, _ = pending
    claim = runs.claim_next(engine)
    report = tmp_path / "results.json"
    first = {"scenario_id": "TC-N-01", "status": "PASS", "duration_ms": 75, "detail": "Verified", "screenshot": "TC-N-01.png"}
    second = {"scenario_id": "TC-N-02", "status": "FAIL", "duration_ms": 25, "detail": "Expected mismatch", "screenshot": None}

    def write_report(results):
        report.write_text(json.dumps({"run_id": str(run_id), "results": results}), encoding="utf-8")

    for malformed in ([first], [first, first], [{**first, "duration_ms": True}, second], [{**first, "screenshot": "../wrong.png"}, second]):
        write_report(malformed)
        with pytest.raises(ValueError):
            read_results(tmp_path, claim)
    write_report([first, second])
    (tmp_path / "TC-N-01.png").write_bytes(b"fixture")
    valid = read_results(tmp_path, claim)
    assert valid[0]["screenshot_path"].endswith("/TC-N-01.png")
    with pytest.raises(IntegrityError):
        runs.finish(engine, claim, [valid[0], valid[0]])
    with Session(engine) as session:
        assert session.scalars(select(QAResult)).all() == []
    assert runs.detail(engine, run_id)["status"] == "RUNNING"
    assert runs.finish(engine, claim, valid)
    detail = runs.detail(engine, run_id)
    assert detail["status"] == "COMPLETED" and [result["status"] for result in detail["results"]] == ["PASS", "FAIL"]
    counts = runs.list_runs(engine, None, 25)["metrics"]
    assert counts["counts"] == {"PASS": 1, "FAIL": 1, "ERROR": 0, "SKIPPED": 0}
    assert counts["pass_rate"] == 0.5 and counts["mean_duration_ms"] == 50
