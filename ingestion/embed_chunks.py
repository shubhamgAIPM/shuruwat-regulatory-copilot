"""Generate normalized local embeddings for chunk JSONL data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/naive_chunks.jsonl"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/naive_chunks_embeddings.jsonl")
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    chunks = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not chunks:
        raise SystemExit(f"No chunks found in {args.input}")

    model = SentenceTransformer(args.model)
    embeddings = model.encode(
        [chunk["content"] for chunk in chunks],
        batch_size=args.batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    dimension = int(embeddings.shape[1])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for chunk, embedding in zip(chunks, embeddings):
            output.write(
                json.dumps(
                    {
                        **chunk,
                        "embedding": embedding.tolist(),
                        "embedding_model": args.model,
                        "embedding_dimensions": dimension,
                    },
                    ensure_ascii=True,
                )
                + "\n"
            )
    print(f"Wrote {len(chunks)} embeddings ({dimension} dimensions) to {args.output}")


if __name__ == "__main__":
    main()