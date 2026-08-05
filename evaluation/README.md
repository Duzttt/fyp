# evaluation/ — RAG Evaluation Module

Tools for evaluating retrieval quality, generation accuracy, and overall RAG performance.

## Structure

```
evaluation/
├── __init__.py                 # Module init
├── retrieval_evaluator.py      # Retrieval-specific metrics (precision, recall, MRR, nDCG)
├── performance_monitor.py      # Runtime performance monitoring (latency, throughput)
├── README.md
├── ragas/                      # RAGAS evaluation
│   ├── __init__.py
│   ├── ragas_evaluator.py      # RAGAS framework integration
│   ├── analyze_ragas.py        # Compare RAGAS CSV results
│   ├── analyze_ragas_root.py   # Root-level analysis script
│   ├── classify_metrics.py     # Classify metric scores (Good/Acceptable/Poor)
│   ├── ragas_analysis_report.md
│   ├── ragas.txt
│   └── results/                # RAGAS evaluation result CSVs
├── deepeval/                   # DeepEval evaluation (placeholder)
│   └── __init__.py
├── results/                    # General evaluation results
│   ├── retrieval_quality_results.json
│   ├── eval_baseline.jsonl
│   └── eval.jsonl
└── logs/                       # Evaluation logs
    ├── eval_stdout.log
    └── eval_stderr.log
```

## Metrics

- **Faithfulness**: How grounded the answer is in retrieved context
- **Answer Relevancy**: How well the answer addresses the question
- **Context Precision**: Relevance of retrieved chunks
- **Context Recall**: Coverage of relevant information

## Usage

```python
from evaluation.ragas.ragas_evaluator import RAGASEvaluator
evaluator = RAGASEvaluator()
results = evaluator.evaluate(test_cases)
```
