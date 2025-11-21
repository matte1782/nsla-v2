# tests/test_logic_feedback.py
"""
Test suite for logic feedback generation and missing link detection.
Tests the four main outcomes and feedback quality.
"""
import pytest
from typing import Dict, Any, Optional
from pydantic import ValidationError

# Assuming the project structure has app directory
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.models import LogicProgram
from app.translator import build_solver
from app.logic_feedback import (
    build_logic_feedback,
    _extract_predicate_names_from_text,
    _collect_predicates_from_program,
    _compute_missing_links
)

# Import Z3 for direct manipulation
try:
    from z3 import Solver, Bool, Not, And, Or, Implies, sat, unsat, unknown
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False

requires_z3 = pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not available")


class TestFeedbackOutcomes:
    """Test the four main feedback outcomes."""
    
    @requires_z3
    def test_consistent_entails_feedback(self):
        """Test feedback for consistent entailment case."""
        # Program: A and (A -> B) entails B
        program = LogicProgram(
            dsl_version="2.1",
            sorts={"Bool": {"type": "Bool"}},
            constants={},
            predicates={"A": {"arity": 0}, "B": {"arity": 0}},
            axioms=[],
            rules=[{"condition": "A", "conclusion": "B"}],
            query="B"
        )
        
        facts = {"A": True}
        solver, query = build_solver(program, facts)
        
        feedback = build_logic_feedback(solver, program, query)
        
        assert feedback.status == "consistent_entails"
        assert "coerente e implica" in feedback.human_summary
        assert feedback.human_summary.count(".") <= 3  # Max 3 sentences
        assert len(feedback.conflicting_axioms) == 0
        assert "B" not in feedback.missing_links  # B is in program
    
    @requires_z3
    def test_consistent_no_entailment_feedback(self):
        """Test feedback for consistent but not entailed query."""
        # Program: A and (A -> B), query C (unrelated)
        program = LogicProgram(
            dsl_version="2.1",
            sorts={"Bool": {"type": "Bool"}},
            constants={},
            predicates={"A": {"arity": 0}, "B": {"arity": 0}},
            axioms=[],
            rules=[{"condition": "A", "conclusion": "B"}],
            query="C"
        )
        
        facts = {"A": True}
        solver, query = build_solver(program, facts)
        
        # Create BoolRef for C
        c_ref = Bool("C")
        
        feedback = build_logic_feedback(solver, program, c_ref)
        
        assert feedback.status == "consistent_no_entailment"
        assert "coerente ma la conclusione non è dimostrabile" in feedback.human_summary
        assert feedback.human_summary.count(".") <= 3
        assert "C" in feedback.missing_links
    
    @requires_z3
    def test_inconsistent_feedback(self):
        """Test feedback for inconsistent program."""
        # Program: A and not A
        program = LogicProgram(
            dsl_version="2.1",
            sorts={"Bool": {"type": "Bool"}},
            constants={},
            predicates={"A": {"arity": 0}},
            axioms=[],
            rules=[
                {"definition": "A"},
                {"definition": "not A"}
            ],
            query=""
        )
        
        facts = {}
        solver, query = build_solver(program, facts)
        
        feedback = build_logic_feedback(solver, program)
