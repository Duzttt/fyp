import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

import pytest  # noqa: E402
from app.services.topic_summarizer import (  # noqa: E402
    Topic,
    TopicPoint,
    TopicSection,
    TopicSummarizerError,
    build_topic_summary_messages,
    detect_language,
    load_document_chunks,
    parse_topic_summary_json,
    propose_topics,
    sample_chunks_for_topics,
    summarize_topic,
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


SAMPLE_TOPIC = Topic(
    title="Supervised learning", query="supervised learning", importance=5
)
SAMPLE_CHUNKS = [
    {"text": "Supervised learning uses labeled examples.", "page": 3},
    {"text": "Models are trained on paired inputs and outputs.", "page": 4},
]


class TestBuildTopicSummaryMessages:
    def test_includes_chunk_numbers_and_pages(self):
        messages = build_topic_summary_messages(SAMPLE_TOPIC, SAMPLE_CHUNKS, "en")
        user = messages[1]["content"]
        assert "[1]" in user
        assert "page 3" in user
        assert "Supervised learning" in user


class TestParseTopicSummaryJson:
    def test_maps_evidence_chunks_to_pages(self):
        raw = json.dumps(
            {
                "heading": "Supervised learning",
                "points": [
                    {"text": "Uses labeled examples.", "evidence_chunk": 1},
                    {"text": "Trains on paired data.", "evidence_chunk": 2},
                ],
            }
        )
        section = parse_topic_summary_json(raw, SAMPLE_CHUNKS)
        assert section == TopicSection(
            title="Supervised learning",
            points=[
                TopicPoint(text="Uses labeled examples.", pages=[3]),
                TopicPoint(text="Trains on paired data.", pages=[4]),
            ],
        )

    def test_invalid_evidence_index_yields_empty_pages(self):
        raw = json.dumps(
            {
                "heading": "H",
                "points": [{"text": "point", "evidence_chunk": 99}],
            }
        )
        section = parse_topic_summary_json(raw, SAMPLE_CHUNKS)
        assert section.points[0].pages == []

    def test_missing_points_raises(self):
        raw = json.dumps({"heading": "H", "points": []})
        with pytest.raises(TopicSummarizerError) as exc_info:
            parse_topic_summary_json(raw, SAMPLE_CHUNKS)
        assert exc_info.value.code == "malformed_json"


class TestSummarizeTopic:
    def _llm(self, *_args, **_kwargs):
        return json.dumps(
            {
                "heading": "Supervised learning",
                "points": [{"text": "Uses labeled examples.", "evidence_chunk": 1}],
            }
        )

    def test_summarizes_retrieved_chunks(self):
        def retrieve(query, top_k):
            assert query == SAMPLE_TOPIC.query
            assert top_k == 6
            return SAMPLE_CHUNKS

        section = summarize_topic(
            SAMPLE_TOPIC,
            top_k=6,
            language="en",
            retrieve_fn=retrieve,
            llm_call=self._llm,
        )
        assert section is not None
        assert section.title == "Supervised learning"
        assert section.points[0].pages == [3]

    def test_empty_retrieval_returns_none(self):
        def retrieve(_query, _top_k):
            return []

        assert (
            summarize_topic(
                SAMPLE_TOPIC,
                top_k=4,
                language="en",
                retrieve_fn=retrieve,
                llm_call=self._llm,
            )
            is None
        )

    def test_retries_once_on_bad_json(self):
        calls = {"count": 0}

        def retrieve(_query, _top_k):
            return SAMPLE_CHUNKS

        def llm_bad_then_ok(*_args, **_kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return "garbage"
            return json.dumps(
                {
                    "heading": "H",
                    "points": [{"text": "p", "evidence_chunk": 1}],
                }
            )

        section = summarize_topic(
            SAMPLE_TOPIC,
            top_k=4,
            language="en",
            retrieve_fn=retrieve,
            llm_call=llm_bad_then_ok,
        )
        assert section is not None
        assert calls["count"] == 2

    def test_persistent_bad_json_raises(self):
        def retrieve(_query, _top_k):
            return SAMPLE_CHUNKS

        def llm_bad(*_args, **_kwargs):
            return "garbage"

        with pytest.raises(TopicSummarizerError) as exc_info:
            summarize_topic(
                SAMPLE_TOPIC,
                top_k=4,
                language="en",
                retrieve_fn=retrieve,
                llm_call=llm_bad,
            )
        assert exc_info.value.code == "malformed_json"
