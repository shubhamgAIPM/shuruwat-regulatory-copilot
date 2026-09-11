"""Unit tests for structure-aware heading detection and chunk metadata."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.create_structure_aware_chunks import detect_heading, make_chunks


def test_detects_hierarchical_and_numbered_headings():
    hierarchical = detect_heading("2.1.1 Registration of Petty Food Business", page=2)
    assert hierarchical is not None
    assert hierarchical.level <= 3
    assert "2.1.1" in hierarchical.title

    numbered = detect_heading(
        "5. Labelling Requirements. -In addition to general requirements",
        page=30,
    )
    assert numbered is not None
    assert numbered.title.startswith("5. Labelling Requirements")

    clause = detect_heading(
        "(2) List of Ingredients : Except for single ingredient foods",
        page=30,
    )
    assert clause is not None
    assert clause.level == 3
    assert "(2)" in clause.title


def test_rejects_form_noise_and_gazette_lines():
    assert detect_heading("MINISTRY OF HEALTH AND FAMILY WELFARE", page=1) is None
    assert detect_heading("1. Name of the Company/Organization: ______", page=10) is None


def test_make_chunks_populates_section_metadata(tmp_path: Path):
    document = {
        "source_filename": "Licensing_Regulations.pdf",
        "pages": [
            {
                "page": 2,
                "indexing_language": "en",
                "text": (
                    "2.1.1 Registration of Petty Food Business\n"
                    "Every petty Food Business Operator shall register themselves "
                    "with the Registering Authority by submitting an application.\n"
                    "(1) The application shall be accompanied by a declaration.\n"
                    "More details about the registration process continue here."
                ),
            }
        ],
    }
    path = tmp_path / "Licensing_Regulations.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    chunks = make_chunks(path, max_words=900, overlap=120)
    assert chunks
    assert chunks[0]["chunking_strategy"] == "structure_aware"
    assert chunks[0]["section"] is not None
    assert "2.1.1" in (chunks[0]["section"] or "")
    assert chunks[0]["source_filename"] == "Licensing_Regulations.pdf"
