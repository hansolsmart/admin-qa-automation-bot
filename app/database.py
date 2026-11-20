import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL


def database_url(path: str | Path | None = None) -> URL:
    database = Path(path or os.environ.get("ADMIN_QA_DB_PATH", "data/admin_qa.sqlite3"))
    return URL.create("sqlite+pysqlite", database=str(database.resolve()))


def create_database_engine(path: str | Path | None = None) -> Engine:
    url = database_url(path)
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"timeout": 5})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record) -> None:
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA busy_timeout = 5000")
            if cursor.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                cursor.execute("PRAGMA journal_mode = WAL")
        finally:
            cursor.close()

    return engine
