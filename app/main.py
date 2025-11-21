# app/main.py

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import Settings, get_settings
from .llm_client import LLMClient
from .models import QuestionRequest, LLMOutput, LegalQueryResult, LogicProgram, JudgeRequest
from .models_v2 import NSLAIterativeConfig
from .pipeline_v2 import NSLAPipelineV2
from .preprocessing import preprocess_question
from .translator import build_solver
from .guardrail_checker import run_guardrail
from .explanation_synthesizer import synthesize_explanation
from .judge_runtime import JudgeRuntime

# ---------------------------------------------------------------------------
# Configure logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
nsla_logger = logging.getLogger("nsla")

llm_client: LLMClient | None = None
judge_runtime: JudgeRuntime | None = None

# ---------------------------------------------------------------------------
# Templates configuration (Jinja2)
# ---------------------------------------------------------------------------
templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_client, judge_runtime
    settings: Settings = get_settings()
    llm_client = LLMClient(settings)
    judge_runtime = JudgeRuntime(
        llm_client,
        enabled=settings.enable_judge_metric,
    )
    print(
        f"LLMClient inizializzato. Modalità: "
        f"{'cloud' if settings.use_cloud else 'locale'}, "
        f"Modello: {llm_client.model_name}"
    )
    nsla_logger.info("NSLA MVP started with logging enabled")
    yield
    llm_client = None
    judge_runtime = None


app = FastAPI(title="NSLA MVP", version="0.1.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# UI route – simple HTML page powered by Jinja2
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def ui_root(request: Request):
    """
    Serves the minimal web UI (index.html) built with Jinja2.
    """
    return templates.TemplateResponse(request, "index.html", {"request": request})


# ---------------------------------------------------------------------------
# Existing API endpoints (v1)
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/llm_only")
def llm_only(payload: QuestionRequest) -> dict:
    if not llm_client:
        raise HTTPException(status_code=500, detail="LLM client not initialized")

    answer = llm_client.ask_llm_plain(payload.question)
    return {
        "answer": answer,
        "mode": "cloud" if llm_client.settings.use_cloud else "locale",
        "model_used": getattr(llm_client, "model_name", None),
    }


@app.post("/llm_structured")
def llm_structured(payload: QuestionRequest) -> LLMOutput:
    if not llm_client:
        raise HTTPException(status_code=500, detail="LLM client not initialized")

    result: LLMOutput = llm_client.ask_llm_structured(payload.question)
    return result


@app.post("/llm_structured_raw")
def llm_structured_raw(payload: QuestionRequest) -> dict:
    if not llm_client:
        raise HTTPException(status_code=500, detail="LLM client not initialized")

    raw = llm_client.ask_llm_structured_raw(payload.question)
    return {
        "raw": raw,
        "model_used": llm_client.model_name,
        "mode": "cloud" if llm_client.settings.use_cloud else "locale",
    }


@app.post("/debug_logic")
def debug_logic(payload: QuestionRequest) -> dict:
    if not llm_client:
        raise HTTPException(status_code=500, detail="LLM client not initialized")

    pre = preprocess_question(payload.question)
    llm_out = llm_client.ask_llm_structured(pre.normalized_question)
    solver, query = build_solver(llm_out.logic_program, pre.facts)
    status = str(solver.check())
    return {
        "z3_status": status,
        "normalized_question": pre.normalized_question,
        "facts": pre.facts,
        "has_query": query is not None,
    }


@app.post("/legal_query", response_model=LegalQueryResult)
def legal_query(payload: QuestionRequest) -> LegalQueryResult:
    """
    Endpoint principale – esegue l'intera pipeline:
    preprocess → LLM → Z3 translator → check (se disponibile) → risultato.
    """
    if not llm_client:
        raise HTTPException(status_code=500, detail="LLM client not initialized")

    # 1️⃣ Pre-processing della domanda
    pre = preprocess_question(payload.question)

    # 2️⃣ Richiesta strutturata all'LLM
    llm_out = llm_client.ask_llm_structured(pre.normalized_question)

    # 3️⃣ Traduzione in Z3
    solver, query = build_solver(llm_out.logic_program, pre.facts)

    # 4️⃣ Esecuzione dei controlli (fallback semplice se `run_checks` non esiste)
    try:
        # Prova a importare run_checks se disponibile
        from .checker import run_checks

        result_checks = run_checks(solver, query, pre.facts)
    except (ImportError, AttributeError):
        # Controllo minimo: status Z3
        status = str(solver.check())
        result_checks = {
            "verified": status != "unknown",
            "checks": [],
            "z3_status": status,
        }

    # 5️⃣ Costruzione della risposta finale
    return LegalQueryResult(
        answer=llm_out.final_answer,
        verified=result_checks["verified"],
        z3_status=result_checks["z3_status"],
        checks=result_checks["checks"],
        logic_program=llm_out.logic_program,
        facts=pre.facts,
    )


# ---------------------------------------------------------------------------
# New NSLA v2 Endpoints
# ---------------------------------------------------------------------------


@app.post("/legal_query_v2")
def legal_query_v2(payload: QuestionRequest) -> dict:
    """
    Single-shot v2 pipeline:
    - Uses NSLAPipelineV2.run_once to process the question.
    Returns a structured response with final answer, logic program, and feedback.
    """
    if not llm_client:
        raise HTTPException(status_code=500, detail="LLM client not initialized")

    # Initialize the v2 pipeline with default config
    pipeline = NSLAPipelineV2(llm_client, judge_runtime=judge_runtime)

    # Execute the one-shot pipeline
    phase2_result = pipeline.run_once(
        payload.question,
        reference_answer=payload.reference_answer,
    )

    # Format the response
    return {
        "mode": "v2_single",
        "final_answer": phase2_result.final_output.final_answer,
        "logic_program": phase2_result.final_output.logic_program,
        "feedback": {
            "status": phase2_result.feedback_v2.status,
            "missing_links": phase2_result.feedback_v2.missing_links,
            "conflicting_axioms": phase2_result.feedback_v2.conflicting_axioms,
            "human_summary": phase2_result.feedback_v2.human_summary,
        },
        "phase2": {
            "canonicalization": (
                phase2_result.canonicalization.model_dump()
                if phase2_result.canonicalization
                else None
            ),
            "logic_program_v1": (
                phase2_result.logic_program_v1.model_dump()
                if phase2_result.logic_program_v1
                else None
            ),
            "feedback_v1": (
                {
                    "status": phase2_result.feedback_v1.status,
                    "missing_links": phase2_result.feedback_v1.missing_links,
                    "conflicting_axioms": phase2_result.feedback_v1.conflicting_axioms,
                    "human_summary": phase2_result.feedback_v1.human_summary,
                }
                if phase2_result.feedback_v1
                else None
            ),
            "answer_v1": phase2_result.answer_v1,
        },
        "guardrail": {
            "ok": phase2_result.guardrail.ok,
            "issues": [issue.dict() for issue in phase2_result.guardrail.issues],
        },
        "explanation": phase2_result.explanation.dict(),
        "structured_stats": phase2_result.structured_stats,
        "llm_status": phase2_result.llm_status,
        "judge": (
            phase2_result.judge_result.model_dump()
            if phase2_result.judge_result
            else None
        ),
        "fallback_used": phase2_result.fallback_used,
        "fallback_feedback": (
            {
                "status": phase2_result.fallback_feedback.status,
                "missing_links": phase2_result.fallback_feedback.missing_links,
                "conflicting_axioms": phase2_result.fallback_feedback.conflicting_axioms,
                "human_summary": phase2_result.fallback_feedback.human_summary,
            }
            if phase2_result.fallback_feedback
            else None
        ),
    }


@app.post("/legal_query_v2_iterative")
def legal_query_v2_iterative(
    payload: QuestionRequest,
    max_iters: int = Query(3, description="Maximum number of iterations"),
) -> dict:
    """
    Iterative v2 pipeline:
    - Uses NSLAPipelineV2.run_iterative to process the question with multiple refinement steps.
    - Allows overriding max_iters via query parameter.
    Returns the best state and the history of iterations.
    """
    if not llm_client:
        raise HTTPException(status_code=500, detail="LLM client not initialized")

    # Initialize the v2 pipeline with custom config for max_iters
    config = NSLAIterativeConfig(max_iters=max_iters)
    pipeline = NSLAPipelineV2(llm_client, config)

    # Execute the iterative pipeline
    best_state, history = pipeline.run_iterative(payload.question)
    structured_stats_iter = pipeline.structured_extractor.get_last_stats()
    llm_status_iter = pipeline.get_last_llm_status()

    # Format the response
    # Guardrail + explanation on best iteration
    best_logic_program = LogicProgram(**best_state.llm_output.logic_program)
    guardrail = run_guardrail(best_logic_program)
    explanation = synthesize_explanation(
        payload.question,
        best_state.llm_output.final_answer,
        best_state.feedback,
        guardrail,
    )

    return {
        "mode": "v2_iterative",
        "best": {
            "iteration": best_state.iteration,
            "final_answer": best_state.llm_output.final_answer,
            "logic_program": best_state.llm_output.logic_program,
            "feedback": {
                "status": best_state.feedback.status,
                "missing_links": best_state.feedback.missing_links,
                "conflicting_axioms": best_state.feedback.conflicting_axioms,
                "human_summary": best_state.feedback.human_summary,
            },
            "guardrail": {
                "ok": guardrail.ok,
                "issues": [issue.dict() for issue in guardrail.issues],
            },
            "explanation": explanation.dict(),
        },
        "history": [
            {
                "iteration": state.iteration,
                "status": state.feedback.status,
                "missing_links": state.feedback.missing_links,
                "conflicting_axioms": state.feedback.conflicting_axioms,
            }
            for state in history
        ],
        "structured_stats": structured_stats_iter,
        "llm_status": llm_status_iter,
    }


# ---------------------------------------------------------------------------
# Judge LLM endpoint
# ---------------------------------------------------------------------------


@app.post("/judge_compare")
def judge_compare(payload: JudgeRequest) -> dict:
    if not llm_client:
        raise HTTPException(status_code=500, detail="LLM client not initialized")

    runtime = judge_runtime or JudgeRuntime(
        llm_client, enabled=get_settings().enable_judge_metric
    )
    result = runtime.evaluate(
        question=payload.question,
        reference_answer=payload.reference_answer,
        answer_a=payload.answer_a,
        answer_b=payload.answer_b,
        label_a=payload.label_a,
        label_b=payload.label_b,
    )
    return result.model_dump()

# ---------------------------------------------------------------------------
# Entry point (optional) – avvio locale
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
    )
