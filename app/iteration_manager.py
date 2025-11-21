"""
Phase 3 – Iteration Manager.

Controls the bounded LLM ↔ Z3 refinement loop, delegating the actual refinement
prompt to ``RefinementRuntime`` and summarizing states via ``HistorySummarizer``.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple

from .history_summarizer import HistorySummarizer
from .logic_feedback import LogicFeedback, build_logic_feedback
from .models import LogicProgram
from .models_v2 import IterationMetrics, IterationState, NSLAIterativeConfig
from .refinement_runtime import RefinementRuntime
from .translator import build_solver
from .canonical_rule_utils import ensure_canonical_query_rule

logger = logging.getLogger(__name__)

FeedbackBuilder = Callable[[object, LogicProgram, object], LogicFeedback]
SolverBuilder = Callable[[LogicProgram, dict], Tuple[object, object]]


class IterationManager:
    """
    Execute the bounded iterative refinement loop (Phase 3).
    """

    def __init__(
        self,
        refinement_runtime: RefinementRuntime,
        config: Optional[NSLAIterativeConfig] = None,
        history_summarizer: Optional[HistorySummarizer] = None,
        solver_builder: SolverBuilder = build_solver,
        feedback_builder: FeedbackBuilder = build_logic_feedback,
        program_sanitizer: Optional[Callable[[LogicProgram], None]] = None,
        program_hydrator: Optional[Callable[[LogicProgram], None]] = None,
        feedback_postprocessor: Optional[
            Callable[[LogicProgram, LogicFeedback], LogicFeedback]
        ] = None,
    ) -> None:
        self.refinement_runtime = refinement_runtime
        self.config = config or NSLAIterativeConfig()
        self.history_summarizer = history_summarizer or HistorySummarizer()
        self.solver_builder = solver_builder
        self.feedback_builder = feedback_builder
        self.program_sanitizer = program_sanitizer
        self.program_hydrator = program_hydrator
        self.feedback_postprocessor = feedback_postprocessor

    def run(
        self,
        question: str,
        initial_program: LogicProgram,
        initial_feedback: LogicFeedback,
        initial_answer: Optional[str],
    ) -> Tuple[IterationState, List[IterationState]]:
        """
        Execute the loop and return (best_state, history).
        """
        history: List[IterationState] = []

        # Iteration 0 uses the structured extractor output as baseline
        self._append_iteration(
            history=history,
            iteration_index=0,
            question=question,
            base_program=initial_program,
            feedback=initial_feedback,
            previous_answer=initial_answer,
        )

        while not self._should_stop(history):
            iter_idx = len(history)
            summary = self.history_summarizer.summarize(history)
            prev_state = history[-1]
            base_program_dict = self._prepare_logic_program_dict(prev_state.llm_output.logic_program)
            base_program = LogicProgram(**base_program_dict)
            self._postprocess_program(base_program)
            ensure_canonical_query_rule(base_program)

            self._append_iteration(
                history=history,
                iteration_index=iter_idx,
                question=question,
                base_program=base_program,
                feedback=prev_state.feedback,
                previous_answer=prev_state.llm_output.final_answer,
                history_summary=summary,
            )

            if len(history) >= self.config.max_iters:
                break

        best_state = self._select_best_state(history)
        return best_state, history

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #
    def _append_iteration(
        self,
        history: List[IterationState],
        iteration_index: int,
        question: str,
        base_program: LogicProgram,
        feedback: LogicFeedback,
        previous_answer: Optional[str],
        history_summary: Optional[str] = None,
    ) -> None:
        llm_output = self.refinement_runtime.run(
            question=question,
            current_program=base_program,
            current_feedback=feedback,
            previous_answer=previous_answer,
            history_summary=history_summary,
        )

        logic_dict = self._prepare_logic_program_dict(llm_output.logic_program)
        logic_program = LogicProgram(**logic_dict)
        self._postprocess_program(logic_program)
        ensure_canonical_query_rule(logic_program)
        solver, query = self.solver_builder(logic_program, facts={})
        next_feedback = self.feedback_builder(solver, logic_program, query)
        if self.feedback_postprocessor:
            next_feedback = self.feedback_postprocessor(logic_program, next_feedback)
        llm_output.logic_program = logic_program.model_dump()

        metrics = IterationMetrics(
            iteration=iteration_index,
            z3_status=next_feedback.status,
            is_best=next_feedback.status == "consistent_entails",
        )

        history.append(
            IterationState(
                iteration=iteration_index,
                llm_output=llm_output,
                feedback=next_feedback,
                metrics=metrics,
            )
        )

    def _should_stop(self, history: List[IterationState]) -> bool:
        if not history:
            return False

        last_state = history[-1]
        if last_state.feedback.status in self.config.stop_on_status:
            return True

        if len(history) >= self.config.max_iters:
            return True

        if len(history) >= 2:
            prev_state = history[-2]
            if (
                prev_state.feedback.status == last_state.feedback.status
                and sorted(prev_state.feedback.missing_links)
                == sorted(last_state.feedback.missing_links)
                and sorted(prev_state.feedback.conflicting_axioms)
                == sorted(last_state.feedback.conflicting_axioms)
            ):
                # No logical change between consecutive iterations
                return True

        return False

    def _select_best_state(self, history: List[IterationState]) -> IterationState:
        # Prefer explicit is_best flag if available
        for state in history:
            if state.metrics.is_best:
                return state

        # Next preference: first consistent_entails
        for state in history:
            if state.feedback.status == "consistent_entails":
                return state

        # Otherwise return the last iteration
        return history[-1]

    @staticmethod
    def _prepare_logic_program_dict(raw: object) -> dict:
        if not isinstance(raw, dict):
            return {}
        data = dict(raw)

        facts = data.get("facts")
        if isinstance(facts, list):
            data["facts"] = {fact: True for fact in facts if isinstance(fact, str)}
        elif not isinstance(facts, dict):
            data["facts"] = {}

        predicates = data.get("predicates")
        if not isinstance(predicates, dict):
            data["predicates"] = {}

        constants = data.get("constants")
        if not isinstance(constants, dict):
            data["constants"] = {}

        axioms = data.get("axioms")
        if axioms is None:
            data["axioms"] = []

        rules = data.get("rules")
        if rules is None:
            data["rules"] = []

        return data

    def _postprocess_program(self, program: LogicProgram) -> None:
        if self.program_sanitizer:
            self.program_sanitizer(program)
        if self.program_hydrator:
            self.program_hydrator(program)


__all__ = ["IterationManager"]

