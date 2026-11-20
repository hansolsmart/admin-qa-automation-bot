import pytest
from playwright.sync_api import expect

from qa.helpers import fill_item, read_items, record, sign_in


@pytest.mark.scenario("TC-N-01")
def test_login(page, app_server, request):
    base, _ = app_server
    sign_in(page, base)
    expect(page.get_by_role("button", name="로그아웃")).to_be_visible()
    assert page.request.get(f"{base}/api/auth/me").json()["username"] == "qa-operator"
    record(request, "Login and authenticated identity confirmed")


@pytest.mark.scenario("TC-N-02")
def test_create_item(page, app_server, request):
    base, path = app_server
    sign_in(page, base)
    fill_item(page, "분기 보고서", "관리자 등록 테스트")
    with page.expect_response(lambda response: response.url.endswith("/api/items") and response.request.method == "POST") as received:
        page.get_by_role("button", name="항목 등록").click()
    response = received.value
    assert response.status == 201
    expect(page.get_by_role("cell", name="분기 보고서")).to_be_visible()
    assert read_items(path) == [(response.json()["id"], "분기 보고서", "관리자 등록 테스트")]
    record(request, "HTTP 201, table visibility and one matching DB row verified")


@pytest.mark.scenario("TC-N-03")
def test_update_item(page, app_server, request):
    base, path = app_server
    sign_in(page, base)
    fill_item(page, "기존 항목")
    page.get_by_role("button", name="항목 등록").click()
    expect(page.get_by_role("cell", name="기존 항목")).to_be_visible()
    item_id = read_items(path)[0][0]
    page.get_by_role("button", name="수정").click()
    fill_item(page, "수정한 항목", "변경 사항")
    page.get_by_role("button", name="변경 저장").click()
    expect(page.get_by_role("cell", name="수정한 항목")).to_be_visible()
    assert read_items(path) == [(item_id, "수정한 항목", "변경 사항")]
    record(request, "Same item ID retained with updated values")
