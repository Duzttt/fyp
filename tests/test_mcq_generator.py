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
    data = _service()._parse_json_response(
        json.dumps({"questions": [VALID_ITEM]})
    )
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
    questions = _service()._validate_questions(
        {"questions": [VALID_ITEM]}, 1
    )
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
