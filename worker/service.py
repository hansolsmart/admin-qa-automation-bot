import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from time import monotonic, time

from app.schemas import SCENARIOS, VERDICTS
from app.services import runs

HEARTBEAT_SECONDS = 5
TEST_TIMEOUT_SECONDS = 120
ROOT = Path(__file__).resolve().parents[1]


def read_results(directory, claim):
    path = directory / "results.json"
    if path.stat().st_size > 64_000:
        raise ValueError("Result file exceeds expected size")
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(envelope, dict) or envelope.get("run_id") != str(claim.id):
        raise ValueError("Wrong result run ID")
    raw = envelope.get("results")
    if not isinstance(raw, list) or len(raw) != len(claim.scenarios):
        raise ValueError("Missing or additional scenario results")
    remaining = set(claim.scenarios)
    results = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("Invalid result entry")
        scenario, status = entry.get("scenario_id"), entry.get("status")
        duration, detail, screenshot = entry.get("duration_ms"), entry.get("detail"), entry.get("screenshot")
        if not isinstance(scenario, str) or scenario not in remaining or status not in VERDICTS:
            raise ValueError("Invalid or duplicate result")
        if type(duration) is not int or not 0 <= duration <= TEST_TIMEOUT_SECONDS * 1000:
            raise ValueError("Invalid test duration")
        if detail is not None and (not isinstance(detail, str) or len(detail) > 400):
            raise ValueError("Invalid result detail")
        screenshot_path = None
        if screenshot is not None:
            if screenshot != f"{scenario}.png":
                raise ValueError("Invalid screenshot name")
            candidate = (directory / screenshot).resolve()
            if candidate.parent != directory:
                raise ValueError("Invalid screenshot path")
            if candidate.is_file():
                screenshot_path = f"{directory.name}/{screenshot}"
        remaining.remove(scenario)
        results.append({
            "scenario_id": scenario, "status": status, "duration_ms": duration,
            "detail": detail, "screenshot_path": screenshot_path,
        })
    return results


def log_event(event, claim=None, **fields):
    print(json.dumps({"time": int(time()), "event": event, "run_id": claim.id if claim else None, **fields}), flush=True)


def stop_process(process):
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False, timeout=8)
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=8)


def run_claim(engine, report_root, claim):
    directory = (report_root / f"run-{claim.id}-{claim.token[:12]}").resolve()
    try:
        directory.mkdir(parents=True, exist_ok=False)
        log_path = directory / "worker.log"
        log_file = log_path.open("wb")
    except OSError:
        runs.finish(engine, claim, [], error_code="REPORT_UNAVAILABLE")
        log_event("run_finished", claim, status="FAILED", error_code="REPORT_UNAVAILABLE")
        return

    log_event("run_claimed", claim, status="RUNNING", scenarios=claim.scenarios)
    env = {**os.environ, "QA_OUTPUT_DIR": str(directory), "QA_RUN_ID": str(claim.id), "PYTHONIOENCODING": "utf-8", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    env["QA_DEMO_FAULT"] = "fixed"
    env.pop("PYTEST_ADDOPTS", None)
    command = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-s", "--tb=short"]
    command.extend(SCENARIOS[scenario][1] for scenario in claim.scenarios)
    error_code = None
    results = []
    with log_file:
        try:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=sys.platform != "win32")
        except OSError:
            error_code = "TEST_START_FAILED"
        else:
            deadline = monotonic() + TEST_TIMEOUT_SECONDS
            try:
                while True:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        error_code = "TEST_TIMEOUT"
                        break
                    try:
                        exit_code = process.wait(timeout=min(HEARTBEAT_SECONDS, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        if not runs.heartbeat(engine, claim):
                            log_event("lease_lost", claim)
                            return
            finally:
                stop_process(process)
            if error_code is None:
                try:
                    if exit_code not in {0, 1}:
                        raise ValueError(f"Unexpected pytest exit code {exit_code}")
                    results = read_results(directory, claim)
                except (OSError, ValueError, UnicodeError) as error:
                    error_code = "INVALID_RESULTS"
                    log_event("collection_error", claim, error_type=type(error).__name__)

    relative_log = f"{directory.name}/{log_path.name}"
    if runs.finish(engine, claim, results, relative_log, error_code):
        log_event("run_finished", claim, status="FAILED" if error_code else "COMPLETED", error_code=error_code)
    else:
        log_event("lease_lost", claim)
