# app/translator.py
# NOTE: This project requires the following packages for full functionality:
#   - z3-solver: for Z3 integration
#   - pydantic: for data models
#   - fastapi: for the web framework
#   - jinja2: for Jinja2Templates in app.main
#   - httpx: for fastapi.testclient in tests
# =============================================================================

import logging
import json
import re
from typing import Dict, Any, List, Tuple, Optional, Union

try:
    from z3 import (
        Solver, Bool, BoolVal, And, Or, Not, Implies, BoolRef,
        Int, Real, String, Datatype, Function, ForAll, Exists,
        sat, unsat, unknown, IntSort, RealSort, StringSort, BoolSort, Const
    )
except ImportError as exc:
    raise ImportError(
        "La libreria 'z3-solver' non è installata correttamente. "
        "Esegui 'pip install z3-solver' nel virtualenv nsla-mvp-env."
    ) from exc

from .models import LogicProgram
from .ontology_utils import (
    get_predicate_signature,
    resolve_predicate_alias,
    resolve_sort_alias,
)

logger = logging.getLogger(__name__)


# Custom exceptions for structured error handling
class InvalidArityError(Exception):
    """Raised when predicate arity doesn't match expected signature."""
    pass


class UnknownPredicateError(Exception):
    """Raised when trying to use an undefined predicate."""
    pass


class TypeMismatchError(Exception):
    """Raised when type checking fails between expected and actual types."""
    pass


class DSLParseError(Exception):
    """Base exception for DSL parsing errors."""
    pass


# =============================================================================
# DSL v1 Parser (backward compatibility)
# =============================================================================

def _parse_atom(name: str) -> Bool:
    """Crea un predicato booleano (BoolRef) dal nome dell'atomo."""
    return Bool(name)


def _parse_formula(formula: str, atoms_cache: Dict[str, Bool]) -> BoolRef:
    """
    Parser minimale per formule booleane nel DSL v1.

    Sintassi supportata:
    - Letterali: P, Q, RespCivile (vengono convertiti in Bool)
    - Negazione: not A, ¬A
    - Congiunzione: A and B
    - Disgiunzione: A or B  
    - Implicazione: A -> B
    
    Esempio: "P and (Q -> R)" viene parsato correttamente.
    """
    formula = formula.strip()
    
    # Gestione implicazione
    if "->" in formula:
        parts = formula.split("->", 1)
        left = _parse_formula(parts[0].strip(), atoms_cache)
        right = _parse_formula(parts[1].strip(), atoms_cache)
        return Implies(left, right)
    
    # Gestione congiunzione/disgiunzione
    if " and " in formula:
        parts = [p.strip() for p in formula.split(" and ")]
        if len(parts) > 1:
            sub_formulas = [_parse_formula(p, atoms_cache) for p in parts]
            return And(*sub_formulas)
    
    if " or " in formula:
        parts = [p.strip() for p in formula.split(" or ")]
        if len(parts) > 1:
            sub_formulas = [_parse_formula(p, atoms_cache) for p in parts]
            return Or(*sub_formulas)
    
    # Gestione negazione
    if formula.startswith("not ") or formula.startswith("¬"):
        atom = formula[4:].strip() if formula.startswith("not ") else formula[1:].strip()
        sub = _parse_formula(atom, atoms_cache)
        return Not(sub)
    
    # Gestione parentesi
    if formula.startswith("(") and formula.endswith(")"):
        return _parse_formula(formula[1:-1], atoms_cache)
    
    # Letterale semplice
    atom_name = formula
    if atom_name not in atoms_cache:
        atoms_cache[atom_name] = _parse_atom(atom_name)
    return atoms_cache[atom_name]


def _add_axioms_to_solver_v1(
    solver: Solver, 
    axioms: List[Dict[str, str]], 
    atoms_cache: Dict[str, Bool]
) -> None:
    """Aggiunge gli assiomi come vincoli al solver Z3 (DSL v1 compatibility)."""
    for axiom in axioms:
        if "formula" not in axiom:
            logger.warning(f"Axiom missing formula: {axiom}")
            continue
        
        formula_str = axiom["formula"]
        try:
            parsed_formula = _parse_formula(formula_str, atoms_cache)
            solver.add(parsed_formula)
            logger.debug(f"Added axiom: {formula_str}")
        except Exception as e:
            raise ValueError(f"Errore nel parsing dell'assioma '{formula_str}': {e}")


# =============================================================================
# DSL v2.1 Parser and Z3 Mapper
# =============================================================================

class Z3TypeMapper:
    """Handles mapping between DSL types and Z3 sorts."""
    
    def __init__(self):
        self.type_cache = {}
        self.entity_sorts = {}
        
    def map_sort(self, sort_name: str, sort_def: Dict[str, Any]) -> Any:
        """
        Map a DSL sort to appropriate Z3 sort.
        
        Args:
            sort_name: Name of the sort
            sort_def: Sort definition from DSL
            
        Returns:
            Z3 sort (BoolSort, IntSort, RealSort, StringSort, or Datatype)
        """
        if sort_name in self.type_cache:
            return self.type_cache[sort_name]
            
        sort_type = sort_def.get("type", "Bool")
        
        if sort_type == "Bool":
            z3_sort = BoolSort()
        elif sort_type == "Int":
            z3_sort = IntSort()
        elif sort_type == "Float":
            z3_sort = RealSort()
        elif sort_type == "String":
            z3_sort = StringSort()
        elif sort_type == "Entity":
            # Create datatype for entity
            values = sort_def.get("values", [])
            if values:
                # Create enum datatype
                dt = Datatype(f"{sort_name}_type")
                for value in values:
                    dt.declare(value)
                z3_sort = dt.create()
                self.entity_sorts[sort_name] = z3_sort
                # Cache both the original name and the type name for test compatibility
                self.type_cache[sort_name] = z3_sort
                self.type_cache[f"{sort_name}_type"] = z3_sort
                return z3_sort
            else:
                # Generic entity sort
                z3_sort = StringSort()  # Fallback
        else:
            logger.warning(f"Unknown sort type '{sort_type}', using BoolSort")
            z3_sort = BoolSort()
            
        self.type_cache[sort_name] = z3_sort
        return z3_sort
    
    def create_constant(self, name: str, sort_name: str, sort_def: Dict[str, Any]) -> Any:
        """Create a Z3 constant with the appropriate sort."""
        z3_sort = self.map_sort(sort_name, sort_def)
        
        if z3_sort == BoolSort():
            return Bool(name)
        elif z3_sort == IntSort():
            return Int(name)
        elif z3_sort == RealSort():
            return Real(name)
        elif z3_sort == StringSort():
            return String(name)
        else:
            # For entity datatypes, create a constructor function
            if hasattr(z3_sort, 'constructor'):
                return z3_sort.constructor(name)
            return String(name)  # Fallback


class DSL21Parser:
    """Parser for DSL v2.1 format."""
    
    def __init__(self, allow_auto_declare: bool = True):
        self.type_mapper = Z3TypeMapper()
        self.predicates = {}
        self.functions = {}
        self.variables = {}
        self.sort_definitions: Dict[str, Dict[str, Any]] = {}
        self.allow_auto_declare = allow_auto_declare

    def load_sorts(self, sorts: Dict[str, Any]) -> None:
        """
        Register sort definitions coming from the LogicProgram so that predicate
        signatures can reference canonical metadata (e.g. Entity vs Bool).
        """
        self.sort_definitions = {}
        if not sorts:
            return
        for name, sort_def in sorts.items():
            if isinstance(sort_def, dict):
                normalized = dict(sort_def)
            else:
                normalized = {"type": sort_def} if isinstance(sort_def, str) else {}
            normalized.setdefault("type", "Entity")
            base_type = normalized.get("type", "Entity")
            if base_type not in {"Bool", "Int", "Float", "String", "Entity"}:
                normalized["type"] = "Entity"
            canonical_name = resolve_sort_alias(name)
            self.sort_definitions[canonical_name] = normalized
        
    def parse_predicates(self, predicates: Dict[str, Any]) -> None:
        """
        Parse and validate predicate definitions.
        
        Stores function declarations in self.predicates for later use.
        For arity 0 predicates, creates Function(name, BoolSort()) to ensure arity() is available.
        """
        for pred_name, pred_def in predicates.items():
            canonical_name = resolve_predicate_alias(pred_name)
            if isinstance(pred_def, dict):
                # Structured predicate definition
                arity = pred_def.get("arity", 0)
                sorts = pred_def.get("sorts", [])
                arity_declared = "arity" in pred_def
                sorts_declared = bool(sorts)
                signature = get_predicate_signature(canonical_name)
                if signature:
                    expected_arity, expected_sorts = signature
                    if not arity_declared:
                        arity = expected_arity
                    if (not sorts_declared and not arity_declared and len(expected_sorts) == expected_arity):
                        sorts = expected_sorts
                if len(sorts) != arity:
                    raise InvalidArityError(
                        f"Predicate '{canonical_name}' arity {arity} doesn't match sorts length {len(sorts)}"
                    )
                
                # Create Z3 function for predicate with proper arity
                if arity == 0:
                    # For arity 0, use Function to ensure arity() method is available
                    self.predicates[canonical_name] = Function(canonical_name, BoolSort())
                else:
                    # Map sort names to Z3 sorts
                    z3_sorts = []
                    for sort_name in sorts:
                        canonical_sort = resolve_sort_alias(sort_name)
                        sort_def = self.sort_definitions.get(canonical_sort, {"type": "Entity"})
                        z3_sort = self.type_mapper.map_sort(canonical_sort, sort_def)
                        z3_sorts.append(z3_sort)
                    
                    # Create function with appropriate signature
                    self.predicates[canonical_name] = Function(
                        canonical_name, *z3_sorts, BoolSort()
                    )
            else:
                # Simple predicate definition (boolean) - arity 0
                self.predicates[canonical_name] = Function(canonical_name, BoolSort())
    
    def parse_rules(self, rules: List[Dict[str, Any]]) -> List[BoolRef]:
        """
        Parse rules and convert to Z3 formulas.
        
        This method properly handles the simplified rule format:
        {"condition": "P", "conclusion": "Q"} -> Implies(Bool("P"), Bool("Q"))
        Also handles complex expressions in condition and conclusion.
        """
        z3_rules = []
        
        for rule in rules:
            if not isinstance(rule, dict):
                logger.warning(f"Invalid rule format (not a dict): {rule}")
                continue
                
            if "condition" in rule and "conclusion" in rule:
                # Structured rule: condition -> conclusion
                condition_expr = str(rule["condition"]).strip()
                conclusion_expr = str(rule["conclusion"]).strip()
                
                # Parse condition and conclusion with strict checking for unknown predicates
                condition_ref = self._parse_expression(condition_expr, strict=True)
                conclusion_ref = self._parse_expression(conclusion_expr, strict=True)
                
                # Create Implies constraint
                implies_formula = Implies(condition_ref, conclusion_ref)
                z3_rules.append(implies_formula)
                
            elif "definition" in rule:
                # Direct definition - parse as expression to handle "not A" correctly
                definition_expr = str(rule["definition"]).strip()
                definition_formula = self._parse_expression(definition_expr)
                z3_rules.append(definition_formula)
            else:
                logger.warning(f"Rule missing condition/conclusion or definition: {rule}")
                
        return z3_rules
    
    def _get_or_create_predicate(self, name: str, allow_undeclared: bool = False) -> BoolRef:
        """
        Helper method to get or create a boolean predicate.
        
        Args:
            name: Predicate name as string
            allow_undeclared: If False, raise UnknownPredicateError for undeclared predicates
            
        Returns:
            BoolRef for the predicate by calling the stored function declaration
        """
        name = resolve_predicate_alias(name.strip())
        
        if name in self.predicates:
            # Get the function declaration and call it with appropriate args
            func_decl = self.predicates[name]
            arity = func_decl.arity()
            if arity == 0:
                return func_decl()
            else:
                # For non-zero arity, create placeholder arguments
                args = [Bool(f"arg_{i}_{name}") for i in range(arity)]
                return func_decl(*args)
        else:
            if allow_undeclared:
                # Create a new function declaration for unknown predicates with arity 0
                new_func_decl = Function(name, BoolSort())
                self.predicates[name] = new_func_decl
                return new_func_decl()  # Call with 0 arguments for arity 0
            else:
                # Raise error for undeclared predicates
                raise UnknownPredicateError(f"Unknown predicate: {name}")
    
    def _parse_expression(self, expr: str, strict: bool = False) -> BoolRef:
        """Parse a logical expression string."""
        expr = expr.strip()

        if not expr:
            raise DSLParseError("Empty expression")

        lower_expr = expr.lower()

        # Handle operator-style calls without leading parenthesis e.g. not(A), and(A,B)
        if lower_expr.startswith("not(") and expr.endswith(")"):
            inner_expr = expr[len("not(") : -1].strip()
            if not inner_expr:
                raise DSLParseError("NOT requires exactly one argument")
            return Not(self._parse_expression(inner_expr, strict=strict))

        if lower_expr.startswith("and(") and expr.endswith(")"):
            inner_expr = expr[len("and(") : -1].strip()
            args = self._split_top_level(inner_expr)
            if len(args) == 1:
                return self._parse_expression(args[0], strict=strict)
            if len(args) < 2:
                raise DSLParseError("AND requires at least two arguments")
            return And(*[self._parse_expression(arg, strict=strict) for arg in args])

        if lower_expr.startswith("or(") and expr.endswith(")"):
            inner_expr = expr[len("or(") : -1].strip()
            args = self._split_top_level(inner_expr)
            if len(args) == 1:
                return self._parse_expression(args[0], strict=strict)
            if len(args) < 2:
                raise DSLParseError("OR requires at least two arguments")
            return Or(*[self._parse_expression(arg, strict=strict) for arg in args])

        if lower_expr.startswith("implies(") and expr.endswith(")"):
            inner_expr = expr[len("implies(") : -1].strip()
            args = self._split_top_level(inner_expr)
            if len(args) != 2:
                raise DSLParseError("IMPLIES requires exactly two arguments")
            return Implies(
                self._parse_expression(args[0], strict=strict),
                self._parse_expression(args[1], strict=strict),
            )

        # Handle S-expression style (prefix) expressions: (and ...), (Pred arg1 ...)
        if expr.startswith("(") and expr.endswith(")"):
            inner = expr[1:-1].strip()
            if not inner:
                raise DSLParseError("Empty parenthesized expression")

            parts = self._split_top_level(inner)
            if parts:
                head = parts[0]
                args = parts[1:]
                head_lower = head.lower()

                if head_lower == "and":
                    if len(args) == 1:
                        return self._parse_expression(args[0], strict=strict)
                    if len(args) < 2:
                        raise DSLParseError("AND requires at least two arguments")
                    return And(*[self._parse_expression(arg, strict=strict) for arg in args])

                if head_lower == "or":
                    if len(args) == 1:
                        return self._parse_expression(args[0], strict=strict)
                    if len(args) < 2:
                        raise DSLParseError("OR requires at least two arguments")
                    return Or(*[self._parse_expression(arg, strict=strict) for arg in args])

                if head_lower == "not":
                    if len(args) != 1:
                        raise DSLParseError("NOT requires exactly one argument")
                    return Not(self._parse_expression(args[0], strict=strict))

                if head_lower == "implies":
                    if len(args) != 2:
                        raise DSLParseError("IMPLIES requires exactly two arguments")
                    return Implies(
                        self._parse_expression(args[0], strict=strict),
                        self._parse_expression(args[1], strict=strict),
                    )

                if head_lower in {"forall", "exists"}:
                    return self._parse_quantified(expr, head_lower)

                # Treat `(Predicate arg1 arg2 ...)` as standard function call
                if args:
                    normalized = f"{head}({', '.join(args)})"
                else:
                    normalized = f"{head}()"
                return self._parse_function_call(normalized, strict=strict)

        # Handle quantified expressions
        if expr.startswith("forall"):
            return self._parse_quantified(expr, "forall")
        elif expr.startswith("exists"):
            return self._parse_quantified(expr, "exists")

        # Handle function/predicate applications (standard format)
        if "(" in expr and expr.endswith(")"):
            return self._parse_function_call(expr, strict=strict)

        # Handle logical operators (infix) or boolean literals / atoms
        return self._parse_logical_expression(expr, strict=strict)
    
    def _parse_quantified(self, expr: str, quantifier: str) -> BoolRef:
        """Parse quantified expressions (forall, exists)."""
        # Simplified parser - TODO: implement full quantified expression parsing
        # For now, treat quantified expressions as boolean variables
        var_name = f"{quantifier}_{hash(expr) % 1000}"
        return Bool(var_name)
    
    def _parse_function_call(self, expr: str, strict: bool = False) -> BoolRef:
        """Parse function or predicate application."""
        func_part = expr.strip()
        if not func_part.endswith(")"):
            raise DSLParseError(f"Invalid function call syntax: {expr}")
        
        func_body = func_part[:-1]
        parts = func_body.split("(", 1)
        if len(parts) != 2:
            raise DSLParseError(f"Invalid function call syntax: {expr}")
        
        func_name = resolve_predicate_alias(parts[0].strip())
        args_str = parts[1].strip()
        args = self._split_args(args_str)
        
        if func_name in self.predicates:
            predicate = self.predicates[func_name]
            arity = predicate.arity()
            if arity != len(args):
                logger.warning(
                    "Arity mismatch for predicate '%s' (expected %d, got %d). Adjusting automatically.",
                    func_name,
                    arity,
                    len(args),
                )
            if arity == 0:
                return predicate()
            else:
                args = []
                for i in range(arity):
                    domain_sort = predicate.domain(i)
                    args.append(Const(f"{func_name}_arg_{i}", domain_sort))
                return predicate(*args)
        else:
            if strict:
                if not self.allow_auto_declare:
                    raise UnknownPredicateError(f"Unknown predicate: {func_name}")
                predicate = self._auto_declare_predicate(func_name, len(args))
                if predicate.arity() == 0:
                    return predicate()
                placeholder_args = []
                for i in range(predicate.arity()):
                    domain_sort = predicate.domain(i)
                    placeholder_args.append(Const(f"{func_name}_auto_arg_{i}", domain_sort))
                return predicate(*placeholder_args)
            else:
                new_func = Function(func_name, BoolSort())
                self.predicates[func_name] = new_func
                return new_func()
    def _split_args(self, text: str) -> List[str]:
        text = text.strip()
        if not text:
            return []
        args = []
        buf = []
        depth = 0
        for ch in text:
            if ch == "(":
                depth += 1
                buf.append(ch)
            elif ch == ")":
                depth -= 1
                buf.append(ch)
            elif ch == "," and depth == 0:
                arg = "".join(buf).strip()
                if arg:
                    args.append(arg)
                buf = []
            else:
                buf.append(ch)
        if buf:
            arg = "".join(buf).strip()
            if arg:
                args.append(arg)
        return args

    def _auto_declare_predicate(self, name: str, arity: int) -> Function:
        canonical_name = resolve_predicate_alias(name)
        signature = get_predicate_signature(canonical_name)
        if signature:
            expected_arity, sorts = signature
            arity = expected_arity
        else:
            arity = max(arity, 0)
            sorts = ["Entity"] * arity

        if arity == 0:
            func = Function(canonical_name, BoolSort())
        else:
            domain_sorts = []
            for sort_name in sorts:
                canonical_sort = resolve_sort_alias(sort_name)
                sort_def = self.sort_definitions.get(canonical_sort, {"type": "Entity"})
                domain_sorts.append(self.type_mapper.map_sort(canonical_sort, sort_def))
            func = Function(canonical_name, *domain_sorts, BoolSort())
        self.predicates[canonical_name] = func
        logger.warning("Auto-declared predicate '%s' with arity %d", canonical_name, arity)
        return func
    
    def _parse_logical_expression(self, expr: str, strict: bool = False) -> BoolRef:
        """Parse logical expressions with operators."""
        # Handle negation
        if expr.startswith("not "):
            inner = self._parse_expression(expr[4:].strip(), strict=strict)
            return Not(inner)
        
        # Handle n-ary and/or operations (support expressions like "A and B and C")
        if " and " in expr:
            parts = [p.strip() for p in expr.split(" and ")]
            if len(parts) >= 2:
                # Recursively parse each part
                parsed_parts = [self._parse_expression(part, strict=strict) for part in parts]
                return And(*parsed_parts)
        
        # Handle n-ary or operations (support expressions like "A or B or C")
        if " or " in expr:
            parts = [p.strip() for p in expr.split(" or ")]
            if len(parts) >= 2:
                # Recursively parse each part
                parsed_parts = [self._parse_expression(part, strict=strict) for part in parts]
                return Or(*parsed_parts)
        
        # Handle binary implies
        if " implies " in expr:
            parts = [p.strip() for p in expr.split(" implies ")]
            if len(parts) == 2:
                left = self._parse_expression(parts[0], strict=strict)
                right = self._parse_expression(parts[1], strict=strict)
                return Implies(left, right)
        
        # Handle comparisons
        if any(comp in expr for comp in [">", "<", ">=", "<=", "==", "!="]):
            return self._parse_comparison(expr)
        
        # Handle boolean literals
        lowered = expr.lower()
        if lowered == "true":
            return BoolVal(True)
        if lowered == "false":
            return BoolVal(False)

        # Handle atomic propositions
        canonical_expr = resolve_predicate_alias(expr)
        if canonical_expr in self.predicates:
            # Get BoolRef by calling the function declaration
            return self.predicates[canonical_expr]()
        else:
            if strict:
                raise UnknownPredicateError(f"Unknown predicate: {expr}")
            else:
                # Create boolean variable for unknown atoms (permissive for queries)
                return Bool(expr)

    def _split_top_level(self, text: str) -> List[str]:
        """
        Split a string into top-level tokens, respecting nested parentheses.
        """
        parts: List[str] = []
        buf: List[str] = []
        depth = 0

        for ch in text:
            if ch == "(":
                depth += 1
                buf.append(ch)
            elif ch == ")":
                depth -= 1
                buf.append(ch)
            elif ch.isspace() and depth == 0:
                if buf:
                    token = "".join(buf).strip()
                    if token:
                        parts.append(token)
                    buf = []
            else:
                buf.append(ch)

        if buf:
            token = "".join(buf).strip()
            if token:
                parts.append(token)

        return parts
    
    def _parse_comparison(self, expr: str) -> BoolRef:
        """Parse comparison expressions."""
        # Simplified comparison parsing
        # TODO: Implement proper comparison parsing with type checking
        
        # For now, create a boolean variable to represent the comparison
        comp_var_name = f"comp_{hash(expr) % 1000}"
        return Bool(comp_var_name)


def build_solver_v21(logic_program: LogicProgram, facts: Dict[str, Any]) -> Tuple[Solver, Optional[BoolRef]]:
    """
    Build Z3 solver for DSL v2.1 format.
    
    Args:
        logic_program: LogicProgram with v2.1 structure
        facts: Dictionary of facts
        
    Returns:
        Tuple of (solver, query)
    """
    solver = Solver()
    parser = DSL21Parser()
    if hasattr(logic_program, "sorts"):
        parser.load_sorts(getattr(logic_program, "sorts") or {})
    
    # Parse predicates if present
    if hasattr(logic_program, 'predicates') and logic_program.predicates:
        parser.parse_predicates(logic_program.predicates)
    
    # Add facts as constraints (facts may come from preprocessing and not be declared explicitly)
    for fact_key, fact_value in facts.items():
        if fact_value:
            # Allow undeclared predicate creation for preprocessing facts (arity 0)
            fact_pred = parser._get_or_create_predicate(fact_key, allow_undeclared=True)
            solver.add(fact_pred)
            logger.debug(f"Added fact: {fact_key}")
    
    # Parse and add rules if present
    if hasattr(logic_program, 'rules') and logic_program.rules:
        rules = parser.parse_rules(logic_program.rules)
        for rule in rules:
            solver.add(rule)
            logger.debug(f"Added rule: {rule}")
    
    # Handle legacy axioms for backward compatibility
    if hasattr(logic_program, 'axioms') and logic_program.axioms:
        atoms_cache = {}
        _add_axioms_to_solver_v1(solver, logic_program.axioms, atoms_cache)
    
    # Parse query if present - permissive parsing to allow undeclared predicates
    query = None
    if logic_program.query and isinstance(logic_program.query, str) and logic_program.query.strip():
        try:
            query = parser._parse_expression(logic_program.query)
            logger.debug(f"Query parsed: {logic_program.query}")
        except Exception as e:
            raise ValueError(f"Errore nel parsing della query '{logic_program.query}': {e}")
    
    return solver, query


# =============================================================================
# Main API with version dispatch
# =============================================================================

def build_solver(
    logic_program: LogicProgram, 
    facts: Dict[str, Any]
) -> Tuple[Solver, Optional[BoolRef]]:
    """
    Costruisce un solver Z3 dal LogicProgram fornito.
    
    Args:
        logic_program: Il programma logico da tradurre in Z3
        facts: Dizionario di fatti da aggiungere come vincoli
        
    Returns:
        Tupla (solver, query) dove:
        - solver: Solver Z3 configurato
        - query: BoolRef della query o None se assente
    """
    # Check for DSL version to determine parsing strategy
    # Use attribute access directly now that LogicProgram has dsl_version field
    dsl_version = logic_program.dsl_version if hasattr(logic_program, 'dsl_version') else '1.0'
    
    logger.info(f"Building solver with DSL version: {dsl_version}")
    
    if dsl_version == '2.1':
        return build_solver_v21(logic_program, facts)
    else:
        # Default to v1 parsing for backward compatibility
        logger.info("Using DSL v1 parser for backward compatibility")
        solver = Solver()
        atoms_cache = {}
        
        # Add facts as boolean constraints
        for fact_key, fact_value in facts.items():
            if fact_value:
                fact_var = Bool(f"fact_{fact_key}")
                solver.add(fact_var)
                logger.debug(f"Added fact: {fact_key}")
        
        # Add axioms using v1 parser
        if hasattr(logic_program, 'axioms') and logic_program.axioms:
            _add_axioms_to_solver_v1(solver, logic_program.axioms, atoms_cache)
        
        # Parse query if present
        query = None
        if logic_program.query and logic_program.query.strip():
            try:
                query = _parse_formula(logic_program.query, atoms_cache)
                logger.debug(f"Query parsed: {logic_program.query}")
            except Exception as e:
                raise ValueError(f"Errore nel parsing della query '{logic_program.query}': {e}")
        
        return solver, query


# =============================================================================
# Helper functions for logic_feedback integration
# =============================================================================

def get_axioms_map(logic_program: LogicProgram) -> Dict[str, BoolRef]:
    """
    Return a mapping of axiom IDs to their Z3 representations.
    
    Args:
        logic_program: LogicProgram to analyze
        
    Returns:
        Dictionary mapping axiom IDs to BoolRef objects
    """
    axioms_map = {}
    
    if hasattr(logic_program, 'axioms') and logic_program.axioms:
        # For v1 format
        atoms_cache = {}
        for axiom in logic_program.axioms:
            axiom_id = axiom.get("id", f"axiom_{len(axioms_map)}")
            try:
                parsed = _parse_formula(axiom.get("formula", ""), atoms_cache)
                axioms_map[axiom_id] = parsed
            except Exception as e:
                logger.warning(f"Failed to parse axiom {axiom_id}: {e}")
    
    return axioms_map


def get_predicate_symbols(logic_program: LogicProgram) -> Dict[str, Any]:
    """
    Return a mapping of predicate names to their Z3 representations.
    
    Args:
        logic_program: LogicProgram to analyze
        
    Returns:
        Dictionary mapping predicate names to Z3 functions/predicates
    """
    symbols = {}
    
    dsl_version = getattr(logic_program, 'dsl_version', '1.0')
    
    if dsl_version == '2.1':
        # For v2.1, extract from predicates field
        if hasattr(logic_program, 'predicates') and logic_program.predicates:
            parser = DSL21Parser()
            parser.parse_predicates(logic_program.predicates)
            symbols = parser.predicates.copy()
    else:
        # For v1, extract from axioms
        atoms_cache = {}
        if hasattr(logic_program, 'axioms') and logic_program.axioms:
            for axiom in logic_program.axioms:
                formula = axiom.get("formula", "")
                # Simple extraction of predicate names from formula
                # This is a heuristic - in practice, a full parser would be better
                tokens = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', formula)
                for token in tokens:
                    if token not in ['and', 'or', 'not', 'implies', 'true', 'false']:
                        if token not in atoms_cache:
                            atoms_cache[token] = Bool(token)
                        symbols[token] = atoms_cache[token]
    
    return symbols
