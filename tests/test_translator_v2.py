# tests/test_translator_v2.py
"""
Test suite for DSL v2.1 parsing and Z3 solver construction.
Tests soundness, type mapping, and predicate recognition.
"""
import pytest
from typing import Dict, Any, Optional
from pydantic import ValidationError

# Assuming the project structure has app directory
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.models import LogicProgram
from app.translator import (
    build_solver, DSL21Parser, Z3TypeMapper,
    InvalidArityError, UnknownPredicateError, DSLParseError
)
from app.logic_feedback import build_logic_feedback


class TestDSL21Parsing:
    """Test DSL v2.1 parsing capabilities."""
    
    def test_simple_predicate_parsing_v21(self):
        """Test parsing of simple boolean predicates in v2.1."""
        predicates = {
            "P": {},
            "Q": {"arity": 0},
            "R": {"arity": 0, "sorts": []}
        }
        
        parser = DSL21Parser()
        parser.parse_predicates(predicates)
        
        assert "P" in parser.predicates
        assert "Q" in parser.predicates  
        assert "R" in parser.predicates
        
        # Check arity
        assert parser.predicates["P"].arity() == 0
        assert parser.predicates["Q"].arity() == 0
        assert parser.predicates["R"].arity() == 0
    
    def test_predicate_with_arguments_v21(self):
        """Test parsing of predicates with arguments."""
        predicates = {
            "has_property": {
                "arity": 2,
                "sorts": ["String", "String"]
            },
            "greater_than": {
                "arity": 2, 
                "sorts": ["Int", "Int"]
            }
        }
        
        parser = DSL21Parser()
        parser.parse_predicates(predicates)
        
        assert "has_property" in parser.predicates
        assert "greater_than" in parser.predicates
        assert parser.predicates["has_property"].arity() == 2
        assert parser.predicates["greater_than"].arity() == 2
    
    def test_invalid_arity_raises_error(self):
        """Test that invalid arity raises InvalidArityError."""
        predicates = {
            "test_pred": {
                "arity": 2,
                "sorts": ["String"]  # Mismatch: arity 2 but only 1 sort
            }
        }
        
        parser = DSL21Parser()
        with pytest.raises(InvalidArityError):
            parser.parse_predicates(predicates)
    
    def test_type_mapping_v21(self):
        """Test Z3 type mapping for DSL sorts."""
        mapper = Z3TypeMapper()
        
        # Test basic type mapping
        bool_sort = mapper.map_sort("Bool", {"type": "Bool"})
        int_sort = mapper.map_sort("Int", {"type": "Int"})
        float_sort = mapper.map_sort("Float", {"type": "Float"})
        string_sort = mapper.map_sort("String", {"type": "String"})
        
        assert str(bool_sort) == "Bool"
        assert str(int_sort) == "Int"
        assert str(float_sort) == "Real"
        assert str(string_sort) == "String"
    
    def test_entity_type_mapping_v21(self):
        """Test entity datatype mapping."""
        mapper = Z3TypeMapper()
        
        # Test entity with values (enum)
        entity_with_values = mapper.map_sort("Role", {
            "type": "Entity",
            "values": ["Admin", "User", "Guest"]
        })
        
        assert "Role_type" in mapper.type_cache
        
        # Test entity without values (fallback to String)
        entity_no_values = mapper.map_sort("GenericEntity", {"type": "Entity"})
        assert str(entity_no_values) == "String"


class TestSolverConstruction:
    """Test solver construction from logic programs."""
    
    def test_minimal_v21_program(self):
        """Test building solver from minimal v2.1 program."""
        program = LogicProgram(
            dsl_version="2.1",
            sorts={"Bool": {"type": "Bool"}},
            constants={},
            predicates={"P": {"arity": 0}, "Q": {"arity": 0}},
            axioms=[],
            rules=[
                {
                    "condition": "P",
                    "conclusion": "Q"
                }
            ],
            query="Q"
        )
        
        facts = {"P": True}
        solver, query = build_solver(program, facts)
        
        assert solver is not None
        assert query is not None
        
        # Check solver has assertions
        assertions = solver.assertions()
        assert len(assertions) >= 2  # P and (P -> Q)
    
    def test_v21_with_facts_only(self):
        """Test v2.1 program with only facts, no rules."""
        program = LogicProgram(
            dsl_version="2.1",
            sorts={"Bool": {"type": "Bool"}},
            constants={},
            predicates={"fact1": {"arity": 0}, "fact2": {"arity": 0}},
            axioms=[],
            rules=[],
            query=""
        )
        
        facts = {"fact1": True, "fact2": True}
        solver, query = build_solver(program, facts)
        
        assert solver is not None
        assert query is None
    
    def test_v21_rules_parsing(self):
        """Test parsing of rules in v2.1 format."""
        program = LogicProgram(
            dsl_version="2.1",
            sorts={"Bool": {"type": "Bool"}},
            constants={},
            predicates={
                "A": {"arity": 0},
                "B": {"arity": 0}, 
                "C": {"arity": 0}
            },
            axioms=[],
            rules=[
                {
                    "condition": "A and B",
                    "conclusion": "C"
                },
                {
                    "definition": "A or B"
                }
            ],
            query=""
        )
        
        facts = {"A": True}
        solver, query = build_solver(program, facts)
        
        assert solver is not None
        # Should have 3 assertions: A, (A and B -> C), (A or B)
    
    def test_unknown_predicate_error(self):
        """Test that unknown predicate in expression raises error."""
        program = LogicProgram(
            dsl_version="2.1", 
            sorts={"Bool": {"type": "Bool"}},
            constants={},
            predicates={"known": {"arity": 0}},
            axioms=[],
            rules=[
                {
                    "condition": "unknown_predicate",  # Not defined
                    "conclusion": "known"
                }
            ],
            query=""
        )
        
        facts = {}
        
        # This should raise UnknownPredicateError during rule parsing
        with pytest.raises(UnknownPredicateError):
            build_solver(program, facts)
    
    def test_backward_compatibility_v1(self):
        """Test that v1 programs still work."""
        program = LogicProgram(
            dsl_version="1.0",
            sorts={},
            constants={},
            axioms=[
                {"id": "ax1", "formula": "P and Q -> R"},
                {"id": "ax2", "formula": "R -> S"}
            ],
            query="S"
        )
        
        facts = {"P": True, "Q": True}
        solver, query = build_solver(program, facts)
        
        assert solver is not None
        assert query is not None


class TestLogicFeedbackIntegration:
    """Test integration with logic feedback system."""
    
    def test_feedback_sat_entails(self):
        """Test feedback generation for consistent entailment."""
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
        assert len(feedback.conflicting_axioms) == 0
        assert len(feedback.missing_links) == 0
    
    def test_feedback_sat_no_entailment(self):
        """Test feedback for consistent but not entailed query."""
        program = LogicProgram(
            dsl_version="2.1",
            sorts={"Bool": {"type": "Bool"}},
            constants={},
            predicates={"A": {"arity": 0}, "B": {"arity": 0}},
            axioms=[],
            rules=[{"condition": "A", "conclusion": "B"}],
            query="C"  # C not connected to A/B
        )
        
        facts = {"A": True}
        solver, query = build_solver(program, facts)
        
        # Create a BoolRef for C manually since it's not defined
        from z3 import Bool
        c_ref = Bool("C")
        
        feedback = build_logic_feedback(solver, program, c_ref)
        
        assert feedback.status == "consistent_no_entailment"
        assert "coerente ma la conclusione non è dimostrabile" in feedback.human_summary
        assert "C" in feedback.missing_links
    
    def test_feedback_unsat(self):
        """Test feedback for inconsistent program."""
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
        
        assert feedback.status == "inconsistent"
        assert "contraddittori" in feedback.human_summary
        assert len(feedback.conflicting_axioms) > 0


if __name__ == "__main__":
    pytest.main([__file__])
