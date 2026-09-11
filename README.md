# Shuruwat

AI regulatory copilot for India's first-time and home-based food entrepreneurs.

Shuruwat answers a narrow set of FSSAI registration and food-labelling questions from a curated regulatory corpus. It retrieves evidence, explains it in plain English, cites the source, and abstains when the corpus is insufficient.

> A trustworthy "I don't have enough evidence" is better than a confident wrong answer.

## Current Status

The repository currently includes:

- Three source PDFs in `data/raw/`
- Reproducible page-level extraction with `pypdf`
- English-only indexing policy for v1
- 108 naive chunks and 160 structure-aware chunks with stable IDs and page traceability
- Local 384-dimensional embeddings for both chunking strategies
- Supabase/Postgres with pgvector schema and seeded corpus
- FastAPI API with local embeddings, Supabase retrieval, and Groq generation
- React/Vite chat UI with citations, source panel, loading states, and cool blue-teal styling
- A 26-question golden set in `data/golden-questions.json`
- Offline retrieval and generation evaluation runners with committed naive and structure-aware baselines
- Deterministic API tests

Both `naive` and `structure_aware` retrieval strategies are implemented. Comparisons keep the embedding model, top-k, generation model, and golden set fixed so only chunking changes.

## Product Scope

### In scope

- FSSAI registration/basic registration requirements
- FSSAI food-labelling requirements
- The supplied Legal Metrology packaged-commodities rules where relevant to label declarations
- Natural-language questions
- Evidence-backed answers and citations
- Explicit abstention and out-of-scope handoff
- Short-term conversation context
- Naive versus structure-aware chunking evaluation

### Out of scope for v1

- Live web search
- Hybrid/BM25 retrieval or reranking
- Agents or multi-agent workflows
- Voice, WhatsApp, or long-term memory
- GST, tax, export, or general legal advice
- State-specific advice unless supported by the corpus
- Packaging-material compliance beyond the supported corpus
- Automated regulatory monitoring
- Multiple regulatory authorities beyond the supplied corpus

## Safety and Trust Rules

The generation layer must answer only from retrieved evidence. It must never invent regulations, section numbers, URLs, requirements, or citation metadata.

The application must abstain when evidence is missing, ambiguous, unsupported, or outside the corpus. It must not expose a fake numerical confidence score.

Every answer displays:

> Shuruwat provides information based on its curated FSSAI sources and is not legal advice. Verify requirements with FSSAI or a qualified professional before acting.

Credentials stay server-side. The browser calls the FastAPI endpoint and never connects directly to Groq or Supabase.

## Architecture

```text
Source PDFs
    -> pypdf page extraction
    -> language and structure inspection
    -> naive or structure-aware chunking
    -> local sentence-transformers embeddings
    -> Supabase Postgres + pgvector

User question
    -> local question embedding
    -> Supabase vector retrieval (strategy-scoped)
    -> evidence-only Groq generation
    -> server-side citation resolution
    -> React chat UI
```

The API contract is:

```text
POST /api/questions
```

Request:

```json
{
  "question": "What must a petty food business submit to register?",
  "conversation_id": "optional-id",
  "retrieval_strategy": "naive"
}
```

Response fields:

```text
answer
answer_type: direct | abstain | hand_off
citations
sources
disclaimer
conversation_id
```

`structure_aware` is implemented alongside `naive`, so switching strategies does not require UI changes.

## Repository Layout

```text
.
├── README.md
├── .env.example
├── requirements.txt
├── app/
│   ├── api/                  FastAPI question API
│   └── web/                  React/Vite client
├── data/
│   ├── raw/                  Supplied source PDFs
│   ├── processed/            Extracted pages, chunks, embeddings
│   └── golden-questions.json Evaluation questions
├── database/
│   ├── migrations/           Supabase schema and pgvector function
│   ├── apply_migration.py    Apply SQL using DATABASE_URL
│   └── seed_embeddings.py    Seed documents and embedded chunks
├── docs/
│   └── DATA_STRATEGY.md      Corpus audit and language policy
├── evals/
│   ├── evidence_match.py     Fuzzy retrieval evidence matching
│   ├── generation_scoring.py Answer-type and citation scoring
│   ├── run_retrieval_eval.py Offline Recall@k / Precision@k
│   ├── run_generation_eval.py Generation eval + review template
│   └── results/              Committed baseline reports
├── ingestion/
│   ├── inspect_pdfs.py       Page-level PDF extraction
│   ├── create_naive_chunks.py
│   ├── create_structure_aware_chunks.py
│   └── embed_chunks.py       Local embedding generation
├── retrieval/
│   └── local_vector_search.py
└── tests/
    ├── test_api.py
    ├── test_evidence_match.py
    ├── test_generation_scoring.py
    └── test_structure_aware_chunks.py
```

## Prerequisites

- Python 3.10+ recommended. The current implementation was also verified in the existing Python 3.9 virtual environment.
- Node.js 18+ and npm for the web client
- A Supabase project with the `vector` extension available
- A Groq API key and a model available to that key
- Permission to use and redistribute the supplied source PDFs

## Setup

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Copy the environment template and fill in the values locally:

```bash
cp .env.example .env
```

Never commit `.env`. It is ignored by Git.

Required variables:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-server-side-key
DATABASE_URL=your-supabase-pooler-connection-string
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
GROQ_API_KEY=your-groq-key
GROQ_MODEL=your-available-groq-model
```

Use a URL-encoded database password. Prefer Supabase's pooler connection string when the direct database host is unreachable over IPv6.

## Rebuild the Corpus

The current processed artifacts are committed for immediate handoff. To regenerate them:

```bash
.venv/bin/python ingestion/inspect_pdfs.py
.venv/bin/python ingestion/create_naive_chunks.py
.venv/bin/python ingestion/embed_chunks.py \
  --input data/processed/naive_chunks.jsonl \
  --output data/processed/naive_chunks_embeddings.jsonl
.venv/bin/python ingestion/create_structure_aware_chunks.py
.venv/bin/python ingestion/embed_chunks.py \
  --input data/processed/structure_aware_chunks.jsonl \
  --output data/processed/structure_aware_chunks_embeddings.jsonl
```

The extraction pipeline preserves page-level text and records language signals. v1 indexes validated English pages only; pages containing unvalidated Devanagari content are marked `review_required` and are not automatically chunked.

Expected current artifacts:

- 3 documents
- 145 extracted pages
- 108 naive chunks / 108 embeddings
- 160 structure-aware chunks / 160 embeddings
- 384 dimensions per embedding

## Supabase Setup

Apply the schema:

```bash
.venv/bin/python database/apply_migration.py
```

Seed embeddings (naive by default; pass structure-aware input for the alternate corpus):

```bash
.venv/bin/python database/seed_embeddings.py
.venv/bin/python database/seed_embeddings.py \
  --input data/processed/structure_aware_chunks_embeddings.jsonl
```

The migration creates `documents`, `chunks`, `eval_questions`, and `retrieval_runs`, enables pgvector, and defines the `match_chunks()` function. The seed is idempotent.

## Run the API

From the repository root:

```bash
.venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Question smoke test:

```bash
curl -X POST http://127.0.0.1:8000/api/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"What must a petty food business submit to register?","retrieval_strategy":"naive"}'
```

## Run the Web Client

In a second terminal:

```bash
cd app/web
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`. The client sends questions to `http://127.0.0.1:8000` by default. Set `VITE_API_URL` when using another API host.

The UI includes a responsive conversation rail, question composer, live source trail, inline citations, loading state, abstention styling, and the mandatory disclaimer. The current history is local to the browser session and does not require accounts.

## Tests and Validation

Run API and eval unit tests:

```bash
.venv/bin/python -m pytest tests/ -q
```

Run the frontend build:

```bash
cd app/web
npm run build
```

The API tests mock retrieval and generation so they do not consume Groq quota or require a live database. Live smoke tests require valid `.env` credentials.

## Golden Evaluation Set

`data/golden-questions.json` contains 26 questions:

- 8 straightforward
- 6 situation-specific
- 5 ambiguous
- 4 out-of-scope
- 3 unanswerable

Out-of-scope and unanswerable questions have `expected_evidence: null` and are scored on answer type / abstention behavior rather than retrieval metrics.

## Evaluation Results

Retrieval eval keeps the embedding model (`all-MiniLM-L6-v2`), top-k (`5`), and golden set fixed. Only chunking strategy changes. Evidence hits use fuzzy matching against chunk content and section metadata because some golden evidence strings are finer-grained than chunk boundaries.

| Strategy | Chunks | Recall@3 | Recall@5 | Precision@5 |
| --- | ---: | ---: | ---: | ---: |
| naive | 108 | 0.465 | 0.592 | 0.474 |
| structure_aware | 160 | **0.535** | **0.605** | 0.389 |

Recall@5 by category:

| Category | naive | structure_aware |
| --- | ---: | ---: |
| straightforward | 0.688 | **0.750** |
| situation_specific | 0.542 | 0.542 |
| ambiguous | 0.500 | 0.450 |

Structure-aware chunking improves overall recall, especially on straightforward questions, while precision drops because section-sized chunks can pull in broader neighboring text. Ambiguous cross-authority questions remain hard for both strategies. That tradeoff is the main controlled RAG finding in this repo.

Committed reports:

- [`evals/results/naive_baseline.md`](evals/results/naive_baseline.md)
- [`evals/results/structure_aware_baseline.md`](evals/results/structure_aware_baseline.md)

Re-run retrieval eval:

```bash
.venv/bin/python evals/run_retrieval_eval.py \
  --chunks data/processed/naive_chunks_embeddings.jsonl \
  --strategy naive \
  --output evals/results/naive_baseline.json

.venv/bin/python evals/run_retrieval_eval.py \
  --chunks data/processed/structure_aware_chunks_embeddings.jsonl \
  --strategy structure_aware \
  --output evals/results/structure_aware_baseline.json
```

Generation eval scores answer-type accuracy and citation validity, and writes a manual review template for faithfulness, completeness, and abstention quality:

```bash
# Offline template + retrieval context (no Groq calls)
.venv/bin/python evals/run_generation_eval.py --dry-run

# Live Groq scoring
.venv/bin/python evals/run_generation_eval.py
```

Dry-run artifacts are in [`evals/results/naive_generation.md`](evals/results/naive_generation.md) and [`evals/results/manual_review_template.md`](evals/results/manual_review_template.md).

## Data and Provenance

See [`docs/DATA_STRATEGY.md`](docs/DATA_STRATEGY.md) for the source inventory, extraction findings, SHA-256 fingerprints, and English-only indexing decision. The supplied PDFs are included because the project owner confirmed permission to publish them in the intended public repository. Their source authority must remain visible in future citation work.

Processed JSON and embeddings are committed intentionally so Cursor can import and inspect the current state immediately. They can be regenerated using the commands above.

## Security Notes

- Never commit `.env`, API keys, service-role keys, database passwords, or generated secret files.
- Rotate any credential that has been pasted into chat, logs, or a public repository.
- Keep Supabase service-role access in the backend only.
- Do not expose raw secrets in error responses or diagnostics.
- Review staged files before every commit and push.

## Continuation in Cursor

After cloning:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
cd app/web && npm install
```

Then configure `.env`, run the Supabase migration and seeder if using a new project, start the API, and start the web client. Begin future work by reading this README, `docs/DATA_STRATEGY.md`, `database/migrations/001_initial.sql`, `data/golden-questions.json`, and `evals/results/`.

Useful next steps: live generation eval with Groq, seeding both chunking strategies into Supabase for side-by-side UI comparison, and hybrid retrieval experiments that stay outside the current v1 scope.
