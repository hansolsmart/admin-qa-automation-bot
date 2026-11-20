from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import httpx
import pytest
from playwright.sync_api import expect

from qa.helpers import fill_item, read_items, record, sign_in


@pytest.mark.scenario("TC-EX-03")
def test_rapid_click_and_concurrent_requests(page, app_server, request):
    base, path = app_server
    sign_in(page, base)
    fill_item(page, "빠른 제출 버튼")
    button = page.get_by_role("button", name="항목 등록")
    expect(button).to_be_enabled()
    button.evaluate("button => { for (let i = 0; i < 10; i += 1) button.click(); }")
    expect(page.get_by_role("cell", name="빠른 제출 버튼")).to_be_visible()
    assert len(read_items(path)) == 1

    csrf = page.request.get(f"{base}/api/auth/me").json()["csrf_token"]
    cookies = {cookie["name"]: cookie["value"] for cookie in page.context.cookies()}
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": uuid4().hex}
    payload = {"name": "동시 등록 10건", "description": "고정된 등록 의도"}
    gate = Barrier(10, timeout=10)
    with httpx.Client(base_url=base, headers=headers, cookies=cookies, trust_env=False, timeout=12) as client:
        def send(_):
            gate.wait()
            return client.post("/api/items", json=payload)

        with ThreadPoolExecutor(max_workers=10) as pool:
            responses = list(pool.map(send, range(10)))
        codes = sorted(response.status_code for response in responses)
        ids = {response.json().get("id") for response in responses}
        count = sum(name == payload["name"] for _, name, _ in read_items(path))
        record(request, f"10 simultaneous requests: statuses={codes}, distinct IDs={len(ids)}, DB rows={count}")
        assert codes == [200] * 9 + [201] and len(ids) == count == 1
        assert client.post("/api/items", json={**payload, "name": "충돌 요청"}).status_code == 409
        independent = client.post("/api/items", json=payload, headers={"Idempotency-Key": uuid4().hex})
        assert independent.status_code == 201 and independent.json()["id"] not in ids
