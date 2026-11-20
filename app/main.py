import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter, time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.database import create_database_engine
from app.errors import ApiError
from app.models import AdminUser
from app.routers import auth, items, runs
from app.schemas import SCENARIOS
from app.services.auth import COOKIE_NAME, current_identity

ROOT = Path(__file__).resolve().parent


def create_app(db_path=None, report_dir=None, secure_cookie=False):
    @asynccontextmanager
    async def lifespan(application):
        yield
        application.state.engine.dispose()

    app = FastAPI(title="Admin QA Automation Bot", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.engine = create_database_engine(db_path)
    app.state.reports = Path(report_dir or os.environ.get("ADMIN_QA_REPORT_DIR", "reports")).resolve()
    app.state.secure_cookie = secure_cookie
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")
    for router in (auth.router, items.router, runs.router):
        app.include_router(router)

    def failure(request, error):
        request.state.error_code = error.code
        return JSONResponse({"error": {"code": error.code, "message": error.message}, "request_id": request.state.request_id}, status_code=error.status)

    @app.exception_handler(ApiError)
    async def app_error(request, error):
        return failure(request, error)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        return failure(request, ApiError(422, "VALIDATION_ERROR", "입력 형식과 길이를 확인해 주세요."))

    @app.exception_handler(OperationalError)
    async def database_error(request, error):
        code = getattr(error.orig, "sqlite_errorcode", 0) & 0xFF
        reason = "DB_BUSY" if code in {5, 6} else "DB_UNAVAILABLE"
        return failure(request, ApiError(503, reason, "잠시 후 다시 시도해 주세요."))

    @app.middleware("http")
    async def log_request(request, call_next):
        request.state.request_id = uuid4().hex
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception as error:
            request.state.error_type = type(error).__name__
            response = failure(request, ApiError(500, "INTERNAL_ERROR", "요청을 처리할 수 없습니다."))
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        route = getattr(request.scope.get("route"), "path", "unmatched")
        print(json.dumps({
            "time": int(time()), "event": "http", "request_id": request.state.request_id, "method": request.method,
            "route": route, "status": response.status_code, "duration_ms": round((perf_counter() - started) * 1000, 1),
            "run_id": getattr(request.state, "run_id", None), "error_code": getattr(request.state, "error_code", None),
            "error_type": getattr(request.state, "error_type", None),
        }), flush=True)
        return response

    @app.get("/health")
    def health():
        with app.state.engine.connect() as connection:
            connection.execute(select(AdminUser.id).limit(1))
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def login_page(request: Request):
        if current_identity(app.state.engine, request.cookies.get(COOKIE_NAME)):
            return RedirectResponse("/items", status_code=303)
        return templates.TemplateResponse(request, "login.html")

    @app.get("/items", include_in_schema=False)
    @app.get("/qa", include_in_schema=False)
    def protected_page(request: Request):
        user = current_identity(app.state.engine, request.cookies.get(COOKIE_NAME))
        if user is None:
            return RedirectResponse("/", status_code=303)
        page = "items" if request.url.path == "/items" else "qa"
        return templates.TemplateResponse(request, f"{page}.html", {"page": page, "username": user.username, "scenarios": SCENARIOS})

    return app


app = create_app(secure_cookie=os.environ.get("ADMIN_QA_SECURE_COOKIE") == "1")
