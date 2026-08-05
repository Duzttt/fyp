"""Re-run RAGAS metrics for rows with missing (NaN) scores in a result CSV.

Usage:
    python scripts/rerun_missing_ragas.py --csv data/eval_result_xxx.csv

Reads the existing CSV (user_input / response / retrieved_contexts /
reference), finds rows where any metric column is NaN, re-runs ONLY those
rows through RAGAS with the configured judge LLM (default NVIDIA NIM), and
writes the merged result back in place.

Why: the main run can lose a few per-row scores when the judge LLM hits
max_tokens / timeout mid-generation. Answers and contexts are already in the
CSV, so only the missing metric columns are recomputed.

Note on Windows: import torch BEFORE pyarrow/ragas so the DLL load order is
torch -> pyarrow (WinError 1114 workaround, same as scripts/run_evaluation.py).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
import django  # noqa: E402

django.setup()

try:
    import torch  # noqa: F401 - DLL order: torch before pyarrow/ragas
except Exception:  # noqa: BLE001 - evaluation still works without torch
    pass

import pandas as pd  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from ragas import evaluate as ragas_evaluate  # noqa: E402
from ragas.dataset_schema import (  # noqa: E402
    EvaluationDataset,
    SingleTurnSample,
)
from ragas.embeddings import LangchainEmbeddingsWrapper  # noqa: E402
from ragas.llms import LangchainLLMWrapper  # noqa: E402
from ragas.metrics import (  # noqa: E402
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from ragas.run_config import RunConfig  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.embedding import EmbeddingService  # noqa: E402
from app.services.runtime_embedding import (  # noqa: E402
    load_runtime_embedding_settings,
)

METRIC_COLUMNS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]
_METRIC_OBJECTS = {
    "faithfulness": faithfulness,
    "answer_relevancy": answer_relevancy,
    "context_precision": context_precision,
    "context_recall": context_recall,
}


def _to_float(value: object) -> Optional[float]:
    """Return None for empty/NaN values so they count as missing."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _build_local_embeddings() -> Embeddings:
    rt = load_runtime_embedding_settings()
    service = EmbeddingService(model_name=rt["model_id"])

    class _LocalEmbeddings(Embeddings):
        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            emb = service.embed_texts(list(texts))
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            return [[float(v) for v in row] for row in emb]

        def embed_query(self, text: str) -> List[float]:
            emb = service.embed_query(text)
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            return [float(v) for v in emb]

    return _LocalEmbeddings()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Path to the result CSV.")
    parser.add_argument(
        "--judge-base-url",
        default=settings.NVIDIA_BASE_URL,
        help="RAGAS judge URL (default: NVIDIA NIM).",
    )
    parser.add_argument(
        "--judge-model",
        default=settings.NVIDIA_MODEL,
        help="RAGAS judge model (default: NVIDIA NIM model).",
    )
    parser.add_argument(
        "--judge-api-key",
        default=settings.NVIDIA_API_KEY,
        help="RAGAS judge API key.",
    )
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    if df.empty:
        print("CSV is empty.", file=sys.stderr)
        return 1

    # Find rows with at least one missing metric.
    missing_mask = pd.Series(False, index=df.index)
    missing_cols: Dict[int, List[str]] = {}
    for idx, row in df.iterrows():
        cols = [c for c in METRIC_COLUMNS if _to_float(row.get(c)) is None]
        if cols:
            missing_mask[idx] = True
            missing_cols[idx] = cols

    if not missing_mask.any():
        print("No missing scores; nothing to do.")
        return 0

    print(f"Rows with missing scores: {missing_mask.sum()}")
    for idx in sorted(missing_cols):
        print(
            f"  [{idx}] missing={missing_cols[idx]} "
            f"Q={str(df.loc[idx, 'user_input'])[:60]}"
        )

    # Build the evaluation dataset from the existing rows.
    samples = [
        SingleTurnSample(
            user_input=str(row["user_input"]),
            response=str(row["response"]),
            retrieved_contexts=_split_contexts(row.get("retrieved_contexts")),
            reference=str(row["reference"]),
        )
        for _, row in df[missing_mask].iterrows()
    ]

    langchain_llm = ChatOpenAI(
        model=args.judge_model,
        openai_api_key=args.judge_api_key or "local",
        openai_api_base=args.judge_base_url,
        temperature=0,
        max_tokens=args.max_tokens,
    )
    evaluator_llm = LangchainLLMWrapper(langchain_llm)
    evaluator_embeddings = LangchainEmbeddingsWrapper(_build_local_embeddings())

    # Only the metrics that were missing on at least one row.
    union: List[str] = []
    for cols in missing_cols.values():
        for c in cols:
            if c not in union:
                union.append(c)
    metrics = [_METRIC_OBJECTS[c] for c in union]
    print(f"\nRe-running metrics: {union} on {len(samples)} rows ...")

    result = ragas_evaluate(
        dataset=EvaluationDataset(samples=samples),
        metrics=metrics,
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=RunConfig(timeout=args.timeout, max_workers=args.max_workers),
    )

    new_df = result.to_pandas()
    new_df.index = df[missing_mask].index  # align back to original row numbers

    for col in union:
        for idx, value in new_df[col].items():
            if _to_float(value) is not None:
                df.at[idx, col] = value

    df.to_csv(args.csv, index=False, encoding="utf-8")
    print(f"\nMerged results written back to: {args.csv}")

    remaining = sum(
        1 for _, row in df.iterrows()
        if any(_to_float(row.get(c)) is None for c in METRIC_COLUMNS)
    )
    print(f"Rows still missing any score: {remaining}")
    return 0


def _split_contexts(raw: object) -> List[str]:
    """retrieved_contexts is stored as a list literal; parse it safely."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    text = str(raw).strip()
    if text in ("[]", "nan"):
        return []
    try:
        import ast

        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (ValueError, SyntaxError):
        pass
    return [text]


if __name__ == "__main__":
    sys.exit(main())
