from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel

from .logic_feedback import LogicFeedback
from .models import LogicProgram


class CanonicalizerConcept(BaseModel):
    """
    Single mapped concept from the canonicalizer (Phase 2.1).

    It corresponds to one span of text in the user's question that has been
    mapped to a canonical ontology predicate (or left partially unmapped).
    """

    text: str
    canonical_predicate: Optional[str]
    confidence: float
    notes: Optional[str] = None


class CanonicalizerUnmappedTerm(BaseModel):
    """
    Segment of the question that the canonicalizer could not map
    to any ontology predicate, or that was detected as out-of-scope.
    """

    text: str
    reason: Literal["unknown", "out_of_scope"]


class CanonicalizerOutput(BaseModel):
    """
    JSON schema for the output of the runtime canonicalizer (Phase 2.1).

    This mirrors the structure described in the canonicalizer_agent_vFinal spec:
    - question: original text
    - language: currently always "it"
    - domain: currently always "civil_law_contractual_liability"
    - concepts: successfully mapped concepts
    - unmapped_terms: unknown / out_of_scope segments
    """

    question: str
    language: Literal["it"]
    domain: Literal["civil_law_contractual_liability"]
    concepts: List[CanonicalizerConcept]
    unmapped_terms: List[CanonicalizerUnmappedTerm]


class LLMOutputV2(BaseModel):
    """
    Unified schema for the refined logic program (Phase 2.3) and final answer.

    This is the object that the iterative loop stores at each iteration and that
    is eventually used as the "v2" program to send to the translator/Z3.
    """

    final_answer: str
    logic_program: Dict[str, Any]
    notes: Optional[str] = None


class GuardrailIssue(BaseModel):
    """
    Individual guardrail violation detected during Phase 2.4 checks.
    """

    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class GuardrailResult(BaseModel):
    """
    Result of running the guardrail / static checker (Phase 2.4).
    """

    ok: bool
    issues: List[GuardrailIssue] = []
    notes: Optional[str] = None


class ExplanationOutput(BaseModel):
    """
    Structured explanation produced in Phase 2.5.
    """

    summary: str
    status: str
    details: Optional[Dict[str, Any]] = None


class JudgeLLMResult(BaseModel):
    """
    Output of the Judge-LLM metric (Phase 4).
    """

    question: str
    reference_answer: Optional[str] = None
    answer_a: str
    answer_b: str
    label_a: str = "baseline"
    label_b: str = "nsla_v2"
    vote: str = "tie"
    confidence: float = 0.0
    rationale: Optional[str] = None

    def normalized_vote(self) -> str:
        """Normalize vote to `label_a`, `label_b`, or `tie` for downstream aggregations."""
        vote = (self.vote or "tie").strip()
        if vote.lower() == "tie":
            return "tie"
        if vote.upper() in {self.label_a.upper(), "LLM", "BASELINE"}:
            return self.label_a
        if vote.upper() in {self.label_b.upper(), "NSLA", "NSLA_V2"}:
            return self.label_b
        return "tie"


class IterationMetrics(BaseModel):
    """
    Metrics tracking for one iteration of the LLM ↔ Z3 refinement loop.

    At this stage we keep the structure simple and model only deltas and a flag
    for "best so far"; more detailed metrics can be added without breaking
    existing code as long as fields here remain backward compatible.
    """

    iteration: int
    f1_delta: float = 0.0
    bleu_delta: float = 0.0
    is_best: bool = False
    z3_status: Optional[str] = None


class IterationState(BaseModel):
    """
    Full state snapshot for one iteration in the NSLA v2 iterative loop.

    It packages together:
    - the LLMOutputV2 proposed at this iteration
    - the LogicFeedback returned by the solver / analyzer
    - the IterationMetrics associated with this step
    """

    iteration: int
    llm_output: LLMOutputV2
    feedback: LogicFeedback
    metrics: IterationMetrics


class NSLAIterativeConfig(BaseModel):
    """
    Configuration for the Phase 3 iterative loop.

    This is intentionally minimal and mirrors the usage in pipeline_v2 / llm_client:
    - max_iters: hard cap on the number of LLM↔Z3 iterations
    - eps: small threshold used to detect "no improvement"
    - stop_on_status: list of Z3 status values that should stop the loop early
    """

    max_iters: int = 3
    eps: float = 0.01
    stop_on_status: List[Literal["consistent_entails", "inconsistent"]] = [
        "consistent_entails",
        "inconsistent",
    ]


class IterationHistory(BaseModel):
    """
    Container for the full history of an iterative NSLA v2 run.

    This is what llm_client imports as IterationHistory.  It keeps:
    - optional case_id (for logging / analytics)
    - the config used for this run
    - the ordered list of IterationState objects
    """

    case_id: Optional[str] = None
    config: Optional[NSLAIterativeConfig] = None
    iterations: List[IterationState] = []

    def best_iteration(self) -> Optional[IterationState]:
        """
        Return the best iteration according to the metrics, if any.

        Preference order:
        - first iteration marked as metrics.is_best = True
        - otherwise, the last iteration in the history
        """
        if not self.iterations:
            return None
        for it in self.iterations:
            if it.metrics.is_best:
                return it
        return self.iterations[-1]


class Phase2RunResult(BaseModel):
    """
    Aggregated result for Phase 2 pipeline execution.

    Includes the refined LLM output, final feedback, guardrail assessment,
    explanation, and optional fallback data when the guardrail blocks the v2 program.
    """

    final_output: LLMOutputV2
    feedback_v2: LogicFeedback
    guardrail: GuardrailResult
    explanation: ExplanationOutput
    fallback_used: bool = False
    fallback_feedback: Optional[LogicFeedback] = None
    canonicalization: Optional[CanonicalizerOutput] = None
    logic_program_v1: Optional[LogicProgram] = None
    feedback_v1: Optional[LogicFeedback] = None
    answer_v1: Optional[str] = None
    judge_result: Optional[JudgeLLMResult] = None
    structured_stats: Optional[Dict[str, Any]] = None
    llm_status: Optional[Dict[str, Any]] = None


__all__ = [
    "CanonicalizerConcept",
    "CanonicalizerUnmappedTerm",
    "CanonicalizerOutput",
    "LLMOutputV2",
    "GuardrailIssue",
    "GuardrailResult",
    "ExplanationOutput",
    "JudgeLLMResult",
    "IterationMetrics",
    "IterationState",
    "NSLAIterativeConfig",
    "IterationHistory",
    "Phase2RunResult",
]
