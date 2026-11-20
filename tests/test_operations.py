import sqlite3
from contextlib import closing

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bootstrap import create_admin, migrate
from app.database import create_database_engine
from app.models import AdminItem, AdminUser
from app.services import items
from qa.helpers import PASSWORD, USERNAME
from scripts.db_snapshot import snapshot


def test_live_backup_new_path_restore_and_no_overwrite(tmp_path):
    original = tmp_path / "운영.sqlite3"
    backup = tmp_path / "backup" / "snapshot.sqlite3"
    restored = tmp_path / "restore" / "verified.sqlite3"
    migrate(original)
    create_admin(original, USERNAME, PASSWORD)
    engine = create_database_engine(original)
    try:
        with Session(engine) as session:
            admin_id = session.scalar(select(AdminUser.id))
        payload = {"name": "백업 대상", "description": "원문 <&>"}
        before, created = items.register(engine, admin_id, "snapshot-test", payload)
        assert created
        snapshot(original, backup)
        items.update(engine, before["id"], {"name": "백업 이후 변경"})
        snapshot(backup, restored)
        with pytest.raises(FileExistsError):
            snapshot(original, restored)
        with closing(sqlite3.connect(restored)) as copy:
            assert copy.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert copy.execute("SELECT version_num FROM alembic_version").fetchone() == ("0001",)
        recovered_engine = create_database_engine(restored)
        try:
            with Session(recovered_engine) as session:
                assert session.scalar(select(AdminItem.name)) == payload["name"]
            assert items.register(recovered_engine, admin_id, "snapshot-test", payload) == (before, False)
        finally:
            recovered_engine.dispose()
    finally:
        engine.dispose()
