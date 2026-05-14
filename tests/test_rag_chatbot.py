"""
Unit tests for the offline RAG chatbot.

What is covered:
1. Text cleaning + 500/100 word chunking (pdf_processor)
2. Retriever round-trip (add_file -> retrieve -> clear)
3. Threshold-reject branch of /api/chatbot/query
4. No-file branch of /api/chatbot/query
5. Prompt assembly + mode normalization + answer validator

We deliberately call the FastAPI handler `query_chatbot` directly with a
ChatbotRequest model instead of going through TestClient, because:
  - it keeps tests independent of the httpx/starlette version pinned in venv
  - it avoids spinning up the full app (DB migrations, scheduled tasks, etc.)
  - the route logic is what we care about, not the HTTP plumbing.
"""

import asyncio
import pytest

from app.utils import pdf_processor, retriever, ai_tutor
from app.api.chatbot import query_chatbot, ChatbotRequest


# Reset the in-memory index before every test so they don't bleed into each other.
@pytest.fixture(autouse=True)
def _reset_retriever():
    retriever.clear()
    yield
    retriever.clear()


# A small fake "uploaded document" used across multiple tests.
SAMPLE_DOC = (
    "Newton's first law states that an object at rest stays at rest, and an "
    "object in motion stays in motion at constant velocity unless acted upon "
    "by an external unbalanced force. This is also called the law of inertia. "
    "An everyday example is a book lying on a table: it does not move until "
    "someone pushes it."
    "\n\n"
    "Photosynthesis is the process by which green plants convert light energy "
    "into chemical energy stored in glucose. It happens mainly in the leaves "
    "and requires sunlight, carbon dioxide, and water."
)


# ---------------------------------------------------------------------------
# 1. Text cleaning + chunking
# ---------------------------------------------------------------------------
class TestChunking:
    def test_clean_text_collapses_whitespace(self):
        raw = "Hello   world.\n\n\n\nFoo\t\tbar."
        out = pdf_processor.clean_text(raw)
        assert "   " not in out
        assert "\n\n\n" not in out
        assert out.startswith("Hello world.")
        assert "Foo bar" in out

    def test_clean_text_drops_unreadable_bytes(self):
        # \x00 is a control byte that should be stripped.
        raw = "Good\x00 text here"
        out = pdf_processor.clean_text(raw)
        assert "\x00" not in out
        assert "Good" in out and "text here" in out

    def test_chunk_text_500_with_100_overlap(self):
        text = " ".join(["word"] * 1200)
        chunks = pdf_processor.chunk_text(text, chunk_words=500, overlap_words=100)
        # 1200 words, step = 500-100 = 400 -> chunks start at 0, 400, 800 = 3 chunks
        assert len(chunks) == 3
        assert len(chunks[0].split()) == 500
        # last chunk covers the tail
        assert len(chunks[-1].split()) <= 500

    def test_chunk_text_empty_input(self):
        assert pdf_processor.chunk_text("") == []
        assert pdf_processor.chunk_text("   ") == []

    def test_chunk_text_shorter_than_window(self):
        # 50 words -> single chunk
        text = " ".join(["w"] * 50)
        chunks = pdf_processor.chunk_text(text, chunk_words=500, overlap_words=100)
        assert len(chunks) == 1
        assert len(chunks[0].split()) == 50


# ---------------------------------------------------------------------------
# 2. Retriever round-trip
# ---------------------------------------------------------------------------
class TestRetriever:
    def test_empty_store_has_no_content(self):
        assert retriever.has_content() is False
        chunks, srcs, sim = retriever.retrieve("anything", top_k=3)
        assert chunks == [] and srcs == [] and sim == 0.0

    def test_add_file_and_retrieve_top_chunk(self):
        chunks = [
            "Newton's first law: an object at rest stays at rest.",
            "Photosynthesis converts light into chemical energy in plants.",
            "The mitochondria is the powerhouse of the cell.",
        ]
        n = retriever.add_file("physics.pdf", chunks)
        assert n == 3
        assert retriever.has_content() is True
        assert retriever.list_files() == ["physics.pdf"]

        top, srcs, sim = retriever.retrieve("what is newton first law", top_k=2)
        assert len(top) == 2
        assert "Newton" in top[0]
        assert srcs[0] == "physics.pdf"
        assert sim >= retriever.SIMILARITY_THRESHOLD

    def test_clear_wipes_index(self):
        retriever.add_file("a.txt", ["only chunk"])
        assert retriever.has_content() is True
        retriever.clear()
        assert retriever.has_content() is False
        assert retriever.list_files() == []


# ---------------------------------------------------------------------------
# Small helper to call the async FastAPI handler from a sync test.
# ---------------------------------------------------------------------------
def _run_query(message: str, mode: str = "normal"):
    req = ChatbotRequest(message=message, mode=mode)
    return asyncio.run(query_chatbot(req))


# ---------------------------------------------------------------------------
# 3. /query - no-file branch
# ---------------------------------------------------------------------------
class TestQueryNoFile:
    def test_returns_no_file_message_when_index_empty(self):
        # autouse fixture already cleared the retriever
        result = _run_query("explain photosynthesis", mode="normal")
        assert result["response"] == ai_tutor.NO_FILE_MESSAGE
        assert result["sources"] == []


# ---------------------------------------------------------------------------
# 4. /query - threshold-reject branch
# ---------------------------------------------------------------------------
class TestQueryThresholdReject:
    def test_unrelated_question_is_rejected_before_calling_ollama(self):
        # Upload some physics content...
        retriever.add_file("physics.txt", [SAMPLE_DOC])
        # ...then ask something completely unrelated.
        result = _run_query("Who is Virat Kohli?", mode="normal")
        # The retriever's cosine similarity is below SIMILARITY_THRESHOLD so
        # the route short-circuits with the canned message - no model call.
        assert result["response"] == ai_tutor.NOT_IN_MATERIAL_MESSAGE
        assert result["sources"] == []


# ---------------------------------------------------------------------------
# 5. Prompt assembly, mode normalization, answer validator
# ---------------------------------------------------------------------------
class TestPromptAndValidator:
    def test_normalize_mode_accepts_ui_labels(self):
        assert ai_tutor.normalize_mode("Normal Answer") == "normal"
        assert ai_tutor.normalize_mode("explain simply") == "simple"
        assert ai_tutor.normalize_mode("Explain-with-Example") == "example"
        assert ai_tutor.normalize_mode("Give Exam Answer") == "exam"
        assert ai_tutor.normalize_mode("Summarize") == "summary"
        # unknown -> normal
        assert ai_tutor.normalize_mode("gibberish") == "normal"
        assert ai_tutor.normalize_mode(None) == "normal"

    def test_build_prompt_embeds_context_question_and_mode(self):
        prompt = ai_tutor.build_prompt(
            ["Newton's first law: object at rest stays at rest."],
            "what is newtons first law",
            "exam",
        )
        assert "E-Shiksha" in prompt
        assert "Newton's first law" in prompt           # context injected
        assert "what is newtons first law" in prompt    # question injected
        assert "Give Exam Answer" in prompt             # mode directive injected
        assert "## Definition" in prompt                # exam recipe spelled out
        assert "Follow-up:" in prompt                   # tutor follow-up rule

    def test_validator_accepts_grounded_answer(self):
        ok, reason = ai_tutor.validate_answer(
            "Newton's first law says an object at rest stays at rest.",
            ["Newton's first law states that an object at rest stays at rest."],
        )
        assert ok is True, reason

    def test_validator_rejects_out_of_context_answer(self):
        ok, reason = ai_tutor.validate_answer(
            "Virat Kohli is an Indian cricketer who scored many centuries.",
            ["Newton's first law states that an object at rest stays at rest."],
        )
        assert ok is False
        assert reason.startswith("low-overlap")

    def test_validator_rejects_refusal_patterns(self):
        ok, _ = ai_tutor.validate_answer(
            "As an AI language model, I cannot answer that.",
            ["any context"],
        )
        assert ok is False

    def test_validator_preserves_canned_not_in_material_message(self):
        ok, reason = ai_tutor.validate_answer(
            ai_tutor.NOT_IN_MATERIAL_MESSAGE, []
        )
        assert ok is True
        assert reason == "refusal-by-design"

    def test_ai_mode_default_is_ollama(self):
        # Sanity-check that the offline backend is the default.
        assert ai_tutor.AI_MODE == "ollama"
