# NSLA v2 – Test plan Phase 4 (ontology hydration & guardrail)

This document tracks the new tests we will add **after** Phase 4 coding is complete. Existing tests remain untouched; these are fresh modules to be created in future commits.

## 1. Ontology hydration for structured extractor ✅

Implemented in `tests/test_structured_extractor_ontology.py`.

- **Target file:** `tests/test_structured_extractor_ontology.py` (new file).
- **Goal:** Verify that `StructuredExtractorRuntime.run()` injects canonical sorts/constants even when the upstream LLM omits them.
- **Test idea:**
  1. Mock `llm_client.call_structured_extractor` to return a `LogicProgram` lacking `sorts`, but referencing predicate arguments (`Contratto`, `Soggetto`, etc.).
  2. Assert that the runtime output contains entries in `program.sorts` for every ontology entity used, with `{"type": "Entity"}` or the ontology metadata.
  3. Ensure downstream translator calls (`build_solver`) no longer emit “Unknown sort type” warnings.

## 2. Guardrail pass scenario with canonical program ✅

Implemented in `tests/test_phase2_guardrail_pass.py`.

- **Target file:** `tests/test_phase2_guardrail_pass.py` (new file).
- **Goal:** Provide a fixture logic program that mirrors the ontology (predicates declared, sorts specified) so that `run_guardrail` returns `ok=True`.
- **Test idea:**
  1. Build a `LogicProgram` with declared sorts, constants, and rules referencing only ontology predicates (e.g., `ContrattoValido`, `ResponsabilitaContrattuale`).
  2. Run `run_guardrail(program)` and assert `result.ok` is `True` and `result.issues` is empty.
  3. (Optional) Extend with a negative case where an undeclared sort/predicate triggers a specific `GuardrailIssue`.

## 3. Iterative loop integration smoke test (next)

- **Target file:** `tests/test_phase3_iterative_guardrail.py`.
- **Goal:** Simulate an iterative run where the best iteration passes guardrail and explanation is produced, ensuring endpoint `/legal_query_v2_iterative` surfaces the guardrail/explanation block.
- **Approach:** Use dependency injection/mocking for `llm_client` to return deterministic programs and check the JSON response shape (without hitting real LLMs).

These tests will be implemented once Phase 4 coding stabilizes. Until then, they serve as our checklist to guarantee the ontology-backed extractor and guardrail logic remain regression-proof.

