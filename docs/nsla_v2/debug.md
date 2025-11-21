# NSLA v2 – Phase 0 Baseline Report (config + translator + preprocessing)

Data: 15 Nov 2025  
Responsabile: ANSA (Architetto Neuro-Simbolico Autonomo)

## Contesto
- Roadmap riferimento: `nsla_v_2_roadmap_neuro_symbolic_legal_assistant.md`, Fase 0.
- Obiettivo: congelare una baseline v1 funzionante (LLM-only + check simbolico) senza regressioni.

## Stato test baseline
- Comando:  
  ```powershell
  cmd /c "cd /d C:\Users\matte\Desktop\Desktop OLD\AI\UNIVER~1\courses\computational_logic\resources\book\neurosimbolic_project_v2 && .\.venv_nsla_v2\Scripts\python.exe -m pytest -q"
  ```
- Esito: **53 passed / 0 failed** (Pytest warnings invariati sui test standalone del prompt loader).
- Problemi rilevati/risolti:
  1. `Unknown predicate: has_question_mark` (facts generati dal preprocess).  
     ➜ `translator.build_solver_v21` ora crea automaticamente predicati 0-arity per i fatti runtime (`allow_undeclared=True` per i facts).  
     ➜ `translator._parse_logical_expression` riconosce i literal `true/false`.
  2. `Unknown predicate: ContrattoValido` nel dummy logic program.  
     ➜ `LLMClient._build_dummy_logic_program` dichiara i predicati con metadati (arity + sorts).

## Configurazione (M0)
- `app/config.py` ora espone:
  - `llm_backend`, `local_model_name`, `cloud_model_name`.
  - Flag `use_cloud`, `use_local_model`, `enable_symbolic_layer`, `benchmark_mode`.
  - Commento/docstring aggiornato per uso come fonte unica di configurazione.

## Documentazione aggiornata
- `README.md`: panoramica Phase 0, mappa M0–M8, comandi base, riferimento test.

---

# NSLA v2 – Phase 1 Debug Report (translator + logic_feedback)

## Contesto e Obiettivi
Questo report documenta le correzioni applicate ai moduli `translator.py` e `logic_feedback.py` per risolvere i fallimenti dei test nella Fase 1 del progetto NSLA v2 (Neuro-Symbolic Legal Assistant). L'obiettivo principale era garantire che i test target `test_minimal_v21_program` e `test_consistent_entails_feedback` passassero correttamente.

## Sintesi dei Problemi Iniziali

### 1. Test `test_minimal_v21_program` - Regole non tradotte
- **Problema**: Il solver conteneva solo 1 asserzione (il fatto P) invece delle 2 aspettate (fatto P + regola P→Q)
- **Causa**: Le regole nel formato `{"condition": "P", "conclusion": "Q"}` non venivano tradotte in vincoli Z3
- **Impatto**: Test falliva per numero di asserzioni insufficiente

### 2. Test `test_consistent_entails_feedback` - Entailment non riconosciuto
- **Problema**: Lo scenario logico A ∧ (A → B) ⊢ B restituiva `"consistent_no_entailment"` invece di `"consistent_entails"`
- **Causa**: 
  - Mancanza dell'import `Not` da Z3 in `logic_feedback.py`
  - Logica di entailment check non corretta
- **Impatto**: Feedback sbagliato sullo stato logico del sistema

### 3. Warning Pydantic v2 - Uso di `.dict()` deprecato
- **Problema**: Uso di `logic_program.dict()` con Pydantic v2
- **Impatto**: Warning durante l'esecuzione dei test

## Fix Applicati

### `app/translator.py`

#### 1. Parsing delle Regole Corretto
```python
def parse_rules(self, rules: List[Dict[str, Any]]) -> List[BoolRef]:
    # ... existing code ...
    if "condition" in rule and "conclusion" in rule:
        # Structured rule: condition -> conclusion
        condition_expr = str(rule["condition"]).strip()
        conclusion_expr = str(rule["conclusion"]).strip()
        
        # Create BoolRef for condition and conclusion
        condition_pred = self._get_or_create_predicate(condition_expr)
        conclusion_pred = self._get_or_create_predicate(conclusion_expr)
        
        # Create Implies constraint
        implies_formula = Implies(condition_pred, conclusion_pred)
        z3_rules.append(implies_formula)
Spiegazione: Il metodo parse_rules ora gestisce correttamente il formato semplificato delle regole, creando predicati BoolRef e traducendo la struttura condition→conclusion in Implies(condition_pred, conclusion_pred).

2. Helper _get_or_create_predicate
def _get_or_create_predicate(self, name: str) -> BoolRef:
    """Helper method to get or create a boolean predicate."""
    name = name.strip()
    
    if name in self.predicates:
        func_decl = self.predicates[name]
        if func_decl.arity() == 0:
            return func_decl()
        else:
            args = [Bool(f"arg_{i}_{name}") for i in range(func_decl.arity())]
            return func_decl(*args)
    else:
        return Bool(name)
Spiegazione: Questo metodo garantisce coerenza tra i predicati dichiarati e quelli usati nelle regole, creando predicati consistenti.

3. Parser per Predicati di Arità 0
# Corrected: Use z3.Function with empty domain for arity 0 predicates
self.predicates[pred_name] = Function(pred_name, BoolSort())
Spiegazione: I predicati di arità 0 vengono ora creati come funzioni booleane con dominio vuoto, garantendo che abbiano l'attributo .arity() richiesto dai test.

app/logic_feedback.py
1. Import Not da Z3
from z3 import Solver, BoolRef, sat, unsat, unknown, Not, And, Or
Spiegazione: Aggiunto l'import esplicito di Not per risolvere il NameError.

2. Uso di model_dump() per Pydantic v2
# Prima: prog_dict = logic_program.dict()
# Ora: 
if isinstance(logic_program, LogicProgram):
    prog_dict = logic_program.model_dump()
else:
    prog_dict = dict(logic_program)
Spiegazione: Sostituiti tutti i casi di .dict() con .model_dump() per compatibilità con Pydantic v2.

3. Logica di Entailment Corretta
if check_status == sat:
    if query_symbol is not None:
        # Create temporary solver and add negated query
        tmp = Solver()
        for a in solver.assertions():
            tmp.add(a)
        tmp.add(Not(query_symbol))
        entail_check = tmp.check()
        
        if entail_check == unsat:
            # Query is entailed: no model exists where query is false
            status_code = "consistent_entails"
            human_summary = "Il sistema logico è coerente e implica la conclusione."
        else:
            # Query is not entailed: there exists a model where query is false
            status_code = "consistent_no_entailment"
            human_summary = "Il sistema è coerente ma la conclusione non è dimostrabile."
Spiegazione: Implementata la logica corretta per l'entailment check: se il solver con la query negata è UNSAT, allora la query è logicamente implicata.

Guida ai Test
Comandi di Verifica (Windows PowerShell)
# Assicurarsi di essere nell'ambiente virtuale corretto
.venv_nsla_v2\Scripts\Activate.ps1

# Test specifici della Fase 1
pytest -v tests/test_translator_v2.py -k "test_simple_predicate_parsing_v21 or test_minimal_v21_program" --maxfail=1
pytest -v tests/test_logic_feedback.py -k "test_consistent_entails_feedback or test_inconsistent_feedback" --maxfail=1

# Test completi della suite
pytest -v --maxfail=1 --disable-warnings
Risultati Attesi
test_simple_predicate_parsing_v21: ✅ PASS (predicati con .arity())
test_minimal_v21_program: ✅ PASS (solver con ≥2 asserzioni)
test_consistent_entails_feedback: ✅ PASS (status = "consistent_entails")
test_inconsistent_feedback: ✅ PASS (status = "inconsistent")
Note Future
Estensioni Potenziali
Parsing di Regole Complesse: Supportare regole con congiunzioni, disgiunzioni e quantificatori
Gestione degli Args: Implementare parsing corretto degli argomenti per predicati con arità > 0
Unsat Core Avanzato: Migliorare l'estrazione e l'identificazione degli assiomi conflittuali
Miglioramenti di Logging
Aggiungere logging dettagliato per il parsing delle regole
Implementare tracer per il processo di entailment checking
Logging delle metriche di performance per solver complessi
Test Aggiuntivi Suggeriti
Test di regressione per backward compatibility con DSL v1
Test di edge cases (regole vuote, predicati non definiti)
Test di performance con programmi logici di grandi dimensioni
Manutenzione
Monitorare l'aggiornamento di Pydantic e Z3 per compatibilità futura
Documentare meglio le assunzioni sui formati delle regole DSL v2.1
Considerare refactoring del parsing per maggiore modularità
Status: ✅ Correzioni applicate e testati
Data:  November 2025
Responsabile: Senior Neuro-Symbolic Engineer

---

# NSLA v2 – Phase 2 Report (Two-pass runtime)

## Deliverable principali
- **Runtime dedicati** per Phase 2:
  - `canonicalizer_runtime.py`: caching + fallback deterministico del canonicalizer.
  - `structured_extractor.py`: enforcement `dsl_version=2.1`, fallback al programma v1 e logging delle statistiche.
  - `refinement_runtime.py`: integrazione del prompt Phase 2.3 con `previous_answer` e `history_summary`.
- **Pipeline aggiornata** (`pipeline_v2.py`):
  - `_prepare_phase2_context` esegue canonicalizer → extractor → translator/Z3 → feedback_v1.
  - `run_once` restituisce `Phase2RunResult` arricchito (canonicalization, logic_program_v1, feedback_v1, answer_v1, eventuale fallback).
  - Endpoint `/legal_query_v2` esporta ora l’intero contesto Phase 2.
- **Prompt Phase 2.3 ottimizzato** (`resources/prompts/prompt_phase_2_3_refinement_llmoutput_v2.txt`): nuova sezione `history_summary` per guidare le correzioni incrementali.
- **Test nuovi**: `tests/test_phase2_runtimes.py` copre cache canonicalizer, fallback extractor e gestione history nel refinement runtime.

## Verifica
```
pytest tests/test_phase2_runtimes.py -q
pytest tests/test_guardrail_checker.py -q
pytest -q       # suite completa (57 test green)
```

---

# NSLA v2 – Phase 3 Report (Iteration Manager)

## Obiettivi raggiunti
- **IterationManager** (`app/iteration_manager.py`):
  - gestisce `max_iters`, early-stop su `stop_on_status`, detection di stalli (missing/conflicts invariati).
  - delega al nuovo `HistorySummarizer` per fornire contesto al prompt Phase 2.3 durante le iterazioni successive.
- **Pipeline iterativa** (`NSLAPipelineV2.run_iterative`):
  - riusa `_prepare_phase2_context` e delega tutto al manager.
  - l’endpoint `/legal_query_v2_iterative` continua a generare guardrail + explanation sul best state.
- **Test dedicati** (`tests/test_iteration_manager.py`):
  - stop immediato su `consistent_entails`.
  - rilevazione di iterazioni identiche.
  - rispetto del limite `max_iters`.

## Note operative
- Il prompt Phase 2.3 ora riceve `history_summary`, riducendo oscillazioni.
- `RefinementRuntime` espone fallback deterministico in caso di failure dell’LLM.
- `Phase2RunResult` include `answer_v1`, `feedback_v1`, `canonicalization` per facilitare l’analisi da UI/benchmark.

## Comando di regressione completo
```
cmd /c "cd /d C:\Users\matte\Desktop\Desktop OLD\AI\UNIVER~1\courses\computational_logic\resources\book\neurosimbolic_project_v2 && .\.venv_nsla_v2\Scripts\python.exe -m pytest -q"
```

Esito: ✅ 57 passed / 0 failed (inclusi i nuovi test Phase 2/3).

---

# Aggiornamento Fase 1 (Translator) e UI/Benchmark

## Translator & logic tests
- Suite Phase 1 verificata nuovamente (`pytest tests/test_translator_v2.py -q`): **13 test passati**.
- Nessun warning residuo: i parser di regole, literal `true/false` e S-expression vengono coperti dallo scenario `test_v21_rules_parsing`.

## UI (M1) potenziata
- `app/templates/index.html` ora consente di scegliere fra:
  - `legal_query` (NSLA v1)
  - `legal_query_v2` (two-pass con guardrail + explanation)
  - `legal_query_v2_iterative` (loop controllato con history).
- Ogni risposta mostra:
  - badge di verifica o stato guardrail a seconda della pipeline,
  - missing links/conflicts,
  - spiegazione Phase 2,
  - history completa delle iterazioni con stato/missing associati,
  - dump JSON raw per il debug front-end.

## Benchmark arricchito (`app/benchmark.py`)
- Per ciascun caso vengono salvati anche:
  - risposta/stato di NSLA v2 (feedback, guardrail, fallback, explanation),
  - risposta/stato della modalità iterativa (best iteration, guardrail, history size),
  - metriche EM/F1/BLEU e tempi dedicati (con delta rispetto a v1),
  - flag di accuratezza per tutte le modalità.
- Report finale stampa ora Accuracy/EM/F1 per **LLM-only**, **NSLA v1**, **NSLA v2** e **NSLA iterativa** più i tempi medi con deviazione standard.

---

# Phase 4 – Dataset & Metrics Kickoff

## Dataset espanso (24 casi)
- `data/cases_dev.json` include ora 24 casi etichettati con `tags` roadmap e `gold_variants` per ogni risposta.
- Nuovi domini coperti: lavoro, consumo, responsabilità medica, IP, trasporti, procedura civile.
- Ogni record è pronto per essere consumato sia dal benchmark sia dal prossimo layer di annotazioni (es. judge LLM).

## Benchmark aggiornato
- `app/benchmark.py` registra `tag_stats`, `v2_guardrail_pass_rate`, `iter_guardrail_pass_rate` e salva i riepiloghi in `logs/benchmark_*.json`.
- Ultima corsa (15 Nov 2025, dataset 24) → F1 LLM-only 11.5 %, NSLA v1/v2 ~19 %, tempi medi <30 ms perché backend dummy.
- `resources/nsla_v2/reports/phase2_vs_phase1.md` contiene sia il run storico (15 casi) sia il nuovo snapshot (24 casi) con note su guardrail e next steps.
- Per riprodurre rapidamente i fallimenti di un singolo caso ora è disponibile il filtro CLI `--case-id` (ripetibile).  
  Esempio (solo `case_003`, dummy backend locale):
  ```powershell
  powershell -NoLogo -NoProfile -Command "
    cd 'C:\Users\matte\Desktop\Desktop OLD\AI\UNIVER~1\courses\computational_logic\resources\book\neurosimbolic_project_v2';
    .\.venv_nsla_v2\Scripts\python.exe app\benchmark.py --case-id case_003 --output data\results_case003.csv --timeout-v2 600 --timeout-iter 900
  "
  ```
  Se l'ID non è presente in `data/cases_dev.json`, il benchmark termina immediatamente senza chiamare gli endpoint FastAPI e stampa la lista degli ID mancanti.

## Fix console warning
- `StructuredExtractorRuntime` arricchisce i programmi con sorts estratte da `legal_it_v1.yaml`; `_parse_function_call` usa placeholder tipizzati. I warning “Unknown sort type 'Contratto'” e gli errori “Sort mismatch” spariscono dopo il restart.

## Ontologia civile/penale allineata
- `resources/ontology/legal_it_v1.yaml`, `app/logic_dsl.py` e `resources/nsla_v2/logic_dsl_v2.md` includono ora predicati che coprono consumer law (`DifettoConformita`, `DirittoSceltaRemedy`), proprietà (`UsucapioneOrdinaria/Abbreviata`), IP (`ContraffazioneMarchio`), penale (`Riciclaggio`, `MisuraCautelare*`, `Multa/Ammenda`) e procedure (`SospensioneEsecuzioneForzata`), in coerenza con Codice Civile e Codice Penale (Regio Decreto 19 ottobre 1930, n. 1398 – fonte Normattiva).
- I prompt Phase 2.1/2.2/2.3 ricordano espressamente di usare il vocabolario canonico e di modellare axioms/regole con formule ben formate, riducendo `UNKNOWN_PREDICATE_DECLARATION` e `Axiom missing formula` in console.

## Judge runtime + metriche Phase 4
- Nuovo modulo `app/judge_runtime.py` + prompt dedicato (`resources/prompts/judge/prompt_phase_4_judge_metric.txt`).
- `NSLAPipelineV2.run_once` può ricevere `reference_answer` e, se il guardrail passa, registra `judge_result` (baseline v1 vs NSLA v2).
- Endpoint FastAPI `POST /judge_compare` espone il servizio di confronto generico (usato anche dal benchmark).
- Config flag: `enable_judge_metric` per abilitare/disabilitare le chiamate reali.
- Benchmark CSV ora salva:
  - `v2_judge_vote`, `v2_judge_confidence`, `v2_judge_rationale`;
  - `judge_vote`, `judge_confidence`, `judge_rationale` per il confronto LLM-only vs NSLA (flag `--judge`).

## Test mirati Phase 4
- `tests/test_structured_extractor_ontology.py` verifica che l’estrattore idrati sorts/predicati mancanti usando l’ontologia.
- `tests/test_phase2_guardrail_pass.py` fornisce un programma canonico che deve passare `run_guardrail` (nessun fallback).
- `tests/test_judge_runtime.py` assicura che il Judge runtime resti sicuro in backend dummy.

## Next steps Phase 4
1. Validare il prompt del judge con run reali (`enable_judge_metric=True` + backend cloud) e calibrare soglie di confidenza.
2. Estendere i test Phase 4 con casi iterativi: best iteration che supera guardrail + spiegazione.
3. Aggiornare `resources/nsla_v2/reports/phase2_vs_phase1.md` con i nuovi campi (judge, ontologia) dopo il prossimo benchmark.

---

# Backend reale (Ollama + kimi-k2 1T cloud)

## Configurazione
- Impostare le variabili prima di avviare FastAPI:
  ```
  set NSLA_LLM_BACKEND=ollama
  set NSLA_OLLAMA_MODEL=kimi-k2:1t-cloud
  ```
- Verificare la presenza del modello con `ollama list` (vedi voce `kimi-k2:1t-cloud`).
- Avviare l’app: `uvicorn app.main:app --reload`.

## Benchmark con judge LLM
- Per attivare il confronto LLM-only vs NSLA usare:
  ```
  python app/benchmark.py --url http://127.0.0.1:8000 --cases data/cases_dev.json --output data/results.csv --judge
  ```
- Il campo `nsla_win_rate` nel riepilogo indica la percentuale di casi in cui il judge preferisce NSLA (0 % sulla baseline dummy: il prompt del judge ritorna sempre `tie`).

## Note operative
- Con backend reale, `/llm_only`, `/legal_query_v2`, `/legal_query_v2_iterative` produrranno output effettivi e il guardrail potrà finalmente validare logiche non dummy.
- I log “Canonicalizer completed: 0 concepts” spariscono appena il canonicalizer LLM restituisce l’estrazione prevista dal prompt.