"""Benchmark local LLM (GGUF) models for the lecture-note RAG system.

Data-driven comparison of candidate llama.cpp models on:
  * Answer quality   — RAGAS metrics scored by a FIXED external judge
                       (NVIDIA NIM nemotron-3-super-120b-a12b by default), so
                       score differences arise only from the generation model.
  * Speed            — per-question latency + tokens/second (4 GB VRAM GPU).
  * Resource         — VRAM used by each model at load time.

The retrieval context is identical for every model (reuses the app's own
``retrieve_with_faiss`` + ``build_context_from_sources``), so the only thing
that changes between runs is the generation model.

Usage (from repo root):
    python scripts/compare_local_models.py
    python scripts/compare_local_models.py --models models/llama-3.2-3b ...
    python scripts/compare_local_models.py --dataset eval_baseline.jsonl
                                         --n-gpu-layers 0

The script starts ONE llama-server per model on a dedicated port (default 8080),
generates answers for every question, shuts it down, then scores all runs with
the same judge. Existing answers are cached per model so re-runs skip repeat
generation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")


# --- Model catalog ---------------------------------------------------------
# alias/name -> filesystem path (relative to the llama.cpp binaries directory).
# The `alias` is what llama-server reports on /v1/models and accepts on
# /v1/chat/completions.
MODEL_CATALOG: Dict[str, str] = {
    # Existing models already in the models directory.
    "llama-3.2-3b": "models/Llama-3.2-3B-Instruct.Q4_K_M.gguf",
    "minicpm5-1b": "models/MiniCPM5-1B-Q8_0.gguf",
    "qwen2.5-3b": "models/qwen2.5-3b-instruct-q4_k_m.gguf",
    "vibethinker-1.5b": "models/VibeThinker-1.5B.Q4_K_M.gguf",
    # Recommended non-thinking additions (download the GGUF into the models dir).
    # Qwen3-4B is the quality pick that still fits in 4 GB VRAM; enable_thinking
    # is turned off automatically by chat().
    "qwen3-4b": "models/Qwen3-4B-Instruct-Q4_K_M.gguf",
    "qwen2.5-1.5b": "models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
    "llama-3.2-1b": "models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
}

# Default judge: NVIDIA NIM (read from .env when available, otherwise args).
JUDGE_BASE_URL = "https://integrate.api.nvidia.com/v1"
JUDGE_MODEL = "nvidia/nemotron-3-super-120b-a12b"


@dataclass
class RunStats:
    """Per-model generation captured by the harness."""

    model: str
    n_gpu_layers: int
    vram_mib: Optional[int] = None
    load_seconds: Optional[float] = None
    answered: int = 0
    failed: int = 0
    latency_s: List[float] = None  # type: ignore[assignment]
    tokens_per_s: List[float] = None  # type: ignore[assignment]
    total_tokens: int = 0
    answers: List[Dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.latency_s is None:
            self.latency_s = []
        if self.tokens_per_s is None:
            self.tokens_per_s = []
        if self.answers is None:
            self.answers = []

    def mean(self, values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def p95(self, values: List[float]) -> float:
        if not values:
            return 0.0
        return sorted(values)[int(len(values) * 0.95) - 1]

    def summary(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "n_gpu_layers": self.n_gpu_layers,
            "vram_mib": self.vram_mib,
            "load_seconds": self.load_seconds,
            "answered": self.answered,
            "failed": self.failed,
            "avg_latency_s": round(self.mean(self.latency_s), 3),
            "p95_latency_s": round(self.p95(self.latency_s), 3),
            "avg_tokens_per_s": round(self.mean(self.tokens_per_s), 2),
            "total_tokens": self.total_tokens,
        }


# --- llama.cpp server control ---------------------------------------------
def _wait_ready(base_url: str, timeout: float = 180.0) -> bool:
    import requests

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/v1/models", timeout=2)
            if r.status_code == 200 and r.json().get("data"):
                return True
        except requests.RequestException:
            pass
        time.sleep(1.0)
    return False


def _gpu_mem_free_mib() -> Optional[int]:
    """Free VRAM in MiB via nvidia-smi; None when unavailable."""
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode != 0:
            return None
        vals = [int(v.strip()) for v in out.stdout.splitlines() if v.strip().isdigit()]
        return vals[0] if vals else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


class LlamaServer:
    """Manage a single llama-server instance for one model."""

    def __init__(
        self,
        server_exe: str,
        models_dir: str,
        alias: str,
        model_path: str,
        port: int,
        n_gpu_layers: int,
        ctx_size: int = 8192,
    ) -> None:
        self.server_exe = server_exe
        self.alias = alias
        self.model_file = Path(models_dir) / model_path
        self.port = port
        self.n_gpu_layers = n_gpu_layers
        self.ctx_size = ctx_size
        self.proc: Optional[subprocess.Popen] = None
        self._log_file: Optional[Any] = None
        self.base_url = f"http://127.0.0.1:{port}"

    def start(self) -> None:
        import requests

        if not self.model_file.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_file}")
        cmd = [
            self.server_exe,
            "--model",
            str(self.model_file),
            "--alias",
            self.alias,
            "--port",
            str(self.port),
            "--n-gpu-layers",
            str(self.n_gpu_layers),
            "--ctx-size",
            str(self.ctx_size),
            "--host",
            "127.0.0.1",
        ]
        log_path = Path(os.environ.get("TEMP", "/tmp")) / f"llama-{self.alias}.log"
        self._log_file = open(log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            cmd,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 180.0
        while time.time() < deadline:
            if self.proc.poll() is not None:
                # Server exited (likely OOM or bad model); read the reason.
                self._log_file.flush()
                tail = log_path.read_text(encoding="utf-8", errors="replace")[-800:]
                self.stop()
                raise RuntimeError(
                    f"llama-server for {self.alias} exited early (ngl={self.n_gpu_layers}). "
                    f"Log tail:\n{tail}"
                )
            try:
                r = requests.get(f"{self.base_url}/v1/models", timeout=2)
                if r.status_code == 200 and r.json().get("data"):
                    return
            except requests.RequestException:
                pass
            time.sleep(1.0)
        self.stop()
        raise RuntimeError(
            f"llama-server for {self.alias} did not become ready on port {self.port}"
        )

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError:
                pass
            self._log_file = None

    def chat(self, messages: List[Dict[str, str]], max_tokens: int, timeout: int):
        """POST /v1/chat/completions and return (text, completion_tokens, elapsed_s).

        Thinking-mode handling mirrors ``llm_client._call_local_llm``:
        MiniCPM and Qwen3-family templates default to thinking, so
        ``enable_thinking=False`` is sent whenever the model name indicates those
        families; otherwise the answer lands in ``reasoning_content`` / an open
        ``<think>`` block and the ``content`` field stays empty or truncated.
        """
        import requests

        payload: Dict[str, Any] = {
            "model": self.alias,
            "messages": messages,
            "stream": False,
            "max_tokens": max_tokens,
        }
        alias_lower = self.alias.lower()
        # Model families whose templates use `enable_thinking` to toggle
        # (vs. no toggle mechanism at all). These default to thinking ON, so we
        # turn it OFF to get clean, complete answers for RAG.
        if any(
            tag in alias_lower
            for tag in ("minicpm", "qwen3", "qwen-3", "qwen3moe")
        ):
            payload["enable_thinking"] = False
            payload.setdefault("temperature", 0.7)
            payload.setdefault("top_p", 0.95)

        start = time.perf_counter()
        r = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=timeout,
        )
        elapsed = time.perf_counter() - start
        r.raise_for_status()
        data = r.json()
        choice = data["choices"][0]
        message = choice.get("message", {}) or {}
        text = message.get("content") or ""
        # Fallback: some reasoning models emit the answer in reasoning_content.
        if not text.strip():
            text = message.get("reasoning_content") or ""
        # Strip <think>...</think> blocks that reasoning models (e.g. VibeThinker,
        # Qwen-style) inline into the content field.
        if "<think>" in text and "</think>" in text:
            start = text.index("<think>")
            end = text.index("</think>") + len("</think>")
            text = (text[:start] + text[end:]).strip()
        usage = data.get("usage", {})
        completion_tokens = int(
            usage.get("completion_tokens")
            or choice.get("completion_tokens")
            or 0
        )
        return text, completion_tokens, elapsed


# --- Generation harness ----------------------------------------------------
def _load_dataset(path: Path) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _run_model(
    *,
    alias: str,
    server_exe: str,
    models_dir: str,
    model_path: str,
    port: int,
    n_gpu_layers: int,
    dataset: List[Dict[str, str]],
    cache_dir: Path,
    top_k: int,
    max_tokens: int,
    timeout: int,
) -> RunStats:
    """Load one model, answer every question, return stats. Answers cached."""

    # Import app services lazily (needs Django setup for QueryLog).
    import django

    django.setup()
    from app.services.local_rag import (
        build_context_from_sources,
        build_rag_messages,
        retrieve_with_faiss,
    )

    stats = RunStats(model=alias, n_gpu_layers=n_gpu_layers)
    cache_path = cache_dir / f"{alias}.jsonl"
    cached: Dict[str, Dict[str, Any]] = {}
    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    cached[rec["question"]] = rec

    free_before = _gpu_mem_free_mib()

    server = LlamaServer(
        server_exe=server_exe,
        models_dir=models_dir,
        alias=alias,
        model_path=model_path,
        port=port,
        n_gpu_layers=n_gpu_layers,
    )
    t0 = time.perf_counter()
    server.start()
    stats.load_seconds = round(time.perf_counter() - t0, 2)

    free_after = _gpu_mem_free_mib()
    if free_before is not None and free_after is not None:
        stats.vram_mib = free_before - free_after

    out_lines: List[str] = []
    try:
        for rec in dataset:
            question = rec["question"]
            ground_truth = rec["ground_truth"]

            if question in cached and cached[question].get("answer"):
                entry = cached[question]
                stats.answered += 1
                stats.total_tokens += int(entry.get("completion_tokens", 0))
                if entry.get("latency_s"):
                    stats.latency_s.append(float(entry["latency_s"]))
                if entry.get("tokens_per_s"):
                    stats.tokens_per_s.append(float(entry["tokens_per_s"]))
                out_lines.append(json.dumps(entry, ensure_ascii=False))
                continue

            try:
                sources = retrieve_with_faiss(query=question, top_k=top_k)
                context = build_context_from_sources(sources)
                messages = build_rag_messages(question, context)
                text, comp_tokens, elapsed = server.chat(
                    messages, max_tokens=max_tokens, timeout=timeout
                )
                entry = {
                    "question": question,
                    "ground_truth": ground_truth,
                    "answer": text,
                    "contexts": [s.get("text", "") for s in sources],
                    "completion_tokens": comp_tokens,
                    "latency_s": round(elapsed, 4),
                    "tokens_per_s": round(comp_tokens / elapsed, 2) if elapsed else 0,
                }
                stats.answered += 1
                stats.total_tokens += comp_tokens
                stats.latency_s.append(elapsed)
                if elapsed:
                    stats.tokens_per_s.append(comp_tokens / elapsed)
                out_lines.append(json.dumps(entry, ensure_ascii=False))
                print(
                    f"    [{alias}] q {stats.answered}/{len(dataset)} "
                    f"({elapsed:.1f}s, {comp_tokens} tok)"
                )
            except Exception as exc:  # noqa: BLE001
                stats.failed += 1
                out_lines.append(
                    json.dumps(
                        {
                            "question": question,
                            "ground_truth": ground_truth,
                            "answer": "",
                            "contexts": [],
                            "completion_tokens": 0,
                            "latency_s": 0,
                            "tokens_per_s": 0,
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )
                print(f"    [{alias}] FAILED q: {question[:60]} -> {exc}")
    finally:
        server.stop()
        cache_dir.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + ("\n" if out_lines else ""))

    return stats


# --- Scoring (RAGAS via fixed judge) --------------------------------------
def _score_run(
    cache_dir: Path,
    alias: str,
    judge_base_url: str,
    judge_model: str,
    judge_api_key: str,
) -> Dict[str, Any]:
    """Score a cached run with RAGAS. Returns {metric -> {mean,min,max}}."""
    import django

    django.setup()

    from app.services.ragas_v2 import RAGASEvaluatorV2

    cache_path = cache_dir / f"{alias}.jsonl"
    questions: List[str] = []
    answers: List[str] = []
    contexts: List[List[str]] = []
    ground_truths: List[str] = []
    with cache_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            questions.append(rec["question"])
            answers.append(rec["answer"])
            contexts.append(rec.get("contexts", []))
            ground_truths.append(rec["ground_truth"])

    evaluator = RAGASEvaluatorV2(
        judge_base_url=judge_base_url,
        judge_model=judge_model,
        judge_api_key=judge_api_key,
    )

    # Build results dict the RAGAS scoring path expects.
    valid = [
        {
            "question": q,
            "answer": a,
            "contexts": c,
            "ground_truth": g,
        }
        for q, a, c, g in zip(questions, answers, contexts, ground_truths)
        if a.strip()
    ]
    if not valid:
        return {}

    result = _ragas_score_samples(evaluator, valid)
    return result.get("scores", {})


def _ragas_score_samples(evaluator: Any, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reuse RAGASEvaluatorV2 internals to score pre-computed answers.

    Mirrors the scoring half of ``RAGASEvaluatorV2.evaluate`` but accepts
    answers generated by an arbitrary model (not the live pipeline).
    """
    from ragas import evaluate as ragas_evaluate
    from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
    from ragas.metrics import (
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        Faithfulness,
    )
    from ragas.run_config import RunConfig

    judge_config = evaluator._resolve_judge_config()
    judge_llm = evaluator._build_judge_llm(judge_config)
    ragas_embeddings = evaluator._build_ragas_embeddings()

    ragas_samples = [
        SingleTurnSample(
            user_input=s["question"],
            retrieved_contexts=s["contexts"],
            response=s["answer"],
            reference=s["ground_truth"],
        )
        for s in samples
    ]
    dataset = EvaluationDataset(samples=ragas_samples)
    metrics = [
        Faithfulness(),
        AnswerRelevancy(),
        ContextPrecision(),
        ContextRecall(),
    ]
    result = ragas_evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=ragas_embeddings,
        run_config=RunConfig(timeout=300, max_workers=2),
    )
    df = result.to_pandas()
    scores: Dict[str, Any] = {}
    for col in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        if col in df.columns:
            vals = df[col].dropna()
            scores[col] = {
                "mean": float(vals.mean()),
                "min": float(vals.min()),
                "max": float(vals.max()),
            }
    return {"scores": scores, "detailed": df.to_dict(orient="records")}


# --- Main ------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Compare local RAG LLM models")
    parser.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Aliases to compare (default: all in MODEL_CATALOG)",
    )
    parser.add_argument(
        "--server-exe",
        default=r"C:\Users\wongs\Desktop\llama-b10208-bin-win-cuda-12.4-x64\llama-server.exe",
    )
    parser.add_argument(
        "--models-dir",
        default=r"C:\Users\wongs\Desktop\llama-b10208-bin-win-cuda-12.4-x64",
    )
    parser.add_argument("--dataset", default="eval_baseline.jsonl")
    parser.add_argument(
        "--port",
        type=int,
        default=8090,
        help="Port for the model-under-test llama-server (uses 8090 to avoid "
        "clashing with a production llama-server already on 8080).",
    )
    parser.add_argument(
        "--n-gpu-layers",
        type=int,
        default=999,
        help="GPU layers for llama-server (999 = offload all; use a small N "
        "for partial offload or 0 for pure CPU).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="Number of dataset questions to run per model (default 8).",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--judge-base-url", default=JUDGE_BASE_URL)
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument(
        "--judge-api-key",
        default="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",
    )
    parser.add_argument("--skip-score", action="store_true", help="Generate only, skip RAGAS")
    parser.add_argument("--out-dir", default="outputs/model_comparison")
    args = parser.parse_args()

    aliases = args.models or list(MODEL_CATALOG.keys())
    unknown = [a for a in aliases if a not in MODEL_CATALOG]
    if unknown:
        parser.error(f"Unknown model aliases: {unknown} (known: {list(MODEL_CATALOG)})")

    out_dir = Path(args.out_dir)
    cache_dir = out_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    dataset = _load_dataset(Path(args.dataset).resolve() or REPO_ROOT / args.dataset)
    if not dataset:
        parser.error(f"Dataset empty: {args.dataset}")
    if args.limit and args.limit < len(dataset):
        dataset = dataset[: args.limit]
    print(f"Dataset: {len(dataset)} questions (limit={args.limit})")

    server_exe = args.server_exe
    if not Path(server_exe).exists():
        parser.error(f"llama-server.exe not found: {server_exe}")

    all_stats: Dict[str, RunStats] = {}
    for alias in aliases:
        print(f"\n=== Generating with {alias} (ngl={args.n_gpu_layers}) ===")
        stats = _run_model(
            alias=alias,
            server_exe=server_exe,
            models_dir=args.models_dir,
            model_path=MODEL_CATALOG[alias],
            port=args.port,
            n_gpu_layers=args.n_gpu_layers,
            dataset=dataset,
            cache_dir=cache_dir,
            top_k=args.top_k,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
        )
        all_stats[alias] = stats
        print(f"  -> {stats.summary()}")

    # Score every run with the same judge.
    scores: Dict[str, Dict[str, Any]] = {}
    if not args.skip_score:
        for alias in aliases:
            print(f"\n=== Scoring {alias} with judge {args.judge_model} ===")
            try:
                scores[alias] = _score_run(
                    cache_dir=cache_dir,
                    alias=alias,
                    judge_base_url=args.judge_base_url,
                    judge_model=args.judge_model,
                    judge_api_key=args.judge_api_key,
                )
                print(f"  -> {scores[alias]}")
            except Exception as exc:  # noqa: BLE001
                print(f"  -> SCORE FAILED: {exc}")
                scores[alias] = {"error": str(exc)}

    # Aggregate result
    aggregated = {
        "timestamp": datetime.now().isoformat(),
        "judge": {"base_url": args.judge_base_url, "model": args.judge_model},
        "n_gpu_layers": args.n_gpu_layers,
        "models": {
            alias: {
                "stats": all_stats[alias].summary(),
                "ragas": scores.get(alias, {}),
            }
            for alias in aliases
        },
    }
    result_path = out_dir / "results.json"
    with result_path.open("w", encoding="utf-8") as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {result_path}")


if __name__ == "__main__":
    main()
