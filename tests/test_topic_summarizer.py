import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

import pytest  # noqa: E402
from app.services.topic_summarizer import (  # noqa: E402
    TopicSummarizerError,
    detect_language,
    load_document_chunks,
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
