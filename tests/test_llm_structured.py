# tests/test_llm_structured.py
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """
    Context manager che garantisce l'esecuzione del lifespan
    (avvio/startup) di FastAPI prima del test.
    """
    with TestClient(app) as c:
        yield c


def test_llm_structured_basic(client: TestClient):
    payload = {
        "question": "Cosa si intende per responsabilità contrattuale?"
    }
    resp = client.post("/llm_structured", json=payload)

    # HTTP 200 e struttura JSON corretta
    assert resp.status_code == 200
    data = resp.json()

    assert "final_answer" in data
    assert "premises" in data
    assert "conclusion" in data
    assert "logic_program" in data

    logic = data["logic_program"]
    assert "sorts" in logic
    assert "constants" in logic
    assert "axioms" in logic
    assert "query" in logic
