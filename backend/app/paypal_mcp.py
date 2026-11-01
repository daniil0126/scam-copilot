"""Read-only PayPal Agent Toolkit (@paypal/mcp) for the chat agent. Plan: docs/plans/14-paypal-agent-toolkit.md.

The server is started per call from the pinned copy in backend/mcp (installed with `npm ci`, never `npx -y`), so the
token is always fresh and no process outlives a request. Three places keep it read-only and Sandbox-only: the
`--tools` flag, ALLOWED below, and a test that fails on any writing tool name.
"""
import asyncio
import json
import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import HTTPException

from app import paypal

log = logging.getLogger("paypal_mcp")

ALLOWED = frozenset({"list_invoices", "get_invoice"})
TOOLS_FLAG = "--tools=invoices.list,invoices.get"
ENTRY = Path(__file__).resolve().parent.parent / "mcp" / "node_modules" / "@paypal" / "mcp" / "dist" / "index.js"
CALL_TIMEOUT = float(os.getenv("PAYPAL_MCP_TIMEOUT_SECONDS", "20"))
MAX_ARG_CHARS = 200  # string arguments (an invoice id, a page number) are short; anything longer is not one

_slots = asyncio.Semaphore(2)
_tools_cache: list[dict] | None = None


class McpUnavailable(Exception):
    """The toolkit cannot answer: no Node, no keys, the process failed, timed out, or the tool reported an error."""


class McpToolError(McpUnavailable):
    """PayPal answered with an error (for example 404 for an unknown invoice); the text is safe to show the model."""


def available() -> bool:
    """False when the chat must work without tools (no Node, not installed, no keys, or not Sandbox)."""
    return bool(
        os.getenv("PAYPAL_MCP", "1") != "0"
        and paypal.PAYPAL_MODE == "sandbox"
        and paypal.PAYPAL_CLIENT_ID
        and paypal.PAYPAL_CLIENT_SECRET
        and shutil.which("node")
        and ENTRY.is_file()
    )


async def _token() -> str:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            return await paypal.get_access_token(client)
    except (HTTPException, httpx.HTTPError) as exc:
        raise McpUnavailable("PayPal token is not available") from exc


@asynccontextmanager
async def _session():
    """A started MCP session. Replaced in tests. The token goes only into the child's environment."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=shutil.which("node") or "node",
        args=[str(ENTRY), TOOLS_FLAG],
        env={"PATH": os.environ.get("PATH", ""), "PAYPAL_ACCESS_TOKEN": await _token(), "PAYPAL_ENVIRONMENT": "SANDBOX"},
    )
    with open(os.devnull, "w") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


def _tool_dict(tool) -> dict:
    return {"name": tool.name, "description": tool.description or "", "inputSchema": tool.input_schema}


async def list_tools() -> list[dict]:
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache
    if not available():
        raise McpUnavailable("PayPal toolkit is not available")
    try:
        async with _slots, asyncio.timeout(CALL_TIMEOUT):
            async with _session() as session:
                found = (await session.list_tools()).tools
    except McpUnavailable:
        raise
    except Exception as exc:
        raise McpUnavailable(f"list_tools failed: {type(exc).__name__}") from exc
    tools = [_tool_dict(t) for t in found if t.name in ALLOWED]
    if {t["name"] for t in tools} != ALLOWED:
        raise McpUnavailable("PayPal toolkit did not offer the expected tools")
    _tools_cache = tools
    return tools


def _check_args(name: str, args: dict, schema: dict) -> None:
    if not isinstance(args, dict):
        raise McpUnavailable("tool arguments must be an object")
    if "invoice_id" in args and not paypal.INVOICE_ID.fullmatch(str(args["invoice_id"])):
        raise McpToolError(f"{name}: invalid invoice id")
    allowed = set((schema or {}).get("properties", {}))
    unknown = set(args) - allowed
    if unknown:
        raise McpUnavailable(f"{name}: unknown arguments {sorted(unknown)}")
    for key, value in args.items():
        if isinstance(value, str) and len(value) > MAX_ARG_CHARS:
            raise McpUnavailable(f"{name}: argument {key} is too long")
        if not isinstance(value, (str, int, bool)):
            raise McpUnavailable(f"{name}: argument {key} has an unsupported type")


async def call_tool(name: str, args: dict) -> dict:
    """Raw PayPal JSON of one allowed tool; any failure is McpUnavailable."""
    if name not in ALLOWED:
        raise McpUnavailable(f"tool {name!r} is not allowed")
    schema = next(t["inputSchema"] for t in await list_tools() if t["name"] == name)
    _check_args(name, args, schema)
    try:
        async with _slots, asyncio.timeout(CALL_TIMEOUT):
            async with _session() as session:
                result = await session.call_tool(name, args)
    except McpUnavailable:
        raise
    except Exception as exc:  # timeout, broken pipe, protocol error; the message could carry the token, so only the type
        log.warning("%s failed: %s", name, type(exc).__name__)
        raise McpUnavailable(f"{name} failed: {type(exc).__name__}") from exc
    text = "".join(getattr(part, "text", "") for part in result.content)
    if result.is_error:
        raise McpUnavailable(f"{name} returned an error")
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise McpUnavailable(f"{name} returned something that is not JSON") from exc
    if not isinstance(data, dict):
        raise McpUnavailable(f"{name} returned an unexpected shape")
    if data.get("ok") is False:  # the server reports PayPal errors as ordinary JSON
        raise McpToolError(f"{name}: PayPal answered {data.get('status')} {str(data.get('message', ''))[:120]}")
    return data
