"""The gate in front of "Pay": only an invoice whose exact version was analysed as low risk gets PayPal's payment page."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

import app.payments as payments
from app.audit_log import AuditEvent
from app.db import SessionLocal
from app.main import app
from app.monitor import account_id
from app.payments import PayIntent, pay_url
from tests.test_monitor import full, sync, world  # noqa: F401  (fixtures)

client = TestClient(app)
HEADERS = {"X-Requested-By": "scamcopilot-ui"}
GOOD = "INV2-AAAA-BBBB-CCCC-DDDD"


def payable(i, value="10.00", **over):
    """A monitor-test invoice with the payer page PayPal puts in `recipient_view_url`."""
    inv = full(i, value=value)
    inv["id"] = f"INV2-AAAA-BBBB-CCCC-DD{i:02d}"
    inv["detail"]["metadata"]["recipient_view_url"] = f"https://www.sandbox.paypal.com/invoice/p/#AAAABBBBCCCCDD{i:02d}"
    inv.update(over)
    return inv


def scam(i):
    inv = payable(i, value="499.99")
    inv["invoicer"]["business_name"] = "Secure Shield Renewals"
    inv["detail"]["note"] = "Your plan was auto-renewed and charged. Call +1 888 555 0142 now to cancel or get a refund."
    return inv


@pytest.fixture(autouse=True)
def clean():
    with SessionLocal() as db:
        db.execute(delete(PayIntent))
        db.execute(delete(AuditEvent))
        db.commit()


def audit(action):
    with SessionLocal() as db:
        return db.scalars(select(AuditEvent).where(AuditEvent.action == action)).all()


def preview(*ids):
    r = client.post("/payments/preview", json={"invoiceIds": list(ids)})
    assert r.status_code == 200, r.text
    return {i["invoiceId"]: i for i in r.json()["items"]}, r.json()["totals"]


def intents(ids, **extra):
    return client.post("/payments/intents", json={"invoiceIds": ids, **extra}, headers=HEADERS)


def test_a_low_risk_invoice_may_be_paid_and_a_scam_may_not(world):
    ok, bad = payable(1), scam(2)
    world.invoices = {ok["id"]: ok, bad["id"]: bad}
    sync()
    views, totals = preview(ok["id"], bad["id"])
    assert views[ok["id"]]["eligible"] and views[ok["id"]]["level"] == "low"
    assert not views[bad["id"]]["eligible"]
    assert views[bad["id"]]["reasons"][0]["code"] == "risk_high"
    assert totals == {"USD": "10.00"}  # the refused invoice is not in the total


def test_an_unknown_invoice_is_not_checked(world):
    views, _ = preview("INV2-ZZZZ-ZZZZ-ZZZZ-ZZZZ")
    only = next(iter(views.values()))
    assert not only["eligible"] and only["reasons"][0]["code"] == "not_checked"


def test_intents_need_the_requested_by_header(world):
    inv = payable(1)
    world.invoices = {inv["id"]: inv}
    sync()
    assert client.post("/payments/intents", json={"invoiceIds": [inv["id"]]}).status_code == 403
    assert client.post("/payments/intents/x/opened").status_code == 403
    assert client.post("/payments/check", json={"invoiceId": inv["id"]}).status_code == 403


def test_intent_gives_the_paypal_page_and_is_audited(world):
    inv = payable(1)
    world.invoices = {inv["id"]: inv}
    sync()
    r = intents([inv["id"]], expectedIds=[inv["id"]], expectedTotals={"USD": "10.00"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["totals"] == {"USD": "10.00"}
    assert body["intents"][0]["url"] == inv["detail"]["metadata"]["recipient_view_url"]
    with SessionLocal() as db:
        assert db.scalar(select(PayIntent.status)) == "ISSUED"
    assert len(audit("pay.intent_created")) == 1


def test_an_invoice_changed_after_its_check_is_refused(world):
    inv = payable(1)
    world.invoices = {inv["id"]: inv}
    sync()
    world.invoices[inv["id"]] = payable(1, value="9999.00")  # PayPal now has a different version
    r = intents([inv["id"]])
    assert r.status_code == 409
    item = r.json()["items"][0]
    assert not item["eligible"] and item["reasons"][0]["code"] == "changed"
    assert len(audit("pay.blocked")) == 1
    with SessionLocal() as db:
        assert db.scalar(select(PayIntent)) is None  # nothing was issued


def test_one_refused_invoice_refuses_the_whole_basket(world):
    ok, bad = payable(1), scam(2)
    world.invoices = {ok["id"]: ok, bad["id"]: bad}
    sync()
    r = intents([ok["id"], bad["id"]])
    assert r.status_code == 409
    assert [i["eligible"] for i in r.json()["items"]] == [True, False]
    assert r.json()["totals"] == {"USD": "10.00"}  # what the person can confirm instead


def test_what_the_person_confirmed_must_match_what_is_paid(world):
    a, b = payable(1), payable(2, value="20.00")
    world.invoices = {a["id"]: a, b["id"]: b}
    sync()
    r = intents([a["id"], b["id"]], expectedIds=[a["id"], b["id"]], expectedTotals={"USD": "10.00"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "changed"
    assert intents([a["id"], b["id"]], expectedIds=[a["id"], b["id"]], expectedTotals={"USD": "30.00"}).status_code == 200


def test_a_paid_or_cancelled_invoice_is_not_payable(world):
    paid, cancelled = payable(1), payable(2)
    paid["status"], cancelled["status"] = "PAID", "CANCELLED"
    world.invoices = {paid["id"]: paid, cancelled["id"]: cancelled}
    sync()
    views, _ = preview(paid["id"], cancelled["id"])
    assert views[paid["id"]]["reasons"][0]["code"] == "paid"
    assert views[cancelled["id"]]["reasons"][0]["code"] == "not_payable"


def test_a_part_paid_invoice_shows_what_is_still_owed(world):
    inv = payable(1, value="100.00")
    inv["status"] = "PARTIALLY_PAID"
    inv["due_amount"] = {"currency_code": "USD", "value": "40.00"}
    world.invoices = {inv["id"]: inv}
    sync()
    view, totals = preview(inv["id"])
    assert view[inv["id"]]["eligible"] and view[inv["id"]]["amount"] == "40.00" and totals == {"USD": "40.00"}


def test_no_page_from_paypal_means_no_link(world):
    inv = payable(1)
    inv["detail"]["metadata"]["recipient_view_url"] = "https://www.sandbox.paypal.com.evil.example/invoice/p/#AAAABBBBCCCCDD01"
    world.invoices = {inv["id"]: inv}
    sync()
    r = intents([inv["id"]])
    assert r.status_code == 409 and r.json()["items"][0]["reasons"][0]["code"] == "no_page"


@pytest.mark.parametrize("url", [
    "http://www.sandbox.paypal.com/invoice/p/#AAAABBBBCCCCDDDD",             # not https
    "https://www.paypal.com/invoice/p/#AAAABBBBCCCCDDDD",                    # live host in sandbox mode
    "https://www.sandbox.paypal.com@evil.example/invoice/p/#AAAABBBBCCCCDDDD",
    "https://www.sandbox.paypal.com:8443/invoice/p/#AAAABBBBCCCCDDDD",
    "https://www.sandbox.paypal.com/invoice/p/?next=//evil.example#AAAABBBBCCCCDDDD",
    "https://www.sandbox.paypal.com/other/#AAAABBBBCCCCDDDD",
    "https://www.sandbox.paypal.com/invoice/p/#ZZZZZZZZZZZZZZZZ",            # another invoice's page
    "https://www.sandbox.paypal.com\\@evil.example/invoice/p/#AAAABBBBCCCCDDDD",
    "https://www.sandbox.paypal.com/invoice/p/#AAAABBBBCCCCDDDD extra",
    "https://evil.example/invoice/p/#AAAABBBBCCCCDDDD",
    "",
])
def test_only_paypals_own_page_for_this_invoice_is_accepted(url):
    assert pay_url({"detail": {"metadata": {"recipient_view_url": url}}}, GOOD) is None


def test_the_right_page_is_accepted():
    url = "https://www.sandbox.paypal.com/invoice/p/#AAAABBBBCCCCDDDD"
    assert pay_url({"detail": {"metadata": {"recipient_view_url": url}}}, GOOD) == url


def test_opening_is_recorded_and_paid_comes_only_from_paypal(world):
    inv = payable(1)
    world.invoices = {inv["id"]: inv}
    sync()
    intent = intents([inv["id"]]).json()["intents"][0]
    r = client.post(f"/payments/intents/{intent['intentId']}/opened", headers=HEADERS)
    assert r.json()["status"] == "OPENED" and len(audit("pay.link_opened")) == 1
    assert client.get("/payments/intents", params={"ids": intent["intentId"]}).json()["items"][0]["status"] == "OPENED"
    world.invoices[inv["id"]] = deepcopy(inv) | {"status": "PAID"}
    assert client.get("/payments/intents", params={"ids": intent["intentId"]}).json()["items"][0]["status"] == "PAID"


def test_an_intent_can_be_cancelled_and_expires(world):
    inv = payable(1)
    world.invoices = {inv["id"]: inv}
    sync()
    first = intents([inv["id"]]).json()["intents"][0]
    assert client.post(f"/payments/intents/{first['intentId']}/cancel", headers=HEADERS).json()["status"] == "CANCELLED"
    assert len(audit("pay.cancelled")) == 1
    assert client.post(f"/payments/intents/{first['intentId']}/opened", headers=HEADERS).status_code == 409
    second = intents([inv["id"]]).json()["intents"][0]
    with SessionLocal() as db:
        row = db.get(PayIntent, second["intentId"])
        row.expires_at = payments._now() - payments.timedelta(seconds=1)
        db.commit()
    assert client.post(f"/payments/intents/{second['intentId']}/opened", headers=HEADERS).status_code == 409


def test_asking_twice_reuses_the_open_intent(world):
    inv = payable(1)
    world.invoices = {inv["id"]: inv}
    sync()
    one = intents([inv["id"]]).json()["intents"][0]["intentId"]
    two = intents([inv["id"]]).json()["intents"][0]["intentId"]
    assert one == two


def test_a_payment_limit_refuses_big_baskets(world, monkeypatch):
    inv = payable(1, value="50.00")
    world.invoices = {inv["id"]: inv}
    sync()
    monkeypatch.setenv("PAY_MAX_TOTAL", "20")
    r = intents([inv["id"]])
    assert r.status_code == 409 and r.json()["error"]["code"] == "over_limit"


def test_a_basket_has_a_size_limit(world):
    assert intents([f"INV2-AAAA-BBBB-CCCC-{n:04d}" for n in range(payments.MAX_BASKET + 1)]).status_code == 422


def test_an_invalid_id_never_reaches_paypal(world):
    assert client.post("/payments/preview", json={"invoiceIds": ["../../v1/payments"]}).status_code == 422
    assert intents(["INV2/x?y"]).status_code == 422


def test_check_now_makes_an_unchecked_invoice_payable(world):
    inv = payable(1)
    world.invoices = {inv["id"]: inv}
    assert preview(inv["id"])[0][inv["id"]]["reasons"][0]["code"] == "not_checked"
    r = client.post("/payments/check", json={"invoiceId": inv["id"]}, headers=HEADERS)
    assert r.status_code == 200 and r.json()["eligible"] is True


def test_intents_belong_to_the_account(world):
    inv = payable(1)
    world.invoices = {inv["id"]: inv}
    sync()
    intent = intents([inv["id"]]).json()["intents"][0]
    with SessionLocal() as db:
        db.get(PayIntent, intent["intentId"]).account_id = "acc_other"
        db.commit()
    assert client.post(f"/payments/intents/{intent['intentId']}/opened", headers=HEADERS).status_code == 404
    assert client.get("/payments/intents", params={"ids": intent["intentId"]}).json()["items"] == []


def test_history_entries_carry_the_paypal_invoice_id(world):
    inv = payable(1)
    world.invoices = {inv["id"]: inv}
    sync()
    entries = client.get("/checks").json()
    assert inv["id"] in [e["invoiceId"] for e in entries]


def test_when_paypal_reports_an_invoice_paid_the_gate_shows_it_paid_at_once(world):
    inv = payable(1)
    world.invoices = {inv["id"]: inv}
    sync()
    intent = intents([inv["id"]]).json()["intents"][0]
    client.post(f"/payments/intents/{intent['intentId']}/opened", headers=HEADERS)
    world.invoices[inv["id"]] = deepcopy(inv) | {"status": "PAID"}
    assert client.get("/payments/intents", params={"ids": intent["intentId"]}).json()["items"][0]["status"] == "PAID"
    view = preview(inv["id"])[0][inv["id"]]  # no monitor pass in between
    assert view["status"] == "PAID" and view["reasons"][0]["code"] == "paid"
