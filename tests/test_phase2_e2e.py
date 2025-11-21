# tests/test_phase2_e2e.py
from fastapi.testclient import TestClient
from app.main import app

def test_phase2_e2e_llm_only_and_structured():
    """
    End-to-end test per la Phase 2 del progetto NSLA.
    Verifica che:
    1) /llm_only funzioni correttamente
    2) /llm_structured funzioni con più domande diverse
    3) La struttura delle risposte strutturate sia valida
    """
    with TestClient(app) as client:
        # Test /llm_only
        question_plain = "Qual è la differenza tra reato e illecito civile?"
        resp_plain = client.post("/llm_only", json={"question": question_plain})
        
        assert resp_plain.status_code == 200
        data_plain = resp_plain.json()
        assert "answer" in data_plain
        assert isinstance(data_plain["answer"], str)
        assert data_plain["answer"].strip() != ""
        
        # Test /llm_structured con più domande
        questions_structured = [
            "Cosa si intende per risarcimento del danno?",
            "Quali sono gli elementi costitutivi della colpa?",
            "Come si configura il reato di truffa?"
        ]
        
        structured_results = []
        
        for question in questions_structured:
            resp_struct = client.post("/llm_structured", json={"question": question})
            
            assert resp_struct.status_code == 200
            data_struct = resp_struct.json()
            
            # Verifica struttura JSON
            assert "final_answer" in data_struct
            assert "premises" in data_struct
            assert "conclusion" in data_struct
            assert "logic_program" in data_struct
            
            # Verifica contenuto
            assert isinstance(data_struct["final_answer"], str)
            assert data_struct["final_answer"].strip() != ""
            
            assert isinstance(data_struct["premises"], list)
            assert len(data_struct["premises"]) >= 1
            
            assert isinstance(data_struct["conclusion"], str)
            assert data_struct["conclusion"].strip() != ""
            
            # Verifica logic_program
            logic = data_struct["logic_program"]
            assert isinstance(logic, dict)
            assert "sorts" in logic
            assert "constants" in logic
            assert "axioms" in logic
            assert "query" in logic
            
            structured_results.append(question)
        
        # Stampiamo un riepilogo semplice
        print(f"\nTest E2E Phase 2 completato con successo!")
        print(f"- /llm_only: 1 domanda testata ✓")
        print(f"- /llm_structured: {len(structured_results)} domande testate ✓")
        print(f"- Risposte strutturate: tutte valide ✓")
