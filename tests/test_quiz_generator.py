"""Unit tests for the QuizGenerator service."""

import json

import pytest

from app.services.quiz_generator import QuizGenerationError, QuizGenerator

SINGLE_Q = {
    "type": "single",
    "text": "What does RAG stand for?",
    "options": [
        "Retrieval-Augmented Generation",
        "Random Access Gateway",
        "Rapid Answer Generator",
        "None of the above",
    ],
    "answer": [0],
    "explanation": "RAG stands for Retrieval-Augmented Generation.",
}

MULTI_Q = {
    "type": "multiple",
    "text": "Which components are part of a RAG pipeline?",
    "options": ["Retriever", "Generator", "Battery", "Water pump"],
    "answer": [0, 1],
    "explanation": "A RAG pipeline has a retriever and a generator.",
}

DOCS = [{"name": "lec1.pdf", "text": "RAG combines retrieval with generation."}]


def _config(num, single, multiple, difficulty="medium"):
    return {
        "num_questions": num,
        "difficulty": difficulty,
        "question_types": {"single": single, "multiple": multiple},
    }


def _make_generator():
    return QuizGenerator(llm_provider="local_llm", model="test-model")


def _patch_llm(monkeypatch, responses):
    responses = list(responses)

    def fake_call_llm(**kwargs):
        return responses.pop(0)

    monkeypatch.setattr("app.services.quiz_generator.call_llm", fake_call_llm)
    return responses


def test_generate_quiz_parses_valid_json(monkeypatch):
    _patch_llm(monkeypatch, [json.dumps([SINGLE_Q, MULTI_Q, SINGLE_Q])])
    result = _make_generator().generate_quiz(DOCS, _config(3, 2, 1))
    assert len(result["questions"]) == 3
    assert result["questions"][0]["answer"] == [0]
    assert result["questions"][1]["answer"] == [0, 1]


def test_generate_quiz_retries_after_invalid_json(monkeypatch):
    responses = _patch_llm(
        monkeypatch, ["not json at all", json.dumps([SINGLE_Q, SINGLE_Q])]
    )
    result = _make_generator().generate_quiz(DOCS, _config(2, 2, 0))
    assert len(result["questions"]) == 2
    assert responses == []


def test_generate_quiz_raises_after_two_failures(monkeypatch):
    _patch_llm(monkeypatch, ["garbage", "still garbage"])
    with pytest.raises(QuizGenerationError):
        _make_generator().generate_quiz(DOCS, _config(1, 1, 0))


def test_generate_quiz_retries_on_count_mismatch(monkeypatch):
    responses = _patch_llm(
        monkeypatch, [json.dumps([SINGLE_Q]), json.dumps([SINGLE_Q, MULTI_Q])]
    )
    result = _make_generator().generate_quiz(DOCS, _config(2, 1, 1))
    assert len(result["questions"]) == 2
    assert responses == []


def test_generate_quiz_drops_questions_with_out_of_range_answer(monkeypatch):
    bad = {**SINGLE_Q, "answer": [9]}
    _patch_llm(monkeypatch, [json.dumps([SINGLE_Q, bad, MULTI_Q])])
    result = _make_generator().generate_quiz(DOCS, _config(2, 1, 1))
    assert len(result["questions"]) == 2
    assert all(q["type"] != "single" or q["answer"] == [0] for q in result["questions"])


def test_generate_quiz_parses_markdown_fenced_json(monkeypatch):
    payload = "```json\n" + json.dumps([SINGLE_Q]) + "\n```"
    _patch_llm(monkeypatch, [payload])
    result = _make_generator().generate_quiz(DOCS, _config(1, 1, 0))
    assert len(result["questions"]) == 1


def test_generate_quiz_accepts_dict_wrapped_questions(monkeypatch):
    _patch_llm(monkeypatch, [json.dumps({"questions": [SINGLE_Q]})])
    result = _make_generator().generate_quiz(DOCS, _config(1, 1, 0))
    assert len(result["questions"]) == 1


def test_generate_quiz_rejects_questions_with_fewer_than_two_options(monkeypatch):
    one_option = {**SINGLE_Q, "options": ["only one"]}
    _patch_llm(monkeypatch, [json.dumps([one_option, MULTI_Q])])
    result = _make_generator().generate_quiz(DOCS, _config(1, 0, 1))
    assert len(result["questions"]) == 1
    assert result["questions"][0]["type"] == "multiple"


def test_generate_quiz_rejects_questions_without_explanation(monkeypatch):
    no_explanation = {**SINGLE_Q, "explanation": ""}
    _patch_llm(monkeypatch, [json.dumps([no_explanation, SINGLE_Q])])
    result = _make_generator().generate_quiz(DOCS, _config(1, 1, 0))
    assert len(result["questions"]) == 1


def test_generate_quiz_raises_without_documents():
    with pytest.raises(QuizGenerationError):
        _make_generator().generate_quiz([], _config(1, 1, 0))
