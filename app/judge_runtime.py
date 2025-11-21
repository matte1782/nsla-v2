from __future__ import annotations

import logging
from typing import Optional

from .models_v2 import JudgeLLMResult

logger = logging.getLogger(__name__)


class JudgeRuntime:
    """
    Phase 4 Judge-LLM runtime.

    Wraps the `LLMClient.call_judge_metric` helper and provides
    graceful fallbacks when the judge is disabled or unavailable.
    """

    def __init__(self, llm_client, *, enabled: bool = True) -> None:
        self.llm_client = llm_client
        self.enabled = enabled

    def evaluate(
        self,
        question: str,
        reference_answer: Optional[str],
        answer_a: str,
        answer_b: str,
        label_a: str = "baseline_v1",
        label_b: str = "nsla_v2",
    ) -> JudgeLLMResult:
        """
        Execute the Judge-LLM metric.

        Args:
            question: Original legal question.
            reference_answer: Gold/reference answer (can be empty/None).
            answer_a: Baseline answer.
            answer_b: Candidate answer to evaluate (typically Phase 2/3 output).
            label_a: Human-readable label for answer_a.
            label_b: Human-readable label for answer_b.
        """

        if not self.enabled:
            return JudgeLLMResult(
                question=question,
                reference_answer=reference_answer,
                answer_a=answer_a,
                answer_b=answer_b,
                label_a=label_a,
                label_b=label_b,
                vote="tie",
                rationale="Judge metric disabled.",
                confidence=0.0,
            )

        try:
            return self.llm_client.call_judge_metric(
                question=question,
                reference_answer=reference_answer,
                answer_a=answer_a,
                answer_b=answer_b,
                label_a=label_a,
                label_b=label_b,
            )
        except Exception as exc:  # pragma: no cover - defensive path
            logger.warning("Judge runtime failed: %s", exc, exc_info=True)
            return JudgeLLMResult(
                question=question,
                reference_answer=reference_answer,
                answer_a=answer_a,
                answer_b=answer_b,
                label_a=label_a,
                label_b=label_b,
                vote="tie",
                rationale=f"Judge runtime error: {exc}",
                confidence=0.0,
            )


__all__ = ["JudgeRuntime"]

