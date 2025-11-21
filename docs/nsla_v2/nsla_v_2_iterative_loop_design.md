# NSLA v2 – Iterative LLM ↔ Z3 Loop Design

## 1. Obiettivo del loop iterativo

**Scopo**: trasformare il layer simbolico da semplice *verificatore* post‑hoc a **partner attivo di raffinamento**.

Per ogni domanda legale vogliamo:
- generare una prima bozza di risposta + programma logico;
- verificare con Z3 coerenza e derivabilità della conclusione;
- usare il feedback logico per guidare uno o più cicli di correzione dell’LLM;
- fermarci in modo controllato, evitando loop infiniti.

Il loop iterativo è pensato inizialmente come **modalità sperimentale** (es. `/legal_query_iterative`) per ricerca e benchmark, non come default in produzione.

---

## 2. Architettura ad alto livello del loop

Pipeline iterativa (vista semplificata):

```text
[Domanda utente]
      ↓
[Iter 0 – LLM primario]
  genera: { final_answer_0, logic_program_0 }
      ↓
[Z3 Checker]
  → feedback_0 = { status, conflicts, missing_links, summary }
      ↓
[Controller NSLA Iterativo]
  decide se fermarsi o chiamare un nuovo passo LLM
      ↓
[Iter k – LLM refinement]
  input: domanda, output_k-1, feedback_k-1, history
  output: { final_answer_k, logic_program_k }
      ↓
[Z3 Checker]
  …
      ↓ (stop condition soddisfatta)
[Risposta finale + storia iterazioni]
```

Elementi chiave:
- **LLM primario**: genera la prima bozza (come NSLA v1).
- **Z3 Checker + Logic Feedback**: valuta e sintetizza i problemi.
- **Iterative Controller**: applica le regole di stop, orchestration e logging.
- **LLM di refinement**: può essere lo stesso modello o uno diverso, ma con prompt specifico.

---

## 3. Stato per iterazione

Per ogni iterazione `k`, definiamo uno stato strutturato:

```json
{
  "iter": k,
  "llm_output": {
    "final_answer": "…",
    "logic_program": { … },
    "notes": "facoltativo, es. spiegazione chain-of-thought non logica"
  },
  "z3_feedback": {
    "status": "consistent_entails" | "consistent_no_entailment" | "inconsistent" | "unknown",
    "conflicting_axioms": ["r1", "r3"],
    "missing_links": ["ResponsabilitaCivile", "DannoPatrimoniale"],
    "unsat_core_raw": ["r1", "r3"],
    "model_snapshot": "id_modello_anonimizzato_o_riassunto",
    "human_summary": "Le regole r1 e r3 sono in conflitto su X…"
  },
  "metrics": {
    "f1": 0.41,
    "bleu": 0.12,
    "z3_time": 0.08,
    "llm_time": 8.3
  }
}
```

Lo **storico completo** è una lista di questi stati: `history = [state_0, state_1, …]`.

Questo rende il loop:
- tracciabile (utile per debug e paper);
- ripetibile (possiamo rigiocare una sessione);
- misurabile (vediamo se miglioriamo o peggioriamo per iterazione).

---

## 4. Tipi di feedback Z3 → LLM

Z3 da solo restituisce solo `SAT / UNSAT / UNKNOWN` + modello o unsat-core.
Per l’LLM dobbiamo costruire un **feedback intermedio strutturato** (Logic Feedback v2).

### 4.1 Classi di stato logico

1. `consistent_entails`
   - Base assiomi è **SAT**.
   - La query (conclusione) è derivabile dal programma.
   - Interpretazione: *il programma logico supporta la conclusione*.

2. `consistent_no_entailment`
   - Base assiomi è **SAT**.
   - La query **non** è derivabile.
   - Interpretazione: programma coerente ma **mancano regole** o la conclusione è troppo forte.

3. `inconsistent`
   - Base assiomi è **UNSAT**.
   - C’è un conflitto fra alcuni assiomi.

4. `unknown`
   - Z3 non riesce a risolvere in tempi/risorse dati (o standard fragment non decidibile).

### 4.2 Informazioni derivate

Per ogni caso, il modulo `logic_feedback` prova a estrarre:

- `conflicting_axioms`: lista di ID delle regole nell’unsat core.
- `missing_links`: predicati che appaiono nella query ma che non hanno regole di supporto o catena di derivazione.
- `redundant_axioms` (opzionale v2.1): regole che non vengono mai usate in nessuna prova.
- `human_summary`: breve descrizione testuale pensata per LLM, ma leggibile anche da un umano.

Esempio di `logic_feedback` sintetico:

```json
{
  "status": "consistent_no_entailment",
  "conflicting_axioms": [],
  "missing_links": ["NessoCausale", "DannoEmergente"],
  "human_summary": "Il programma è coerente, ma non esistono regole che collegano il fatto di inadempimento al danno patrimoniale richiesto."
}
```

---

## 5. Prompt di refinement per l’LLM

Ogni iterazione dopo la prima usa un **prompt di refinement** che prende in input:
- domanda originale;
- gold_answer (solo in benchmark mode, non in produzione);
- risposta e programma logico dell’iterazione precedente;
- feedback strutturato `logic_feedback`.

Schema concettuale:

```text
System: Sei un assistente legale neuro-simbolico. Devi correggere il tuo programma logico
per renderlo coerente e, se possibile, sufficiente a supportare la conclusione.

User:
DOMANDA ORIGINALE:
{question}

TUA RISPOSTA PRECEDENTE (ITER {k-1}):
{final_answer_prev}

PROGRAMMA LOGICO PRECEDENTE:
{logic_program_prev}

FEEDBACK LOGICO DA Z3:
- Stato: {logic_feedback.status}
- Riassunto: {logic_feedback.human_summary}
- Assiomi in conflitto: {logic_feedback.conflicting_axioms}
- Collegamenti mancanti: {logic_feedback.missing_links}

ISTRUZIONI:
1. Mantieni valide tutte le premesse corrette.
2. Risolvi i conflitti espliciti corretti nel feedback.
3. Aggiungi SOLO le regole minime necessarie per collegare i concetti mancanti.
4. Se ritieni che la conclusione non sia dimostrabile con i fatti disponibili, esplicitalo chiaramente.

Restituisci un JSON con la stessa struttura di output di NSLA v1:
{
  "final_answer": "...",
  "logic_program": { ... }
}
```

Caratteristiche:
- correzioni **incrementali**, non riscrittura totale;
- focus sulle parti segnalate da Z3 (conflitti, missing links);
- esplicita la possibilità di dichiarare la non dimostrabilità.

---

## 6. Criteri di stop: evitare loop infiniti

Per ogni domanda, l’iterative controller applica una funzione di stop deterministica, basata su:

1. **Limite massimo di iterazioni** `max_iters`
   - Es. default = 3.
   - `if k >= max_iters: stop`.

2. **Goal logico raggiunto**
   - Se `status == consistent_entails` per l’ultima iterazione, e opzionalmente
   - se l’ultima iter non peggiora le metriche testuali (F1 vs gold), ci possiamo fermare.

3. **Assenza di miglioramento**
   - Se per due iterazioni consecutive:
     - F1 (o BLEU) non migliora oltre una soglia minima `eps` (es. 0.01), **e**
     - la struttura del programma logico cambia poco (es. stesso numero di assiomi, stessi predicati principali),
   - allora si considera che il processo si sia stabilizzato → stop.

4. **Fallback di sicurezza**
   - Se Z3 ritorna `unknown` per N iterazioni, o se si verificano errori ripetuti nel translator,
   - il sistema ritorna la miglior iterazione vista finora (per F1 o per stato logico) + un flag `uncertain`.

Pseudocodice di alto livello:

```python
def run_nsla_iterative(question, max_iters=3, eps=0.01):
    history = []
    curr_output = first_llm_call(question)  # NSLA v1

    for k in range(max_iters):
        feedback = run_z3_and_build_feedback(curr_output.logic_program)
        metrics = eval_metrics(curr_output.final_answer)  # solo in benchmark

        state = IterState(k, curr_output, feedback, metrics)
        history.append(state)

        if should_stop(history, max_iters, eps):
            break

        curr_output = refine_with_llm(question, state, history)

    best_state = select_best_state(history)  # es. priorità a consistent_entails, poi F1
    return best_state, history
```

La funzione `should_stop(...)` incapsula la logica di arresto e può essere testata unitariamente.

---

## 7. Integrazione con il benchmark

Per valutare l’efficacia del loop iterativo rispetto a v1:

- Aggiungere nel benchmark le seguenti colonne per ogni caso:
  - `f1_llm_only`
  - `f1_nsla_v1`
  - `f1_nsla_iter_last` (ultima iterazione)
  - `delta_f1_iter_vs_v1`
  - `iters_used`
  - `z3_status_final`

- Opzionalmente loggare anche:
  - vettore F1 per iter: `[f1_iter_0, f1_iter_1, ...]`;
  - tempo totale di tutte le iterazioni.

Questo consente di rispondere sperimentalmente a domande del tipo:
- quante iterazioni medie servono per raggiungere `consistent_entails`?
- il guadagno medio di F1/BLEU giustifica il costo in latenza?
- su quali tipi di casi il loop iterativo porta benefici (es. contratti complessi vs casi semplici)?

---

## 8. Strategie per evitare degrado qualitativo

Per evitare che il refinement degradi la qualità del testo o introduca allucinazioni logiche:

1. **Conservazione delle parti corrette**
   - Nel prompt, chiedere esplicitamente: “Mantieni intatti i fatti e le parti del ragionamento non menzionate nel feedback come errate”.
   - In futuro, si può fare diff strutturale tra `logic_program_k` e `logic_program_k-1` e penalizzare cambiamenti inutili.

2. **Controllo di regressione**
   - Se una nuova iterazione **peggiora** F1 di molto, rispetto alla precedente, il controller può decidere di scartarla e usare lo stato precedente.

3. **Fragment logico limitato**
   - La DSL v2 (vista nell’altro canvas) sarà progettata per cadere in un frammento di logica decidibile/gestibile (tipo quantificatori limitati, niente aritmetica pesante arbitraria).
   - Questo riduce il rischio di `unknown` e migliora la stabilità di Z3.

---

## 9. Interfacce software suggerite

Per rendere il loop chiaro e mantenibile, conviene definire alcune interfacce/pseudo‑classi:

```python
class LLMOutput(BaseModel):
    final_answer: str
    logic_program: Dict[str, Any]

class LogicFeedback(BaseModel):
    status: Literal[
        "consistent_entails",
        "consistent_no_entailment",
        "inconsistent",
        "unknown",
    ]
    conflicting_axioms: List[str] = []
    missing_links: List[str] = []
    human_summary: str = ""
    # opzionali: unsat_core_raw, model_snapshot

class IterationState(BaseModel):
    iter_index: int
    llm_output: LLMOutput
    logic_feedback: LogicFeedback
    metrics: Dict[str, float]

class NSLAIterativeController:
    def __init__(self, max_iters: int = 3, eps: float = 0.01):
        ...

    def run(self, question: str) -> Tuple[IterationState, List[IterationState]]:
        ...

    def should_stop(self, history: List[IterationState]) -> bool:
        ...

    def select_best_state(self, history: List[IterationState]) -> IterationState:
        ...
```

Queste astrazioni rendono più semplice:
- scrivere test unitari;
- fare benchmark offline su dataset;
- cambiare policy di stop senza toccare Z3 o la DSL.

---

## 10. Riepilogo decisionale

- Il loop iterativo LLM ↔ Z3 **non è il default**, ma una **modalità avanzata** per ricerca e casi complessi.
- Ogni iterazione produce uno stato completo (output LLM + feedback Z3 + metriche).
- Z3 non restituisce solo SAT/UNSAT: un modulo di `logic_feedback` traduce il risultato in insight strutturati.
- Un **controller** centrale gestisce iterazioni, criteri di stop e selezione del miglior stato.
- Il benchmark v2 misurerà se il loop porta un vantaggio reale rispetto a NSLA v1.

Questo design rende il loop:
- **riproducibile** (stati e history salvabili);
- **analizzabile** (metriche per iterazione);
- **sicuro** rispetto ai loop infiniti (max_iters, soglie, regressione controllata).

