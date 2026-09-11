"""Seed validated documents and embedded chunks into Supabase."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import psycopg


DOCUMENTS: dict[str, dict[str, str]] = {
    "Licensing_Regulations.pdf": {
        "title": "Food Safety and Standards (Licensing and Registration of Food Businesses) Regulations, 2011",
        "authority": "Food Safety and Standards Authority of India",
        "document_type": "regulation",
    },
    "Labeling rules 1.pdf": {
        "title": "FSSAI Labelling Regulations",
        "authority": "Food Safety and Standards Authority of India",
        "document_type": "regulation",
    },
    "9 The Legal Metrology (Package Commodities) Rules, 2011.pdf": {
        "title": "The Legal Metrology (Packaged Commodities) Rules, 2011",
        "authority": "Department of Consumer Affairs",
        "document_type": "rule",
    },
}


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def source_hash(filename: str) -> str:
    return hashlib.sha256((Path("data/raw") / filename).read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path("data/processed/naive_chunks_embeddings.jsonl")
    )
    parser.add_argument(
        "--strategy",
        choices=("naive", "structure_aware"),
        default=None,
        help="Expected chunking_strategy; defaults to the strategy found in the input file",
    )
    args = parser.parse_args()
    load_dotenv()

    chunks = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not chunks:
        raise SystemExit(f"No embedded chunks found in {args.input}")
    strategies = {chunk["chunking_strategy"] for chunk in chunks}
    if len(strategies) != 1:
        raise SystemExit(f"Input must contain a single chunking_strategy, found: {sorted(strategies)}")
    strategy = args.strategy or next(iter(strategies))
    if strategy not in {"naive", "structure_aware"}:
        raise SystemExit(f"Unsupported chunking_strategy: {strategy}")
    if any(chunk["chunking_strategy"] != strategy or chunk["language"] != "en" for chunk in chunks):
        raise SystemExit(f"Input contains chunks outside the English-only {strategy} seed")

    documents = {chunk["source_filename"] for chunk in chunks}
    unknown = documents - DOCUMENTS.keys()
    if unknown:
        raise SystemExit(f"No document metadata mapping for: {sorted(unknown)}")

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            for filename in sorted(documents):
                document_id = next(chunk["document_id"] for chunk in chunks if chunk["source_filename"] == filename)
                metadata = DOCUMENTS[filename]
                cursor.execute(
                    """
                    insert into documents (
                        document_id, title, authority, document_type, original_filename,
                        language_policy, source_sha256
                    ) values (%s, %s, %s, %s, %s, %s, %s)
                    on conflict (document_id) do update set
                        title = excluded.title,
                        authority = excluded.authority,
                        document_type = excluded.document_type,
                        language_policy = excluded.language_policy,
                        source_sha256 = excluded.source_sha256
                    """,
                    (
                        document_id,
                        metadata["title"],
                        metadata["authority"],
                        metadata["document_type"],
                        filename,
                        "english_validated_only",
                        source_hash(filename),
                    ),
                )

            for chunk in chunks:
                cursor.execute(
                    """
                    insert into chunks (
                        chunk_id, document_id, content, section, subsection, parent_heading,
                        page_start, page_end, chunking_strategy, language, embedding_model, embedding
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (chunk_id) do update set
                        content = excluded.content,
                        section = excluded.section,
                        subsection = excluded.subsection,
                        parent_heading = excluded.parent_heading,
                        page_start = excluded.page_start,
                        page_end = excluded.page_end,
                        embedding_model = excluded.embedding_model,
                        embedding = excluded.embedding
                    """,
                    (
                        chunk["chunk_id"],
                        chunk["document_id"],
                        chunk["content"],
                        chunk.get("section"),
                        chunk.get("subsection"),
                        chunk.get("parent_heading"),
                        chunk["page_start"],
                        chunk["page_end"],
                        chunk["chunking_strategy"],
                        chunk["language"],
                        chunk["embedding_model"],
                        vector_literal(chunk["embedding"]),
                    ),
                )
    print(f"Seeded {len(documents)} documents and {len(chunks)} {strategy} chunks")


if __name__ == "__main__":
    main()