from alembic import context

from app.database import create_database_engine, database_url
from app.models import Base


def run_migrations() -> None:
    config = context.config
    database_path = config.attributes.get("database_path")
    if context.is_offline_mode():
        context.configure(url=database_url(database_path), target_metadata=Base.metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_database_engine(database_path)
    try:
        with engine.connect() as connection:
            # Keep SQLite DDL and its Alembic revision marker in one transaction.
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()
            connection.commit()
    finally:
        engine.dispose()


run_migrations()
