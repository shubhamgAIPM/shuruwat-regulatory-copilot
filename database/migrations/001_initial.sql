create extension if not exists vector;

create table if not exists documents (
    document_id text primary key,
    title text not null,
    authority text not null,
    document_type text not null,
    regulation_name text,
    publication_date date,
    effective_date date,
    version text,
    status text,
    source_url text,
    original_filename text not null unique,
    language_policy text not null default 'english_validated_only',
    source_sha256 text,
    created_at timestamptz not null default now()
);

create table if not exists chunks (
    chunk_id text primary key,
    document_id text not null references documents(document_id) on delete cascade,
    content text not null,
    section text,
    subsection text,
    parent_heading text,
    page_start integer not null check (page_start > 0),
    page_end integer not null check (page_end >= page_start),
    chunking_strategy text not null check (chunking_strategy in ('naive', 'structure_aware')),
    language text not null,
    embedding_model text not null,
    embedding vector(384) not null,
    created_at timestamptz not null default now()
);

create index if not exists chunks_document_id_idx on chunks(document_id);
create index if not exists chunks_embedding_idx on chunks using ivfflat (embedding vector_cosine_ops) with (lists = 10);

create table if not exists eval_questions (
    question_id text primary key,
    question text not null,
    intent text not null,
    expected_documents jsonb not null default '[]'::jsonb,
    expected_sections jsonb not null default '[]'::jsonb,
    expected_answer_points jsonb not null default '[]'::jsonb,
    should_abstain boolean not null,
    difficulty text not null,
    created_at timestamptz not null default now()
);

create table if not exists retrieval_runs (
    run_id text primary key,
    question_id text references eval_questions(question_id) on delete set null,
    query text not null,
    chunking_strategy text not null,
    embedding_model text not null,
    top_k integer not null check (top_k > 0),
    results jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create or replace function match_chunks(
    query_embedding vector(384),
    match_count integer,
    requested_strategy text default 'naive'
)
returns table (
    chunk_id text,
    document_id text,
    content text,
    section text,
    page integer,
    retrieval_score real
)
language sql stable
as $$
    select c.chunk_id, c.document_id, c.content, c.section, c.page_start,
           (1 - (c.embedding <=> query_embedding))::real as retrieval_score
    from chunks c
    where c.chunking_strategy = requested_strategy
    order by c.embedding <=> query_embedding
    limit match_count;
$$;