import os
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import expect

from qa.helpers import PASSWORD, USERNAME, read_items, sign_in


def test_dashboard_runs_worker_and_displays_evidence(page, app_server):
    base, path = app_server
    sign_in(page, base)
    page.get_by_role("link", name="QA 대시보드").click()
    with page.expect_response(lambda response: response.url.endswith("/api/qa/runs") and response.request.method == "POST") as received:
        page.get_by_role("button", name="QA 실행").click()
    response = received.value
    assert response.status == 202
    run_id = response.json()["id"]
    expect(page.get_by_role("button", name=f"실행 #{run_id}")).to_contain_text("PENDING")
    reports = path.parent / "reports"
    env = {**os.environ, "ADMIN_QA_DB_PATH": str(path), "ADMIN_QA_REPORT_DIR": str(reports), "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, "-m", "worker", "--once"], env=env, capture_output=True, encoding="utf-8", timeout=135, check=False)
    print(result.stdout)
    assert result.returncode == 0, result.stderr
    detail = page.request.get(f"{base}/api/qa/runs/{run_id}").json()
    assert detail["status"] == "COMPLETED", detail
    assert [row["status"] for row in detail["results"]] == ["PASS", "PASS", "PASS"], detail
    assert read_items(path) == []
    page.reload()
    page.get_by_role("button", name=f"실행 #{run_id}").click()
    result_panel = page.get_by_role("region", name="실행 상세")
    expect(result_panel).to_contain_text("COMPLETED")
    expect(result_panel.get_by_text("PASS", exact=True)).to_have_count(3)
    expect(result_panel.get_by_role("link", name="스크린샷")).to_have_count(3)
    assert page.request.get(base + detail["log_url"]).status == 200
    assert page.request.get(base + detail["results"][0]["screenshot_url"]).headers["content-type"] == "image/png"
    anonymous = page.context.browser.new_context()
    try:
        assert anonymous.request.get(base + detail["log_url"]).status == 401
    finally:
        anonymous.close()
    output = os.environ.get("QA_OUTPUT_DIR")
    if output:
        target = Path(output) / "dashboard"
        target.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=target / "dashboard.png")
        for directory in reports.iterdir():
            shutil.copytree(directory, target / directory.name, dirs_exist_ok=True)


def test_mobile_keyboard_flow(page, app_server):
    base, _ = app_server
    page.set_viewport_size({"width": 390, "height": 840})
    page.goto(base)
    page.keyboard.press("Tab")
    expect(page.get_by_label("사용자명")).to_be_focused()
    page.keyboard.type(USERNAME)
    page.keyboard.press("Tab")
    expect(page.get_by_label("비밀번호")).to_be_focused()
    page.keyboard.type(PASSWORD)
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", name="데이터 관리")).to_be_visible()
    expect(page.get_by_role("button", name="항목 등록")).to_be_visible()
    page.get_by_role("link", name="QA 대시보드").click()
    expect(page.get_by_role("button", name="QA 실행")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth === window.innerWidth")
