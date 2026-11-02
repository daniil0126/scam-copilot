"""Stand-ins for the PayPal toolkit and for a model that calls tools. No Node, no network (plan 14).

`FakeMcp.install(monkeypatch)` replaces the three public functions of `app.paypal_mcp`, so the code under test is the
real agent. `ScriptedProvider` plays a model: each `step` returns the next prepared turn.
"""
import asyncio
import copy

from app import paypal_mcp


def list_item(id, number="0042", amount="35.00", currency="EUR", date="2026-10-30", due="2026-11-13", status="SENT",
              recipient="buyer@example.org"):
    """One element of a list_invoices result: no issuer name, no items, no note (as the real server returns it)."""
    return {
        "id": id, "status": status, "amount": {"currency_code": currency, "value": amount},
        "due_amount": {"currency_code": currency, "value": amount},
        "detail": {"invoice_number": number, "invoice_date": date, "currency_code": currency, "payment_term": {"due_date": due}},
        "invoicer": {"email_address": "billing@nordhost.test"},
        "primary_recipients": [{"billing_info": {"email_address": recipient}}],
        "links": [{"href": "https://api.sandbox.paypal.com/v2/invoicing/invoices/" + id, "rel": "self"}],
        "unilateral": False,
    }


def listing(*items, total=None):
    return {"items": list(items), "total_items": len(items) if total is None else total, "links": []}


def detail(id="INV2-AAAA-BBBB-CCCC-0001", note="Hosting, October.", status="SENT", name="Nordhost GmbH",
           email="billing@nordhost.test", phone="5550100", items=None):
    """What get_invoice returns: the full invoice, with an address that must never reach the model."""
    return {
        "id": id, "status": status,
        "detail": {"invoice_number": "0042", "invoice_date": "2026-10-12", "currency_code": "EUR", "note": note,
                   "payment_term": {"due_date": "2026-10-26"}},
        "invoicer": {"business_name": name, "email_address": email, "phones": [{"country_code": "049", "national_number": phone}],
                     "address": {"address_line_1": "1 Secret Street", "admin_area_2": "Berlin", "postal_code": "10115"}},
        "primary_recipients": [{"billing_info": {"email_address": "buyer@example.org", "business_name": "Buyer Ltd"}}],
        "items": items if items is not None else [{"name": "VPS plan M", "quantity": "1", "unit_amount": {"currency_code": "EUR", "value": "35.00"}}],
        "amount": {"currency_code": "EUR", "value": "35.00"},
    }


class FakeMcp:
    """`replies[tool]` is a raw result, an exception to raise, or a function of the arguments."""

    def __init__(self, **replies):
        self.replies, self.calls = replies, []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        reply = self.replies[name]
        reply = reply(args) if callable(reply) else reply
        if isinstance(reply, Exception):
            raise reply
        return copy.deepcopy(reply)

    async def list_tools(self):
        return [{"name": n, "description": n, "inputSchema": {}} for n in ("list_invoices", "get_invoice")]

    def available(self):
        return True

    def install(self, monkeypatch):
        monkeypatch.setattr(paypal_mcp, "call_tool", self.call_tool)
        monkeypatch.setattr(paypal_mcp, "list_tools", self.list_tools)
        monkeypatch.setattr(paypal_mcp, "available", self.available)
        return self


def call(name, arguments=None, id="call_1"):
    """A model turn that asks for one tool."""
    return {"content": None, "tool_calls": [{"id": id, "name": name, "arguments": arguments if arguments is not None else {}}]}


def calls(*specs):
    """A model turn that asks for several tools: (name, arguments) pairs."""
    return {"content": None, "tool_calls": [{"id": f"call_{i}", "name": n, "arguments": a} for i, (n, a) in enumerate(specs, 1)]}


def say(text):
    return {"content": text, "tool_calls": []}


class ScriptedProvider:
    name = "scripted"

    def __init__(self, turns, final="Final answer.", delay=0.0):
        self.turns, self.final, self.delay = list(turns), final, delay
        self.step_calls, self.complete_calls = [], []

    async def step(self, system, messages, tools):
        self.step_calls.append({"system": system, "messages": copy.deepcopy(messages), "tools": tools})
        if self.delay:
            await asyncio.sleep(self.delay)
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn

    async def complete(self, system, messages, *, json_output=False):
        self.complete_calls.append((system, copy.deepcopy(messages)))
        return self.final
