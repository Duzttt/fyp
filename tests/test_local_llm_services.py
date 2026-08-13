import pytest

from app.services.question_suggestions import QuestionSuggestionService


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
