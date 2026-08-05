#!/usr/bin/env python
"""
Retrieval Quality Checker

This script tests retrieval quality for a given query using the hybrid retrieval system.
It displays BM25, Dense, and Hybrid scores side-by-side for analysis.

Usage:
    python tests/check_retrieval_quality.py "your query here"
    python tests/check_retrieval_quality.py "What is machine learning?"
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from retrieval.hybrid_retriever import HybridRetriever, FusionMethod
from retrieval.bm25_index import BM25Index
from retrieval.dense_retriever import DenseRetriever


# Sample lecture note chunks (replace with actual data from your vector store)
SAMPLE_DOCUMENTS = [
    {
        "id": "lecture1_chunk1",
        "text": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
        "source": "lecture1.pdf",
        "metadata": {"page": 1, "heading": "Introduction to ML"}
    },
    {
        "id": "lecture1_chunk2",
        "text": "Deep learning is a subset of machine learning that uses neural networks with multiple layers to progressively extract higher-level features from raw input.",
        "source": "lecture1.pdf",
        "metadata": {"page": 2, "heading": "Deep Learning Basics"}
    },
    {
        "id": "lecture2_chunk1",
        "text": "Neural networks are computing systems inspired by biological neural networks that constitute the brain. They consist of layers of interconnected nodes.",
        "source": "lecture2.pdf",
        "metadata": {"page": 1, "heading": "Neural Network Architecture"}
    },
    {
        "id": "lecture2_chunk2",
        "text": "Supervised learning uses labeled training data where the algorithm learns to map inputs to desired outputs with minimal error.",
        "source": "lecture2.pdf",
        "metadata": {"page": 3, "heading": "Supervised Learning"}
    },
    {
        "id": "lecture3_chunk1",
        "text": "Unsupervised learning algorithms discover hidden patterns or data groupings without the need for human intervention or labeled data.",
        "source": "lecture3.pdf",
        "metadata": {"page": 1, "heading": "Unsupervised Learning"}
    },
    {
        "id": "lecture3_chunk2",
        "text": "Reinforcement learning is a type of machine learning where an agent learns to make decisions by taking actions in an environment to maximize cumulative reward.",
        "source": "lecture3.pdf",
        "metadata": {"page": 2, "heading": "Reinforcement Learning"}
    },
    {
        "id": "lecture4_chunk1",
        "text": "Natural language processing (NLP) is a branch of artificial intelligence that helps computers understand, interpret, and manipulate human language.",
        "source": "lecture4.pdf",
        "metadata": {"page": 1, "heading": "NLP Fundamentals"}
    },
    {
        "id": "lecture4_chunk2",
        "text": "Computer vision is a field of artificial intelligence that trains computers to interpret and understand the visual world from digital images and videos.",
        "source": "lecture4.pdf",
        "metadata": {"page": 3, "heading": "Computer Vision"}
    },
]


def check_retrieval_quality(query: str, top_k: int = 5):
    """
    Check retrieval quality for a given query.
    
    Displays side-by-side comparison of BM25, Dense, and Hybrid retrieval results.
    
    Args:
        query: The search query
        top_k: Number of results to display
    """
    print("=" * 80)
    print(f"RETRIEVAL QUALITY CHECK")
    print("=" * 80)
    print(f"Query: {query}")
    print(f"Top-K: {top_k}")
    print("=" * 80)
    
    # Initialize retrievers
    print("\nInitializing retrievers...")
    bm25_index = BM25Index(SAMPLE_DOCUMENTS)
    dense_retriever = DenseRetriever(SAMPLE_DOCUMENTS)
    hybrid_retriever = HybridRetriever(SAMPLE_DOCUMENTS, fusion_method=FusionMethod.RRF)
    print("[OK] Retrievers initialized\n")
    
    # Get results from each method
    print("Retrieving results...\n")
    
    bm25_results = bm25_index.search(query, top_k=top_k)
    dense_results = dense_retriever.search(query, top_k=top_k)
    hybrid_results = hybrid_retriever.retrieve(query, top_k=top_k)
    
    # Display BM25 results
    print("-" * 80)
    print("BM25 RESULTS (Keyword-based)")
    print("-" * 80)
    for i, (doc_id, score) in enumerate(bm25_results, 1):
        doc = next((d for d in SAMPLE_DOCUMENTS if d["id"] == doc_id), None)
        if doc:
            print(f"{i}. [{doc_id}] Score: {score:.4f}")
            print(f"   Source: {doc['source']} | {doc['metadata'].get('heading', 'N/A')}")
            print(f"   Text: {doc['text'][:100]}...")
            print()
    
    # Display Dense results
    print("-" * 80)
    print("DENSE RESULTS (Vector-based / Semantic)")
    print("-" * 80)
    for i, (doc_id, score) in enumerate(dense_results, 1):
        doc = next((d for d in SAMPLE_DOCUMENTS if d["id"] == doc_id), None)
        if doc:
            print(f"{i}. [{doc_id}] Score: {score:.4f}")
            print(f"   Source: {doc['source']} | {doc['metadata'].get('heading', 'N/A')}")
            print(f"   Text: {doc['text'][:100]}...")
            print()
    
    # Display Hybrid results
    print("-" * 80)
    print("HYBRID RESULTS (RRF Fusion)")
    print("-" * 80)
    for i, result in enumerate(hybrid_results, 1):
        print(f"{i}. [{result['id']}] Score: {result['score']:.4f}")
        print(f"   Source: {result['source']} | {result['metadata'].get('heading', 'N/A')}")
        print(f"   Text: {result['text'][:100]}...")
        print()
    
    # Analysis summary
    print("=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    
    bm25_top = bm25_results[0][0] if bm25_results else "N/A"
    dense_top = dense_results[0][0] if dense_results else "N/A"
    hybrid_top = hybrid_results[0]["id"] if hybrid_results else "N/A"
    
    print(f"BM25 Top Result:     {bm25_top}")
    print(f"Dense Top Result:    {dense_top}")
    print(f"Hybrid Top Result:   {hybrid_top}")
    print()
    
    # Check agreement
    if bm25_top == dense_top:
        print("[OK] BM25 and Dense agree on top result")
    else:
        print("[INFO] BM25 and Dense disagree - Hybrid fusion provides balanced ranking")
    
    # Show unique contributions
    bm25_ids = {doc_id for doc_id, _ in bm25_results}
    dense_ids = {doc_id for doc_id, _ in dense_results}
    
    only_in_bm25 = bm25_ids - dense_ids
    only_in_dense = dense_ids - bm25_ids
    
    if only_in_bm25:
        print(f"\nDocuments only in BM25: {', '.join(only_in_bm25)}")
    if only_in_dense:
        print(f"Documents only in Dense: {', '.join(only_in_dense)}")
    
    print("\n" + "=" * 80)
    
    # Return structured results for programmatic use
    return {
        "query": query,
        "bm25_results": [{"id": doc_id, "score": score} for doc_id, score in bm25_results],
        "dense_results": [{"id": doc_id, "score": score} for doc_id, score in dense_results],
        "hybrid_results": hybrid_results,
        "summary": {
            "bm25_top": bm25_top,
            "dense_top": dense_top,
            "hybrid_top": hybrid_top,
            "bm25_unique": list(only_in_bm25),
            "dense_unique": list(only_in_dense),
        }
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default query if none provided
        query = "What is deep learning?"
        print(f"No query provided. Using default: '{query}'\n")
    else:
        query = " ".join(sys.argv[1:])
    
    results = check_retrieval_quality(query, top_k=5)
    
    # Optionally save results to JSON
    output_path = project_root / "data" / "retrieval_quality_results.json"
    output_path.parent.mkdir(exist_ok=True)
    
    # Convert for JSON serialization
    json_results = results.copy()
    json_results["hybrid_results"] = [
        {k: v for k, v in r.items() if k != "text"} | {"text_preview": r["text"][:100]}
        for r in results["hybrid_results"]
    ]
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {output_path}")
