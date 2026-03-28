"""Tests para knowledge routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.knowledge_routes import create_knowledge_router


class _Doc:
    def __init__(self, content: str, name: str, score: float | None = None):
        self.content = content
        self.name = name
        self.score = score


class _FakeKnowledge:
    def __init__(self):
        self.search_calls = []

    def search(self, query: str, max_results: int | None = None, filters=None, search_type=None):
        self.search_calls.append(
            {
                "query": query,
                "max_results": max_results,
                "filters": filters,
                "search_type": search_type,
            }
        )
        return [_Doc(content="resultado", name="doc-1", score=0.9)]


def test_search_knowledge_uses_max_results_signature():
    knowledge = _FakeKnowledge()
    app = FastAPI()
    app.include_router(create_knowledge_router(knowledge))
    client = TestClient(app)

    response = client.post("/knowledge/search", json={"query": "hola", "max_results": 3})

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert knowledge.search_calls == [
        {
            "query": "hola",
            "max_results": 3,
            "filters": None,
            "search_type": None,
        }
    ]
