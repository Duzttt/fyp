import csv

configs = {
    "Baseline (500/100, BM25+dense)": "eval_baseline_result.csv",
    "Smart Chunker v2": "eval_baseline_result_after_smartchunker_v2.csv",
    "Enhanced Retrieval v1": "eval_baseline_result_after_retrieaval_v1.csv",
}

all_data = {}
for label, fname in configs.items():
    faiths = []
    relevs = []
    precs = []
    recs = []
    questions = []
    with open(fname, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_q = row["user_input"]
            fv = None
            rv = None
            pv = None
            rc = None
            try:
                fv = float(row["faithfulness"])
            except Exception:
                pass
            try:
                rv = float(row["answer_relevancy"])
            except Exception:
                pass
            try:
                pv = float(row["context_precision"])
            except Exception:
                pass
            try:
                rc = float(row["context_recall"])
            except Exception:
                pass
            faiths.append(fv)
            relevs.append(rv)
            precs.append(pv)
            recs.append(rc)
            questions.append({
                "q": user_q[:80],
                "faithfulness": fv,
                "answer_relevancy": rv,
                "context_precision": pv,
                "context_recall": rc,
            })

    def avg(lst):
        vals = [x for x in lst if x is not None]
        return sum(vals) / len(vals) if vals else 0

    all_data[label] = {
        "count": len(faiths),
        "faith_avg": avg(faiths),
        "relev_avg": avg(relevs),
        "prec_avg": avg(precs),
        "recall_avg": avg(recs),
        "questions": questions,
    }

print("=== AVERAGE METRICS ===")
for label, d in all_data.items():
    cnt = d["count"]
    fa = d["faith_avg"]
    ra = d["relev_avg"]
    pa = d["prec_avg"]
    ca = d["recall_avg"]
    overall = (fa + ra + pa + ca) / 4
    print(f"{label} ({cnt} questions):")
    print(f"  Faithfulness:      {fa:.4f}")
    print(f"  Answer Relevancy:  {ra:.4f}")
    print(f"  Context Precision: {pa:.4f}")
    print(f"  Context Recall:    {ca:.4f}")
    print(f"  Overall Average:   {overall:.4f}")
    print()

print("=== WORST SCORING QUESTIONS ===")
for label, d in all_data.items():
    qs = d["questions"]
    def min_score(q):
        vals = [q["faithfulness"], q["answer_relevancy"], q["context_precision"], q["context_recall"]]
        valid = [v for v in vals if v is not None]
        return min(valid) if valid else 1.0
    worst = sorted(qs, key=min_score)[:3]
    print()
    print(f"{label} - 3 worst:")
    for w in worst:
        print(f"  Q: {w['q']}")
        fv = w["faithfulness"]
        rv = w["answer_relevancy"]
        pv = w["context_precision"]
        rc = w["context_recall"]
        print(f"    F={fv}, R={rv}, P={pv}, C={rc}")

print()
print("=== PER-QUESTION COMPARISON ===")
labels = list(configs.keys())
baseline_qs = all_data[labels[0]]["questions"]
for i, bq in enumerate(baseline_qs):
    q_text = bq["q"][:60]
    scores = []
    for label in labels:
        qs = all_data[label]["questions"]
        if i < len(qs):
            q = qs[i]
            fv = q["faithfulness"]
            rv = q["answer_relevancy"]
            pv = q["context_precision"]
            rc = q["context_recall"]
            vals = [v for v in [fv, rv, pv, rc] if v is not None]
            avg = sum(vals) / len(vals) if vals else 0
            scores.append(avg)
        else:
            scores.append(0)
    min_s = min(scores)
    max_s = max(scores)
    if max_s - min_s > 0.3:
        print(f"  Q{i+1}: {q_text}")
        for j, label in enumerate(labels):
            print(f"    {label[:15]}: {scores[j]:.3f}")
