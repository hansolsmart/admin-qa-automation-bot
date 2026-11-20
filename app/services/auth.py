from dataclasses import dataclass
from hashlib import scrypt, sha256
from hmac import compare_digest
from secrets import token_bytes, token_urlsafe
from time import time

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import AdminSession, AdminUser
from app.repositories import write_session

COOKIE_NAME = "admin_qa_session"
SESSION_SECONDS = 8 * 60 * 60
MAX_ATTEMPTS = 5
LOCK_SECONDS = 60
DUMMY_HASH = "00" * 16 + "$" + "00" * 64


@dataclass(frozen=True)
class Identity:
    admin_id: int
    username: str
    token: str

    @property
    def csrf_token(self):
        return sha256(f"csrf:{self.token}".encode()).hexdigest()

    def public(self):
        return {"username": self.username, "csrf_token": self.csrf_token}


def hash_password(password, salt=None):
    salt = salt if salt is not None else token_bytes(16)
    digest = scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def login(engine, username, password):
    now = int(time())
    failure = None
    identity = None
    with write_session(engine) as session:
        user = session.scalar(select(AdminUser).where(AdminUser.username == username.strip().casefold()))
        stored_hash = user.password_hash if user else DUMMY_HASH
        if user and user.login_locked_until and user.login_locked_until > now:
            failure = ApiError(429, "LOGIN_LIMITED", "잠시 후 다시 로그인해 주세요.")
        elif not compare_digest(hash_password(password, bytes.fromhex(stored_hash.split("$", 1)[0])), stored_hash) or user is None:
            failure = ApiError(401, "INVALID_CREDENTIALS", "사용자명 또는 비밀번호를 확인해 주세요.")
            if user:
                user.failed_login_count = 1 if user.login_locked_until else user.failed_login_count + 1
                user.login_locked_until = None
                if user.failed_login_count >= MAX_ATTEMPTS:
                    user.login_locked_until = now + LOCK_SECONDS
                    failure = ApiError(429, "LOGIN_LIMITED", "잠시 후 다시 로그인해 주세요.")
        else:
            user.failed_login_count = 0
            user.login_locked_until = None
            session.execute(delete(AdminSession).where(AdminSession.expires_at <= now))
            identity = Identity(user.id, user.username, token_urlsafe(32))
            session.add(AdminSession(token_hash=token_hash(identity.token), admin_id=user.id, created_at=now, expires_at=now + SESSION_SECONDS))
    if failure:
        raise failure
    return identity


def token_hash(token):
    return sha256(token.encode()).hexdigest()


def current_identity(engine, token):
    if token is None or len(token) != 43 or not token.isascii():
        return None
    with Session(engine) as session:
        user = session.scalar(
            select(AdminUser).join(AdminSession, AdminSession.admin_id == AdminUser.id)
            .where(AdminSession.token_hash == token_hash(token), AdminSession.expires_at > int(time()))
        )
        return Identity(user.id, user.username, token) if user else None


def logout(engine, identity):
    with write_session(engine) as session:
        session.execute(delete(AdminSession).where(AdminSession.token_hash == token_hash(identity.token)))
