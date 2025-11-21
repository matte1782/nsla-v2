# NSLA v2 – Guida tecnica per la DSL logica

## 1. Obiettivi della DSL logica v2

La DSL logica v2 è il "linguaggio ponte" tra LLM e Z3. Gli obiettivi principali sono:

1. **Correttezza teorica**
   - Ogni programma DSL deve poter essere tradotto in modo deterministico in formule Z3.
   - Il frammento logico deve essere **decidibile** e ben supportato dal solver (evitare combinazioni esplosive di quantificatori e aritmetica complessa).

2. **Canonicità e unificazione del linguaggio legale**
   - Una stessa norma/istituto giuridico può essere espresso in molti modi in linguaggio naturale.
   - In DSL deve esistere **un solo modo canonico** per rappresentare quello stesso concetto.

3. **Allineamento con il dominio legale**
   - La DSL deve riflettere concetti giuridici stabili (es. ResponsabilitàCivile, NessoCausale, Inadempimento, Dolo, ecc.).
   - Ogni predicato DSL è legato a un concetto dell'ontologia legale interna.

4. **Machine-friendliness per LLM**
   - Struttura JSON rigida, schema stabile e documentato.
   - Vocabolario chiuso di tipi e predicati (con versione esplicita).
   - Esempi few-shot coerenti per aiutare il modello a non "inventare" nuovi simboli.

5. **Validabilità e debugging**
   - Possibilità di validare il programma DSL *prima* di chiamare Z3 (validator statico).
   - Ogni errore (tipo sbagliato, predicato sconosciuto, arità errata) deve essere spiegabile e loggato.

---

## 2. Struttura generale della DSL logica v2

La DSL è rappresentata come JSON strutturato con un header di versione e sezioni principali.

```json
{
  "dsl_version": "2.0",
  "language": "it",
  "meta": {
    "case_id": "case_001",
    "source": "user_query|dataset",
    "jurisdiction": "IT",
    "time_reference": "2024"
  },
  "ontology_version": "1.0",
  "entities": [
    {
      "id": "P1",
      "type": "PersonaFisica",
      "roles": ["attore"],
      "attributes": {"nome": "Mario"}
    }
  ],
  "facts": [
    {"pred": "EsisteContratto", "args": ["P1", "P2", "Contr1"]},
    {"pred": "Inadempimento", "args": ["P2", "Contr1"]}
  ],
  "rules": [
    {
      "id": "r1",
      "if": [
        {"pred": "EsisteContratto", "args": ["X", "Y", "C"]},
        {"pred": "Inadempimento", "args": ["Y", "C"]},
        {"pred": "DannoPatrimoniale", "args": ["X"]}
      ],
      "then": {"pred": "ResponsabilitaContrattuale", "args": ["Y", "X", "C"]}
    }
  ],
  "query": {
    "goal": {"pred": "ResponsabilitaContrattuale", "args": ["P2", "P1", "Contr1"]}
  }
}
```

### 2.1 Sezioni principali

- `dsl_version`: versione della DSL (es. "2.0"). Permette di mantenere retrocompatibilità.
- `ontology_version`: versione dell’ontologia legale (insieme di predicati/concetti ammessi).
- `entities`: elenco di oggetti giuridicamente rilevanti (persone, contratti, eventi).
- `facts`: fatti atomici sul caso concreto, istanze di predicati sull’ontologia.
- `rules`: regole inferenziali (implicazioni) in forma di pattern se/allora.
- `query`: formula da verificare (entailment) o da soddisfare con Z3.

### 2.2 Vincoli teorici

Per garantire decidibilità e performance, imponiamo:

- **Logica del primo ordine a frammento controllato**:
  - Prevalentemente quantificatore-free, con variabili trattate come simboli universali nelle regole.
  - Nessuna ricorsione non stratificata nelle regole.

- **Aritmetica limitata**:
  - Linear arithmetic su interi e reali (es. danni ≥ 0, termini temporali, soglie).

- **Predicati tipati**:
  - Ogni predicato ha firma fissa, dichiarata nell’ontologia (es. `ResponsabilitaContrattuale(Obbligato, AventeDiritto, Contratto)`).
  - I tipi delle costanti/variabili devono rispettare la firma.

---

## 3. Ontologia legale e vocabolario canonico

### 3.1 Problema: una legge, molti modi di dirla

Lo stesso contenuto normativo può essere espresso come:

- "responsabilità contrattuale del debitore";
- "il debitore risponde per inadempimento";
- "il contraente inadempiente è responsabile verso la controparte".

Se lasciamo che il LLM inventi predicati arbitrari (`ResponsabilitaDebitore`, `RispondePerInadempimento`, ecc.), il layer simbolico perde consistenza. Invece, dobbiamo:

1. Definire un **vocabolario canonico** di concetti legali → ontologia.
2. Fornire al LLM una **mappa di sinonimi** da linguaggio naturale a concetto canonico.
3. Validare a runtime che ogni predicato DSL appartenga al vocabolario.

### 3.2 Struttura dell’ontologia

L’ontologia è un file versionato (es. `ontology/legal_it_v1.yaml`) che elenca:

```yaml
ontology_version: "1.0"
predicates:
  - name: ResponsabilitaContrattuale
    args: [Obbligato, AventeDiritto, Contratto]
    description: "Il soggetto Obbligato è responsabile contrattualmente verso AventeDiritto in relazione al Contratto."
    synonyms:
      - "responsabilità contrattuale"
      - "responsabilità del debitore"
      - "risponde per inadempimento"

  - name: Inadempimento
    args: [Debitore, Contratto]
    description: "Il Debitore non adempie alla propria obbligazione contrattuale."
    synonyms:
      - "mancato adempimento"
      - "violazione del contratto"

  - name: DannoPatrimoniale
    args: [Soggetto]
    description: "Il Soggetto subisce un danno economicamente valutabile."
    synonyms:
      - "danno economico"
      - "perdita patrimoniale"
```

Proprietà chiave:

- **Nome canonico** (`name`): l’unico che può apparire in `facts`, `rules`, `query`.
- **Signature** (`args`): tipi degli argomenti per validazione.
- **Sinonimi**: frasi NL che il LLM può usare nel testo discorsivo, ma che vanno mappate al nome canonico in DSL.

### 3.3 Come unifichiamo formulazioni diverse

Pipeline di unificazione:

1. **Pre‑estrazione concetti dal testo**
   - Il LLM (con prompt dedicato) estrae concetti legali citati nel caso in forma semantica:

     ```json
     {
       "concepts": [
         {"text": "responsabilità del debitore", "canonical_pred": "ResponsabilitaContrattuale"},
         {"text": "mancato adempimento", "canonical_pred": "Inadempimento"}
       ]
     }
     ```

2. **Normalizzazione verso l’ontologia**
   - Un modulo di normalizzazione verifica che `canonical_pred` esista in `ontology.predicates`.
   - Se non esiste, il programma DSL viene rigettato o marcato come da correggere.

3. **Uso esclusivo di nomi canonici nella DSL**
   - Nel JSON che va a Z3, **solo** `name` canonici sono ammessi.
   - I sinonimi vivono nel testo discorsivo (`final_answer`) o nella fase di estrazione concetti.

4. **Validator statico**
   - Prima di inviare il programma a Z3:
     - controlliamo che ogni `pred` sia nel vocabolario;
     - che il numero di `args` corrisponda alla firma;
     - che i tipi referenziati esistano in `entities` con tipo coerente.

Questa strategia fa sì che 100 modi diversi di descrivere la stessa regola convergano su **uno** schema DSL interno.

---

## 4. Schema dettagliato della DSL logica v2

### 4.1 Entities

```json
{
  "id": "P1",
  "type": "PersonaFisica",    
  "roles": ["attore", "creditore"],
  "attributes": {
    "nome": "Mario Rossi",
    "codice_fiscale": "..."
  }
}
```

- `id`: etichetta univoca nel caso.
- `type`: deve essere in un vocabolario di tipi (es. `PersonaFisica`, `PersonaGiuridica`, `Contratto`, `Evento`).
- `roles`: opzionale, ruoli processuali o funzionali.
- `attributes`: metadati non usati direttamente da Z3 ma utili per spiegazioni / UI.

### 4.2 Facts

```json
{"pred": "EsisteContratto", "args": ["P1", "P2", "Contr1"]}
{"pred": "Inadempimento", "args": ["P2", "Contr1"]}
{"pred": "DannoPatrimoniale", "args": ["P1"]}
```

- Ogni `pred` deve essere definito in ontologia.
- Gli argomenti devono essere id di `entities` o costanti tipizzate (es. numeri, date), secondo firma.

### 4.3 Rules (implicazioni)

```json
{
  "id": "r1",
  "if": [
    {"pred": "EsisteContratto", "args": ["X", "Y", "C"]},
    {"pred": "Inadempimento", "args": ["Y", "C"]},
    {"pred": "DannoPatrimoniale", "args": ["X"]}
  ],
  "then": {"pred": "ResponsabilitaContrattuale", "args": ["Y", "X", "C"]}
}
```

- Variabili (`X`, `Y`, `C`) sono trattate come implicitamente universalmente quantificate.
- Niente cicli ricorsivi non stratificati.
- Possibile estensione con vincoli aritmetici/temporali in un campo `constraints`.

### 4.4 Query

```json
{
  "goal": {"pred": "ResponsabilitaContrattuale", "args": ["P2", "P1", "Contr1"]}
}
```

- Query singola o combinazione booleana di più obiettivi (estendibile con AND/OR se necessario).
- In Z3 viene tradotta come formula da verificare (entailment o satisfiability a seconda del design).

---

## 5. Integrazione con Z3 e garanzie di correttezza

### 5.1 Translator v2 (JSON DSL → Z3)

Principi:

- Traduzione **puramente meccanica**: niente euristiche semantiche dentro il translator.
- Mappature tipiche:
  - Predicati → funzioni/predicati Z3.
  - Entities → costanti di tipo opportuno.
  - Rules → implicazioni logiche.
  - Facts → asserzioni.

Ogni passo deve preservare la struttura logica:

- `facts` + `rules` costituiscono la base di conoscenza.
- `query` viene trasformata in formula di verifica.

### 5.2 Validatore statico prima di Z3

Il validatore DSL esegue:

1. **Validazione sintattica** (JSON schema / Pydantic):
   - campi obbligatori presenti;
   - tipi corretti (stringhe vs liste, ecc.).

2. **Validazione ontologica**:
   - tutti i `pred` appartengono all’ontologia corrente;
   - le arità sono rispettate;
   - i tipi degli argomenti sono coerenti con le definizioni dei predicati.

3. **Validazione semantica minima**:
   - nessun duplicato di id regola;
   - nessuna referenza a entità non definite.

Se qualsiasi controllo fallisce, il programma **non viene mandato a Z3**; invece generiamo un oggetto `logic_feedback` con stato `invalid_dsl` e messaggi di errore, che possono essere usati dal loop LLM nella v2.

---

## 6. Strategia per aiutare gli LLM a non "perdere il filo"

Per far sì che gli LLM rispettino la DSL v2 in modo stabile:

1. **Prompt con schema esplicito**
   - Fornire nell’istruzione:
     - schema JSON;
     - elenco dei predicati canonici rilevanti per il caso;
     - esempi completi (input domanda → output DSL).

2. **Vocabolario chiuso**
   - Dichiarare nel prompt che l’LLM può usare **solo** i predicati elencati.
   - Penalizzare/out‑of‑scope ogni predicato non riconosciuto, tramite validator.

3. **Feedback di errore strutturato**
   - Quando il validator trova errori, ritornare all’LLM un feedback JSON:

     ```json
     {
       "status": "invalid_dsl",
       "errors": [
         {
           "type": "UNKNOWN_PREDICATE",
           "pred": "ResponsabilitaDebitore",
           "suggested_pred": "ResponsabilitaContrattuale"
         }
       ]
     }
     ```

   - Il prompt di refining può chiedere al modello di correggere il programma **senza riscriverlo interamente**, mantenendo ciò che è valido.

4. **Test di regressione per i prompt**
   - Ogni nuova versione di prompt per la DSL viene testata su un set fisso di casi.
   - Si misura la % di DSL parseabili e semanticamente valide.

---

## 7. Dataset legali esterni e coerenza della DSL

Per integrare dataset legali open‑source senza rompere la DSL:

1. **Mappatura concettuale**
   - Per ogni dataset, mappare gli istituti legali usati (es. "breach of contract", "liability") ai concetti della nostra ontologia.
   - Se manca un concetto, valutare se introdurlo nell’ontologia con attenzione (evitando proliferazione incontrollata).

2. **Normalizzazione linguistica**
   - Nei casi in cui i dataset siano in inglese/altre lingue, introdurre una layer di mapping NL → concetto canonico della nostra ontologia italiana/interna.

3. **Test di compatibilità**
   - Prima di usare i nuovi casi nel benchmark, verificare che possano essere espressi in DSL v2 senza forzature.

---

## 8. Sintesi operativa

- La DSL logica v2 definisce **un singolo vocabolario canonico** di concetti legali, mantenuto in un’ontologia versionata.
- Il LLM può parlare in molti modi diversi di una stessa regola nel testo naturale, ma in DSL deve sempre mappare a **uno stesso predicato canonico**.
- Un validator statico + translator deterministico garantiscono che solo programmi corretti arrivino a Z3.
- Il feedback strutturato (errori di DSL, status Z3, unsat‑core) è la base per il loop iterativo della v2: LLM non solo viene verificato, ma viene guidato a correggere il proprio ragionamento.

Questa guida diventa il riferimento per:
- scrivere i prompt di estrazione e generazione DSL;
- implementare i moduli `translator_v2`, `logic_feedback` e validator;
- modellare nuovi concetti legali in modo consistente e teoricamente fondato.

