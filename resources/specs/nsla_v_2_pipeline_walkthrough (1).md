# NSLA v2 – Full Pipeline Walkthrough (Concrete Example)

This document provides a complete, step-by-step walkthrough of how a real legal question flows through the entire **NSLA v2 pipeline**: Phases 2.1 → 2.5.

It serves as a **companion document** to `nsla_v2_pipeline.md`.

---

# 🔍 Example Legal Question

**User Question (Italian):**
> "Il contratto di manutenzione è stato concluso tra Alfa e Beta. Il debitore non ha eseguito la prestazione pattuita causando un danno economico al creditore. Può essere ritenuto responsabile contrattualmente ai sensi dell'art. 1218 c.c.?"

This is a realistic, complete question about **responsabilità contrattuale**.

---

# 🧠 Phase 2.1 – Canonicalization

System used: `canonicalizer_agent_vFinal.json`
Files loaded:
- `ontology/legal_it_v1.yaml`

### Input
```
{
  "question": "Il contratto di manutenzione è stato concluso ...",
  "options": {"return_low_confidence": false}
}
```

### Output (CanonicalizerOutput)
```
{
  "question": "...",
  "language": "it",
  "domain": "civil_law_contractual_liability",
  "concepts": [
    {"text": "contratto", "canonical_predicate": "Contratto", "confidence": 0.95},
    {"text": "prestazione", "canonical_predicate": "Prestazione", "confidence": 0.92},
    {"text": "non ha eseguito", "canonical_predicate": "Inadempimento", "confidence": 0.88},
    {"text": "danno economico", "canonical_predicate": "DannoPatrimoniale", "confidence": 0.94},
    {"text": "responsabile contrattualmente", "canonical_predicate": "ResponsabilitaContrattuale", "confidence": 0.96}
  ],
  "unmapped_terms": []
}
```

### Interpretation
The canonicalizer correctly identifies all predicates relevant to ответственность contrattuale.

---

# 🏗 Phase 2.2 – Structured Extraction → logic_program_v1

Files loaded:
- `dsl_nsla_v_2_1.md`
- `nsla_v_2_dsl_logica_guida_tecnica.md`
- `ontology/legal_it_v1.yaml`

### Input
```
{
  "question": "...",
  "canonicalization": {...},
  "target_task": "determine if ResponsabilitaContrattuale is entailed"
}
```

### Output: logic_program_v1
```
{
  "logic_program_v1": {
    "dsl_version": "2.1",
    "sorts": {
      "Soggetto": {},
      "Contratto": {},
      "Prestazione": {},
      "Danno": {}
    },
    "constants": {
      "alfa": "Soggetto",
      "beta": "Soggetto",
      "contratto_manutenzione": "Contratto"
    },
    "predicates": {
      "ContrattoValido": {"arity": 2},
      "Prestazione": {"arity": 1},
      "Inadempimento": {"arity": 2},
      "DannoPatrimoniale": {"arity": 1},
      "NessoCausale": {"arity": 2},
      "ResponsabilitaContrattuale": {"arity": 3}
    },
    "axioms": [
      {"formula": "ContrattoValido(alfa, contratto_manutenzione)"},
      {"formula": "Prestazione(contratto_manutenzione)"}
    ],
    "rules": [
      {
        "condition": "Inadempimento(alfa, contratto_manutenzione) and DannoPatrimoniale(beta) and NessoCausale(alfa, beta)",
        "conclusion": "ResponsabilitaContrattuale(alfa, beta, contratto_manutenzione)"
      }
    ],
    "query": "ResponsabilitaContrattuale(alfa, beta, contratto_manutenzione)"
  }
}
```

---

# 🧩 Phase 2.2 → Translator v1 → Z3

Translator produces SMT2.
Solver response:
```
status = SAT
```

But **does not entail** the query.

### logic_feedback_v1
```
{
  "status": "consistent_no_entailment",
  "missing_links": ["NessoCausale"],
  "conflicting_axioms": [],
  "human_summary": "Il sistema è coerente ma manca almeno un presupposto: il nesso causale."
}
```

---

# 🔧 Phase 2.3 – Refinement (Single-Pass LLMOutput_v2)

Files loaded:
- `ontology/legal_it_v1.yaml`
- `nsla_v_2_iterative_loop_design.md`
- `dsl_nsla_v_2_1.md`

### LLM receives
- v1 logic
- solver feedback
- missing links (`NessoCausale`)
- question

### Output (LLMOutput_v2)
```
{
  "final_answer": "Sì, il debitore è responsabile contrattualmente perché vi è inadempimento, danno e nesso causale.",
  "logic_program": {
    "dsl_version": "2.1",
    "sorts": {...},
    "constants": {...},
    "predicates": {...},
    "axioms": [...],
    "rules": [
      {
        "condition": "ContrattoValido(alfa, contratto_manutenzione) and Inadempimento(alfa, contratto_manutenzione) and DannoPatrimoniale(beta) and NessoCausale(alfa, beta)",
        "conclusion": "ResponsabilitaContrattuale(alfa, beta, contratto_manutenzione)"
      }
    ],
    "query": "ResponsabilitaContrattuale(alfa, beta, contratto_manutenzione)"
  },
  "notes": "Added NessoCausale to satisfy missing_links."
}
```

---

# 🛡 Phase 2.4 – Guardrail Check

### Input
```
logic_program_v2
```

### Output
```
{
  "ok": true,
  "issues": [],
  "auto_fix_suggestions": []
}
```

Everything valid.

---

# 🧠 Phase 2.3 → Translator v2 → Z3

Now the solver finds **entailed**:

```
status = UNSAT when assuming ¬ResponsabilitaContrattuale → so ENTAILED
```

---

# 📝 Phase 2.5 – Explanation Synthesis

### Input
- final_answer
- logic_program_v2
- logic_feedback_v2

### Output
```
{
  "explanation_it": "Il debitore è responsabile contrattualmente ...",
  "key_predicates": ["Inadempimento", "DannoPatrimoniale", "NessoCausale", "ResponsabilitaContrattuale"],
  "notes": null
}
```

---

# ✅ Final Outcome of the Pipeline

The NSLA v2 engine has:
- Understood the question
- Canonicalized legal concepts using ontology
- Built a logic program
- Checked it with a solver
- Refined missing reasoning
- Ensured consistency via guardrails
- Rechecked solver
- Produced final structured legal explanation

A perfect neuro-symbolic loop.

---

# 📌 THIS DOCUMENT CAN BE SAVED AS
`docs/nsla_v2/nsla_v2_pipeline_walkthrough.md`

Use it next to `nsla_v2_pipeline.md` for full clarity.

