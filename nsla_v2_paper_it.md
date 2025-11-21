# **NSLA-v2: Un Prototipo Neuro-Simbolico per il Ragionamento Legale**
### **Rapporto di Ricerca Ibrido (Tecnico + Accademico)**  
**Autore:** Matteo Panzeri (con assistenza di strumenti basati su LLM)  
**Data:** 2025

---

# **Abstract**
Questo documento presenta lo sviluppo, l'analisi critica e l'archiviazione del progetto **NSLA-v2**, un prototipo neuro-simbolico creato per esplorare se **l'entailment logico SMT (Z3)** possa fungere da fondamento per compiti di ragionamento giuridico. La pipeline del sistema integra: (1) estrazione strutturata, (2) un linguaggio formale (DSL) per clausole legali, (3) un processo neuro-simbolico multi-step e (4) un livello di validazione tramite solver logici.

Sebbene i primi test su casi sintetici abbiano mostrato risultati promettenti, esperimenti più rigorosi hanno evidenziato limiti strutturali: il diritto è **contestuale**, **non monotono**, **interpretativo**, mentre Z3 opera esclusivamente con logiche **monotone**, **totalmente specificate** e prive di contesto implicito. Questa incompatibilità teorica impedisce inferenze affidabili, pur in presenza di un DSL solido, predicate ben definiti e vincoli tecnicamente corretti.

NSLA-v2 non raggiunge l'obiettivo originario, ma offre contributi importanti: componenti modulari riutilizzabili, un corpus di casi di test, un'analisi dettagliata dei limiti del ragionamento SMT nel dominio legale e la nascita di nuove idee di ricerca (BinaryLLM, Neuro-Symbolic Concept Generator, Fractal Reasoning Engine). Il progetto rappresenta un esempio di **ricerca guidata dal fallimento**, essenziale per avanzare nel campo dell'IA.

---

# **1. Introduzione**
Il ragionamento legale è un dominio naturale per testare tecniche neuro-simboliche grazie alla presenza simultanea di testi complessi, regole, eccezioni, strutture gerarchiche e interpretazioni. NSLA-v2 nasce per verificare se sia possibile:

- rappresentare clausole legali in modo formale (via DSL),
- tradurre automaticamente il testo in formule logiche,
- utilizzare Z3 per valutare coerenza, obblighi derivati, contraddizioni e inferenze.

L'idea iniziale era costruire un sistema dove:

```
Testo → Estrazione Strutturata → DSL → Normalizzazione → Guardrail → Codifica Z3 → Soluzione SMT → Feedback
```

## **Obiettivo scientifico**
Capire se un motore SMT possa fungere da "cuore logico" per sistemi legali automatizzati.

## **Esito**
L'esito finale è negativo, ma illuminante: Z3 non è adatto alla complessità interpretativa del diritto.

---

# **2. Contesto e Lavori Correlati**
## **2.1 Neuro-Symbolic AI**
I sistemi neuro-simbolici combinano:
- riconoscimento statistico (LLM, reti neurali),
- ragionamento simbolico (logica, vincoli, inferenze).

Sono efficaci in domini come:
- verifica formale,
- program synthesis,
- sistemi safety-critical.

## **2.2 Solver SMT (Z3)**
Z3 eccelle in:
- dimostrazione automatica di proprietà,
- verifica di contratti software,
- analisi statica,
- modellazione di vincoli matematici.

Limite fondamentale: richiede **specificazione totale**, non gestisce ambiguità né contesto.

## **2.3 Ragionamento Giuridico**
Proprietà del ragionamento legale:
- **non monotono** (aggiungere fatti può cambiare le conclusioni),
- **contestuale** (dipende dall'interpretazione e dal contesto sociale),
- **normativamente gerarchico** (eccezioni, priorità, precedenti),
- **aperto** (concetti vaghi: "ragionevole", "adeguato", ecc.).

Queste proprietà violano i presupposti della logica SMT.

---

# **3. Progettazione del Sistema**
## **3.1 Architettura della Pipeline**
```
Testo → Estrattore Strutturato → DSL → Normalizzazione → Guardrail → Traduzione Z3 → Solver → Feedback
```

## **3.2 Componenti Principali**
- **Estrattore strutturato**: individua attori, obblighi, condizioni.
- **DSL**: formalizzazione di clausole legali.
- **Normalizzatore**: uniforma predicati, arità, tipi.
- **Guardrail**: blocca DSL malformati.
- **Traduttore Z3**: genera simboli, vincoli e formule logiche.
- **Solver SMT**: calcola SAT/UNSAT e produce modelli.
- **Feedback Loop**: raffinamento iterativo.

## **3.3 Motivazioni progettuali**
L'architettura è:
- modulare,
- scalabile,
- deterministica,
- conforme ai principi di ingegneria formale.

---

# **4. Setup Sperimentale**
## **4.1 Dataset**
Casi sintetici di giurisprudenza contrattuale:
- acquisto,
- locazione,
- pagamento,
- consegna,
- risoluzione.

## **4.2 Compiti Valutati**
- consistenza DSL,
- rilevazione contraddizioni,
- robustezza normalizzazione,
- effetto dell'aggiunta di fatti sul modello logico.

## **4.3 Test**
- pytest (unit, integration, regression),
- casi avversariali,
- validazione dei modelli logici,
- test iterativi.

---

# **5. Risultati e Failure Modes**
## **5.1 Risultati Positivi**
- DSL stabile e coerente,
- encoding Z3 privo di errori,
- guardrail efficace,
- test robusti.

## **5.2 Errori strutturali (Failure Modes)**
### **1. Perdita di contesto semantico**
Il linguaggio naturale contiene implicature non traducibili in DSL.

### **2. Non-monotonicità**
L'aggiunta di fatti può alterare radicalmente le conclusioni.

### **3. Sovra-specificazione**
Z3 richiede specificazione completa, incompatibile con il diritto.

### **4. Mancanza di interpretazione dinamica**
Z3 non gestisce cambiamenti semantici contestuali.

### **5. Entailment ≠ Ragionamento legale**
Il ragionamento legale richiede eccezioni, contesto, priorità.

---

# **6. Discussione**
## **Perché il risultato negativo è prezioso**
Esso mostra i limiti dei solver SMT in domini complessi.

### **Conclusione chiave**
> Il limite non è tecnico, ma teorico: il diritto non è formalizzabile come logica monotona.

---

# **7. Lezioni Apprese**
### **Cosa ha funzionato**
- Architettura modulare,
- DSL robusto,
- Test esaustivi,
- Guardrail efficace.

### **Cosa NON ha funzionato**
- Uso di SMT come fondamento del ragionamento,
- Conservazione del contesto,
- Logica monotona in dominio interpretativo.

### **Lezione finale**
Il ragionamento legale richiede logiche:
- non monotone,
- contestuali,
- deontiche.

---

# **8. Direzioni Future**
- **BinaryLLM Protocol**: embedding binari a bassa energia.
- **Neuro-Symbolic Concept Generator**: generatore di concetti astratti verificati via Z3.
- **Fractal Reasoning Engine**: reasoning multilivello con auto-validazione.

---

# **9. Conclusione**
NSLA-v2 evidenzia che un approccio ingegneristico eccellente non può superare un mismatch teorico. Il progetto resta una base scientifica per ricerche future e come esempio di metodo rigoroso.

---

# **10. Ringraziamenti**
Realizzato da **Matteo Panzeri**, con supporto di agenti LLM avanzati e tecniche di reasoning assistito.

---

# **Appendice A: Struttura della Repository**

La repository `nsla-v2` è organizzata in modo modulare:

## **app/**
- pipeline neuro-simbolica,
- DSL,

