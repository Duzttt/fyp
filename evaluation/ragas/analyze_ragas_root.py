import pandas as pd
import sys

files = {
    'v1': r'C:\Users\wongs\Documents\GitHub\AI-Based-Lecture-Note-Question-Answering-System-Using-Retrieval-Augmented-Generation-RAG-\eval_baseline_result_after_retrieaval_v1.csv',
    'v2': r'C:\Users\wongs\Documents\GitHub\AI-Based-Lecture-Note-Question-Answering-System-Using-Retrieval-Augmented-Generation-RAG-\eval_baseline_result_after_retrieaval.csv'
}

metrics = ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']

results = {}
for label, path in files.items():
    df = pd.read_csv(path)
    # Convert to numeric, coerce errors to NaN
    for col in metrics:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    # Compute means (ignoring NaN)
    avg = df[metrics].mean()
    results[label] = avg
    print(f'\n--- {label} averages ---')
    for m in metrics:
        print(f'{m}: {avg[m]:.4f}')

# Compare
print('\n--- Differences (v2 - v1) ---')
for m in metrics:
    diff = results['v2'][m] - results['v1'][m]
    print(f'{m}: {diff:+.4f}')

# Check which version better overall
overall = {k: v.mean() for k, v in results.items()}
print('\nOverall average:')
for k, v in overall.items():
    print(f'{k}: {v:.4f}')
better = 'v2' if overall['v2'] > overall['v1'] else 'v1'
print(f'Better overall: {better}')

# Check per metric
print('\nBetter per metric:')
for m in metrics:
    if results['v2'][m] > results['v1'][m]:
        print(f'{m}: v2 better')
    elif results['v2'][m] < results['v1'][m]:
        print(f'{m}: v1 better')
    else:
        print(f'{m}: tie')

# Count rows
for label, path in files.items():
    df = pd.read_csv(path)
    print(f'\n{label}: {len(df)} rows')