from uuid import uuid4

import pytest
from playwright.sync_api import expect

from qa.faults import active_fault
from qa.helpers import fill_item, read_items, record, sign_in


@pytest.mark.scenario("TC-EX-01")
def test_committed_registration_after_response_loss(page, app_server, request):
    base, path = app_server
    sign_in(page, base)
    keys = []
    first = {}

    def disconnect_once(route):
        if route.request.method != "POST":
            route.continue_()
            return
        headers = route.request.all_headers()
        if keys and active_fault() == "network":
            headers["idempotency-key"] = uuid4().hex
        keys.append(headers["idempotency-key"])
        if len(keys) == 1:
            result = route.fetch()
            first.update(status=result.status, id=result.json().get("id"))
            route.abort("connectionreset")
        else:
            route.continue_(headers=headers)

    page.route("**/api/items", disconnect_once)
    fill_item(page, "응답 단절 확인")
    page.get_by_role("button", name="항목 등록").click()
    expect(page.get_by_role("status")).to_contain_text("같은 내용으로 다시 시도")
    assert first["status"] == 201 and read_items(path) == [(first["id"], "응답 단절 확인", "")]
    with page.expect_response(lambda response: response.url.endswith("/api/items") and response.request.method == "POST") as received:
        page.get_by_role("button", name="항목 등록").click()
    replay = received.value
    expect(page.get_by_role("cell", name="응답 단절 확인").first).to_be_visible()
    rows = read_items(path)
    record(request, f"First HTTP {first['status']} aborted at browser; retry HTTP {replay.status}; same_key={keys[0] == keys[1]}; DB rows={len(rows)}")
    assert replay.status == 200 and keys[0] == keys[1] and replay.json()["id"] == first["id"] and len(rows) == 1
