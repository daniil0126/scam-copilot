"""Live check of the background monitor against a RUNNING backend and the PayPal Sandbox.

    .venv/bin/uvicorn app.main:app --port 8000        # in another terminal, without --reload
    .venv/bin/python scripts/live_monitor_check.py    # BASE_URL=http://localhost:8000 by default

Creates one draft invoice in the Sandbox (the only write; the backend allows it in sandbox mode only), then checks:
it appears once after a sync, a second sync adds nothing, pause blocks /monitoring/sync, resume brings it back.
Exits with 1 if any step fails.
"""
import os
import sys
import time
import uuid

import httpx

BASE = os.getenv("BASE_URL", "http://localhost:8000")
RECIPIENT = os.getenv("SANDBOX_RECIPIENT", "sb-kckt753313725@personal.example.com")
TIMEOUT = float(os.getenv("CHECK_TIMEOUT_SECONDS", "180"))

failures = 0


def step(ok: bool, text: str) -> None:
    global failures
    failures += not ok
    print(("PASS " if ok else "FAIL ") + text)


def monitoring(api: httpx.Client) -> dict:
    return api.get("/monitoring").json()


def sync_and_wait(api: httpx.Client, since: str | None) -> dict:
    """Starts a pass and waits until `lastSuccessfulSyncAt` moves past `since`, or the state turns ERROR."""
    r = api.post("/monitoring/sync")
    if r.status_code != 200:
        raise SystemExit(f"FAIL /monitoring/sync answered {r.status_code}: {r.text}")
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        body = monitoring(api)
        if body["state"] == "ERROR":
            raise SystemExit(f"FAIL monitor is in ERROR: {body['errors']}")
        if body["lastSuccessfulSyncAt"] and body["lastSuccessfulSyncAt"] != since:
            return body
        time.sleep(2)
    raise SystemExit(f"FAIL no finished pass within {TIMEOUT:.0f}s")


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=60) as api:
        try:
            before = monitoring(api)
        except httpx.HTTPError as e:
            print(f"FAIL backend is not reachable at {BASE}: {e}")
            return 1
        if before["state"] == "PAUSED":
            api.post("/monitoring/resume")
        print(f"start: state={before['state']} totalInvoices={before['totalInvoices']}")

        # A pass first, so the count below is not skewed by invoices that existed before the monitor ran.
        base = sync_and_wait(api, before["lastSuccessfulSyncAt"])

        name = f"Live Check {uuid.uuid4().hex[:6]}"
        created = api.post("/paypal/sandbox/invoices", json={"recipient_email": RECIPIENT, "supplier_name": name})
        if created.status_code != 200:
            print(f"FAIL could not create the Sandbox invoice: {created.status_code} {created.text}")
            return 1
        invoice_id = created.json()["id"]
        print(f"created {invoice_id}")

        after = sync_and_wait(api, base["lastSuccessfulSyncAt"])
        step(after["totalInvoices"] == base["totalInvoices"] + 1, f"new invoice counted once ({base['totalInvoices']} -> {after['totalInvoices']})")

        again = sync_and_wait(api, after["lastSuccessfulSyncAt"])
        step(again["totalInvoices"] == after["totalInvoices"], f"second pass adds nothing ({again['totalInvoices']})")
        step(again["state"] == "ACTIVE" and not again["errors"], f"state ACTIVE, no errors ({again['errors']})")

        step(api.post("/monitoring/pause").json() == {"state": "PAUSED"}, "pause")
        step(api.post("/monitoring/sync").status_code == 409, "sync is refused while paused")
        step(api.post("/monitoring/resume").json() == {"state": "ACTIVE"}, "resume")
    print("OK" if not failures else f"{failures} step(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
