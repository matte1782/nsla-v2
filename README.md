# **NSLA-v2 — Neuro-Symbolic Legal Assistant (Research Prototype)**
### **Hybrid Technical + Academic Project Overview**
**Author:** Matteo Panzeri  
**Status:** Research Prototype (Paused)  
**Year:** 2025  

---

# 🚀 **1. Project Summary**
NSLA-v2 is a **neuro-symbolic research prototype** exploring whether *pure logical entailment using Z3* can be used as the core reasoning mechanism for legal tasks such as:
- contract interpretation,
- clause consistency,
- obligation entailment,
- contradiction detection.

The prototype combines:
- **structured extraction**,
- a custom **legal DSL**,
- a multi-stage **neuro-symbolic pipeline**,
- **Z3 SMT-based reasoning**,
- and iterative feedback loops.

### ❗ Important
This project represents a **negative research result**: while the engineering is correct, the theoretical foundations make Z3-based legal interpretation structurally unsuitable. 

Despite this limitation, the project produced:
- reusable code modules,
- a clean neuro-symbolic pipeline,
- DSL design patterns,
- a large test suite,
- and several new research directions.

It is published as a **case study in failure-driven research**, demonstrating critical thinking and scientific reasoning.

---

# 🧠 **2. Motivation**
Legal reasoning appears rule-like and logic-driven, making it a tempting domain for symbolic and neuro-symbolic systems. The goal was to test whether:

```
Text → Structured Extraction → DSL → Logic → Z3 → Legal Entailment
```

…could work reliably.

What we found is equally valuable:
> **The mismatch between law (non-monotonic, contextual, interpretative) and SMT solvers (monotonic, fully specified) makes pure logical entailment insufficient.**

This insight allowed us to pivot toward more promising research directions.

---

# 🏗️ **3. Architecture / System Design**

NSLA-v2 implements a **multi-stage neuro-symbolic pipeline** that combines LLM-based structured extraction with formal reasoning via Z3. The architecture is modular, testable, and designed for failure analysis—critical for understanding the limits of SMT-based legal reasoning.

### **Pipeline Flow**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Input: Legal Question (Natural Language)                          │
└──────────────────────┬──────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 2.1: Canonicalization (LLM)                                 │
│  → Extracts domain, concepts, unmapped terms                       │
│  → Module: canonicalizer_runtime.py                                │
└──────────────────────┬──────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 2.2: Structured Extraction (LLM → DSL)                      │
│  → Converts NL to LogicProgram (predicates, axioms, rules, query)  │
│  → Hydrates ontology from resources/ontology/legal_it_v1.yaml      │
│  → Module: structured_extractor.py                                 │
│  → DSL spec: logic_dsl.py (version 2.1)                            │
└──────────────────────┬──────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 2.3: Refinement (LLM feedback loop)                         │
│  → Receives Z3 feedback from v1 program                            │
│  → Generates refined LogicProgram v2 + final_answer                │
│  → Module: refinement_runtime.py                                   │
└──────────────────────┬──────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 2.4: Guardrail Checker                                      │
│  → Validates DSL version, predicate arities, sort compatibility    │
│  → Prevents malformed programs from reaching translator            │
│  → Module: guardrail_checker.py                                    │
└──────────────────────┬──────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Translator + Z3 Solver                                            │
│  → Encodes DSL into Z3 constraints (sorts → DatatypeSort)          │
│  → Builds solver with axioms, rules, query                         │
│  → Module: translator.py (DSL21Parser)                             │
└──────────────────────┬──────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Z3 Solver Result → Logic Feedback                                 │
│  → Status: consistent_entails | consistent_no_entailment |         │
│             inconsistent                                            │
│  → Missing links, conflicting axioms, human summary                │
│  → Module: logic_feedback.py                                       │
└──────────────────────┬──────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 2.5: Explanation Synthesis                                  │
│  → Generates human-readable explanation from feedback              │
│  → Module: explanation_synthesizer.py                              │
└──────────────────────┬──────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────────┐
│  (Optional) Phase 3: Iterative Refinement                          │
│  → Bounded loop: LLM ↔ Z3 feedback (max_iters configurable)       │
│  → Selects best iteration by heuristic (status priority)           │
│  → Module: iteration_manager.py                                    │
└──────────────────────┬──────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────────┐
│  (Optional) Phase 4: Judge-LLM Evaluation                          │
│  → Compares baseline vs. NSLA-v2 answer against reference          │
│  → Module: judge_runtime.py                                        │
└──────────────────────┬──────────────────────────────────────────────┘
                       ↓
                  Final Output
```

### **Module-to-Stage Mapping**

| **Pipeline Stage**          | **Module/File**                      | **Key Responsibilities**                                                                 |
|-----------------------------|--------------------------------------|------------------------------------------------------------------------------------------|
| **Orchestration**           | `pipeline_v2.py`                     | Coordinates all phases, manages LLM status, fact synthesis, program sanitization        |
| **DSL Specification**       | `logic_dsl.py`                       | Defines canonical sorts (Debitore, Contratto, etc.), predicates, DSL version (2.1)      |
| **Ontology Utilities**      | `ontology_utils.py`                  | Resolves predicate/sort aliases (e.g., "Soggetto obbligato" → "Debitore")               |
| **Canonicalization**        | `canonicalizer_runtime.py`           | Phase 2.1: Domain extraction, concept identification                                     |
| **Structured Extraction**   | `structured_extractor.py`            | Phase 2.2: NL → LogicProgram, hydrates sorts/predicates from ontology                    |
| **Refinement**              | `refinement_runtime.py`              | Phase 2.3: Iterative LLM refinement using Z3 feedback                                    |
| **Guardrail**               | `guardrail_checker.py`               | Phase 2.4: Static validation (DSL version, arity, sorts)                                 |
| **Z3 Translation**          | `translator.py`                      | Encodes DSL into Z3 (DSL21Parser), builds solver, handles fact synthesis                |
| **Logic Feedback**          | `logic_feedback.py`                  | Interprets Z3 results (sat/unsat/unknown) into actionable feedback                      |
| **Explanation**             | `explanation_synthesizer.py`         | Phase 2.5: Generates human-readable summaries                                            |
| **Iteration Manager**       | `iteration_manager.py`               | Phase 3: Bounded refinement loop with state tracking                                     |
| **Judge Metric**            | `judge_runtime.py`                   | Phase 4: LLM-based evaluation of baseline vs. NSLA-v2 answers                           |
| **Canonical Rules**         | `canonical_rule_utils.py`            | Ensures query rules follow DSL conventions                                               |
| **Data Models**             | `models.py`, `models_v2.py`          | Pydantic schemas: LogicProgram, LLMOutput, IterationState, GuardrailResult, etc.        |

### **Testing & Validation**

The codebase includes comprehensive tests that validate each stage:

- **Unit Tests**: `test_translator_autodeclare.py`, `test_guardrail_checker.py`, `test_structured_extractor_ontology.py`, `test_logic_feedback.py`
- **Integration Tests**: `test_phase2_e2e.py`, `test_phase3_e2e.py`, `test_phase2_runtimes.py`
- **Golden Cases**: `test_nsla_v2_golden_cases.py` — validates legal reasoning patterns (contractual liability, tort law, usucapion)
- **Component Tests**: `test_iteration_manager.py`, `test_explanation_synthesizer.py`, `test_judge_runtime.py`
- **Smoke Tests**: `test_benchmark_smoke.py` — validates benchmark infrastructure

Run tests:
```bash
pytest -v
```

### **Research Value & Insights**

This architecture is designed for **failure-driven research**:

1. **Neuro-Symbolic Integration**: Demonstrates how LLMs can interface with formal reasoning (Z3) through a typed DSL, showcasing both strengths (structured extraction) and weaknesses (semantic loss).

2. **Formal Verification Layer**: The guardrail + translator pipeline ensures that only well-formed logical programs reach Z3, making failures attributable to reasoning (not syntax).

3. **Iterative Feedback Loop**: Phase 3 implements a bounded refinement mechanism where Z3 feedback (missing links, conflicts) guides LLM re-generation—a pattern reusable in other symbolic AI domains.

4. **Documented Limitations**: The architecture exposes **why Z3 fails for legal reasoning**:
   - **Non-monotonicity**: Legal conclusions change with new context; Z3 assumes monotonic logic.
   - **Semantic loss**: NL → DSL translation strips nuance (intent, context, interpretation).
   - **Over-specification**: Law tolerates ambiguity; Z3 requires complete, consistent axioms.
   - **Entailment mismatch**: SAT/UNSAT ≠ legal validity (e.g., contract interpretation involves policy, not pure logic).

5. **Reusable Components**: Despite the theoretical mismatch, the modules (structured extraction, ontology mapping, iterative refinement, guardrails) are **directly applicable** to domains where formal reasoning is viable (e.g., compliance checking, configuration synthesis, protocol verification).

6. **Benchmarking Infrastructure**: The test suite provides reproducible failure cases, enabling future research to measure progress on neuro-symbolic legal reasoning or pivot to better-suited formalisms (e.g., non-monotonic logics, probabilistic reasoning).

### **Why This Design Matters**

For **research recruiters** evaluating this project:
- This is not a failed product—it's a **successful scientific experiment** that disproves a hypothesis.
- The architecture demonstrates **systems thinking**: modularity, testability, instrumentation (LLM status tracking, guardrails, feedback loops).
- The codebase is **publication-ready**: clear separation of concerns, comprehensive tests, documented limitations.
- The negative result **guides future research**: highlights where symbolic AI needs augmentation (e.g., probabilistic layers, defeasible reasoning, hybrid retrieval).

This project exemplifies the kind of **rigorous, failure-tolerant research** essential for advancing AI in complex, interpretive domains like law.

---

# 📦 **4. Repository Structure**
```
nsla-v2/
├── app/                           # Main application code (core logic)
│   ├── templates/                 # Templates for prompts/UI
│   ├── logic_dsl.py              # DSL specification (v2.1)
│   ├── translator.py             # Z3 translator (DSL → SMT)
│   ├── pipeline_v2.py            # Main pipeline orchestration
│   ├── guardrail_checker.py      # DSL validation & guardrails
│   ├── structured_extractor.py   # Phase 2.2: NL → DSL
│   ├── canonicalizer_runtime.py  # Phase 2.1: Domain extraction
│   ├── refinement_runtime.py     # Phase 2.3: Iterative refinement
│   ├── explanation_synthesizer.py # Phase 2.5: Human-readable output
│   ├── iteration_manager.py      # Phase 3: Bounded refinement loop
│   ├── judge_runtime.py          # Phase 4: LLM-based evaluation
│   ├── logic_feedback.py         # Z3 result interpretation
│   ├── ontology_utils.py         # Ontology mapping utilities
│   ├── models.py / models_v2.py  # Pydantic data models
│   └── ...                       # Other modules
├── tests/                         # Comprehensive test suite
│   ├── test_translator_autodeclare.py    # Unit: Z3 translator
│   ├── test_guardrail_checker.py         # Unit: Guardrail validation
│   ├── test_structured_extractor_ontology.py  # Unit: DSL extraction
│   ├── test_logic_feedback.py            # Unit: Z3 feedback
│   ├── test_phase2_e2e.py                # Integration: Phase 2
│   ├── test_phase3_e2e.py                # Integration: Phase 3
│   ├── test_nsla_v2_golden_cases.py      # Golden test cases
│   └── ...                               # Other tests
├── docs/                          # Documentation
│   └── nsla_v2/                   # Project-specific docs
│       ├── json/                  # JSON schemas/examples
│       ├── reports/               # Analysis reports
│       ├── dsl_nsla_v_2_1.md     # DSL guide
│       ├── logic_dsl_v2.md       # DSL specification
│       ├── nsla_v_2_phase_3_pipeline.md  # Phase 3 design
│       └── ...                    # Other documentation
├── data/                          # Test cases & benchmark results
│   ├── cases_dev.json            # Development test cases
│   └── results_*.csv             # Benchmark outputs
├── resources/                     # Static resources
│   ├── ontology/                 # Legal domain ontology
│   │   └── legal_it_v1.yaml     # Italian legal ontology
│   ├── prompts/                  # LLM prompt templates
│   │   ├── phase3/              # Phase 3 prompts
│   │   └── judge/               # Judge LLM prompts
│   └── specs/                    # Formal specifications
├── scripts/                       # Utility scripts
│   ├── inspect_subset_guardrail.py
│   └── manual_sanity.py
├── requirements.txt               # Python dependencies
├── README.md                      # This file
├── nsla_v2_paper_en.md           # Research paper (English)
└── nsla_v2_paper_it.md           # Research paper (Italian)
```

---

# 🔬 **5. Key Findings**
### ✔ What works well
- DSL design is clean and expressive.
- Guardrail system handles malformed DSL robustly.
- Z3 encodings are deterministic and well-formed.
- Unit and integration tests pass consistently on structured cases.
- Pipeline is modular and maintainable.

### ✘ What fundamentally fails
1. **Semantic loss**: Natural language → DSL strips essential meaning.
2. **Non-monotonicity**: Legal reasoning changes with added context; SMT cannot.
3. **Over-specification**: Law tolerates ambiguity; Z3 requires completeness.
4. **Interpretive reasoning**: Legal judgement is contextual, not purely logical.
5. **Entailment mismatch**: Solver SAT/UNSAT ≠ legal validity.

### 🎓 Scientific insight
> Legal reasoning cannot be reliably reduced to monotonic logical entailment.

This negative result is useful to guide future research.

---

# 🧪 **6. Experiments & Testing**
NSLA-v2 includes:
- DSL validation tests
- Z3 translator tests
- end-to-end pipeline tests
- adversarial malformed-DSL scenarios
- benchmark micro-cases (contracts, obligations, contradictions)

Run tests:
```bash
pytest -v
```

---

# ⚠️ **7. Project Status**
### **Status: Paused Research Prototype**
The project is kept public as:
- a case study of neuro-symbolic system design,
- a record of limitations of SMT-based legal reasoning,
- a foundation for future experiments.

See: `docs/PAPER_DRAFT_EN.md` for full explanation.

---

# 🔭 **8. Future Research Directions**
This project directly inspired several more promising lines of work:

### **1. BinaryLLM Protocol**
Binary latent representations for ultra-low-energy inference.

### **2. Neuro-Symbolic Concept Generator**
Generate abstract mathematical propositions → verify with Z3.

### **3. Fractal Reasoning Engine**
Multi-layer reasoning engine with internal self-verification loops.

All of these exploit the strengths of symbolic solvers without forcing them into domains they cannot model.

---

# ▶️ **9. How to Use / Run**
Install dependencies:
```bash
pip install -r requirements.txt
```

Execute pipeline (example):
```bash
python src/pipeline_iterative.py
```

Run benchmarks:
```bash
pytest -v tests/
```

---

# 👤 **10. Author**
This project was developed by **Matteo Panzeri**, with the assistance of advanced LLM-based research tools used responsibly to accelerate architectural exploration, debugging, and documentation.

---

# 📄 **11. License**
MIT License (recommended for research prototypes).