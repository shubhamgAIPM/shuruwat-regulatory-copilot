"""Server-side question API for grounded naive RAG answers."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Literal, Optional

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer


DISCLAIMER = (
    "Shuruwat provides information based on its curated FSSAI sources and is not legal advice. "
    "Verify requirements with FSSAI or a qualified professional before acting."
)
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()
app = FastAPI(title="Shuruwat API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_embedding_model: SentenceTransformer | None = None


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    conversation_id: Optional[str] = None
    retrieval_strategy: Literal["naive", "structure_aware"] = "naive"


class Source(BaseModel):
    id: str
    chunk_id: str
    document_id: str
    document_title: str
    authority: str
    section: Optional[str]
    page: int
    excerpt: str
    retrieval_score: float


class QuestionResponse(BaseModel):
    answer: str
    answer_type: Literal["direct", "abstain", "hand_off"]
    citations: list[str]
    sources: list[Source]
    disclaimer: str
    conversation_id: str


def embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        )
    return _embedding_model


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def retrieve(question: str, strategy: str) -> list[dict[str, Any]]:
    query_vector = embedding_model().encode([question], normalize_embeddings=True)[0]
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("set local ivfflat.probes = 10")
            cursor.execute(
                """
                select c.chunk_id, c.document_id, c.content, c.section, c.page_start,
                       d.title, d.authority,
                       (1 - (c.embedding <=> %s::vector))::real as retrieval_score
                from chunks c
                join documents d on d.document_id = c.document_id
                where c.chunking_strategy = %s and c.language = 'en'
                order by c.embedding <=> %s::vector
                limit 5
                """,
                (vector_literal(query_vector.tolist()), strategy, vector_literal(query_vector.tolist())),
            )
            rows = cursor.fetchall()
    return [
        {
            "chunk_id": row[0],
            "document_id": row[1],
            "content": row[2],
            "section": row[3],
            "page": row[4],
            "document_title": row[5],
            "authority": row[6],
            "retrieval_score": float(row[7]),
        }
        for row in rows
    ]


def generate_answer(question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    evidence_text = "\n\n".join(
        f"[{index + 1}] chunk_id={item['chunk_id']} | {item['document_title']} | "
        f"section={item['section'] or 'Not labelled'} | page={item['page']}\n{item['content']}"
        for index, item in enumerate(evidence)
    )
    prompt = f"""You are Shuruwat, a narrow regulatory information assistant.
Answer only from the evidence below. Do not use general knowledge to fill gaps.
The corpus covers FSSAI registration/basic registration, FSSAI food labelling, and the supplied Legal Metrology rules.
For GST, tax, export, cosmetics, packaging materials, state-specific advice, or any unsupported question, use answer_type hand_off or abstain.
If the evidence is insufficient or ambiguous, use answer_type abstain.
Use plain English for a first-time Indian food entrepreneur.
Every material claim must cite one or more evidence numbers such as [1]. Never invent section numbers, pages, URLs, or source metadata.
Return JSON only with keys: answer, answer_type, citation_numbers.
answer_type must be direct, abstain, or hand_off.

QUESTION:
{question}

EVIDENCE:
{evidence_text}
"""
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
    )
    content = completion.choices[0].message.content or "{}"
    result = json.loads(content)
    citation_numbers = result.get("citation_numbers", [])
    valid_numbers = {number for number in citation_numbers if isinstance(number, int) and 1 <= number <= len(evidence)}
    citations = [evidence[number - 1]["chunk_id"] for number in sorted(valid_numbers)]
    return {
        "answer": str(result.get("answer", "I do not have enough evidence to answer that.")),
        "answer_type": result.get("answer_type", "abstain"),
        "citations": citations,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "retrieval_strategy": "naive"}


@app.post("/api/questions", response_model=QuestionResponse)
def answer_question(request: QuestionRequest) -> QuestionResponse:
    try:
        evidence = retrieve(request.question, request.retrieval_strategy)
        if not evidence:
            return QuestionResponse(
                answer="I do not have enough evidence in the curated sources to answer that.",
                answer_type="abstain",
                citations=[],
                sources=[],
                disclaimer=DISCLAIMER,
                conversation_id=request.conversation_id or str(uuid.uuid4()),
            )
        result = generate_answer(request.question, evidence)
        source_models = [
            Source(id=f"S{index + 1}", excerpt=item["content"], **item)
            for index, item in enumerate(evidence)
            if item["chunk_id"] in result["citations"]
        ]
        return QuestionResponse(
            **result,
            sources=source_models,
            disclaimer=DISCLAIMER,
            conversation_id=request.conversation_id or str(uuid.uuid4()),
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail="The regulatory service is temporarily unavailable.") from error