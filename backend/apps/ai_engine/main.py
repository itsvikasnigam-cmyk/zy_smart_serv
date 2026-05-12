from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(title="ZY Smart Serv - AI Engine", version="0.1.0")


class AIRequest(BaseModel):
    client_id: str
    chat_id: str
    batch_id: str
    customer_phone: str
    batch_text: str = Field(default="", description="Concatenated customer messages")


class AIResponse(BaseModel):
    action: Literal["REPLY", "HANDOFF", "NEEDS_OWNER_DATA"]
    reply_text: str | None = None
    intent: str = "unknown"
    routing_intent: str = "general"
    confidence: float = 0.5
    language: str = "auto"
    handoff_reason: str | None = None
    missing_fields: list[str] = []
    risk_reason: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.post("/ai/respond", response_model=AIResponse)
def respond(req: AIRequest) -> AIResponse:
    # Phase C stub: always reply with a short acknowledgment.
    text = req.batch_text.strip()
    if not text:
        return AIResponse(action="REPLY", reply_text="Hi! How can I help you today?")
    return AIResponse(action="REPLY", reply_text=f"Got it: {text}")

