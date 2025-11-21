from app.explanation_synthesizer import synthesize_explanation
from app.logic_feedback import LogicFeedback
from app.models_v2 import GuardrailResult


def _feedback(status: str) -> LogicFeedback:
    return LogicFeedback(
        status=status,
        conflicting_axioms=[],
        missing_links=["NessoCausale"] if status != "consistent_entails" else [],
        human_summary="Mock summary",
    )


def test_explanation_success_status():
    explanation = synthesize_explanation(
        question="Cos'è un contratto?",
        final_answer="Sì, il contratto è valido.",
        feedback=_feedback("consistent_entails"),
        guardrail=GuardrailResult(ok=True, issues=[]),
    )

    assert explanation.status == "consistent_entails"
    assert "contratto" in explanation.summary.lower()


def test_explanation_guardrail_failure():
    explanation = synthesize_explanation(
        question="Test",
        final_answer="",
        feedback=_feedback("consistent_no_entailment"),
        guardrail=GuardrailResult(ok=False, issues=[]),
    )

    assert explanation.status == "guardrail_failed"

