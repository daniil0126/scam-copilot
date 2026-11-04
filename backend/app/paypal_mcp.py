"""Read-only PayPal Agent Toolkit (@paypal/mcp) for the chat agent. Plan: docs/plans/14-paypal-agent-toolkit.md.

The server runs from the pinned copy in backend/mcp (installed with `npm ci`, never `npx -y`). It is started once and
kept for the next calls: starting Node and the MCP handshake cost about a second on a laptop and over ten on a small
host, which made every chat question wait for it. The process is restarted when it fails and every PAYPAL_MCP_SESSION_SECONDS
(the token it holds in its environment must not outlive PayPal's). PAYPAL_MCP_PERSIST=0 goes back to one process per call.
Three places keep it read-only and Sandbox-only: the `--tools` flag, ALLOWED below, and a test that fails on any writing
tool name.
"""
import asyncio
import json
import logging
import os
import shutil
import time
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

PERSIST = os.getenv("PAYPAL_MCP_PERSIST", "1") != "0"
SESSION_TTL = float(os.getenv("PAYPAL_MCP_SESSION_SECONDS", "10800"))  # 3 h, well inside the life of a PayPal token (about 9 h)
START_TIMEOUT = float(os.getenv("PAYPAL_MCP_START_TIMEOUT_SECONDS", "60"))  # a cold start on a small host is slow

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


class _Shared:
    """The one running session: the task that holds it open, how to tell that task to stop, and when it started."""

    def __init__(self, session, task, stop):
        self.session, self.task, self.stop, self.started = session, task, stop, time.monotonic()


class _State:
    loop = None
    lock: asyncio.Lock | None = None
    shared: _Shared | None = None


_state = _State()


def _locked() -> asyncio.Lock:
    """A lock for the running event loop. A session from another loop (tests start a new loop per test) is simply forgotten."""
    loop = asyncio.get_running_loop()
    if _state.loop is not loop:
        _state.loop, _state.lock, _state.shared = loop, asyncio.Lock(), None
    return _state.lock  # type: ignore[return-value]


async def _hold(ready: asyncio.Future, stop: asyncio.Event) -> None:
    """Keeps a session open until told to stop. It runs as its own task because the stdio client has to be entered and left
    by the same task; the callers only use the session in between."""
    try:
        async with _session() as session:
            if not ready.done():
                ready.set_result(session)
            await stop.wait()
    except asyncio.CancelledError:
        if not ready.done():
            ready.cancel()
    except Exception as exc:
        if not ready.done():
            ready.set_exception(exc)
        else:
            log.info("toolkit process ended: %s", type(exc).__name__)


async def _close(shared: _Shared) -> None:
    shared.stop.set()
    try:
        await asyncio.wait_for(shared.task, 5)
    except Exception:  # a process that will not stop is cancelled by wait_for; nothing else to do
        pass


async def _session_now() -> _Shared:
    """The running session, started if there is none, it has died or it is older than SESSION_TTL."""
    async with _locked():
        shared = _state.shared
        if shared and (shared.task.done() or time.monotonic() - shared.started > SESSION_TTL):
            _state.shared = None
            await _close(shared)
            shared = None
        if shared is None:
            loop = asyncio.get_running_loop()
            ready, stop = loop.create_future(), asyncio.Event()
            task = asyncio.create_task(_hold(ready, stop))
            try:
                session = await asyncio.wait_for(ready, START_TIMEOUT)
            except BaseException as exc:
                stop.set()
                task.cancel()
                if isinstance(exc, (Exception, asyncio.CancelledError)) and not isinstance(exc, McpUnavailable):
                    raise McpUnavailable(f"the toolkit did not start: {type(exc).__name__}") from exc
                raise
            shared = _state.shared = _Shared(session, task, stop)
        return shared


async def _drop() -> None:
    """Forgets the running session (it failed or timed out) so that the next call starts a clean one."""
    async with _locked():
        shared, _state.shared = _state.shared, None
    if shared:
        await _close(shared)


async def _use(func):
    """Runs `func(session)` on the shared session with the call timeout. A broken session is replaced and the call is tried
    once more; a timeout is not retried (PayPal is slow, not the process dead) and drops the session."""
    if not PERSIST:
        async with asyncio.timeout(CALL_TIMEOUT), _session() as session:
            return await func(session)
    for attempt in (1, 2):
        shared = await _session_now()
        try:
            async with asyncio.timeout(CALL_TIMEOUT):
                return await func(shared.session)
        except McpUnavailable:
            raise
        except TimeoutError:
            await _drop()
            raise
        except Exception:
            await _drop()
            if attempt == 2:
                raise


async def warm() -> None:
    """Starts the process ahead of the first question (called when the app starts). Failures are only logged."""
    if not (PERSIST and available()):
        return
    try:
        await list_tools()
        log.info("toolkit is ready")
    except McpUnavailable as exc:
        log.warning("toolkit not ready: %s", exc)


async def close() -> None:
    """Stops the running process (called when the app stops)."""
    shared, _state.shared = _state.shared, None
    if shared:
        await _close(shared)


async def list_tools() -> list[dict]:
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache
    if not available():
        raise McpUnavailable("PayPal toolkit is not available")
    try:
        async with _slots:
            found = (await _use(lambda session: session.list_tools())).tools
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
        async with _slots:
            result = await _use(lambda session: session.call_tool(name, args))
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
