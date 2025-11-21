import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .canonicalizer_runtime import CanonicalizerRuntime
from .explanation_synthesizer import synthesize_explanation
from .guardrail_checker import run_guardrail
from .iteration_manager import IterationManager
from .logic_feedback import LogicFeedback, build_logic_feedback
from .models import LLMOutput, LogicProgram
from .models_v2 import (
    LLMOutputV2,
    IterationMetrics,
    IterationState,
    NSLAIterativeConfig,
    Phase2RunResult,
    JudgeLLMResult,
)
from .refinement_runtime import RefinementRuntime
from .structured_extractor import StructuredExtractorRuntime, ensure_logic_program
from .translator import (
    build_solver,
    UnknownPredicateError,
    DSLParseError,
    InvalidArityError,
    TypeMismatchError,
)
from .judge_runtime import JudgeRuntime
from .canonical_rule_utils import ensure_canonical_query_rule
from .ontology_utils import resolve_predicate_alias, resolve_sort_alias, get_predicate_signature


logger = logging.getLogger(__name__)


class NSLAPipelineV2:
    FACT_SYNTHESIS_MAX_ROUNDS = 3

    def __init__(
        self,
        llm_client,
        config: Optional[NSLAIterativeConfig] = None,
        canonicalizer_runtime: Optional[CanonicalizerRuntime] = None,
        structured_extractor: Optional[StructuredExtractorRuntime] = None,
        refinement_runtime: Optional[RefinementRuntime] = None,
        iteration_manager: Optional[IterationManager] = None,
        judge_runtime: Optional[JudgeRuntime] = None,
    ) -> None:
        """
        NSLA v2 pipeline controller.

        llm_client must implement at least:
          - call_canonicalizer(question: str) -> CanonicalizerOutput
          - call_structured_extractor(question: str, canonicalization: CanonicalizerOutput) -> LogicProgram
          - call_refinement_llm(question: str, logic_program_v1: LogicProgram, feedback_v1: LogicFeedback) -> Dict[str, Any]
          - (for iterative mode) call_primary_llm(question: str) -> Dict[str, Any]  # LLMOutputV2-like
        """
        self.llm_client = llm_client
        self.config = config or NSLAIterativeConfig()
        self.canonicalizer = canonicalizer_runtime or CanonicalizerRuntime(llm_client)
        self.structured_extractor = structured_extractor or StructuredExtractorRuntime(
            llm_client
        )
        self.refinement_runtime = refinement_runtime or RefinementRuntime(llm_client)
        self._iteration_manager = iteration_manager
        self.judge_runtime = judge_runtime
        self._last_llm_status: Dict[str, Any] = {}

    def run_once(self, question: str, reference_answer: Optional[str] = None) -> Phase2RunResult:
        """
        Phase 2 one-shot pipeline execution.

        Steps:
        - Phase 2.1: Canonicalizer (LLM)
        - Phase 2.2: Structured Extractor → logic_program_v1 (LLM)
        - Translator + Z3: build solver + feedback_v1
        - Phase 2.3: Refinement LLM → LLMOutputV2 (logic_program_v2 + final_answer)
        - Translator + Z3 again: build feedback_v2
        """
        context = self._prepare_phase2_context(question)
        iter_llm_status = dict(context.get("llm_status") or {})
        iter_llm_status = dict(context.get("llm_status") or {})
        iter_llm_status = dict(context.get("llm_status") or {})

        logic_program_v1 = context["logic_program_v1"]
        feedback_v1 = context["feedback_v1"]
        canonicalization = context["canonicalization"]
        llm_status = dict(context.get("llm_status") or {})

        # Phase 2.3: Refinement LLM → LLMOutputV2 (contains dict for logic_program and final_answer)
        llm_output_v2 = self.refinement_runtime.run(
            question=question,
            current_program=logic_program_v1,
            current_feedback=feedback_v1,
            previous_answer=context["answer_v1"],
        )
        llm_status_update = self.llm_client.pop_llm_statuses()
        if llm_status_update:
            llm_status.update(llm_status_update)

        # Convert logic_program dict to LogicProgram model
        logic_program_v2 = LogicProgram(**llm_output_v2.logic_program)
        self._sanitize_logic_program(logic_program_v2)
        self._hydrate_logic_program(logic_program_v2)
        ensure_canonical_query_rule(logic_program_v2)
        llm_output_v2.logic_program = logic_program_v2.model_dump()

        # Phase 2.4: Guardrail checker
        guardrail = run_guardrail(logic_program_v2)

        if not guardrail.ok:
            result = self._build_guardrail_failure_result(
                question=question,
                reference_answer=reference_answer,
                llm_output=llm_output_v2,
                logic_program_v1=logic_program_v1,
                feedback_v1=feedback_v1,
                canonicalization=canonicalization,
                llm_status=llm_status,
                guardrail=guardrail,
                answer_v1=context["answer_v1"],
                structured_stats=context.get("structured_stats"),
            )
            self._last_llm_status = dict(llm_status)
            return result

        feedback_v2 = self._evaluate_with_fact_synthesis(logic_program_v2)
        llm_output_v2.logic_program = logic_program_v2.model_dump()
        guardrail = run_guardrail(logic_program_v2)
        if not guardrail.ok:
            result = self._build_guardrail_failure_result(
                question=question,
                reference_answer=reference_answer,
                llm_output=llm_output_v2,
                logic_program_v1=logic_program_v1,
                feedback_v1=feedback_v1,
                canonicalization=canonicalization,
                llm_status=llm_status,
                guardrail=guardrail,
                answer_v1=context["answer_v1"],
                structured_stats=context.get("structured_stats"),
            )
            self._last_llm_status = dict(llm_status)
            return result

        highlight_preds = self._collect_fact_predicates(logic_program_v2)
        llm_output_v2.final_answer = self._augment_final_answer(
            llm_output_v2.final_answer,
            highlight_preds,
        )

        # Phase 2.5: Explanation
        explanation = synthesize_explanation(
            question,
            llm_output_v2.final_answer,
            feedback_v2,
            guardrail,
        )

        result = Phase2RunResult(
            final_output=llm_output_v2,
            feedback_v2=feedback_v2,
            guardrail=guardrail,
            explanation=explanation,
            canonicalization=canonicalization,
            logic_program_v1=logic_program_v1,
            feedback_v1=feedback_v1,
            answer_v1=context["answer_v1"],
            structured_stats=context.get("structured_stats"),
            llm_status=llm_status,
        )
        result.judge_result = self._maybe_run_judge(
            question=question,
            reference_answer=reference_answer,
            baseline_answer=context["answer_v1"],
            candidate_answer=llm_output_v2.final_answer,
            guardrail_ok=True,
        )
        self._last_llm_status = dict(llm_status)
        return result

    def run_iterative(self, question: str) -> Tuple[IterationState, List[IterationState]]:
        """
        Iterative loop as per v2 design.

        High-level idea:
        - Iter 0: primary LLM call → LLMOutputV2_0 + LogicFeedback_0
        - Iter k>0: refinement LLM over previous logic_program + feedback
        - At each step run Z3 and store IterationState
        - Stop when:
            - status in config.stop_on_status, or
            - k+1 >= max_iters
        - Select best_state with a simple heuristic.
        """
        context = self._prepare_phase2_context(question)
        iter_llm_status = dict(context.get("llm_status") or {})

        if not context.get("v1_solver_ready", True):
            logger.warning(
                "Skipping iterative pipeline for question '%s' due to invalid v1 program",
                question,
            )
            fallback_output = LLMOutputV2(
                final_answer=context["answer_v1"],
                logic_program=context["logic_program_v1"].model_dump(),
            )
            metrics = IterationMetrics(
                iteration=0,
                f1_delta=0.0,
                bleu_delta=0.0,
                is_best=True,
                z3_status="invalid_logic_program",
            )
            best_state = IterationState(
                iteration=0,
                llm_output=fallback_output,
                feedback=context["feedback_v1"],
                metrics=metrics,
            )
            history = [best_state]
            self._last_llm_status = dict(iter_llm_status)
            return best_state, history

        if self._iteration_manager is None:
            self._iteration_manager = IterationManager(
                refinement_runtime=self.refinement_runtime,
                config=self.config,
                program_sanitizer=self._sanitize_logic_program,
                program_hydrator=self._hydrate_logic_program,
                feedback_postprocessor=self._iteration_feedback_postprocessor,
            )
        manager = self._iteration_manager

        best_state, history = manager.run(
            question=question,
            initial_program=context["logic_program_v1"],
            initial_feedback=context["feedback_v1"],
            initial_answer=context["answer_v1"],
        )
        status_update = self.llm_client.pop_llm_statuses()
        if status_update:
            iter_llm_status.update(status_update)
        self._last_llm_status = dict(iter_llm_status)

        return best_state, history

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _prepare_phase2_context(self, question: str) -> Dict[str, Any]:
        """
        Shared preparation logic between run_once and run_iterative.
        """
        canonicalization = self.canonicalizer.run(question)
        baseline_output: LLMOutput = self.llm_client.ask_llm_structured(question)

        fallback_program = ensure_logic_program(baseline_output.logic_program)
        self._sanitize_logic_program(fallback_program)
        self._hydrate_logic_program(fallback_program)
        ensure_canonical_query_rule(fallback_program)
        logic_program_v1 = self.structured_extractor.run(
            question,
            canonicalization,
            fallback_program=fallback_program,
            )
        self._sanitize_logic_program(logic_program_v1)
        self._hydrate_logic_program(logic_program_v1)
        ensure_canonical_query_rule(logic_program_v1)

        llm_status = self.llm_client.pop_llm_statuses() or {}
        v1_solver_ready = True
        feedback_v1: LogicFeedback

        try:
            feedback_v1 = self._evaluate_with_fact_synthesis(logic_program_v1)
        except (
            UnknownPredicateError,
            DSLParseError,
            InvalidArityError,
            TypeMismatchError,
            ValueError,
        ) as exc:
            v1_solver_ready = False
            logger.warning(
                "Phase2 context: unable to build solver for question '%s': %s",
                question,
                exc,
            )
            llm_status["translator_v1"] = f"error:{exc.__class__.__name__}"
            feedback_v1 = LogicFeedback(
                status="invalid_logic_program",
                conflicting_axioms=[],
                missing_links=[],
                human_summary=(
                    "Impossibile costruire il solver per il programma v1: "
                    f"{exc}"
                ),
            )

        return {
            "canonicalization": canonicalization,
            "logic_program_v1": logic_program_v1,
            "feedback_v1": feedback_v1,
            "answer_v1": baseline_output.final_answer,
            "structured_stats": self.structured_extractor.get_last_stats(),
            "v1_solver_ready": v1_solver_ready,
            "llm_status": llm_status,
        }

    def _maybe_run_judge(
        self,
        *,
        question: str,
        reference_answer: Optional[str],
        baseline_answer: str,
        candidate_answer: str,
        guardrail_ok: bool,
    ) -> Optional[JudgeLLMResult]:
        if (
            not reference_answer
            or not self.judge_runtime
            or not guardrail_ok
        ):
            return None

        return self.judge_runtime.evaluate(
            question=question,
            reference_answer=reference_answer,
            answer_a=baseline_answer,
            answer_b=candidate_answer,
            label_a="baseline_v1",
            label_b="nsla_v2",
        )

    def _build_guardrail_failure_result(
        self,
        *,
        question: str,
        reference_answer: Optional[str],
        llm_output: LLMOutputV2,
        logic_program_v1: LogicProgram,
        feedback_v1: LogicFeedback,
        canonicalization: Any,
        llm_status: Dict[str, Any],
        guardrail: Any,
        answer_v1: str,
        structured_stats: Optional[Dict[str, Any]],
    ) -> Phase2RunResult:
        solver_fallback, query_fallback = build_solver(logic_program_v1, facts={})
        fallback_feedback = build_logic_feedback(
            solver_fallback, logic_program_v1, query_fallback
        )
        explanation = synthesize_explanation(
            question,
            llm_output.final_answer,
            fallback_feedback,
            guardrail,
        )
        result = Phase2RunResult(
            final_output=llm_output,
            feedback_v2=fallback_feedback,
            guardrail=guardrail,
            explanation=explanation,
            fallback_used=True,
            fallback_feedback=fallback_feedback,
            canonicalization=canonicalization,
            logic_program_v1=logic_program_v1,
            feedback_v1=feedback_v1,
            answer_v1=answer_v1,
            structured_stats=structured_stats,
            llm_status=llm_status,
        )
        result.judge_result = self._maybe_run_judge(
            question=question,
            reference_answer=reference_answer,
            baseline_answer=answer_v1,
            candidate_answer=llm_output.final_answer,
            guardrail_ok=False,
        )
        return result

    # ------------------------------------------------------------------ #
    # Fact synthesis + answer helpers
    # ------------------------------------------------------------------ #
    def _evaluate_with_fact_synthesis(self, program: LogicProgram) -> LogicFeedback:
        attempts = 0
        while True:
            solver, query = build_solver(program, facts={})
            feedback = build_logic_feedback(solver, program, query)
            if (
                not feedback.missing_links
                or feedback.status != "consistent_no_entailment"
                or attempts >= self.FACT_SYNTHESIS_MAX_ROUNDS
            ):
                return feedback
            added = self._synthesize_missing_facts(program, feedback.missing_links)
            if not added:
                return feedback
            attempts += 1

    def _synthesize_missing_facts(
        self,
        program: LogicProgram,
        missing_links: List[str],
    ) -> bool:
        if not missing_links:
            return False

        program.axioms = list(program.axioms or [])
        program.constants = dict(program.constants or {})
        predicates = program.predicates or {}
        existing_formulas: Set[str] = {
            str(entry.get("formula")).strip()
            for entry in program.axioms
            if isinstance(entry, dict) and entry.get("formula")
        }

        added = False
        for raw_name in missing_links:
            canonical = resolve_predicate_alias(raw_name) or raw_name
            spec = predicates.get(canonical)
            if not spec:
                continue
            sorts = spec.get("sorts") or []
            args: List[str] = []
            for idx, sort_name in enumerate(sorts):
                const_name = self._ensure_constant_for_sort(
                    program, sort_name or "Entity", idx
                )
                args.append(const_name)
            if args:
                formula = f"{canonical}({', '.join(args)})"
            else:
                formula = canonical
            if formula in existing_formulas:
                continue
            program.axioms.append({"formula": formula})
            existing_formulas.add(formula)
            added = True
            logger.info("Fact synthesis: injected %s", formula)
        return added

    def _coerce_numeric_literals(self, program: LogicProgram) -> None:
        predicates = program.predicates or {}
        if not predicates:
            return

        atom_pattern = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^()]+)\)")

        def normalize(text: Optional[str]) -> Optional[str]:
            if not isinstance(text, str) or "(" not in text:
                return text

            def repl(match: re.Match[str]) -> str:
                name = match.group(1)
                args_blob = match.group(2) or ""
                meta = predicates.get(resolve_predicate_alias(name) or name)
                if not meta:
                    return match.group(0)
                sorts = meta.get("sorts") or []
                args = [
                    token.strip()
                    for token in re.split(r"\s*,\s*", args_blob)
                    if token.strip()
                ]
                changed = False
                new_args: List[str] = []
                for idx, arg in enumerate(args):
                    if idx >= len(sorts):
                        new_args.append(arg)
                        continue
                    if self._looks_numeric_literal(arg):
                        placeholder = self._ensure_constant_for_sort(
                            program, sorts[idx], idx
                        )
                        new_args.append(placeholder)
                        changed = True
                    else:
                        new_args.append(arg)
                if not changed:
                    return match.group(0)
                return f"{name}({', '.join(new_args)})"

            return atom_pattern.sub(repl, text)

        for axiom in program.axioms or []:
            if isinstance(axiom, dict) and "formula" in axiom:
                axiom["formula"] = normalize(axiom.get("formula")) or axiom.get("formula")

        for rule in program.rules or []:
            if isinstance(rule, dict):
                rule["condition"] = normalize(rule.get("condition")) or rule.get("condition")
                rule["conclusion"] = normalize(rule.get("conclusion")) or rule.get("conclusion")

        if isinstance(program.query, str):
            program.query = normalize(program.query) or program.query

    def _ensure_declared_predicates(self, program: LogicProgram) -> None:
        declared = dict(program.predicates or {})
        collector = getattr(self.structured_extractor, "_collect_predicate_candidates", None)
        if callable(collector):
            candidates = collector(program)
        else:
            candidates = self._collect_predicate_candidates_fallback(program)

        for raw_name in candidates:
            canonical = resolve_predicate_alias(raw_name) or raw_name
            key = (canonical or "").strip()
            if not key:
                continue
            if key.lower() in StructuredExtractorRuntime.LOGICAL_KEYWORDS:
                continue
            if key in declared:
                continue
            signature = get_predicate_signature(key)
            if signature:
                arity, sorts = signature
                declared[key] = {
                    "arity": arity,
                    "sorts": [resolve_sort_alias(sort) for sort in sorts],
                }
            else:
                declared[key] = {"arity": 0, "sorts": []}

        program.predicates = declared

    @staticmethod
    def _collect_predicate_candidates_fallback(program: LogicProgram) -> Set[str]:
        pattern = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")
        keywords = StructuredExtractorRuntime.LOGICAL_KEYWORDS
        found: Set[str] = set()

        def harvest(text: Optional[str]) -> None:
            if not isinstance(text, str):
                return
            for token in pattern.findall(text):
                lower = token.lower()
                if lower in keywords:
                    continue
                canonical = resolve_predicate_alias(token) or token
                if canonical:
                    found.add(canonical)

        for axiom in program.axioms or []:
            if isinstance(axiom, dict):
                harvest(axiom.get("formula"))
                harvest(axiom.get("condition"))
                harvest(axiom.get("conclusion"))
            else:
                harvest(str(axiom))

        for rule in program.rules or []:
            if isinstance(rule, dict):
                harvest(rule.get("condition"))
                harvest(rule.get("conclusion"))
            else:
                harvest(str(rule))

        harvest(program.query if isinstance(program.query, str) else None)
        return found

    @staticmethod
    def _looks_numeric_literal(value: str) -> bool:
        return bool(re.fullmatch(r"[+-]?\d+(\.\d+)?", value or ""))

    def _ensure_constant_for_sort(
        self,
        program: LogicProgram,
        sort_name: Optional[str],
        position: int,
    ) -> str:
        target_sort = resolve_sort_alias(sort_name) or (sort_name or "Entity")
        for const_name, const_spec in program.constants.items():
            if isinstance(const_spec, dict) and const_spec.get("sort") == target_sort:
                return const_name
        base = target_sort.lower()
        suffix = position + 1
        candidate = f"{base}_{suffix}"
        while candidate in program.constants:
            suffix += 1
            candidate = f"{base}_{suffix}"
        program.constants[candidate] = {"sort": target_sort}
        return candidate

    @staticmethod
    def _augment_final_answer(answer: str, predicates: List[str]) -> str:
        unique = [p for p in dict.fromkeys(predicates) if p]
        if not unique:
            return answer
        summary = "Requisiti simbolici soddisfatti: " + ", ".join(unique) + "."
        normalized_answer = answer or ""
        if summary.lower() in normalized_answer.lower():
            return normalized_answer
        separator = "\n\n" if normalized_answer.strip() else ""
        return f"{normalized_answer}{separator}{summary}"

    def _collect_fact_predicates(self, program: LogicProgram) -> List[str]:
        keywords = {
            "and",
            "or",
            "not",
            "implies",
            "true",
            "false",
        }
        pattern = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")
        names: List[str] = []

        def harvest(text: Optional[str]) -> None:
            if not isinstance(text, str):
                return
            for token in pattern.findall(text):
                lower = token.lower()
                if lower in keywords:
                    continue
                canonical = resolve_predicate_alias(token) or token
                names.append(canonical)

        for axiom in program.axioms or []:
            if isinstance(axiom, dict):
                harvest(axiom.get("formula"))
            else:
                harvest(str(axiom))

        for rule in program.rules or []:
            if isinstance(rule, dict):
                harvest(rule.get("condition"))
                harvest(rule.get("conclusion"))
            else:
                harvest(str(rule))

        harvest(program.query if isinstance(program.query, str) else None)

        ordered: List[str] = []
        seen: Set[str] = set()
        for name in names:
            if name and name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

    def _iteration_feedback_postprocessor(
        self, program: LogicProgram, feedback: LogicFeedback
    ) -> LogicFeedback:
        if (
            not feedback.missing_links
            or feedback.status != "consistent_no_entailment"
        ):
            return feedback
        try:
            return self._evaluate_with_fact_synthesis(program)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Iteration feedback post-processing failed: %s",
                exc,
                exc_info=True,
            )
            return feedback

    def get_last_llm_status(self) -> Dict[str, Any]:
        return dict(self._last_llm_status)

    # ------------------------------------------------------------------ #
    # Sanitization helpers
    # ------------------------------------------------------------------ #
    def _sanitize_logic_program(self, program: LogicProgram) -> None:
        program.axioms = list(program.axioms or [])
        sanitized_axioms = []
        for entry in program.axioms:
            if isinstance(entry, str):
                formula = self._sanitize_expression(entry)
                if formula:
                    sanitized_axioms.append({"formula": formula})
                continue
            if not isinstance(entry, dict):
                continue
            formula = self._sanitize_expression(entry.get("formula"))
            if not formula:
                condition = self._sanitize_expression(entry.get("condition"))
                conclusion = self._sanitize_expression(entry.get("conclusion"))
                if conclusion:
                    formula = conclusion if not condition or condition.lower() in {"true", "vero", "1"} else f"{condition} -> {conclusion}"
            if formula:
                sanitized_axioms.append({"formula": formula})
        program.axioms = sanitized_axioms

        program.rules = list(program.rules or [])
        sanitized_rules = []
        for entry in program.rules:
            if not isinstance(entry, dict):
                continue
            condition = self._sanitize_expression(entry.get("condition")) or "true"
            conclusion = self._sanitize_expression(entry.get("conclusion"))
            if not conclusion:
                continue
            sanitized_rules.append(
                {
                    "condition": condition,
                    "conclusion": conclusion,
                    "id": entry.get("id"),
                }
            )
        program.rules = sanitized_rules

        query = getattr(program, "query", None)
        if isinstance(query, dict):
            name = str(query.get("pred") or "").strip()
            args = query.get("args") or []
            clean_args = [str(arg).strip() for arg in args if str(arg).strip()]
            if name:
                joined = ",".join(clean_args)
                program.query = f"{name}({joined})" if joined else name
            else:
                program.query = None

    def _hydrate_logic_program(self, program: LogicProgram) -> None:
        hydrate_sorts = getattr(self.structured_extractor, "_hydrate_sorts", None)
        if callable(hydrate_sorts):
            hydrate_sorts(program)
        hydrate_predicates = getattr(self.structured_extractor, "_hydrate_predicates", None)
        if callable(hydrate_predicates):
            hydrate_predicates(program)
        self._coerce_numeric_literals(program)
        self._ensure_declared_predicates(program)

    def _sanitize_expression(self, expr: Optional[str]) -> str:
        if expr is None:
            return ""
        text = str(expr).strip()
        if not text:
            return ""
        replacements = {
            "∨": " or ",
            "∧": " and ",
            "¬": " not ",
            "→": " -> ",
            "⇒": " -> ",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = " ".join(text.split())
        return self._strip_comparisons(text)

    @staticmethod
    def _strip_comparisons(expr: str) -> str:
        if not expr:
            return ""

        def _normalize_args(args_blob: str) -> str:
            tokens = [
                tok.strip()
                for tok in re.split(r"\s*,\s*", args_blob)
                if tok.strip()
            ]
            return ", ".join(tokens)

        prefix_patterns = [
            re.compile(
                r"\(\s*(>=|<=|>|<|=)\s*\(\s*(?P<pred>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<args>[^()]+?)\)\s*(?P<rhs>[^\s()]+)?\s*\)",
                re.DOTALL,
            ),
            re.compile(
                r"\(\s*(>=|<=|>|<|=)\s*(?P<pred>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<args>[^()]+?)\)\s*(?P<rhs>[^\s()]+)?\s*\)",
                re.DOTALL,
            ),
        ]

        def prefix_repl(match: re.Match[str]) -> str:
            pred = match.group("pred")
            args = _normalize_args(match.group("args") or "")
            return f"{pred}({args})" if args else pred

        for pattern in prefix_patterns:
            expr = pattern.sub(prefix_repl, expr)

        infix_pattern = re.compile(
            r"(?P<pred>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<args>[^()]+?)\)\s*(>=|<=|>|<|=)\s*(?P<rhs>[A-Za-z0-9_\.\-]+)",
            re.DOTALL,
        )

        def infix_repl(match: re.Match[str]) -> str:
            pred = match.group("pred")
            args = _normalize_args(match.group("args") or "")
            return f"{pred}({args})" if args else pred

        return infix_pattern.sub(infix_repl, expr)