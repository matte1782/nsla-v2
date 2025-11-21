# app/models.py
from typing import List, Dict, Any, Union, Optional
from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str
    reference_answer: Optional[str] = None


class LogicProgram(BaseModel):
    """
    Generic logic program definition shared across NSLA v1 (dsl_version=1.0) and
    Phase 2/3 (dsl_version=2.1).  All sections default to empty containers so
    classic v1 payloads remain valid, while Phase 2 components can fill in the
    richer DSL metadata (sorts, predicates, structured rules).
    """

    dsl_version: str = "1.0"
    sorts: Dict[str, Any] = Field(default_factory=dict)
    constants: Dict[str, Any] = Field(default_factory=dict)
    predicates: Dict[str, Any] = Field(default_factory=dict)
    facts: Dict[str, Any] = Field(default_factory=dict)
    axioms: List[Dict[str, Any]] = Field(default_factory=list)
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    query: Union[str, Dict[str, Any], None] = None


class LLMOutput(BaseModel):
    final_answer: str
    premises: List[str]
    conclusion: str
    logic_program: LogicProgram


class LegalQueryResult(BaseModel):
    answer: str
    verified: bool
    z3_status: str
    checks: List[str]
    logic_program: LogicProgram
    facts: Dict[str, Any]


class JudgeRequest(BaseModel):
    question: str
    answer_a: str
    answer_b: str
    reference_answer: Optional[str] = None
    label_a: str = "LLM"
    label_b: str = "NSLA"
