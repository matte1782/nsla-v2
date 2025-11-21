"""
Phase 2.2 – Structured Extractor runtime.

This module wraps ``LLMClient.call_structured_extractor`` adding:
- runtime fallbacks (reusing v1 logic program if available, otherwise dummy)
- enforcement of DSL version metadata
- lightweight telemetry (log counts of predicates/rules)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

from .models import LogicProgram, LLMOutput
from .models_v2 import CanonicalizerOutput
from .prompt_loader import get_prompt_loader
from .ontology_utils import (
    get_predicate_signature,
    resolve_predicate_alias,
    resolve_sort_alias,
    SORT_ALIAS_MAP,
    PREDICATE_ALIAS_MAP,
)
from .canonical_rule_utils import ensure_canonical_query_rule

logger = logging.getLogger(__name__)


class StructuredExtractorRuntime:
    LOGICAL_KEYWORDS = {
        "and",
        "or",
        "not",
        "implies",
        "=>",
        "exists",
        "forall",
        "true",
        "false",
        ">=",
        "<=",
        ">",
        "<",
        "=",
    }

    """
    Execute the ontology-guided structured extractor (Phase 2.2).

    Args:
        llm_client: Component exposing ``call_structured_extractor`` and (optionally)
            ``_build_dummy_logic_program`` for deterministic tests.
        enforce_dsl_version: If set, overrides the ``dsl_version`` returned by the
            LLM to guarantee translator compatibility.
    """

    def __init__(self, llm_client, enforce_dsl_version: str = "2.1") -> None:
        self.llm_client = llm_client
        self.enforce_dsl_version = enforce_dsl_version
        loader = get_prompt_loader()
        ontology = {}
        try:
            ontology = loader.load_yaml_file("legal_it_v1.yaml")
        except Exception:
            logger.warning("Unable to load ontology metadata for structured extractor", exc_info=True)
        self.canonical_sorts: Dict[str, Dict[str, Any]] = {}
        for name, spec in (ontology.get("sorts") or {}).items():
            if isinstance(spec, dict):
                data = dict(spec)
            else:
                data = {"type": spec} if isinstance(spec, str) else {}
            data.setdefault("type", "Entity")
            self.canonical_sorts[name] = data

        self.sort_aliases: Dict[str, str] = dict(SORT_ALIAS_MAP)

        self.ontology_predicates: Dict[str, Dict[str, Any]] = {}
        self.predicate_aliases: Dict[str, str] = dict(PREDICATE_ALIAS_MAP)
        for name, spec in (ontology.get("predicates") or {}).items():
            if not isinstance(spec, dict):
                continue
            arity = int(spec.get("arity", 0))
            sorts = spec.get("sorts")
            if isinstance(sorts, list) and len(sorts) == arity:
                normalized = [str(s) for s in sorts]
            else:
                normalized = ["Entity"] * arity
            synonyms = []
            if isinstance(spec.get("synonyms"), list):
                synonyms = [
                    str(entry).strip()
                    for entry in spec.get("synonyms")
                    if str(entry).strip()
                ]
            self.ontology_predicates[name] = {
                "arity": arity,
                "sorts": normalized,
                "synonyms": synonyms,
            }
            self._register_predicate_alias(name, synonyms)

        self._last_stats: Dict[str, Any] = {}
        self._current_stats: Dict[str, Any] = {}

    def run(
        self,
        question: str,
        canonicalization: CanonicalizerOutput,
        *,
        fallback_program: Optional[LogicProgram] = None,
    ) -> LogicProgram:
        """
        Run the extractor and normalize the resulting ``LogicProgram``.

        Args:
            question: Original legal question.
            canonicalization: Output of Phase 2.1.
            fallback_program: Optional program to reuse if the extractor fails.

        Returns:
            LogicProgram ready for translator/Z3.
        """
        self._current_stats = {}

        try:
            program = self.llm_client.call_structured_extractor(
                question,
                canonicalization,
            )
            stats_func = getattr(self.llm_client, "pop_structured_stats", None)
            if callable(stats_func):
                self._current_stats.update(stats_func() or {})
            logger.info(
                "Structured extractor v2.2: DSL=%s, predicates=%d, rules=%d",
                program.dsl_version,
                len(program.predicates),
                len(program.rules),
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning(
                "Structured extractor failed (%s). Using fallback logic program.",
                exc,
                exc_info=True,
            )
            program = self._fallback_program(question, fallback_program)
            self._current_stats["fallback_used"] = True

        if self.enforce_dsl_version:
            program.dsl_version = self.enforce_dsl_version

        self._normalize_axioms_and_rules(program)
        self._hydrate_sorts(program)
        self._hydrate_predicates(program)
        self._canonicalize_formulas(program)
        ensure_canonical_query_rule(program)
        self._current_stats["predicates_total"] = len(program.predicates or {})
        self._current_stats["rules_total"] = len(program.rules or [])
        self._last_stats = dict(self._current_stats)
        if self._last_stats:
            logger.info("Structured extractor stats: %s", self._last_stats)
        self._current_stats = {}
        return program

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _fallback_program(
        self,
        question: str,
        fallback_program: Optional[LogicProgram],
    ) -> LogicProgram:
        if fallback_program is not None:
            return fallback_program

        builder = getattr(self.llm_client, "_build_dummy_logic_program", None)
        if callable(builder):
            return builder(question)

        # Worst-case fallback: empty LogicProgram
        logger.debug("Structured extractor fallback: empty LogicProgram generated.")
        return LogicProgram()

    def _normalize_axioms_and_rules(self, program: LogicProgram) -> None:
        if not isinstance(program.sorts, dict):
            program.sorts = {}
        if not isinstance(program.constants, dict):
            program.constants = {}
        if not isinstance(program.predicates, dict):
            program.predicates = {}
        if not isinstance(program.axioms, list):
            program.axioms = []
        if not isinstance(program.rules, list):
            program.rules = []
        if not isinstance(getattr(program, "facts", {}), dict):
            program.facts = {}
        program.axioms = program.axioms or []
        normalized_axioms = []
        for entry in program.axioms:
            if isinstance(entry, str):
                formula = self._sanitize_expression(entry)
                if formula:
                    normalized_axioms.append({"formula": formula})
                self._increment_stat("axiom_strings_wrapped")
                continue
            if not isinstance(entry, dict):
                continue
            formula = self._sanitize_expression(entry.get("formula"))
            if formula:
                normalized_axioms.append({"formula": formula})
                continue
            condition = self._sanitize_expression(entry.get("condition"))
            conclusion = self._sanitize_expression(entry.get("conclusion"))
            if conclusion:
                if not condition or condition.lower() in {"true", "vero", "1"}:
                    normalized_axioms.append({"formula": conclusion})
                else:
                    normalized_axioms.append({"formula": f"{condition} -> {conclusion}"})
                self._increment_stat("axiom_condition_wrapped")
                continue
            if entry.get("pred"):
                formula = self._format_atom(entry.get("pred"), entry.get("args"))
                normalized_axioms.append({"formula": formula})
                self._increment_stat("axiom_atoms_wrapped")
        program.axioms = normalized_axioms

        program.rules = program.rules or []
        normalized_rules = []
        for entry in program.rules:
            if not isinstance(entry, dict):
                continue
            condition = self._sanitize_expression(entry.get("condition") or "true")
            if not condition:
                condition = "true"
            conclusion = self._sanitize_expression(entry.get("conclusion"))
            if not conclusion and entry.get("pred"):
                conclusion = self._format_atom(entry.get("pred"), entry.get("args"))
                self._increment_stat("rule_atoms_wrapped")
            if conclusion:
                normalized_rules.append(
                    {
                        "condition": condition,
                        "conclusion": conclusion,
                        "id": entry.get("id"),
                    }
                )
        program.rules = normalized_rules

        facts = getattr(program, "facts", {}) or {}
        normalized_facts = {}
        for name, rows in facts.items():
            if isinstance(rows, list) and rows and all(isinstance(item, str) for item in rows):
                normalized_facts[name] = [[item] for item in rows]
                self._increment_stat("fact_rows_normalized", len(rows))
            else:
                normalized_facts[name] = rows
        program.facts = normalized_facts

    def _format_atom(self, predicate: Any, args: Any) -> str:
        name = str(predicate).strip()
        arg_list = []
        if isinstance(args, list):
            arg_list = [str(arg).strip() for arg in args if str(arg).strip()]
        joined = ", ".join(arg_list)
        return f"{name}({joined})" if joined else f"{name}()"

    # ------------------------------------------------------------------ #
    # Ontology helpers
    # ------------------------------------------------------------------ #
    def _hydrate_sorts(self, program: LogicProgram) -> None:
        """
        Ensure that all sorts referenced by predicates/constants have canonical
        metadata so the translator does not fall back to BoolSort.
        """
        program.sorts = program.sorts or {}
        normalized_sorts: Dict[str, Dict[str, Any]] = {}
        for name, spec in program.sorts.items():
            canonical_name = self._resolve_sort_alias(name)
            normalized_sorts[canonical_name] = self._coerce_sort_def(
                canonical_name, spec
            )

        program.sorts = normalized_sorts

        program.constants = program.constants or {}
        normalized_constants: Dict[str, Dict[str, Any]] = {}
        for const_name, const_def in program.constants.items():
            if isinstance(const_def, dict):
                data = dict(const_def)
            elif isinstance(const_def, str):
                data = {"sort": const_def}
                self._increment_stat("constant_strings_normalized")
            else:
                data = {}
            if "sort" in data:
                data["sort"] = self._resolve_sort_alias(data["sort"])
            normalized_constants[const_name] = data
        program.constants = normalized_constants

        # Ensure sorts for predicate arguments
        for pred_def in (program.predicates or {}).values():
            sorts = pred_def.get("sorts") or []
            for sort_name in sorts:
                sort_name = self._resolve_sort_alias(sort_name)
                if sort_name not in program.sorts:
                    program.sorts[sort_name] = self._coerce_sort_def(
                        sort_name, self.canonical_sorts.get(sort_name)
                    )

        # Ensure sorts for constants
        for const_def in (program.constants or {}).values():
            sort_name = const_def.get("sort")
            if sort_name and sort_name not in program.sorts:
                program.sorts[sort_name] = self._coerce_sort_def(
                    sort_name, self.canonical_sorts.get(sort_name)
                )

    def _hydrate_predicates(self, program: LogicProgram) -> None:
        raw_predicates = program.predicates or {}
        predicates: Dict[str, Dict[str, Any]] = {}
        for name, spec in raw_predicates.items():
            normalized_name = str(name or "").strip()
            if not normalized_name or normalized_name.lower() in self.LOGICAL_KEYWORDS:
                self._increment_stat("logical_predicates_removed")
                continue
            predicates[normalized_name] = spec

        normalized: Dict[str, Dict[str, Any]] = {}
        for name, spec in predicates.items():
            canonical_name = self._resolve_predicate_alias(name)
            canonical_key = canonical_name or name
            if not canonical_key:
                continue
            if canonical_key.lower() in self.LOGICAL_KEYWORDS:
                self._increment_stat("logical_predicates_removed")
                continue

            data = dict(spec) if isinstance(spec, dict) else {}
            canonical_meta = self._get_canonical_predicate_meta(canonical_key)

            if canonical_meta:
                data["arity"] = canonical_meta["arity"]
                data["sorts"] = [
                    self._resolve_sort_alias(s) for s in canonical_meta["sorts"]
                ]
            else:
                arity = int(data.get("arity", 0))
                sorts = data.get("sorts") or []
                if arity and len(sorts) != arity:
                    data["sorts"] = ["Entity"] * arity
                    self._increment_stat("predicate_unknown_sorts")
                else:
                    data["sorts"] = [self._resolve_sort_alias(s) for s in sorts]
                data["arity"] = arity or len(data["sorts"])

            existing = normalized.get(canonical_key, {})
            normalized[canonical_key] = {**existing, **data}

        program.predicates = normalized
        # Ensure predicates referenced in rules/query/axioms are declared
        missing_predicates = self._collect_predicate_candidates(program)
        for name in missing_predicates:
            canonical_name = self._resolve_predicate_alias(name) or name
            if not canonical_name:
                continue
            if canonical_name.lower() in self.LOGICAL_KEYWORDS:
                continue
            if canonical_name in program.predicates:
                continue
            ont_entry = self._get_canonical_predicate_meta(canonical_name)
            if ont_entry:
                program.predicates[canonical_name] = {
                    "arity": ont_entry["arity"],
                    "sorts": [self._resolve_sort_alias(s) for s in ont_entry["sorts"]],
                }
                self._increment_stat("auto_declared_predicates")
            else:
                program.predicates[canonical_name] = {
                    "arity": 0,
                    "sorts": [],
                }

    def _coerce_sort_def(self, name: str, spec: Any) -> Dict[str, Any]:
        if isinstance(spec, dict):
            data = dict(spec)
        elif isinstance(spec, str):
            data = {"type": spec}
        else:
            data = {}
        if not data.get("type"):
            canonical = self.canonical_sorts.get(name, {})
            data["type"] = canonical.get("type", "Entity")
        return data

    def _resolve_sort_alias(self, name: Optional[str]) -> str:
        canonical = resolve_sort_alias(name)
        key = (str(name).strip() if name else "Entity")
        if canonical != key:
            self._increment_stat("sort_alias_hits")
        return canonical

    def _register_predicate_alias(
        self, canonical: str, synonyms: Optional[List[str]] = None
    ) -> None:
        canonical_key = str(canonical or "").strip()
        if not canonical_key:
            return
        self.predicate_aliases[canonical_key.lower()] = canonical_key
        for synonym in synonyms or []:
            syn_key = str(synonym).strip().lower()
            if syn_key:
                self.predicate_aliases[syn_key] = canonical_key

    def _resolve_predicate_alias(self, name: Optional[str]) -> str:
        canonical = resolve_predicate_alias(name)
        key = str(name).strip() if name else ""
        if canonical and canonical != key:
            self._increment_stat("predicate_alias_hits")
        return canonical

    def _get_canonical_predicate_meta(self, name: str) -> Optional[Dict[str, Any]]:
        entry = self.ontology_predicates.get(name)
        if entry:
            return entry
        signature = get_predicate_signature(name)
        if not signature:
            return None
        arity, sorts = signature
        return {"arity": arity, "sorts": sorts}

    def _collect_predicate_candidates(self, program: LogicProgram) -> Set[str]:
        """
        Scan rules/axioms/query to find predicates that need declarations.
        """

        candidates: Set[str] = set()

        def extract(expr: Optional[str]):
            if not isinstance(expr, str):
                return
            for token in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", expr):
                key = token.strip()
                if key.lower().startswith("not "):
                    key = key[4:].strip()
                if key.lower() in self.LOGICAL_KEYWORDS:
                    continue
                canonical = self._resolve_predicate_alias(key)
                candidates.add(canonical or key)

        for rule in program.rules or []:
            extract(rule.get("condition"))
            extract(rule.get("conclusion"))

        for axiom in program.axioms or []:
            extract(axiom.get("formula"))
            extract(axiom.get("condition"))
            extract(axiom.get("conclusion"))

        extract(program.query if isinstance(program.query, str) else None)

        return candidates

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
            "⇒": " -> ",
            "→": " -> ",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = self._desugar_comparisons(text)
        text = re.sub(r"\s+", " ", text).strip()
        return self._canonicalize_expression(text)

    def _desugar_comparisons(self, expr: str) -> str:
        patterns = [
            re.compile(
                r"\(\s*(>=|<=|>|<)\s*\(\s*(?P<pred>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<args>[^()]+?)\)\s*(?P<rhs>[^\s()]+)?\s*\)",
                re.DOTALL,
            ),
            re.compile(
                r"\(\s*(>=|<=|>|<)\s*(?P<pred>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<args>[^()]+?)\)\s*(?P<rhs>[^\s()]+)?\s*\)",
                re.DOTALL,
            ),
        ]

        def repl(match: re.Match[str]) -> str:
            pred = match.group("pred")
            args_part = match.group("args") or ""
            args = [
                tok.strip(",")
                for tok in re.split(r"[,\s]+", args_part)
                if tok.strip(",")
            ]
            joined = ", ".join(args)
            return f"{pred}({joined})" if joined else pred

        for pattern in patterns:
            expr = pattern.sub(repl, expr)

        infix_pattern = re.compile(
            r"(?P<pred>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<args>[^()]+?)\)\s*(>=|<=|>|<|=)\s*(?P<rhs>[A-Za-z0-9_\.\-]+)",
            re.DOTALL,
        )

        def infix_repl(match: re.Match[str]) -> str:
            pred = match.group("pred")
            raw_args = match.group("args") or ""
            args = [
                token.strip()
                for token in re.split(r"\s*,\s*", raw_args)
                if token.strip()
            ]
            joined = ", ".join(args)
            return f"{pred}({joined})" if joined else pred

        expr = infix_pattern.sub(infix_repl, expr)
        return expr

    def _canonicalize_expression(self, expr: str) -> str:
        def repl(match: re.Match[str]) -> str:
            token = match.group(1)
            canonical = self._resolve_predicate_alias(token) or token
            return canonical + match.group(2)

        return re.sub(r"([A-Za-z_][A-Za-z0-9_]*)(\s*\()", repl, expr)

    def _canonicalize_formulas(self, program: LogicProgram) -> None:
        def rewrite(value: Optional[str]) -> Optional[str]:
            if not isinstance(value, str):
                return value
            return self._canonicalize_expression(value)

        for axiom in program.axioms or []:
            if isinstance(axiom, dict) and "formula" in axiom:
                axiom["formula"] = rewrite(axiom.get("formula"))
        for rule in program.rules or []:
            if isinstance(rule, dict):
                rule["condition"] = rewrite(rule.get("condition")) or "true"
                rule["conclusion"] = rewrite(rule.get("conclusion"))
        if isinstance(program.query, str):
            program.query = rewrite(program.query)

    def _increment_stat(self, key: str, amount: int = 1) -> None:
        if not hasattr(self, "_current_stats"):
            self._current_stats = {}
        self._current_stats[key] = self._current_stats.get(key, 0) + amount

    def get_last_stats(self) -> Dict[str, Any]:
        return dict(self._last_stats)


def ensure_logic_program(value: LLMOutput | LogicProgram) -> LogicProgram:
    """
    Utility used by callers to guarantee a LogicProgram instance.
    """
    if isinstance(value, LogicProgram):
        return value

    if hasattr(value, "logic_program"):
        return LogicProgram(**value.logic_program)

    raise TypeError(
        "ensure_logic_program expects LogicProgram or LLMOutput with logic_program"
    )


__all__ = ["StructuredExtractorRuntime", "ensure_logic_program"]

