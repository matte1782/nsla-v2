# Piano operativo MVP – Neuro-Symbolic Legal Assistant (LLM + SMT)

Autore: Matteo Panzeri – Università di Pavia  
Obiettivo: implementare un **MVP semplice, veloce e scalabile** per migliorare la coerenza logica degli LLM con uno **strato simbolico (Z3)** post-output.

---

## 1. Struttura generale del sistema (MVP)

### 1.1 Componenti principali

- **UI Web minimale**  
  Interfaccia per inserire la domanda e visualizzare:
  - risposta dell’LLM;
  - stato di verifica logica (verified ✅ / not verified ⚠️);
  - (opzionale) dettagli logici.

- **API Backend (FastAPI)**  
  - Punto centrale di orchestrazione.
  - Riceve la query, chiama il modulo LLM, costruisce DSL logica, chiama Z3, applica i multi-check e genera la risposta finale.

- **Modulo LLM (via Ollama)**  
  - LLM locale (es. `qwen2.5:7b` o `llama3:8b`).
  - Genera JSON strutturato: premesse, conclusione, `logic_program` DSL.

- **Modulo di Pre-Processing & Facts**  
  - Esegue una normalizzazione minima della domanda.
  - Estrae fatti numerici e simbolici rilevanti (es. mesi di lavoro, soglie).

- **Modulo DSL logica (JSON) + Validazione**  
  - Definisce uno schema chiaro per `logic_program`.
  - Valida che l’LLM produca un JSON conforme.

- **Modulo Translator DSL → Z3**  
  - Converte il DSL in oggetti Z3 (sort, funzioni, predicati, assiomi, query).

- **Multi-Check Orchestrator + Feedback loop**  
  - Esegue controlli: sintassi/tipo, consistenza, fact-alignment.
  - In caso di errori, genera feedback strutturato per far rigenerare all’LLM solo la parte logica.

- **Benchmark & Logging**  
  - Script dedicato per eseguire test batch e raccogliere metriche.

### 1.2 Flusso dei dati (alto livello)

```text
[Utente] → [UI Web]
        → HTTP POST /legal_query
        → [API Backend]
            → [Pre-Processing & Facts]
            → [LLM via Ollama → JSON strutturato]
            → [Validazione DSL]
            → [Translator DSL → Z3]
            → [Multi-Check (Z3)]
            → [Feedback loop (se necessario)]
        → [Output finale JSON]
        → [UI Web: risposta + stato verifica]
```

---

## 2. Moduli indipendenti – descrizione dettagliata

### M0 – Config & Types Core

- **Funzione concreta**  
  Racchiude configurazione globale e tipi di base.

- **Input**  
  - File `.env` o YAML con:
    - modello LLM da usare;
    - timeouts Z3;
    - numero massimo di iterazioni del feedback loop;
    - flag per abilitare/disabilitare il layer logico.

- **Output**  
  - Oggetto `Settings` (Pydantic) accessibile da tutti i moduli.

- **Tecnologie consigliate**  
  - `pydantic` / `pydantic-settings`
  - `python-dotenv`
  - `logging`

- **Estensioni future**  
  - Config per ambienti diversi (dev / prod).
  - Feature flags per attivare futuri moduli (RAG, multi-solver, ecc.).

---

### M1 – UI Web minimale

- **Funzione concreta**  
  Interfaccia semplice per interrogare il sistema e visualizzare risultati.

- **Input**  
  - Testo della domanda dell’utente.

- **Output**  
  - Risposta in linguaggio naturale.
  - Flag `verified` (true/false/unknown).
  - (Opzionale) dettagli logici: trace, formule chiave.

- **Tecnologie consigliate**  
  - Opzione A (tutto in un backend):
    - `FastAPI` + `Jinja2` (template HTML minimal + un po’ di CSS).
  - Opzione B (se si preferisce separare):
    - `Streamlit` che chiama l’API backend.

- **Estensioni future**  
  - Visualizzazione grafica del grafo logico (premesse → conclusione).
  - Filtri per vedere solo i casi non verificati.
  - Pannello “metriche” (per i benchmark).

---

### M2 – API Backend (FastAPI Gateway)

- **Funzione concreta**  
  Entry point del sistema. Espone:
  - `/health` – check rapido.
  - `/llm_only` – baseline senza layer logico.
  - `/legal_query` – pipeline completa LLM+SMT.
  - (Opzionale) `/benchmark/run` – esecuzione batch test.

- **Input**  
  - `POST /legal_query` con JSON:
    ```json
    {
      "question": "...",
      "meta": {"domain": "legal"}
    }
    ```

- **Output**  
  ```json
  {
    "answer": "...",
    "verified": true,
    "checks_passed": ["syntax", "consistency"],
    "logical_trace": ["..."],
    "raw_logic": {...},
    "timing_ms": {
      "llm": 1200,
      "smt": 50,
      "total": 1300
    }
  }
  ```

- **Tecnologie consigliate**  
  - `fastapi`, `uvicorn`, `pydantic`.

- **Estensioni future**  
  - Autenticazione (API key, JWT).
  - Rate limiting.
  - Versioning degli endpoint.

---

### M3 – Pre-Processing & Facts Builder

- **Funzione concreta**  
  - Pulizia e normalizzazione della domanda.
  - Estrazione di fatti rilevanti per il caso (es. numeri, date, soglie) che diventano hard constraints per Z3.

- **Input**  
  - `question: str` dall’utente.

- **Output**  
  ```python
  {
    "normalized_question": "...",
    "facts": {
      "LavoroMesi(Mario)": 8,
      "SogliaMesi": 6
    }
  }
  ```

- **Tecnologie consigliate**  
  - MVP: `re` (regex), funzioni Python.
  - Facoltativo: `spacy` con modello italiano per NER (nomi propri, date).

- **Estensioni future**  
  - Integrazione con un motore RAG per recuperare clausole contrattuali standard.
  - Miglior pipeline NLU con modelli dedicati legal-domain.

---

### M4 – LLM Reasoning & JSON Generator (Ollama Client)

- **Funzione concreta**  
  - Chiamare un modello servito da **Ollama**.
  - Ottenere un **JSON strutturato** contenente:
    - `final_answer`
    - `premises`
    - `conclusion`
    - `logic_program` (DSL logica JSON)

- **Input**  
  - `normalized_question`
  - `facts` (eventualmente inseriti nel prompt come contesto)

- **Output**  
  Oggetto Python (Pydantic) tipo:
  ```python
  LLMOutput(
      final_answer: str,
      premises: List[str],
      conclusion: str,
      logic_program: LogicProgram
  )
  ```

- **Tecnologie consigliate**  
  - Ollama installato localmente.
  - Chiamata via `subprocess` o API HTTP.
  - `pydantic` per validare il JSON.

- **Estensioni future**  
  - Supporto per più modelli LLM selezionabili da config.
  - Miglioramento del prompt engineering (few-shot, esempi legali).

---

### M5 – DSL Logic Schema & Validator

- **Funzione concreta**  
  - Definire e documentare la DSL logica (in JSON) che l’LLM deve produrre.
  - Validare che `logic_program` soddisfi lo schema.

- **Input**  
  - `logic_program` (dict) generato dall’LLM.

- **Output**  
  - Oggetto `LogicProgram` validato (Pydantic) **oppure** eccezione di validazione.

- **Tecnologie consigliate**  
  - `pydantic` per lo schema.

- **Estensioni future**  
  - Versioning della DSL (`version: 1`, `2`, ...).
  - Supporto a più dialetti (es. JSON DSL + SMT-LIB testuale).

---

### M6 – Translator DSL → Z3

- **Funzione concreta**  
  - Convertire `LogicProgram` + `facts` in:
    - un solver Z3 con tutte le asserzioni;
    - una formula Z3 `query` corrispondente alla conclusione da verificare.

- **Input**  
  - `logic_program: LogicProgram`
  - `facts: dict`

- **Output**  
  ```python
  solver: z3.Solver
  query: z3.BoolRef  # formula della conclusione
  ```

- **Tecnologie consigliate**  
  - `z3-solver` (Python API).

- **Estensioni future**  
  - Uso di `pysmt` per mantenere l’API solver-agnostic.
  - Supporto a teorie aggiuntive (reali, bitvector, array) se servono.

---

### M7 – Multi-Check Orchestrator & Feedback Loop

- **Funzione concreta**  
  - Eseguire i controlli logici:
    1. **Syntax/Type check**: verifica che la traduzione DSL→Z3 non generi errori.
    2. **Consistency check**: aggiunge `Not(query)` e chiama `solver.check()`.
    3. **Fact-alignment check**: se SAT, confronta il modello con i `facts`.
  - In caso di problemi, creare un messaggio di feedback per l’LLM e rigenerare `logic_program` (max N volte).

- **Input**  
  - `solver`, `query`, `facts`, `LLMOutput` originale.

- **Output**  
  ```python
  {
    "verified": True/False,
    "checks_passed": [...],
    "error_type": None or "syntax"/"consistency"/"fact_mismatch",
    "logical_trace": [...],
    "model_snippet": {...}  # opzionale
  }
  ```

- **Tecnologie consigliate**  
  - `z3-solver` per `check()`, `model()`, `unsat_core()`.

- **Estensioni future**  
  - Counterfactual robustness (modificando parametri nel solver).
  - Supporto a MaxSMT (soft constraints) per gestire assunzioni deboli.

---

### M8 – Benchmark & Evaluation Harness

- **Funzione concreta**  
  - Fornire script/test per eseguire batch di casi e calcolare metriche.

- **Input**  
  - File `cases_dev.json` con micro-casi:
    ```json
    {
      "id": 1,
      "question": "...",
      "gold_answer": true
    }
    ```

- **Output**  
  - CSV risultati: baseline LLM-only vs LLM+SMT.
  - Metriche aggregate.

- **Tecnologie consigliate**  
  - `pytest` o script Python semplice.
  - `pandas` per analisi.

- **Estensioni future**  
  - Integrazione con sistemi di tracking esperimenti (MLflow, W&B).
  - Dashboard metriche (Grafana/Metabase).

---

## 3. Step operativi – da zero all’integrazione funzionante

### 3.1 Setup iniziale

- **Prerequisiti**
  - OS: Linux/macOS o WSL.
  - Python ≥ 3.10.

- **Installazioni base**
  ```bash
  # Repo Python
  mkdir nsla && cd nsla
  python -m venv .venv
  source .venv/bin/activate  # o equivalente su Windows

  pip install fastapi uvicorn pydantic z3-solver pandas
  pip install jinja2  # se si usano template HTML

  # Ollama (da sito ufficiale)
  # Dopo l'installazione:
  ollama pull qwen2.5:7b  # o llama3
  ```

- **Struttura repo consigliata**
  ```text
  nsla/
    app/
      main.py          # FastAPI – M2, wiring generale
      config.py        # M0
      models.py        # Pydantic (LLMOutput, LogicProgram, ecc.)
      llm_client.py    # M4
      preprocessing.py # M3
      logic_dsl.py     # M5
      translator.py    # M6
      checker.py       # M7
      benchmark.py     # M8 (script)
      templates/       # M1 (HTML)
    data/
      cases_dev.json   # micro-casi
    tests/
      test_logic.py
      test_end_to_end.py
    README.md
  ```

---

### 3.2 Fase 1 – Pipeline LLM-only (baseline)

1. Implementare `llm_client.py` (M4) con funzione:
   ```python
   def ask_llm(question: str) -> str:
       # chiama ollama e restituisce una risposta testuale semplice
   ```

2. In `main.py` (FastAPI):
   - Endpoint `/llm_only` che accetta `question` e restituisce `{"answer": ...}`.

3. Test rapido:
   ```bash
   uvicorn app.main:app --reload
   # chiamata da curl o browser
   ```

---

### 3.3 Fase 2 – Aggiungere JSON strutturato (premesse, conclusione, logic_program)

1. Definire in `models.py` i modelli `LLMOutput` e `LogicProgram` (M4 + M5).
2. Modificare `ask_llm` per chiedere **solo JSON** (prompt few-shot).
3. Aggiungere endpoint `/llm_structured` per vedere il JSON grezzo.
4. Testare:
   - percentuale di risposte che fanno parse corretto.

---

### 3.4 Fase 3 – Traduzione DSL → Z3

1. Implementare `translator.py` (M6) con funzione:
   ```python
   def build_solver(logic_program: LogicProgram, facts: dict) -> tuple[Solver, BoolRef]:
       ...
   ```

2. Implementare `preprocessing.py` (M3) per estrarre `facts` minimi.
3. Aggiungere endpoint `/debug_logic` che:
   - prende la domanda;
   - chiama LLM structured;
   - costruisce solver e query;
   - ritorna `sat/unsat/unknown`.

---

### 3.5 Fase 4 – Multi-Check & Feedback

1. Implementare `checker.py` (M7) con funzioni:
   - `run_checks(solver, query, facts) -> dict`
   - `maybe_repair_with_feedback(...) -> dict` (loop max N).

2. In `main.py`, endpoint `/legal_query`:
   - orchestrare M3 → M4 → M5 → M6 → M7;
   - costruire risposta finale JSON.

3. Test end-to-end su pochi casi manuali.

---

### 3.6 Fase 5 – UI Web minimale

1. Creare template HTML (M1) con:
   - `textarea` per domanda;
   - bottone INVIA;
   - area risposta + badge `Verified`.

2. Collegare il form a `/legal_query` (POST) e mostrare il risultato.

---

### 3.7 Fase 6 – Benchmark iniziale

1. Creare `data/cases_dev.json` con 20–30 micro-casi (domande + `gold_answer`).
2. Implementare `benchmark.py` (M8) per:
   - iterare sui casi;
   - chiamare `/llm_only` e `/legal_query`;
   - salvare risultati in CSV;
   - calcolare metriche.

---

## 4. Benchmark & metriche per modulo e sistema

### 4.1 Metriche per modulo

- **M4 – LLM Reasoning**
  - `% JSON validi` (parse OK / totale).
  - `% logic_program presenti`.

- **M5/M6 – DSL & Translator**
  - `% traduzioni senza eccezioni Z3`.
  - Tempo medio di costruzione solver.

- **M7 – Multi-Check**
  - `% casi con `verified=True`.
  - `% correzioni riuscite` (errori risolti entro N iterazioni).
  - Tempo medio check SMT.

### 4.2 Metriche di sistema (end-to-end)

- **Accuracy task-specific**  
  - `# risposte corrette / # casi` per:
    - baseline LLM-only;
    - NSLA (LLM+SMT).

- **Contradiction Rate**  
  - `% risposte LLM-only che risultano logicamente inconsistenti sotto verifica Z3`.

- **Improvement Rate**  
  - `Accuracy(NSLA) – Accuracy(LLM-only)` (punti percentuali).

- **Latency Overhead**  
  - `tempo_medio_NSLA / tempo_medio_LLM-only`.

- **Qualità percepita (opzionale)**  
  - Valutazione soggettiva (es. scala 1–5) su chiarezza delle spiegazioni.

---

## 5. Strategie di scalabilità futura

- **Separazione chiara dei moduli**  
  Ogni modulo in file/namespace separato, con API ben definite. Così è facile:
  - spostare il modulo LLM su un servizio separato;
  - spostare la parte Z3 su un “logic service” se crescerà.

- **Astrazione dei client**  
  - Definire interfacce:
    - `LLMClient` (oggi: `OllamaClient`, domani: `OpenAIClient` ecc.).
    - `LogicEngine` (oggi: Z3, domani: CVC5, Prover9).

- **Config-driven design**  
  - Tutte le scelte (modello, timeouts, max_iter, abilita_layer_logico) sono in config (M0), non hard-coded.

- **DSL versionata**  
  - Aggiungere un campo `dsl_version` in `logic_program`; permette di evolvere la rappresentazione senza rompere il vecchio codice.

- **Supporto a job asincroni (in futuro)**  
  - Se i casi diventano pesanti:
    - introdurre una coda (Redis + RQ/Celery);
    - eseguire la pipeline come job;
    - far controllare all’utente lo stato con un `job_id`.

- **Benchmark continuo**  
  - Integrare `benchmark.py` in una pipeline CI (anche locale) per assicurarsi che modifiche future non peggiorino le metriche chiave.

---

Questo piano operativo rende il progetto:
- immediatamente implementabile (MVP step-by-step),
- chiaro e leggibile per altri collaboratori (moduli indipendenti e documentati),
- pronto per una validazione scientifica tramite benchmark semplici ma significativi,
- già pensato per scalare nel lungo periodo se i risultati sperimentali saranno positivi.

