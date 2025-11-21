from app.canonicalizer_runtime import CanonicalizerRuntime
from app.structured_extractor import StructuredExtractorRuntime
from app.refinement_runtime import RefinementRuntime
from app.models import LogicProgram
from app.logic_feedback import LogicFeedback
from app.models_v2 import CanonicalizerOutput, LLMOutputV2


class _CanonicalizerStub:
    def __init__(self):
        self.calls = 0

    def call_canonicalizer(self, question: str) -> CanonicalizerOutput:
        self.calls += 1
        return CanonicalizerOutput(
            question=question,
            language="it",
            domain="civil_law_contractual_liability",
            concepts=[],
            unmapped_terms=[],
        )


def test_canonicalizer_runtime_cache_hits():
    stub = _CanonicalizerStub()
    runtime = CanonicalizerRuntime(stub, enable_cache=True)

    out_1 = runtime.run("Qual è la responsabilità del debitore?")
    out_2 = runtime.run(" Qual è la responsabilità del debitore? ")

    assert stub.calls == 1, "Expected cached result on second call"
    assert out_1 == out_2


def test_structured_extractor_enforces_version_and_fallback():
    class _ExtractorStub:
        def __init__(self, fail=False):
            self.fail = fail
            self.calls = 0

        def call_structured_extractor(self, question, canonicalization):
            self.calls += 1
            if self.fail:
                raise RuntimeError("boom")
            return LogicProgram(dsl_version="0.9", predicates={"P": {"arity": 0}})

        @staticmethod
        def _build_dummy_logic_program(question):
            return LogicProgram(dsl_version="2.1")

    canonicalization = CanonicalizerOutput(
        question="Test",
        language="it",
        domain="civil_law_contractual_liability",
        concepts=[],
        unmapped_terms=[],
    )

    happy = StructuredExtractorRuntime(_ExtractorStub())
    program = happy.run("Test", canonicalization)
    assert program.dsl_version == "2.1"

    fallback_prog = LogicProgram(dsl_version="2.1", predicates={"F": {"arity": 0}})
    failing = StructuredExtractorRuntime(_ExtractorStub(fail=True))
    program_fb = failing.run("Test", canonicalization, fallback_program=fallback_prog)
    assert program_fb is fallback_prog


class _RefinementStubClient:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.received_history = None

    def call_refinement_llm(
        self,
        question,
        logic_program_v1,
        feedback_v1,
        answer_v1=None,
        history_summary=None,
    ):
        if self.should_fail:
            raise RuntimeError("LLM offline")
        self.received_history = history_summary
        return {
            "final_answer": answer_v1 or "Risposta",
            "logic_program": logic_program_v1.model_dump(),
            "notes": "ok",
        }

    @staticmethod
    def _build_dummy_logic_program(question):
        return LogicProgram(dsl_version="2.1")


def test_refinement_runtime_passes_history_and_answer():
    client = _RefinementStubClient()
    runtime = RefinementRuntime(client)
    program = LogicProgram(dsl_version="2.1")
    feedback = LogicFeedback(
        status="consistent_no_entailment",
        conflicting_axioms=[],
        missing_links=["NessoCausale"],
        human_summary="Manca il nesso causale.",
    )

    result = runtime.run(
        "Domanda",
        program,
        feedback,
        previous_answer="Risposta v1",
        history_summary="Iter 0: mancava NessoCausale",
    )

    assert isinstance(result, LLMOutputV2)
    assert result.final_answer == "Risposta v1"
    assert client.received_history == "Iter 0: mancava NessoCausale"


def test_refinement_runtime_fallback_on_failure():
    client = _RefinementStubClient(should_fail=True)
    runtime = RefinementRuntime(client)
    program = LogicProgram(dsl_version="2.1")
    feedback = LogicFeedback(
        status="inconsistent",
        conflicting_axioms=["r1"],
        missing_links=[],
        human_summary="Conflicts",
    )

    result = runtime.run("Domanda", program, feedback, previous_answer="Prev answer")
    assert result.final_answer == "Prev answer"
    assert result.logic_program["dsl_version"] == "2.1"

