import argparse
import getpass
import os
from pathlib import Path
from time import time

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.database import create_database_engine
from app.models import AdminUser
from app.repositories import write_session
from app.services.auth import hash_password

ROOT = Path(__file__).resolve().parents[1]


def migrate(path=None):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_path"] = path
    command.upgrade(config, "head")


def create_admin(path, username, password):
    username = username.strip().casefold()
    if not 1 <= len(username) <= 64 or "\x00" in username or not 12 <= len(password) <= 256:
        raise ValueError("사용자명은 1~64자, 비밀번호는 12~256자여야 합니다.")
    encoded = hash_password(password)
    engine = create_database_engine(path)
    try:
        with write_session(engine) as session:
            if session.scalar(select(AdminUser.id).where(AdminUser.username == username)) is not None:
                raise ValueError("이미 등록한 사용자명입니다.")
            session.add(AdminUser(username=username, password_hash=encoded, created_at=int(time())))
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    admin = commands.add_parser("create-admin")
    admin.add_argument("username")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    migrate()
    if args.command == "create-admin":
        password = os.environ.get("ADMIN_QA_PASSWORD") or getpass.getpass("관리자 비밀번호: ")
        try:
            create_admin(None, args.username, password)
        except ValueError as error:
            parser.error(str(error))
        print("관리자 계정을 생성했습니다.")
    elif args.command == "serve":
        uvicorn.run("app.main:app", host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    main()
