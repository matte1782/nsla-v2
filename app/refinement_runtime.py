"""
Phase 2.3 – Refinement runtime.

This module centralizes the orchestration of solver-guided refinement prompts.
It adds:
- graceful fallback when the LLM backend is unavailable
- structured logging of prompt context (status, missing links, history)
- optional history summaries used by the iterative controller.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .logic_feedback import LogicFeedback
from .models import LogicProgram
from .models_v2 import LLMOutputV2

logger = logging.getLogger(__name__)


class RefinementRuntime:
    MAX_REFINEMENT_ATTEMPTS = 2

    """
    Execute the Phase 2.3 refinement prompt and normalize the output.

    Args:
        llm_client: Provides ``call_refinement_llm`` and dummy helpers.
    """

    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def run(
        self,
        question: str,
        current_program: LogicProgram,
        current_feedback: LogicFeedback,
        *,
        previous_answer: Optional[str] = None,
        history_summary: Optional[str] = None,
    ) -> LLMOutputV2:
        """
        Run the refinement LLM and validate the resulting ``LLMOutputV2``.
        """
        attempts = 0
        retry_hint = ""
        last_result: Optional[LLMOutputV2] = None

        while attempts < self.MAX_REFINEMENT_ATTEMPTS:
            try:
                runtime_history = history_summary
                if retry_hint:
                    base = history_summary or "Nessuna iterazione precedente: primo refinement."
                    runtime_history = f"{base}\n\n{retry_hint}"
                raw_dict = self.llm_client.call_refinement_llm(
                    question=question,
                    logic_program_v1=current_program,
                    feedback_v1=current_feedback,
                    answer_v1=previous_answer,
                    history_summary=runtime_history,
                )
                result = LLMOutputV2(**raw_dict)
                last_result = result
                if self._covers_missing_links(
                    result.logic_program, current_feedback.missing_links
                ):
                    logger.info(
                        "Refinement runtime completed (status=%s, predicates=%d)",
                        current_feedback.status,
                        len(result.logic_program.get("predicates", {})),
                    )
                    return result
                retry_hint = self._build_retry_hint(current_feedback.missing_links)
                attempts += 1
                logger.warning(
                    "Refinement output missing predicates %s. Retrying (%d/%d).",
                    current_feedback.missing_links,
                    attempts,
                    self.MAX_REFINEMENT_ATTEMPTS,
                )
            except Exception as exc:  # pragma: no cover - fallback path
                logger.error(
                    "Refinement runtime failed (%s). Returning deterministic fallback.",
                    exc,
                    exc_info=True,
                )
                return self._fallback_output(
                    question=question,
                    previous_answer=previous_answer,
                    current_program=current_program,
                )

        return last_result or self._fallback_output(
            question=question,
            previous_answer=previous_answer,
            current_program=current_program,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _fallback_output(
        self,
        question: str,
        previous_answer: Optional[str],
        *,
        current_program: Optional[LogicProgram] = None,
    ) -> LLMOutputV2:
        builder = getattr(self.llm_client, "_build_dummy_logic_program", None)
        if current_program is not None:
            logic_program = current_program.model_dump()
        elif callable(builder):
            logic_program = builder(question).model_dump()
        else:
            logic_program = LogicProgram().model_dump()

        answer = previous_answer or (
            "Risposta generica (fallback) in attesa di un refinement valido."
        )

        return LLMOutputV2(
            final_answer=answer,
            logic_program=logic_program,
            notes="Fallback refinement output",
        )

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _covers_missing_links(
        logic_program: Dict[str, Any],
        missing_links: List[str],
    ) -> bool:
        if not missing_links:
            return True

        corpus: List[str] = []
        for axiom in logic_program.get("axioms", []):
            if isinstance(axiom, dict):
                formula = axiom.get("formula")
            else:
                formula = str(axiom)
            if formula:
                corpus.append(str(formula))
        for rule in logic_program.get("rules", []):
            if isinstance(rule, dict):
                corpus.append(str(rule.get("condition") or ""))
                corpus.append(str(rule.get("conclusion") or ""))
            else:
                corpus.append(str(rule))
        query = logic_program.get("query")
        if isinstance(query, str):
            corpus.append(query)

        haystack = "\n".join(corpus).lower()
        for predicate in missing_links:
            token = (predicate or "").strip().lower()
            if not token:
                continue
            if f"{token}(" not in haystack:
                return False
        return True

    @staticmethod
    def _build_retry_hint(missing_links: List[str]) -> str:
        if not missing_links:
            return ""
        joined = ", ".join(sorted({link for link in missing_links if link}))
        return (
            "ATTENZIONE: aggiungi fatti o assiomi per ciascun predicato in "
            f"missing_links ({joined}) prima di restituire l'output."
        )


__all__ = ["RefinementRuntime"]

