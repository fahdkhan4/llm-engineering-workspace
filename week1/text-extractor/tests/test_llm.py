"""Unit tests for the LLM client layer.

Uses a scripted fake client — no network calls, no API key required.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Ensure the project root is importable.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --------------------------------------------------------------------------- #
# Fake OpenAI response builders
# --------------------------------------------------------------------------- #


def _make_response(
    content: str = "Test answer",
    model: str = "fake-model",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
):
    """Build a fake OpenAI ChatCompletion response."""
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        model_dump=lambda: {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    )
    message = SimpleNamespace(content=content, role="assistant")
    choice = SimpleNamespace(message=message, index=0, finish_reason="stop")
    return SimpleNamespace(choices=[choice], model=model, usage=usage)


def _make_empty_response():
    """A response where the model returned empty/whitespace content."""
    return _make_response(content="")


def _make_whitespace_response():
    """A response where the model returned only whitespace."""
    return _make_response(content="   \n  ")


def _make_none_response():
    """A response where message.content is None."""
    return _make_response(content=None)


class _FakeCompletions:
    """Records calls and returns scripted responses."""

    def __init__(self, responses: list | None = None):
        self._responses = list(responses) if responses else [_make_response()]
        self._call_count = 0
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        self._call_count += 1
        if self._call_count <= len(self._responses):
            resp = self._responses[self._call_count - 1]
        else:
            resp = self._responses[-1]
        if isinstance(resp, Exception):
            raise resp
        return resp


class _FakeChat:
    def __init__(self, completions: _FakeCompletions):
        self.completions = completions


class _FakeClient:
    def __init__(self, responses: list | None = None):
        self._completions = _FakeCompletions(responses)
        self.chat = _FakeChat(self._completions)

    @property
    def call_count(self) -> int:
        return self._completions._call_count

    @property
    def calls(self) -> list[dict]:
        return self._completions.calls


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _clean_imports(monkeypatch):
    """Set GROQ_API_KEY so LLMNotConfigured is not raised."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    # Clear the lru_cache on _client so our patches take effect.
    from llm import llm_client
    llm_client._client.cache_clear()
    yield
    llm_client._client.cache_clear()


def _patch_client(fake: _FakeClient):
    """Patch _client() to return our fake."""
    return patch("llm.llm_client._client", return_value=fake)


def _dummy_contexts():
    from llm.llm_client import RetrievedContext
    return [
        RetrievedContext(
            chunk_id=1,
            document_id=1,
            document_name="test.pdf",
            section_title="Intro",
            page_start=1,
            page_end=1,
            content="This is test context content.",
            score=0.95,
        )
    ]


# --------------------------------------------------------------------------- #
# 1. Empty/whitespace LLM response → fallback string, never ""
# --------------------------------------------------------------------------- #


class TestFallbackOnEmptyResponse:
    """Guarantee the strict return contract: never return an empty answer."""

    def test_empty_content_returns_fallback(self):
        from llm.llm_client import FALLBACK_ANSWER, answer_question

        fake = _FakeClient([_make_empty_response()])
        with _patch_client(fake):
            result = answer_question("What is X?", _dummy_contexts(), [])

        assert result.answer == FALLBACK_ANSWER
        assert result.answer != ""

    def test_whitespace_content_returns_fallback(self):
        from llm.llm_client import FALLBACK_ANSWER, answer_question

        fake = _FakeClient([_make_whitespace_response()])
        with _patch_client(fake):
            result = answer_question("What is X?", _dummy_contexts(), [])

        assert result.answer == FALLBACK_ANSWER

    def test_none_content_returns_fallback(self):
        from llm.llm_client import FALLBACK_ANSWER, answer_question

        fake = _FakeClient([_make_none_response()])
        with _patch_client(fake):
            result = answer_question("What is X?", _dummy_contexts(), [])

        assert result.answer == FALLBACK_ANSWER

    def test_valid_content_returned_as_is(self):
        from llm.llm_client import FALLBACK_ANSWER, answer_question

        fake = _FakeClient([_make_response(content="The answer is 42.")])
        with _patch_client(fake):
            result = answer_question("What is X?", _dummy_contexts(), [])

        assert result.answer == "The answer is 42."
        assert result.answer != FALLBACK_ANSWER


# --------------------------------------------------------------------------- #
# 2. API call count — 1 for standalone, 2 for follow-up needing rewrite
# --------------------------------------------------------------------------- #


class TestCallCount:
    """Verify the expected number of LLM API calls."""

    def test_standalone_query_makes_one_call(self):
        from llm.llm_client import answer_question

        fake = _FakeClient([_make_response()])
        with _patch_client(fake):
            answer_question("What is sharding?", _dummy_contexts(), [])

        assert fake.call_count == 1, "A standalone query should make exactly 1 LLM call"

    def test_followup_query_makes_two_calls(self):
        from llm.llm_client import HistoryTurn, answer_question, rewrite_query

        history = [
            HistoryTurn(role="user", content="What is sharding?"),
            HistoryTurn(role="assistant", content="Sharding splits data across servers."),
        ]
        rewrite_response = _make_response(content="sharding partition key types")
        answer_response = _make_response(content="The partition key determines...")

        fake = _FakeClient([rewrite_response, answer_response])
        with _patch_client(fake):
            rewritten = rewrite_query("Tell me more about it", history)
            result = answer_question(rewritten, _dummy_contexts(), history)

        assert fake.call_count == 2, "A follow-up should make exactly 2 LLM calls (rewrite + answer)"


# --------------------------------------------------------------------------- #
# 3. Rate limit (429) & timeout handling
# --------------------------------------------------------------------------- #


class TestErrorHandling:
    """Verify graceful degradation on API errors."""

    def test_rate_limit_429_in_rewrite_falls_back(self):
        from openai import RateLimitError
        from llm.llm_client import HistoryTurn, rewrite_query

        # Build a minimal 429 error
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.json.return_value = {"error": {"message": "rate limited"}}
        error = RateLimitError(
            message="rate limited",
            response=mock_response,
            body={"error": {"message": "rate limited"}},
        )

        history = [
            HistoryTurn(role="user", content="What is caching?"),
            HistoryTurn(role="assistant", content="Caching stores frequent data."),
        ]
        fake = _FakeClient([error])
        with _patch_client(fake):
            result = rewrite_query("Tell me more", history)

        # Should fall back to keyword concatenation, not raise
        assert isinstance(result, str)
        assert len(result) > 0

    def test_timeout_in_answer_raises_llm_not_configured(self):
        from openai import APITimeoutError
        from llm.llm_client import LLMNotConfigured, answer_question

        error = APITimeoutError(request=MagicMock())
        fake = _FakeClient([error])
        with _patch_client(fake):
            with pytest.raises(LLMNotConfigured, match="LLM request failed"):
                answer_question("What is X?", _dummy_contexts(), [])


# --------------------------------------------------------------------------- #
# 4. Token usage propagation
# --------------------------------------------------------------------------- #


class TestUsagePropagation:
    """Verify that token counts flow through to the response."""

    def test_usage_dict_contains_token_counts(self):
        from llm.llm_client import answer_question

        fake = _FakeClient([
            _make_response(prompt_tokens=200, completion_tokens=80)
        ])
        with _patch_client(fake):
            result = answer_question("What is X?", _dummy_contexts(), [])

        assert result.usage is not None
        assert result.usage["prompt_tokens"] == 200
        assert result.usage["completion_tokens"] == 80
        assert result.usage["total_tokens"] == 280

    def test_model_name_is_propagated(self):
        from llm.llm_client import answer_question

        fake = _FakeClient([_make_response(model="test-model-v2")])
        with _patch_client(fake):
            result = answer_question("What is X?", _dummy_contexts(), [])

        assert result.model == "test-model-v2"


# --------------------------------------------------------------------------- #
# 5. Max tokens is set
# --------------------------------------------------------------------------- #


class TestMaxTokensSet:
    """Verify max_tokens is passed in the API call."""

    def test_answer_question_sets_max_tokens(self):
        from llm.llm_client import answer_question

        fake = _FakeClient([_make_response()])
        with _patch_client(fake):
            answer_question("What is X?", _dummy_contexts(), [])

        assert fake.calls[0].get("max_tokens") == 800

    def test_rewrite_uses_fast_model(self):
        from llm.llm_client import HistoryTurn, rewrite_query

        history = [
            HistoryTurn(role="user", content="What is caching?"),
            HistoryTurn(role="assistant", content="Caching stores data."),
        ]
        fake = _FakeClient([_make_response(content="caching strategies")])
        with _patch_client(fake):
            rewrite_query("Tell me more", history)

        from llm.llm_client import _FAST_MODEL, _MODEL

        used_model = fake.calls[0].get("model", "")
        # Should use the fast model, not the main model
        assert used_model == _FAST_MODEL != _MODEL

    def test_summary_uses_fast_model(self):
        from llm.llm_client import _FAST_MODEL, _MODEL, summarise_document

        fake = _FakeClient([_make_response(content="This document is an overview.")])
        with _patch_client(fake):
            summarise_document("Sample document text for summarisation.")

        used_model = fake.calls[0].get("model", "")
        assert used_model == _FAST_MODEL != _MODEL


# --------------------------------------------------------------------------- #
# 6. Session Limits & AnswerResponse.usage Propagation via qa_service
# --------------------------------------------------------------------------- #


class TestQAServiceIntegration:
    """Verify session limits and schema usage propagation in qa_service."""

    @pytest.fixture
    def test_db(self, tmp_path):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base
        from database.session import _add_missing_columns

        db_url = f"sqlite:///{tmp_path / 'qa_test.db'}"
        test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(test_engine)
        _add_missing_columns(test_engine)

        Session = sessionmaker(bind=test_engine)
        session = Session()
        yield session
        session.close()

    def test_answer_response_usage_contains_token_counts(self, test_db, monkeypatch):
        from service import qa_service
        from schema.chat_schema import AnswerResponse

        # Return mock hits so we don't need real documents
        mock_hit = SimpleNamespace(
            chunk=SimpleNamespace(
                id=1,
                document_id=1,
                filename="test.pdf",
                document=SimpleNamespace(filename="test.pdf"),
                section_title="Intro",
                page_start=1,
                page_end=1,
                content="System design principles.",
            ),
            score=0.9,
        )
        monkeypatch.setattr(
            "repository.document_repository.search_chunks",
            lambda *args, **kwargs: [mock_hit],
        )

        fake = _FakeClient([
            _make_response(
                content="Here is the grounded answer [1].",
                prompt_tokens=150,
                completion_tokens=40,
            )
        ])
        with _patch_client(fake):
            response = qa_service.ask(test_db, "What is system design?")

        assert isinstance(response, AnswerResponse)
        assert response.usage is not None
        assert response.usage["prompt_tokens"] == 150
        assert response.usage["completion_tokens"] == 40
        assert response.usage["total_tokens"] == 190

    def test_hard_session_turns_limit_exceeded(self, test_db, monkeypatch):
        from service import qa_service
        from repository import chat_repository
        from database.models import MessageRole

        # Set max_session_turns to a small number
        monkeypatch.setattr("config.settings.max_session_turns", 2)

        fake = _FakeClient([_make_response(content="Initial answer")])
        session = chat_repository.get_or_create_session(test_db, "test-limit-session", None)

        # Pre-seed messages exceeding max_session_turns (2)
        chat_repository.add_message(test_db, session, MessageRole.USER, "Q1")
        chat_repository.add_message(test_db, session, MessageRole.ASSISTANT, "A1")
        chat_repository.add_message(test_db, session, MessageRole.USER, "Q2")

        with _patch_client(fake):
            response = qa_service.ask(test_db, "Q3", session_key="test-limit-session")

        assert "reached its turn limit" in response.answer
        # Ensure LLM was not called after exceeding turn limit
        assert fake.call_count == 0

    def test_hard_session_tokens_limit_exceeded(self, test_db, monkeypatch):
        from service import qa_service
        from repository import chat_repository
        from database.models import MessageRole

        monkeypatch.setattr("config.settings.max_session_tokens", 500)

        fake = _FakeClient([_make_response(content="Answer")])
        session = chat_repository.get_or_create_session(test_db, "test-token-limit-session", None)

        # Seed turn with 600 tokens (exceeds 500 token limit)
        chat_repository.add_message(
            test_db, session, MessageRole.ASSISTANT, "Previous long answer", token_count=600
        )

        with _patch_client(fake):
            response = qa_service.ask(test_db, "Next question", session_key="test-token-limit-session")

        assert "reached its turn limit" in response.answer
        # Ensure LLM was not called
        assert fake.call_count == 0


# --------------------------------------------------------------------------- #
# 7. Streaming Support Tests
# --------------------------------------------------------------------------- #


class TestStreaming:
    """Verify stream_answer_question and ask_stream SSE format."""

    def test_stream_answer_question_yields_chunks(self):
        import json
        from llm.llm_client import stream_answer_question

        # Mock stream chunks
        chunk1 = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello "))],
            model="gpt-test",
            usage=None,
        )
        chunk2 = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="world!"))],
            model="gpt-test",
            usage=None,
        )
        chunk3 = SimpleNamespace(
            choices=[],
            model="gpt-test",
            usage=SimpleNamespace(
                model_dump=lambda: {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}
            ),
        )

        mock_completions = MagicMock()
        mock_completions.create.return_value = iter([chunk1, chunk2, chunk3])
        mock_client = MagicMock(chat=MagicMock(completions=mock_completions))

        with patch("llm.llm_client._client", return_value=mock_client):
            events = list(stream_answer_question("test?", _dummy_contexts(), []))

        chunks = [json.loads(e) for e in events]
        text = "".join(c["chunk"] for c in chunks if "chunk" in c)
        assert text == "Hello world!"
        assert any(c.get("done") is True for c in chunks)
        final_event = next(c for c in chunks if c.get("done"))
        assert final_event["usage"]["total_tokens"] == 12

    def test_ask_stream_yields_sse_with_metadata_first(self, tmp_path, monkeypatch):
        import json
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base, ChatMessage, MessageRole
        from database.session import _add_missing_columns
        from service import qa_service

        db_url = f"sqlite:///{tmp_path / 'stream_test.db'}"
        test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(test_engine)
        _add_missing_columns(test_engine)

        Session = sessionmaker(bind=test_engine)
        session = Session()

        mock_hit = SimpleNamespace(
            chunk=SimpleNamespace(
                id=1,
                document_id=1,
                filename="doc.pdf",
                document=SimpleNamespace(filename="doc.pdf"),
                section_title="Architecture",
                page_start=1,
                page_end=2,
                content="Distributed caching reduces DB load.",
            ),
            score=0.88,
        )
        monkeypatch.setattr(
            "repository.document_repository.search_chunks",
            lambda *args, **kwargs: [mock_hit],
        )

        stream_events = [
            json.dumps({"chunk": "Distributed "}),
            json.dumps({"chunk": "caching."}),
            json.dumps({"done": True, "model": "test-model", "usage": {"total_tokens": 45}}),
        ]
        monkeypatch.setattr(
            "service.qa_service.stream_answer_question",
            lambda *args, **kwargs: stream_events,
        )

        sse_output = list(qa_service.ask_stream(session, "Explain caching"))

        # Verify SSE event wire protocol
        assert all(e.startswith("data: ") and e.endswith("\n\n") for e in sse_output)

        # First event MUST be the sources metadata
        first_payload = json.loads(sse_output[0].replace("data: ", "").strip())
        assert "sources" in first_payload
        assert len(first_payload["sources"]) == 1
        assert first_payload["sources"][0]["document_name"] == "doc.pdf"
        assert "session_key" in first_payload

        # Subsequent events are chunks
        second_payload = json.loads(sse_output[1].replace("data: ", "").strip())
        assert second_payload["chunk"] == "Distributed "

        # Check that assistant message was persisted with tokens
        assistant_msgs = session.query(ChatMessage).filter_by(role=MessageRole.ASSISTANT).all()
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].content == "Distributed caching."
        assert assistant_msgs[0].token_count == 45
        session.close()
