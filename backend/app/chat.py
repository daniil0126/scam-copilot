from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import llm
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
    return {"enabled": provider is not None, "provider": provider.name if provider else None}


@router.post("/chat")
async def chat(body: ChatRequest, db: Session = Depends(get_db)):
    if body.messages[-1].role != "user":
        raise HTTPException(422, "The last message must be from the user")
    check = db.get(Check, body.check_id) if body.check_id else None
    try:
        reply = await llm.chat_reply([m.model_dump() for m in body.messages], check.result if check else None)
    except llm.LLMUnavailable:
        raise HTTPException(503, "The AI assistant is not configured on the server.")
    except Exception:
        llm.log.exception("LLM chat failed")
        raise HTTPException(502, "The AI assistant failed to answer. Try again.")
    return {"reply": reply}
