# **NSLA‑v2: A Neuro‑Symbolic Legal Reasoning Prototype**  
### **A Hybrid Technical + Academic Research Report**  
**Author:** Matteo Panzeri (with assistance from LLM‑based research tools)  
**Date:** 2025  

---

# **Abstract**
This report documents the development, analysis, and eventual suspension of **NSLA‑v2**, a neuro‑symbolic prototype designed to test whether **pure logical entailment using Z3** could support legal reasoning tasks. The project combines: (1) structured extraction, (2) a custom legal DSL, (3) a neuro‑symbolic pipeline, and (4) SMT‑based inference. While initial results showed promise on small synthetic cases, deeper experimentation revealed **structural limitations**: legal reasoning is inherently context‑dependent, non‑monotonic, and interpretative, whereas Z3 operates on fully‑specified, monotonic logical constraints. This mismatch prevents robust legal inference even when the DSL, predicates, and constraints are technically correct.

Although NSLA‑v2 does not achieve its original goal, the project produced valuable insights, reusable components, and new research directions (e.g., BinaryLLM, Concept Generator, Fractal Reasoning Engine). It stands as a **case study in failure‑driven research**, demonstrating critical thinking, system‑level engineering, rigorous testing, and reflective scientific analysis.

---

# **1. Introduction**
Legal reasoning is an attractive domain for neuro‑symbolic AI: it is rule‑based, text‑heavy, and seemingly compatible with logic formalization. The motivation behind NSLA‑v2 was to explore whether **pure logical entailment**, expressed through a custom DSL and executed via **Z3**, could serve as a foundational reasoning mechanism for legal tasks such as:
- contract interpretation,
- clause validation,
- entailment between obligations,
- contradiction detection.

Initial goals:
- Design a domain‑specific language (DSL) for legal facts.
- Translate natural language → structured extraction → DSL → logical formulas.
- Use Z3 to compute entailment, consistency, and derived obligations.
- Establish a feedback loop to refine logical output.

### **Why investigate this?**
The project serves as a scientific exploration—not a product. Its purpose was to evaluate feasibility, understand limitations, and extract principles useful for future research.

---

# **2. Background and Related Work**
### **2.1 Neuro‑Symbolic AI**
Neuro‑symbolic systems attempt to combine:
- statistical perception (LLMs, embeddings), and
- symbolic reasoning (logic, constraints, search).

This hybrid approach is powerful in formal verification, program synthesis, and safety‑critical systems. However, its application to *legal reasoning* is far less explored.

### **2.2 SMT and Z3**
Z3 is a state‑of‑the‑art SMT solver widely used in:
- formal verification,
- program analysis,
- compiler correctness,
- security.

Its strengths—determinism, precision, total explicitness—are also its weaknesses when applied to domains with ambiguity (law, ethics, natural language).

### **2.3 Legal Reasoning**
Legal interpretation is:
- **non‑monotonic** (adding facts can change conclusions),
- **contextual** (meaning depends on social, contractual, or jurisprudential context),
- **open‑textured** (concepts such as "reasonable" have fuzzy boundaries),
- **hierarchical** (norm conflicts, exceptions, jurisprudence).

These characteristics fundamentally conflict with monotonic logics typically handled by SMT solvers.

---

# **3. System Design**
This section summarizes the architecture implemented in NSLA‑v2.

### **3.1 Pipeline Overview**
```
Text → Structured Extraction → DSL → Normalization → Guardrail Checks → Z3 Encoding → Solve → Feedback
```

### **3.2 Components**
- **Structured extractor**: identifies actors, obligations, permissions.
- **DSL**: formal representation of clauses.
- **DSL Normalizer**: ensures consistent predicate naming, arity, and type usage.
- **Guardrail**: blocks malformed DSL programs before Z3.
- **Z3 Translator**: generates variables, sorts, constraints.
- **Solver**: checks SAT/UNSAT, generates model.
- **Feedback loop**: a refinement mechanism.

### **3.3 Why this architecture?**
It adheres to principles of:
- clarity,
- determinism,
- modularity,
- reproducibility.

The architecture itself is high quality—even though the domain mismatch prevents strong performance.

---

# **4. Experimental Setup**
### **4.1 Data**
Small benchmark of legal micro‑scenarios involving:
- purchase contracts,
- lease agreements,
- delivery obligations,
- payment duties,
- termination clauses.

### **4.2 Tasks Evaluated**
- Does the solver detect contradictions?
- Does DSL normalization preserve meaning?
- Are predicates mapped correctly?
- Does adding facts preserve or break entailment?

### **4.3 Testing Methodology**
- Pytest‑based unit and integration tests.
- Adversarial cases (incomplete DSL, malformed inputs).
- Iterative refinement loops.
- Validation of logical models.

---

# **5. Results and Failure Modes**
Despite technical correctness, the core issue is conceptual.

### **5.1 Positive Observations**
- DSL translation is stable and systematic.
- Z3 constraints are well‑formed.
- Guardrail blocks malformed programs effectively.
- Unit tests for logic operations pass consistently.

### **5.2 Failure Modes**
#### **1. Loss of semantic context**
Transforming natural language to DSL strips away:
- implicit conditions,
- legal interpretation layers,
- context dependencies.

#### **2. Non‑monotonicity**
Adding background facts can flip entailment results.
SMT solvers are not built for this behavior.

#### **3. Over‑specification**
Law allows underspecification. Z3 requires full specification.

#### **4. Lack of interpretative adaptation**
Semantic drift in language cannot be handled by static symbolic systems.

#### **5. Entailment ≠ Legal reasoning**
Even with a perfect DSL and correct constraints, the solver cannot capture the *interpretive*, *argumentative*, and *contextual* nature of human legal decisions.

---

# **6. Discussion**
### **Why this negative result matters**
Negative results guide research by:
- eliminating unfit approaches,
- revealing structural limitations,
- identifying promising alternative directions.

This case demonstrates that **logical entailment alone is insufficient** as a foundation for legal AI—an important insight for future research.

### **Key takeaway:**
> The problem is not in the implementation, but in the theoretical mismatch between legal reasoning and SMT‑based formal logic.

---

# **7. Lessons Learned**
### What worked:
- Modular architecture
- Solid DSL design
- Rigorous guardrail system
- Comprehensive tests

### What did not work:
- Entailment as primary reasoning method
- Mapping law → monotonic logic
- Context preservation

### What we learned:
- Legal AI requires logics that allow:
  - exceptions,
  - priorities,
  - context shifts,
  - defeasible reasoning.

Z3 alone cannot provide this.

---

# **8. Future Directions**
This project directly inspired several new research ideas:

### **1. BinaryLLM Protocol**  
Binary latent spaces for low‑energy inference.

### **2. Neuro‑Symbolic Concept Generator**  
Generate abstract mathematical propositions + verify them using solvers.

### **3. Fractal Reasoning Engine**  
Multi‑layer reasoning with self‑verification.

These directions align more naturally with solvers and avoid domain mismatch.

---

# **9. Conclusion**
NSLA‑v2 is a valuable experiment demonstrating that:
- strong engineering cannot overcome a theoretical mismatch, and
- failure‑driven research provides deep insight.

The project is archived as a research reference, code base, and foundation for future work.

---

# **10. Acknowledgments**
This research report and prototype were created by **Matteo Panzeri**, with assistance from advanced LLM‑based engineering agents, used critically and responsibly to accelerate ideation, documentation, and debugging.

---

# **Appendix A: Repository Structure**

The NSLA‑v2 repository is organized as a modular research prototype with clear separation of concerns. Below is an overview of the main directories and files:

### **Root Directory**
- **`README.md`**: Project overview, motivation, architecture summary, and usage instructions.
- **`requirements.txt`**: Python dependencies for the entire project.
- **`benchmark_llm_structured.py`**: Standalone script for benchmarking LLM structured extraction performance.
- **`test_*.py`**: Standalone test files for isolated component testing (LLM client, prompt loader).
- **`tmp_*.py`**: Temporary utility scripts for debugging and inspection.

### **`app/`** — Core Application Logic
Contains the main components of the neuro‑symbolic pipeline:
- **DSL and Logic**: `logic_dsl.py`, `models.py`, `models_v2.py` — legal domain‑specific language definitions and data models.
- **Extraction**: `structured_extractor.py` — extracts actors, obligations, and conditions from natural language.
- **Translation**: `translator.py` — converts DSL to Z3‑compatible logical formulas.
- **Normalization**: `canonical_rule_utils.py`, `ontology_utils.py` — ensures predicate consistency and type alignment.
- **Guardrails**: `guardrail_checker.py` — validates DSL programs before Z3 encoding to prevent malformed input.
- **Pipeline**: `pipeline_v2.py`, `main.py` — orchestrates the end‑to‑end neuro‑symbolic reasoning workflow.
- **Runtimes**: `judge_runtime.py`, `canonicalizer_runtime.py`, `refinement_runtime.py` — manages different phases of the pipeline.
- **Feedback & Iteration**: `logic_feedback.py`, `iteration_manager.py`, `history_summarizer.py` — implements refinement loops.
- **Explanation**: `explanation_synthesizer.py` — generates human‑readable explanations from solver outputs.
- **Utilities**: `llm_client.py`, `prompt_loader.py`, `config.py`, `checker.py`, `preprocessing.py` — supporting infrastructure.
- **Templates**: `templates/index.html` — minimal web interface (if applicable).

### **`tests/`** — Comprehensive Test Suite
Contains unit tests, integration tests, and end‑to‑end validation:
- **Component tests**: `test_translator_v2.py`, `test_guardrail_checker.py`, `test_logic_feedback.py`, `test_llm_structured.py`, etc.
- **Runtime tests**: `test_judge_runtime.py`, `test_phase2_runtimes.py`, `test_iteration_manager.py`.
- **End‑to‑end tests**: `test_end_to_end.py`, `test_phase2_e2e.py`, `test_phase3_e2e.py`.
- **Golden cases**: `test_nsla_v2_golden_cases.py` — known correct test cases for validation.
- **Benchmark tests**: `test_benchmark_smoke.py` — performance and correctness checks.
- **Configuration**: `conftest.py` — shared pytest fixtures and setup.

### **`data/`** — Benchmark Cases and Results
Stores test cases, evaluation data, and experimental results:
- **`cases_dev.json`**, **`cases_dev_subset_1_5.json`**: Legal micro‑scenarios for benchmarking.
- **`case_*.json`**: Individual test case responses.
- **`results_*.csv`**: Experimental results from different pipeline phases and configurations.

### **`docs/`** — Technical Documentation
Contains design documents, specifications, and planning materials:
- **`project.md`**, **`piano_operativo_mvp_llm_smt_nsla_matteo_panzeri.md`**: Project planning and operational notes.
- **`nsla_v2/`**: Detailed technical documentation including DSL guides, pipeline walkthroughs, test plans, phase reports, and debugging notes.

### **`resources/`** — Prompts, Ontology, and Specifications
Supporting resources for the pipeline:
- **`prompts/`**: LLM prompt templates organized by pipeline phase.
- **`ontology/`**: Legal ontology definitions for structured extraction.
- **`specs/`**: System specification documents and pipeline walkthroughs.

### **`scripts/`** — Utility Scripts
Standalone scripts for debugging and manual testing:
- **`inspect_subset_guardrail.py`**, **`manual_sanity.py`**: Diagnostic tools for pipeline validation.

### **Architecture Rationale**
The repository structure reflects the modularity principles of the NSLA‑v2 system:
- **Separation of concerns**: Extraction, DSL, translation, and solving are isolated.
- **Testability**: Each component has corresponding unit tests.
- **Documentation**: Technical decisions are recorded in `docs/`.
- **Reproducibility**: Benchmarks, test cases, and results are versioned.

This organization supports iterative research, debugging, and future extensions.

