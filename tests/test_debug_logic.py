# tests/test_debug_logic.py
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """
    Context manager per TestClient che esegue il lifespan di FastAPI
    """
    with TestClient(app) as c:
        yield c


def test_debug_logic(client: TestClient):
    """
    Test dell'endpoint /debug_logic: verifica che risponda con i campi corretti
    """
    payload = {"question": "Cosa si intende per responsabilità contrattuale?"}
    resp = client.post("/debug_logic", json=payload)
    
    assert resp.status_code == 200
    data = resp.json()
    
    # Controlla la struttura della risposta
    assert "z3_status" in data
    assert "normalized_question" in data
    assert "facts" in data
    assert "has_query" in data
    
    # Controlla i tipi e che i campi essenziali non siano vuoti
    assert isinstance(data["z3_status"], str)
    assert data["z3_status"] != ""
    assert isinstance(data["normalized_question"], str)
    assert data["normalized_question"].strip() != ""
    assert isinstance(data["facts"], dict)
    assert isinstance(data["has_query"], bool)
