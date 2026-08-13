"""Integration tests for RAGAS V2 Evaluator (mocked RAGAS)."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch


class TestRAGASEvaluatorV2Integration:
    """Test full evaluation flow with mocked dependencies."""

    @patch("app.services.ragas_v2.RAGASEvaluatorV2._build_ragas_embeddings")
    @patch("app.services.ragas_v2.RAGASEvaluatorV2._build_judge_llm")
    @patch("app.services.ragas_v2.RAGASEvaluatorV2.run_rag")
    @patch("ragas.evaluate")
    def test_evaluate_full_flow(
        self,
        mock_ragas_evaluate,
        mock_run_rag,
        mock_build_judge_llm,
        mock_embeddings,
    ):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        mock_run_rag.return_value = [
            {
                "question": "What is AI?",
                "answer": "AI is artificial intelligence.",
                "contexts": ["AI is a branch of computer science."],
                "ground_truth": "AI is artificial intelligence.",
            }
        ]

        mock_result = MagicMock()
        mock_df = MagicMock()
        mock_result.to_pandas.return_value = mock_df
        mock_df.to_csv = MagicMock()
        mock_df.to_dict.return_value = [
            {
                "question": "What is AI?",
                "answer": "AI is artificial intelligence.",
                "faithfulness": 0.9,
                "answer_relevancy": 0.85,
                "context_precision": 0.8,
                "context_recall": 0.95,
            }
        ]

        def stat_mock(value):
            return MagicMock(
                dropna=MagicMock(
                    return_value=MagicMock(
                        mean=MagicMock(return_value=value),
                        min=MagicMock(return_value=value - 0.1),
                        max=MagicMock(return_value=value + 0.1),
                    )
                )
            )

        mock_df.__getitem__.side_effect = lambda key: stat_mock(0.875)
        mock_df.__contains__.side_effect = lambda key: key in {
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
        }
        mock_ragas_evaluate.return_value = mock_result

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps({"question": "What is AI?", "ground_truth": "AI is..."})
                + "\n"
            )
            tmp_path = f.name

        try:
            evaluator = RAGASEvaluatorV2(
                judge_base_url="http://test:8080/v1",
                judge_model="test-model",
                judge_api_key="test-key",
            )

            result = evaluator.evaluate(
                dataset_path=tmp_path,
                top_k=3,
            )

            assert result["num_questions"] == 1
            assert "scores" in result
            assert "csv_path" in result

        finally:
            os.unlink(tmp_path)

    def test_format_report(self):
        from app.services.ragas_v2 import RAGASEvaluatorV2

        result = {
            "num_questions": 10,
            "scores": {
                "faithfulness": {"mean": 0.85, "min": 0.5, "max": 1.0},
                "answer_relevancy": {"mean": 0.92, "min": 0.7, "max": 1.0},
            },
        }

        report = RAGASEvaluatorV2.format_report(result)
        assert "RAGAS V2 EVALUATION REPORT" in report
        assert "Questions evaluated: 10" in report
        assert "faithfulness" in report
        assert "0.8500" in report
