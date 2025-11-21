# tests/test_nsla_v2_golden_cases.py
"""
Golden test cases for NSLA v2 legal reasoning patterns.

This module validates higher-level legal reasoning patterns built on top of the DSL v2.1 and symbolic layer.
"""
import os
import sys

# Ensure we can import from the app directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.models import LogicProgram
from app.translator import build_solver
from app.logic_feedback import build_logic_feedback

try:
    from z3 import Solver, Bool, sat, unsat, unknown
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False

requires_z3 = pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not available")


@requires_z3
def test_contractual_liability_entails():
    """
    Test Case 1: Contractual Liability (entails)
    
    Legal logic: If ContrattoValido and Inadempimento and NessoCausale and DannoPatrimoniale, then ResponsabilitaContrattuale.
    Facts: all four premises are True.
    
    Expected:
    - feedback.status == "consistent_entails"
    - "coerente" and "implica" appear in human_summary
    - feedback.conflicting_axioms is empty
    - "ResponsabilitaContrattuale" not in missing_links
    """
    # Build the legal program
    program = LogicProgram(
        dsl_version="2.1",
        sorts={"Bool": {"type": "Bool"}},
        constants={},
        predicates={
            "ContrattoValido": {"arity": 0},
            "Inadempimento": {"arity": 0},
            "NessoCausale": {"arity": 0},
            "DannoPatrimoniale": {"arity": 0},
            "ResponsabilitaContrattuale": {"arity": 0}
        },
        axioms=[],
        rules=[
            {
                "condition": "ContrattoValido and Inadempimento and NessoCausale and DannoPatrimoniale",
                "conclusion": "ResponsabilitaContrattuale"
            }
        ],
        query="ResponsabilitaContrattuale"
    )
    
    # Set all premises as facts
    facts = {
        "ContrattoValido": True,
        "Inadempimento": True,
        "NessoCausale": True,
        "DannoPatrimoniale": True
    }
    
    solver, query = build_solver(program, facts)
    feedback = build_logic_feedback(solver, program, query)
    
    # Validate the feedback
    assert feedback.status == "consistent_entails"
    assert "coerente" in feedback.human_summary
    assert "implica" in feedback.human_summary
    assert len(feedback.conflicting_axioms) == 0
    assert "ResponsabilitaContrattuale" not in feedback.missing_links


@requires_z3
def test_contractual_liability_not_entailed():
    """
    Test Case 2: Contractual Liability (not entailed)
    
    Same logic program as Case 1, but missing the NessoCausale fact.
    
    Expected:
    - feedback.status == "consistent_no_entailment"
    - "coerente ma la conclusione non è dimostrabile" in human_summary
    - feedback.conflicting_axioms is empty
    - "NessoCausale" appears in missing_links
    """
    # Build the legal program (same as Case 1)
    program = LogicProgram(
        dsl_version="2.1",
        sorts={"Bool": {"type": "Bool"}},
        constants={},
        predicates={
            "ContrattoValido": {"arity": 0},
            "Inadempimento": {"arity": 0},
            "NessoCausale": {"arity": 0},
            "DannoPatrimoniale": {"arity": 0},
            "ResponsabilitaContrattuale": {"arity": 0}
        },
        axioms=[],
        rules=[
            {
                "condition": "ContrattoValido and Inadempimento and NessoCausale and DannoPatrimoniale",
                "conclusion": "ResponsabilitaContrattuale"
            }
        ],
        query="ResponsabilitaContrattuale"
    )
    
    # Facts, but missing NessoCausale
    facts = {
        "ContrattoValido": True,
        "Inadempimento": True,
        "DannoPatrimoniale": True
    }
    
    solver, query = build_solver(program, facts)
    feedback = build_logic_feedback(solver, program, query)
    
    # Validate the feedback
    assert feedback.status == "consistent_no_entailment"
    assert "coerente ma la conclusione non è dimostrabile" in feedback.human_summary
    assert len(feedback.conflicting_axioms) == 0
    assert "NessoCausale" in feedback.missing_links


@requires_z3
def test_conflicting_rules_inconsistent():
    """
    Test Case 3: Conflicting Rules (inconsistent)
    
    Legal logic: 
      If ContrattoValido and RitardoOltreSoglia then ClausolaPenaleApplicabile.
      If ContrattoValido and RitardoOltreSoglia then not ClausolaPenaleApplicabile.
    Facts: both ContrattoValido and RitardoOltreSoglia are True.
    
    Expected:
    - feedback.status == "inconsistent"
    - "contraddittori" in human_summary
    - len(feedback.conflicting_axioms) > 0
    """
    # Build the legal program with conflicting rules
    program = LogicProgram(
        dsl_version="2.1",
        sorts={"Bool": {"type": "Bool"}},
        constants={},
        predicates={
            "ContrattoValido": {"arity": 0},
            "RitardoOltreSoglia": {"arity": 0},
            "ClausolaPenaleApplicabile": {"arity": 0}
        },
        axioms=[],
        rules=[
            {
                "condition": "ContrattoValido and RitardoOltreSoglia",
                "conclusion": "ClausolaPenaleApplicabile"
            },
            {
                "condition": "ContrattoValido and RitardoOltreSoglia",
                "conclusion": "not ClausolaPenaleApplicabile"
            }
        ],
        query=""
    )
    
    facts = {
        "ContrattoValido": True,
        "RitardoOltreSoglia": True
    }
    
    solver, query = build_solver(program, facts)
    feedback = build_logic_feedback(solver, program, query)
    
    # Validate the feedback
    assert feedback.status == "inconsistent"
    assert "contraddittori" in feedback.human_summary
    assert len(feedback.conflicting_axioms) > 0
