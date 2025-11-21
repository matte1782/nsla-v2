# app/preprocessing.py
from __future__ import annotations

from typing import Dict, Any
from pydantic import BaseModel


class PreprocessResult(BaseModel):
    normalized_question: str
    facts: Dict[str, Any] = {}


def preprocess_question(question: str) -> PreprocessResult:
    # Strip leading/trailing whitespace and collapse multiple whitespace to a single space
    normalized = " ".join(question.split())
    # Simple fact extraction (placeholder for MVP)
    facts = {
        "has_question_mark": normalized.rstrip().endswith("?")
    }
    return PreprocessResult(
        normalized_question=normalized,
        facts=facts
    )
