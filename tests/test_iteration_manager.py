from app.iteration_manager import IterationManager
from app.models import LogicProgram
from app.models_v2 import LLMOutputV2, NSLAIterativeConfig
from app.logic_feedback import LogicFeedback
from app.refinement_runtime import RefinementRuntime
from app.history_summarizer import HistorySummarizer


class _StubRefinementRuntime(RefinementRuntime):
    def __init__(self):
        # Do not call super().__init__ to avoid needing a real client
        self.counter = 0

    def run(
        self,
        question,
        current_program,
        current_feedback,
        previous_answer=None,
        history_summary=None,
    ):
        self.counter += 1
        return LLMOutputV2(
            final_answer=f"Iter {self.counter}",
            logic_program={"dsl_version": "2.1"},
            notes="stub",
        )


def _logic_feedback(status, missing=None, conflicts=None, summary=""):
    return LogicFeedback(
        status=status,
        missing_links=missing or [],
        conflicting_axioms=conflicts or [],
        human_summary=summary or status,
    )


def _dummy_solver_builder(program, facts):
    return object(), object()


class _FeedbackSequence:
    def __init__(self, outputs):
        self.outputs = outputs
        self.index = 0

    def __call__(self, solver, program, query):
        result = self.outputs[self.index]
        self.index += 1
        return result


def test_iteration_manager_stops_on_consistent_entails():
    feedbacks = [_logic_feedback("consistent_entails")]
    manager = IterationManager(
        refinement_runtime=_StubRefinementRuntime(),
        config=NSLAIterativeConfig(max_iters=3),
        history_summarizer=HistorySummarizer(),
        solver_builder=_dummy_solver_builder,
        feedback_builder=_FeedbackSequence(feedbacks),
    )

    best, history = manager.run(
        question="Domanda",
        initial_program=LogicProgram(),
        initial_feedback=_logic_feedback("consistent_no_entailment"),
        initial_answer="Risposta v1",
    )

    assert len(history) == 1
    assert best.iteration == 0
    assert best.feedback.status == "consistent_entails"


def test_iteration_manager_detects_no_change():
    seq = _FeedbackSequence(
        [
            _logic_feedback("consistent_no_entailment", ["Nesso"]),
            _logic_feedback("consistent_no_entailment", ["Nesso"]),
        ]
    )
    manager = IterationManager(
        refinement_runtime=_StubRefinementRuntime(),
        config=NSLAIterativeConfig(max_iters=5),
        history_summarizer=HistorySummarizer(),
        solver_builder=_dummy_solver_builder,
        feedback_builder=seq,
    )

    best, history = manager.run(
        question="Domanda",
        initial_program=LogicProgram(),
        initial_feedback=_logic_feedback("consistent_no_entailment"),
        initial_answer="Risposta v1",
    )

    assert len(history) == 2
    assert best.feedback.status == "consistent_no_entailment"


def test_iteration_manager_respects_max_iters():
    seq = _FeedbackSequence(
        [
            _logic_feedback("consistent_no_entailment"),
            _logic_feedback("inconsistent", ["r1"]),
        ]
    )
    manager = IterationManager(
        refinement_runtime=_StubRefinementRuntime(),
        config=NSLAIterativeConfig(max_iters=2),
        history_summarizer=HistorySummarizer(),
        solver_builder=_dummy_solver_builder,
        feedback_builder=seq,
    )

    best, history = manager.run(
        question="Domanda",
        initial_program=LogicProgram(),
        initial_feedback=_logic_feedback("consistent_no_entailment"),
        initial_answer="Risposta v1",
    )

    assert len(history) == 2
    assert best.iteration in {0, 1}

