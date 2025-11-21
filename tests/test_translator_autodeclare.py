from app.models import LogicProgram
from app.translator import build_solver


def test_translator_auto_declares_unknown_predicate_in_rules():
    program = LogicProgram(
        dsl_version="2.1",
        sorts={"Entity": {"type": "Entity"}},
        predicates={},
        rules=[
            {"condition": "UsucapioneOrdinaria(D,C)", "conclusion": "Responsabilita(D,C)"},
        ],
        query="UsucapioneOrdinaria(D,C)",
    )

    solver, query = build_solver(program, facts={})

    assert solver is not None
    assert query is not None


def test_translator_handles_single_argument_and():
    program = LogicProgram(
        dsl_version="2.1",
        sorts={},
        predicates={
            "Inadempimento": {"arity": 1, "sorts": ["Entity"]},
        },
        rules=[
            {"condition": "(and (Inadempimento D))", "conclusion": "Inadempimento()"},
        ],
    )

    solver, _ = build_solver(program, facts={})
    assert solver is not None


def test_translator_handles_not_function_style():
    program = LogicProgram(
        dsl_version="2.1",
        sorts={"Entity": {"type": "Entity"}},
        predicates={
            "Responsabilita": {"arity": 2, "sorts": ["Entity", "Entity"]},
            "HaObbligo": {"arity": 2, "sorts": ["Entity", "Entity"]},
        },
        rules=[
            {"condition": "not(Responsabilita(D,C))", "conclusion": "HaObbligo(D,C)"},
        ],
    )

    solver, _ = build_solver(program, facts={})
    assert solver is not None


def test_translator_resolves_sort_and_predicate_aliases():
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
        query="responsabilitacontrattuale(deb, cred, contr)",
    )

    solver, query = build_solver(program, facts={})
    assert solver is not None
    assert query is not None

