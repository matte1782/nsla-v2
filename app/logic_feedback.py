from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

try:
    from z3 import Solver, Bool, Not, BoolRef, sat, unsat, unknown
except ImportError as exc:
    raise ImportError("z3-solver is required. Install it in your virtualenv.") from exc

logger = logging.getLogger(__name__)


@dataclass
class LogicFeedback:
    status: str  # "consistent_entails" | "consistent_no_entailment" | "inconsistent"
    conflicting_axioms: List[str]
    missing_links: List[str]
    human_summary: str


# -----------------------------
# Public helpers required by tests
# -----------------------------
LOGICAL_KEYWORDS: Set[str] = {"and", "or", "not", "implies", "true", "false"}


def _extract_predicate_names_from_text(text: str) -> List[str]:
    """
    Extract predicate symbols mentioned inside a logical expression string.
    Supports both infix ("Pred(a) and Q(b)") and prefix ("(and Pred(a) Q(b))") styles.
    """
    if not isinstance(text, str) or not text.strip():
        return []

    raw = text.strip()
    atoms_in_order: List[str] = []
    seen: Set[str] = set()

    # First pass: grab every identifier immediately preceding '('
    for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", raw):
        atom = match.group(1)
        if atom.lower() in LOGICAL_KEYWORDS:
            continue
        if atom not in seen:
            seen.add(atom)
            atoms_in_order.append(atom)

    if atoms_in_order:
        return atoms_in_order

    # Fallback: very simple split-based heuristics (legacy DSL v1)
    parts = re.split(r"\band\b|\bAND\b", raw)
    for tok in parts:
        t = tok.strip()
        if not t:
            continue
        if t.startswith("(") and t.endswith(")"):
            t = t[1:-1].strip()
        if t.lower().startswith("not "):
            t = t[4:].strip()
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", t)
        if not m:
            continue
        atom = m.group(0)
        if atom.lower() in LOGICAL_KEYWORDS:
            continue
        if atom not in seen:
            seen.add(atom)
            atoms_in_order.append(atom)

    return atoms_in_order


def _normalize_atom_text(text: str) -> str:
    """
    Normalize atoms like "Predicato(a, b)" into "Predicato(a,b)" for stable comparisons.
    """
    if not isinstance(text, str):
        return ""
    atom = text.strip()
    if not atom:
        return ""
    if atom.lower().startswith("not "):
        atom = atom[4:].strip()
    if "(" not in atom or not atom.endswith(")"):
        return atom
    name, args_str = atom.split("(", 1)
    name = name.strip()
    args_body = args_str[:-1]  # remove trailing ')'
    args = [arg.strip() for arg in args_body.split(",") if arg.strip()]
    joined = ",".join(args)
    return f"{name}({joined})" if joined else name


def _collect_predicates_from_program(logic_program: Any) -> Set[str]:
    """
    Collect predicate symbols from:
      - logic_program.predicates keys (v2.1)
      - rule 'condition' and 'conclusion' strings (extracting atoms)
      - v1 axioms (optional; only if present)
    Returns a set of unique names.
    """
    names: Set[str] = set()

    # v2.1 declared predicates
    preds = getattr(logic_program, "predicates", None) or {}
    for k in preds.keys():
        if isinstance(k, str) and k.strip():
            names.add(k.strip())

    # v2.1 rules: conditions + conclusions
    rules = getattr(logic_program, "rules", None) or []
    for r in rules:
        if not isinstance(r, dict):
            continue

        # condition atoms
        cond = str(r.get("condition", "")).strip()
        if cond:
            names.update(_extract_predicate_names_from_text(cond))

        # conclusion: allow "not X" → normalize to "X"
        concl = str(r.get("conclusion", "")).strip()
        if concl:
            if concl.lower().startswith("not "):
                concl = concl[4:].strip()
            # take first identifier token if present
            toks = _extract_predicate_names_from_text(concl)
            if toks:
                names.add(toks[0])

    # v1 axioms (if present)
    axioms = getattr(logic_program, "axioms", None) or []
    for ax in axioms:
        if not isinstance(ax, dict):
            continue
        formula = str(ax.get("formula", "")).strip()
        if formula:
            names.update(_extract_predicate_names_from_text(formula))

    return names


# -----------------------------
# Internal entailment helpers
# -----------------------------

def _solver_entails(solver: Solver, proposition: BoolRef) -> bool:
    """Entailment: solver ⊨ P  iff  solver ∧ ¬P is UNSAT."""
    solver.push()
    try:
        solver.add(Not(proposition))
        return solver.check() == unsat
    finally:
        solver.pop()


def _atom_entails(solver: Solver, atom_name: str) -> bool:
    """Entailment check for a simple Bool atom by name."""
    return _solver_entails(solver, Bool(atom_name))


def _extract_query_name(query: Optional[BoolRef], logic_program: Any) -> Optional[str]:
    """Safely get a stable string name for the query."""
    if query is not None:
        try:
            return _normalize_atom_text(str(query))
        except Exception:
            pass
    q = getattr(logic_program, "query", None)
    if isinstance(q, str):
        normalized = _normalize_atom_text(q)
        return normalized or None
    if isinstance(q, dict):
        name = str(q.get("pred") or "").strip()
        args = q.get("args") or []
        clean_args = [str(arg).strip() for arg in args if str(arg).strip()]
        raw = f"{name}({','.join(clean_args)})" if name else ""
        normalized = _normalize_atom_text(raw)
        return normalized or None
    return None


def _rules_concluding(logic_program: Any, conclusion_name: str) -> List[Dict[str, Any]]:
    """Collect rules whose 'conclusion' matches the given name (trimmed, exact after normalizing 'not ')."""
    rules = getattr(logic_program, "rules", []) or []
    out: List[Dict[str, Any]] = []
    normalized_target = _normalize_atom_text(conclusion_name)
    target_pred = normalized_target.split("(", 1)[0] if normalized_target else ""
    for r in rules:
        if not isinstance(r, dict):
            continue
        concl = _normalize_atom_text(str(r.get("conclusion", "")))
        concl_pred = concl.split("(", 1)[0] if concl else ""
        if concl == normalized_target or (target_pred and concl_pred == target_pred):
            out.append(r)
    return out


def _compute_missing_links_for_query(solver: Solver, logic_program: Any, q_name: str) -> List[str]:
    """
    Missing links logic:
      - If no rule concludes q_name  => [q_name]
      - Else collect AND-atoms from each rule.condition concluding q_name,
        and include those not entailed by the current solver knowledge.
      - Deduplicate; never include q_name itself.
    """
    query_expr = getattr(logic_program, "query", None)
    target_atom = _normalize_atom_text(query_expr) or q_name
    target_pred = (_normalize_atom_text(target_atom) or "").split("(", 1)[0]
    concl_rules = _rules_concluding(logic_program, target_atom)
    if not concl_rules:
        normalized = _normalize_atom_text(target_atom)
        predicate_only = normalized.split("(", 1)[0] if normalized else normalized
        return [predicate_only or q_name]

    missing: List[str] = []
    for r in concl_rules:
        cond = str(r.get("condition", "")).strip()
        if not cond:
            # empty condition rule => nothing to add
            continue
        atoms = _extract_predicate_names_from_text(cond)
        for atom in atoms:
            try:
                if not _atom_entails(solver, atom):
                    missing.append(atom)
            except Exception:
                # be conservative: treat as missing if entailment check fails
                missing.append(atom)

    # de-dup, drop the conclusion itself if present
    seen: Set[str] = set()
    dedup: List[str] = []
    for m in missing:
        normalized = _normalize_atom_text(m)
        if normalized == _normalize_atom_text(target_atom):
            continue
        if target_pred and normalized.split("(", 1)[0] == target_pred:
            continue
        key = normalized or m
        if key not in seen:
            seen.add(key)
            dedup.append(key)
    return dedup


# -----------------------------
# Compatibility wrapper expected by tests
# -----------------------------

def _compute_missing_links(solver: Solver, logic_program: Any, q_name: str) -> List[str]:
    """
    Compatibility wrapper expected by tests.
    Delegates to the internal implementation that computes the list of missing
    premises (or the query atom itself when no rule concludes it).
    """
    return _compute_missing_links_for_query(solver, logic_program, q_name)


# -----------------------------
# Primary API
# -----------------------------

def build_logic_feedback(
    solver: Solver,
    logic_program: Any,
    query: Optional[BoolRef] = None
) -> LogicFeedback:
    """
    Evaluate solver state and return structured feedback:
      - inconsistent: UNSAT
      - consistent_entails: SAT and entails(query)
      - consistent_no_entailment: SAT and not entails(query), or no query provided
    """
    res = solver.check()

    if res == unsat:
        # Inconsistency: produce non-empty conflicting_axioms (heuristic)
        conflicting: List[str] = []
        try:
            for i, _ in enumerate(solver.assertions()):
                conflicting.append(f"assertion_{i}")
        except Exception:
            pass
        if not conflicting:
            rules = getattr(logic_program, "rules", []) or []
            for i, _ in enumerate(rules):
                conflicting.append(f"rule_{i}")
        if not conflicting:
            conflicting = ["conflict_0"]

        return LogicFeedback(
            status="inconsistent",
            conflicting_axioms=conflicting,
            missing_links=[],
            human_summary="Sono presenti assiomi contraddittori."
        )

    # Treat UNKNOWN as SAT-like, proceed with entailment checks
    if res not in (sat, unknown):
        logger.warning("Unexpected solver result; treating as SAT-like.")

    q_name = _extract_query_name(query, logic_program)

    # No query provided: coherent, no conclusion requested
    if not q_name:
        return LogicFeedback(
            status="consistent_no_entailment",
            conflicting_axioms=[],
            missing_links=[],
            human_summary="Il sistema è coerente ma non è stata richiesta alcuna conclusione."
        )

    # Entailment of the query name
    try:
        entailed = _solver_entails(solver, Bool(q_name))
    except Exception:
        entailed = False

    if entailed:
        return LogicFeedback(
            status="consistent_entails",
            conflicting_axioms=[],
            missing_links=[],
            human_summary="Il sistema è coerente e implica la conclusione."
        )

    # Not entailed: compute missing links
    missing_links = _compute_missing_links_for_query(solver, logic_program, q_name)
    return LogicFeedback(
        status="consistent_no_entailment",
        conflicting_axioms=[],
        missing_links=missing_links,
        human_summary="Il sistema è coerente ma la conclusione non è dimostrabile."
    )


__all__ = [
    "LogicFeedback",
    "build_logic_feedback",
    "_extract_predicate_names_from_text",
    "_collect_predicates_from_program",
    "_compute_missing_links",
]
