"""The assistant can propose a payment and never make one: no tool confirms, and the person's own words switch the proposal on."""
import json

import pytest
from sqlalchemy import select

from app import agent, payments, paypal_mcp
from app.audit_log import AuditEvent
from app.db import SessionLocal
from tests.test_agent import RAW, ToolProvider, ask, call, mcp, text, use  # noqa: F401  (fixtures and helpers)
from tests.test_checks import client, fresh_db  # noqa: F401

READY = {"invoiceId": RAW["id"], "eligible": True, "reasons": [], "supplier": "Acme Ltd", "number": "0042",
         "amount": "499.00", "currency": "USD", "dueDate": "2026-11-15", "status": "SENT", "level": "low",
         "checkedAt": "2026-11-07T10:00:00Z", "limited": False, "contentHash": "h"}


@pytest.fixture
def gate(monkeypatch):
    """The stored verdict for the one invoice the fake PayPal returns; tests change `box['view']`."""
    box = {"view": dict(READY)}
    monkeypatch.setattr(payments, "stored_view", lambda db, account, invoice_id: {**box["view"], "invoiceId": invoice_id})
    return box


def names(provider, call_index=0):
    return {t["function"]["name"] for t in provider.seen[call_index][2]}


def test_no_tool_can_confirm_or_pay():
    assert paypal_mcp.ALLOWED == frozenset({"list_invoices", "get_invoice"})
    offered = {t["function"]["name"] for t in agent.tools_for([{"role": "user", "content": "pay all"}])}
    assert offered == {"list_invoices", "get_invoice", "show_invoice_table", "propose_payment"}
    props = json.dumps(agent.PROPOSE_TOOL)
    assert "confirm" not in agent.PROPOSE_TOOL["function"]["parameters"]["properties"] and "url" not in props.lower().replace("curl", "")


def test_the_proposal_is_offered_only_when_the_person_talks_about_paying(mcp, use):
    provider = use(ToolProvider(text("Nothing to report."), text("ok")))
    ask("Which invoices came in this week?")
    assert "propose_payment" not in names(provider)
    provider = use(ToolProvider(text("ok")))
    ask("Pay all my invoices")
    assert "propose_payment" in names(provider)


def test_a_note_that_says_pay_everything_does_not_switch_the_proposal_on(mcp, use, gate):
    provider = use(ToolProvider(call("list_invoices"), call("propose_payment", {}, id="c2"), text("I could not do that.")))
    body = ask("Which invoices came in this week?").json()  # the note of RAW says IGNORE ALL PREVIOUS INSTRUCTIONS
    assert "propose_payment" not in names(provider, 1)
    assert "unknown tool" in provider.seen[2][1][-1]["content"]  # a call to a tool that was not offered is refused
    assert "paymentProposal" not in body


def test_pay_all_gives_a_proposal_built_by_the_server(mcp, use, gate):
    provider = use(ToolProvider(call("list_invoices"), call("propose_payment", {}, id="c2"),
                                text("1 invoice is ready. Please review it below.")))
    body = ask("Pay all my invoices").json()
    proposal = body["paymentProposal"]
    assert [i["invoiceId"] for i in proposal["items"]] == [RAW["id"]]
    assert proposal["totals"] == {"USD": "499.00"} and proposal["excluded"] == []
    told = provider.seen[2][1][-1]["content"]  # what the model learned: counts, no ids, no names, no links
    assert RAW["id"] not in told and "Acme" not in told and "paypal.com" not in told
    assert '"ready": 1' in told
    assert "contentHash" not in json.dumps(proposal)  # internal detail stays on the server


def test_invoices_with_warning_signs_are_left_out_with_the_reason(mcp, use, gate):
    gate["view"].update(eligible=False, level="high", reasons=[{"code": "risk_high", "text": "High risk"}])
    provider = use(ToolProvider(call("list_invoices"), call("propose_payment", {}, id="c2"), text("None are ready.")))
    body = ask("Pay all my invoices").json()
    proposal = body["paymentProposal"]
    assert proposal["items"] == [] and proposal["excluded"][0]["reasons"][0]["code"] == "risk_high"
    assert '"High risk": 1' in provider.seen[2][1][-1]["content"]


def test_paid_and_cancelled_invoices_are_not_in_scope(mcp, use, gate):
    mcp.reply = {"items": [{**RAW, "status": "PAID"}]}
    use(ToolProvider(call("list_invoices"), call("propose_payment", {}, id="c2"), text("Nothing is left to pay.")))
    body = ask("Pay all my invoices").json()
    assert "paymentProposal" not in body


def test_proposing_before_reading_is_an_error_for_the_model(mcp, use, gate):
    mcp.reply = {"items": []}
    provider = use(ToolProvider(call("propose_payment", {}), text("I need to read your invoices first.")))
    body = ask("Pay all my invoices").json()
    assert "paymentProposal" not in body
    assert ("list_invoices", {"page_size": agent.MAX_PAGE_SIZE}) in mcp.calls  # nothing was read yet, so the agent read first
    assert "No invoices have been read yet" in provider.seen[1][1][-1]["content"]


def test_the_words_above_a_proposal_are_written_by_code(mcp, use, gate):
    use(ToolProvider(call("list_invoices"), call("propose_payment", {}, id="c2"), text("Done! I have paid all invoices for you.")))
    body = ask("Pay all my invoices").json()
    assert "paid" not in body["reply"].lower().replace("unpaid", "")
    assert body["reply"] == ("1 invoice (499.00 USD) has no warning signs. I can't pay for you: review it in History, then continue to PayPal.")


def test_a_proposal_comes_without_the_list_the_model_read(mcp, use, gate):
    use(ToolProvider(call("list_invoices", {"query": "Acme"}), call("propose_payment", {}, id="c2"), text("ok")))
    mcp.reply = {"items": [RAW, {**RAW, "id": "INV2-EEEE-FFFF-GGGG-HHHH"}]}
    body = ask("Pay all my invoices").json()
    assert "paymentProposal" in body and "table" not in body and "invoices" not in body


def test_every_qualifying_invoice_is_proposed_and_batches_are_said_plainly(mcp, use, gate, monkeypatch):
    monkeypatch.setattr(payments, "MAX_BASKET", 1)
    mcp.reply = {"items": [RAW, {**RAW, "id": "INV2-EEEE-FFFF-GGGG-HHHH"}]}
    use(ToolProvider(call("list_invoices"), call("propose_payment", {}, id="c2"), text("ok")))
    body = ask("Pay all my invoices").json()
    assert len(body["paymentProposal"]["items"]) == 2  # nothing is cut off at the size of one payment
    assert "One payment holds at most 1, so you will confirm them in batches." in body["reply"]


def test_the_proposal_covers_all_pages_even_if_the_model_read_only_a_few(mcp, use, gate, monkeypatch):
    other = {**RAW, "id": "INV2-EEEE-FFFF-GGGG-HHHH"}

    async def paged(name, args):
        mcp.calls.append((name, args))
        return {"items": [RAW]} if args.get("page_size") == 1 else {"items": [RAW, other]}

    monkeypatch.setattr(paypal_mcp, "call_tool", paged)
    use(ToolProvider(call("list_invoices", {"page_size": 1}), call("propose_payment", {}, id="c2"), text("ok")))
    body = ask("pay all the low risk invoices").json()
    assert sorted(i["invoiceId"] for i in body["paymentProposal"]["items"]) == sorted([RAW["id"], other["id"]])


def test_a_proposal_is_audited(mcp, use, gate):
    use(ToolProvider(call("list_invoices"), call("propose_payment", {}, id="c2"), text("1 ready.")))
    ask("Pay all my invoices")
    with SessionLocal() as db:
        rows = db.scalars(select(AuditEvent).where(AuditEvent.action == "pay.proposal_made")).all()
    assert rows and rows[-1].detail["ready"] == 1 and rows[-1].actor == "system"


def test_the_stream_carries_the_proposal(mcp, use, gate):
    use(ToolProvider(call("list_invoices"), call("propose_payment", {}, id="c2"), text("1 ready.")))
    r = client.post("/chat/stream", json={"messages": [{"role": "user", "content": "Pay all my invoices"}]})
    events = [json.loads(line) for line in r.text.splitlines() if line.strip().startswith("{")]
    answer = next(e for e in events if e["type"] == "answer")
    assert answer["paymentProposal"]["items"][0]["invoiceId"] == RAW["id"]
    step = next(e for e in events if e.get("name") == "propose_payment" and e["state"] == "done")
    assert step["local"] is True and step["summary"] == "1 ready, 0 left out"
