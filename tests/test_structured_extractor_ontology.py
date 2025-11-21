from app.models import LogicProgram
from app.models_v2 import CanonicalizerOutput
from app.structured_extractor import StructuredExtractorRuntime


class _DummyLLM:
    def __init__(self, logic_program: LogicProgram):
        self._logic_program = logic_program

    def call_structured_extractor(self, question, canonicalization):
        return self._logic_program

    def pop_structured_stats(self):
        return {"axiom_strings_wrapped": 0}


def _canonicalization() -> CanonicalizerOutput:
    return CanonicalizerOutput(
        question="Cos'è la responsabilità contrattuale?",
        language="it",
        domain="civil_law_contractual_liability",
        concepts=[],
        unmapped_terms=[],
    )


def test_structured_extractor_hydrates_ontology_sorts():
    dummy_program = LogicProgram(
        dsl_version="2.1",
        sorts={},  # missing metadata on purpose
        constants={
            "deb": "Debitore",
            "credit": {"sort": "Soggetto titolare della pretesa"},
        },
        predicates={
            "Inadempimento": {"arity": 2, "sorts": []},
            "ContrattoValido": {"arity": 2, "sorts": ["Soggetto obbligato all'adempimento", "Accordo tra parti che genera obbligazioni"]},
        },
        rules=[],
    )
    runtime = StructuredExtractorRuntime(_DummyLLM(dummy_program))

    hydrated = runtime.run(
        question="Cos'è la responsabilità contrattuale?",
        canonicalization=_canonicalization(),
    )

    assert "Debitore" in hydrated.sorts
    assert "Creditore" in hydrated.sorts
    assert hydrated.predicates["ContrattoValido"]["sorts"] == ["Debitore", "Contratto"]
    stats = runtime.get_last_stats()
    assert stats.get("sort_alias_hits", 0) >= 1


def test_structured_extractor_normalizes_axioms_rules_and_facts():
    dummy_program = LogicProgram(
        dsl_version="2.1",
        predicates={
            "ResponsabilitaContrattuale": {"arity": 3, "sorts": ["Debitore", "Creditore", "Contratto"]},
        },
        axioms=[
            {"pred": "Contratto", "args": ["ContrattoServizi"]},
        ],
        rules=[
            {"pred": "ResponsabilitaContrattuale", "args": ["Deb", "Cred", "ContrattoServizi"]},
        ],
        facts={
            "ContrattoValido": ["ContrattoServizi"],
        },
    )
    runtime = StructuredExtractorRuntime(_DummyLLM(dummy_program))
    hydrated = runtime.run(
        question="Quando scatta la responsabilità contrattuale?",
        canonicalization=_canonicalization(),
    )
    assert hydrated.axioms[0]["formula"] == "Contratto(ContrattoServizi)"
    assert hydrated.rules[0]["conclusion"].startswith("ResponsabilitaContrattuale")
    assert hydrated.facts["ContrattoValido"] == [["ContrattoServizi"]]


def test_structured_extractor_auto_declares_predicate_aliases():
    dummy_program = LogicProgram(
        dsl_version="2.1",
        predicates={},
        constants={
            "deb": {"sort": "soggetto obbligato all'adempimento"},
            "cred": {"sort": "soggetto titolare della pretesa"},
            "contr": {"sort": "accordo tra parti"},
        },
        rules=[
            {
                "condition": "inadempimento(deb, contr)",
                "conclusion": "responsabilitacontrattuale(deb, cred, contr)",
            }
        ],
    )
    runtime = StructuredExtractorRuntime(_DummyLLM(dummy_program))
    hydrated = runtime.run(
        question="Quando sussiste la responsabilità contrattuale?",
        canonicalization=_canonicalization(),
    )
    assert "ResponsabilitaContrattuale" in hydrated.predicates
    assert hydrated.predicates["ResponsabilitaContrattuale"]["sorts"] == [
        "Debitore",
        "Creditore",
        "Contratto",
    ]
    assert "Debitore" in hydrated.sorts and "Creditore" in hydrated.sorts
    stats = runtime.get_last_stats()
    assert stats.get("predicate_alias_hits", 0) >= 1

