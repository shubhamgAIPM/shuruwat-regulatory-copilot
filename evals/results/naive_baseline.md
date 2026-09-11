# Naive Retrieval Baseline

- Generated: `2026-09-11T19:51:03.680989+00:00`
- Chunking strategy: `naive`
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Chunks file: `data/processed/naive_chunks_embeddings.jsonl`
- Golden set: `data/golden-questions.json` (26 questions)
- Top-k: `5`
- Matching: fuzzy content match (naive chunks have `section=null`)

## Overall (questions with expected evidence)

| Metric | Value |
| --- | ---: |
| Scored questions | 19 |
| Recall@3 | 0.465 |
| Recall@5 | 0.592 |
| Precision@5 | 0.474 |
| Skipped (null evidence) | 7 |

## By category

| Category | Count | Recall@3 | Recall@5 | Precision@5 |
| --- | ---: | ---: | ---: | ---: |
| ambiguous | 5 | 0.350 | 0.500 | 0.400 |
| situation_specific | 6 | 0.431 | 0.542 | 0.500 |
| straightforward | 8 | 0.562 | 0.688 | 0.500 |

## Notes

- Out-of-scope and unanswerable questions are excluded from retrieval metrics.
- Compare with `structure_aware_baseline.md` using the same golden set and embedding model.
