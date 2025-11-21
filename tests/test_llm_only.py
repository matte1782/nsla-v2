# tests/test_llm_only.py
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """
    Create a TestClient inside a context manager so that FastAPI's
    lifespan (startup/shutdown) is executed before the first request.
    """
    with TestClient(app) as c:
        yield c


def test_llm_only_endpoint_basic(client: TestClient):
    """
    Test that the /llm_only endpoint:
    * returns HTTP 200,
    * contains a non‑empty "answer" field,
    * includes "mode" and "model_used" fields.
    """
    payload = {"question": "Scrivi in breve cosa si intende per responsabilità contrattuale."}
    resp = client.post("/llm_only", json=payload)

    # The request must succeed.
    assert resp.status_code == 200

    data = resp.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert data["answer"].strip() != ""

    # Meta‑information about the model that was used.
    assert "mode" in data
    assert "model_used" in data
