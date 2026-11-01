"""Safety checks that read the code and the log path (plan 13). Pure: no database, no HTTP."""
import io
import logging
import re
from pathlib import Path

import pytest

from app import security

APP = Path(__file__).resolve().parents[1] / "app"
SOURCES = [p for p in APP.rglob("*.py") if "__pycache__" not in p.parts]


# --- secrets in logs ---------------------------------------------------------------------------------------------

def test_scrubber_hides_configured_secrets_bearer_tokens_and_pairs(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-CANARY-123456")
    text = ("key sk-CANARY-123456 sent; Authorization: Bearer abcDEF123456789 ok; "
            "access_token=AAA.bbb.ccc&x=1; client_secret: \"SHHH-secret-1\"")
    out = security.scrub(text)
    for secret in ("sk-CANARY-123456", "abcDEF123456789", "AAA.bbb.ccc", "SHHH-secret-1"):
        assert secret not in out, secret
    assert "x=1" in out  # only the secret is hidden, not the rest of the line


def test_scrubber_works_on_real_log_records(monkeypatch):
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "paypal-CANARY-987654")
    original = logging.getLogRecordFactory()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    log = logging.getLogger("scamcopilot.test_security")
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        security.install_log_scrubber()
        security.install_log_scrubber()  # a second call does nothing
        log.info("token request failed for %s", "paypal-CANARY-987654")
        log.info("plain line %d", 7)
    finally:
        log.removeHandler(handler)
        logging.setLogRecordFactory(original)
    logged = stream.getvalue()
    assert "paypal-CANARY-987654" not in logged and "plain line 7" in logged


# --- SSRF: the backend never opens links from an invoice ------------------------------------------------------------

ALLOWED_HOSTS = {"api-m.paypal.com", "api-m.sandbox.paypal.com", "openrouter.ai"}


def test_outbound_hosts_are_only_paypal_and_openrouter():
    """Every `httpx` call site builds its URL from a fixed base. Hosts written as literals next to a call must be allowed."""
    for path in SOURCES:
        src = path.read_text(encoding="utf-8")
        if "httpx" not in src:
            continue
        for host in re.findall(r"https?://([A-Za-z0-9.-]+)", src):
            if host in {"www.w3.org"}:
                continue
            assert host in ALLOWED_HOSTS, f"{path.name} mentions {host}, which is not an allowed outbound host"
        # no request is made to a URL taken from data: calls take BASE_URL / a constant, not an invoice field
        assert not re.search(r"(client|httpx)\.(get|post|request|stream)\(\s*(inv|invoice|link|url|page)\w*[\[.]", src), path.name


# --- no payments, cancellations or changes -------------------------------------------------------------------------

ALLOWED_WRITES = {
    ("POST", "/v1/notifications/verify-webhook-signature"),  # asks PayPal to check a signature, changes nothing
    ("POST", "/v2/invoicing/search-invoices"),               # a search sent as POST, read-only
    ("POST", "/v2/invoicing/invoices"),                      # sandbox-only demo data (routes under /sandbox)
}
FORBIDDEN_WORDS = ("/payments", "/cancel", "/remind", "/refund", "/record-payment", "/delete", "/checkout")


def test_paypal_writes_are_only_the_known_ones():
    calls = []
    for path in SOURCES:
        for method, target in re.findall(r"paypal_request\(\s*\"(POST|PUT|PATCH|DELETE)\",\s*f?\"([^\"]+)\"", path.read_text(encoding="utf-8")):
            calls.append((path.name, method, re.sub(r"\{[^}]*\}", "{id}", target.split("?")[0])))
    assert calls, "the scan found no PayPal write calls, the pattern is out of date"
    for file, method, target in calls:
        sandbox_send = target == "/v2/invoicing/invoices/{id}/send" and file == "paypal.py"  # sandbox-only demo route
        assert (method, target) in ALLOWED_WRITES or sandbox_send, f"{file}: unexpected {method} {target}"
        assert not any(w in target for w in FORBIDDEN_WORDS), f"{file}: {method} {target}"


@pytest.mark.parametrize("word", FORBIDDEN_WORDS)
def test_no_forbidden_paypal_endpoint_appears_in_the_code(word):
    for path in SOURCES:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "paypal_request" in line or "BASE_URL" in line:
                assert word not in line, f"{path.name}: {line.strip()}"


# --- the chat agent reads PayPal through two tools and nothing else (plan 14) ----------------------------------------

WRITE_VERBS = ("create", "send", "cancel", "delete", "update", "record", "pay", "refund", "remind", "generate", "capture")


def test_the_agent_tools_are_exactly_the_two_reads_everywhere():
    from app import agent, paypal_mcp
    names = {"list_invoices", "get_invoice"}
    assert paypal_mcp.ALLOWED == names
    assert {t["function"]["name"] for t in agent.PAYPAL_TOOLS} == names
    # the one other function fetches nothing: it only picks which invoices already read are drawn as a table
    assert {t["function"]["name"] for t in agent.TOOLS} == names | {"show_invoice_table"}
    src = (APP / "agent.py").read_text(encoding="utf-8")
    body = src[src.index("def _show_table"):src.index("def _dump")]
    assert "paypal_mcp" not in body and "httpx" not in body  # no network from the display function
    assert paypal_mcp.TOOLS_FLAG == "--tools=invoices.list,invoices.get"  # the server itself starts with only these two
    for name in names:
        assert not any(name.startswith(verb) for verb in WRITE_VERBS), name


def test_the_paypal_token_reaches_the_tool_server_only_through_its_environment():
    """Command-line arguments are visible in `ps`; the environment of the child is not."""
    holders = [p.name for p in SOURCES if "PAYPAL_ACCESS_TOKEN" in p.read_text(encoding="utf-8")]
    assert holders == ["paypal_mcp.py"]
    src = (APP / "paypal_mcp.py").read_text(encoding="utf-8")
    assert re.search(r"args=\[str\(ENTRY\), TOOLS_FLAG\]", src)  # nothing else on the command line
    assert not re.search(r"(log|print)\w*\(.*(token|_token\()", src, re.I)


def test_a_failing_tool_call_does_not_put_the_token_in_the_log(monkeypatch, caplog):
    import asyncio
    from contextlib import asynccontextmanager

    from app import paypal_mcp

    async def tools():
        return [{"name": n, "description": "", "inputSchema": {"properties": {"page": {}}}} for n in paypal_mcp.ALLOWED]

    @asynccontextmanager
    async def broken():
        raise RuntimeError("connection refused with PAYPAL_ACCESS_TOKEN=A21-SECRET-TOKEN")
        yield

    monkeypatch.setattr(paypal_mcp, "list_tools", tools)
    monkeypatch.setattr(paypal_mcp, "_session", broken)
    with caplog.at_level(logging.DEBUG), pytest.raises(paypal_mcp.McpUnavailable) as raised:
        asyncio.run(paypal_mcp.call_tool("list_invoices", {}))
    assert "A21-SECRET-TOKEN" not in caplog.text and "A21-SECRET-TOKEN" not in str(raised.value)
