from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, Header, Request

from app.errors import ApiError
from app.services import auth


def identity(request: Request):
    user = auth.current_identity(request.app.state.engine, request.cookies.get(auth.COOKIE_NAME))
    if user is None:
        raise ApiError(401, "UNAUTHENTICATED", "로그인이 필요합니다.")
    return user


CurrentUser = Annotated[auth.Identity, Depends(identity)]


def verify_csrf(user: CurrentUser, x_csrf_token: Annotated[str | None, Header()] = None):
    if not x_csrf_token or not x_csrf_token.isascii() or not compare_digest(user.csrf_token, x_csrf_token):
        raise ApiError(403, "CSRF_REJECTED", "요청 검증에 실패했습니다.")
    return user


VerifiedUser = Annotated[auth.Identity, Depends(verify_csrf)]
