"""Run offline retrieval evaluation against the golden question set.

Computes Recall@3, Recall@5, and Precision@5 using fuzzy evidence matching
against local embedded chunks. Questions with null expected_evidence are
excluded from retrieval metrics and reported separately.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.evidence_match import (  # noqa: E402
    chunk_matches_evidence,
    matched_evidence_for_chunk,
    precision_at_k,
    recall_at_k,
)
from retrieval.local_vector_search import load_chunks, retrieve  # noqa: E402


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_CHUNKS = Path("data/processed/naive_chunks_embeddings.jsonl")
DEFAULT_GOLDEN = Path("data/golden-questions.json")
DEFAULT_OUTPUT = Path("evals/results/naive_baseline.json")


def load_golden(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def evaluate_question(
    question: dict[str, Any],
    retrieved: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = question.get("expected_evidence")
    category = question.get("category", "unknown")
    result: dict[str, Any] = {
        "question": question["question"],
        "category": category,
        "expected_answer_type": question.get("expected_answer_type"),
        "expected_evidence": expected,
        "retrieved": [
            {
                "chunk_id": item["chunk_id"],
                "page": item["page"],
                "section": item.get("section"),
                "retrieval_score": item["retrieval_score"],
                "matched_evidence": matched_evidence_for_chunk(item, expected or []),
                "excerpt": item["content"][:240],
            }
            for item in retrieved
        ],
    }

    if expected is None:
        result["included_in_retrieval_metrics"] = False
        result["skip_reason"] = "expected_evidence is null"
        result["metrics"] = None
        return result

    metrics = {
        "recall_at_3": recall_at_k(retrieved, expected, 3),
        "recall_at_5": recall_at_k(retrieved, expected, 5),
        "precision_at_5": precision_at_k(retrieved, expected, 5),
        "evidence_hits": {
            item: any(chunk_matches_evidence(chunk, item) for chunk in retrieved[:5])
            for item in expected
        },
    }
    result["included_in_retrieval_metrics"] = True
    result["metrics"] = metrics
    return result


def summarize(per_question: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [item for item in per_question if item.get("included_in_retrieval_metrics")]
    skipped = [item for item in per_question if not item.get("included_in_retrieval_metrics")]

    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in scored:
        by_category.setdefault(item["category"], []).append(item)

    def category_summary(items: list[dict[str, Any]]) -> dict[str, float]:
        return {
            "count": len(items),
            "recall_at_3": mean([q["metrics"]["recall_at_3"] for q in items]),
            "recall_at_5": mean([q["metrics"]["recall_at_5"] for q in items]),
            "precision_at_5": mean([q["metrics"]["precision_at_5"] for q in items]),
        }

    return {
        "scored_questions": len(scored),
        "skipped_questions": len(skipped),
        "overall": category_summary(scored) if scored else {
            "count": 0,
            "recall_at_3": 0.0,
            "recall_at_5": 0.0,
            "precision_at_5": 0.0,
        },
        "by_category": {
            category: category_summary(items) for category, items in sorted(by_category.items())
        },
        "skipped_categories": sorted({item["category"] for item in skipped}),
    }


def render_markdown(report: dict[str, Any]) -> str:
    overall = report["summary"]["overall"]
    lines = [
        "# Naive Retrieval Baseline",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Chunking strategy: `{report['chunking_strategy']}`",
        f"- Embedding model: `{report['embedding_model']}`",
        f"- Chunks file: `{report['chunks_path']}`",
        f"- Golden set: `{report['golden_path']}` ({report['question_count']} questions)",
        f"- Top-k: `{report['top_k']}`",
        f"- Matching: fuzzy content match (naive chunks have `section=null`)",
        "",
        "## Overall (questions with expected evidence)",
        "",
        f"| Metric | Value |",
        f"| --- | ---: |",
        f"| Scored questions | {overall['count']} |",
        f"| Recall@3 | {overall['recall_at_3']:.3f} |",
        f"| Recall@5 | {overall['recall_at_5']:.3f} |",
        f"| Precision@5 | {overall['precision_at_5']:.3f} |",
        f"| Skipped (null evidence) | {report['summary']['skipped_questions']} |",
        "",
        "## By category",
        "",
        "| Category | Count | Recall@3 | Recall@5 | Precision@5 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for category, stats in report["summary"]["by_category"].items():
        lines.append(
            f"| {category} | {stats['count']} | {stats['recall_at_3']:.3f} | "
            f"{stats['recall_at_5']:.3f} | {stats['precision_at_5']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Out-of-scope and unanswerable questions are excluded from retrieval metrics.",
            "- Structure-aware chunking should re-run this script with the same golden set.",
            "",
        ]
    )
    return "\n".join(lines)


def run_eval(
    golden_path: Path,
    chunks_path: Path,
    model_name: str,
    top_k: int,
    strategy: str,
) -> dict[str, Any]:
    questions = load_golden(golden_path)
    chunks = load_chunks(chunks_path)
    model = SentenceTransformer(model_name)

    per_question: list[dict[str, Any]] = []
    for question in questions:
        retrieved = retrieve(question["question"], chunks, model, top_k=top_k)
        per_question.append(evaluate_question(question, retrieved))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chunking_strategy": strategy,
        "embedding_model": model_name,
        "chunks_path": str(chunks_path),
        "golden_path": str(golden_path),
        "question_count": len(questions),
        "top_k": top_k,
        "matching_method": "fuzzy_content",
        "summary": summarize(per_question),
        "questions": per_question,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--strategy", default="naive")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = run_eval(
        golden_path=args.golden,
        chunks_path=args.chunks,
        model_name=args.model,
        top_k=args.top_k,
        strategy=args.strategy,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")

    overall = report["summary"]["overall"]
    print(
        json.dumps(
            {
                "output": str(args.output),
                "markdown": str(markdown_path),
                "scored_questions": overall["count"],
                "recall_at_3": round(overall["recall_at_3"], 4),
                "recall_at_5": round(overall["recall_at_5"], 4),
                "precision_at_5": round(overall["precision_at_5"], 4),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
