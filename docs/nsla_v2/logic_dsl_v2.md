# NSLA Logic DSL v2 – Specifica operativa

Versione: `2.1`  
Ultimo aggiornamento: 2025-11-15  
Responsabile: ANSA (Architetto Neuro-Simbolico Autonomo)

---

## 1. Scopo

La DSL logica v2 definisce il formato canonico che il layer simbolico del progetto NSLA utilizza per:

1. **Descrivere** i fatti e le regole legali a partire dall’output dell’LLM.
2. **Tradurre** la struttura JSON in vincoli SMT (Z3).
3. **Verificare** la coerenza logica e generare feedback strutturato da esporre al loop LLM ↔ Z3.

Questa specifica è vincolante per tutti i moduli M3–M7 (preprocessing, translator, logic_feedback, pipeline).

---

## 2. Struttura del `logic_program`

Ogni programma logico deve essere un JSON con i campi seguenti:

```jsonc
{
  "dsl_version": "2.1",
  "sorts": {
    "Debitore": {"extends": "Soggetto"},
    "Creditore": {"extends": "Soggetto"},
    "Contratto": {},
    "Danno": {}
  },
  "constants": {
    "Professionista": {"sort": "Debitore"},
    "Cliente": {"sort": "Creditore"},
    "ContrattoServizi": {"sort": "Contratto"},
    "DannoEconomico": {"sort": "Danno"}
  },
  "predicates": {
    "Contratto": {"arity": 1, "sorts": ["Contratto"], "description": "..."},
    "Inadempimento": {"arity": 2, "sorts": ["Debitore","Contratto"], "description": "..."}
  },
  "facts": {
    "has_question_mark": true,
    "Contratto": ["ContrattoServizi"]
  },
  "rules": [
    {
      "condition": "(and (Contratto ContrattoServizi) (Inadempimento Professionista ContrattoServizi))",
      "conclusion": "(ResponsabilitaContrattuale Professionista Cliente ContrattoServizi)",
      "id": "r1"
    }
  ],
  "axioms": [
    {"id": "a1", "formula": "(implies (Inadempimento Professionista ContrattoServizi) (Imputabilita Professionista ContrattoServizi))"}
  ],
  "query": "(ResponsabilitaContrattuale Professionista Cliente ContrattoServizi)"
}
```

### Regole di validazione
1. `dsl_version` è obbligatorio e per Fase 1 vale `"2.1"`.
2. `sorts` deve elencare solo tipi conosciuti (vedi §3). È ammesso `extends` per ereditarietà semplice.
3. `constants` richiedono sempre il campo `sort` (stringa). Possono includere metadati aggiuntivi (es. `label`), ignorati dal translator.
4. `predicates` devono specificare:
   - `arity`: intero ≥ 0
   - `sorts`: array di lunghezza = `arity`
   - `description` (facoltativo ma consigliato)
   - `synonyms` (lista di stringhe) opzionale, utile per prompt.
5. `facts` è un dizionario:
   - per predicate 0-arity: `{"has_question_mark": true}`
   - per predicate n-arity: `{"Contratto": [["ContrattoServizi"]]}` (lista di tuple).
   - informazioni booleane dal preprocess (`has_question_mark`, `contains_euro_amount`, …) devono essere 0-arity e verranno materializzate se true.
6. `rules.condition` e `rules.conclusion` devono essere espressioni infisse in stile Lisp giglia (`(Pred arg1 arg2)`), oppure combinazioni con `and`, `or`, `not`, `implies`.
7. `axioms` è opzionale ed è pensato per compatibilità con DSL v1: `formula` viene passato al parser storico.
8. `query` è facoltativa ma raccomandata; se assente il translator assume `consistent_no_entailment` di default.

---

## 3. Vocabolario canonico

### 3.1 Sorts principali
| Sort            | Descrizione                                  | Sinonimi |
|----------------|----------------------------------------------|----------|
| `Soggetto`      | Entità generica (persona fisica/giuridica)   | Persona, Parte |
| `Debitore`      | Parte obbligata all’adempimento              | - |
| `Creditore`     | Parte titolare della pretesa                 | - |
| `Professionista`| Operatore che agisce per scopi professionali | Operatore economico |
| `Consumatore`   | Persona fisica che agisce per scopi privati (art. 3 Codice del Consumo) | Cliente |
| `Contratto`     | Oggetto negoziale                           | Accordo |
| `Bene`          | Bene materiale o immateriale                | Cosa |
| `BeneRegistrato`| Bene mobile soggetto a registrazione (es. auto) | Veicolo |
| `Marchio`       | Segno distintivo registrato                 | Trademark |
| `Prestazione`   | Oggetto dell’obbligazione                    | - |
| `Danno`         | Pregiudizio economico o non patrimoniale     | - |
| `Evento`        | Fatti rilevanti (violazioni, sinistri)       | - |
| `MisuraCautelare` | Misura cautelare personale o reale (artt. 272 ss. c.p.p.) | - |
| `Pena`          | Sanzione penale principale/accessoria (R.D. 19/10/1930 n. 1398) | - |

### 3.2 Predicati canonici (estratto)
| Nome | Firma | Descrizione | Sinonimi |
|------|-------|-------------|----------|
| `Contratto(Contratto)` | 1 arg | Esistenza di un contratto | “contratto valido” |
| `Consenso(Soggetto, Contratto)` | 2 arg | Consenso valido delle parti (artt. 1325-1326 c.c.) | accordo di volontà |
| `CapacitaContrattuale(Soggetto)` | 1 arg | Capacità di concludere contratti (art. 1425 c.c.) | capacità di agire |
| `OggettoDeterminato(Contratto)` | 1 arg | Oggetto possibile e determinato/determinabile (art. 1346 c.c.) | oggetto determinato |
| `FormaPrescritta(Contratto)` | 1 arg | Forma ad substantiam quando richiesta | forma richiesta |
| `ContrattoValido(Debitore, Contratto)` | 2 arg | Contratto valido (artt. 1325 ss. c.c.) | validità contratto |
| `Inadempimento(Debitore, Contratto)` | 2 arg | Mancato adempimento | violazione contratto |
| `Adempimento(Debitore, Contratto)` | 2 arg | Esecuzione corretta | esecuzione prestazione |
| `HaObbligo(Debitore, Creditore, Contratto)` | 3 arg | Relazione obbligatoria derivante da uno specifico contratto | obbligo contrattuale |
| `ResponsabilitaContrattuale(Debitore, Creditore, Contratto)` | 3 arg | Responsabilità debitoria | responsabilità del professionista |
| `ResponsabilitaCivileColpa(Soggetto, Danno)` | 2 arg | Responsabilità ex art. 2043 c.c. | responsabilità aquiliana |
| `DifettoConformita(Bene)` | 1 arg | Difetto di conformità (art. 129 Codice del Consumo) | vizio del prodotto |
| `DirittoSceltaRemedy(Consumatore, Bene)` | 2 arg | Diritti del consumatore (art. 130 Codice del Consumo) | garanzia legale |
| `ContrattoAdesione(Contratto)` | 1 arg | Contratto predisposto unilateralmente (art. 1341 c.c.) | contratto di adesione |
| `TrascrizioneOpponibileATerzi(Contratto)` | 1 arg | Effetti prenotativi della trascrizione (art. 2645-bis c.c.) | opponibilità |
| `UsucapioneOrdinaria(Soggetto, Bene)` | 2 arg | Usucapione ventennale (art. 1158 c.c.) | usucapione ventennale |
| `UsucapioneAbbreviata(Soggetto, BeneRegistrato)` | 2 arg | Usucapione abbreviata (art. 1153 c.c.) | usucapione biennale |
| `Riciclaggio(Soggetto)` | 1 arg | Riciclaggio di proventi illeciti (art. 648-bis c.p.) | lavaggio di denaro |
| `ContraffazioneMarchio(Soggetto, Marchio)` | 2 arg | Contraffazione di marchio registrato (art. 473 c.p.) | uso illecito di marchio |
| `MisuraCautelarePersonale(MisuraCautelare)` | 1 arg | Misura cautelare personale (artt. 272 ss. c.p.p.) | misura personale |
| `MisuraCautelareReale(MisuraCautelare)` | 1 arg | Misura cautelare reale | misura reale |
| `Multa(Pena)` | 1 arg | Pena pecuniaria per delitti (art. 17 c.p.) | pena pecuniaria |
| `Ammenda(Pena)` | 1 arg | Pena pecuniaria per contravvenzioni (art. 17 c.p.) | pena pecuniaria contravvenzionale |
| `Risarcimento(Debitore, Creditore, Danno)` | 3 arg | Obbligo risarcitorio contrattuale | risarcimento del danno |
| `RisarcimentoIllecito(Soggetto, Soggetto, Danno)` | 3 arg | Obbligo risarcitorio da illecito (art. 2043 c.c.) | responsabilità aquiliana |
| `NessoCausale(Evento, Danno)` | 2 arg | Relazione causa-effetto | collegamento causale |
| `DannoPatrimoniale(Soggetto)` | 1 arg | Danno economico | perdita economica |
| `Mora(Debitore)` | 1 arg | Ritardo debitore | mora debendi |
| `Imputabilita(Debitore, Contratto)` | 2 arg | Imputabilità dell’inadempimento | colpa debitore |

La lista completa è centralizzata in `app/logic_dsl.py` sotto forma di dizionari Python riutilizzabili dai moduli runtime.

---

## 4. Guida all’uso runtime

### 4.1 Validatore statico (obiettivo Fase 1)
Prima di invocare Z3:
1. Verificare che tutti i predicati nelle `rules` e `facts` siano definiti o marcati `allow_undeclared=True` (solo per facts runtime).
2. Verificare che gli argomenti rispettino la firma dichiarata (sort coerenti).
3. Controllare duplicati di `id` in `rules` e `axioms`.
4. Segnalare errori come `UnknownPredicateError`, `InvalidArityError`, `TypeMismatchError` con messaggi contestuali.

### 4.2 Preprocessing facts
Il modulo `app/preprocessing.py` può aggiungere facts booleane 0-arity (es. `has_question_mark`). Questi facts devono essere accettati dal translator impostando `allow_undeclared=True` **solo** per i facts runtime.

### 4.3 Logging & tracing
Il translator deve loggare:
- DSL version,
- numero di predicati registrati,
- regole aggiunte al solver,
- eventuali warning (predicati mancanti, facts scartati).

Il modulo `logic_feedback` usa lo stesso vocabolario per produrre `missing_links` e `conflicting_axioms`. Qualsiasi nuovo predicato inserito in `logic_dsl.py` deve sempre essere accompagnato dagli alias per facilitare il prompt engineering.

---

## 5. Compatibilità e versioning
- La DSL v2.1 è compatibile con la DSL v1 tramite il campo `dsl_version` e la presenza delle sezioni `axioms`/`query` in formato stringa; il translator effettua fallback automatico alla pipeline legacy se `dsl_version != "2.1"`.
- Le versioni future (es. `2.2`) dovranno:
  - mantenere backward compatibility oppure prevedere una migrazione esplicita,
  - documentare in questa guida le differenze nella sezione “ChangeLog”.
- `app/logic_dsl.py` espone `DSL_VERSION = "2.1"` da importare nei moduli runtime; eventuali nuove versioni devono aggiornare questo valore e la tabella dei predicati.

---

## 6. ChangeLog
- **2025-11-17**: aggiunti `HaObbligo` e la nuova firma di `Risarcimento` (3 argomenti) per allineare i runtime con i pattern generati dall'LLM e ridurre i falsi positivi della guardrail.
- **2025-11-16**: aggiunto il predicato canonico `ContrattoValido` per allineare la guardrail con l'ontologia aggiornata e permettere ai runtime Phase 2 di validare i contratti proposti dall'LLM.
- **2025-11-18**: ampliata l'ontologia con predicati civili e penali (es. `Consenso`, `Riciclaggio`, `ContraffazioneMarchio`) basati sul Codice Civile e sul Codice Penale (Regio Decreto 19 ottobre 1930, n. 1398) per coprire i casi della Phase 4.
- **2025-11-15**: prima edizione della guida operativa (ANSA) per la Fase 1 della roadmap. Centralizzate definizioni di sorts/predicati e stabilite regole di validazione.


