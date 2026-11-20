import json
import os
import socket
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from qa.helpers import PASSWORD, USERNAME


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        channel = os.environ.get("ADMIN_QA_BROWSER_CHANNEL") or None
        browser = playwright.chromium.launch(channel=channel)
        print(f"Browser: {browser.version}; channel={channel or 'bundled chromium'}")
        yield browser
        browser.close()


@pytest.fixture
def app_server(tmp_path, monkeypatch, request):
    from app import bootstrap
    from app.main import create_app

    from qa.faults import configure_fault

    path = tmp_path / "scenario.sqlite3"
    bootstrap.migrate(path)
    bootstrap.create_admin(path, USERNAME, PASSWORD)
    app = create_app(path, tmp_path / "reports")
    configure_fault(monkeypatch, request.node)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_config=None, log_level="warning"))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 8
            while not server.started and thread.is_alive() and monotonic() < deadline:
                sleep(0.025)
            assert server.started, "isolated loopback app failed to start"
            yield f"http://127.0.0.1:{port}", path
        finally:
            server.should_exit = True
            thread.join(timeout=6)
            assert not thread.is_alive(), "isolated loopback app failed to stop"


@pytest.fixture
def page(browser, request):
    context = browser.new_context(viewport={"width": 1240, "height": 860})
    page = context.new_page()
    page.set_default_timeout(5000)
    request.node.qa_page = page
    try:
        yield page
    finally:
        context.close()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    marker = item.get_closest_marker("scenario")
    if not marker or report.when == "setup" and report.passed:
        return report
    scenario_id = marker.args[0]
    records = getattr(item.config, "qa_records", {})
    item.config.qa_records = records
    if report.when == "teardown":
        if report.failed:
            records[scenario_id] = outcome(scenario_id, "ERROR", report, "Scenario cleanup failed")
        return report

    status = {"passed": "PASS", "failed": "FAIL" if report.when == "call" else "ERROR", "skipped": "SKIPPED"}[
        report.outcome
    ]
    detail = getattr(item, "qa_detail", None)
    if call.excinfo and not detail:
        detail = str(call.excinfo.value).splitlines()[0][:400]
    result = outcome(scenario_id, status, report, detail)
    output_dir = os.environ.get("QA_OUTPUT_DIR")
    browser_page = getattr(item, "qa_page", None)
    if output_dir and browser_page and report.when == "call" and not report.skipped:
        path = Path(output_dir) / f"{scenario_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            browser_page.screenshot(path=path, timeout=3000)
        except Exception as error:
            print(f"Screenshot unavailable for {scenario_id}: {type(error).__name__}")
        else:
            result["screenshot"] = path.name
    records[scenario_id] = result
    return report


def outcome(scenario_id, status, report, detail):
    return {
        "scenario_id": scenario_id,
        "status": status,
        "duration_ms": round(report.duration * 1000),
        "detail": detail,
        "screenshot": None,
    }


def pytest_sessionfinish(session, exitstatus):
    output_dir = os.environ.get("QA_OUTPUT_DIR")
    if output_dir:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        temporary = target / "results.tmp"
        results = list(getattr(session.config, "qa_records", {}).values())
        temporary.write_text(json.dumps({"run_id": os.environ.get("QA_RUN_ID"), "results": results}, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target / "results.json")
