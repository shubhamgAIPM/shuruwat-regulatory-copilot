"""Scoring helpers for generation evaluation."""

from __future__ import annotations

import re
from typing import Any

from evals.evidence_match import chunk_matches_evidence


CITATION_PATTERN = re.compile(r"\[(\d+)\]")

ANSWER_TYPE_ALIASES = {
    "direct": "direct",
    "answer": "direct",
    "abstain": "abstain",
    "abstention": "abstain",
    "hand_off": "hand_off",
    "handoff": "hand_off",
    "hand-off": "hand_off",
}


def normalize_answer_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return ANSWER_TYPE_ALIASES.get(value.strip().lower())


def score_answer_type(expected: str, actual: Any) -> dict[str, Any]:
    expected_normalized = normalize_answer_type(expected) or expected
    actual_normalized = normalize_answer_type(actual)
    return {
        "expected": expected_normalized,
        "actual": actual_normalized,
        "correct": actual_normalized == expected_normalized,
    }


def extract_inline_citation_numbers(answer: str) -> list[int]:
    return sorted({int(match) for match in CITATION_PATTERN.findall(answer or "")})


def score_citations(
    answer: str,
    citations: list[str],
    retrieved: list[dict[str, Any]],
    expected_evidence: list[str] | None,
) -> dict[str, Any]:
    retrieved_by_id = {item["chunk_id"]: item for item in retrieved}
    valid_citations = [chunk_id for chunk_id in citations if chunk_id in retrieved_by_id]
    invalid_citations = [chunk_id for chunk_id in citations if chunk_id not in retrieved_by_id]
    inline_numbers = extract_inline_citation_numbers(answer)
    invalid_inline = [number for number in inline_numbers if number < 1 or number > len(retrieved)]

    grounded_citations: list[str] = []
    ungrounded_citations: list[str] = []
    if expected_evidence:
        for chunk_id in valid_citations:
            chunk = retrieved_by_id[chunk_id]
            if any(chunk_matches_evidence(chunk, item) for item in expected_evidence):
                grounded_citations.append(chunk_id)
            else:
                ungrounded_citations.append(chunk_id)

    return {
        "citation_count": len(citations),
        "valid_citation_count": len(valid_citations),
        "invalid_citations": invalid_citations,
        "inline_citation_numbers": inline_numbers,
        "invalid_inline_citation_numbers": invalid_inline,
        "all_citations_valid": not invalid_citations and not invalid_inline,
        "grounded_citation_count": len(grounded_citations),
        "ungrounded_citations": ungrounded_citations,
        "has_citation_when_direct": len(valid_citations) > 0,
    }


def score_generation_example(
    question: dict[str, Any],
    generation: dict[str, Any],
    retrieved: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_type = question.get("expected_answer_type", "abstain")
    answer_type_score = score_answer_type(expected_type, generation.get("answer_type"))
    citation_score = score_citations(
        answer=str(generation.get("answer", "")),
        citations=list(generation.get("citations") or []),
        retrieved=retrieved,
        expected_evidence=question.get("expected_evidence"),
    )

    needs_citations = expected_type == "direct" and answer_type_score["actual"] == "direct"
    if needs_citations:
        citation_ok = citation_score["has_citation_when_direct"] and citation_score["all_citations_valid"]
    else:
        citation_ok = citation_score["all_citations_valid"]

    return {
        "answer_type": answer_type_score,
        "citations": citation_score,
        "passed_automatic_checks": answer_type_score["correct"] and citation_ok,
    }
