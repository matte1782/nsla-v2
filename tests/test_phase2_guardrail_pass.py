from app.models import LogicProgram
from app.guardrail_checker import run_guardrail


def test_guardrail_passes_canonical_program():
    program = LogicProgram(
        dsl_version="2.1",
        sorts={
            "Debitore": {"type": "Debitore"},
            "Creditore": {"type": "Creditore"},
            "Contratto": {"type": "Contratto"},
            "Danno": {"type": "Danno"},
        },
        constants={
            "parte_a": {"sort": "Debitore"},
            "parte_b": {"sort": "Creditore"},
            "contratto_x": {"sort": "Contratto"},
            "danno_y": {"sort": "Danno"},
        },
        predicates={
            "HaObbligo": {
                "arity": 3,
                "sorts": ["Debitore", "Creditore", "Contratto"],
            },
            "ContrattoValido": {
                "arity": 2,
                "sorts": ["Debitore", "Contratto"],
            },
            "Inadempimento": {
                "arity": 2,
                "sorts": ["Debitore", "Contratto"],
            },
            "Imputabilita": {
                "arity": 2,
                "sorts": ["Debitore", "Contratto"],
            },
            "DannoPatrimoniale": {
                "arity": 1,
                "sorts": ["Creditore"],
            },
            "NessoCausale": {
                "arity": 2,
                "sorts": ["Debitore", "Creditore"],
            },
            "ResponsabilitaContrattuale": {
                "arity": 3,
                "sorts": ["Debitore", "Creditore", "Contratto"],
            },
        },
        rules=[
            {
                "condition": "(and (HaObbligo parte_a parte_b contratto_x) "
                "(ContrattoValido parte_a contratto_x) "
                "(Inadempimento parte_a contratto_x) "
                "(Imputabilita parte_a contratto_x) "
                "(DannoPatrimoniale parte_b) "
                "(NessoCausale parte_a parte_b))",
                "conclusion": "(ResponsabilitaContrattuale parte_a parte_b contratto_x)",
            }
        ],
        query="(ResponsabilitaContrattuale parte_a parte_b contratto_x)",
    )

    result = run_guardrail(program)

    assert result.ok is True
    assert result.issues == []


def test_guardrail_flags_unknown_sort():
    program = LogicProgram(
        dsl_version="2.1",
        sorts={"Fantasia": {"type": "Fantasia"}},
        predicates={},
    )

    result = run_guardrail(program)

    assert result.ok is False
    assert any(issue.code == "UNKNOWN_SORT_DECLARATION" for issue in result.issues)


def test_guardrail_accepts_aliases_and_synonyms():
    program = LogicProgram(
        dsl_version="2.1",
        sorts={
            "soggetto obbligato all'adempimento": {"type": "Soggetto"},
            "soggetto titolare della pretesa": {"type": "Soggetto"},
            "accordo tra parti": {"type": "Accordo"},
        },
        predicates={
            "responsabilitacontrattuale": {
                "arity": 3,
                "sorts": [
                    "soggetto obbligato all'adempimento",
                    "soggetto titolare della pretesa",
                    "accordo tra parti",
                ],
            }
        },
        rules=[
            {
                "condition": "responsabilitacontrattuale(deb, cred, contr)",
                "conclusion": "responsabilitacontrattuale(deb, cred, contr)",
            }
        ],
    )

    result = run_guardrail(program)
    assert result.ok is True


def test_guardrail_flags_unknown_predicate_in_rules():
    program = LogicProgram(
        dsl_version="2.1",
        sorts={},
        predicates={},
        rules=[{"condition": "Inesistente()", "conclusion": "Altro()"}],
    )

    result = run_guardrail(program)
    assert result.ok is False
    assert any(issue.code == "RULE_UNKNOWN_PREDICATE" for issue in result.issues)

