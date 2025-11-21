# tests/test_phase3_e2e.py
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


def test_phase3_e2e_pipeline(client: TestClient):
    """
    Test end-to-end della pipeline Phase 3:
    1. Verifica /llm_only con una domanda legale semplice
    2. Verifica /llm_structured con una seconda domanda legale
    3. Verifica /debug_logic con una terza domanda legale
    Controlla solo la struttura delle risposte, non il contenuto semantico
    """
    
    # Test 1: /llm_only
    question1 = "Qual è la definizione di contratto?"
    resp1 = client.post("/llm_only", json={"question": question1})
    
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "answer" in data1
    assert isinstance(data1["answer"], str)
    assert data1["answer"].strip() != ""  # answer non vuota
    
    # Test 2: /llm_structured
    question2 = "Cosa si intende per responsabilità civile?"
    resp2 = client.post("/llm_structured", json={"question": question2})
    
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert "final_answer" in data2
    assert "premises" in data2
    assert "conclusion" in data2
    assert "logic_program" in data2
    
    # Controlla tipi e che i campi non siano vuoti
    assert isinstance(data2["final_answer"], str)
    assert data2["final_answer"].strip() != ""
    assert isinstance(data2["premises"], list)
    assert len(data2["premises"]) > 0
    assert isinstance(data2["conclusion"], str)
    assert data2["conclusion"].strip() != ""
    assert isinstance(data2["logic_program"], dict)
    
    # Test 3: /debug_logic
    question3 = "Quali sono gli elementi del reato di furto?"
    resp3 = client.post("/debug_logic", json={"question": question3})
    
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert "z3_status" in data3
    assert "normalized_question" in data3
    assert "facts" in data3
    assert "has_query" in data3
    
    # Controlla che i campi siano dei tipi attesi
    assert isinstance(data3["z3_status"], str)
    assert isinstance(data3["normalized_question"], str)
    assert data3["normalized_question"].strip() != ""
    assert isinstance(data3["facts"], dict)
    assert isinstance(data3["has_query"], bool)
