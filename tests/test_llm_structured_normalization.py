import json

import pytest

from app.config import Settings
from app.llm_client import LLMClient, LLMCallError


def test_normalize_logic_program_dict_coerces_strings():
    client = LLMClient(Settings(llm_backend="dummy"))
    raw = {
        "dsl_version": "2.1",
        "axioms": ["ContrattoValido(C) -> HaObbligo(C)"],
        "rules": ["HaObbligo(C) -> Responsabilita(C)"],
        "facts": ["has_question_mark"],
        "constants": ["Debitore"],
    }

    normalized, stats = client._normalize_logic_program_dict(raw)

    assert normalized["axioms"][0]["formula"] == "ContrattoValido(C) -> HaObbligo(C)"
    assert normalized["rules"][0]["conclusion"] == "Responsabilita(C)"
    assert normalized["facts"]["has_question_mark"] is True
    assert normalized["constants"]["c0"]["sort"] == "Debitore"
    assert stats["axiom_strings_wrapped"] == 1
    assert stats["rule_strings_wrapped"] == 1
    assert stats["fact_list_coerced"] == 1
    assert stats["constant_list_coerced"] == 1


def test_rule_parts_from_string_handles_arrows():
    client = LLMClient(Settings(llm_backend="dummy"))

    condition, conclusion = client._rule_parts_from_string("A -> B")
    assert condition == "A"
    assert conclusion == "B"

    condition2, conclusion2 = client._rule_parts_from_string("B :- A")
    assert condition2 == "A"
    assert conclusion2 == "B"


def test_ask_llm_structured_normalizes_logic_program(monkeypatch):
    client = LLMClient(Settings(llm_backend="dummy"))

    def fake_raw(question: str) -> str:
        return json.dumps(
            {
                "final_answer": "Test",
                "premises": [],
                "conclusion": "Test",
                "logic_program": {
                    "dsl_version": "2.1",
                    "axioms": ["ContrattoValido(C) -> HaObbligo(C)"],
                    "predicates": {},
                    "rules": [],
                },
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(client, "ask_llm_structured_raw", fake_raw)

    output = client.ask_llm_structured("Q")
    assert isinstance(output.logic_program.axioms[0], dict)
    assert output.logic_program.axioms[0]["formula"].startswith("ContrattoValido")


def test_call_llm_with_retry_records_status(monkeypatch):
    client = LLMClient(Settings(llm_backend="ollama"))
    client.max_retries = 1

    def fake_call(prompt: str, timeout: int = 300) -> str:
        raise RuntimeError("fireworks_chat_tp: 429: Request didn't generate first token before the given deadline")

    monkeypatch.setattr(client, "_call_ollama", fake_call)

    with pytest.raises(LLMCallError) as exc:
        client._call_llm_with_retry("prompt", timeout=1, operation_name="Canonicalizer")
    assert exc.value.reason in {"throttled", "error"}
    statuses = client.pop_llm_statuses()
    assert "Canonicalizer" in statuses
    assert "error" in statuses["Canonicalizer"]

