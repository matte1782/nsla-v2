"""
Phase 2.5 Explanation Synthesis.

Current implementation is deterministic and leverages the available artifacts:
    - final answer proposed by the Phase 2 refinement
    - logic feedback status / summary
    - guardrail result

When the LLM backend is available, this module can be extended to call the
dedicated prompt (`prompt_phase_2_5_explanation_synthesis.txt`).  For now we
produce a concise explanation anchored to the symbolic reasoning outputs.
"""

from __future__ import annotations

from typing import Dict, Any

from .logic_feedback import LogicFeedback
from .models_v2 import ExplanationOutput, GuardrailResult


def synthesize_explanation(
    question: str,
    final_answer: str,
    feedback: LogicFeedback,
    guardrail: GuardrailResult,
) -> ExplanationOutput:
    """
    Build a short explanation referencing the solver feedback and guardrail outcome.

    Args:
        question: Original legal question.
        final_answer: Final answer provided by the LLM/logic program.
        feedback: LogicFeedback produced by Z3 on the final program.
        guardrail: Outcome of Phase 2.4 guardrail checks.

    Returns:
        ExplanationOutput with summary text and status.
    """

    if not guardrail.ok:
        summary = (
            "Il programma logico generato non ha superato i controlli di sicurezza. "
            "È stata mantenuta la risposta precedente oppure è richiesto un nuovo refinement."
        )
        details: Dict[str, Any] = {
            "question": question,
            "final_answer": final_answer,
            "guardrail_issues": [issue.message for issue in guardrail.issues],
        }
        return ExplanationOutput(summary=summary, status="guardrail_failed", details=details)

    status = feedback.status
    if status == "consistent_entails":
        summary = (
            "Il sistema simbolico è coerente e la conclusione proposta è dimostrata "
            "dalle regole modellate. "
            "Risposta finale: "
            f"{final_answer}"
        )
    elif status == "consistent_no_entailment":
        summary = (
            "Il programma logico è coerente ma non implica ancora la conclusione. "
            "Mancano collegamenti o premesse aggiuntive. "
            f"Feedback sintetico: {feedback.human_summary}"
        )
    else:  # inconsistent
        summary = (
            "Il solver ha rilevato un conflitto logico nelle regole generate. "
            "È necessario correggere le premesse: "
            f"{feedback.human_summary}"
        )

    details = {
        "question": question,
        "final_answer": final_answer,
        "missing_links": feedback.missing_links,
        "conflicting_axioms": feedback.conflicting_axioms,
    }

    return ExplanationOutput(summary=summary, status=status, details=details)


__all__ = ["synthesize_explanation"]

