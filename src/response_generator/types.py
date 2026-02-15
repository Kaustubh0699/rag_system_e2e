from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_question: str
    enhanced_query: str
    assistant_response: str


class GroundedResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    user_question: str
    enhanced_query: str
    response: str
    context_chunk_ids: List[str] = Field(default_factory=list)
