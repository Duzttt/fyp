from argparse import ArgumentParser
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_INDEX_PATH = Path("data/faiss_index/index.faiss")
DEFAULT_CHUNKS_PATH = Path("data/faiss_index/chunks.npy")
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# Based on the real lecture PDF content (history of computing trends).
DEFAULT_QUERY = (
    "What are the LEARNING OUTCOMES of the course? "
    "mentioned in this document?"
)


def parse_args():
    parser = ArgumentParser(
        description=(
            "Load local FAISS index + chunks, embed a fixed query, "
            "run top-k search, and print matched text chunks."
        )
    )
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--model-name", type=str, default=DEFAULT_MODEL_NAME)
    parser.add_argument("--query", type=str, default=DEFAULT_QUERY)
    parser.add_argument("--top-k", type=int, default=3)
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.index_path.exists():
        raise FileNotFoundError(f"index.faiss not found: {args.index_path}")
    if not args.chunks_path.exists():
        raise FileNotFoundError(f"chunks.npy not found: {args.chunks_path}")

    print("Loading FAISS index and chunks...")
    index = faiss.read_index(str(args.index_path))
    chunks = np.load(str(args.chunks_path), allow_pickle=True).tolist()

    print(f"Index path: {args.index_path}")
    print(f"Chunks path: {args.chunks_path}")
    print(f"Index vectors (ntotal): {index.ntotal}")
    print(f"Index dimension (d): {index.d}")
    print(f"Chunk count: {len(chunks)}")
    print("-" * 80)

    print(f"Loading embedding model: {args.model_name}")
    model = SentenceTransformer(args.model_name)

    print(f"Query: {args.query}")
    query_vector = model.encode([args.query], show_progress_bar=False)
    query_vector = np.asarray(query_vector, dtype="float32")

    if query_vector.shape[1] != index.d:
        raise ValueError(
            "Embedding dimension mismatch: "
            f"query vector dim={query_vector.shape[1]}, index dim={index.d}. "
            "Please use the same embedding model that was used to build this index."
        )

    top_k = max(1, min(args.top_k, index.ntotal))
    distances, indices = index.search(query_vector, top_k)

    print("\nTop-K search result")
    print("-" * 80)
    for rank, (chunk_idx, distance) in enumerate(
        zip(indices[0], distances[0]),
        start=1,
    ):
        if chunk_idx < 0 or chunk_idx >= len(chunks):
            print(f"[Rank {rank}] Invalid chunk index: {chunk_idx}, distance={distance}")
            continue

        print(f"[Rank {rank}] chunk_index={chunk_idx}, distance={float(distance):.6f}")
        print("Chunk text:")
        chunk_obj = chunks[chunk_idx]
        if isinstance(chunk_obj, dict):
            print(f"source={chunk_obj.get('source', 'unknown')}")
            print(f"page={chunk_obj.get('page', 'unknown')}")
            print(chunk_obj.get("text", ""))
        else:
            print(chunk_obj)
        print("-" * 80)


if __name__ == "__main__":
    main()
