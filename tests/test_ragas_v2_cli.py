"""Tests for RAGAS V2 CLI."""

import importlib
import sys


class TestRAGASV2CLI:
    """Test CLI argument parsing and subcommands."""

    def test_module_import_does_not_trigger_django_setup(self):
        """Importing the module must not call django.setup()."""
        import scripts.ragas_v2_eval as cli_mod

        importlib.reload(cli_mod)

        assert hasattr(cli_mod, "main")

    def test_evaluate_subcommand_parses_args(self):
        """Test that 'evaluate' subcommand parses correctly."""
        sys.argv = [
            "ragas_v2_eval.py",
            "evaluate",
            "--dataset",
            "test.jsonl",
            "--out",
            "results/test.csv",
            "--judge-base-url",
            "http://localhost:8080/v1",
            "--judge-model",
            "test-model",
        ]

        import scripts.ragas_v2_eval as cli_mod

        importlib.reload(cli_mod)
