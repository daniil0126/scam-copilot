"""How a chat question is answered: through the agent (it may read the account's invoices) when that is possible, otherwise as
the plain chat always did. Kept apart from the routes so it can be tested without the web stack (plan 14)."""
from app import agent, llm, paypal_mcp


def tools_enabled(provider) -> bool:
    """The agent is used only with a provider that can run tool turns and a toolkit that can answer (Node, keys, Sandbox)."""
    return provider is not None and llm.can_use_tools(provider) and paypal_mcp.available()


def tool_names(provider) -> list[str]:
    """For `GET /ai/status`: the tools the chat can use now, or an empty list."""
    return [t["function"]["name"] for t in agent.TOOLS] if tools_enabled(provider) else []


async def answer(messages: list[dict], check: dict | None = None) -> tuple[str, list[str]]:
    """Returns (reply, tools used). Any failure of the agent, the toolkit or the model on the tool path ends in the plain
    chat; the user does not see it. The same guards apply on both paths, and on the tool path a value may also come from
    what the tools returned."""
    provider = llm.get_provider()
    if provider is None:
        raise llm.LLMUnavailable()
    if tools_enabled(provider):
        history, system, source = llm.chat_inputs(messages, check)
        try:
            result = await agent.run(provider, system, history)
        except agent.AgentUnavailable:
            pass
        else:
            return llm.guard_chat_reply(result.reply, check, source + "\n" + result.grounding), result.tools_used
    return await llm.chat_reply(messages, check), []
