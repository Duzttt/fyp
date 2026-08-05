import pandas as pd

files = {
    'v1': r'C:\Users\wongs\Documents\GitHub\AI-Based-Lecture-Note-Question-Answering-System-Using-Retrieval-Augmented-Generation-RAG-\eval_baseline_result_after_retrieaval_v1.csv',
    'v2': r'C:\Users\wongs\Documents\GitHub\AI-Based-Lecture-Note-Question-Answering-System-Using-Retrieval-Augmented-Generation-RAG-\eval_baseline_result_after_retrieaval.csv'
}

metrics = ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']

# thresholds from skill
thresholds = {
    'faithfulness': (0.80, 0.60),
    'answer_relevancy': (0.85, 0.70),
    'context_precision': (0.70, 0.50),
    'context_recall': (0.80, 0.60)
}

def classify(metric, value):
    good, acceptable = thresholds[metric]
    if value > good:
        return 'Good'
    elif value >= acceptable:
        return 'Acceptable'
    else:
        return 'Poor'

for label, path in files.items():
    df = pd.read_csv(path)
    for col in metrics:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    avg = df[metrics].mean()
    print(f'\n--- {label} classification ---')
    for m in metrics:
        c = classify(m, avg[m])
        print(f'{m}: {avg[m]:.4f} -> {c}')
    # Count rows with empty retrieved_contexts
    empty_contexts = df['retrieved_contexts'].apply(lambda x: str(x).strip() == '[]' or str(x).strip() == '').sum()
    print(f'Rows with empty retrieved_contexts: {empty_contexts}/{len(df)}')

# Identify weak metrics per version
print('\nWeak metrics (Poor or Acceptable) per version:')
for label, path in files.items():
    df = pd.read_csv(path)
    for col in metrics:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    avg = df[metrics].mean()
    weak = []
    for m in metrics:
        c = classify(m, avg[m])
        if c != 'Good':
            weak.append(f'{m} ({c})')
    print(f'{label}: {weak}')