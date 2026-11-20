import pytest
from playwright.sync_api import expect

from qa.helpers import fill_item, read_items, record, sign_in


@pytest.mark.scenario("TC-EX-02")
def test_special_characters_round_trip(page, app_server, request):
    base, path = app_server
    sign_in(page, base)
    name = '한글 O\'Reilly & <샘플> "원문"'
    description = "A < B & C > D | SELECT 항목"
    fill_item(page, name, description)
    with page.expect_response(lambda response: response.url.endswith("/api/items") and response.request.method == "POST") as received:
        page.get_by_role("button", name="항목 등록").click()
    result = received.value.json()
    cell = page.locator("tbody tr td:first-child").first
    expect(cell).to_be_visible()
    match_http = result["name"] == name and result["description"] == description
    match_db = read_items(path) == [(result["id"], name, description)]
    match_ui = cell.text_content() == name and page.get_by_role("cell", name=description).count() == 1
    record(request, f"Literal round trip equality: HTTP={match_http}, DB={match_db}, browser={match_ui}")
    assert match_http and match_db and match_ui
