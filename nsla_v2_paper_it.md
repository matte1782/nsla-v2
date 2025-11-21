NSLA-v2: Un Prototipo Neuro-Simbolico per il Ragionamento Legale

Rapporto di Ricerca Ibrido (Tecnico + Accademico)

Autore: Matteo Panzeri (con assistenza di strumenti basati su LLM)Data: 2025

Abstract (Italiano)

Questo documento descrive lo sviluppo, l’analisi e l’archiviazione del progetto NSLA-v2, un prototipo neuro-simbolico ideato per valutare la possibilità di utilizzare l'entailment logico puro tramite Z3 come base per compiti di ragionamento legale. Il sistema integra: (1) estrazione strutturata, (2) un DSL giuridico personalizzato, (3) una pipeline neuro-simbolica e (4) inferenza basata su SMT. Sebbene i primi risultati mostrassero un comportamento promettente su casi sintetici semplici, esperimenti più approfonditi hanno rivelato limiti strutturali: il ragionamento giuridico è intrinsecamente contestuale, non monotono e interpretativo, mentre Z3 opera con vincoli logici completamente specificati e monotoni. Questa incompatibilità impedisce inferenze legali solide anche quando il DSL, i predicati e i vincoli sono formalmente corretti.

Sebbene NSLA-v2 non raggiunga il suo obiettivo originale, il progetto ha prodotto insight utili, componenti riutilizzabili e nuove direzioni di ricerca (es. BinaryLLM, Concept Generator, Fractal Reasoning Engine). Si configura come un case study di ricerca guidata dal fallimento, che evidenzia pensiero critico, ingegneria di sistema avanzata, test rigorosi e riflessione scientifica.

1. Introduzione

Il dominio del ragionamento legale è apparentemente naturale per l’IA neuro-simbolica: ricco di regole, testo strutturato e relazioni logiche. L’obiettivo iniziale di NSLA-v2 era esplorare se l'entailment logico puro, espresso tramite un DSL personalizzato ed eseguito con Z3, potesse fungere da fondamento per attività come:

interpretazione contrattuale,

validazione di clausole,

inferenza di obblighi,

rilevazione di contraddizioni.

Gli obiettivi principali erano:

progettare un linguaggio specifico (DSL) per rappresentare fatti giuridici;

tradurre testo naturale → estrazione strutturata → DSL → formule logiche;

usare Z3 per determinare consistenza, SAT/UNSAT e modelli;

stabilire un ciclo di feedback e raffinamento iterativo.

Perché questa ricerca?

Per sondare i limiti del metodo e capire fino a che punto un approccio SMT possa supportare sistemi complessi di ragionamento. Questo lavoro è un’esplorazione scientifica, non un prodotto destinato a produzione.

2. Contesto e Lavori Correlati

2.1 IA Neuro-Simbolica

I sistemi neuro-simbolici uniscono:

percezione statistica (LLM, embedding), e

ragionamento simbolico (logica, vincoli, ricerca).

Questo approccio è molto efficace nella verifica formale, nella sintesi di programmi e nei sistemi safety-critical. Il suo impiego nel ragionamento giuridico, invece, è ancora poco esplorato.

2.2 SMT e Z3

Z3 è un solver SMT all’avanguardia, utilizzato in:

verifica formale di software,

analisi statica,

studi di sicurezza,

ottimizzazione.

La sua forza — rigore, determinismo, esplicitazione totale — diventa anche una debolezza quando applicata a domini ambigui come il diritto.

2.3 Ragionamento Legale

Il ragionamento giuridico è:

non monotono (aggiungere fatti può cambiare conclusioni),

contestuale,

interpretativo,

soggetto a eccezioni e gerarchie normative.

Queste proprietà sono intrinsecamente incompatibili con la logica monotona gestita dai solver SMT.

3. Progettazione del Sistema

3.1 Panoramica della Pipeline

Testo → Estrazione Strutturata → DSL → Normalizzazione → Guardrail → Encoding Z3 → Solve → Feedback

3.2 Componenti

Estrattore strutturato: identifica attori, obblighi, condizioni.

DSL legale: formalizza fatti e relazioni.

Normalizzatore DSL: uniforma predicati, arità, tipi.

Guardrail: blocca programmi DSL malformati prima del solver.

Traduttore Z3: genera simboli, vincoli e formule.

Solver: esegue SAT/UNSAT e produce modelli.

Feedback loop: meccanismo iterativo di raffinamento.

3.3 Motivazione dell'architettura

L’architettura enfatizza:

modularità,

chiarezza,

riproducibilità,

determinismo.

Anche se il dominio non si presta allo strumento, l’architettura rimane valida.

4. Setup Sperimentale

4.1 Dataset

Micro-scenari giuridici sintetici:

contratti di acquisto,

contratti di locazione,

obblighi di pagamento o consegna,

clausole di risoluzione.

4.2 Compiti Valutati

Rilevazione di contraddizioni.

Coerenza tra DSL e testo.

Robustezza della normalizzazione.

Comportamento del solver all’aggiunta di fatti.

4.3 Metodologia di Test

Pytest (unit test, integration test).

Casi avversariali.

Validazione dei modelli logici.

Loop di raffinamento.

5. Risultati e Failure Modes

Nonostante la correttezza tecnica del sistema, emergono limiti concettuali.

5.1 Risultati Positivi

Normalizzazione coerente.

Encoding Z3 stabile.

Guardrail efficace.

Test unitari solidi.

5.2 Principali Failure Modes

1. Perdita di contesto semantico

Il testo giuridico contiene implicature e interpretazioni non traducibili in DSL.

2. Non-monotonicità

L'aggiunta di fatti può ribaltare l’inferenza: SMT non lo gestisce.

3. Sovra-specificazione

Il diritto tollera ambiguità; Z3 richiede specificazione completa.

4. Mancanza di interpretazione dinamica

La semantica giuridica evolve; la logica statica no.

5. Entailment ≠ Ragionamento legale

Anche con DSL perfetto, il solver non può replicare la ricchezza del ragionamento umano.

6. Discussione

Perché il risultato negativo è prezioso

I risultati negativi:

riducono lo spazio di ricerca,

evitano sprechi futuri,

evidenziano limiti teorici,

aprono nuove direzioni.

Conclusione chiave:

Il problema non è nell’implementazione, ma nella mancata compatibilità tra logica monotona e diritto.

7. Lezioni Apprese

Cosa ha funzionato:

Modularità

DSL robusto

Test rigorosi

Guardrail chiaro

Cosa non ha funzionato:

Entailment come motore principale

Preservazione del contesto

Logica monotona

Insight finale:

Il ragionamento legale richiede logiche:

deontiche,

non monotone,

contestuali.

8. Direzioni Future

1. BinaryLLM Protocol

Rappresentazioni latenti binarie a bassa energia.

2. Generatore Neuro-Simbolico di Concetti

Produzione di proposizioni astratte + verifica logica.

3. Fractal Reasoning Engine

Motore di reasoning multilivello auto-validante.

9. Conclusione

NSLA-v2 dimostra che:

l’ingegneria avanzata non può superare limiti teorici del dominio;

la ricerca guidata dal fallimento è estremamente preziosa.

Il progetto rimane come riferimento per future esplorazioni.

10. Ringraziamenti

Questo progetto è stato sviluppato da Matteo Panzeri, con il supporto critico di strumenti di reasoning avanzati basati su LLM, usati in modo responsabile per accelerare ideazione e analisi.

---

# Appendice A: Struttura della Repository

La repository NSLA-v2 è organizzata come un prototipo di ricerca modulare con chiara separazione delle responsabilità. Di seguito si riporta una panoramica delle directory e dei file principali:

### **Directory Radice**
- **`README.md`**: Panoramica del progetto, motivazione, sintesi dell'architettura e istruzioni d'uso.
- **`requirements.txt`**: Dipendenze Python per l'intero progetto.
- **`benchmark_llm_structured.py`**: Script standalone per il benchmarking delle prestazioni di estrazione strutturata tramite LLM.
- **`test_*.py`**: File di test standalone per il testing isolato di componenti (client LLM, prompt loader).
- **`tmp_*.py`**: Script di utilità temporanei per debugging e ispezione.

### **`app/`** — Logica Applicativa Principale
Contiene i componenti principali della pipeline neuro-simbolica:
- **DSL e Logica**: `logic_dsl.py`, `models.py`, `models_v2.py` — definizioni del linguaggio specifico di dominio giuridico e modelli di dati.
- **Estrazione**: `structured_extractor.py` — estrae attori, obblighi e condizioni dal linguaggio naturale.
- **Traduzione**: `translator.py` — converte il DSL in formule logiche compatibili con Z3.
- **Normalizzazione**: `canonical_rule_utils.py`, `ontology_utils.py` — garantisce coerenza dei predicati e allineamento dei tipi.
- **Guardrail**: `guardrail_checker.py` — valida i programmi DSL prima della codifica Z3 per prevenire input malformati.
- **Pipeline**: `pipeline_v2.py`, `main.py` — orchestra il flusso di ragionamento neuro-simbolico end-to-end.
- **Runtime**: `judge_runtime.py`, `canonicalizer_runtime.py`, `refinement_runtime.py` — gestisce le diverse fasi della pipeline.
- **Feedback e Iterazione**: `logic_feedback.py`, `iteration_manager.py`, `history_summarizer.py` — implementa loop di raffinamento.
- **Spiegazione**: `explanation_synthesizer.py` — genera spiegazioni leggibili dall'umano a partire dagli output del solver.
- **Utilità**: `llm_client.py`, `prompt_loader.py`, `config.py`, `checker.py`, `preprocessing.py` — infrastruttura di supporto.
- **Template**: `templates/index.html` — interfaccia web minimale (se applicabile).

### **`tests/`** — Suite di Test Completa
Contiene test unitari, test di integrazione e validazione end-to-end:
- **Test dei componenti**: `test_translator_v2.py`, `test_guardrail_checker.py`, `test_logic_feedback.py`, `test_llm_structured.py`, ecc.
- **Test dei runtime**: `test_judge_runtime.py`, `test_phase2_runtimes.py`, `test_iteration_manager.py`.
- **Test end-to-end**: `test_end_to_end.py`, `test_phase2_e2e.py`, `test_phase3_e2e.py`.
- **Casi golden**: `test_nsla_v2_golden_cases.py` — casi di test corretti noti per la validazione.
- **Test di benchmark**: `test_benchmark_smoke.py` — controlli di prestazioni e correttezza.
- **Configurazione**: `conftest.py` — fixture pytest condivise e setup.

### **`data/`** — Casi di Benchmark e Risultati
Archivia casi di test, dati di valutazione e risultati sperimentali:
- **`cases_dev.json`**, **`cases_dev_subset_1_5.json`**: Micro-scenari giuridici per il benchmarking.
- **`case_*.json`**: Risposte dei singoli casi di test.
- **`results_*.csv`**: Risultati sperimentali di diverse fasi e configurazioni della pipeline.

### **`docs/`** — Documentazione Tecnica
Contiene documenti di progettazione, specifiche e materiali di pianificazione:
- **`project.md`**, **`piano_operativo_mvp_llm_smt_nsla_matteo_panzeri.md`**: Pianificazione del progetto e note operative.
- **`nsla_v2/`**: Documentazione tecnica dettagliata che include guide al DSL, walkthrough della pipeline, piani di test, report di fase e note di debugging.

### **`resources/`** — Prompt, Ontologia e Specifiche
Risorse di supporto per la pipeline:
- **`prompts/`**: Template di prompt LLM organizzati per fase della pipeline.
- **`ontology/`**: Definizioni dell'ontologia giuridica per l'estrazione strutturata.
- **`specs/`**: Documenti di specifica del sistema e walkthrough della pipeline.

### **`scripts/`** — Script di Utilità
Script standalone per debugging e test manuali:
- **`inspect_subset_guardrail.py`**, **`manual_sanity.py`**: Strumenti diagnostici per la validazione della pipeline.

### **Rationale Architetturale**
La struttura della repository riflette i principi di modularità del sistema NSLA-v2:
- **Separazione delle responsabilità**: estrazione, DSL, traduzione e risoluzione sono isolati.
- **Testabilità**: ogni componente ha corrispondenti test unitari.
- **Documentazione**: le decisioni tecniche sono registrate in `docs/`.
- **Riproducibilità**: benchmark, casi di test e risultati sono versionati.

Tale organizzazione supporta la ricerca iterativa, il debugging e future estensioni.