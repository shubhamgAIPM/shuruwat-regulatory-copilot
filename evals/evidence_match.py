"""Fuzzy evidence matching for naive chunks that lack section metadata.

Golden questions reference section strings such as
``5(2) List of Ingredients`` or ``2.1.1 Registration of Petty Food Business``.
Naive chunks store ``section=null``, but the section text usually appears in
``content``. Matching therefore uses normalized substring checks, clause-token
variants, and descriptive title fragments.
"""

from __future__ import annotations

import re
from typing import Any


CLAUSE_PATTERN = re.compile(
    r"""
    (?P<clause>
        \d+(?:\.\d+)+              # hierarchical: 2.1.1
        (?:\s*\(\d+(?:\)\([a-z0-9]+)*\))?  # optional 2.1.1(1) / 2.1.1(4)(a)
      | \d+(?:\([a-z0-9]+\))+      # flat: 5(2), 5(2)(b), 5(10)(a)
      | SCHEDULE\s*[-–—]?\s*\w+    # SCHEDULE - 3 / Schedule-II
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

WHITESPACE_PATTERN = re.compile(r"\s+")
PUNCT_PATTERN = re.compile(r"[^\w\s().\-]")


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, and soften punctuation noise."""
    cleaned = text.replace("–", "-").replace("—", "-").replace(":", " ")
    cleaned = PUNCT_PATTERN.sub(" ", cleaned)
    return WHITESPACE_PATTERN.sub(" ", cleaned).strip().lower()


def extract_clause_token(expected: str) -> str | None:
    match = CLAUSE_PATTERN.search(expected.strip())
    if not match:
        return None
    return re.sub(r"\s+", "", match.group("clause")).lower()


def extract_title_fragment(expected: str) -> str | None:
    """Return the descriptive title after a leading clause token, if any."""
    stripped = expected.strip()
    match = CLAUSE_PATTERN.match(stripped)
    if not match:
        # No leading clause; use the whole string if it has enough words.
        fragment = normalize(stripped)
        return fragment if len(fragment.split()) >= 2 else None
    remainder = stripped[match.end() :].strip(" :-–—.")
    fragment = normalize(remainder)
    if len(fragment) < 4:
        return None
    return fragment


def clause_variants(clause: str) -> set[str]:
    """Generate formatting variants that appear in extracted PDF text."""
    compact = clause.lower().replace(" ", "")
    variants = {compact, compact.replace("-", "")}

    # "5(2)(b)" -> also try "(2)(b)" and "(2)" when parent section is elsewhere.
    flat = re.fullmatch(r"(\d+)(\([a-z0-9]+\)+)", compact)
    if flat:
        nested = flat.group(2)
        variants.add(nested)
        first_paren = re.match(r"(\([a-z0-9]+\))", nested)
        if first_paren:
            variants.add(first_paren.group(1))

    # "2.1.1(1)" -> "2.1.1 (1)" and "2.1.1"
    hierarchical = re.fullmatch(r"(\d+(?:\.\d+)+)(\(\d+(?:\)\([a-z0-9]+)*\))?", compact)
    if hierarchical:
        base = hierarchical.group(1)
        variants.add(base)
        if hierarchical.group(2):
            variants.add(base + hierarchical.group(2))
            variants.add(f"{base} {hierarchical.group(2)}")
            variants.add(hierarchical.group(2))

    # Schedule variants: schedule-3, schedule 3, schedule - 3
    schedule = re.fullmatch(r"schedule[-–—]?(\w+)", compact, flags=re.IGNORECASE)
    if schedule:
        label = schedule.group(1).lower()
        variants.update(
            {
                f"schedule-{label}",
                f"schedule {label}",
                f"schedule - {label}",
                f"schedule – {label}",
            }
        )

    return {normalize(variant) for variant in variants if variant}


def chunk_matches_evidence(chunk: dict[str, Any], expected: str) -> bool:
    """Return True when a retrieved chunk supports an expected evidence string."""
    haystack = normalize(
        " ".join(
            part
            for part in (
                chunk.get("content") or "",
                chunk.get("section") or "",
                chunk.get("subsection") or "",
                chunk.get("parent_heading") or "",
            )
            if part
        )
    )
    expected_norm = normalize(expected)
    if not expected_norm:
        return False

    if expected_norm in haystack:
        return True

    title = extract_title_fragment(expected)
    if title and title in haystack:
        return True

    clause = extract_clause_token(expected)
    if not clause:
        return False

    for variant in clause_variants(clause):
        if variant and variant in haystack:
            # Prefer title confirmation when available to reduce false positives
            # on short clause tokens like "(2)".
            if title and len(variant) <= 4:
                return title in haystack
            return True
    return False


def matched_evidence_for_chunk(
    chunk: dict[str, Any], expected_evidence: list[str]
) -> list[str]:
    return [item for item in expected_evidence if chunk_matches_evidence(chunk, item)]


def recall_at_k(
    retrieved: list[dict[str, Any]],
    expected_evidence: list[str],
    k: int,
) -> float:
    if not expected_evidence:
        return 0.0
    top = retrieved[:k]
    found = sum(
        1
        for item in expected_evidence
        if any(chunk_matches_evidence(chunk, item) for chunk in top)
    )
    return found / len(expected_evidence)


def precision_at_k(
    retrieved: list[dict[str, Any]],
    expected_evidence: list[str],
    k: int,
) -> float:
    top = retrieved[:k]
    if not top:
        return 0.0
    if not expected_evidence:
        return 0.0
    relevant = sum(1 for chunk in top if matched_evidence_for_chunk(chunk, expected_evidence))
    return relevant / len(top)
