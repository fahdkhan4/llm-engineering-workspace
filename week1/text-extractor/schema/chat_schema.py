"""Request/response models for the question endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """One retrieved chunk, so the frontend can show where the answer came from."""

    # 1-based position. The answer cites this chunk as "[index]", so the
    # frontend can turn every marker into a link to this exact passage.
    index: int
    chunk_id: int
    document_id: int
    document_name: str
    section_title: str | None = None
    page_start: int
    page_end: int
    score: float
    excerpt: str


class AnswerResponse(BaseModel):
    question: str
    answer: str
    # Echo it back so the frontend can keep the thread going.
    session_key: str
    sources: list[SourceRef] = Field(default_factory=list)
    model: str | None = None
    # Token usage metadata from the LLM (prompt_tokens, completion_tokens, etc.)
    usage: dict | None = None
    # False while llm/llm_client.py is still the stub.
    llm_configured: bool = True
