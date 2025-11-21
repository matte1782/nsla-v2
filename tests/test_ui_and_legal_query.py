# tests/test_ui_and_legal_query.py
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """
    TestClient con context manager per garantire l'esecuzione del lifespan.
    """
    with TestClient(app) as c:
        yield c


def test_ui_root_loads(client: TestClient):
    """
    Verifica che la pagina HTML (GET /) sia servita correttamente
    e contenga gli elementi fondamentali del form.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<textarea" in resp.text
    assert "btn-send" in resp.text or "Invia" in resp.text


def test_legal_query_basic(client: TestClient):
    """
    Verifica l'endpoint /legal_query risponda con la struttura minima
    prevista dal modello LegalQueryResult.
    """
    payload = {
        "question": "In breve, cosa si intende per responsabilità contrattuale?"
    }
    resp = client.post("/legal_query", json=payload)
    assert resp.status_code == 200

    data = resp.json()

    # Chiavi richieste da LegalQueryResult
    assert "answer" in data
    assert "verified" in data
    assert "z3_status" in data
    assert "logic_program" in data
    assert "facts" in data

    # Controllo di tipi e contenuto minimo
    assert isinstance(data["answer"], str)
    assert data["answer"].strip() != ""
    assert isinstance(data["verified"], bool)
    assert isinstance(data["z3_status"], str)
    assert isinstance(data["logic_program"], dict)
    assert isinstance(data["facts"], dict)
