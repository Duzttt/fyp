import json
import os

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

from app.services.mcq_generator import (  # noqa: E402
    MCQGenerationError,
    MCQGeneratorService,
)


@pytest.fixture(autouse=True)
def patch_runtime(monkeypatch):
    monkeypatch.setattr(
        "app.services.mcq_generator.load_runtime_llm_settings",
        lambda: {
            "provider": "local_llm",
            "model": "qwen2.5-3b",
            "api_key": None,
            "base_url": "http://127.0.0.1:8080",
        },
    )


def _service() -> MCQGeneratorService:
    return MCQGeneratorService(llm_provider="local_llm")


def _documents() -> list:
    return [
        {
            "name": "lecture1.pdf",
            "content": "Retrieval-augmented generation combines retrieval "
            "and generation to answer questions.",
        }
    ]


VALID_ITEM = {
    "question": "What is RAG?",
    "options": {
        "A": "Retrieval-augmented generation",
        "B": "Random access graphics",
        "C": "Rapid answer generator",
        "D": "None of the above",
    },
    "correct_answer": "A",
    "explanation": "RAG stands for retrieval-augmented generation.",
    "difficulty": "easy",
    "source_doc": "lecture1.pdf",
}


def test_build_prompt_includes_context_and_config():
    prompt = _service()._build_prompt(_documents(), 5, "medium")
    assert "lecture1.pdf" in prompt
    assert "EXACTLY 5" in prompt
    assert "understanding and explanation" in prompt


def test_build_prompt_mixed_difficulty():
    prompt = _service()._build_prompt(_documents(), 3, "mixed")
    assert "roughly one third easy" in prompt


def test_parse_json_response_plain():
    data = _service()._parse_json_response(json.dumps({"questions": [VALID_ITEM]}))
    assert data["questions"][0]["correct_answer"] == "A"


def test_parse_json_response_with_code_fences():
    raw = "```json\n" + json.dumps({"questions": [VALID_ITEM]}) + "\n```"
    data = _service()._parse_json_response(raw)
    assert len(data["questions"]) == 1


def test_parse_json_response_with_leading_text():
    raw = "Here is the quiz:\n" + json.dumps({"questions": [VALID_ITEM]})
    data = _service()._parse_json_response(raw)
    assert len(data["questions"]) == 1


def test_parse_json_response_invalid_raises():
    with pytest.raises(MCQGenerationError):
        _service()._parse_json_response("this is not json")


def test_parse_json_response_empty_raises():
    with pytest.raises(MCQGenerationError):
        _service()._parse_json_response("")


def test_validate_questions_valid_returns_normalized():
    questions = _service()._validate_questions({"questions": [VALID_ITEM]}, 1)
    assert len(questions) == 1
    assert questions[0]["question"] == "What is RAG?"
    assert questions[0]["options"]["A"] == "Retrieval-augmented generation"
    assert questions[0]["correct_answer"] == "A"
    assert questions[0]["explanation"]
    assert questions[0]["source_doc"] == "lecture1.pdf"


def test_validate_questions_missing_option_raises():
    bad = {**VALID_ITEM, "options": {"A": "1", "B": "2", "C": "3"}}
    with pytest.raises(MCQGenerationError):
        _service()._validate_questions({"questions": [bad]}, 1)


def test_validate_questions_invalid_answer_raises():
    bad = {**VALID_ITEM, "correct_answer": "E"}
    with pytest.raises(MCQGenerationError):
        _service()._validate_questions({"questions": [bad]}, 1)


def test_validate_questions_missing_explanation_raises():
    bad = {**VALID_ITEM, "explanation": ""}
    with pytest.raises(MCQGenerationError):
        _service()._validate_questions({"questions": [bad]}, 1)


def test_validate_questions_wrong_count_raises():
    with pytest.raises(MCQGenerationError):
        _service()._validate_questions({"questions": [VALID_ITEM]}, 3)


def test_validate_questions_defaults_difficulty():
    item = {k: v for k, v in VALID_ITEM.items() if k != "difficulty"}
    questions = _service()._validate_questions({"questions": [item]}, 1)
    assert questions[0]["difficulty"] == "medium"


def test_validate_questions_truncates_extra_questions():
    questions = _service()._validate_questions(
        {"questions": [VALID_ITEM, VALID_ITEM, VALID_ITEM]}, 2
    )
    assert len(questions) == 2


def _json_response(items):
    return json.dumps({"questions": items})


def _mock_llm(monkeypatch, side_effect):
    from unittest.mock import MagicMock

    mock = MagicMock(side_effect=side_effect)
    monkeypatch.setattr("app.services.llm_client.call_llm", mock)
    return mock


def test_generate_mcqs_success(monkeypatch):
    mock = _mock_llm(monkeypatch, [_json_response([VALID_ITEM])])
    questions = _service().generate_mcqs(_documents(), num_questions=1)
    assert len(questions) == 1
    assert questions[0]["question"] == "What is RAG?"
    assert mock.call_count == 1
    assert mock.call_args.kwargs["call_type"] == "mcq"
    assert mock.call_args.kwargs["provider"] == "local_llm"


def test_generate_mcqs_retries_then_succeeds(monkeypatch):
    mock = _mock_llm(monkeypatch, ["not json at all", _json_response([VALID_ITEM])])
    questions = _service().generate_mcqs(_documents(), num_questions=1)
    assert len(questions) == 1
    assert mock.call_count == 2


def test_generate_mcqs_all_retries_fail(monkeypatch):
    mock = _mock_llm(monkeypatch, ["bad", "still bad", "nope"])
    with pytest.raises(MCQGenerationError):
        _service().generate_mcqs(_documents(), num_questions=1)
    assert mock.call_count == 3


def test_generate_mcqs_timeout_raises(monkeypatch):
    import time

    def slow_llm(**kwargs):
        time.sleep(0.2)
        return _json_response([VALID_ITEM])

    mock = _mock_llm(monkeypatch, slow_llm)
    with pytest.raises(MCQGenerationError, match="timed out"):
        _service().generate_mcqs(_documents(), num_questions=1, timeout_seconds=0.05)
    assert mock.call_count == 1


def test_generate_mcqs_empty_documents_raises():
    with pytest.raises(MCQGenerationError):
        _service().generate_mcqs([], num_questions=1)


def test_generate_mcqs_clamps_num_questions(monkeypatch):
    items = [{**VALID_ITEM, "question": f"Q{i}?"} for i in range(20)]
    mock = _mock_llm(monkeypatch, [_json_response(items)])
    questions = _service().generate_mcqs(_documents(), num_questions=99)
    assert len(questions) == 20
    prompt = mock.call_args.kwargs["messages"][0]["content"]
    assert "EXACTLY 20" in prompt


def test_provider_gemini_routing(monkeypatch):
    class FakeSettings:
        GEMINI_API_KEY = "test-key"
        GEMINI_MODEL = "gemini-2.0-flash"
        GEMINI_BASE_URL = "https://example.invalid/v1beta"
        LLM_PROVIDER = "local_llm"

    monkeypatch.setattr("app.services.mcq_generator.settings", FakeSettings)
    mock = _mock_llm(monkeypatch, [_json_response([VALID_ITEM])])
    service = MCQGeneratorService(llm_provider="gemini")
    questions = service.generate_mcqs(_documents(), num_questions=1)
    assert len(questions) == 1
    assert mock.call_args.kwargs["provider"] == "gemini"
    assert mock.call_args.kwargs["response_format"] == "json"
    assert mock.call_args.kwargs["api_key"] == "test-key"
