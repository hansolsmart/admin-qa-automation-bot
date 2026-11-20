import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bootstrap import create_admin, migrate
from app.main import create_app
from app.models import AdminSession, AdminUser
from app.services.auth import COOKIE_NAME
from qa.helpers import PASSWORD, USERNAME


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "api.sqlite3"
    migrate(path)
    create_admin(path, USERNAME, PASSWORD)
    app = create_app(path, tmp_path / "reports")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client


def login(client):
    response = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_authentication_logout_and_csrf(client):
    assert client.get("/health").json() == {"status": "ok"}
    anon = client.get("/api/items")
    assert anon.status_code == 401
    assert anon.headers["x-request-id"] == anon.json()["request_id"]
    assert client.get("/items", follow_redirects=False).headers["location"] == "/"
    headers = login(client)
    assert client.get("/api/auth/me").json()["username"] == USERNAME
    capture = client.cookies.get(COOKIE_NAME)
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers={"Cookie": f"{COOKIE_NAME}={capture}"}).status_code == 401
    assert client.get("/qa", follow_redirects=False).status_code == 303


def test_login_cookie_throttle_and_redaction(client, capsys):
    invalid_origin = client.post("/api/auth/login", headers={"Origin": "https://example.invalid"}, json={"username": USERNAME, "password": PASSWORD})
    assert invalid_origin.status_code == 403
    result = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    cookie = result.headers["set-cookie"].lower()
    assert all(value in cookie for value in ("httponly", "samesite=strict", "max-age=28800"))
    raw_token = client.cookies.get(COOKIE_NAME)
    csrf = result.json()["csrf_token"]
    with Session(client.app.state.engine) as session:
        account = session.scalar(select(AdminUser))
        assert PASSWORD not in account.password_hash and "$" in account.password_hash
        assert session.scalar(select(AdminSession.token_hash)) != raw_token
    credential = "redaction-probe"
    denied = [client.post("/api/auth/login", json={"username": USERNAME, "password": credential}) for _ in range(5)]
    assert [response.status_code for response in denied] == [401, 401, 401, 401, 429]
    assert client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD}).status_code == 429
    invalid = client.post("/api/auth/login", json={"username": USERNAME, "password": [credential]})
    assert invalid.status_code == 422 and credential not in invalid.text
    logs = capsys.readouterr().out
    assert all(secret not in logs for secret in (raw_token, PASSWORD, credential, csrf))
    assert any(json.loads(line)["error_code"] == "LOGIN_LIMITED" for line in logs.splitlines())


def test_secure_cookie(tmp_path):
    path = tmp_path / "secure.sqlite3"
    migrate(path)
    create_admin(path, USERNAME, PASSWORD)
    with TestClient(create_app(path, secure_cookie=True), base_url="https://localhost") as client:
        result = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
        assert "Secure" in result.headers["set-cookie"]
        assert client.get("/api/auth/me").status_code == 200


def test_item_validation_pagination_and_original_replay(client):
    headers = login(client)
    key = {**headers, "Idempotency-Key": "first-record"}
    body = {"name": " '원문' <&> ", "description": "설명"}
    assert client.post("/api/items", json=body).status_code == 403
    assert client.post("/api/items", headers=headers, json=body).status_code == 422
    assert client.post("/api/items", headers=key, json={"name": "\t "}).status_code == 422
    first = client.post("/api/items", headers=key, json=body)
    assert first.status_code == 201
    id = first.json()["id"]
    assert client.patch(f"/api/items/{id}", headers=headers, json={}).status_code == 422
    assert client.patch(f"/api/items/{id}", headers=headers, json={"name": None}).status_code == 422
    assert client.patch("/api/items/999", headers=headers, json={"name": "absent"}).status_code == 404
    assert client.patch(f"/api/items/{id}", headers=headers, json={"name": "수정"}).json()["name"] == "수정"
    replay = client.post("/api/items", headers=key, json=body)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert client.post("/api/items", headers=key, json={"name": "collision"}).status_code == 409
    second = client.post("/api/items", headers={**headers, "Idempotency-Key": uuid4().hex}, json={"name": "second"}).json()
    page = client.get("/api/items?limit=1").json()
    assert page["items"][0]["id"] == page["next_before"] == second["id"]
    next_page = client.get(f"/api/items?before={page['next_before']}&limit=1").json()
    assert next_page["items"][0]["id"] == id and next_page["next_before"] is None


def test_run_validation_and_api_spec_paths(client):
    headers = login(client)
    for bad in ([], ["TC-N-01", "TC-N-01"], ["unknown"]):
        assert client.post("/api/qa/runs", headers=headers, json={"scenarios": bad}).status_code == 422
    response = client.post("/api/qa/runs", headers=headers, json={"scenarios": ["TC-N-01"]})
    assert response.status_code == 202 and response.json()["status"] == "PENDING"
    run = response.json()["id"]
    assert client.get(f"/api/qa/runs/{run}").json()["results"] == []
    assert client.get(f"/api/qa/runs/{run}/evidence/log").status_code == 404
    assert client.get("/api/qa/runs/999").status_code == 404
    assert client.get("/api/qa/runs").json()["metrics"]["pass_rate"] is None
    spec = Path("docs/06_api_spec.md").read_text(encoding="utf-8")
    for path, actions in client.app.openapi()["paths"].items():
        for method in actions:
            assert f"| {method.upper()} | `{path}` |" in spec
