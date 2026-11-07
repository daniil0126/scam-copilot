import asyncio
import copy
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import agent, llm, paypal_mcp
from app.db import get_db
from app.models import Check

router = APIRouter(tags=["ai"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=llm.MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    check_id: str | None = None  # a stored check the question is about


@router.get("/ai/status")
def ai_status():
    provider = llm.get_provider()
    status = {"enabled": provider is not None, "provider": provider.name if provider else None}
    if agent.enabled(provider):  # the model may read PayPal with these tools, and nothing else
        status["tools"] = sorted(paypal_mcp.ALLOWED)
    return status


@router.post("/chat")
async def chat(body: ChatRequest, db: Session = Depends(get_db)):
    if body.messages[-1].role != "user":
        raise HTTPException(422, "The last message must be from the user")
    check = db.get(Check, body.check_id) if body.check_id else None
    messages = [m.model_dump() for m in body.messages]
    provider = llm.get_provider()
    if agent.enabled(provider):
        try:
            out = await agent.answer(provider, messages, check.result if check else None)
            return {"reply": out.reply, **({"toolsUsed": out.tools} if out.tools else {}),
                    **({"invoices": out.invoices} if out.invoices else {}), **({"table": out.table} if out.table else {}),
                    **({"paymentProposal": out.proposal} if out.proposal else {})}
        except Exception as e:  # PayPal or the model failed: the chat still answers, without tools
            llm.log.warning("Chat agent failed, answering without tools: %s", type(e).__name__)
    try:
        reply = await llm.chat_reply(messages, check.result if check else None)
    except llm.LLMUnavailable:
        raise HTTPException(503, "The AI assistant is not configured on the server.")
    except Exception as e:  # only the type is logged: a provider's message can carry request details
        llm.log.warning("LLM chat failed: %s", type(e).__name__)
        raise HTTPException(502, "The AI assistant failed to answer. Try again.")
    return {"reply": reply}


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, db: Session = Depends(get_db)):
    """Same answer as `POST /chat`, sent as lines of JSON while it is being produced: the steps of the agent
    ({"type": "model" | "tool", ...}), then {"type": "answer", "reply", "toolsUsed"} or {"type": "error", "message"}."""
    if body.messages[-1].role != "user":
        raise HTTPException(422, "The last message must be from the user")
    provider = llm.get_provider()
    if provider is None:
        raise HTTPException(503, "The AI assistant is not configured on the server.")
    check = db.get(Check, body.check_id) if body.check_id else None
    result = copy.deepcopy(check.result) if check else None  # read now: the session is not for the stream to use
    messages = [m.model_dump() for m in body.messages]

    async def produce(queue: asyncio.Queue):
        async def emit(event: dict):
            await queue.put(event)
        try:
            if agent.enabled(provider):
                try:
                    out = await agent.answer(provider, messages, result, emit)
                    await emit({"type": "answer", "reply": out.reply, "toolsUsed": out.tools, "invoices": out.invoices,
                                "table": out.table, **({"paymentProposal": out.proposal} if out.proposal else {})})
                    return
                except Exception as e:
                    llm.log.warning("Chat agent failed, answering without tools: %s", type(e).__name__)
                    await emit({"type": "fallback"})
            await emit({"type": "answer", "reply": await llm.chat_reply(messages, result), "toolsUsed": [], "invoices": [], "table": None})
        except Exception as e:
            llm.log.warning("LLM chat failed: %s", type(e).__name__)
            await emit({"type": "error", "message": "The AI assistant failed to answer. Try again."})
        finally:
            await queue.put(None)

    async def lines():
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(produce(queue))
        try:
            while (event := await queue.get()) is not None:
                yield json.dumps(event) + "\n"
        finally:
            task.cancel()  # the panel was closed or the question abandoned

    return StreamingResponse(lines(), media_type="application/x-ndjson")


class ExplainRequest(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=llm.MAX_MESSAGE_CHARS)


@router.post("/invoices/{invoice_id}/explain")
async def explain(invoice_id: str, body: ExplainRequest | None = None, db: Session = Depends(get_db)):
    """AI explanation of a checked invoice on request (docs/plans/contracts.md, section 5).

    Without a question: the explanation of the result, also for a LOW one, stored with the check. With a question: an
    answer about this invoice. A model that fails or is rejected gives `status: UNAVAILABLE`, not an error: the check
    itself is unaffected.
    """
    check = db.scalars(select(Check).where(Check.paypal_invoice_id == invoice_id)).first()
    if check is None:
        raise HTTPException(404, "This invoice has not been checked yet.")
    provider = llm.get_provider()
    if provider is None:
        raise HTTPException(503, "The AI assistant is not configured on the server.")

    result = copy.deepcopy(check.result)
    if body and body.question:
        try:
            reply = await llm.chat_reply([{"role": "user", "content": body.question}], result)
        except Exception as e:
            llm.log.warning("LLM explain failed: %s", type(e).__name__)
            return {"ai": {"status": "UNAVAILABLE", "summary": llm.UNAVAILABLE_TEXT, "provider": provider.name}}
        return {"ai": {"status": "OK", "summary": reply, "provider": provider.name}}

    analysis = await llm.analyse_invoice(result["invoice"], result, force=True)
    if analysis is None:  # the provider was switched off between the two lines above
        raise HTTPException(503, "The AI assistant is not configured on the server.")
    llm.apply_analysis(result, analysis)
    check.result = result  # a new object: SQLAlchemy does not see a change made inside the old JSON
    db.commit()
    return {"ai": result["ai"]}
