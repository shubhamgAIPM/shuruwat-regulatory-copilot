"""Run generation evaluation against the golden question set.

For each question:
1. Retrieve top-k chunks offline from local embeddings
2. Optionally call Groq with the production evidence-only prompt
3. Score answer_type accuracy and citation validity
4. Emit a manual review template for faithfulness / completeness review

Use ``--dry-run`` to build retrieval context and the review template without
calling Groq.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.generation_scoring import score_generation_example  # noqa: E402
from retrieval.local_vector_search import load_chunks, retrieve  # noqa: E402


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_CHUNKS = Path("data/processed/naive_chunks_embeddings.jsonl")
DEFAULT_GOLDEN = Path("data/golden-questions.json")
DEFAULT_OUTPUT = Path("evals/results/naive_generation.json")
DEFAULT_GROQ_MODEL = "qwen/qwen3-32b"


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_golden(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_prompt(question: str, evidence: list[dict[str, Any]]) -> str:
    evidence_text = "\n\n".join(
        f"[{index + 1}] chunk_id={item['chunk_id']} | section={item.get('section') or 'Not labelled'} | "
        f"page={item['page']}\n{item['content']}"
        for index, item in enumerate(evidence)
    )
    return f"""You are Shuruwat, a narrow regulatory information assistant.
Answer only from the evidence below. Do not use general knowledge to fill gaps.
The corpus covers FSSAI registration/basic registration, FSSAI food labelling, and the supplied Legal Metrology rules.
For GST, tax, export, cosmetics, packaging materials, state-specific advice, or any unsupported question, use answer_type hand_off or abstain.
If the evidence is insufficient or ambiguous, use answer_type abstain.
Use plain English for a first-time Indian food entrepreneur.
Every material claim must cite one or more evidence numbers such as [1]. Never invent section numbers, pages, URLs, or source metadata.
Return JSON only with keys: answer, answer_type, citation_numbers.
answer_type must be direct, abstain, or hand_off.

QUESTION:
{question}

EVIDENCE:
{evidence_text}
"""


def generate_with_groq(question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    from groq import Groq

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    if not evidence:
        return {
            "answer": "I do not have enough evidence in the curated sources to answer that.",
            "answer_type": "abstain",
            "citations": [],
        }

    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": build_prompt(question, evidence)},
        ],
    )
    content = completion.choices[0].message.content or "{}"
    result = json.loads(content)
    citation_numbers = result.get("citation_numbers", [])
    valid_numbers = {
        number
        for number in citation_numbers
        if isinstance(number, int) and 1 <= number <= len(evidence)
    }
    citations = [evidence[number - 1]["chunk_id"] for number in sorted(valid_numbers)]
    return {
        "answer": str(result.get("answer", "I do not have enough evidence to answer that.")),
        "answer_type": result.get("answer_type", "abstain"),
        "citations": citations,
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(per_question: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [
        item
        for item in per_question
        if item.get("generation") and not item["generation"].get("dry_run")
    ]
    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in scored:
        by_category.setdefault(item["category"], []).append(item)

    def category_stats(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "count": len(items),
            "answer_type_accuracy": mean(
                [1.0 if item["scores"]["answer_type"]["correct"] else 0.0 for item in items]
            ),
            "automatic_pass_rate": mean(
                [1.0 if item["scores"]["passed_automatic_checks"] else 0.0 for item in items]
            ),
            "citation_validity_rate": mean(
                [1.0 if item["scores"]["citations"]["all_citations_valid"] else 0.0 for item in items]
            ),
        }

    empty = {
        "count": 0,
        "answer_type_accuracy": 0.0,
        "automatic_pass_rate": 0.0,
        "citation_validity_rate": 0.0,
    }
    return {
        "scored_questions": len(scored),
        "overall": category_stats(scored) if scored else empty,
        "by_category": {
            category: category_stats(items) for category, items in sorted(by_category.items())
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    overall = report["summary"]["overall"]
    lines = [
        f"# Generation Eval ({report['chunking_strategy']})",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Mode: `{report['mode']}`",
        f"- Chunks: `{report['chunks_path']}`",
        f"- Golden set: `{report['golden_path']}`",
        f"- Embedding model: `{report['embedding_model']}`",
        "",
        "## Automatic scores",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Scored questions | {overall['count']} |",
        f"| Answer type accuracy | {overall['answer_type_accuracy']:.3f} |",
        f"| Citation validity | {overall['citation_validity_rate']:.3f} |",
        f"| Automatic pass rate | {overall['automatic_pass_rate']:.3f} |",
        "",
        "## By category",
        "",
        "| Category | Count | Answer type | Citations valid | Auto pass |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for category, stats in report["summary"]["by_category"].items():
        lines.append(
            f"| {category} | {stats['count']} | {stats['answer_type_accuracy']:.3f} | "
            f"{stats['citation_validity_rate']:.3f} | {stats['automatic_pass_rate']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Manual review",
            "",
            "Use `evals/results/manual_review_template.md` to score faithfulness,",
            "citation correctness, completeness, and abstention quality.",
            "",
        ]
    )
    return "\n".join(lines)


def render_manual_review_template(per_question: list[dict[str, Any]]) -> str:
    lines = [
        "# Manual Generation Review Template",
        "",
        "Score each answered question on a 0/1 scale:",
        "",
        "- **Faithfulness**: every claim is supported by cited evidence",
        "- **Citation correctness**: cited chunks actually support the claim",
        "- **Completeness**: answer covers the expected regulatory points",
        "- **Abstention quality**: abstain/hand_off used when evidence is missing or out of scope",
        "",
        "| # | Category | Expected type | Actual type | Faithfulness | Citation | Completeness | Abstention | Notes |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for index, item in enumerate(per_question, start=1):
        actual = ""
        generation = item.get("generation") or {}
        if not generation.get("dry_run"):
            actual = generation.get("answer_type") or ""
        lines.append(
            f"| {index} | {item['category']} | {item['expected_answer_type']} | {actual} |  |  |  |  |  |"
        )
    lines.extend(
        [
            "",
            "## Reviewer notes",
            "",
            "- Prefer abstention over unsupported certainty.",
            "- Mark citation correctness 0 if the answer cites a chunk that does not contain the claimed requirement.",
            "- For out_of_scope / unanswerable questions, abstention quality is the primary score.",
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
    dry_run: bool,
) -> dict[str, Any]:
    questions = load_golden(golden_path)
    chunks = load_chunks(chunks_path)
    model = SentenceTransformer(model_name)

    per_question: list[dict[str, Any]] = []
    for question in questions:
        retrieved = retrieve(question["question"], chunks, model, top_k=top_k)
        if dry_run:
            generation: dict[str, Any] = {
                "answer": "",
                "answer_type": None,
                "citations": [],
                "dry_run": True,
            }
            scores = None
        else:
            generation = generate_with_groq(question["question"], retrieved)
            scores = score_generation_example(question, generation, retrieved)

        per_question.append(
            {
                "question": question["question"],
                "category": question.get("category", "unknown"),
                "expected_answer_type": question.get("expected_answer_type"),
                "expected_evidence": question.get("expected_evidence"),
                "retrieved": [
                    {
                        "chunk_id": item["chunk_id"],
                        "page": item["page"],
                        "section": item.get("section"),
                        "retrieval_score": item["retrieval_score"],
                        "excerpt": item["content"][:240],
                    }
                    for item in retrieved
                ],
                "generation": generation,
                "scores": scores,
            }
        )

    if dry_run:
        summary: dict[str, Any] = {
            "scored_questions": 0,
            "overall": {
                "count": 0,
                "answer_type_accuracy": 0.0,
                "automatic_pass_rate": 0.0,
                "citation_validity_rate": 0.0,
            },
            "by_category": {},
            "note": "dry_run mode does not call the LLM; use live mode for automatic scores",
        }
    else:
        summary = summarize(per_question)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry_run" if dry_run else "live_groq",
        "chunking_strategy": strategy,
        "embedding_model": model_name,
        "chunks_path": str(chunks_path),
        "golden_path": str(golden_path),
        "question_count": len(questions),
        "top_k": top_k,
        "summary": summary,
        "questions": per_question,
    }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--strategy", default="naive")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Retrieve evidence and write a review template without calling Groq",
    )
    args = parser.parse_args()

    if not args.dry_run and not os.environ.get("GROQ_API_KEY"):
        raise SystemExit(
            "GROQ_API_KEY is required for live generation eval. "
            "Re-run with --dry-run to build the manual review template only."
        )

    report = run_eval(
        golden_path=args.golden,
        chunks_path=args.chunks,
        model_name=args.model,
        top_k=args.top_k,
        strategy=args.strategy,
        dry_run=args.dry_run,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")

    template_path = args.output.parent / "manual_review_template.md"
    template_path.write_text(render_manual_review_template(report["questions"]), encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(args.output),
                "markdown": str(args.output.with_suffix(".md")),
                "manual_review_template": str(template_path),
                "mode": report["mode"],
                "summary": report["summary"]["overall"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
