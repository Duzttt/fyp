import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

import pytest  # noqa: E402
from app.services.topic_summarizer import (  # noqa: E402
    Topic,
    TopicSummarizerError,
    detect_language,
    load_document_chunks,
    propose_topics,
    sample_chunks_for_topics,
)


class TestDetectLanguage:
    def test_chinese_dominant_text(self):
        texts = [
            "机器学习是一种通过数据训练模型的方法。",
            "监督学习使用带标签的样本进行训练。",
        ]
        assert detect_language(texts) == "zh"

    def test_english_dominant_text(self):
        texts = [
            "Machine learning enables systems to learn from data.",
            "Evaluation relies on train and test splits.",
        ]
        assert detect_language(texts) == "en"

    def test_empty_text_defaults_to_english(self):
        assert detect_language([]) == "en"
        assert detect_language([""]) == "en"


class TestLoadDocumentChunks:
    def test_loads_only_matching_document_sorted_by_page(self, monkeypatch):
        class FakeStore:
            def __init__(self):
                self.chunks = [
                    {"text": "B content", "source": "doc.pdf", "page": 7},
                    {"text": "A content", "source": "doc.pdf", "page": 2},
                    {"text": "other", "source": "other.pdf", "page": 1},
                ]

        monkeypatch.setattr(
            "app.services.topic_summarizer.load_runtime_embedding_settings",
            lambda: {"embedding_dim": 384},
        )
        monkeypatch.setattr(
            "app.services.topic_summarizer.VectorStore",
            type(
                "FakeVS",
                (),
                {"get_cached": classmethod(lambda cls, **kw: FakeStore())},
            ),
        )

        chunks = load_document_chunks("doc.pdf")
        assert [c["page"] for c in chunks] == [2, 7]
        assert all(c["source"] == "doc.pdf" for c in chunks)

    def test_unindexed_document_raises(self, monkeypatch):
        class FakeStore:
            def __init__(self):
                self.chunks = [{"text": "x", "source": "other.pdf", "page": 1}]

        monkeypatch.setattr(
            "app.services.topic_summarizer.load_runtime_embedding_settings",
            lambda: {"embedding_dim": 384},
        )
        monkeypatch.setattr(
            "app.services.topic_summarizer.VectorStore",
            type(
                "FakeVS",
                (),
                {"get_cached": classmethod(lambda cls, **kw: FakeStore())},
            ),
        )

        with pytest.raises(TopicSummarizerError) as exc_info:
            load_document_chunks("missing.pdf")
        assert exc_info.value.code == "document_not_indexed"


class TestSampleChunks:
    def test_even_sampling_caps_at_max(self):
        chunks = [{"text": f"chunk {i}", "page": i + 1} for i in range(50)]
        sample = sample_chunks_for_topics(chunks, max_samples=10)
        assert len(sample) == 10
        assert sample[0]["page"] == 1
        assert sample[-1]["page"] == 50

    def test_fewer_chunks_than_max_returns_all(self):
        chunks = [{"text": "a"}, {"text": "b"}]
        assert len(sample_chunks_for_topics(chunks)) == 2


class TestProposeTopics:
    def _llm_ok(self, *_args, **_kwargs):
        return json.dumps(
            {
                "topics": [
                    {
                        "title": "Supervised learning",
                        "query": "supervised learning labeled data",
                        "importance": 5,
                    },
                    {
                        "title": "Evaluation",
                        "query": "train test split evaluation",
                        "importance": 4,
                    },
                ]
            }
        )

    def test_parses_valid_json(self):
        topics = propose_topics(
            [{"text": "Machine learning basics."}],
            language="en",
            topic_count=4,
            llm_call=self._llm_ok,
        )
        assert topics == [
            Topic(
                title="Supervised learning",
                query="supervised learning labeled data",
                importance=5,
            ),
            Topic(
                title="Evaluation",
                query="train test split evaluation",
                importance=4,
            ),
        ]

    def test_fenced_json_is_stripped(self):
        def llm_fenced(*_args, **_kwargs):
            return (
                "```json\n"
                + json.dumps(
                    {"topics": [{"title": "T", "query": "q", "importance": 3}]}
                )
                + "\n```"
            )

        topics = propose_topics([{"text": "x"}], "en", 4, llm_call=llm_fenced)
        assert topics[0].title == "T"

    def test_malformed_json_retries_once_then_succeeds(self):
        calls = {"count": 0}

        def llm_bad_then_ok(*_args, **_kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return "not json at all"
            return json.dumps(
                {"topics": [{"title": "T", "query": "q", "importance": 2}]}
            )

        topics = propose_topics([{"text": "x"}], "en", 4, llm_call=llm_bad_then_ok)
        assert topics[0].title == "T"
        assert calls["count"] == 2

    def test_persistent_malformed_json_raises(self):
        def llm_bad(*_args, **_kwargs):
            return "still not json"

        with pytest.raises(TopicSummarizerError) as exc_info:
            propose_topics([{"text": "x"}], "en", 4, llm_call=llm_bad)
        assert exc_info.value.code == "malformed_json"
