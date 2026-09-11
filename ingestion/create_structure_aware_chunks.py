"""Create structure-aware chunks using heading boundaries from extracted pages.

Unlike naive word windows, this splitter:
1. Detects section / subsection headings in English pages
2. Groups body text under the nearest heading
3. Populates section, subsection, and parent_heading metadata
4. Splits oversized sections with overlapping word windows while keeping metadata

Uses the same embedding model and golden set as the naive baseline so retrieval
comparisons stay controlled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


DEFAULT_MAX_WORDS = 1000
DEFAULT_MIN_WORDS = 180
DEFAULT_OVERLAP = 150

CHAPTER_PATTERN = re.compile(r"^CHAPTER\s+[\w.\-IVXLC]+$", re.IGNORECASE)
SCHEDULE_PATTERN = re.compile(
    r"^(?:THE\s+)?(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|"
    r"TENTH|ELEVENTH|[A-Za-z0-9]+)\s+SCHEDULE\b.*$|^SCHEDULE\s*[-–—]?\s*\w+.*$",
    re.IGNORECASE,
)
HIERARCHICAL_PATTERN = re.compile(r"^(\d+(?:\.\d+){1,3})\s+(.+)$")
NUMBERED_TITLE_PATTERN = re.compile(r"^(\d+)\.\s+([A-Za-z].+)$")
CLAUSE_PATTERN = re.compile(r"^\((\d+[a-z]?)\)\s+(.+)$", re.IGNORECASE)
GAZETTE_NOISE_PATTERN = re.compile(
    r"GAZETTE|EXTRAORDINARY|PART\s+III|SEC\.\s*4|MINISTRY OF|Notification$",
    re.IGNORECASE,
)
FORM_NOISE_PATTERN = re.compile(
    r"_{3,}|Name of the Company|Registered Of+ice Address|Address of Premise",
    re.IGNORECASE,
)


@dataclass
class Heading:
    level: int  # 1=chapter/schedule, 2=section, 3=subsection/clause
    title: str
    page: int


@dataclass
class Segment:
    section: str | None
    subsection: str | None
    parent_heading: str | None
    page_start: int
    page_end: int
    lines: list[str]


def stable_id(*parts: str) -> str:
    value = "|".join(parts).encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:24]


def clean_heading_title(raw: str) -> str:
    title = re.split(r"\s*[-–—.]\s*", raw, maxsplit=1)[0].strip()
    title = re.sub(r"\s+", " ", title)
    return title[:160].strip(" :-")


def is_noise_line(line: str) -> bool:
    if len(line) < 3:
        return True
    if GAZETTE_NOISE_PATTERN.search(line) and len(line) < 90:
        return True
    if FORM_NOISE_PATTERN.search(line):
        return True
    if line.endswith((":", ";")) and "_" in line:
        return True
    return False


def detect_heading(line: str, page: int) -> Heading | None:
    text = line.strip()
    if not text or is_noise_line(text) or len(text) > 140:
        return None

    if CHAPTER_PATTERN.match(text):
        return Heading(level=1, title=clean_heading_title(text), page=page)

    if SCHEDULE_PATTERN.match(text):
        title = clean_heading_title(text)
        # Reject mid-sentence schedule references.
        if len(title.split()) > 6 and not title.upper().startswith(("SCHEDULE", "THE")):
            return None
        return Heading(level=1, title=title, page=page)

    hierarchical = HIERARCHICAL_PATTERN.match(text)
    if hierarchical:
        number, rest = hierarchical.group(1), hierarchical.group(2)
        if FORM_NOISE_PATTERN.search(rest):
            return None
        if re.match(r"^[\d.\s]+$", rest):
            return None
        title_body = clean_heading_title(rest)
        if len(title_body.split()) < 2:
            return None
        depth = number.count(".") + 1
        title = f"{number} {title_body}"
        # Deeper paths like 5.1.2 stay as section boundaries; clause text stays in body.
        return Heading(level=2 if depth <= 3 else 3, title=title, page=page)

    numbered = NUMBERED_TITLE_PATTERN.match(text)
    if numbered:
        number, rest = numbered.group(1), numbered.group(2)
        if FORM_NOISE_PATTERN.search(rest):
            return None
        if re.match(r"^[\d.\s]+$", rest):
            return None
        title_body = clean_heading_title(rest)
        if len(title_body.split()) < 2 and not title_body.isupper():
            return None
        # Prefer short regulatory titles over long sentence-like "headings".
        if len(title_body.split()) > 14:
            return None
        return Heading(level=2, title=f"{number}. {title_body}", page=page)

    clause = CLAUSE_PATTERN.match(text)
    if clause:
        number, rest = clause.group(1), clause.group(2)
        title_body = clean_heading_title(rest)
        if len(title_body) < 4 or len(title_body.split()) > 12:
            return None
        return Heading(level=3, title=f"({number}) {title_body}", page=page)

    return None


def windows(words: list[str], size: int, overlap: int) -> Iterator[tuple[int, list[str]]]:
    if size <= overlap:
        raise ValueError("max words must be greater than overlap")
    step = size - overlap
    for start in range(0, len(words), step):
        chunk = words[start : start + size]
        if chunk:
            yield start, chunk


def flush_segment(segment: Segment | None) -> Segment | None:
    if segment is None:
        return None
    content = "\n".join(line for line in segment.lines if line.strip()).strip()
    if not content:
        return None
    segment.lines = [content]
    return segment


def build_segments(
    document: dict[str, Any],
    min_words: int = DEFAULT_MIN_WORDS,
    max_words: int = DEFAULT_MAX_WORDS,
) -> list[Segment]:
    segments: list[Segment] = []
    current: Segment | None = None
    section: str | None = None
    subsection: str | None = None
    parent_heading: str | None = None

    def start_segment(page: int) -> Segment:
        return Segment(
            section=section,
            subsection=subsection,
            parent_heading=parent_heading,
            page_start=page,
            page_end=page,
            lines=[],
        )

    for page in document["pages"]:
        if page["indexing_language"] != "en":
            continue
        page_number = page["page"]
        for raw_line in page.get("text", "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            heading = detect_heading(line, page_number)
            if heading is not None and heading.level <= 2:
                flushed = flush_segment(current)
                if flushed is not None:
                    segments.append(flushed)

                section = heading.title
                subsection = None
                if heading.level == 1:
                    parent_heading = heading.title
                else:
                    parent_heading = parent_heading or heading.title

                current = start_segment(page_number)
                current.lines.append(line)
                continue

            if heading is not None and heading.level == 3:
                subsection = heading.title
                if section is None:
                    section = heading.title
                if current is None:
                    current = start_segment(page_number)
                else:
                    current.subsection = subsection
                    if current.section is None:
                        current.section = section
                current.page_end = page_number
                current.lines.append(line)
                continue

            if is_noise_line(line) and current is None:
                continue
            if current is None:
                current = start_segment(page_number)
            current.page_end = page_number
            current.lines.append(line)

    flushed = flush_segment(current)
    if flushed is not None:
        segments.append(flushed)
    return merge_small_segments(segments, min_words=min_words, max_words=max_words)


def segment_word_count(segment: Segment) -> int:
    return len(segment.lines[0].split()) if segment.lines else 0


def merge_small_segments(
    segments: list[Segment],
    min_words: int,
    max_words: int,
) -> list[Segment]:
    """Merge tiny consecutive segments to avoid over-fragmentation."""
    if not segments:
        return []

    merged: list[Segment] = []
    current = segments[0]
    for nxt in segments[1:]:
        current_words = segment_word_count(current)
        next_words = segment_word_count(nxt)
        same_family = (current.section == nxt.section) or (
            current.parent_heading and current.parent_heading == nxt.parent_heading
        )
        if (
            same_family
            and current_words < min_words
            and current_words + next_words <= max_words
        ):
            current.lines = ["\n".join([current.lines[0], nxt.lines[0]])]
            current.page_end = max(current.page_end, nxt.page_end)
            if not current.subsection and nxt.subsection:
                current.subsection = nxt.subsection
            continue
        merged.append(current)
        current = nxt
    merged.append(current)
    return merged


def segment_to_chunks(
    segment: Segment,
    document_id: str,
    source_filename: str,
    max_words: int,
    overlap: int,
) -> list[dict[str, Any]]:
    content = segment.lines[0]
    words = content.split()
    chunks: list[dict[str, Any]] = []

    def make_chunk(chunk_words: list[str], word_start: int) -> dict[str, Any]:
        body = " ".join(chunk_words).strip()
        chunk_id = stable_id(
            document_id,
            str(segment.page_start),
            str(word_start),
            segment.section or "",
            segment.subsection or "",
            body,
        )
        return {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "source_filename": source_filename,
            "content": body,
            "section": segment.section,
            "subsection": segment.subsection,
            "parent_heading": segment.parent_heading,
            "page_start": segment.page_start,
            "page_end": segment.page_end,
            "chunking_strategy": "structure_aware",
            "language": "en",
            "word_start": word_start,
            "word_end": word_start + len(chunk_words),
        }

    if len(words) <= max_words:
        if words:
            chunks.append(make_chunk(words, 0))
        return chunks

    for start, chunk_words in windows(words, max_words, overlap):
        chunks.append(make_chunk(chunk_words, start))
    return chunks


def make_chunks(
    processed_path: Path,
    max_words: int,
    overlap: int,
    min_words: int = DEFAULT_MIN_WORDS,
) -> list[dict[str, Any]]:
    document = json.loads(processed_path.read_text(encoding="utf-8"))
    document_id = stable_id(document["source_filename"])
    chunks: list[dict[str, Any]] = []
    for segment in build_segments(document, min_words=min_words, max_words=max_words):
        chunks.extend(
            segment_to_chunks(
                segment,
                document_id=document_id,
                source_filename=document["source_filename"],
                max_words=max_words,
                overlap=overlap,
            )
        )
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/structure_aware_chunks.jsonl")
    )
    parser.add_argument("--max-words", type=int, default=DEFAULT_MAX_WORDS)
    parser.add_argument("--min-words", type=int, default=DEFAULT_MIN_WORDS)
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    args = parser.parse_args()

    processed_paths = sorted(
        path for path in args.processed_dir.glob("*.json") if path.name != "inspection_summary.json"
    )
    chunks = [
        chunk
        for processed_path in processed_paths
        for chunk in make_chunks(
            processed_path,
            max_words=args.max_words,
            overlap=args.overlap,
            min_words=args.min_words,
        )
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for chunk in chunks:
            output.write(json.dumps(chunk, ensure_ascii=True) + "\n")

    with_section = sum(1 for chunk in chunks if chunk.get("section"))
    print(
        json.dumps(
            {
                "chunk_count": len(chunks),
                "chunks_with_section": with_section,
                "section_coverage": round(with_section / len(chunks), 3) if chunks else 0.0,
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
