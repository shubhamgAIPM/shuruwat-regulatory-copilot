"""Extract page-level text and basic metadata from the raw PDF corpus."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader


HEADING_PATTERN = re.compile(
    r"(?im)^(?:chapter\s+[\w.-]+|\d+(?:\.\d+)*[.)]?\s+\S.+|[A-Z][A-Z\s,&'-]{5,})$"
)
DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097f]")


def inspect_pdf(pdf_path: Path, processed_root: Path) -> dict[str, Any]:
    reader = PdfReader(str(pdf_path))
    pages: list[dict[str, Any]] = []
    all_text: list[str] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").replace("\x00", "").strip()
        headings = [line.strip() for line in text.splitlines() if HEADING_PATTERN.match(line.strip())]
        pages.append(
            {
                "page": page_number,
                "text": text,
                "character_count": len(text),
                "word_count": len(text.split()),
                "has_text": bool(text),
                "non_ascii_count": sum(ord(character) > 127 for character in text),
                "replacement_character_count": text.count("�"),
                "devanagari_count": len(DEVANAGARI_PATTERN.findall(text)),
                "indexing_language": "en" if not DEVANAGARI_PATTERN.search(text) else "review_required",
                "headings": headings[:20],
            }
        )
        all_text.append(text)

    relative_output = pdf_path.relative_to(Path("data/raw"))
    output_path = processed_root / relative_output.with_suffix(".json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "source_filename": pdf_path.name,
        "indexing_language_policy": "english_validated_only",
        "source_path": str(pdf_path),
        "metadata": {key: value for key, value in reader.metadata.items()} if reader.metadata else {},
        "page_count": len(reader.pages),
        "pages": pages,
        "text": "\n\n".join(all_text),
    }
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    pdf_paths = sorted(args.raw_dir.glob("*.pdf"))
    if not pdf_paths:
        raise SystemExit(f"No PDF files found in {args.raw_dir}")

    summary = []
    for pdf_path in pdf_paths:
        result = inspect_pdf(pdf_path, args.processed_dir)
        pages = result["pages"]
        summary.append(
            {
                "source_filename": result["source_filename"],
                "page_count": result["page_count"],
                "pages_with_text": sum(page["has_text"] for page in pages),
                "empty_pages": [page["page"] for page in pages if not page["has_text"]],
                "character_count": sum(page["character_count"] for page in pages),
            }
        )

    args.processed_dir.mkdir(parents=True, exist_ok=True)
    (args.processed_dir / "inspection_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()