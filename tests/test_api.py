from fastapi.testclient import TestClient

from app.api import main


client = TestClient(main.app)


EVIDENCE = [
    {
        "chunk_id": "chunk-registration",
        "document_id": "doc-licensing",
        "content": "Every petty Food Business Operator shall register themselves.",
        "section": "2.1.1 Registration of Petty Food Business",
        "page": 2,
        "document_title": "Licensing and Registration of Food Businesses",
        "authority": "Food Safety and Standards Authority of India",
        "retrieval_score": 0.91,
    },
    {
        "chunk_id": "chunk-fee",
        "document_id": "doc-licensing",
        "content": "Fees are prescribed in Schedule 3.",
        "section": "SCHEDULE - 3",
        "page": 22,
        "document_title": "Licensing and Registration of Food Businesses",
        "authority": "Food Safety and Standards Authority of India",
        "retrieval_score": 0.82,
    },
]


def test_health_returns_naive_strategy():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "retrieval_strategy": "naive"}


def test_direct_answer_exposes_only_cited_sources(monkeypatch):
    monkeypatch.setattr(main, "retrieve", lambda question, strategy: EVIDENCE)
    monkeypatch.setattr(
        main,
        "generate_answer",
        lambda question, evidence: {
            "answer": "Register with the Registering Authority using the required process.\n",
            "answer_type": "direct",
            "citations": ["chunk-registration"],
        },
    )

    response = client.post(
        "/api/questions",
        json={"question": "How do I register?", "conversation_id": "conversation-1"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["answer_type"] == "direct"
    assert body["citations"] == ["chunk-registration"]
    assert [source["id"] for source in body["sources"]] == ["S1"]
    assert body["conversation_id"] == "conversation-1"
    assert "not legal advice" in body["disclaimer"]


def test_empty_retrieval_abstains_without_calling_generation(monkeypatch):
    monkeypatch.setattr(main, "retrieve", lambda question, strategy: [])

    def fail_generation(question, evidence):
        raise AssertionError("generation should not run without evidence")

    monkeypatch.setattr(main, "generate_answer", fail_generation)

    response = client.post("/api/questions", json={"question": "Is this covered?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer_type"] == "abstain"
    assert body["citations"] == []
    assert body["sources"] == []


def test_invalid_question_is_rejected():
    response = client.post("/api/questions", json={"question": "?"})

    assert response.status_code == 422