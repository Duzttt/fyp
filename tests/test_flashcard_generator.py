"""Unit tests for the FlashcardGenerator service."""

import json

import pytest

from app.services.flashcard_generator import (
    FlashcardGenerationError,
    FlashcardGenerator,
)

CARD_A = {
    "front": "What does RAG stand for?",
    "back": "Retrieval-Augmented Generation.",
    "hint": "Three words, starts with Retrieval.",
    "tags": ["rag", "basics"],
}

CARD_B = {
    "front": "Name one component of a RAG pipeline.",
    "back": "A retriever.",
    "hint": "It fetches relevant passages.",
    "tags": ["architecture"],
}

DOCS = [{"name": "lec1.pdf", "text": "RAG combines retrieval with generation."}]


def _config(num, topic=""):
    return {"num_cards": num, "topic": topic}


def _make_generator():
    return FlashcardGenerator(llm_provider="local_llm", model="test-model")


def _patch_llm(monkeypatch, responses):
    responses = list(responses)

    def fake_call_llm(**kwargs):
        if responses:
            return responses.pop(0)
        return "exhausted fallback: not valid json"

    monkeypatch.setattr("app.services.flashcard_generator.call_llm", fake_call_llm)
    return responses


def test_generate_parses_valid_json(monkeypatch):
    _patch_llm(monkeypatch, [json.dumps([CARD_A, CARD_B])])
    result = _make_generator().generate(DOCS, _config(2))
    assert len(result["cards"]) == 2
    assert result["cards"][0]["front"] == CARD_A["front"]
    assert result["cards"][0]["tags"] == ["rag", "basics"]


def test_generate_retries_after_invalid_json(monkeypatch):
    responses = _patch_llm(monkeypatch, ["not json at all", json.dumps([CARD_A])])
    result = _make_generator().generate(DOCS, _config(1))
    assert len(result["cards"]) == 1
    assert responses == []


def test_generate_raises_after_two_failures(monkeypatch):
    _patch_llm(monkeypatch, ["garbage", "still garbage"])
    with pytest.raises(FlashcardGenerationError):
        _make_generator().generate(DOCS, _config(1))


def test_generate_retries_on_count_mismatch(monkeypatch):
    responses = _patch_llm(
        monkeypatch, [json.dumps([CARD_A]), json.dumps([CARD_A, CARD_B])]
    )
    result = _make_generator().generate(DOCS, _config(2))
    assert len(result["cards"]) == 2
    assert responses == []


def test_generate_drops_cards_missing_back(monkeypatch):
    bad = {"front": "Only front, no back."}
    _patch_llm(monkeypatch, [json.dumps([CARD_A, bad, CARD_B])])
    result = _make_generator().generate(DOCS, _config(2))
    assert len(result["cards"]) == 2


def test_generate_drops_cards_missing_front(monkeypatch):
    bad = {"back": "Only back, no front."}
    _patch_llm(monkeypatch, [json.dumps([bad, CARD_A])])
    result = _make_generator().generate(DOCS, _config(1))
    assert len(result["cards"]) == 1


def test_generate_parses_markdown_fenced_json(monkeypatch):
    payload = "```json\n" + json.dumps([CARD_A]) + "\n```"
    _patch_llm(monkeypatch, [payload])
    result = _make_generator().generate(DOCS, _config(1))
    assert len(result["cards"]) == 1


def test_generate_accepts_dict_wrapped_cards(monkeypatch):
    _patch_llm(monkeypatch, [json.dumps({"cards": [CARD_A]})])
    result = _make_generator().generate(DOCS, _config(1))
    assert len(result["cards"]) == 1


def test_generate_normalizes_hint_and_tags(monkeypatch):
    card = {
        "front": "Q?",
        "back": "A.",
        "hint": "  A clue.  ",
        "tags": [" Concept ", "", "BASICS", "extra", "five", "six"],
    }
    _patch_llm(monkeypatch, [json.dumps([card])])
    result = _make_generator().generate(DOCS, _config(1))
    normalized = result["cards"][0]
    assert normalized["hint"] == "A clue."
    assert normalized["tags"] == ["concept", "basics", "extra"]


def test_generate_accepts_missing_optional_fields(monkeypatch):
    card = {"front": "Q?", "back": "A."}
    _patch_llm(monkeypatch, [json.dumps([card])])
    result = _make_generator().generate(DOCS, _config(1))
    assert result["cards"][0]["hint"] == ""
    assert result["cards"][0]["tags"] == []


def test_generate_raises_without_documents():
    with pytest.raises(FlashcardGenerationError):
        _make_generator().generate([], _config(1))


def test_generate_trims_excess_cards(monkeypatch):
    _patch_llm(monkeypatch, [json.dumps([CARD_A, CARD_B, CARD_A])])
    result = _make_generator().generate(DOCS, _config(2))
    assert len(result["cards"]) == 2


def test_generate_quotes_unquoted_keys(monkeypatch):
    raw = '[{front: "Q?", back: "A.", hint: "", tags: []}]'
    _patch_llm(monkeypatch, [raw])
    result = _make_generator().generate(DOCS, _config(1))
    assert result["cards"][0]["front"] == "Q?"
    assert result["cards"][0]["back"] == "A."


def test_generate_skips_non_dict_arrays(monkeypatch):
    raw = '["Intro", "Concepts"]' + json.dumps([CARD_A])
    _patch_llm(monkeypatch, [raw])
    result = _make_generator().generate(DOCS, _config(1))
    assert len(result["cards"]) == 1


def test_generate_uses_flashcards_call_type(monkeypatch):
    captured = {}

    def fake_call_llm(**kwargs):
        captured.update(kwargs)
        return json.dumps([CARD_A])

    monkeypatch.setattr("app.services.flashcard_generator.call_llm", fake_call_llm)
    _make_generator().generate(DOCS, _config(1))
    assert captured["call_type"] == "flashcards"


def test_generate_injects_topic_into_prompt(monkeypatch):
    captured = {}

    def fake_call_llm(**kwargs):
        captured.update(kwargs)
        return json.dumps([CARD_A])

    monkeypatch.setattr("app.services.flashcard_generator.call_llm", fake_call_llm)
    _make_generator().generate(DOCS, _config(1, topic="sorting"))
    user_prompt = captured["messages"][1]["content"]
    assert "sorting" in user_prompt
