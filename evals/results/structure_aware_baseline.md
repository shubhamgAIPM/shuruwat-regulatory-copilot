# Structure Aware Retrieval Baseline

- Generated: `2026-09-11T20:20:27.815523+00:00`
- Chunking strategy: `structure_aware`
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Chunks file: `data/processed/structure_aware_chunks_embeddings.jsonl`
- Golden set: `data/golden-questions.json` (26 questions)
- Top-k: `5`
- Matching: `fuzzy_content`

## Overall (questions with expected evidence)

| Metric | Value |
| --- | ---: |
| Scored questions | 19 |
| Recall@3 | 0.535 |
| Recall@5 | 0.605 |
| Precision@5 | 0.389 |
| Skipped (null evidence) | 7 |

## By category

| Category | Count | Recall@3 | Recall@5 | Precision@5 |
| --- | ---: | ---: | ---: | ---: |
| ambiguous | 5 | 0.250 | 0.450 | 0.400 |
| situation_specific | 6 | 0.486 | 0.542 | 0.400 |
| straightforward | 8 | 0.750 | 0.750 | 0.375 |

## Notes

- Out-of-scope and unanswerable questions are excluded from retrieval metrics.
- Compare naive and structure_aware results with the same golden set and embedding model.
- Fuzzy content matching is used because some expected evidence strings are finer-grained than chunk boundaries.
