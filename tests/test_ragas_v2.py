"""Tests for RAGAS V2 Evaluator."""

import os
from unittest.mock import patch


class TestRAGASEvaluatorV2Init:
    """Test RAGASEvaluatorV2 initialization and config resolution."""

    def test_init_with_explicit_args(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        evaluator = RAGASEvaluatorV2(
            judge_base_url="http://custom:8080/v1",
            judge_model="custom-model",
            judge_api_key="test-key",
        )
        assert evaluator.judge_base_url == "http://custom:8080/v1"
        assert evaluator.judge_model == "custom-model"
        assert evaluator.judge_api_key == "test-key"

    def test_init_defaults_to_none(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        evaluator = RAGASEvaluatorV2()
        assert evaluator.judge_base_url is None
        assert evaluator.judge_model is None
        assert evaluator.judge_api_key is None


class TestNormalizeBaseUrl:
    """Test /v1 base URL normalization."""

    def test_adds_v1_if_missing(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        assert RAGASEvaluatorV2._normalize_base_url("http://localhost:8080") == (
            "http://localhost:8080/v1"
        )

    def test_keeps_v1_if_present(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        assert RAGASEvaluatorV2._normalize_base_url("http://localhost:8080/v1") == (
            "http://localhost:8080/v1"
        )

    def test_strips_trailing_slash(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        assert RAGASEvaluatorV2._normalize_base_url("http://localhost:8080/") == (
            "http://localhost:8080/v1"
        )


class TestRAGASEvaluatorV2ResolveConfig:
    """Test judge config resolution."""

    @patch.dict(
        os.environ,
        {
            "RAGAS_JUDGE_BASE_URL": "http://env:8080/v1",
            "RAGAS_JUDGE_MODEL": "env-model",
            "RAGAS_JUDGE_API_KEY": "env-key",
        },
    )
    def test_env_vars_take_priority_over_fallback(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        evaluator = RAGASEvaluatorV2()
        config = evaluator._resolve_judge_config()
        assert config["base_url"] == "http://env:8080/v1"
        assert config["model"] == "env-model"
        assert config["api_key"] == "env-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.services.ragas_v2.settings")
    def test_explicit_args_take_priority_over_env(self, mock_settings):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        evaluator = RAGASEvaluatorV2(
            judge_base_url="http://explicit:8080/v1",
            judge_model="explicit-model",
            judge_api_key="explicit-key",
        )
        config = evaluator._resolve_judge_config()
        assert config["base_url"] == "http://explicit:8080/v1"

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.services.ragas_v2.settings")
    def test_local_llm_fallback_normalizes_v1(self, mock_settings):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        mock_settings.LOCAL_LLM_BASE_URL = "http://localhost:8080"
        mock_settings.LOCAL_LLM_MODEL = "local-model"
        mock_settings.OPENROUTER_API_KEY = None
        evaluator = RAGASEvaluatorV2()
        config = evaluator._resolve_judge_config()
        assert config["base_url"] == "http://localhost:8080/v1"
        assert config["model"] == "local-model"

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.services.ragas_v2.settings")
    def test_openrouter_fallback(self, mock_settings):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        mock_settings.OPENROUTER_API_KEY = "or-key"
        mock_settings.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
        evaluator = RAGASEvaluatorV2()
        config = evaluator._resolve_judge_config()
        assert config["model"] == "deepseek/deepseek-v4-flash"
        assert config["api_key"] == "or-key"
        assert config["base_url"] == "https://openrouter.ai/api/v1"

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.services.ragas_v2.settings")
    def test_explicit_args_normalize_v1(self, mock_settings):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        evaluator = RAGASEvaluatorV2(
            judge_base_url="http://explicit:8080",
            judge_model="explicit-model",
        )
        config = evaluator._resolve_judge_config()
        assert config["base_url"] == "http://explicit:8080/v1"
