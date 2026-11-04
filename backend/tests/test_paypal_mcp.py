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


# --- one process for many calls ---------------------------------------------------------------------------------------

@pytest.fixture
def counting(monkeypatch):
    """A fake `_session` that counts how often it is entered and left, one FakeSession per start."""
    log = SimpleNamespace(started=0, stopped=0, sessions=[])
    factory = {"make": lambda: FakeSession()}

    @asynccontextmanager
    async def _session():
        log.started += 1
        session = factory["make"]()
        log.sessions.append(session)
        try:
            yield session
        finally:
            log.stopped += 1
    monkeypatch.setattr(paypal_mcp, "_session", _session)
    monkeypatch.setattr(paypal_mcp, "available", lambda: True)
    monkeypatch.setattr(paypal_mcp, "_tools_cache", None)
    monkeypatch.setattr(paypal_mcp, "PERSIST", True)
    log.factory = factory
    return log


def test_one_process_serves_several_calls(counting):
    async def go():
        for _ in range(3):
            await paypal_mcp.call_tool("list_invoices", {})
        await paypal_mcp.call_tool("get_invoice", {"invoice_id": "INV2-1"})
        await paypal_mcp.close()
    run(go())
    assert counting.started == 1 and counting.stopped == 1
    assert len(counting.sessions[0].calls) == 4


def test_without_persistence_every_call_starts_its_own(counting, monkeypatch):
    monkeypatch.setattr(paypal_mcp, "PERSIST", False)
    async def go():
        for _ in range(2):
            await paypal_mcp.call_tool("list_invoices", {})
    run(go())
    assert counting.started == 3 and counting.stopped == 3  # the tool list, then one per call


def test_a_dead_process_is_replaced_and_the_call_succeeds(counting):
    class Dying(FakeSession):
        async def call_tool(self, name, args):
            raise BrokenPipeError("the process is gone")
    made = iter([Dying(), FakeSession()])
    counting.factory["make"] = lambda: next(made, FakeSession())
    async def go():
        # the first session lists the tools, then dies on the call; the second serves it
        return await paypal_mcp.call_tool("list_invoices", {})
    assert run(go()) == {"items": []}
    assert counting.started == 2


def test_a_process_that_keeps_failing_ends_in_unavailable(counting):
    class Dying(FakeSession):
        async def call_tool(self, name, args):
            raise BrokenPipeError("gone")
    counting.factory["make"] = lambda: Dying()
    with pytest.raises(McpUnavailable):
        run(paypal_mcp.call_tool("list_invoices", {}))
    assert counting.started == 2  # tried once more on a fresh one, not forever


def test_a_timeout_drops_the_session_and_is_not_retried(counting, monkeypatch):
    counting.factory["make"] = lambda: FakeSession(delay=1)
    monkeypatch.setattr(paypal_mcp, "CALL_TIMEOUT", 0.05)
    async def go():
        with pytest.raises(McpUnavailable):
            await paypal_mcp.call_tool("list_invoices", {})
        counting.factory["make"] = lambda: FakeSession()
        return await paypal_mcp.call_tool("list_invoices", {})  # a clean session after the timeout
    assert run(go()) == {"items": []}
    assert counting.started == 2


def test_an_old_session_is_restarted(counting, monkeypatch):
    monkeypatch.setattr(paypal_mcp, "SESSION_TTL", 0)
    async def go():
        await paypal_mcp.call_tool("list_invoices", {})
        await paypal_mcp.call_tool("list_invoices", {})
    run(go())
    assert counting.started >= 2


def test_calls_at_the_same_time_share_one_start(counting):
    async def go():
        await asyncio.gather(*[paypal_mcp.call_tool("list_invoices", {}) for _ in range(4)])
        await paypal_mcp.close()
    run(go())
    assert counting.started == 1


def test_warm_starts_the_process_and_never_raises(counting, monkeypatch):
    async def go():
        await paypal_mcp.warm()
        await paypal_mcp.close()
    run(go())
    assert counting.started == 1
    counting.factory["make"] = lambda: FakeSession(tools=())
    monkeypatch.setattr(paypal_mcp, "_tools_cache", None)
    run(paypal_mcp.warm())  # a toolkit without the tools: logged, not raised
