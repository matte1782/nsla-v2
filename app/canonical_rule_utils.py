from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import logging

from .logic_dsl import SORTS
from .models import LogicProgram

logger = logging.getLogger(__name__)


def ensure_canonical_query_rule(program: LogicProgram) -> None:
    """
    Guarantee that the query predicate has at least one derivation rule.

    If the LLM omitted the final rule, we synthesize a canonical one so the
    guardrail/translator always see a derivable target predicate.
    """
    atom = _extract_query_atom(program.query)
    if not atom:
        return

    raw_query, predicate, args = atom
    builder = _CANONICAL_RULE_BUILDERS.get(predicate)
    if not builder:
        return

    program.rules = list(program.rules or [])
    if _has_rule_for_query(program.rules, raw_query):
        return

    rule = builder(program, args)
    if not rule:
        return
    rule["conclusion"] = raw_query or rule.get("conclusion") or _build_conclusion(predicate, args)

    program.rules.append(rule)
    logger.info("Injected canonical rule for query '%s'", raw_query)


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #


def _build_rule_contratto_valido(program: LogicProgram, args: List[str]) -> Optional[Dict[str, str]]:
    if len(args) != 2:
        return None
    condition = (
        f"(and Consenso({args[0]}, {args[1]}) "
        f"CapacitaContrattuale({args[0]}) "
        f"CausaLegittima({args[1]}) "
        f"OggettoDeterminato({args[1]}) "
        f"FormaPrescritta({args[1]}))"
    )
    conclusion = _build_conclusion("ContrattoValido", args)
    return {"condition": condition, "conclusion": conclusion}


def _build_rule_responsabilita_contrattuale(
    program: LogicProgram, args: List[str]
) -> Optional[Dict[str, str]]:
    if len(args) != 3:
        return None
    condition = (
        f"(and HaObbligo({args[0]}, {args[1]}, {args[2]}) "
        f"Inadempimento({args[0]}, {args[2]}) "
        f"DannoPatrimoniale({args[1]}) "
        f"Imputabilita({args[0]}, {args[2]}))"
    )
    conclusion = _build_conclusion("ResponsabilitaContrattuale", args)
    return {"condition": condition, "conclusion": conclusion}


def _build_rule_contratto_adesione(program: LogicProgram, args: List[str]) -> Optional[Dict[str, str]]:
    if len(args) != 1:
        return None
    contratto = args[0]
    professionista = _ensure_constant(program, f"{contratto}_professionista", "Professionista")
    consumatore = _ensure_constant(program, f"{contratto}_consumatore", "Consumatore")
    condition = (
        f"(and PredeterminatoDa({contratto}, {professionista}) "
        f"NonNegoziabileDa({contratto}, {consumatore}) "
        f"PuoSoloAccettareOppureRifiutare({consumatore}, {contratto}))"
    )
    conclusion = _build_conclusion("ContrattoAdesione", args)
    return {"condition": condition, "conclusion": conclusion}


def _build_rule_usucapione_ordinaria(program: LogicProgram, args: List[str]) -> Optional[Dict[str, str]]:
    if len(args) != 2:
        return None
    condition = (
        f"(and PossessoContinuato({args[0]}, {args[1]}) "
        f"PossessoPubblico({args[0]}, {args[1]}) "
        f"BuonaFede({args[0]}))"
    )
    conclusion = _build_conclusion("UsucapioneOrdinaria", args)
    return {"condition": condition, "conclusion": conclusion}


def _build_rule_usucapione_abbreviata(program: LogicProgram, args: List[str]) -> Optional[Dict[str, str]]:
    if len(args) != 2:
        return None
    titolo = _ensure_constant(program, f"titolo_{args[1]}", "Titolo")
    condition = (
        f"(and PossessoContinuato({args[0]}, {args[1]}) "
        f"PossessoPubblico({args[0]}, {args[1]}) "
        f"BuonaFede({args[0]}) "
        f"TitoloIdoneo({titolo}, {args[1]}))"
    )
    conclusion = _build_conclusion("UsucapioneAbbreviata", args)
    return {"condition": condition, "conclusion": conclusion}


_CANONICAL_RULE_BUILDERS = {
    "ContrattoValido": _build_rule_contratto_valido,
    "ResponsabilitaContrattuale": _build_rule_responsabilita_contrattuale,
    "ContrattoAdesione": _build_rule_contratto_adesione,
    "UsucapioneOrdinaria": _build_rule_usucapione_ordinaria,
    "UsucapioneAbbreviata": _build_rule_usucapione_abbreviata,
}


# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #


def _extract_query_atom(query: object) -> Optional[Tuple[str, str, List[str]]]:
    if isinstance(query, dict):
        name = str(query.get("pred") or "").strip()
        args = query.get("args") or []
        args_list = [str(arg).strip() for arg in args if str(arg).strip()]
        if not name:
            return None
        raw = f"{name}({', '.join(args_list)})" if args_list else name
        return raw, name, args_list

    if not isinstance(query, str):
        return None
    text = query.strip()
    if not text:
        return None

    if "(" not in text or not text.endswith(")"):
        return text, text, []

    name, args_str = text.split("(", 1)
    name = name.strip()
    args_body = args_str[:-1]  # remove trailing ")"
    args = [arg.strip() for arg in args_body.split(",") if arg.strip()]
    return text, name, args


def _has_rule_for_query(rules: List[Dict[str, str]], target_conclusion: str) -> bool:
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if (rule.get("conclusion") or "").strip() == target_conclusion:
            return True
    return False


def _build_conclusion(predicate: str, args: List[str]) -> str:
    if args:
        params = ", ".join(args)
        return f"{predicate}({params})"
    return f"{predicate}()"


def _ensure_constant(program: LogicProgram, base_name: str, sort_name: str) -> str:
    program.constants = dict(program.constants or {})
    program.sorts = dict(program.sorts or {})

    for name, meta in program.constants.items():
        if _resolve_sort(meta.get("sort")) == sort_name:
            return name

    candidate = base_name
    idx = 1
    while candidate in program.constants:
        idx += 1
        candidate = f"{base_name}_{idx}"

    program.constants[candidate] = {"sort": sort_name}
    _ensure_sort_definition(program, sort_name)
    return candidate


def _ensure_sort_definition(program: LogicProgram, sort_name: str) -> None:
    if sort_name in (program.sorts or {}):
        return
    program.sorts = dict(program.sorts or {})
    spec = SORTS.get(sort_name)
    if spec and spec.extends:
        program.sorts[sort_name] = {"type": spec.extends}
    else:
        program.sorts[sort_name] = {"type": "Entity"}


def _resolve_sort(sort_name: Optional[str]) -> Optional[str]:
    if not sort_name:
        return None
    key = str(sort_name).strip()
    return key or None


__all__ = ["ensure_canonical_query_rule"]


