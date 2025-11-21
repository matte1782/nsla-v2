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

# 🏗️ **3. System Architecture**
The NSLA-v2 architecture is modular, deterministic, and research-oriented.

### **Pipeline Overview**
```
Input Text
   ↓
Structured Extraction
   ↓
Legal DSL
   ↓
Normalization
   ↓
Guardrail Checks
   ↓
Z3 Encoding
   ↓
SMT Solve → SAT / UNSAT / Model
   ↓
Feedback Loop
```

### **Key Components**
- `structured_extractor/` → parses text into structured entities
- `dsl/` → legal DSL definitions and syntax rules
- `normalizer/` → predicate normalization, arity checks, type control
- `guardrail/` → blocks malformed DSL programs
- `translator_z3/` → logical encoding for Z3
- `pipeline_iterative/` → multi-stage reasoning + refinement
- `tests/` → rigorous test suite

---

# 📦 **4. Repository Structure**
```
neurosimbolic_project_v2/
├── src/
│   ├── dsl/
│   ├── z3_translator/
│   ├── pipeline/
│   ├── guardrail/
│   └── ...
├── tests/
│   ├── unit_tests/
│   ├── integration_tests/
│   └── adversarial_tests/
├── docs/
│   ├── PAPER_DRAFT_EN.md
│   ├── PAPER_DRAFT_IT.md
│   ├── ARCHITECTURE.md
│   ├── DSL_GUIDE.md
│   ├── WORKFLOW_CURSOR.md
│   └── NOTES/
├── requirements.txt
├── README.md
└── LICENSE
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