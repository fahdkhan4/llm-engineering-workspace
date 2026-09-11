"""The LLM seam: chat completions through Groq's OpenAI-compatible API.

Three calls live here:

    answer_question()    the grounded answer, from the retrieved chunks
    rewrite_query()      a follow-up turned into a standalone search query
    summarise_document() a document-level overview, written once at ingest

Without `GROQ_API_KEY` these raise `LLMNotConfigured` (or return None), and the
endpoint replies with `llm_configured: false` while still returning the
retrieved sources - so the frontend always has real data to render.

Embeddings are not here; they live in `llm/embedder.py`.
"""

from __future__ import annotations
from dotenv import load_dotenv
from dataclasses import dataclass, field
from functools import lru_cache
from openai import OpenAI, OpenAIError
import logging
import os
import textwrap
import json

from config import settings

load_dotenv()

logger = logging.getLogger(__name__)

# Groq speaks the OpenAI wire protocol, so the OpenAI SDK talks to it unchanged.
_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
_MODEL = os.getenv("GROQ_MODEL", settings.main_model)
_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", settings.fast_model)

FALLBACK_ANSWER = (
    "I could not find enough relevant information in the documents to answer that."
)


_SYSTEM_PROMPT = textwrap.dedent("""\
    You are the answer engine for a Document Intelligence Workspace.

    ## Input
    You get numbered source blocks, then the question. Each block starts with
    its number and where it came from: "[2] report.pdf | Section 3 | pp.4-5".

    ## Grounding
    - Answer only from the numbered sources. Never use outside knowledge.
    - Never guess, infer, or fill a gap.
    - Conversation history is only there to resolve follow-ups and pronouns
      ("it", "that one", "more detail"). It is never evidence.
    - Copy names, dates, figures, units and conditions exactly. Never round.
    - If a source only names or lists a topic without explaining it, say that
      the document only lists it. Never fill in the explanation yourself, even
      when the user asks for "more detail" - a marker on a sentence the source
      does not actually make is the worst thing you can do.
    - Combine sources when the answer spans several of them.
    - If two sources disagree, say so and cite both.

    ## Citations - numbers only
    - Cite with the source number in square brackets, right after the sentence
      it supports: [1]
    - Two sources for one sentence: [2][5]
    - Use only numbers that appear in the source blocks. Never invent one.
    - Never write file names, section titles or page numbers in your text. The
      number carries all of that, and the reader can click it to see the exact
      passage.
    - Every sentence that states a fact ends with a marker.
    - Do not add a "Sources" list at the end.

    ## Plain language
    - Write for a smart reader who has not opened the document.
    - Short sentences. Everyday words.
    - Keep a technical term if the document uses it, then explain it in a few
      plain words the first time it appears.
    - Open with the direct answer in one sentence. Then give the detail.
    - Use "-" bullets when you list three or more things. One level only:
      never put a bullet under a bullet.
    - Plain text only. No markdown: no **bold**, no *italics*, no headings,
      no tables.
    - No preamble, no restating the question, no filler.
    - Answer in the language of the question.
    - Never mention retrieval, context blocks, or how the sources were picked.

    ## When the sources fall short
    If they cannot answer the question at all, reply with exactly:
      "The documents do not cover this."
    If they answer only part of it, answer that part with markers, then end
    with a line starting "Not in the documents:" naming what is missing.

    ## Examples

    Q: What is the notice period for termination?
    A: Either side can end the agreement by giving 60 days of written notice [3].

    Q: What is the notice period, and who signed it?
    A: Either side can end the agreement by giving 60 days of written notice [3].
    Not in the documents: who signed the agreement.

    Q: What is this document about?
    A: It is a 40-day study plan for learning system design [1]. The work is
    split into five phases, from the basics up to full system designs [1][4].
    Each day covers one topic and takes about 2-3 hours [1].

    Q: What was Q3 headcount?
    A: The documents do not cover this.
    """)


class LLMNotConfigured(RuntimeError):
    """Raised while `answer_question` has not been implemented yet."""


@dataclass(slots=True)
class RetrievedContext:
    """A chunk selected for the question, with everything needed to cite it."""

    chunk_id: int
    document_id: int
    document_name: str
    section_title: str | None
    page_start: int
    page_end: int
    content: str
    score: float

    @property
    def label(self) -> str:
        parts = [self.document_name]
        if self.section_title:
            parts.append(self.section_title)
        pages = (
            f"p.{self.page_start}"
            if self.page_start == self.page_end
            else f"pp.{self.page_start}-{self.page_end}"
        )
        parts.append(pages)
        return " | ".join(parts)


@dataclass(slots=True)
class HistoryTurn:
    role: str  # "user" or "assistant"
    content: str


@dataclass(slots=True)
class LLMAnswer:
    answer: str
    model: str | None = None
    usage: dict = field(default_factory=dict)


def build_context_block(contexts: list[RetrievedContext]) -> str:
    """Optional helper: the retrieved chunks as a numbered, citable block."""
    return "\n\n".join(
        f"[{index}] {ctx.label}\n{ctx.content}"
        for index, ctx in enumerate(contexts, start=1)
    )

def _system_prompt_answer_generating():
    return _SYSTEM_PROMPT


def _history_messages(history: list[HistoryTurn]) -> list[dict]:
    """History turns as chat messages, dropping empty or unknown-role ones."""
    return [
        {"role": turn.role, "content": turn.content}
        for turn in history
        if turn.role in ("user", "assistant") and turn.content
    ]


def _user_prompt(question: str, contexts: list[RetrievedContext]) -> str:
    # The citation format and grounding rules live in the system prompt;
    # restating them here only risks contradicting it.
    return (
        f"### Retrieved Contexts\n{build_context_block(contexts)}\n\n"
        f"### User Question\n{question}"
    )


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    """The shared client, so connections are reused across requests."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise LLMNotConfigured(
            "GROQ_API_KEY is not set. Add it to text-extractor/.env."
        )
    return OpenAI(base_url=_BASE_URL, api_key=api_key, timeout=30.0, max_retries=3)

def answer_question(
    question: str,
    contexts: list[RetrievedContext],
    history: list[HistoryTurn],
) -> LLMAnswer:
    logger.debug("I am in the llm generation phase")
    messages = [
        {"role": "system", "content": _system_prompt_answer_generating()},
        {"role": "user", "content": f"### Retrieved Contexts\n{build_context_block(contexts)}"},
        {"role": "assistant", "content": "I have read the sources and will answer only from them."},
        *_history_messages(history),
        {"role": "user", "content": question},
    ]

    try:
        response = _client().chat.completions.create(
            model=_MODEL,
            messages=messages,
            temperature=0,  # grounded extraction, not creative writing
            max_tokens=800,
        )
    except OpenAIError as exc:
        logger.exception("LLM request failed")
        raise LLMNotConfigured(f"The LLM request failed: {exc}") from exc

    message = response.choices[0].message
    content = (message.content or "").strip()
    return LLMAnswer(
        answer=content if content else FALLBACK_ANSWER,
        model=response.model,
        usage=response.usage.model_dump() if response.usage else {},
    )


# --------------------------------------------------------------------------- #
# Follow-up handling
# --------------------------------------------------------------------------- #

_REWRITE_MODEL = os.getenv("GROQ_REWRITE_MODEL", _FAST_MODEL)
_REWRITE_MAX_CHARS = 300
_REWRITE_HISTORY_TURNS = 6
_REWRITE_TURN_CHARS = 600

_REWRITE_SYSTEM_PROMPT = textwrap.dedent("""\
    You rewrite the user's latest message into a standalone search query for a
    keyword-based document search engine.

    Rules:
    - Resolve pronouns and references ("it", "that", "those", "more detail",
      "explain further") using the conversation history.
    - Carry over the topic nouns of the turn being followed up on, so the query
      makes sense on its own without the history.
    - If the message already stands on its own, return it unchanged.
    - Keep it short: keywords and topic terms, no full sentences needed.
    - Return only the query text. No quotes, no explanation, no prefix.

    Example:
      History: user "major points about load balancing" / assistant "..."
      Message: "give me more detail about it"
      Output: load balancing types algorithms health checks
    """)


def _fallback_query(question: str, history: list[HistoryTurn]) -> str:
    """No-LLM follow-up handling: reuse the previous question's topic terms."""
    previous = next(
        (turn.content for turn in reversed(history) if turn.role == "user"), ""
    )
    if not previous:
        return question
    return f"{previous} {question}"[:_REWRITE_MAX_CHARS]


def rewrite_query(question: str, history: list[HistoryTurn]) -> str:
    """A follow-up as a self-contained search query.

    Retrieval sees only this string, so "give me more detail about it" has to
    carry its own topic or it matches nothing useful. Never raises: any failure
    degrades to the keyword fallback, and the answer call reports the real error.
    """
    if not history:
        return question

    turns = _history_messages(history)[-_REWRITE_HISTORY_TURNS:]
    if not turns:
        return question

    transcript = "\n".join(
        f"{turn['role']}: {turn['content'][:_REWRITE_TURN_CHARS]}" for turn in turns
    )
    try:
        response = _client().chat.completions.create(
            model=_REWRITE_MODEL,
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"### Conversation\n{transcript}\n\n"
                        f"### Latest message\n{question}\n\n"
                        "### Standalone query"
                    ),
                },
            ],
            temperature=0,
            max_tokens=256,
        )
        rewritten = (response.choices[0].message.content or "").strip().strip('"')
    except (OpenAIError, LLMNotConfigured, IndexError) as exc:
        logger.warning("Query rewrite failed, falling back to keywords: %s", exc)
        return _fallback_query(question, history)

    if not rewritten:
        return _fallback_query(question, history)
    return rewritten[:_REWRITE_MAX_CHARS]


# --------------------------------------------------------------------------- #
# Document summaries
# --------------------------------------------------------------------------- #

_SUMMARY_INPUT_CHARS = 6000
_SUMMARY_MAX_TOKENS = 400

_SUMMARY_SYSTEM_PROMPT = textwrap.dedent("""\
    You write a short factual overview of a document, for a reader who has not
    opened it.

    Rules:
    - Say what the document is, what it covers, and how it is organised.
    - Use only what the excerpt shows. Never guess at what the rest contains.
    - 3 to 6 sentences. Plain text, no markdown, no bullet points.
    - No preamble. Do not start with "This document" every time; vary naturally.
    - Keep the document's own terminology.
    """)


def summarise_document(
    text: str, title: str | None = None, page_count: int = 0
) -> str | None:
    """A short overview of the document, or None if it could not be produced.

    Answers about a document as a whole ("what is this about?") have no single
    chunk to retrieve, so this is written once at ingest and cited alongside
    the chunks. Never raises: a failed summary must not fail an upload.
    """
    excerpt = (text or "").strip()[:_SUMMARY_INPUT_CHARS]
    if not excerpt:
        return None

    header = f"Title: {title or 'unknown'}\nPages: {page_count or 'unknown'}"
    try:
        response = _client().chat.completions.create(
            model=_FAST_MODEL,
            messages=[
                {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"{header}\n\n### Excerpt\n{excerpt}"},
            ],
            temperature=0,
            max_tokens=_SUMMARY_MAX_TOKENS,
        )
        summary = (response.choices[0].message.content or "").strip()
    except (OpenAIError, LLMNotConfigured, IndexError) as exc:
        logger.warning("Document summary skipped: %s", exc)
        return None

    return summary or None


# --------------------------------------------------------------------------- #
# Streaming support
# --------------------------------------------------------------------------- #


def stream_answer_question(
    question: str,
    contexts: list[RetrievedContext],
    history: list[HistoryTurn],
):
    """Yield token chunks from a streaming LLM completion.

    Yields JSON-encoded strings suitable for Server-Sent Events.
    The first event carries source metadata; subsequent events carry answer
    chunks; the final event carries usage statistics.
    """
    messages = [
        {"role": "system", "content": _system_prompt_answer_generating()},
        {"role": "user", "content": f"### Retrieved Contexts\n{build_context_block(contexts)}"},
        {"role": "assistant", "content": "I have read the sources and will answer only from them."},
        *_history_messages(history),
        {"role": "user", "content": question},
    ]

    try:
        stream = _client().chat.completions.create(
            model=_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=800,
            stream=True,
            stream_options={"include_usage": True},
        )
    except OpenAIError as exc:
        logger.exception("LLM streaming request failed")
        yield json.dumps({"error": str(exc)})
        return

    collected = []
    model_name = None
    usage_data = {}

    for chunk in stream:
        if not model_name and chunk.model:
            model_name = chunk.model

        if chunk.usage:
            usage_data = chunk.usage.model_dump() if hasattr(chunk.usage, 'model_dump') else {}

        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                collected.append(delta.content)
                yield json.dumps({"chunk": delta.content})

    full_answer = "".join(collected).strip()
    if not full_answer:
        yield json.dumps({"chunk": FALLBACK_ANSWER})

    yield json.dumps({
        "done": True,
        "model": model_name,
        "usage": usage_data,
    })
