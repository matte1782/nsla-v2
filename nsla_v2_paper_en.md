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
(Will be filled after repo finalization.)

