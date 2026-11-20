from fastapi import APIRouter, Request, Response

from app.errors import ApiError
from app.routers.dependencies import CurrentUser, VerifiedUser
from app.schemas import LoginInput
from app.services import auth

router = APIRouter(prefix="/api/auth")


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response):
    if request.headers.get("content-type", "").partition(";")[0].lower() != "application/json":
        raise ApiError(415, "JSON_REQUIRED", "JSON 요청이 필요합니다.")
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise ApiError(403, "CSRF_REJECTED", "요청 출처를 확인할 수 없습니다.")
    user = auth.login(request.app.state.engine, payload.username, payload.password)
    response.set_cookie(auth.COOKIE_NAME, user.token, max_age=auth.SESSION_SECONDS, httponly=True, samesite="strict", secure=request.app.state.secure_cookie)
    return user.public()


@router.get("/me")
def me(user: CurrentUser):
    return user.public()


@router.post("/logout", status_code=204)
def logout(request: Request, user: VerifiedUser):
    auth.logout(request.app.state.engine, user)
    response = Response(status_code=204)
    response.delete_cookie(auth.COOKIE_NAME, httponly=True, samesite="strict", secure=request.app.state.secure_cookie)
    return response
