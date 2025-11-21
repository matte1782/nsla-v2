# NSLA v2 – Pipeline Operativa (Phase 2)

Questo documento descrive l’orchestrazione completa della **Phase 2** di NSLA v2, basata sulla struttura esistente della v1 (translator + Z3 + logic_feedback) e sui nuovi componenti neuro‑simbolici.

---
## 1. Contesto e obiettivi

- **Non** modifichiamo la pipeline v1 esistente.
- Aggiungiamo una nuova modalità `legal_query_v2` che:
  1. Riusa la pipeline v1 per ottenere `logic_program_v1` + `logic_feedback_v1`.
  2. Aggiunge un **single-pass refinement** guidato dal solver (Phase 2.3).
  3. Integra il **Legal Question Canonicalizer** come componente opzionale a monte.

---
## 2. Componenti principali Phase 2

### 2.1 Canonicalizer (Phase 2.1)
- Implementato come agente logico secondo `canonicalizer_agent_vFinal.json`.
- Usa solo predicati definiti in `ontology/legal_it_v1.yaml`.
- Input: domanda in NL.
- Output (JSON):
  - `question`, `language`, `domain`
  - `concepts[]` (text, canonical_predicate, confidence, notes)
  - `unmapped_terms[]` (text, reason)

### 2.2 Structured Extractor → logic_program_v1 (Phase 2.2)
- Prende in input:
  - domanda in NL
  - output del Canonicalizer (facoltativo ma consigliato)
- Costruisce un `logic_program_v1` conforme a DSL v2.1 usando solo predicati dell’ontologia.

### 2.3 Refinement LLMOutput_v2 (Phase 2.3)
- Riceve:
  - `question`
  - `logic_program_v1`
  - `answer_v1`, `logic_feedback_v1`
- Produce:
  - `LLMOutput_v2` = { `final_answer`, `logic_program` (v2), `notes` }

### 2.4 Guardrail / Static Checker (Phase 2.4)
- Valida sintattica e localmente la coerenza di `logic_program_v2`.
- Non modifica il programma; restituisce solo `ok` + `issues`.

### 2.5 Explanation Synthesis (Phase 2.5)
- Riceve:
  - `question`
  - `final_answer`
  - `logic_program_v2` verificato
  - `logic_feedback_v2`
- Restituisce spiegazione in linguaggio naturale + lista predicati chiave.

---
## 3. Orchestrazione endpoint /legal_query_v2

### 3.1 Flusso high-level

```text
Utente → /legal_query_v2 → Orchestrator v2
  1) Canonicalizer (opzionale ma raccomandato)
  2) Structured Extractor → logic_program_v1
  3) Translator+Z3 v1 → answer_v1 + logic_feedback_v1
  4) Refinement (Phase 2.3) → LLMOutput_v2.logic_program
  5) Guardrail (Phase 2.4)
  6) Translator+Z3 v2 → logic_feedback_v2
  7) Explanation (Phase 2.5)
  8) Aggregazione risposta finale
```

### 3.2 Pseudocodice orchestratore

```python
def legal_query_v2(request):
    question = request.question

    # 1. Canonicalizer (Phase 2.1)
    canonicalization = run_phase_2_1_canonicalizer(question)

    # 2. Structured Extractor (Phase 2.2)
    logic_program_v1 = run_phase_2_2_structured_extractor(
        question=question,
        canonicalization=canonicalization,
    )

    # 3. Run v1 pipeline (translator + Z3 + feedback)
    answer_v1, logic_feedback_v1 = run_v1_symbolic_layer(logic_program_v1)

    # 4. Refinement (Phase 2.3)
    llm_output_v2 = run_phase_2_3_refinement(
        question=question,
        logic_program_v1=logic_program_v1,
        answer_v1=answer_v1,
        logic_feedback_v1=logic_feedback_v1,
    )
    logic_program_v2 = llm_output_v2["logic_program"]
    final_answer = llm_output_v2["final_answer"]

    # 5. Guardrail (Phase 2.4)
    guardrail = run_phase_2_4_guardrail(logic_program_v2)
    if not guardrail["ok"]:
        # opzionale: fallback a v1 o segnalazione errore
        return build_error_response(question, answer_v1, logic_feedback_v1, guardrail)

    # 6. Z3 v2
    answer_v2, logic_feedback_v2 = run_v1_symbolic_layer(logic_program_v2)

    # 7. Explanation (Phase 2.5)
    explanation = run_phase_2_5_explanation(
        question=question,
        final_answer=answer_v2 or final_answer,
        logic_program=logic_program_v2,
        logic_feedback_v2=logic_feedback_v2,
    )

    # 8. Aggregazione
    return {
        "question": question,
        "answer_v1": answer_v1,
        "logic_feedback_v1": logic_feedback_v1,
        "answer_v2": answer_v2,
        "logic_feedback_v2": logic_feedback_v2,
        "final_answer": answer_v2 or final_answer,
        "canonicalization": canonicalization,
        "logic_program_v1": logic_program_v1,
        "logic_program_v2": logic_program_v2,
        "guardrail": guardrail,
        "explanation": explanation,
    }
```

---
## 4. File richiesti per Phase 2 (senza toccare v1)

Questi file appartengono alla **Phase 2**, ma l’implementazione di codice Python vero e proprio può essere fatta in Fase 3.

### 4.1 Già esistenti dalla Phase 1 / baseline v1

- `app/translator.py` (già ottimizzato in Phase 1)
- `app/logic_feedback.py`
- `tests/` relativi a translator + feedback + NSLA v1

### 4.2 Artefatti di specifica / prompt (Phase 2)

Da tenere in `resources/specs/` o `docs/nsla_v2/`:

- `dsl_nsla_v_2_1.md`
- `nsla_v_2_dsl_logica_guida_tecnica.md`
- `nsla_v_2_iterative_loop_design.md`
- `nsla_v_2_roadmap_neuro_symbolic_legal_assistant.md`
- `ontology/legal_it_v1.yaml`
- `canonicalizer_agent_vFinal.json`
- `nsla_v2_pipeline.md` (questo documento)
- Prompt Phase 2.1–2.5 (es. in `prompts/nsla_v2_phase_2.md` o file separati)

### 4.3 Modelli/schema Python (da implementare in Phase 3)

File da creare **quando passi all’implementazione backend**:

- `app/models_v2.py`
  - `CanonicalizerOutput` (schema Phase 2.1)
  - `LLMOutput_v2` (schema Phase 2.3)

- `app/canonicalizer.py`
  - Implementazione runtime del canonicalizer in Python, seguendo
    `canonicalizer_agent_vFinal.json`.

- `app/pipeline_v2.py`
  - Implementazione dell’orchestratore `legal_query_v2` basato sullo pseudocodice sopra.

Questi file appartengono alla **Phase 3 (implementazione)**, ma li abbiamo già
progettati in Phase 2.

---
## 5. Nota su /legal_query_v2

- Non è necessario creare subito la cartella `api/`.
- Puoi:
  - mantenere la struttura attuale in `app/` (come v1),
  - aggiungere in seguito un `api_v2.py` o estendere l’endpoint esistente
    con un parametro `mode="v2"`.
- La Fase 2 è principalmente **di design/specifica**: definisce pipeline, agenti,
  prompt e ontologia.
- La Fase 3 sarà dedicata a:
  - implementare codice Python nei file indicati,
  - collegare gli endpoint FastAPI,
  - aggiungere test `pytest` per Phase 2/3.

---
## 6. Checklist: abbiamo tutto per chiudere Phase 2?

- [x] DSL v2.1 definita (`dsl_nsla_v_2_1.md`).
- [x] Guida logica NSLA v2 (`nsla_v_2_dsl_logica_guida_tecnica.md`).
- [x] Roadmap e design loop (`nsla_v_2_roadmap_neuro_symbolic_legal_assistant.md`, `nsla_v_2_iterative_loop_design.md`).
- [x] Ontologia responsabilità contrattuale (`ontology/legal_it_v1.yaml`).
- [x] Specifica completa canonicalizer (`canonicalizer_agent_vFinal.json`).
- [x] Prompt Phase 2.1–2.5 definiti.
- [x] Documento di orchestrazione `nsla_v2_pipeline.md` (questo).

=> **Conclusione**: Phase 2 (design & spec) è concettualmente completa.
La prossima fase (Phase 3) consisterà nel trasformare queste specifiche in
codice Python, endpoint API e test automatici.

