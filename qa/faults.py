"""Test-only failure baselines with no effect on normal app startup."""

import os
from uuid import uuid4


def active_fault():
    return os.environ.get("QA_DEMO_FAULT", "")


def configure_fault(monkeypatch, node):
    marker = node.get_closest_marker("scenario")
    fault = active_fault()
    if not marker or (fault, marker.args[0]) not in {("special", "TC-EX-02"), ("duplicate", "TC-EX-03")}:
        return

    from app.services import items

    original = items.register

    def degraded(engine, admin_id, key, payload):
        if fault == "special":
            payload = {**payload, "name": payload["name"].replace("<", "").replace(">", "")}
        else:
            key = uuid4().hex
        return original(engine, admin_id, key, payload)

    monkeypatch.setattr(items, "register", degraded)
