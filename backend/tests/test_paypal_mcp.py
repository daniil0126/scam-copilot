import asyncio
import json
import re
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app import paypal_mcp
from app.paypal_mcp import McpUnavailable

SCHEMAS = {
    "list_invoices": {"properties": {"page": {}, "page_size": {}, "total_required": {}}},
    "get_invoice": {"properties": {"invoice_id": {}}},
}


class FakeSession:
    def __init__(self, tools=("list_invoices", "get_invoice"), reply=None, is_error=False, delay=0):
        self.tools, self.reply, self.is_error, self.delay = tools, reply, is_error, delay
        self.calls = []

    async def list_tools(self):
        return SimpleNamespace(tools=[
            SimpleNamespace(name=n, description=f"{n} d", input_schema=SCHEMAS.get(n, {})) for n in self.tools
        ])

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        await asyncio.sleep(self.delay)
        text = self.reply if self.reply is not None else json.dumps({"items": []})
        return SimpleNamespace(content=[SimpleNamespace(text=text)], is_error=self.is_error)


@pytest.fixture
def fake(monkeypatch):
    def install(session):
        @asynccontextmanager
        async def _session():
            yield session
        monkeypatch.setattr(paypal_mcp, "_session", _session)
        monkeypatch.setattr(paypal_mcp, "available", lambda: True)
        monkeypatch.setattr(paypal_mcp, "_tools_cache", None)
        return session
    return install


def run(coro):
    return asyncio.run(coro)


def test_list_tools_is_exactly_the_allowed_pair(fake):
    fake(FakeSession(tools=("list_invoices", "get_invoice", "create_invoice")))
    names = {t["name"] for t in run(paypal_mcp.list_tools())}
    assert names == {"list_invoices", "get_invoice"}


def test_missing_tool_makes_it_unavailable(fake):
    fake(FakeSession(tools=("list_invoices",)))
    with pytest.raises(McpUnavailable):
        run(paypal_mcp.list_tools())


def test_allowlist_has_no_writing_tool():
    assert paypal_mcp.ALLOWED == {"list_invoices", "get_invoice"}
    assert not any(re.match(r"(create|send|cancel|delete|update|record|pay|refund|remind|generate)", n) for n in paypal_mcp.ALLOWED)
    assert paypal_mcp.TOOLS_FLAG == "--tools=invoices.list,invoices.get"


def test_call_returns_parsed_json(fake):
    s = fake(FakeSession(reply='{"items": [{"id": "INV2-1"}]}'))
    assert run(paypal_mcp.call_tool("list_invoices", {"page_size": 5})) == {"items": [{"id": "INV2-1"}]}
    assert s.calls == [("list_invoices", {"page_size": 5})]


@pytest.mark.parametrize("name,args", [
    ("create_invoice", {}),
    ("list_invoices", {"query": "x"}),
    ("get_invoice", {"invoice_id": "x" * 500}),
    ("get_invoice", {"invoice_id": {"a": 1}}),
])
def test_rejected_before_reaching_the_server(fake, name, args):
    s = fake(FakeSession())
    with pytest.raises(McpUnavailable):
        run(paypal_mcp.call_tool(name, args))
    assert s.calls == []


def test_tool_error_not_json_and_non_object(fake):
    for kwargs in ({"is_error": True}, {"reply": "not json"}, {"reply": "[1]"}, {"reply": '{"ok": false, "status": 404, "message": "gone"}'}):
        fake(FakeSession(**kwargs))
        with pytest.raises(McpUnavailable):
            run(paypal_mcp.call_tool("get_invoice", {"invoice_id": "INV2-1"}))


def test_timeout_becomes_unavailable(fake, monkeypatch):
    fake(FakeSession(delay=1))
    monkeypatch.setattr(paypal_mcp, "CALL_TIMEOUT", 0.05)
    with pytest.raises(McpUnavailable):
        run(paypal_mcp.call_tool("list_invoices", {}))


def test_unavailable_without_keys_or_node(monkeypatch):
    monkeypatch.setattr(paypal_mcp.paypal, "PAYPAL_CLIENT_ID", None)
    assert paypal_mcp.available() is False
    monkeypatch.setattr(paypal_mcp, "_tools_cache", None)
    with pytest.raises(McpUnavailable):
        run(paypal_mcp.list_tools())


def test_not_available_outside_sandbox(monkeypatch):
    monkeypatch.setattr(paypal_mcp.paypal, "PAYPAL_CLIENT_ID", "id")
    monkeypatch.setattr(paypal_mcp.paypal, "PAYPAL_CLIENT_SECRET", "secret")
    monkeypatch.setattr(paypal_mcp.paypal, "PAYPAL_MODE", "live")
    assert paypal_mcp.available() is False


def test_paypal_error_json_is_a_tool_error(fake):
    fake(FakeSession(reply='{"ok": false, "status": 404, "message": "The specified resource does not exist."}'))
    with pytest.raises(paypal_mcp.McpToolError, match="404"):
        run(paypal_mcp.call_tool("get_invoice", {"invoice_id": "NOPE"}))
