import argparse
import json
import math
import os
import platform
import socket
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, perf_counter, sleep

import httpx
import uvicorn

from app.bootstrap import create_admin, migrate
from app.main import create_app
from qa.helpers import PASSWORD, USERNAME, read_items

REQUESTS = 40
CONCURRENCY = 4


@contextmanager
def app_endpoint(database, reports):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        app = create_app(database, reports)
        server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False, log_level="warning"))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        port = listener.getsockname()[1]
        thread.start()
        try:
            deadline = monotonic() + 10
            while not server.started and thread.is_alive() and monotonic() < deadline:
                sleep(0.02)
            if not server.started:
                raise RuntimeError("Benchmark server did not start")
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(timeout=8)


def load(client, method, count, concurrency, shared=False):
    def send(position):
        spec = {}
        if method == "POST":
            key = "shared" if shared else f"bench-{position}"
            spec = {"headers": {"Idempotency-Key": key}, "json": {"name": key}}
        start = perf_counter()
        response = client.request(method, "/api/items", **spec)
        return round((perf_counter() - start) * 1000, 2), response

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        pairs = list(pool.map(send, range(count)))
    durations, responses = zip(*pairs)
    p95 = sorted(durations)[math.ceil(0.95 * count) - 1]
    codes = [response.status_code for response in responses]
    locked = sum(response.status_code == 503 and response.json().get("error", {}).get("code") == "DB_BUSY" for response in responses)
    return {"requests": count, "concurrency": concurrency, "p95_ms": p95, "status_codes": codes, "db_busy": locked}


def worker_memory_mib(pid):
    try:
        if sys.platform == "win32":
            output = subprocess.check_output([
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                f"(Get-Process -Id {pid} -ErrorAction Stop).WorkingSet64",
            ], stderr=subprocess.DEVNULL, text=True, timeout=4)
            return round(int(output.strip()) / 1024**2, 2)
        status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
        rss = next(line for line in status.splitlines() if line.startswith("VmRSS:"))
        return round(int(rss.split()[1]) / 1024, 2)
    except (OSError, subprocess.SubprocessError, ValueError, StopIteration):
        return None


@contextmanager
def worker_process(database, reports, log_path):
    env = {**os.environ, "ADMIN_QA_DB_PATH": str(database), "ADMIN_QA_REPORT_DIR": str(reports), "PYTHONIOENCODING": "utf-8"}
    with log_path.open("wb") as log:
        worker = subprocess.Popen([sys.executable, "-m", "worker"], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            sleep(0.7)
            if worker.poll() is not None:
                raise RuntimeError("Benchmark worker did not start")
            yield worker
        finally:
            worker.terminate()
            worker.wait(timeout=8)


def queue_benchmark(client, worker):
    response = client.post("/api/qa/runs", json={"scenarios": ["TC-N-01", "TC-N-02", "TC-N-03"]})
    response.raise_for_status()
    run_id = response.json()["id"]
    samples = []
    deadline = monotonic() + 130
    while monotonic() < deadline and worker.poll() is None:
        result = client.get(f"/api/qa/runs/{run_id}").json()
        if result["status"] in {"COMPLETED", "FAILED"}:
            verdicts = [entry["status"] for entry in result["results"]]
            return {
                "run_id": run_id, "run_status": result["status"], "verdicts": verdicts,
                "queue_seconds": result["started_at"] - result["requested_at"],
                "execution_seconds": result["finished_at"] - result["started_at"],
                "worker_rss_samples_mib": samples, "worker_rss_max_mib": max(samples, default=None),
            }
        if result["status"] == "RUNNING":
            memory = worker_memory_mib(worker.pid)
            if memory is not None:
                samples.append(memory)
        sleep(0.25)
    raise RuntimeError("Worker benchmark timed out")


def benchmark(output):
    output.mkdir(parents=True, exist_ok=True)
    reports = (output / "worker-evidence").resolve()
    with TemporaryDirectory(prefix="admin-qa-benchmark-") as temporary:
        database = Path(temporary) / "load.sqlite3"
        migrate(database)
        create_admin(database, USERNAME, PASSWORD)
        with (
            app_endpoint(database, reports) as base,
            httpx.Client(base_url=base, trust_env=False, timeout=10) as client,
            worker_process(database, reports, output / "worker.log") as worker,
        ):
            credentials = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
            credentials.raise_for_status()
            client.headers["X-CSRF-Token"] = credentials.json()["csrf_token"]
            client.get("/api/items").raise_for_status()
            reads = load(client, "GET", REQUESTS, CONCURRENCY)
            writes = load(client, "POST", REQUESTS, CONCURRENCY)
            replay = load(client, "POST", 10, 10, shared=True)
            shared_rows = sum(name == "shared" for _, name, _ in read_items(database))
            queue = queue_benchmark(client, worker)
    busy = reads["db_busy"] + writes["db_busy"] + replay["db_busy"]
    budgets = {
        "read_p95": reads["p95_ms"] < 500 and set(reads["status_codes"]) == {200},
        "write_p95": writes["p95_ms"] < 500 and set(writes["status_codes"]) == {201},
        "data_integrity": busy == 0 and shared_rows == 1 and sorted(replay["status_codes"]) == [200] * 9 + [201],
        "queue_wait": queue["queue_seconds"] < 5,
        "execution": queue["run_status"] == "COMPLETED" and queue["verdicts"] == ["PASS"] * 3 and queue["execution_seconds"] < 120,
        "memory_sampled": queue["worker_rss_max_mib"] is not None,
    }
    result = {
        "platform": platform.platform(), "logical_processors": os.cpu_count(), "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "playwright": version("playwright"), "browser_channel": os.environ.get("ADMIN_QA_BROWSER_CHANNEL", "bundled chromium"),
        "reads": reads, "writes": writes, "shared_key": replay, "shared_key_rows": shared_rows,
        "queue": queue, "budgets": budgets,
    }
    (output / "benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Benchmark gates: " + json.dumps(budgets), flush=True)
    return all(budgets.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path, help="Directory for benchmark JSON and QA evidence")
    args = parser.parse_args()
    return 0 if benchmark(args.output) else 1


if __name__ == "__main__":
    raise SystemExit(main())
