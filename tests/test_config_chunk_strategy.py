import pytest


class TestChunkStrategyConfig:
    def test_default_chunk_strategy(self):
        from app.config import Settings

        s = Settings(_env_file=None)
        assert s.CHUNK_STRATEGY == "sentence"

    def test_valid_strategy_paragraph(self):
        from app.config import Settings

        s = Settings(CHUNK_STRATEGY="paragraph", _env_file=None)
        assert s.CHUNK_STRATEGY == "paragraph"

    def test_invalid_strategy_falls_back_to_sentence(self):
        from app.config import Settings

        s = Settings(CHUNK_STRATEGY="invalid", _env_file=None)
        assert s.CHUNK_STRATEGY == "sentence"

    def test_case_insensitive_strategy(self):
        from app.config import Settings

        s = Settings(CHUNK_STRATEGY="PARAGRAPH", _env_file=None)
        assert s.CHUNK_STRATEGY == "paragraph"
