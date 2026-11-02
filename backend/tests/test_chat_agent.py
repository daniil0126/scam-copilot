"""Which way a chat question goes (plan 14): through the agent when it can, as before when it cannot, and never to an error.

No web stack, no network: a scripted model and a fake toolkit (tests/fake_mcp.py).
"""
import asyncio

import pytest

from app import agent, chat_agent, llm, paypal_mcp
from fake_mcp import FakeMcp, ScriptedProvider, call, detail, list_item, listing, say

ID1, ID2 = "INV2-AAAA-BBBB-CCCC-0001", "INV2-AAAA-BBBB-CCCC-0002"
ASK = [{"role": "user", "content": "Which invoices exist?"}]


class PlainProvider:
    """A model that cannot run tool turns: only `complete`."""
    name = "plain"

    def __init__(self, reply="Plain answer."):
        self.reply, self.calls = reply, []

    async def complete(self, system, messages, *, json_output=False):
        self.calls.append((system, messages))
        return self.reply


@pytest.fixture
def use(monkeypatch):
    def install(provider):
        monkeypatch.setattr(llm, "get_provider", lambda: provider)
        return provider
    return install


def check_result():
    return {"level": "high", "score": 70, "recommendation": "Verify.", "comparison": [], "evidence": [],
            "findings": [{"id": "phone", "label": "Phone number in invoice text", "severity": "high", "detail": "A phone number."}],
            "invoice": {"number": "0042", "supplier": {"name": "Acme", "email": "billing@acme.test", "phone": ""},
                        "amount": 349.99, "currency": "USD", "dueDate": "2026-11-15", "note": "Call us", "status": "SENT"}}


def answer(messages=ASK, check=None):
    return asyncio.run(chat_agent.answer(messages, check))


# --- the tool path -------------------------------------------------------------------------------------------------------

def test_a_question_about_the_account_is_answered_through_the_agent(monkeypatch, use):
    FakeMcp(list_invoices=listing(list_item(ID1), list_item(ID2, amount="70.00"))).install(monkeypatch)
    provider = use(ScriptedProvider([call("list_invoices", {}), say("There are two invoices, 105.00 EUR in total.")]))
    reply, used = answer()
    assert used == ["list_invoices"] and reply == "There are two invoices, 105.00 EUR in total."  # the total is in the tool data
    assert provider.complete_calls == []


def test_a_value_the_tools_did_not_return_is_replaced_by_a_marker(monkeypatch, use):
    FakeMcp(get_invoice=detail()).install(monkeypatch)
    use(ScriptedProvider([call("get_invoice", {"invoice_id": ID1}), say("It was sent by ceo@evil.example for 999.00 EUR.")]))
    reply, used = answer()
    assert used == ["get_invoice"] and "ceo@evil.example" not in reply and "999.00" not in reply and llm.ai_guard.REDACTED in reply


def test_an_answer_that_states_fraud_is_replaced_on_the_tool_path_too(monkeypatch, use):
    FakeMcp(list_invoices=listing(list_item(ID1))).install(monkeypatch)
    use(ScriptedProvider([call("list_invoices", {}), say("Yes, this is a scam.")]))
    reply, used = answer()
    assert reply.startswith("I can't say for certain") and used == ["list_invoices"]


def test_a_question_about_an_open_check_uses_no_tool_and_sees_the_check(monkeypatch, use):
    mcp = FakeMcp().install(monkeypatch)
    provider = use(ScriptedProvider([say("It asks you to call a phone number, which needs checking.")]))
    reply, used = answer([{"role": "user", "content": "Why is this risky?"}], check_result())
    assert used == [] and mcp.calls == [] and "<invoice_data>" in provider.step_calls[0]["system"]
    assert reply.startswith("It asks you to call")


# --- the way back to the plain chat ---------------------------------------------------------------------------------------

def test_without_the_toolkit_the_plain_chat_answers(monkeypatch, use):
    monkeypatch.setattr(paypal_mcp, "available", lambda: False)
    provider = use(ScriptedProvider([say("never used")], final="Plain answer."))
    assert answer() == ("Plain answer.", []) and provider.step_calls == []
    assert chat_agent.tool_names(provider) == []


def test_a_model_without_tool_turns_gets_the_plain_chat(monkeypatch, use):
    FakeMcp().install(monkeypatch)
    provider = use(PlainProvider())
    assert answer() == ("Plain answer.", []) and len(provider.calls) == 1 and chat_agent.tool_names(provider) == []


@pytest.mark.parametrize("failure", [RuntimeError("No free model answered a tool request"), paypal_mcp.McpUnavailable("down")])
def test_a_failing_agent_falls_back_to_the_plain_chat_without_an_error(monkeypatch, use, failure):
    FakeMcp(list_invoices=failure).install(monkeypatch)
    provider = use(ScriptedProvider([call("list_invoices", {})] if isinstance(failure, paypal_mcp.McpUnavailable) else [failure],
                                    final="Plain answer."))
    assert answer() == ("Plain answer.", [])
    assert len(provider.complete_calls) == 1


def test_no_provider_is_still_reported(use):
    use(None)
    with pytest.raises(llm.LLMUnavailable):
        answer()


def test_the_status_lists_the_tools_only_when_they_can_be_used(monkeypatch, use):
    FakeMcp().install(monkeypatch)
    assert chat_agent.tool_names(ScriptedProvider([])) == ["list_invoices", "get_invoice"]
    assert chat_agent.tool_names(None) == [] and chat_agent.tool_names(PlainProvider()) == []
    monkeypatch.setattr(paypal_mcp, "available", lambda: False)
    assert chat_agent.tool_names(ScriptedProvider([])) == []


def test_the_system_prompt_of_the_tool_path_keeps_the_chat_rules_and_adds_the_tool_rules(monkeypatch, use):
    FakeMcp().install(monkeypatch)
    provider = use(ScriptedProvider([say("Hi.")]))
    answer()
    system = provider.step_calls[0]["system"]
    assert system.startswith(llm.CHAT_SYSTEM) and agent.TOOL_RULES in system
    assert "The invoice the user is asking about" not in system  # no check, no invoice block
