1. Struttura generale del sistema (MVP)

Vista ad alto livello (solo i pezzi minimi):

[Web UI] 
   ↓ HTTP
[API Backend (FastAPI)]
   ↓
[Modulo LLM (Ollama)]
   ↓ JSON strutturato (premesse, conclusione, logic_program)
[Modulo Logico (Z3 + Translator)]
   ↓ esito SAT/UNSAT + modello/unsat-core
[Multi-Check & Feedback]
   ↓
[Risposta finale + trace logico] → Web UI


Componenti principali:

Web UI minimale (form + risultati)

API Backend (FastAPI)

Client LLM (Ollama)

Modulo di pre-processing & KB di fatti

Modulo DSL logica (JSON) + validazione schema

Traduttore DSL → Z3

Multi-Check Orchestrator + feedback loop

Harness di benchmark & logging

2. Moduli indipendenti (dettaglio)
M0 – Core & Config

Funzione
Configurazione condivisa e tipi di base (Pydantic models, costanti, logging).

Input / Output

Input: file .env / config YAML (modello LLM, timeouts, numero max iterazioni, ecc.)

Output: oggetti di configurazione Python (es. Settings) usati dagli altri moduli.

Tecnologie

pydantic, python-dotenv o pydantic-settings, logging.

Estensioni future

Config per ambienti diversi (dev / prod).

Feature flags (es. abilita/disabilita feedback loop, abilita RAG, ecc.).

M1 – Web UI (Frontend minimal)

Funzione
Fornire un’interfaccia semplicissima in cui:

inserire il quesito;

visualizzare risposta e stato di verifica logica.

Input / Output

Input: testo della domanda (es. caso legale).

Output:

risposta naturale;

indicatori tipo “Verified: ✅/❌”;

link/box “Mostra dettagli logici”.

Tecnologie

MVP:

HTML+CSS minimale + template di FastAPI oppure

streamlit che chiama l’API backend.

Scelta rapida: FastAPI + Jinja2 (tutto in un repo).

Estensioni future

Visualizzazione grafo logico (premesse → conclusione).

Filtri per vedere solo i casi “non verificati”.

Dashboard metriche (accuracy, tempi, ecc.).

M2 – API Backend (Gateway REST)

Funzione

Esporre endpoint tipo /legal_query, /health, /benchmark/run.

Orchestrare la pipeline chiamando M3–M7.

Input / Output

Input: POST /legal_query con JSON { "question": "...", "meta": {...} }

Output:

{
  "answer": "...",
  "verified": true,
  "checks_passed": ["syntax", "consistency"],
  "logical_trace": [...],
  "raw_logic": {...},
  "timing_ms": {...}
}


Tecnologie

fastapi, uvicorn, pydantic.

Estensioni future

Authentication (token, API key).

Throttling / rate limiting.

Multi-tenant (diversi progetti / dataset).

M3 – Pre-Processing & Facts Builder

Funzione

Fare un pre-processing leggero del testo:

estrarre numeri, date, nomi (anche solo con regex semplici);

costruire una mini-KB di fatti ground da usare nel check logico.

Input / Output

Input: stringa question.

Output:

{
  "normalized_question": "...",
  "facts": {
    "LavoroMesi(Mario)": 8,
    "SogliaMesi": 6
  }
}


Tecnologie

MVP: re (regex) e funzioni Python.

Se vuoi: spacy con modello italiano per NER.

Estensioni future

Modello dedicato per estrazione di clausole legali.

Integrazione con RAG (retrieval di norme da database esterno).

M4 – LLM Reasoning & JSON Generator (client Ollama)

Funzione

Chiamare Ollama con un prompt ben definito e ottenere un JSON strutturato:

final_answer

premises

conclusion

logic_program (DSL logica)

Input / Output

Input: normalized_question + facts (from M3).

Output: oggetto Python (Pydantic) con i campi sopra.

Tecnologie

subprocess o chiamata HTTP a Ollama:

ollama run qwen2.5:7b -p "<prompt>".

pydantic per validare lo schema.

Estensioni future

Supporto a più LLM (modello configurabile).

Prompt dinamici in base al tipo di caso (contratto, licenziamento, ecc.).

M5 – DSL Validator & Translator → Z3

Funzione

Validare che logic_program rispetti uno schema semplice.

Tradurlo in oggetti Z3:

sort, funzioni, predicati, asserzioni, query.

Input / Output

Input: logic_program (dict) + facts (da M3).

Output:

oggetto Solver Z3 con tutte le asserzioni caricate;

oggetto Z3 query (formula che rappresenta la conclusione da verificare).

Tecnologie

z3-solver (Python).

pydantic per lo schema DSL:

class LogicProgram(BaseModel):
    sorts: Dict[str, Any]
    constants: Dict[str, Any]
    axioms: List[FormulaSpec]
    query: str


Estensioni future

Supporto a SMT-LIB testuale in aggiunta al DSL JSON.

Abstraction layer tipo pysmt per supportare altri solver oltre a Z3.

M6 – Multi-Check Orchestrator & Feedback Loop

Funzione

Lanciare sequenzialmente:

syntax/type check del DSL e della traduzione in Z3;

consistency check (premesse + negazione conclusione);

fact-alignment check (modello vs facts).

Se fallisce qualcosa → costruire prompt di correzione per l’LLM (solo logic_program).

Input / Output

Input: solver, query, facts, output LLM originale.

Output:

{
  "verified": True/False,
  "checks_passed": [...],
  "error_type": None or "syntax"/"consistency"/"fact_mismatch",
  "logical_trace": [...],  # stringhe con formule chiave
  "model_snippet": {...}   # opzionale
}


Tecnologie

z3-solver per check(), modelli e unsat-core.

Funzioni Python per generare prompt di feedback.

Estensioni future

Counterfactual checks (variare parametri e controllare comportamento).

MaxSMT (soft constraints) per separare assunzioni forti/deboli.

M7 – Benchmark & Evaluation Harness

Funzione

Eseguire in batch un set di micro-casi di test:

run LLM-only;

run pipeline LLM+SMT;

calcolare metriche.

Input / Output

Input: file JSON/CSV con casi di test:

{ "id": 1, "question": "...", "gold_answer": true }


Output:

file CSV con risultati per caso (baseline vs NSLA);

statistiche aggregate (accuracy, contraddictions, tempi).

Tecnologie

pytest o semplice script Python.

pandas per analisi risultati.

Estensioni future

Integrazione con strumenti tipo MLflow / Weights & Biases per tracking esperimenti.

Dashboard (Grafana, ecc.) per vedere performance nel tempo.

3. Step operativi: da zero al prototipo funzionante
Fase 0 – Setup ambiente

Prerequisiti

OS: Linux o macOS (ok anche WSL).

Python ≥ 3.10.

Installazioni base

# Python deps
pip install fastapi uvicorn pydantic z3-solver pandas

# (facoltativo) per UI semplice
pip install jinja2

# Installare Ollama
# -> scarica da sito ufficiale, poi:
ollama pull qwen2.5:7b  # o llama3


Repo struttura consigliata

nsla/
  app/
    main.py          # FastAPI
    config.py        # M0
    models.py        # Pydantic models
    llm_client.py    # M4
    preprocessing.py # M3
    logic_dsl.py     # M5
    checker.py       # M6
    benchmark.py     # M7
    templates/       # M1 (HTML)
  tests/
    test_logic.py
    test_end_to_end.py
  data/
    cases_dev.json   # micro-casi benchmark
  README.md

Fase 1 – LLM-only pipeline

Implementa M2 + M4 con un endpoint /llm_only.

Input: domanda → output: solo final_answer (senza DM logica).

Test rapido via curl o browser:

uvicorn app.main:app --reload
curl -X POST ... /llm_only

Fase 2 – Aggiungere DSL logica e Z3

Implementa schema logic_program in models.py (M5).

Modifica llm_client.py (M4) per chiedere all’LLM il JSON completo.

Implementa traduttore DSL → Z3 (M5).

Crea endpoint /debug_logic che:

riceve question;

stampa su log il DSL;

esegue solo check() Z3 e ritorna SAT/UNSAT.

Fase 3 – Multi-Check & Feedback (M6)

Implementa funzioni:

syntax_check(logic_program)

consistency_check(solver, query)

fact_alignment_check(model, facts)

Implementa un loop massimo di 2–3 iterazioni:

se fallisce → crea prompt tipo:
“Hai usato una formula non valida X, rigenera solo la sezione logic_program.”

Crea endpoint /legal_query che usa l’intera pipeline.

Fase 4 – Web UI minimale (M1)

Aggiungi pagina HTML con:

<textarea> per domanda;

bottone “Invia”;

box per risposta e stato verified.

Collega la form a /legal_query via JS o form POST.

Fase 5 – Benchmark base (M7)

Crea data/cases_dev.json con 20–30 casi (domande + gold_answer).

Implementa benchmark.py che:

per ogni caso:

chiama LLM-only (M4 isolato);

chiama pipeline completa /legal_query;

calcola:

accuracy LLM-only vs NSLA;

% casi dove Z3 segnala inconsistenza;

tempi medi.

Esegui e salva i risultati in CSV in data/results.csv.

4. Benchmark: valutare moduli e sistema
A. Metriche per modulo

M4 – LLM Reasoning

% JSON validi (parsing OK / totale).

% logic_program presenti e non vuoti.

M5 – DSL → Z3

% traduzioni senza eccezioni (nessun crash di Z3).

% formule con tipi coerenti (no errori di sort).

M6 – Multi-Check

% casi con verified=True`.

% correzioni riuscite (feedback loop che porta da errore a successo).

tempo medio check (ms).

B. Metriche di sistema (end-to-end)

Accuracy task-specific:

risposte corrette (true/false) vs gold.

Contradiction Rate:

% di risposte LLM-only che risultano logicamente inconsistenti quando verificate da Z3.

Improvement Rate:

Accuracy(NSLA) - Accuracy(LLM-only) in punti percentuali.

Latency Overhead:

tempo_NSLA / tempo_LLM-only.

Qualità percepita (opzionale):

tu + eventuali colleghi valutate a occhio:

chiarezza delle spiegazioni;

quanto il “verified ✅” aumenta fiducia nella risposta.

5. Strategie per scalabilità futura (senza riscrivere tutto)

Separazione chiara dei moduli

Ogni modulo ha file dedicato e interfaccia chiara (funzioni pure, input/output documentati).

Questo permette di:

spostare M4 in un servizio separato (LLM microservice);

spostare M5–M6 in un “Logic microservice” se necessario.

Interfacce astratte invece di dipendenze hard-coded

Es. in llm_client.py definisci una classe/intefaccia LLMClient, con implementazione OllamaClient.

Domani puoi aggiungere OpenAIClient, LocalHFClient, ecc. senza toccare il resto.

Config centralizzata (M0)

Modello LLM, timeouts, numero massimo di iterazioni, attivazione/deattivazione del layer logico: tutto in config.

Per passare da MVP a produzione basta cambiare config, non il codice.

Schema DSL versionato

Mantieni un logic_program_version, così puoi evolvere la DSL senza rompere i vecchi test.

Supporto a job asincroni (in futuro)

Se i casi diventano pesanti, potrai:

mettere in coda le richieste (es. con Redis + RQ/Celery);

restituire un ID e far controllare lo stato.

L’architettura modulare facilita questo spostando M4–M6 in job separati.

Benchmark automatici in CI

Aggiungi un job (anche locale) che lancia benchmark.py su un sottoinsieme di casi ogni volta che modifichi logica/LLM.

Se le metriche scendono sotto una soglia, sai che hai rotto qualcosa.