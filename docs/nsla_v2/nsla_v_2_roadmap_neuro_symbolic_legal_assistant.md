# NSLA v2 – Guida tecnico‑strategica

## Titolo progetto
**NSLA v2 – Neuro‑Symbolic Legal Assistant con loop LLM ↔ Z3 e benchmark avanzato**

---

## Diagramma della Pipeline

```text
[Utente / Dataset legale]
        ↓
     [Front‑end]
        ↓ HTTP
[API Backend (FastAPI) – Orchestrator]
        ↓
 ┌─────────────────────────────────────────────────────────────┐
 │               STRATO NEURALE (LLM LAYER)                    │
 │                                                             │
 │  [Pre‑processing & Facts]                                   │
 │        ↓                                                    │
 │  [Prompt Manager v2]                                        │
 │        ↓                                                    │
 │  [LLM Client] — plain → /llm_only                           │
 │        ↓                                                    │
 │  [LLM Structured Output]                                    │
 │   (final_answer, premises, conclusion, logic_program_v1)    │
 └─────────────────────────────────────────────────────────────┘
        ↓
 ┌─────────────────────────────────────────────────────────────┐
 │                 STRATO SIMBOLICO (Z3 LAYER)                  │
 │                                                             │
 │  [Logic DSL Validator & Versioning]                         │
 │        ↓                                                    │
 │  [Translator v2 JSON DSL → Z3]                              │
 │        ↓                                                    │
 │  [Z3 Engine]                                                │
 │     ├─ Consistency check (SAT/UNSAT base axioms)            │
 │     ├─ Entailment check (conclusion / query)                │
 │     └─ Unsat‑core / model extraction                        │
 │        ↓                                                    │
 │  [Logic Feedback Engine]                                    │
 │    (status, conflicting_axioms, missing_links, summary)     │
 └─────────────────────────────────────────────────────────────┘
        ↓
 ┌─────────────────────────────────────────────────────────────┐
 │          STRATO ITERATIVO (NSLA v2 REFINEMENT)              │
 │                                                             │
 │  Modalità base (v1):                                       │
 │     usa direttamente final_answer_v1 + verified_v1          │
 │                                                             │
 │  Modalità v2 2‑pass / iterativa:                            │
 │     [Refinement Prompt Builder]                             │
 │        ↓                                                    │
 │     [LLM Refinement] → nuovo (final_answer_v2, logic_v2)    │
 │        ↓                                                    │
 │     [Z3 Re‑check] → status_v2                               │
 │        ↓                                                    │
 │     [Loop Manager] (max_iters, criteri di stop)             │
 └─────────────────────────────────────────────────────────────┘
        ↓
[Aggregator Risposta]
        ↓
[Output finale + trace logica + metriche]
        ↓
[UI / Benchmark Engine / Logging & Analytics]
```

---

## Roadmap v2 — Fasi

### Fase 0 – Baseline & consolidamento v1

**Obiettivo operativo**  
Congelare una baseline stabile di NSLA v1 (LLM‑only + NSLA one‑shot + benchmark attuale) da cui partire senza regressioni.

**Attività chiave**
- Pulizia del codice esistente e allineamento alla struttura modulare M0–M8.
- Verifica che tutti i test `pytest` e i benchmark v1 passino con esito positivo.
- Allineamento documentazione v1 (README, piano operativo) con lo stato reale del codice.
- Introduzione di flag di configurazione per:
  - `use_cloud` / `use_local_model`;
  - `enable_symbolic_layer`;
  - `benchmark_mode`.

**Deliverable**
- Branch stabile `v1-stable` con tag di versione (es. `v1.1`).
- Documentazione sintetica dell’architettura v1 (diagrammi + descrizione moduli).
- Snapshot dei risultati benchmark v1 (F1, BLEU, tempi) come baseline.

**Ruoli coinvolti**
- AI engineer / backend engineer.
- DevOps / MLOps leggero per setup ambienti e logging.

**Durata stimata**  
1–2 settimane, in parallelo con lavoro leggero di refactor.

---

### Fase 1 – Hardening del layer simbolico (Z3) e DSL v2

**Obiettivo operativo**  
Rendere il layer simbolico **robusto, leggibile e verificabile**, evitando asserzioni non coerenti e ambiguità di DSL.

**Attività chiave**
- Definizione chiara della **DSL logica v2**:
  - tipi (sorts), costanti, predicati, regole;
  - convenzioni precise per nomi e firma dei predicati legali;
  - gestione delle versioni (`dsl_version`).
- Estensione e pulizia di `translator.py`:
  - mappatura deterministica DSL → Z3;
  - gestione esplicita di errori di tipo e di arietà;
  - funzioni helper per costruire pattern legali frequenti (responsabilità, nesso causale, soglie temporali/quantitative).
- Introduzione di un **modulo `logic_feedback`** che, a partire da:
  - risultato Z3 (SAT/UNSAT, modello, unsat‑core),
  - struttura del `logic_program`,
  restituisca un oggetto strutturato con:
  - `status` (consistent_entails / consistent_no_entailment / inconsistent),
  - `conflicting_axioms`,
  - `missing_links`,
  - `human_summary` sintetico.
- Battery di test unitari su casi puramente simbolici per verificare:
  - soundness delle traduzioni;
  - coerenza degli assiomi legali modellati.

**Deliverable**
- `logic_dsl_v2.md` con specifica formale della DSL.
- Modulo `logic_feedback.py` con API documentata.
- Suite di test unitari su DSL + translator + feedback.

**Ruoli coinvolti**
- Research engineer neuro‑simbolico.
- Esperto Z3 / SMT.
- Collaborazione con dominio legale per la modellazione di concetti chiave.

**Durata stimata**  
2–4 settimane, iterativa, con revisione congiunta AI/legale.

---

### Fase 2 – NSLA v2 two‑pass (Z3 → LLM feedback controllato)

**Obiettivo operativo**  
Introdurre una modalità `/legal_query_v2` con **un solo pass di refining** guidato dal feedback del solver, senza loop arbitrariamente lunghi.

**Attività chiave**
- Nuovo endpoint o parametro di modalità:
  - `/legal_query_v2` oppure `/legal_query?mode=v2`.
- Pipeline v2:
  1. Esecuzione di NSLA v1: domanda → LLM structured → logic_program_v1 → Z3.
  2. Interpretazione del risultato tramite `logic_feedback`.
  3. Se `status != consistent_entails` o se F1/metriche < soglia:
     - costruzione di un **refinement prompt** che include:
       - domanda originale;
       - risposta e programma logico v1;
       - `logic_feedback.human_summary`, `conflicting_axioms`, `missing_links`.
     - chiamata LLM per generare `LLMOutput_v2` (nuova answer e nuovo logic_program).
     - nuovo giro di Z3 su `logic_program_v2`.
  4. Aggregazione risultati: risposta finale, stato v1 vs v2, logica associata.
- Estensione del benchmark per misurare:
  - F1/ BLEU per LLM‑only, NSLA v1, NSLA v2;
  - variazione di F1/ BLEU fra v1 e v2;
  - tempo aggiuntivo introdotto dal secondo pass.

**Deliverable**
- Endpoint `/legal_query_v2` documentato.
- Nuove colonne in `results.csv` per metrics v2.
- Report interno che confronta v1 vs v2 su dev‑set.

**Ruoli coinvolti**
- Backend engineer.
- Prompt engineer / AI researcher per progettare il refinement prompt.

**Durata stimata**  
2–3 settimane, inclusi aggiustamenti del prompt e test.

---

### Fase 3 – Modalità iterativa limitata (loop LLM ↔ Z3)

**Obiettivo operativo**  
Sperimentare un **loop iterativo limitato** LLM ↔ Z3 (es. fino a 3 iterazioni) per casi complessi, con gestione robusta dei criteri di stop.

**Attività chiave**
- Implementazione di un **Iteration Manager** (es. `run_nsla_iterative`) che gestisce:
  - `max_iters` configurabile;
  - criteri di stop (raggiunta consistenza, nessun miglioramento, oscillazioni).
- Definizione di una struttura di **history** per ogni caso:
  - lista delle coppie (LLMOutput_k, logic_feedback_k, metrics_k).
- Prompt di refinement iterativo che:
  - incoraggi modifiche locali al programma logico (non riscrittura totale);
  - utilizzi il contesto delle iterazioni precedenti nel modo più sintetico possibile.
- Integrazione nel backend come modalità opzionale:
  - `/legal_query_iterative` oppure `mode=iter` + parametri.
- Estensione del benchmark per registrare:
  - numero medio di iterazioni per caso;
  - miglioramento medio di F1/ BLEU per iter;
  - distribuzione degli stati Z3 finali (consistent_entails, ecc.).

**Deliverable**
- Funzionalità iterativa integrata e protetta da config (feature flag).
- Dataset di log delle iterazioni per analisi offline.

**Ruoli coinvolti**
- AI researcher.
- Neuro‑symbolic engineer.

**Durata stimata**  
3–5 settimane in modalità sperimentale.

---

### Fase 4 – Dataset legali potenziati e metriche scientifiche

**Obiettivo operativo**  
Rendere il benchmark **scientificamente credibile**, arricchendo dataset e metriche, anche sfruttando corpora legali open‑source.

**Attività chiave**
- Revisione di `cases_dev.json`:
  - trasformazione delle `gold_answer` in frasi complete e precise;
  - introduzione di `gold_variants` per accettare più formulazioni equivalenti;
  - tagging dei casi per tipologia (contratto, responsabilità civile, lavoro, ecc.).
- Valutazione e, se adeguato, integrazione di dataset open‑source:
  - selezione di sottoinsiemi coerenti con il dominio e la lingua;
  - mappatura verso il formato `cases_dev`.
- Estensione del benchmark con metriche aggiuntive:
  - F1, EM, BLEU già presenti;
  - delta F1 tra modalità (LLM‑only, NSLA v1, NSLA v2, iterativa);
  - metriche di coerenza logica (percentuale di casi `consistent_entails`).
- Possibile introduzione di un **Judge LLM** separato, per stimare qualità percepita della risposta.

**Integrazione Loop Iterativo Fondamentale**
- Prendre info da file apposito capire se gia implementato e se si a che punto.
 Capire se logica va bene e che algoritmi dobbiamo introdurre per ragionare al meglio
 Vediamo come sbloccare la situazione al meglio chiedendo anche a cursor che avra la possibilita
 di vedere tutta la cartella come è la situazione per non incorrere in erroir. Ragiona come un ingegnere
 neuro simbolico esperto
** DataSet **
- Sì, esistono risorse, ma la situazione è frammentata: mentre per la Giurisprudenza Costituzionale e la Legislazione esistono veri portali Open Data, per il Diritto Penale (Cassazione) e le Ontologie Logiche le risorse sono spesso accademiche o consultabili ma non scaricabili "in blocco" (bulk) come dataset open source pronti all'uso per il machine learning.
Ecco una panoramica con i link diretti alle risorse disponibili.
1. Dataset Open Source (Sentenze e Leggi)
Questi sono i portali ufficiali dove puoi trovare dati strutturati (XML, JSON, CSV) o scaricabili liberamente.
Corte Costituzionale - Portale Open Data (Il migliore per "Openness")
È l'unica alta corte italiana che rilascia ufficialmente le sentenze in formato aperto e strutturato.
Cosa contiene: Tutte le pronunce dal 1956 a oggi.
Formati: XML, JSON, CSV.
Link: dati.cortecostituzionale.it
Normattiva (Legislazione, non giurisprudenza)
Il database ufficiale della legge italiana.[1] Anche se non è un "dataset" unico scaricabile, è la fonte primaria per il testo del Codice Penale aggiornato.
Link: normattiva.it
Nota: Esistono scraper su GitHub (cerca "Normattiva scraper") creati dalla community per estrarre questi dati in formato dataset.
Corte di Cassazione (Situazione Ibrida)
Esiste il progetto "Open Sentenze", ma non è un vero open dataset "bulk" (scaricabile tutto in una volta). È più un motore di ricerca gratuito. Per dataset massivi di sentenze penali (anonimizzate) spesso si deve passare per accordi di ricerca con il CED della Cassazione o usare le API limitate.
SentenzeWeb: italgiure.giustizia.it/sncass/ (Motore di ricerca gratuito per le sentenze degli ultimi 5 anni).
GitHub - Awesome Italian Public Datasets
Questa è la risorsa comunitaria più aggiornata. Controlla la sezione "Law" o "Giustizia" per eventuali dump rilasciati da hackathon o progetti civici.
Link: italia/awesome-italian-public-datasets
2. Ontologie Logiche (Legge Penale / Legal Tech)
Le ontologie specifiche per il diritto penale italiano sono quasi esclusivamente progetti di ricerca accademici. Non troverai un file .owl o .rdf su GitHub pronto per il download come per il software open source classico. Spesso bisogna contattare i ricercatori o consultare le pubblicazioni.
Ecco i progetti più rilevanti a cui fare riferimento:
PrOnto (Privacy Ontology for Legal Reasoning)
Sviluppata dal CIRSFID (Università di Bologna), è una delle ontologie legali più avanzate in Italia. Anche se focalizzata sulla privacy (GDPR), modella concetti penali come "violazione", "sanzione", "agente", "obbligo".
Riferimento: Cerca "PrOnto ontology CIRSFID" su Google Scholar o ResearchGate. Spesso i file OWL sono allegati ai paper o disponibili su richiesta ai laboratori del CIRSFID.
Italian Crime Ontology
Un progetto storico (Asaro et al., CNR) che mirava a mappare il codice penale italiano in classi logiche (Reato, Pena, Circostanza, ecc.).
Stato: Non esiste un repository pubblico attivo. È reperibile principalmente tramite paper accademici (es. su ResearchGate o Semantic Scholar).
Ontologie della Pubblica Amministrazione (OntoPiA)
Il Team per la Trasformazione Digitale ha rilasciato ontologie ufficiali su GitHub. Non coprono il "reato" in sé, ma coprono le Persone, le Organizzazioni e i Luoghi, fondamentali per costruire un knowledge graph legale.
Link: github.com/italia/dati-semantic-assets
Consiglio per la ricerca
Se stai cercando di addestrare una AI o costruire un sistema esperto, la strada migliore oggi è:
Scaricare il dataset XML della Corte Costituzionale per avere una base di linguaggio giuridico di alta qualità.
Usare le ontologie OntoPiA (persone/luoghi) come scheletro.
Costruire manualmente (o estrarre con NLP dai testi di Normattiva) le classi specifiche per i reati (es. Art. 575 CP -> Classe Omicidio).

**Deliverable**
- `cases_dev_v2.json` e, se opportuno, `cases_external.json`.
- Script di benchmark aggiornato con nuove metriche.
- Report comparativo v1 vs v2 su più dataset.

**Ruoli coinvolti**
- Legal domain expert.
- Data engineer / ML engineer.

**Durata stimata**  
4–6 settimane, anche in parallelo con le fasi 2–3.

---

### Fase 5 – UI "Research Mode" e osservabilità

**Obiettivo operativo**  
Offrire una **UI avanzata** per ricercatori/ingegneri che permetta di ispezionare, caso per caso, il comportamento neuro‑simbolico.

**Attività chiave**
- Estensione della UI esistente con una vista dedicata "Research/Debug":
  - mostrare domanda, gold, risposta LLM‑only, risposta NSLA (v1, v2, iterativa);
  - visualizzare stato Z3 (SAT/UNSAT, entailment, unsat‑core sintetico);
  - evidenziare differenze tra iterazioni (se modalità iterativa attiva).
- Integrazione con i log strutturati generati da `benchmark.py` e dal backend.
- Introduzione di metriche base in UI (senza sovraccaricare l’utente finale):
  - F1/ BLEU per caso;
  - flag logico (`verified`, `consistent_entails`, ecc.).

**Deliverable**
- Nuova UI "Research" operativa.
- Documentazione d’uso per team interno (ricerca e sviluppo).

**Ruoli coinvolti**
- Full‑stack / frontend engineer.
- AI engineer.

**Durata stimata**  
3–4 settimane.

---

### Fase 6 – Documentazione finale, linee guida e paper interno

**Obiettivo operativo**  
Chiudere la v2 con una documentazione solida per manutenzione, ulteriori esperimenti e potenziale pubblicazione.

**Attività chiave**
- Redazione di una **guida architetturale v2** con diagrammi aggiornati.
- Descrizione formale del loop LLM ↔ Z3 e delle strategie di controllo.
- Raccolta e sintesi dei risultati sperimentali:
  - confronto numerico v1 vs v2 (F1, BLEU, tempi, coerenza logica);
  - analisi qualitativa di pochi casi emblematici.
- Stesura di linee guida per:
  - manutenzione dei prompt;
  - estensione della DSL;
  - aggiunta di nuovi modelli LLM o nuovi solver.

**Deliverable**
- Documento tecnico v2 (architettura + risultati).
- Bozza di paper interno / accademico.

**Ruoli coinvolti**
- Project lead.
- AI researcher.

**Durata stimata**  
2–3 settimane.

---

## Prompt Management

**Obiettivo**  
Gestire i prompt come **artefatti di prima classe**, versionati e testati al pari del codice.

### Organizzazione e versioning

- Repository Git con directory dedicata, ad esempio `prompts/` suddivisa in:
  - `prompts/plain_llm/` (per `/llm_only`);
  - `prompts/structured/` (per output JSON strutturato);
  - `prompts/refinement/` (per v2 e modalità iterative);
  - `prompts/judge/` (per LLM giudice, se usato).
- Ogni file di prompt con convenzione chiara:
  - `scenario_nomePrompt_vX.Y.md` (es. `legal_structured_italian_v1.2.md`).
- Commit che modificano prompt sempre accompagnati da:
  - riferimento al benchmark eseguito;
  - breve nota sui cambiamenti.

### Standard di scrittura

- Struttura interna dei prompt:
  - sezione "Ruolo" (persona dell’LLM);
  - sezione "Istruzioni dure" (vincoli non violabili);
  - sezione "Formato output" (con esempi JSON rigorosi);
  - sezione "Esempi few‑shot" (facoltativa, ma controllata nel numero di token).
- Evitare testo ridondante; preferire istruzioni numerate e vincoli espliciti sul formato.

### Test e validazione

- Ogni modifica significativa a un prompt comporta:
  - riesecuzione di un sottoinsieme fisso di casi (`prompt_regression_set`);
  - valutazione automatica (F1 / EM / % JSON validi).
- Possibile uso di A/B testing interno:
  - due varianti di prompt su un sottoinsieme del dataset;
  - confronto delle metriche prima di unificare.

### Metriche di efficienza

- Per ciascun prompt, monitorare:
  - lunghezza media richiesta (token input);
  - lunghezza media risposta (token output);
  - tempo medio di inferenza;
  - % di risposte non parseabili (formato errato).
- Obiettivo: ridurre la complessità dei prompt mantenendo o aumentando le metriche di qualità.

---

## Revisione e Iterazione

**Retrospettive post‑rilascio**
- Dopo ogni milestone (Fase 2, 3, 4…), organizzare una breve retrospettiva focalizzata su:
  - cosa ha funzionato nella pipeline neuro‑simbolica;
  - dove il layer simbolico ha dato valore;
  - dove il costo computazionale non è giustificato.

**Aggiornamenti documentali e tecnici**
- Ogni cambio di architettura o DSL comporta aggiornamento di:
  - `logic_dsl_v2.md`;
  - guida di prompt;
  - README o documentazione architetturale.
- Introdurre brevi "ADR" (Architecture Decision Records) per le decisioni critiche (es. introduzione loop iterativo, scelta di un dataset esterno).

**Metriche di miglioramento continuo**
- Tracciare nel tempo:
  - F1/ BLEU globali e per categoria di caso;
  - tassi di `consistent_entails` vs `inconsistent`;
  - latenza media per modalità (LLM‑only, NSLA v1, v2, iterativa);
  - nsla_win_rate secondo il judge LLM (se abilitato).
- Usare queste metriche come criterio oggettivo per accettare o rigettare modifiche importanti.

---

## Output Finale Atteso

**Artefatti finali**
- Roadmap v2 consolidata e aggiornata (questo documento).
- Implementazione di NSLA v2 con:
  - layer simbolico Z3 robusto e versionato;
  - modalità two‑pass e iterativa opzionale;
  - benchmark avanzato su dataset legali interni ed esterni.
- Set di prompt organizzati per scenario, versionati e collegati ai risultati di benchmark.
- Documentazione architetturale completa (diagrammi, DSL, flussi).

**Strumenti consigliati**
- **Git/GitHub/GitLab** per codice, prompt e documentazione.
- **Notion / Obsidian** per note progettuali e ADR.
- **Miro / Excalidraw** per diagrammi evolutivi.
- **Jira / Linear** per tracking delle fasi e delle issue.
- **MLflow / Weights & Biases / fogli di calcolo versionati** per tracciare gli esperimenti di benchmark.

**Changelog narrativo sintetico (v2 rispetto a v1)**
- Il sistema passa da un modello **LLM + Z3 one‑shot** a una pipeline **neuro‑simbolica iterativa**, dove Z3 non solo verifica ma guida correzioni successive dell’LLM.
- Il layer simbolico è rafforzato tramite una DSL chiara, versionata e testata, con feedback strutturato derivato da Z3.
- Il benchmark evolve da metriche basilari (accuracy, F1) a un sistema più ricco, in grado di misurare l’impatto reale del layer simbolico su qualità, coerenza e costo computazionale.
- La gestione dei prompt diventa sistematica, tracciata e valutata sperimentalmente, rendendo l’evoluzione del sistema ripetibile e analizzabile nel tempo.

