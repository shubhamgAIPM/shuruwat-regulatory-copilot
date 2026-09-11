"""Unit tests for fuzzy evidence matching used by retrieval eval."""

from evals.evidence_match import (
    chunk_matches_evidence,
    precision_at_k,
    recall_at_k,
)


def test_matches_hierarchical_section_in_content():
    chunk = {
        "content": "2.1.1 Registration of Petty Food Business (1) Every petty Food Business Operator shall...",
        "section": None,
    }
    assert chunk_matches_evidence(chunk, "2.1.1 Registration of Petty Food Business")
    assert chunk_matches_evidence(chunk, "2.1.1(1)")


def test_matches_title_when_parent_clause_missing():
    chunk = {
        "content": "(2) List of Ingredients : Except for single ingredient foods, a list of ingredients shall be declared...",
        "section": None,
    }
    assert chunk_matches_evidence(chunk, "5(2) List of Ingredients")


def test_matches_schedule_variants():
    chunk = {
        "content": "SCHEDULE - 3 Fees for Registration Rs 100",
        "section": None,
    }
    assert chunk_matches_evidence(chunk, "SCHEDULE - 3")


def test_recall_and_precision():
    expected = ["2.1.1 Registration of Petty Food Business", "SCHEDULE - 3"]
    retrieved = [
        {"content": "2.1.1 Registration of Petty Food Business applies here", "section": None},
        {"content": "Unrelated packaging letter height rules", "section": None},
        {"content": "SCHEDULE - 3 fees table", "section": None},
        {"content": "More unrelated text", "section": None},
        {"content": "Still unrelated", "section": None},
    ]
    assert recall_at_k(retrieved, expected, 3) == 1.0
    assert recall_at_k(retrieved[:1], expected, 3) == 0.5
    assert precision_at_k(retrieved, expected, 5) == 0.4
