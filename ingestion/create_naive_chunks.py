"""Create stable, page-traceable naive chunks from eligible extracted text."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator


DEFAULT_CHUNK_SIZE = 1200
DEFAULT_OVERLAP = 200


def stable_id(*parts: str) -> str:
    value = "|".join(parts).encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:24]


def windows(words: list[str], size: int, overlap: int) -> Iterator[tuple[int, list[str]]]:
    if size <= overlap:
        raise ValueError("chunk size must be greater than overlap")
    step = size - overlap
    for start in range(0, len(words), step):
        chunk = words[start : start + size]
        if chunk:
            yield start, chunk


def make_chunks(processed_path: Path, size: int, overlap: int) -> list[dict[str, Any]]:
    document = json.loads(processed_path.read_text(encoding="utf-8"))
    document_id = stable_id(document["source_filename"])
    chunks: list[dict[str, Any]] = []
    for page in document["pages"]:
        if page["indexing_language"] != "en":
            continue
        text = page.get("text", "")
        words = text.split()
        for start, chunk_words in windows(words, size, overlap):
            content = " ".join(chunk_words).strip()
            chunk_id = stable_id(document_id, str(page["page"]), str(start), content)
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "source_filename": document["source_filename"],
                    "content": content,
                    "section": None,
                    "subsection": None,
                    "page_start": page["page"],
                    "page_end": page["page"],
                    "chunking_strategy": "naive",
                    "language": "en",
                    "word_start": start,
                    "word_end": start + len(chunk_words),
                }
            )
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/naive_chunks.jsonl"))
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    args = parser.parse_args()

    processed_paths = sorted(
        path for path in args.processed_dir.glob("*.json") if path.name != "inspection_summary.json"
    )
    chunks = [
        chunk
        for processed_path in processed_paths
        for chunk in make_chunks(processed_path, args.chunk_size, args.overlap)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for chunk in chunks:
            output.write(json.dumps(chunk, ensure_ascii=True) + "\n")
    print(json.dumps({"chunk_count": len(chunks), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()