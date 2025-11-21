# NSLA v2 — Phase 3 Pipeline Specification (Iterative LLM ↔ Z3 Loop)

## 1. Overview
This document defines the architecture, control flow, state machine, and agent-level coordination for **Phase 3** of the Neuro‑Symbolic Legal Assistant v2 (NSLA v2). Phase 3 introduces a *bounded iterative refinement* mechanism (LLM ↔ Z3) that attempts to improve the correctness of the logic program over multiple controlled iterations.

Phase 3 does **not** replace Phase 2. Instead, it extends it with an optional mode:
```
/legal_query_iterative
```
or:
```
/legal_query?mode=iter
```

This mode activates a bounded number of LLM refinement cycles, guided by solver feedback, history summarization, and strict guardrails.

---

## 2. Files Required
Phase 3 depends on the following existing files (all produced during Phase 1–2):

### **Ontology & DSL**
- `ontology/legal_it_v1.yaml`
- `dsl_nsla_v_2_1.md`
- `nsla_v_2_dsl_logica_guida_tecnica.md`

### **Pipeline & Agent Specs**
- `nsla_v_2_pipeline.md`
- `nsla_v_2_pipeline_walkthrough.md`
- `canonicalizer_agent_vFinal.json`

### **Phase 3 Prompts (Agents)**
Located in:
```
resources/nsla_v2/prompts_phase3/
```
- `prompt_3_0_initial_llmoutput_v2.md`
- `prompt_3_1_iterative_refinement_agent.md`
- `prompt_3_2_history_summarizer.md`
- `prompt_3_3_iteration_inspector.md` (optional)

### **Existing components from Phase 1–2**
- `app/translator.py` (already validated; no changes required in Phase 3)
- `app/logic_feedback.py` (Phase 1 refined)
- `app/models_v2.py` (definitions of CanonicalizerOutput, LLMOutput_v2)
- `app/canonicalizer.py` (Phase 2 final canonicalizer)

---

## 3. Objective
The purpose of the Phase 3 pipeline is to:
1. Run **LLMOutput_v2 (iteration 0)** using Prompt 3.0.
2. Run Z3 → collect **logic_feedback_0**.
3. Decide whether to continue (based on consistency / missing links / improvement).
4. If improvement is needed:
   - Summarize history using Prompt 3.2.
   - Generate refined program using Prompt 3.1.
   - Validate with guardrails.
   - Run Z3 again.
5. Stop when:
   - Program becomes consistent (entails the query correctly), or
   - No improvement across iterations, or
   - Oscillation detected, or
   - `max_iters` reached.

The output is the final state and the full iteration history.

---

## 4. High-Level Architecture

```
                 ┌────────────────────┐
                 │  Input Question    │
                 └──────────┬─────────┘
                            │
                            ▼
                ┌──────────────────────┐
                │ Phase 2.1 Canonical. │
                └──────────┬───────────┘
                            ▼
                ┌──────────────────────┐
                │ Phase 2.2 LP_v1      │
                └──────────┬───────────┘
                            ▼
                ┌──────────────────────────┐
                │ Phase 3 Iteration Loop   │
                │  LLMOutput ↔ Z3          │
                └──────────┬───────────────┘
                            ▼
                ┌──────────────────────────┐
                │ Final Program & Feedback │
                └──────────────────────────┘
```

---

## 5. Detailed Sequence — Iteration 0

### **Step 0 — Inputs**
- Natural-language question (Italian)

### **Step 1 — Phase 2.1 Canonicalization**
Executes `canonicalizer_agent_vFinal` → produces:
```
CanonicalizerOutput
```

### **Step 2 — Phase 2.2 Logic Program v1**
Using ontology-driven structured extraction → produces:
```
logic_program_v1
```

### **Step 3 — Translator + Z3**
- Translates DSL → SMT
- Runs Z3
- Produces:
```
answer_v1
logic_feedback_v1
```

### **Step 4 — Phase 3.0 Initial LLMOutput_v2**
Prompt used: `prompt_3_0_initial_llmoutput_v2.md`

Goal: produce first refinement candidate.

Output:
```
LLMOutput_v2_iter0
```

---

## 6. State Machine — Iterative Loop (Phase 3)

```
start → iter0 → check → (stop | iter1 → check → iter2 → check → stop)
```

### **State: ITER_K**
Inputs:
- `LLMOutput_v2_iterK`
- Z3 feedback (`logic_feedback_K`)
- Iteration history

Outputs:
- next iteration program or stop

### **Transition Logic**
**Stop if any of these is true:**
- `status_K == consistent_entails`
- improvement metrics saturated (no new missing_links solved)
- oscillation detected across last 2 iterations
- `K >= max_iters`

**Otherwise continue:**
- Summarize history with Prompt 3.2
- Generate refinement with Prompt 3.1
- Apply guardrail (Prompt 3.4)
- Run Z3 → produce next feedback

---

## 7. Iteration History Structure
Stored as:
```
{
  "iterations": [
    {
      "k": 0,
      "llm_output": {...},
      "feedback": {...},
      "metrics": {...}
    },
    {
      "k": 1,
      "llm_output": {...},
      "feedback": {...},
      "metrics": {...}
    }
  ]
}
```
History is summarized by Prompt 3.2 before each refinement request.

---

## 8. Pseudocode for Phase 3 Controller

```python
def run_nsla_iterative(question, max_iters=3):
    # --- Phase 2 baseline ---
    canon = run_phase_2_1_canonicalizer(question)
    lp_v1 = run_phase_2_2_structured(program=canon)
    ans_v1, fb_v1 = run_z3(lp_v1)

    # --- Iteration 0 (initial refinement) ---
    llm0 = call_prompt_3_0_initial_llmoutput_v2(
        question, lp_v1, ans_v1, fb_v1
    )
    feedback0 = run_z3(llm0.logic_program)

    history = []
    history.append({"k": 0, "llm_output": llm0, "feedback": feedback0})

    # --- main loop ---
    for k in range(1, max_iters + 1):

        if should_stop(history):
            break

        summary = call_prompt_3_2_history_summarizer(history)

        llmK = call_prompt_3_1_iterative_refinement(
            question, history[-1], summary
        )

        guard = run_phase_2_4_guardrail(llmK.logic_program)
        if not guard.ok:
            apply_guardrail_policy(guard, llmK)

        feedbackK = run_z3(llmK.logic_program)

        history.append({"k": k, "llm_output": llmK, "feedback": feedbackK})

    return {
        "final_program": history[-1]["llm_output"].logic_program,
        "final_feedback": history[-1]["feedback"],
        "iteration_history": history
    }
```

---

## 9. Stop Criteria (deterministic)
Stop when **any** of the following is true:

### **1. Consistency achieved**
```
logic_feedback.status == "consistent_entails"
```

### **2. No improvement**
```
missing_links(K) == missing_links(K-1)
```

### **3. Regression or oscillation**
```
missing_links(K) > missing_links(K-1)
```
OR pattern:
```
A → B → A
```

### **4. Max iterations reached**
```
K == max_iters
```

---

## 10. Refusal Policy
If the refinement prompt produces a program violating:
- ontology boundaries
- arity mismatch
- contradictory rules

→ The iteration manager must request a corrected program OR stop.

Policy options:
```
"fail_fast" (stop immediately)
"auto_retry" (one retry allowed)
"fallback_to_v1" (return the iteration with best metrics)
```

---

## 11. Logging and Benchmarking
For each run, store:
```
/query_id/iter_0_llm_output.json
/query_id/iter_0_feedback.json
/query_id/iter_1_llm_output.json
...
/query_id/final.json
```

Metrics to record:
- number of iterations
- change in missing_links
- improvement in entailment status
- average refinement time
- oscillation count

---

## 12. Final Output Format of `/legal_query_iterative`
```
{
  "final_answer": "YES/NO + short reasoning",
  "final_logic_program": { ... },
  "final_feedback": { ... },
  "iterations": [ ... ],
  "metrics": {
    "num_iters": <int>,
    "converged": true/false,
    "oscillations": <int>
  }
}
```

---

## 13. Integration Notes
Phase 3 should:
- be optional (feature flag)
- never break Phase 1–2
- use the exact same DSL, ontology, and canonicalizer

It is intended for **complex borderline cases** where:
- v1 logic misses links
- Z3 fails to entail
- one-shot refinement is insufficient

When Phase 3 works correctly, it provides the highest quality reasoning chain of NSLA v2.

