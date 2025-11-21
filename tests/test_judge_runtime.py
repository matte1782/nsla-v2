from app.config import Settings
from app.judge_runtime import JudgeRuntime
from app.llm_client import LLMClient


def test_judge_runtime_returns_tie_with_dummy_backend():
    settings = Settings(llm_backend="dummy")
    client = LLMClient(settings)
    runtime = JudgeRuntime(client, enabled=True)

    result = runtime.evaluate(
        question="Cos'è la responsabilità contrattuale?",
        reference_answer="Il debitore risponde per inadempimento imputabile.",
        answer_a="Risposta baseline",
        answer_b="Risposta migliorata",
        label_a="baseline",
        label_b="nsla_v2",
    )

    assert result.vote == "tie"
    assert result.confidence == 0.0
    assert result.rationale.startswith("Dummy backend") or "dummy" in result.rationale.lower()

