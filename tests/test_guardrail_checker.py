import pytest

from app.models import LogicProgram
from app.guardrail_checker import run_guardrail


def build_valid_program() -> LogicProgram:
    return LogicProgram(
        dsl_version="2.1",
        predicates={
            "Contratto": {"arity": 1, "sorts": ["Contratto"]},
            "Inadempimento": {"arity": 2, "sorts": ["Debitore", "Contratto"]},
        },
        rules=[
            {
                "condition": "(and (Contratto ContrattoServizi) (Inadempimento Professionista ContrattoServizi))",
                "conclusion": "(Contratto ContrattoServizi)",
            }
        ],
        query="(Contratto ContrattoServizi)",
    )


def test_guardrail_accepts_valid_program():
    program = build_valid_program()
    result = run_guardrail(program)
    assert result.ok, f"Expected guardrail to accept valid program, issues: {result.issues}"


def test_guardrail_detects_invalid_predicate():
    program = build_valid_program()
    program.predicates["Contratto"]["arity"] = 2  # type: ignore[index]

    result = run_guardrail(program)

    assert not result.ok
    assert any(issue.code == "PREDICATE_ARITY_MISMATCH" for issue in result.issues)

