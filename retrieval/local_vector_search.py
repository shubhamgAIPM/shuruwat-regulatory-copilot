"""Run local cosine-similarity retrieval against embedded chunk JSONL data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def load_chunks(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def retrieve(
    query: str,
    chunks: list[dict[str, Any]],
    model: SentenceTransformer,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    if not query.strip():
        raise ValueError("query must not be empty")
    if top_k < 1:
        raise ValueError("top_k must be positive")
    query_embedding = model.encode([query], normalize_embeddings=True)[0]
    matrix = np.asarray([chunk["embedding"] for chunk in chunks], dtype=np.float32)
    scores = matrix @ query_embedding
    indices = np.argsort(-scores)[:top_k]
    return [
        {
            "chunk_id": chunks[index]["chunk_id"],
            "document_id": chunks[index]["document_id"],
            "content": chunks[index]["content"],
            "section": chunks[index].get("section"),
            "page": chunks[index]["page_start"],
            "retrieval_score": float(scores[index]),
        }
        for index in indices
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--chunks", type=Path, default=Path("data/processed/naive_chunks_embeddings.jsonl"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    chunks = load_chunks(args.chunks)
    model = SentenceTransformer(args.model)
    print(json.dumps(retrieve(args.query, chunks, model, args.top_k), indent=2))


if __name__ == "__main__":
    main()