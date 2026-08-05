# DeepEval RAG Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有 RAG 系统新增一条与 RAGAS 平行的 deepeval 评估通道:支持从 PDF/JSONL 生成测试集、用可配置 judge LLM(gemini/openrouter/local_llm)本地运行 deepeval RAG 指标、输出每用例明细 CSV 与汇总报告。

**Architecture:** 新增 `evaluation/deepeval_evaluator.py`,结构镜像现有 `evaluation/ragas_evaluator.py`(三入口:`evaluate_from_pdfs` / `evaluate_from_jsonl` / `evaluate`)。judge 通过自定义 `DeepEvalBaseLLM` 子类复用 `app/services/llm_client.call_llm`(不引入第二个 HTTP 客户端,judge provider 跟随项目 runtime 设置,可被 `DEEPEVAL_*` 环境变量或 CLI 参数覆盖)。RAG 管道执行委托给现有 `RAGASEvaluator.run_rag_pipeline`(复用 hybrid retrieval + 生成,零重复,不重构现有文件)。deepeval 4.x 无全局 `set_default_model`,judge 通过每个 metric 的 `model=` 参数注入。不执行 `deepeval login`,评估完全本地运行(不上传 Confident AI)。

**Tech Stack:** deepeval>=4.0.0,<5.0.0 · Python 3.11(项目 .venv) · pytest · Black/Ruff/mypy

## Global Constraints

- Python 3.9+ 兼容类型标注:`Optional[X]` / `List` / `Dict`(不用 `X | None`)。
- 行宽 88(Black 默认);imports 分组 stdlib → 第三方 → 本地;`__all__` 声明公共 API。
- deepeval 版本锁定 `deepeval>=4.0.0,<5.0.0`(requirements.txt 的 RAGAS evaluation 段)。
- deepeval 4.x 的 `LLMTestCase` 字段名为 **`input`**(不是 `query`),构造时用 `input=...`。
- judge 后端统一走 `app.services.llm_client.call_llm(provider, model, call_type, messages, timeout, query_text, **kwargs)`;`call_llm` 返回 `str` 或 `(str, ...)` 元组,必须解包取首元素。
- `call_llm` 会写 Django `QueryLog`,因此 CLI 与测试必须先 `django.setup()`(conftest.py 已处理测试侧)。
- Windows 下 torch/pyarrow DLL 加载顺序问题:CLI 脚本在导入 deepeval/ragas 之前先 `import torch`(与 `scripts/run_evaluation.py:27-33` 相同 workaround)。
- 评估必须本地运行:绝不调用 `deepeval login`,不传 `metric_collection`(这两者才会触发上传 Confident AI)。
- 报告 CSV 命名沿用现有惯例:`evaluation/deepeval_results_YYYYMMDD_HHMMSS.csv`。

---

### Task 1: 安装并验证 deepeval 依赖

**Files:**
- Modify: `requirements.txt`(RAGAS evaluation 段,`ragas>=0.1.0,<1.0.0` 之后)
- Test: 手动验证命令(无新增测试文件)

**Interfaces:**
- Produces: 环境可 `import deepeval`,版本 ≥4.0.0 且 <5.0.0;现有测试不回归。

- [ ] **Step 1: 修改 requirements.txt 添加依赖**

在 `requirements.txt` 的 `# RAGAS evaluation` 段末尾(`pyarrow>=8.0.0,<17` 之后)追加:

```text

# DeepEval evaluation (RAG metrics, local judge)
deepeval>=4.0.0,<5.0.0
```

- [ ] **Step 2: 安装**

Run: `.venv/Scripts/python -m pip install -r requirements.txt`
Expected: 安装成功;若与现有 `langchain`/`faiss-cpu==1.7.4` 依赖冲突,pip 报错——此时记录冲突并选择:优先保现有运行时,尝试 `pip install "deepeval==4.1.5"` 单独解决;若仍冲突,回退方案为在计划中追加 Task 0(隔离虚拟环境 `requirements-eval.txt`)并向用户说明。默认预期无冲突。

- [ ] **Step 3: 验证 deepeval 可导入且版本正确**

Run:
```bash
.venv/Scripts/python -c "import deepeval; print(deepeval.__version__)"
.venv/Scripts/python -c "from deepeval.models import DeepEvalBaseLLM; from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric, ContextualPrecisionMetric, ContextualRecallMetric, ContextualRelevancyMetric; from deepeval.test_case import LLMTestCase; print('imports ok')"
```
Expected: 打印 ≥4.0.0 的版本号和 `imports ok`。

- [ ] **Step 4: 现有测试冒烟回归**

Run: `.venv/Scripts/python -m pytest tests/test_ragas_eval.py tests/test_llm_client.py -q`
Expected: 全部 PASS(确认 deepeval 安装未破坏 RAGAS/langchain 链路)。

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "build: add deepeval>=4 for RAG evaluation"
```

---

### Task 2: DeepEvalJudgeLLM 适配器 + resolve_judge_config

**Files:**
- Create: `evaluation/deepeval_evaluator.py`(本任务实现前半部分:judge LLM 与配置解析)
- Test: `tests/test_deepeval_evaluator.py`(本任务新增前半部分测试)

**Interfaces:**
- Consumes: `app.services.llm_client.call_llm(provider, model, call_type, messages, timeout, query_text, **kwargs)`;`app.services.runtime_llm.load_runtime_llm_settings() -> Dict[str, Optional[str]]`(键:`provider`/`model`/`api_key`/`base_url`);`deepeval.models.DeepEvalBaseLLM`。
- Produces:
  - `resolve_judge_config(provider=None, model=None, api_key=None, base_url=None) -> Dict[str, str]`,键 `provider`/`model`/`api_key`/`base_url`。优先级:显式参数 > `DEEPEVAL_PROVIDER`/`DEEPEVAL_MODEL`/`DEEPEVAL_API_KEY`/`DEEPEVAL_BASE_URL` 环境变量 > `load_runtime_llm_settings()`。
  - `class DeepEvalJudgeLLM(DeepEvalBaseLLM)`:`__init__(self, provider: str, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None, call_type: str = "deepeval_judge", timeout: int = 300)`;实现 `load_model()`、`generate(prompt: str, **kwargs) -> str`、`async a_generate(prompt: str, **kwargs) -> str`、`get_model_name() -> str`。
  - 模块级异常 `DeepEvalEvaluatorError(Exception)`。

- [ ] **Step 1: 写失败的测试**

`tests/test_deepeval_evaluator.py`:

```python
"""Tests for the DeepEval RAG evaluator (judge LLM adapter + config)."""

import os
from types import SimpleNamespace

import pytest


def test_resolve_judge_config_prefers_explicit_args():
    from evaluation.deepeval_evaluator import resolve_judge_config

    cfg = resolve_judge_config(
        provider="openrouter",
        model="deepseek/deepseek-v4-flash",
        api_key="sk-explicit",
        base_url="https://openrouter.ai/api/v1",
    )
    assert cfg == {
        "provider": "openrouter",
        "model": "deepseek/deepseek-v4-flash",
        "api_key": "sk-explicit",
        "base_url": "https://openrouter.ai/api/v1",
    }


def test_resolve_judge_config_uses_deepeval_env_vars(monkeypatch):
    from evaluation.deepeval_evaluator import resolve_judge_config

    monkeypatch.setenv("DEEPEVAL_PROVIDER", "gemini")
    monkeypatch.setenv("DEEPEVAL_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("DEEPEVAL_API_KEY", "sk-env")
    monkeypatch.setenv("DEEPEVAL_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")

    cfg = resolve_judge_config()
    assert cfg["provider"] == "gemini"
    assert cfg["model"] == "gemini-2.5-flash"
    assert cfg["api_key"] == "sk-env"
    assert cfg["base_url"] == "https://generativelanguage.googleapis.com/v1beta"


def test_resolve_judge_config_falls_back_to_runtime_settings(monkeypatch):
    from evaluation.deepeval_evaluator import resolve_judge_config

    monkeypatch.delenv("DEEPEVAL_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPEVAL_MODEL", raising=False)
    monkeypatch.delenv("DEEPEVAL_API_KEY", raising=False)
    monkeypatch.delenv("DEEPEVAL_BASE_URL", raising=False)

    fake_runtime = {
        "provider": "local_llm",
        "model": "qwen2.5:3b",
        "api_key": None,
        "base_url": "http://localhost:8080",
    }
    monkeypatch.setattr(
        "app.services.runtime_llm.load_runtime_llm_settings", lambda: fake_runtime
    )

    cfg = resolve_judge_config()
    assert cfg["provider"] == "local_llm"
    assert cfg["model"] == "qwen2.5:3b"
    assert cfg["base_url"] == "http://localhost:8080"


def test_judge_llm_generate_wraps_call_llm(monkeypatch):
    from evaluation.deepeval_evaluator import DeepEvalJudgeLLM

    captured = {}

    def fake_call_llm(**kwargs):
        captured.update(kwargs)
        return ("judged answer", 42)  # tuple form, must unpack to str

    monkeypatch.setattr("app.services.llm_client.call_llm", fake_call_llm)

    judge = DeepEvalJudgeLLM(
        provider="openrouter",
        model="deepseek/deepseek-v4-flash",
        api_key="sk-1",
        base_url="https://openrouter.ai/api/v1",
    )
    out = judge.generate("Is the answer grounded in the context?")

    assert out == "judged answer"
    assert captured["provider"] == "openrouter"
    assert captured["model"] == "deepseek/deepseek-v4-flash"
    assert captured["call_type"] == "deepeval_judge"
    assert captured["messages"] == [
        {"role": "user", "content": "Is the answer grounded in the context?"}
    ]
    assert captured["api_key"] == "sk-1"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"


def test_judge_llm_generate_local_llm_kwargs(monkeypatch):
    from evaluation.deepeval_evaluator import DeepEvalJudgeLLM

    captured = {}

    def fake_call_llm(**kwargs):
        captured.update(kwargs)
        return "plain string"

    monkeypatch.setattr("app.services.llm_client.call_llm", fake_call_llm)

    judge = DeepEvalJudgeLLM(
        provider="local_llm",
        model="qwen2.5:3b",
        base_url="http://localhost:8080",
    )
    assert judge.generate("q") == "plain string"
    assert captured["api_key"] not in captured  # local_llm 不传 api_key
    assert captured["base_url"] == "http://localhost:8080"
    assert captured["num_predict"] == 4096


def test_judge_llm_get_model_name():
    from evaluation.deepeval_evaluator import DeepEvalJudgeLLM

    judge = DeepEvalJudgeLLM(provider="gemini", model="gemini-2.5-flash")
    assert judge.get_model_name() == "gemini-2.5-flash"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/Scripts/python -m pytest tests/test_deepeval_evaluator.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'evaluation.deepeval_evaluator'`。

- [ ] **Step 3: 实现 judge 适配器与配置解析**

`evaluation/deepeval_evaluator.py`(本任务范围):

```python
"""DeepEval-based RAG evaluation, parallel to ``evaluation.ragas_evaluator``.

Provides a local, cloud-free DeepEval evaluation path for the RAG pipeline:
- ``DeepEvalJudgeLLM``: a ``DeepEvalBaseLLM`` subclass that reuses
  ``app.services.llm_client.call_llm`` as the judge backend, so the judge
  provider/model follow the project runtime settings (gemini / openrouter /
  local_llm) and can be overridden via ``DEEPEVAL_*`` env vars or CLI args.
- ``DeepEvalEvaluator``: runs the RAG pipeline and scores answers with
  DeepEval RAG metrics (Faithfulness, Answer Relevancy, Contextual
  Precision/Recall, Contextual Relevancy), writing per-case CSV results.

Usage:
    from evaluation.deepeval_evaluator import DeepEvalEvaluator

    evaluator = DeepEvalEvaluator()
    result = evaluator.evaluate_from_jsonl("eval.jsonl", top_k=5)
    print(result["report"])
"""
```

完整模块实现见下方,本任务先写配置解析与 judge 类(模块骨架 + `__all__` 只含已实现符号;Task 3 追加其余):

```python
import asyncio
import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

from app.services.runtime_llm import load_runtime_llm_settings  # noqa: E402

logger = logging.getLogger("deepeval_eval")


class DeepEvalEvaluatorError(Exception):
    """Custom exception for DeepEval evaluator errors."""

    pass


def resolve_judge_config(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, str]:
    """Resolve the judge LLM config used by DeepEval metrics.

    Priority: explicit args > DEEPEVAL_* env vars > runtime LLM settings.
    """
    if provider and model:
        return {
            "provider": provider,
            "model": model,
            "api_key": api_key or "",
            "base_url": base_url or "",
        }

    env_provider = os.environ.get("DEEPEVAL_PROVIDER")
    env_model = os.environ.get("DEEPEVAL_MODEL")
    env_api_key = os.environ.get("DEEPEVAL_API_KEY")
    env_base_url = os.environ.get("DEEPEVAL_BASE_URL")
    if env_provider and env_model:
        return {
            "provider": env_provider,
            "model": env_model,
            "api_key": env_api_key or "",
            "base_url": env_base_url or "",
        }

    rt = load_runtime_llm_settings()
    return {
        "provider": provider or rt.get("provider") or "local_llm",
        "model": model or rt.get("model") or "",
        "api_key": api_key or rt.get("api_key") or "",
        "base_url": base_url or rt.get("base_url") or "",
    }


class DeepEvalJudgeLLM:
    """Placeholder — replaced by the real DeepEvalBaseLLM subclass in Step 3."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError
```

> 注意:Step 3 的最终版 `DeepEvalJudgeLLM` 继承 `deepeval.models.DeepEvalBaseLLM`(延迟导入,见下),并实现:

```python
class DeepEvalJudgeLLM:  # 实际应继承 DeepEvalBaseLLM,见下方注释
    ...
```

**实现指引(写代码时按此展开,避免占位):**

模块顶部**不要** `import deepeval`(重量级),在 `DeepEvalJudgeLLM` 内按需导入:

```python
class DeepEvalJudgeLLM(DeepEvalBaseLLM):  # 由 _import_deepeval() 提供基类
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        call_type: str = "deepeval_judge",
        timeout: int = 300,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key or ""
        self.base_url = base_url or ""
        self.call_type = call_type
        self.timeout = timeout
        super().__init__(model=model)

    def load_model(self) -> Dict[str, str]:
        """Return an opaque handle consumed by ``generate``/``a_generate``."""
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
        }

    def _provider_kwargs(self) -> Dict[str, Any]:
        if self.provider == "local_llm":
            return {"base_url": self.base_url, "num_predict": 4096}
        if self.provider in ("gemini", "openrouter"):
            return {"api_key": self.api_key, "base_url": self.base_url}
        return {}

    def _call(self, prompt: str) -> str:
        from app.services.llm_client import call_llm

        result = call_llm(
            provider=self.provider,
            model=self.model,
            call_type=self.call_type,
            messages=[{"role": "user", "content": prompt}],
            timeout=self.timeout,
            query_text=prompt[:120],
            **self._provider_kwargs(),
        )
        if isinstance(result, tuple):
            result = result[0]
        return str(result)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return self._call(prompt)

    async def a_generate(self, prompt: str, **kwargs: Any) -> str:
        return await asyncio.to_thread(self._call, prompt)

    def get_model_name(self) -> str:
        return self.model
```

基类导入方式(模块级延迟,保证测试可先于 deepeval 安装失败时给出清晰报错,也避免拖慢无关测试):

```python
def _import_deepeval():
    try:
        from deepeval.models import DeepEvalBaseLLM

        return DeepEvalBaseLLM
    except ImportError as exc:
        raise DeepEvalEvaluatorError(
            "DeepEval not installed. Run: pip install 'deepeval>=4,<5'"
        ) from exc


_DEEPEVAL_BASE_LLM = None


def _get_base_llm():
    global _DEEPEVAL_BASE_LLM
    if _DEEPEVAL_BASE_LLM is None:
        _DEEPEVAL_BASE_LLM = _import_deepeval()
    return _DEEPEVAL_BASE_LLM
```

`DeepEvalJudgeLLM` 最终定义为:`class DeepEvalJudgeLLM(_get_base_llm()):`——由于 `__init_subclass__` 在类创建时触发,`_get_base_llm()` 会在模块导入时执行一次(此时 deepeval 已安装,Task 1 保证)。若 deepeval 缺失,模块导入抛 `DeepEvalEvaluatorError`,与 ragas 的延迟报错风格一致。

模块 `__all__`:

```python
__all__ = [
    "DeepEvalEvaluatorError",
    "DeepEvalJudgeLLM",
    "resolve_judge_config",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/Scripts/python -m pytest tests/test_deepeval_evaluator.py -q`
Expected: PASS(6 个测试)。

- [ ] **Step 5: Commit**

```bash
git add evaluation/deepeval_evaluator.py tests/test_deepeval_evaluator.py
git commit -m "feat(evaluation): add DeepEval judge LLM adapter and config resolution"
```

---

### Task 3: DeepEvalEvaluator 核心(指标、evaluate、报告、CSV)

**Files:**
- Modify: `evaluation/deepeval_evaluator.py`(追加 `DeepEvalEvaluator` 类与指标工厂)
- Test: `tests/test_deepeval_evaluator.py`(追加后半部分测试)

**Interfaces:**
- Consumes:
  - Task 2:`DeepEvalJudgeLLM`、`resolve_judge_config`、`DeepEvalEvaluatorError`。
  - `evaluation.ragas_evaluator.RAGASEvaluator.run_rag_pipeline(questions: List[str], top_k: int) -> List[Dict[str, Any]]`,每项含 `question`/`answer`/`contexts`。
  - deepeval 4.x:`from deepeval.evaluate import evaluate`;`from deepeval.test_case import LLMTestCase`;`from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric, ContextualPrecisionMetric, ContextualRecallMetric, ContextualRelevancyMetric`。
- Produces:
  - `DEFAULT_METRICS: List[str] = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]`
  - `build_metrics(judge: DeepEvalJudgeLLM, names: Optional[List[str]] = None) -> List[Any]`
  - `class DeepEvalEvaluator`:
    - `__init__(self, provider=None, model=None, api_key=None, base_url=None, call_type: str = "deepeval_judge", timeout: int = 300)`
    - `run_rag_pipeline(questions: List[str], top_k: int = 5) -> List[Dict[str, Any]]`(委托 `RAGASEvaluator().run_rag_pipeline`)
    - `evaluate(questions: List[str], ground_truths: List[str], top_k: int = 5, metrics: Optional[List[str]] = None, batch_size: int = 5, output_path: Optional[str] = None) -> Dict[str, Any]`——返回 `{"scores": {...}, "num_questions": int, "detailed": List[Dict], "csv_path": str, "report": str}`;`scores` 为每指标 `{"avg_score": float, "threshold": float, "pass_rate": float}`。
    - `evaluate_from_pdfs(pdf_paths, num_questions_per_pdf=5, top_k=5, language="en", metrics=None, batch_size=5, output_path=None)`——复用 `RAGASEvaluator.generate_qa_from_text` 生成 QA(委托方式与 ragas 版一致)。
    - `evaluate_from_jsonl(jsonl_path, top_k=5, metrics=None, batch_size=5, output_path=None)`——JSONL 格式 `{"question": "...", "ground_truth": "..."}`。
    - `format_report(result: Dict[str, Any]) -> str`(静态方法)。
  - `_metrics_to_rows(test_results) -> List[Dict]`(内部,供测试直接验证)。

- [ ] **Step 1: 写失败的测试**

`tests/test_deepeval_evaluator.py` 追加:

```python
def _fake_result(test_case_input, metric_name, score, success=True, threshold=0.5):
    metric_data = SimpleNamespace(
        name=metric_name,
        score=score,
        threshold=threshold,
        success=success,
        reason="ok",
        error=None,
        strict_mode=False,
        is_flaky=False,
    )
    return SimpleNamespace(
        test_case=SimpleNamespace(input=test_case_input),
        metrics_data=[metric_data],
    )


def test_build_metrics_creates_requested_metrics(monkeypatch):
    from evaluation.deepeval_evaluator import build_metrics

    judge = SimpleNamespace(get_model_name=lambda: "m")
    monkeypatch.setattr(
        "evaluation.deepeval_evaluator._import_metrics",
        lambda: SimpleNamespace(
            FaithfulnessMetric=lambda **kw: SimpleNamespace(name="Faithfulness", **kw),
            AnswerRelevancyMetric=lambda **kw: SimpleNamespace(name="AnswerRelevancy", **kw),
            ContextualPrecisionMetric=lambda **kw: SimpleNamespace(name="ContextualPrecision", **kw),
            ContextualRecallMetric=lambda **kw: SimpleNamespace(name="ContextualRecall", **kw),
            ContextualRelevancyMetric=lambda **kw: SimpleNamespace(name="ContextualRelevancy", **kw),
        ),
    )
    metrics = build_metrics(judge, ["faithfulness", "contextual_relevancy"])
    assert [m.name for m in metrics] == ["Faithfulness", "ContextualRelevancy"]
    assert all(m.model is judge for m in metrics)


def test_build_metrics_rejects_unknown():
    from evaluation.deepeval_evaluator import build_metrics

    judge = SimpleNamespace(get_model_name=lambda: "m")
    with pytest.raises(ValueError, match="Unknown metric: nope"):
        build_metrics(judge, ["nope"])


def test_evaluate_maps_to_llm_test_cases(monkeypatch, tmp_path):
    from evaluation.deepeval_evaluator import DeepEvalEvaluator

    captured = {}

    def fake_run_pipeline(questions, top_k=5):
        return [
            {"question": q, "answer": f"answer for {q}", "contexts": ["ctx1", "ctx2"]}
            for q in questions
        ]

    def fake_evaluate(test_cases, metrics, **kwargs):
        captured["test_cases"] = test_cases
        captured["metrics"] = metrics
        return SimpleNamespace(
            test_results=[
                _fake_result(tc.input, "Faithfulness", 0.9) for tc in test_cases
            ]
        )

    monkeypatch.setattr(
        "evaluation.ragas_evaluator.RAGASEvaluator.run_rag_pipeline", fake_run_pipeline
    )
    monkeypatch.setattr(
        "evaluation.deepeval_evaluator.deepeval_evaluate", fake_evaluate, raising=False
    )

    out_path = str(tmp_path / "deep.csv")
    evaluator = DeepEvalEvaluator(provider="openrouter", model="m", api_key="k")
    result = evaluator.evaluate(
        questions=["q1", "q2"],
        ground_truths=["g1", "g2"],
        top_k=3,
        metrics=["faithfulness"],
        batch_size=1,
        output_path=out_path,
    )

    assert len(captured["test_cases"]) == 1  # batch_size=1 → 每次 1 条
    tc = captured["test_cases"][0]
    assert tc.input == "q1"
    assert tc.actual_output == "answer for q1"
    assert tc.expected_output == "g1"
    assert tc.retrieval_context == ["ctx1", "ctx2"]
    assert captured["metrics"][0].name == "Faithfulness"

    assert result["num_questions"] == 2
    assert result["scores"]["Faithfulness"]["avg_score"] == pytest.approx(0.9)
    assert result["scores"]["Faithfulness"]["pass_rate"] == pytest.approx(1.0)
    assert result["csv_path"] == out_path
    assert "DeepEval" in result["report"]


def test_evaluate_skips_empty_answers(monkeypatch, tmp_path):
    from evaluation.deepeval_evaluator import DeepEvalEvaluator

    def fake_run_pipeline(questions, top_k=5):
        return [
            {"question": "q1", "answer": "", "contexts": []},
            {"question": "q2", "answer": "ok", "contexts": ["c"]},
        ]

    captured = {}

    def fake_evaluate(test_cases, metrics, **kwargs):
        captured["count"] = len(test_cases)
        return SimpleNamespace(
            test_results=[_fake_result("q2", "Faithfulness", 1.0)]
        )

    monkeypatch.setattr(
        "evaluation.ragas_evaluator.RAGASEvaluator.run_rag_pipeline", fake_run_pipeline
    )
    monkeypatch.setattr(
        "evaluation.deepeval_evaluator.deepeval_evaluate", fake_evaluate, raising=False
    )

    evaluator = DeepEvalEvaluator()
    result = evaluator.evaluate(
        questions=["q1", "q2"],
        ground_truths=["g1", "g2"],
        output_path=str(tmp_path / "out.csv"),
    )
    assert captured["count"] == 1
    assert result["num_questions"] == 1


def test_evaluate_from_jsonl(monkeypatch, tmp_path):
    import json

    from evaluation.deepeval_evaluator import DeepEvalEvaluator

    jsonl_path = tmp_path / "qa.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"question": "q1", "ground_truth": "g1"}) + "\n")

    seen = {}

    def fake_evaluate(questions, ground_truths, **kwargs):
        seen["questions"] = questions
        seen["ground_truths"] = ground_truths
        return {
            "scores": {},
            "num_questions": 1,
            "detailed": [],
            "csv_path": "",
            "report": "",
        }

    monkeypatch.setattr(
        "evaluation.deepeval_evaluator.DeepEvalEvaluator.evaluate",
        fake_evaluate,
        raising=False,
    )

    evaluator = DeepEvalEvaluator()
    evaluator.evaluate_from_jsonl(str(jsonl_path))
    assert seen["questions"] == ["q1"]
    assert seen["ground_truths"] == ["g1"]


def test_format_report_contains_scores():
    from evaluation.deepeval_evaluator import DeepEvalEvaluator

    result = {
        "scores": {
            "Faithfulness": {"avg_score": 0.9, "threshold": 0.5, "pass_rate": 1.0},
            "AnswerRelevancy": {"avg_score": 0.75, "threshold": 0.5, "pass_rate": 0.8},
        },
        "num_questions": 10,
    }
    report = DeepEvalEvaluator.format_report(result)
    assert "DeepEval EVALUATION REPORT" in report
    assert "Questions evaluated: 10" in report
    assert "Faithfulness" in report and "0.9000" in report
    assert "AnswerRelevancy" in report and "0.7500" in report
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/Scripts/python -m pytest tests/test_deepeval_evaluator.py -q`
Expected: FAIL(`DeepEvalEvaluator` / `build_metrics` / `deepeval_evaluate` 未定义)。

- [ ] **Step 3: 实现 evaluator 核心**

在 `evaluation/deepeval_evaluator.py` 追加(放在 Task 2 的 `resolve_judge_config`/`DeepEvalJudgeLLM` 之后、`__all__` 更新):

```python
DEFAULT_METRICS: List[str] = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]

_METRIC_NAMES = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "AnswerRelevancy",
    "context_precision": "ContextualPrecision",
    "context_recall": "ContextualRecall",
    "contextual_relevancy": "ContextualRelevancy",
}


def _import_metrics() -> Any:
    """Lazily import deepeval metric classes (keeps module import light)."""
    from deepeval.metrics import (  # noqa: F401
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
    )

    return SimpleNamespace(
        FaithfulnessMetric=FaithfulnessMetric,
        AnswerRelevancyMetric=AnswerRelevancyMetric,
        ContextualPrecisionMetric=ContextualPrecisionMetric,
        ContextualRecallMetric=ContextualRecallMetric,
        ContextualRelevancyMetric=ContextualRelevancyMetric,
    )


def build_metrics(
    judge: Any,
    names: Optional[List[str]] = None,
) -> List[Any]:
    """Build the requested DeepEval metrics, all bound to ``judge``."""
    selected = names or list(DEFAULT_METRICS)
    for name in selected:
        if name not in _METRIC_NAMES:
            raise ValueError(f"Unknown metric: {name}. Valid: {sorted(_METRIC_NAMES)}")

    m = _import_metrics()
    factories = {
        "faithfulness": lambda: m.FaithfulnessMetric(model=judge),
        "answer_relevancy": lambda: m.AnswerRelevancyMetric(model=judge),
        "context_precision": lambda: m.ContextualPrecisionMetric(model=judge),
        "context_recall": lambda: m.ContextualRecallMetric(model=judge),
        "contextual_relevancy": lambda: m.ContextualRelevancyMetric(model=judge),
    }
    return [factories[name]() for name in selected]
```

> 注意:`_import_metrics` 里用 `SimpleNamespace` 需要 `from types import SimpleNamespace`(模块顶部 import)。若实现时希望直接返回 `__import__` 结果,也可以改为返回 dict 并让 `build_metrics` 用 `m["FaithfulnessMetric"]`——二选一,测试只 patch `_import_metrics` 且要求返回值同时支持 `.FaithfulnessMetric` 属性访问,因此**必须**用 `SimpleNamespace`。

`DeepEvalEvaluator` 类:

```python
class DeepEvalEvaluator:
    """DeepEval-based evaluator for RAG pipeline quality.

    Runs the existing RAG pipeline (via ``RAGASEvaluator.run_rag_pipeline``)
    and scores the outputs with DeepEval RAG metrics. The judge LLM reuses
    ``app.services.llm_client.call_llm`` (gemini / openrouter / local_llm).
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        call_type: str = "deepeval_judge",
        timeout: int = 300,
    ) -> None:
        self.judge_config = resolve_judge_config(
            provider=provider, model=model, api_key=api_key, base_url=base_url
        )
        self.call_type = call_type
        self.timeout = timeout

    def _build_judge(self) -> DeepEvalJudgeLLM:
        return DeepEvalJudgeLLM(
            provider=self.judge_config["provider"],
            model=self.judge_config["model"],
            api_key=self.judge_config["api_key"] or None,
            base_url=self.judge_config["base_url"] or None,
            call_type=self.call_type,
            timeout=self.timeout,
        )

    def run_rag_pipeline(
        self, questions: List[str], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Run the RAG pipeline (hybrid retrieval + generation)."""
        from evaluation.ragas_evaluator import RAGASEvaluator

        return RAGASEvaluator().run_rag_pipeline(questions, top_k=top_k)

    def evaluate(
        self,
        questions: List[str],
        ground_truths: List[str],
        top_k: int = 5,
        metrics: Optional[List[str]] = None,
        batch_size: int = 5,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run DeepEval metrics over RAG outputs.

        Returns dict with ``scores`` (per-metric avg_score/threshold/pass_rate),
        ``num_questions``, ``detailed`` (per-case rows), ``csv_path`` and
        ``report`` (formatted string).
        """
        if len(questions) != len(ground_truths):
            raise DeepEvalEvaluatorError(
                "questions and ground_truths must have the same length"
            )

        from deepeval.evaluate import evaluate as deepeval_evaluate
        from deepeval.test_case import LLMTestCase

        logger.info("Running RAG pipeline for %d questions...", len(questions))
        rag_results = self.run_rag_pipeline(questions, top_k=top_k)

        judge = self._build_judge()
        eval_metrics = build_metrics(judge, metrics)

        rows: List[Dict[str, Any]] = []
        test_cases: List[Any] = []
        for rag_result, gt in zip(rag_results, ground_truths):
            if not rag_result["answer"]:
                continue
            test_cases.append(
                LLMTestCase(
                    input=rag_result["question"],
                    actual_output=rag_result["answer"],
                    expected_output=gt,
                    retrieval_context=rag_result.get("contexts", []),
                )
            )

        if not test_cases:
            raise DeepEvalEvaluatorError("No valid RAG results to evaluate")

        logger.info("Running DeepEval evaluation over %d cases...", len(test_cases))
        for start in range(0, len(test_cases), max(1, batch_size)):
            batch = test_cases[start : start + batch_size]
            result = deepeval_evaluate(
                test_cases=batch,
                metrics=eval_metrics,
            )
            rows.extend(self._metrics_to_rows(result.test_results))

        csv_path = output_path or self._default_csv_path()
        self._write_csv(rows, csv_path)

        scores: Dict[str, Dict[str, float]] = {}
        for row in rows:
            entry = scores.setdefault(
                row["metric"],
                {"avg_score": 0.0, "threshold": row["threshold"], "pass_rate": 0.0, "count": 0, "passed": 0},
            )
            entry["count"] += 1
            entry["avg_score"] += row["score"]
            if row["success"]:
                entry["passed"] += 1
        for name, entry in scores.items():
            entry["avg_score"] = entry["avg_score"] / entry["count"]
            entry["pass_rate"] = entry["passed"] / entry["count"]
            del entry["count"]
            del entry["passed"]

        detailed = [
            {k: row[k] for k in ("input", "metric", "score", "threshold", "success", "reason")}
            for row in rows
        ]

        result: Dict[str, Any] = {
            "scores": scores,
            "num_questions": len(test_cases),
            "detailed": detailed,
            "csv_path": csv_path,
        }
        result["report"] = self.format_report(result)
        return result

    @staticmethod
    def _metrics_to_rows(test_results: List[Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for tr in test_results:
            tc_input = getattr(tr.test_case, "input", "")
            for md in tr.metrics_data:
                rows.append(
                    {
                        "input": tc_input,
                        "metric": md.name,
                        "score": float(md.score),
                        "threshold": float(getattr(md, "threshold", 0.5)),
                        "success": bool(getattr(md, "success", False)),
                        "reason": getattr(md, "reason", ""),
                    }
                )
        return rows

    @staticmethod
    def _default_csv_path() -> str:
        from datetime import datetime
        from pathlib import Path

        eval_dir = Path("evaluation")
        eval_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return str(eval_dir / f"deepeval_results_{ts}.csv")

    @staticmethod
    def _write_csv(rows: List[Dict[str, Any]], path: str) -> None:
        import csv

        fieldnames = ["input", "metric", "score", "threshold", "success", "reason"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows({k: row.get(k, "") for k in fieldnames} for row in rows)

    def evaluate_from_jsonl(
        self,
        jsonl_path: str,
        top_k: int = 5,
        metrics: Optional[List[str]] = None,
        batch_size: int = 5,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate from a JSONL file: {"question": "...", "ground_truth": "..."}."""
        import json

        questions: List[str] = []
        ground_truths: List[str] = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                questions.append(data["question"])
                ground_truths.append(data["ground_truth"])
        if not questions:
            raise DeepEvalEvaluatorError(f"No questions found in {jsonl_path}")
        return self.evaluate(
            questions=questions,
            ground_truths=ground_truths,
            top_k=top_k,
            metrics=metrics,
            batch_size=batch_size,
            output_path=output_path,
        )

    def evaluate_from_pdfs(
        self,
        pdf_paths: List[str],
        num_questions_per_pdf: int = 5,
        top_k: int = 5,
        language: str = "en",
        metrics: Optional[List[str]] = None,
        batch_size: int = 5,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """End-to-end evaluation from PDF files (auto-generate QA pairs)."""
        from evaluation.ragas_evaluator import RAGASEvaluator

        base = RAGASEvaluator()
        all_questions: List[str] = []
        all_ground_truths: List[str] = []
        for pdf_path in pdf_paths:
            if not os.path.exists(pdf_path):
                logger.warning("PDF not found: %s", pdf_path)
                continue
            text = base._read_pdf_text(pdf_path)  # type: ignore[attr-defined]
            if not text.strip():
                logger.warning("No text extracted from: %s", pdf_path)
                continue
            try:
                qa_pairs = base.generate_qa_from_text(
                    text=text,
                    num_questions=num_questions_per_pdf,
                    language=language,
                )
            except Exception as exc:  # noqa: BLE001 - mirror RAGAS flow
                logger.warning("Skipping PDF %s: %s", pdf_path, exc)
                continue
            for qa in qa_pairs:
                all_questions.append(qa["question"])
                all_ground_truths.append(qa["ground_truth"])
        if not all_questions:
            raise DeepEvalEvaluatorError("No questions generated from PDFs")
        return self.evaluate(
            questions=all_questions,
            ground_truths=all_ground_truths,
            top_k=top_k,
            metrics=metrics,
            batch_size=batch_size,
            output_path=output_path,
        )

    @staticmethod
    def format_report(result: Dict[str, Any]) -> str:
        """Format DeepEval evaluation result as a readable report."""
        scores = result.get("scores", {})
        num_q = result.get("num_questions", 0)
        lines = [
            "=" * 60,
            "DeepEval EVALUATION REPORT",
            "=" * 60,
            "",
            f"Questions evaluated: {num_q}",
            "",
            "METRICS:",
            "-" * 40,
        ]
        for metric, value in scores.items():
            if isinstance(value, dict):
                lines.append(
                    f"{metric:<25} avg={value['avg_score']:.4f} "
                    f"threshold={value['threshold']:.2f} pass={value['pass_rate']:.2%}"
                )
            else:
                lines.append(f"{metric:<25} {value}")
        lines.extend(["", "=" * 60])
        return "\n".join(lines)
```

> 实现注意:
> - `evaluate_from_pdfs` 里 `base._read_pdf_text` 实际不存在——`RAGASEvaluator` 用模块级函数 `from app.services.pdf_chunking import read_pdf_text`。写代码时改为直接 `from app.services.pdf_chunking import read_pdf_text` 并调用之,勿引用私有属性。计划中此行为已知笔误,实现时以正确方式书写(与 `ragas_evaluator.evaluate_from_pdfs:558` 一致)。
> - `evaluate()` 内的 `from deepeval.evaluate import evaluate as deepeval_evaluate` 是模块级名字绑定:测试里 `monkeypatch.setattr("evaluation.deepeval_evaluator.deepeval_evaluate", fake, raising=False)` 才能生效,因此**不要**把它写成局部别名之外的用法。

更新 `__all__`:

```python
__all__ = [
    "DEFAULT_METRICS",
    "DeepEvalEvaluator",
    "DeepEvalEvaluatorError",
    "DeepEvalJudgeLLM",
    "build_metrics",
    "resolve_judge_config",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/Scripts/python -m pytest tests/test_deepeval_evaluator.py -q`
Expected: PASS(11 个测试)。

- [ ] **Step 5: 代码质量检查**

Run: `.venv/Scripts/python -m ruff check evaluation/deepeval_evaluator.py tests/test_deepeval_evaluator.py`
Run: `.venv/Scripts/python -m black --check evaluation/deepeval_evaluator.py tests/test_deepeval_evaluator.py`
Expected: 无错误;若 black 报格式差异,运行 `black evaluation/deepeval_evaluator.py tests/test_deepeval_evaluator.py` 后重新跑测试。

- [ ] **Step 6: Commit**

```bash
git add evaluation/deepeval_evaluator.py tests/test_deepeval_evaluator.py
git commit -m "feat(evaluation): add DeepEvalEvaluator with RAG metrics and CSV report"
```

---

### Task 4: CLI 脚本 scripts/evaluate_deepeval.py

**Files:**
- Create: `scripts/evaluate_deepeval.py`
- Test: `tests/test_deepeval_evaluator.py` 追加 `test_parse_cli_args`

**Interfaces:**
- Consumes: Task 3 的 `DeepEvalEvaluator`、`DEFAULT_METRICS`、`DeepEvalEvaluatorError`。
- Produces: CLI 入口 `python scripts/evaluate_deepeval.py`,参数:
  - `--jsonl PATH`(与 `--pdf` 二选一)
  - `--pdf PATH`(可多次,如 `--pdf a.pdf --pdf b.pdf`)
  - `--top-k INT`(默认 5)
  - `--num-questions-per-pdf INT`(默认 5)
  - `--language {en,zh}`(默认 en)
  - `--provider {gemini,openrouter,local_llm}`(默认 None → runtime)
  - `--model TEXT` / `--base-url TEXT` / `--api-key TEXT`
  - `--metrics comma,separated`(默认 `faithfulness,answer_relevancy,context_precision,context_recall`;合法值见 `_METRIC_NAMES`)
  - `--batch-size INT`(默认 5)
  - `--output PATH`(默认自动 `evaluation/deepeval_results_<ts>.csv`)

- [ ] **Step 1: 写失败的测试**

`tests/test_deepeval_evaluator.py` 追加:

```python
def test_parse_cli_args(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate_deepeval.py",
            "--jsonl",
            "eval.jsonl",
            "--top-k",
            "3",
            "--provider",
            "openrouter",
            "--metrics",
            "faithfulness,answer_relevancy",
            "--batch-size",
            "2",
        ],
    )
    from scripts.evaluate_deepeval import parse_args

    args = parse_args()
    assert args.jsonl == "eval.jsonl"
    assert args.top_k == 3
    assert args.provider == "openrouter"
    assert args.metrics == ["faithfulness", "answer_relevancy"]
    assert args.batch_size == 2
    assert args.pdf is None
```

> `scripts/` 目录需可导入:确认 `scripts/__init__.py` 存在;若不存在,在 Task 4 Step 1 中创建空文件。

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/Scripts/python -m pytest tests/test_deepeval_evaluator.py::test_parse_cli_args -q`
Expected: FAIL(`ModuleNotFoundError: No module named 'scripts'` 或 `parse_args` 不存在)。

- [ ] **Step 3: 实现 CLI**

`scripts/evaluate_deepeval.py`:

```python
"""Run RAG evaluation with DeepEval metrics, output CSV + report.

Usage:
    python scripts/evaluate_deepeval.py --jsonl eval_baseline.jsonl --top-k 5
    python scripts/evaluate_deepeval.py --pdf media/data_source/lecture.pdf --language zh
    python scripts/evaluate_deepeval.py --jsonl eval.jsonl --provider openrouter \\
        --model deepseek/deepseek-v4-flash --metrics faithfulness,answer_relevancy
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ``call_llm`` writes Django ``QueryLog``; initialise Django so those imports
# succeed without ``manage.py``.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
import django  # noqa: E402

django.setup()

# Windows DLL workaround: deepeval/ragas pull in pyarrow; loading torch AFTER
# pyarrow makes torch's c10.dll fail (WinError 1114). Import torch first.
try:
    import torch  # noqa: F401
except Exception:  # noqa: BLE001 - evaluation still works without torch
    pass

from evaluation.deepeval_evaluator import (  # noqa: E402
    DEFAULT_METRICS,
    DeepEvalEvaluator,
    DeepEvalEvaluatorError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run DeepEval RAG evaluation on a JSONL dataset or PDFs."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--jsonl", default=None, help="Path to JSONL dataset.")
    source.add_argument(
        "--pdf", action="append", default=None, help="PDF path (repeatable)."
    )
    parser.add_argument("--top-k", type=int, default=5, help="Chunks to retrieve.")
    parser.add_argument(
        "--num-questions-per-pdf", type=int, default=5, help="QA pairs per PDF."
    )
    parser.add_argument(
        "--language", choices=["en", "zh"], default="en", help="Question language."
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "openrouter", "local_llm"],
        default=None,
        help="Judge LLM provider (default: runtime settings).",
    )
    parser.add_argument("--model", default=None, help="Judge LLM model.")
    parser.add_argument("--base-url", default=None, help="Judge LLM base URL.")
    parser.add_argument("--api-key", default=None, help="Judge LLM API key.")
    parser.add_argument(
        "--metrics",
        default=",".join(DEFAULT_METRICS),
        help="Comma-separated metrics (faithfulness, answer_relevancy, "
        "context_precision, context_recall, contextual_relevancy).",
    )
    parser.add_argument(
        "--batch-size", type=int, default=5, help="Test cases per evaluation batch."
    )
    parser.add_argument(
        "--output", default=None, help="Output CSV path (default: evaluation/)."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]

    try:
        evaluator = DeepEvalEvaluator(
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            base_url=args.base_url,
        )
        if args.jsonl:
            result = evaluator.evaluate_from_jsonl(
                jsonl_path=args.jsonl,
                top_k=args.top_k,
                metrics=metrics,
                batch_size=args.batch_size,
                output_path=args.output,
            )
        else:
            result = evaluator.evaluate_from_pdfs(
                pdf_paths=list(args.pdf or []),
                num_questions_per_pdf=args.num_questions_per_pdf,
                top_k=args.top_k,
                language=args.language,
                metrics=metrics,
                batch_size=args.batch_size,
                output_path=args.output,
            )
    except DeepEvalEvaluatorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(result["report"])
    print(f"\nDetailed results: {result['csv_path']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/Scripts/python -m pytest tests/test_deepeval_evaluator.py -q`
Expected: PASS(12 个测试)。

- [ ] **Step 5: 验证 CLI 帮助**

Run: `.venv/Scripts/python scripts/evaluate_deepeval.py --help`
Expected: 打印全部参数,退出码 0(证明 Django setup 与导入链正常,即使没有真实 judge 调用)。

- [ ] **Step 6: Commit**

```bash
git add scripts/evaluate_deepeval.py tests/test_deepeval_evaluator.py
git commit -m "feat(evaluation): add deepeval CLI evaluation script"
```

---

### Task 5: 文档更新

**Files:**
- Modify: `evaluation/README.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: 前序任务的公共符号名(仅文档引用)。

- [ ] **Step 1: 更新 evaluation/README.md**

在 `## Files` 表格追加一行,并在 `## Metrics` 后追加一节:

```markdown
| `deepeval_evaluator.py` | DeepEval framework integration for automated RAG evaluation |

## DeepEval Metrics

- **Faithfulness**: Whether the answer is grounded in the retrieved context
- **Answer Relevancy**: How well the answer addresses the question
- **Contextual Precision**: Relevance of retrieved chunks (requires ground truth)
- **Contextual Recall**: Coverage of relevant information (requires ground truth)
- **Contextual Relevancy**: Overall relevance of the retrieved context (optional)

## DeepEval Usage

```bash
# From a JSONL dataset ({"question": "...", "ground_truth": "..."})
python scripts/evaluate_deepeval.py --jsonl eval_baseline.jsonl --top-k 5

# From PDFs (auto-generate questions, Chinese)
python scripts/evaluate_deepeval.py --pdf media/data_source/lecture.pdf --language zh

# Override judge LLM (OpenRouter / Gemini / local llama.cpp)
python scripts/evaluate_deepeval.py --jsonl eval.jsonl \
    --provider openrouter --model deepseek/deepseek-v4-flash
```

Judge resolution priority: CLI args > `DEEPEVAL_PROVIDER`/`DEEPEVAL_MODEL`/
`DEEPEVAL_API_KEY`/`DEEPEVAL_BASE_URL` env vars > runtime LLM settings
(`data/settings.json`). Runs fully locally; no Confident AI account needed.
```

- [ ] **Step 2: 更新 AGENTS.md**

在 `## Commands` 的 Backend 段(`pytest tests/` 之后)追加:

```markdown
# DeepEval RAG evaluation
python scripts/evaluate_deepeval.py --jsonl eval_baseline.jsonl --top-k 5
```

在 `### Key Runtime Files` 列表(`app/services/llm_client.py` 之后)追加一行:

```markdown
- `evaluation/deepeval_evaluator.py` — DeepEval RAG evaluation (local judge via `call_llm`)
```

- [ ] **Step 3: 检查格式**

Run: `.venv/Scripts/python -m pytest tests/test_deepeval_evaluator.py -q`
Expected: PASS(无代码改动,确认文档步骤未破坏任何东西)。

- [ ] **Step 4: Commit**

```bash
git add evaluation/README.md AGENTS.md
git commit -m "docs: document DeepEval RAG evaluation usage"
```

---

### Task 6: 端到端冒烟评估

**Files:**
- 运行产物(不入库):`evaluation/deepeval_results_*.csv`
- Test: 手动运行验证

**Interfaces:**
- Consumes: 全部前序任务;现有数据集 `eval_baseline.jsonl`(25 条);judge LLM 可用性取决于环境(优先 OpenRouter key,其次 runtime 设置)。

- [ ] **Step 1: 小样本冒烟(3 条)**

Run:
```bash
.venv/Scripts/python scripts/evaluate_deepeval.py \
  --jsonl eval_baseline.jsonl --top-k 5 --batch-size 3 \
  --metrics faithfulness,answer_relevancy
```
Expected: 打印 DeepEval EVALUATION REPORT,含 `Faithfulness`/`AnswerRelevancy` 的 avg/threshold/pass;`evaluation/deepeval_results_*.csv` 生成;无 `deepeval login`/上传行为。

若 judge 调用失败(无 key / 本地服务未启动),记录错误并执行 Step 2 的降级验证。

- [ ] **Step 2(降级验证,可选):mock judge 全链路**

若 Step 1 因 judge 不可用失败,用单元测试覆盖全链路作为替代证据(已由 Task 3/4 提供),并在最终汇报中注明"真实 judge 冒烟未执行,原因:...",附上 `.env` 中可用的 key 名称(`OPENROUTER_API_KEY`/`GEMINI_API_KEY`)供用户自行运行。

- [ ] **Step 3: 全量运行(可选,耗时长)**

Run:
```bash
.venv/Scripts/python scripts/evaluate_deepeval.py \
  --jsonl eval_baseline.jsonl --top-k 5 --batch-size 10
```
Expected: 4 个默认指标全部出分。此步为可选;若 judge 成本/时间受限,记录并跳过。

- [ ] **Step 4: 最终质量门**

Run:
```bash
.venv/Scripts/python -m pytest tests/ -q --tb=short
.venv/Scripts/python -m ruff check app/ django_app/ django_backend/ evaluation/deepeval_evaluator.py scripts/evaluate_deepeval.py
.venv/Scripts/python -m black --check app/ django_app/ django_backend/ evaluation/deepeval_evaluator.py scripts/evaluate_deepeval.py
```
Expected: 全部 PASS;ruff/black 无告警(若有历史遗留告警,仅确认新增文件干净)。

- [ ] **Step 5: Commit(若有产物代码调整)**

```bash
git add -A
git commit -m "chore(evaluation): finalize deepeval evaluation integration"
```

---

## Self-Review

**1. Spec coverage(对照用户需求"用 deepeval 进行 RAG 评估"):**
- 依赖安装 → Task 1 ✓
- deepeval 指标评估流程(与 RAGAS 平行的三入口)→ Task 3 ✓
- judge LLM 复用项目现有 provider(gemini/openrouter/local_llm),无需 OpenAI key → Task 2 ✓
- CLI 入口 + 文档 → Task 4、5 ✓
- 端到端验证 + 与现有 RAGAS 结果可比(指标一一对应)→ Task 6 ✓
- 指标映射:faithfulness↔Faithfulness、answer_relevancy↔AnswerRelevancy、context_precision↔ContextualPrecision、context_recall↔ContextualRecall,外加可选 ContextualRelevancy ✓

**2. Placeholder scan:** 计划中唯一标注"按此展开"的 `DeepEvalJudgeLLM` 给出了完整最终代码(含 `_get_base_llm` 机制);`evaluate_from_pdfs` 中的 `_read_pdf_text` 笔误已在实现注意中明确修正指令。无 TBD/TODO。

**3. Type consistency:** `resolve_judge_config` 返回键 `provider/model/api_key/base_url` 在 Task 2 定义、Task 3 `_build_judge` 消费,一致;`evaluate()` 返回 dict 键 `scores/num_questions/detailed/csv_path/report` 在 Task 3 定义、Task 4 CLI 消费(`result["report"]`/`result["csv_path"]`),一致;`DEFAULT_METRICS` 与 `_METRIC_NAMES` 的合法名在 Task 3 定义、Task 4 `--metrics` 帮助文本引用,一致。
