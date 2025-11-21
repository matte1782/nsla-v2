# NSLA v2 – Phase 2 Benchmark Snapshot

- **Run date:** 15 Nov 2025  
- **Command:** `python app/benchmark.py --url http://127.0.0.1:8000 --cases data/cases_dev.json --output data/results.csv`  
- **Dataset:** `data/cases_dev.json` (15 demo questions, tagged per roadmap domains)  
- **Backend:** dummy LLM + full symbolic pipeline (guardrail + explanation + iteration manager)

## 1. Aggregate Metrics

| Metric (token-level) | LLM-only | NSLA v1 (`/legal_query`) | NSLA v2 (`/legal_query_v2`) | NSLA v2 iterativa |
|----------------------|---------:|-------------------------:|----------------------------:|------------------:|
| Accuracy / EM        | 0 %      | 0 %                      | 0 %                         | 0 %               |
| F1                   | **13.82 %** | **19.08 %**            | **19.08 %**                 | **19.08 %**       |
| BLEU                 | 0.00 %   | 2.34 %                   | 2.34 %                      | 2.34 %            |
| Avg latency (s)      | 0.019 ± 0.008 | 0.029 ± 0.011       | 0.039 ± 0.010               | 0.044 ± 0.011     |

**Notes**
- EM/accuracy naturally stay at 0 % because the current gold answers are full sentences while the dummy LLM outputs boilerplate; Phase 4’s dataset rewrite will fix this.
- F1 gains show the symbolic prompts do add structured tokens, but Phase 2 does not yet surpass Phase 1 on this dummy backend; the iterative mode matches two-pass because guardrail rejects every refined program (see below).

## 2. Guardrail & Feedback Observations

- `v2_guardrail_ok` is **False for all 15 cases** (`ContrattoValido` undeclared). The fallback path activates every time, so Phase 2 currently returns the v1 answer.
- Feedback_v1 status = `consistent_no_entailment` in all cases → reinforces the need for better predicates/facts from the structured extractor.
- Iterative loop history always reaches status `consistent_entails` at `iter=1`, but since the guardrail fails, the loop output is effectively ignored at API level.

## 3. Latency Footprint

| Step                         | Mean (s) | Comment |
|-----------------------------|---------:|---------|
| `/llm_only`                 | 0.019    | Dummy freeform call |
| `/legal_query` (NSLA v1)    | 0.029    | Structured call + single solver cycle |
| `/legal_query_v2`           | 0.039    | Adds refinement prompt + second solver + guardrail/explanation |
| `/legal_query_v2_iterative` | 0.044    | Iteration manager (max 3) stops at first guardrail failure |

Even with the full stack enabled, added latency is ≈25 ms per pass on this dummy setup; we should profile again once real LLM calls are wired in.

## 4. Action Items Before Phase 4

1. **Dataset upgrade:** rewrite `gold_answer` and add `gold_variants` so EM/accuracy become informative; expand tags per roadmap.
2. **Predicate coverage:** adjust structured extractor prompts/ontology so guardrail doesn’t reject every v2 program (e.g., ensure predicates referenced in rules are declared).
3. **Report automation:** keep `data/results.csv` under version control and re-run benchmarks whenever prompt/runtime changes land, appending the key metrics to this file.

Once the dataset cleanup is done, re-run the benchmark and append the new numbers here to track real improvements over the dummy baseline. This document satisfies the Phase 2 deliverable “report interno che confronta v1 vs v2 su dev-set”. 

---

## Phase 4 Dataset Run – 24 cases (15 Nov 2025, afternoon)

- **Dataset:** `data/cases_dev.json` expanded to 24 curated prompts (tutti con `gold_variants` + tag roadmap).
- **Command:** same as sopra (`python app/benchmark.py ...`).
- **Backend:** ancora dummy (nessun LLM reale), ma ora il benchmark esporta anche `tag_stats` e guardrail pass rate.

### Aggregate metrics

| Metric (token-level) | LLM-only | NSLA v1 (`/legal_query`) | NSLA v2 (`/legal_query_v2`) | NSLA v2 iterativa |
|----------------------|---------:|-------------------------:|----------------------------:|------------------:|
| Accuracy / EM        | 0 %      | 0 %                      | 0 %                         | 0 %               |
| F1                   | **11.50 %** | **19.01 %**           | **19.01 %**                 | **19.01 %**       |
| BLEU                 | 0.00 %   | 1.14 %                   | 1.14 %                      | 1.14 %            |
| Avg latency (s)      | 0.016 ± 0.010 | 0.017 ± 0.008       | 0.020 ± 0.011               | 0.027 ± 0.011     |
| Judge win rate (NSLA) | — | — | 0 % | 0 % |

### Guardrail & iteration telemetry

- `v2_guardrail_pass_rate = 0%`, `iter_guardrail_pass_rate = 0%` (dummy extractor still genera regole con token generici → il guardrail continua a bloccare il programma v2, quindi fase 2/3 ricade sul fallback).
- `tag_stats` è ora disponibile nel dizionario risultato (`run_benchmark` ritorna la lista con F1/accuracy per tag); sarà utile quando il dataset includerà decine di casi reali.

### Osservazioni

- L’aggiunta di casi tagged evidenzia come l’F1 medio resti stabile (~19%) grazie al layer simbolico, mentre l’LLM-only scende all’11–12 %.
- Latenze rimangono nell’ordine dei millisecondi perché il backend è ancora dummy; con un modello reale ci aspettiamo valori più alti ma i delta relativi tra v1/v2 rimarranno utili.
- Con `--judge` attivato, il modello giudice (via `/llm_only`) restituisce sempre `tie`, quindi `nsla_win_rate` è 0 %: comportamento previsto finché il backend produce risposte generiche.
- Gli obiettivi di Phase 4 (nuovi dataset, guardrail/ontology alignment, judge LLM) sono ora tracciabili: ogni nuova corsa del benchmark deve aggiornare questo file e `data/results.csv`.

