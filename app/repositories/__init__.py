from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def write_session(engine):
    with Session(engine) as session, session.begin():
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        yield session


def page_by_id(session, query, model, before, limit):
    if before is not None:
        query = query.where(model.id < before)
    rows = session.scalars(query.order_by(model.id.desc()).limit(limit + 1)).all()
    return rows[:limit], rows[limit - 1].id if len(rows) > limit else None
