"""Unit tests for generation scoring helpers."""

from evals.generation_scoring import (
    extract_inline_citation_numbers,
    score_answer_type,
    score_citations,
    score_generation_example,
)


def test_score_answer_type_accepts_aliases():
    assert score_answer_type("hand_off", "handoff")["correct"] is True
    assert score_answer_type("abstain", "abstention")["correct"] is True
    assert score_answer_type("direct", "abstain")["correct"] is False


def test_extract_inline_citation_numbers():
    assert extract_inline_citation_numbers("Register under [1] and see fee in [3].") == [1, 3]


def test_score_citations_flags_invalid_and_ungrounded():
    retrieved = [
        {
            "chunk_id": "c1",
            "content": "2.1.1 Registration of Petty Food Business requires an application.",
            "section": "2.1.1 Registration of Petty Food Business",
        },
        {
            "chunk_id": "c2",
            "content": "Unrelated packaging letter height rules.",
            "section": None,
        },
    ]
    result = score_citations(
        answer="Submit the form [1]. Ignore [9].",
        citations=["c1", "missing"],
        retrieved=retrieved,
        expected_evidence=["2.1.1 Registration of Petty Food Business"],
    )
    assert result["invalid_citations"] == ["missing"]
    assert result["invalid_inline_citation_numbers"] == [9]
    assert result["grounded_citation_count"] == 1
    assert result["all_citations_valid"] is False


def test_score_generation_example_requires_citations_for_direct_answers():
    question = {
        "expected_answer_type": "direct",
        "expected_evidence": ["2.1.1 Registration of Petty Food Business"],
    }
    retrieved = [
        {
            "chunk_id": "c1",
            "content": "2.1.1 Registration of Petty Food Business requires registration.",
            "section": None,
        }
    ]
    generation = {
        "answer": "You must register [1].",
        "answer_type": "direct",
        "citations": ["c1"],
    }
    scores = score_generation_example(question, generation, retrieved)
    assert scores["passed_automatic_checks"] is True

    generation_missing = {
        "answer": "You must register.",
        "answer_type": "direct",
        "citations": [],
    }
    scores_missing = score_generation_example(question, generation_missing, retrieved)
    assert scores_missing["passed_automatic_checks"] is False
