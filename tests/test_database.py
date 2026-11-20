from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import create_database_engine
from app.models import AdminItem, AdminSession, AdminUser, Base, IdempotencyRecord, QAResult, QARun


def migration_config(path):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_path"] = path
    return config


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "admin.sqlite3"
    command.upgrade(migration_config(path), "head")
    engine = create_database_engine(path)
    try:
        yield engine
    finally:
        engine.dispose()


def admin(username="qa"):
    return AdminUser(username=username, password_hash="fixture-only", created_at=1)


def item(admin_id, name="QA 항목"):
    return AdminItem(created_by=admin_id, name=name, created_at=1, updated_at=1)


def registration(admin_id, item_id, key="fixture-key"):
    return IdempotencyRecord(
        admin_id=admin_id,
        item_id=item_id,
        idempotency_key=key,
        request_hash="a" * 64,
        response_json="{}",
        created_at=1,
    )


def test_migration_up_check_down_and_up(tmp_path):
    path = tmp_path / "lifecycle.sqlite3"
    config = migration_config(path)
    engine = create_database_engine(path)
    try:
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        command.check(config)
        assert set(inspect(engine).get_table_names()) == {*Base.metadata.tables, "alembic_version"}
        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0001"
    finally:
        engine.dispose()


def test_connection_enforces_foreign_keys_and_uses_wal(database):
    with database.connect() as first, database.connect() as second:
        for connection in (first, second):
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 5000

    with pytest.raises(IntegrityError, match="FOREIGN KEY"), Session(database) as session, session.begin():
        session.add(item(99))


def test_database_rejects_whitespace_name_and_invalid_expiry(database):
    with Session(database) as session, session.begin():
        user = admin()
        session.add(user)
        session.flush()
        admin_id = user.id

    with pytest.raises(IntegrityError, match="ck_admin_item_name"), Session(database) as session, session.begin():
        session.add(item(admin_id, "   "))

    with pytest.raises(IntegrityError, match="ck_session_expiry"), Session(database) as session, session.begin():
        session.add(AdminSession(token_hash="b" * 64, admin_id=admin_id, created_at=2, expires_at=1))


def test_duplicate_registration_rolls_back_the_new_item(database):
    with Session(database) as session, session.begin():
        owner = admin()
        other = admin("qa-other")
        session.add_all([owner, other])
        session.flush()
        owner_id, other_id = owner.id, other.id
        created = item(owner_id, "원본")
        session.add(created)
        session.flush()
        session.add(registration(owner_id, created.id))

    with pytest.raises(IntegrityError, match="UNIQUE"), Session(database) as session, session.begin():
        duplicate = item(owner_id, "롤백 대상")
        session.add(duplicate)
        session.flush()
        session.add(registration(owner_id, duplicate.id))

    with Session(database) as session, session.begin():
        assert session.scalars(select(AdminItem.name)).all() == ["원본"]
        independent = item(other_id, "별도 관리자")
        session.add(independent)
        session.flush()
        session.add(registration(other_id, independent.id))


def test_run_states_and_verdicts_use_separate_constraints(database):
    with Session(database) as session, session.begin():
        user = admin()
        session.add(user)
        session.flush()
        admin_id = user.id
        run = QARun(requested_by=admin_id, selected_scenarios='["TC-N-01"]', requested_at=1)
        session.add(run)
        session.flush()
        assert run.status == "PENDING"
        run.status = "RUNNING"
        run.started_at = run.heartbeat_at = 2
        run.lease_token = "fixture-lease"
        run.lease_expires_at = 5
        session.flush()
        run.status = "COMPLETED"
        run.finished_at = 3
        run.lease_token = run.lease_expires_at = None
        run_id = run.id
        session.add(QAResult(run_id=run_id, scenario_id="TC-N-01", status="FAIL", duration_ms=25))

    with pytest.raises(IntegrityError, match="ck_qa_run_status"), Session(database) as session, session.begin():
        session.add(QARun(
            requested_by=admin_id,
            selected_scenarios='["TC-N-01"]',
            requested_at=1,
            started_at=2,
            status="PASS",
        ))

    with pytest.raises(IntegrityError, match="ck_qa_result_status"), Session(database) as session, session.begin():
        session.add(QAResult(run_id=run_id, scenario_id="TC-N-02", status="COMPLETED", duration_ms=25))

    with pytest.raises(IntegrityError, match="UNIQUE"), Session(database) as session, session.begin():
        session.add(QAResult(run_id=run_id, scenario_id="TC-N-01", status="PASS", duration_ms=25))


def test_run_databases_are_isolated(database, tmp_path):
    path = tmp_path / "qa" / "test-run.sqlite3"
    command.upgrade(migration_config(path), "head")
    isolated = create_database_engine(path)
    try:
        with Session(isolated) as session, session.begin():
            session.add(admin())
        with Session(database) as session:
            assert session.scalars(select(AdminUser)).all() == []
    finally:
        isolated.dispose()
