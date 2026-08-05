"""RAGAS Baseline Evaluation - Two Phase Pipeline.

Phase 1: Generate QA dataset from PDFs using LLM-A
Phase 2: Evaluate with RAGAS using LLM-B as judge

Usage:
    # Phase 1: Generate QA (start llama-server with model A first)
    python scripts/ragas_baseline.py generate \\
        --pdf-dir media/data_source/ragas \\
        --out eval_baseline.jsonl \\
        --base-url http://localhost:8080 \\
        --model <model-a> \\
        --num-questions 5

    # Phase 2: Evaluate (start llama-server with model B first)
    python scripts/ragas_baseline.py evaluate \\
        --dataset eval_baseline.jsonl \\
        --out eval_baseline_result.csv \\
        --base-url http://localhost:8080 \\
        --model <model-b> \\
        --top-k 5

    # Both phases in sequence
    python scripts/ragas_baseline.py all \\
        --pdf-dir media/data_source/ragas \\
        --out eval_baseline_result.csv \\
        --gen-base-url http://localhost:8080 \\
        --gen-model <model-a> \\
        --eval-base-url http://localhost:8080 \\
        --eval-model <model-b>
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
import django

django.setup()

from app.config import settings  # noqa: E402

logger = logging.getLogger(__name__)


def _call_llm(
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout: int = 300,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return content.strip()


def _extract_text(pdf_path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    texts = []
    for page in reader.pages:
        t = page.extract_text()
        if t and t.strip():
            texts.append(t.strip())
    return "\n\n".join(texts)


def _parse_json_array(content: str) -> List[Dict[str, str]]:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end > start:
        try:
            result = json.loads(content[start : end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    return []


# ──────────────────────────────────────────────
# Phase 1: Generate QA Dataset
# ──────────────────────────────────────────────

_QA_PROMPT = """Based on the following lecture content, generate {num} question-answer pairs.

Rules:
- Questions should be specific and test understanding of the material
- Answers must come ONLY from the provided text (ground truth)
- Mix difficulty levels: factual recall, conceptual understanding, comparison
- Return ONLY a JSON array, no extra text

[
    {{"question": "Your question here?", "ground_truth": "Answer from the text."}},
    ...
]

Lecture content:
{text}"""


def generate_qa(
    pdf_dir: str,
    out_path: str,
    base_url: str,
    model: str,
    num_questions: int = 5,
    language: str = "en",
    timeout: int = 300,
    api_key: Optional[str] = None,
) -> int:
    pdf_dir = Path(pdf_dir)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs in {pdf_dir}")

    print(f"Found {len(pdfs)} PDFs in {pdf_dir}")
    total = 0
    tmp = out_path + ".tmp"

    with open(tmp, "w", encoding="utf-8") as fh:
        for pdf in pdfs:
            print(f"  Processing: {pdf.name} ...", end=" ", flush=True)
            text = _extract_text(str(pdf))
            if not text.strip():
                print("SKIP (no text)")
                continue

            prompt = _QA_PROMPT.format(num=num_questions, text=text[:8000])
            try:
                content = _call_llm(
                    base_url=base_url,
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=timeout,
                    temperature=0.7,
                    api_key=api_key,
                )
                qa_pairs = _parse_json_array(content)
                if not qa_pairs:
                    print(f"PARSE FAIL (retrying with shorter text)")
                    prompt = _QA_PROMPT.format(num=num_questions, text=text[:3000])
                    content = _call_llm(
                        base_url=base_url,
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        timeout=timeout,
                        temperature=0.5,
                        api_key=api_key,
                    )
                    qa_pairs = _parse_json_array(content)

                for qa in qa_pairs:
                    if "question" in qa and "ground_truth" in qa:
                        fh.write(json.dumps(qa, ensure_ascii=False) + "\n")
                        total += 1
                print(f"OK ({len(qa_pairs)} QAs)")
            except Exception as e:
                print(f"ERROR: {e}")

    os.replace(tmp, out_path)
    print(f"\nGenerated {total} Q-A pairs → {out_path}")
    return total


# ──────────────────────────────────────────────
# Phase 2: RAGAS Evaluation
# ──────────────────────────────────────────────


def evaluate(
    dataset_path: str,
    out_path: str,
    base_url: str,
    model: str,
    top_k: int = 5,
    timeout: int = 300,
    max_workers: int = 4,
    api_key: Optional[str] = None,
    judge_base_url: Optional[str] = None,
    judge_model: Optional[str] = None,
    judge_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate RAGAS with separate answer generator and judge models.

    Args:
        base_url/model/api_key: Answer generator (qwen local)
        judge_base_url/judge_model/judge_api_key: RAGAS judge (Gemini)
    """
    from app.services.local_rag import build_context_from_sources, retrieve_with_faiss

    questions = []
    ground_truths = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            questions.append(rec["question"])
            ground_truths.append(rec["ground_truth"])

    print(f"Loaded {len(questions)} questions from {dataset_path}")
    print(f"Answer generator: {base_url} / {model}")
    j_url = judge_base_url or base_url
    j_model = judge_model or model
    print(f"RAGAS judge: {j_url} / {j_model}")

    rows = []
    for i, q in enumerate(questions):
        print(f"  [{i+1}/{len(questions)}] {q[:60]}...", end=" ", flush=True)
        try:
            sources = retrieve_with_faiss(query=q, top_k=top_k)
            context = build_context_from_sources(sources)
            answer = _call_llm(
                base_url=base_url,
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": f"Context:\n{context}\n\nQuestion: {q}\n\nAnswer based on the context:",
                    }
                ],
                timeout=timeout,
                temperature=0.3,
                api_key=api_key,
            )
            rows.append(
                {
                    "question": q,
                    "answer": answer,
                    "contexts": [s.get("text", "") for s in sources],
                    "ground_truth": ground_truths[i],
                }
            )
            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")
            rows.append(
                {"question": q, "answer": "", "contexts": [], "ground_truth": ground_truths[i]}
            )

    valid = [r for r in rows if r["answer"]]
    print(f"\nValid RAG results: {len(valid)}/{len(rows)}")

    if not valid:
        raise ValueError("No valid RAG results to evaluate")

    data = {
        "question": [r["question"] for r in valid],
        "answer": [r["answer"] for r in valid],
        "contexts": [r["contexts"] for r in valid],
        "ground_truth": [r["ground_truth"] for r in valid],
    }

    from datasets import Dataset as HFDataset
    from langchain_core.embeddings import Embeddings
    from langchain_openai import ChatOpenAI
    from ragas import evaluate as ragas_evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )
    from ragas.run_config import RunConfig

    from app.services.embedding import EmbeddingService
    from app.services.runtime_embedding import load_runtime_embedding_settings

    rt = load_runtime_embedding_settings()
    embedding_service = EmbeddingService(model_name=rt["model_id"])

    class LocalEmb(Embeddings):
        def embed_documents(self, texts):
            emb = embedding_service.embed_texts(texts)
            return [[float(v) for v in row] for row in emb.tolist()]

        def embed_query(self, text):
            emb = embedding_service.embed_query(text)
            return [float(v) for v in emb.tolist()]

    judge_key = judge_api_key or api_key or "local"
    llm = ChatOpenAI(
        model=j_model,
        openai_api_key=judge_key,
        openai_api_base=j_url,
        temperature=0,
        max_tokens=4096,
    )
    ragas_llm = LangchainLLMWrapper(llm)

    dataset = HFDataset.from_dict(data)
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    for m in metrics:
        if hasattr(m, "llm"):
            m.llm = ragas_llm

    print("\nRunning RAGAS evaluation...")
    result = ragas_evaluate(
        dataset=dataset,
        metrics=metrics,
        embeddings=LocalEmb(),
        run_config=RunConfig(timeout=timeout, max_workers=max_workers),
    )

    df = result.to_pandas()
    df.to_csv(out_path, index=False, encoding="utf-8")

    scores = {}
    for col in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        if col in df.columns:
            vals = df[col].dropna()
            scores[col] = {"mean": float(vals.mean()), "min": float(vals.min()), "max": float(vals.max())}

    print(f"\n{'='*50}")
    print("RAGAS Results:")
    print(f"{'='*50}")
    for metric, s in scores.items():
        print(f"  {metric:22s}: avg={s['mean']:.4f}  min={s['min']:.4f}  max={s['max']:.4f}")
    print(f"{'='*50}")
    print(f"CSV saved to: {out_path}")

    return {"num_questions": len(valid), "scores": scores, "csv_path": out_path}


def main():
    parser = argparse.ArgumentParser(description="RAGAS Baseline Evaluation")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Phase 1: Generate QA dataset")
    gen.add_argument("--pdf-dir", required=True)
    gen.add_argument("--out", required=True)
    gen.add_argument("--base-url", required=True)
    gen.add_argument("--model", required=True)
    gen.add_argument("--num-questions", type=int, default=5)
    gen.add_argument("--timeout", type=int, default=300)
    gen.add_argument("--api-key", default=None, help="API key (for Gemini/OpenRouter)")

    evl = sub.add_parser("evaluate", help="Phase 2: RAGAS evaluation")
    evl.add_argument("--dataset", required=True)
    evl.add_argument("--out", required=True)
    evl.add_argument("--base-url", required=True, help="Answer generator URL (qwen)")
    evl.add_argument("--model", required=True, help="Answer generator model (qwen)")
    evl.add_argument("--top-k", type=int, default=5)
    evl.add_argument("--timeout", type=int, default=300)
    evl.add_argument("--api-key", default=None, help="Answer generator API key")
    evl.add_argument("--judge-base-url", default=None, help="RAGAS judge URL (Gemini)")
    evl.add_argument("--judge-model", default=None, help="RAGAS judge model (Gemini)")
    evl.add_argument("--judge-api-key", default=None, help="RAGAS judge API key")

    both = sub.add_parser("all", help="Both phases")
    both.add_argument("--pdf-dir", required=True)
    both.add_argument("--out", required=True)
    both.add_argument("--gen-base-url", required=True)
    both.add_argument("--gen-model", required=True)
    both.add_argument("--eval-base-url", required=True)
    both.add_argument("--eval-model", required=True)
    both.add_argument("--num-questions", type=int, default=5)
    both.add_argument("--top-k", type=int, default=5)
    both.add_argument("--timeout", type=int, default=300)
    both.add_argument("--gen-api-key", default=None)
    both.add_argument("--eval-api-key", default=None)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "generate":
        generate_qa(args.pdf_dir, args.out, args.base_url, args.model, args.num_questions, timeout=args.timeout, api_key=args.api_key)

    elif args.command == "evaluate":
        evaluate(
            args.dataset, args.out, args.base_url, args.model,
            args.top_k, args.timeout, api_key=args.api_key,
            judge_base_url=args.judge_base_url, judge_model=args.judge_model,
            judge_api_key=args.judge_api_key,
        )

    elif args.command == "all":
        jsonl_path = args.out.replace(".csv", ".jsonl")
        generate_qa(args.pdf_dir, jsonl_path, args.gen_base_url, args.gen_model, args.num_questions, timeout=args.timeout, api_key=args.gen_api_key)
        print(f"\n{'='*50}")
        print("Switch to model B, then press Enter to continue...")
        print(f"{'='*50}")
        input()
        evaluate(jsonl_path, args.out, args.eval_base_url, args.eval_model, args.top_k, args.timeout, api_key=args.eval_api_key)


if __name__ == "__main__":
    main()
