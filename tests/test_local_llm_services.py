import pytest

from app.services.question_suggestions import QuestionSuggestionService
from app.services.summarizer import DocumentSummarizer


def test_question_suggestions_dispatches_to_local_llm(
    monkeypatch: pytest.MonkeyPatch,
):
    service = QuestionSuggestionService(llm_provider="local_llm")
    monkeypatch.setattr(
        service,
        "_call_local_llm",
        lambda prompt: f"local: {prompt}",
    )

    assert service._call_llm("question prompt") == "local: question prompt"


def test_summarizer_dispatches_to_local_llm(
    monkeypatch: pytest.MonkeyPatch,
):
    service = DocumentSummarizer(llm_provider="local_llm", model="test-model")
    monkeypatch.setattr(
        service,
        "_call_local_llm",
        lambda prompt, response_format=None: f"local: {prompt}",
    )

    assert service._call_llm("summary prompt") == "local: summary prompt"
