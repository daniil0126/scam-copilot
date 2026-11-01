import asyncio
import json

import httpx
import pytest

from app import llm, llm_openrouter
from app.llm_openrouter import OpenRouterProvider, PaidModelRefused

FREE = "google/gemma-4-31b-it:free"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", FREE)
    monkeypatch.setattr(llm_openrouter, "ROUND_PAUSE", 0)
    llm_openrouter._verified.clear()
    llm_openrouter._tools.clear()
    llm_openrouter._cooling.clear()


def transport(models, chat=None, calls=None):
    """A fake OpenRouter. `calls` collects (method, path) so a test can prove nothing reached /chat/completions."""
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append((request.method, request.url.path, request))
        if request.url.path.endswith("/models"):
            if isinstance(models, Exception):
                raise models
            return httpx.Response(200, json={"data": models})
        return chat(request) if chat else httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    return httpx.MockTransport(handler)


def model(id=FREE, **pricing):
    return {"id": id, "pricing": {"prompt": "0", "completion": "0", "request": "0", "image": "0", **pricing}}


def chats(calls):
    return [c for c in calls if c[1].endswith("/chat/completions")]


@pytest.mark.parametrize("name", ["anthropic/claude-sonnet-4", "openai/gpt-4o", "google/gemma-4-31b-it", "openrouter/auto", "", ":free",
                                  "a/b:free:paid", "https://evil.example/x:free"])
def test_a_model_id_that_is_not_free_is_refused_at_construction(monkeypatch, name):
    monkeypatch.setenv("LLM_MODEL", name)
    with pytest.raises(PaidModelRefused):
        OpenRouterProvider()


def test_a_missing_key_is_refused(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY")
    with pytest.raises(PaidModelRefused):
        OpenRouterProvider()


@pytest.mark.parametrize("models", [
    [model(prompt="0.000001")],           # a ':free' id that has a price
    [model(completion="0.000002")],
    [model(request="0.01")],
    [model(web_search="0.5")],            # any price field counts, not just the usual ones
    [model(prompt="free")],               # not a number: cannot be read
    [model(id="other/model:free")],       # the configured model is not in the list
    [],
    [{"id": FREE}],                       # no pricing at all
    httpx.ConnectError("down"),           # the lookup itself fails: fail closed
])
def test_nothing_is_sent_unless_the_price_is_confirmed_zero(models):
    async def run():
        calls = []
        provider = OpenRouterProvider(transport(models, calls=calls))
        with pytest.raises(RuntimeError, match="refused"):
            await provider.complete("sys", [{"role": "user", "content": "hi"}])
        assert chats(calls) == []
    asyncio.run(run())


def test_a_free_model_is_called_with_the_key_and_no_fallback_models():
    async def run():
        calls = []
        provider = OpenRouterProvider(transport([model()], calls=calls))
        assert await provider.complete("be brief", [{"role": "user", "content": "hi"}]) == "ok"
        (request,) = [c[2] for c in chats(calls)]
        body = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer sk-test" and str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert body["model"] == FREE and body["messages"][0] == {"role": "system", "content": "be brief"}
        assert "models" not in body and "route" not in body and "provider" not in body  # no way to fall back to another model
    asyncio.run(run())


def test_the_price_is_checked_once_then_remembered():
    async def run():
        calls = []
        provider = OpenRouterProvider(transport([model()], calls=calls))
        await provider.complete("s", [{"role": "user", "content": "a"}])
        await provider.complete("s", [{"role": "user", "content": "b"}])
        assert len([c for c in calls if c[1].endswith("/models")]) == 1 and len(chats(calls)) == 2
    asyncio.run(run())


def test_a_price_that_turns_paid_later_stops_the_calls(monkeypatch):
    async def run():
        calls = []
        listing = [model()]
        provider = OpenRouterProvider(transport(listing, calls=calls))
        await provider.complete("s", [{"role": "user", "content": "a"}])
        listing[0]["pricing"]["prompt"] = "0.001"
        monkeypatch.setattr(llm_openrouter, "PRICE_TTL", 0)  # the hour has passed
        with pytest.raises(RuntimeError, match="refused"):
            await provider.complete("s", [{"role": "user", "content": "b"}])
        assert len(chats(calls)) == 1
    asyncio.run(run())


def test_json_wrapped_in_a_fence_or_prose_is_unwrapped():
    async def run():
        reply = lambda r: httpx.Response(200, json={"choices": [{"message": {"content": r}}]})
        text = 'Sure!\n```json\n{"summary": "x", "level": "low"}\n```'
        provider = OpenRouterProvider(transport([model()], chat=lambda r: reply(text)))
        assert llm.parse_analysis(await provider.complete("s", [{"role": "user", "content": "a"}], json_output=True))["summary"] == "x"
    asyncio.run(run())


def test_an_error_status_raises_without_echoing_the_body():
    async def run():
        provider = OpenRouterProvider(transport([model()], chat=lambda r: httpx.Response(429, text="secret prompt text")))
        with pytest.raises(RuntimeError) as e:
            await provider.complete("s", [{"role": "user", "content": "a"}])
        assert "429" in str(e.value) and "secret" not in str(e.value)
    asyncio.run(run())


def test_get_provider_returns_none_instead_of_raising_for_a_paid_model(monkeypatch, caplog):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o")
    assert llm.get_provider() is None
    assert "refused to start" in caplog.text


def test_get_provider_gives_the_free_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    assert llm.get_provider().name == "openrouter"


OTHER = "nvidia/nemotron-3.5-lightning:free"


def answer(by_model):
    """A chat handler that answers per model id with a status or a text."""
    def chat(request: httpx.Request) -> httpx.Response:
        outcome = by_model[json.loads(request.content)["model"]]
        if isinstance(outcome, int):
            return httpx.Response(outcome, json={"error": "secret prompt echo"})
        return httpx.Response(200, json={"choices": [{"message": {"content": outcome}}]})
    return chat


def two_models(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", f"{FREE}, {OTHER}")
    return [model(), model(id=OTHER)]


def test_a_rate_limited_model_hands_over_to_the_next(monkeypatch):
    async def run():
        calls = []
        provider = OpenRouterProvider(transport(two_models(monkeypatch), chat=answer({FREE: 429, OTHER: "from the second"}), calls=calls))
        assert await provider.complete("s", [{"role": "user", "content": "a"}]) == "from the second"
        assert [json.loads(c[2].content)["model"] for c in chats(calls)] == [FREE, OTHER]
    asyncio.run(run())


def test_a_model_that_is_no_longer_free_is_skipped_and_never_called(monkeypatch):
    async def run():
        calls = []
        listing = two_models(monkeypatch)
        listing[0]["pricing"]["prompt"] = "0.001"
        provider = OpenRouterProvider(transport(listing, chat=answer({FREE: "must not be asked", OTHER: "fine"}), calls=calls))
        assert await provider.complete("s", [{"role": "user", "content": "a"}]) == "fine"
        assert [json.loads(c[2].content)["model"] for c in chats(calls)] == [OTHER]
    asyncio.run(run())


def test_a_model_missing_from_the_list_is_skipped(monkeypatch):
    async def run():
        monkeypatch.setenv("LLM_MODEL", f"{FREE},{OTHER}")
        provider = OpenRouterProvider(transport([model(id=OTHER)], chat=answer({FREE: "no", OTHER: "fine"})))
        assert await provider.complete("s", [{"role": "user", "content": "a"}]) == "fine"
    asyncio.run(run())


def test_all_models_busy_gives_one_error_without_echoing_a_body(monkeypatch):
    async def run():
        provider = OpenRouterProvider(transport(two_models(monkeypatch), chat=answer({FREE: 429, OTHER: 503})))
        with pytest.raises(RuntimeError) as e:
            await provider.complete("s", [{"role": "user", "content": "a"}])
        assert "429" in str(e.value) and "503" in str(e.value) and "secret" not in str(e.value)
    asyncio.run(run())


def test_a_bad_key_does_not_try_the_other_models(monkeypatch):
    async def run():
        calls = []
        provider = OpenRouterProvider(transport(two_models(monkeypatch), chat=answer({FREE: 401, OTHER: "no"}), calls=calls))
        with pytest.raises(RuntimeError, match="401"):
            await provider.complete("s", [{"role": "user", "content": "a"}])
        assert len(chats(calls)) == 1
    asyncio.run(run())


def test_one_paid_id_in_the_list_refuses_the_whole_setting(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", f"{FREE},openai/gpt-4o")
    with pytest.raises(PaidModelRefused):
        OpenRouterProvider()


def test_a_model_that_just_failed_is_not_asked_again_at_once(monkeypatch):
    async def run():
        calls = []
        provider = OpenRouterProvider(transport(two_models(monkeypatch), chat=answer({FREE: 429, OTHER: "fine"}), calls=calls))
        await provider.complete("s", [{"role": "user", "content": "a"}])
        await provider.complete("s", [{"role": "user", "content": "b"}])
        asked = [json.loads(c[2].content)["model"] for c in chats(calls)]
        assert asked == [FREE, OTHER, OTHER]  # the second question goes straight to the model that answered
    asyncio.run(run())


def test_when_every_model_is_cooling_they_are_tried_anyway(monkeypatch):
    async def run():
        provider = OpenRouterProvider(transport(two_models(monkeypatch), chat=answer({FREE: 429, OTHER: 429})))
        with pytest.raises(RuntimeError):
            await provider.complete("s", [{"role": "user", "content": "a"}])
        provider2 = OpenRouterProvider(transport(two_models(monkeypatch), chat=answer({FREE: "back", OTHER: "back"})))
        assert await provider2.complete("s", [{"role": "user", "content": "a"}]) == "back"
    asyncio.run(run())


def test_a_model_closed_to_the_account_does_not_stop_the_others(monkeypatch):
    async def run():
        provider = OpenRouterProvider(transport(two_models(monkeypatch), chat=answer({FREE: 403, OTHER: "fine"})))
        assert await provider.complete("s", [{"role": "user", "content": "a"}]) == "fine"
    asyncio.run(run())


# --- tool requests: `step` (plan 14) ---------------------------------------------------------------------------------

TOOLS = [{"type": "function", "function": {"name": "list_invoices", "description": "List invoices.",
                                           "parameters": {"type": "object", "properties": {}}}}]
ASK = [{"role": "user", "content": "Which invoices exist?"}]
M1, M2 = "a/first:free", "b/second:free"


def tool_model(id=FREE, tools=True, **pricing):
    return {**model(id, **pricing), "supported_parameters": ["temperature", "tools"] if tools else ["temperature"]}


def tool_call(name="list_invoices", arguments='{"days": 7}', id="call_1"):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": arguments}}


def reply_for(replies):
    """A /chat/completions handler that answers per model id; a value is a message dict or a status code."""
    def chat(request):
        answer = replies[json.loads(request.content)["model"]]
        if isinstance(answer, int):
            return httpx.Response(answer, json={})
        return httpx.Response(200, json={"choices": [{"message": answer}]})
    return chat


def test_a_tool_request_returns_the_calls_with_parsed_arguments():
    async def run():
        calls = []
        chat = reply_for({FREE: {"content": None, "tool_calls": [tool_call(), tool_call("get_invoice", '{"invoice_id": "INV2-X"}', "call_2")]}})
        provider = OpenRouterProvider(transport([tool_model()], chat, calls))
        out = await provider.step("sys", ASK, TOOLS)
        assert out == {"content": None, "tool_calls": [
            {"id": "call_1", "name": "list_invoices", "arguments": {"days": 7}},
            {"id": "call_2", "name": "get_invoice", "arguments": {"invoice_id": "INV2-X"}}]}
        (request,) = [c[2] for c in chats(calls)]
        body = json.loads(request.content)
        assert body["tools"] == TOOLS and body["tool_choice"] == "auto" and body["messages"][0]["role"] == "system"
        assert body["model"] == FREE and "models" not in body and "route" not in body
    asyncio.run(run())


def test_a_final_answer_without_calls_is_returned_as_content():
    async def run():
        provider = OpenRouterProvider(transport([tool_model()], reply_for({FREE: {"content": "  Two invoices.  "}})))
        assert await provider.step("sys", ASK, TOOLS) == {"content": "Two invoices.", "tool_calls": []}
    asyncio.run(run())


def test_tool_results_go_back_to_the_model_as_they_are():
    async def run():
        calls = []
        provider = OpenRouterProvider(transport([tool_model()], reply_for({FREE: {"content": "ok"}}), calls))
        history = [*ASK, {"role": "assistant", "content": None, "tool_calls": [tool_call()]},
                   {"role": "tool", "tool_call_id": "call_1", "content": "<tool_data>[]</tool_data>"}]
        await provider.step("sys", history, TOOLS)
        sent = json.loads(chats(calls)[0][2].content)["messages"]
        assert sent[1:] == history
    asyncio.run(run())


def test_a_model_without_tool_support_is_skipped_and_the_next_one_answers(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", f"{M1},{M2}")

    async def run():
        calls = []
        chat = reply_for({M1: {"content": "never asked"}, M2: {"content": None, "tool_calls": [tool_call()]}})
        provider = OpenRouterProvider(transport([tool_model(M1, tools=False), tool_model(M2)], chat, calls))
        out = await provider.step("sys", ASK, TOOLS)
        assert out["tool_calls"][0]["name"] == "list_invoices"
        assert [json.loads(c[2].content)["model"] for c in chats(calls)] == [M2]  # the first model got no request at all
    asyncio.run(run())


def test_without_any_model_that_takes_tools_nothing_is_asked_and_plain_chat_still_works():
    async def run():
        calls = []
        provider = OpenRouterProvider(transport([tool_model(tools=False)], calls=calls))
        with pytest.raises(RuntimeError, match="no tool support"):
            await provider.step("sys", ASK, TOOLS)
        assert chats(calls) == []
        assert await provider.complete("sys", ASK) == "ok"  # the same model still serves `complete`
    asyncio.run(run())


@pytest.mark.parametrize("bad", [
    {"content": None, "tool_calls": [tool_call(arguments="{not json")]},        # arguments that are not JSON
    {"content": None, "tool_calls": [tool_call(arguments="[1, 2]")]},           # JSON, but not an object
    {"content": None, "tool_calls": [{"id": "x", "function": {"arguments": "{}"}}]},  # no tool name
    {"content": None, "tool_calls": [{"function": {"name": "list_invoices", "arguments": "{}"}}]},  # no id
    {"content": "   "},                                                          # nothing at all
])
def test_an_unusable_reply_moves_on_to_the_next_model(monkeypatch, bad):
    monkeypatch.setenv("LLM_MODEL", f"{M1},{M2}")

    async def run():
        chat = reply_for({M1: bad, M2: {"content": "fine"}})
        provider = OpenRouterProvider(transport([tool_model(M1), tool_model(M2)], chat))
        assert (await provider.step("sys", ASK, TOOLS))["content"] == "fine"
    asyncio.run(run())


def test_a_busy_model_is_cooled_and_the_next_one_is_used(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", f"{M1},{M2}")

    async def run():
        chat = reply_for({M1: 429, M2: {"content": "fine"}})
        provider = OpenRouterProvider(transport([tool_model(M1), tool_model(M2)], chat))
        assert (await provider.step("sys", ASK, TOOLS))["content"] == "fine"
        assert M1 in llm_openrouter._cooling
    asyncio.run(run())


def test_a_tool_request_never_reaches_a_model_that_is_not_free():
    async def run():
        calls = []
        provider = OpenRouterProvider(transport([tool_model(prompt="0.000001")], calls=calls))
        with pytest.raises(RuntimeError, match="refused"):
            await provider.step("sys", ASK, TOOLS)
        assert chats(calls) == []
    asyncio.run(run())


def test_more_calls_than_the_limit_are_cut_and_a_request_without_tools_is_refused():
    async def run():
        many = [tool_call(id=f"c{i}") for i in range(llm_openrouter.MAX_TOOL_CALLS + 3)]
        provider = OpenRouterProvider(transport([tool_model()], reply_for({FREE: {"content": None, "tool_calls": many}})))
        assert len((await provider.step("sys", ASK, TOOLS))["tool_calls"]) == llm_openrouter.MAX_TOOL_CALLS
        with pytest.raises(ValueError):
            await provider.step("sys", ASK, [])
    asyncio.run(run())


def test_the_provider_is_recognised_as_able_to_use_tools():
    assert llm.can_use_tools(OpenRouterProvider()) is True and llm.can_use_tools(object()) is False


def test_a_reply_that_hit_the_token_limit_is_marked_and_a_tool_turn_gets_the_larger_budget():
    async def run():
        calls = []
        chat = reply_for({FREE: {"content": "Invoices:\nINV2-AAAA"}})

        def handler(request):
            response = chat(request)
            body = response.json()
            body["choices"][0]["finish_reason"] = "length"
            return httpx.Response(200, json=body)

        provider = OpenRouterProvider(transport([tool_model()], handler, calls))
        out = await provider.step("sys", ASK, TOOLS)
        assert out["truncated"] is True and out["content"] == "Invoices:\nINV2-AAAA"
        (request,) = [c[2] for c in chats(calls)]
        assert json.loads(request.content)["max_tokens"] == 1500
    asyncio.run(run())
