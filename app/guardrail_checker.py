"""
Guardrail / static checker for NSLA v2 logic programs (Phase 2.4).

The guardrail validates the structure of the logic program before it is sent to
the translator/Z3.  Checks implemented:
    - DSL version compatibility
    - Predicate definitions aligned with the canonical DSL (arity + sorts)
    - Rule/query parsing using the DSL21Parser in strict mode

If any violation is detected, the guardrail returns a GuardrailResult with
the list of issues; upstream components can decide whether to fallback to v1
or retry.
"""

from __future__ import annotations

from typing import Dict, List

from .models import LogicProgram
from .models_v2 import GuardrailIssue, GuardrailResult
from .logic_dsl import (
    DSL_VERSION as CANONICAL_DSL_VERSION,
    PREDICATES,
    SORTS,
)
from .translator import (
    DSL21Parser,
    UnknownPredicateError,
    InvalidArityError,
    DSLParseError,
)
from .ontology_utils import (
    get_predicate_signature,
    resolve_predicate_alias,
    resolve_sort_alias,
)


def _build_issue(code: str, message: str, details: dict | None = None) -> GuardrailIssue:
    return GuardrailIssue(code=code, message=message, details=details)


def run_guardrail(logic_program: LogicProgram) -> GuardrailResult:
    """
    Execute Phase 2.4 guardrail checks.

    Args:
        logic_program: LogicProgram instance (dsl_version 2.1) to validate.

    Returns:
        GuardrailResult with ok flag and issue list.
    """

    issues: List[GuardrailIssue] = []

    if logic_program.dsl_version != CANONICAL_DSL_VERSION:
        issues.append(
            _build_issue(
                "DSL_VERSION_MISMATCH",
                f"dsl_version '{logic_program.dsl_version}' is not supported. "
                f"Expected '{CANONICAL_DSL_VERSION}'.",
                {"actual": logic_program.dsl_version, "expected": CANONICAL_DSL_VERSION},
            )
        )

    parser = DSL21Parser(allow_auto_declare=False)

    canonical_sorts: Dict[str, dict] = {}
    for sort_name, sort_meta in (logic_program.sorts or {}).items():
        canonical_name = resolve_sort_alias(sort_name)
        canonical_sorts[canonical_name] = sort_meta
        if canonical_name not in SORTS:
            issues.append(
                _build_issue(
                    "UNKNOWN_SORT_DECLARATION",
                    f"Sort '{sort_name}' is not part of the canonical DSL.",
                    {"sort": sort_name},
                )
            )

    parser.load_sorts(canonical_sorts)

    for const_name, const_meta in (logic_program.constants or {}).items():
        sort_name = const_meta.get("sort")
        if not sort_name:
            continue
        canonical_sort = resolve_sort_alias(sort_name)
        if canonical_sort not in SORTS:
            issues.append(
                _build_issue(
                    "UNKNOWN_CONSTANT_SORT",
                    f"Constant '{const_name}' references unknown sort '{sort_name}'.",
                    {"constant": const_name, "sort": sort_name},
                )
            )

    # Validate predicate declarations against canonical DSL
    declared_predicates = logic_program.predicates or {}
    canonical_predicates: Dict[str, dict] = {}
    for pred_name, meta in declared_predicates.items():
        canonical_name = resolve_predicate_alias(pred_name)
        spec = PREDICATES.get(canonical_name)
        if not spec:
            issues.append(
                _build_issue(
                    "UNKNOWN_PREDICATE_DECLARATION",
                    f"Predicate '{pred_name}' is not part of the canonical DSL.",
                    {"predicate": pred_name},
                )
            )
            continue

        expected_arity = len(spec.args)
        actual_arity = int(meta.get("arity", expected_arity))
        if expected_arity != actual_arity:
            issues.append(
                _build_issue(
                    "PREDICATE_ARITY_MISMATCH",
                    f"Predicate '{canonical_name}' arity mismatch (expected {expected_arity}, got {actual_arity}).",
                    {"predicate": canonical_name, "expected": expected_arity, "actual": actual_arity},
                )
            )
            actual_arity = expected_arity

        sorts = meta.get("sorts") or list(spec.args)
        canonical_sorts_meta = []
        for idx, sort_name in enumerate(sorts):
            canonical_sort = resolve_sort_alias(sort_name)
            canonical_sorts_meta.append(canonical_sort)
            if canonical_sort not in SORTS:
                issues.append(
                    _build_issue(
                        "PREDICATE_SORT_UNKNOWN",
                        f"Predicate '{canonical_name}' references unknown sort '{sort_name}'.",
                        {"predicate": canonical_name, "sort": sort_name},
                    )
                )
        if len(canonical_sorts_meta) != actual_arity:
            signature = get_predicate_signature(canonical_name)
            if signature:
                canonical_sorts_meta = signature[1]
            else:
                canonical_sorts_meta = canonical_sorts_meta[:actual_arity]

        canonical_predicates[canonical_name] = {
            "arity": actual_arity,
            "sorts": canonical_sorts_meta,
        }

    # Let the parser perform structural validation (arity + syntax)
    try:
        parser.parse_predicates(canonical_predicates)
    except InvalidArityError as exc:
        issues.append(
            _build_issue(
                "INVALID_ARITY",
                str(exc),
                {"context": "parse_predicates"},
            )
        )

    try:
        parser.parse_rules(logic_program.rules or [])
    except UnknownPredicateError as exc:
        issues.append(
            _build_issue(
                "RULE_UNKNOWN_PREDICATE",
                str(exc),
                {"context": "parse_rules"},
            )
        )
    except DSLParseError as exc:
        issues.append(
            _build_issue(
                "RULE_PARSE_ERROR",
                str(exc),
                {"context": "parse_rules"},
            )
        )

    if logic_program.query:
        try:
            parser._parse_expression(str(logic_program.query), strict=True)  # type: ignore[attr-defined]
        except (UnknownPredicateError, DSLParseError) as exc:
            issues.append(
                _build_issue(
                    "QUERY_PARSE_ERROR",
                    str(exc),
                    {"context": "parse_query"},
                )
            )

    ok = len(issues) == 0
    return GuardrailResult(ok=ok, issues=issues)


__all__ = ["run_guardrail"]

