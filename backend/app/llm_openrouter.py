"""OpenRouter provider that can only ever use free models.

Set LLM_PROVIDER=openrouter, LLM_API_KEY and LLM_MODEL: one model id ending in `:free`, or several separated by commas.
Free models are often rate-limited (429) or withdrawn, so the next one in the list is tried when a model is busy, failing,
or no longer provably free. Two guards keep a paid model out, for every model of the list:

1. the model id must end in `:free`, and the address of the API is fixed here, not configurable;
2. before the first call, and then once an hour, the model's prices are read from OpenRouter and must all be zero.

Anything that does not add up, including a failed price lookup, refuses the model: the provider stays off and checks run
on rules alone. Nothing is sent to OpenRouter until both guards pass. A separate OpenRouter key with a credit limit is the
third line of defence and is set in the OpenRouter dashboard, not here.
"""
import asyncio
import json
import logging
import os
import re
import time

import httpx

from app.llm import PROVIDERS

log = logging.getLogger("scamcopilot.llm")

BASE_URL = "https://openrouter.ai/api/v1"
PRICE_TTL = 3600
TIMEOUT = 15  # per model: a model that has not answered by now is slower than trying the next one
MAX_TOKENS = 700
_lock = asyncio.Semaphore(2)  # free models have a low requests-per-minute limit
_verified: dict[str, float] = {}  # model id -> time the zero price was confirmed
_cooling: dict[str, float] = {}  # model id -> time until which it is skipped after failing (a 429 rarely clears sooner)
COOLDOWN = 60.0


ROUNDS = 2  # passes over the list; the second follows a short pause
ROUND_PAUSE = 3.0
BUSY_STATUSES = {403, 408, 425, 429, 500, 502, 503, 504}  # 403: this model is closed to the account (a data policy), not the key  # worth trying another model: rate limit, overload, upstream error


class _Busy(Exception):
    """This model could not answer right now (rate limit, overload, timeout, empty answer)."""


class PaidModelRefused(Exception):
    """The configured model is not provably free."""


def _free_id(model: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._\-]+/[A-Za-z0-9._\-]+:free", model))


def _json_text(text: str) -> str:
    """Models often wrap JSON in a code fence or add a sentence around it. Returns the outermost {...} if there is one."""
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if 0 <= start < end else text


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self.models = [m.strip() for m in os.getenv("LLM_MODEL", "").split(",") if m.strip()]
        self.model = self.models[0] if self.models else ""  # the preferred one
        self._key = os.getenv("LLM_API_KEY", "").strip()
        self._transport = transport
        if not self._key:
            raise PaidModelRefused("LLM_API_KEY is not set")
        for model in self.models or [""]:
            if not _free_id(model):  # one paid id in the list refuses the whole setting, so a typo cannot go unnoticed
                raise PaidModelRefused(f"LLM_MODEL {model!r} is not a free model (the id must end in ':free')")

    async def _verify_free(self, client: httpx.AsyncClient, model: str) -> None:
        if time.monotonic() - _verified.get(model, -PRICE_TTL) < PRICE_TTL:
            return
        _verified.pop(model, None)
        try:
            res = await client.get(f"{BASE_URL}/models")
            res.raise_for_status()
            entry = next((m for m in res.json()["data"] if m["id"] == model), None)
        except Exception as e:
            raise PaidModelRefused(f"could not confirm the price of {model!r}: {type(e).__name__}") from e
        pricing = (entry or {}).get("pricing")
        if not isinstance(pricing, dict) or not pricing:
            raise PaidModelRefused(f"{model!r} is not in OpenRouter's model list, so its price is unknown")
        try:
            paid = {k: v for k, v in pricing.items() if float(v) != 0}
        except (TypeError, ValueError):
            raise PaidModelRefused(f"{model!r} has a price that cannot be read: {pricing}")
        if paid:
            raise PaidModelRefused(f"{model!r} is not free: {paid}")
        _verified[model] = time.monotonic()

    async def complete(self, system: str, messages: list[dict], *, json_output: bool = False) -> str:
        failures: list[str] = []
        for round_ in range(ROUNDS):
            if round_:
                await asyncio.sleep(ROUND_PAUSE)  # a rate limit often clears within seconds
            now = time.monotonic()
            ready = [m for m in self.models if _cooling.get(m, 0) <= now]
            for model in ready or self.models:  # all cooling: try them anyway rather than fail without asking
                try:
                    text = await self._ask(model, system, messages)
                except PaidModelRefused as e:  # this model is not provably free: never called, the next one is tried
                    failures.append(f"{model}: refused")
                    log.warning("model skipped: %s", e)
                    continue
                except _Busy as e:
                    failures.append(f"{model}: {e}")
                    _cooling[model] = time.monotonic() + COOLDOWN
                    continue
                _cooling.pop(model, None)
                return _json_text(text) if json_output else text
        raise RuntimeError("No free model answered (" + "; ".join(dict.fromkeys(failures)) + ")")

    async def _ask(self, model: str, system: str, messages: list[dict]) -> str:
        async with _lock, httpx.AsyncClient(timeout=TIMEOUT, transport=self._transport) as client:
            await self._verify_free(client, model)
            try:
                res = await client.post(
                    f"{BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {self._key}", "X-Title": "Scam Copilot"},
                    json={"model": model, "messages": [{"role": "system", "content": system}, *messages],
                          "temperature": 0.2, "max_tokens": MAX_TOKENS},
                )
            except httpx.HTTPError as e:
                raise _Busy(type(e).__name__) from e
        if res.status_code in BUSY_STATUSES:
            raise _Busy(str(res.status_code))
        if res.status_code != 200:  # a bad key or a closed account will not be fixed by another model
            raise RuntimeError(f"OpenRouter answered {res.status_code}")  # the body is not logged: it can echo the prompt
        text = ((res.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        if not text.strip():
            raise _Busy("empty answer")
        return text.strip()


PROVIDERS["openrouter"] = OpenRouterProvider
