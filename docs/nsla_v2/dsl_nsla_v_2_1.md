# DSL logica v2.1 per NSLA – Specifica Formale  
*Versione Markdown ufficiale, derivata dal documento tecnico PDF (Deep Research 2025).*

---

## Indice dei contenuti

- [1. Introduzione e Scopo](#1-introduzione-e-scopo)
- [2. Architettura Logica della DSL](#2-architettura-logica-della-dsl)
  - [2.1 Struttura generale](#21-struttura-generale)
  - [2.2 Moduli e namespaces](#22-moduli-e-namespaces)
- [3. Tipi e Sorts](#3-tipi-e-sorts)
  - [3.1 Definizione dei sorts](#31-definizione-dei-sorts)
  - [3.2 Ereditarietà tra sorts](#32-ereditarieta-tra-sorts)
- [4. Sintassi Formale](#4-sintassi-formale)
  - [4.1 Espressioni logiche](#41-espressioni-logiche)
  - [4.2 Operatori e precedenze](#42-operatori-e-precedenze)
- [5. Semantica e Regole di Valutazione](#5-semantica-e-regole-di-valutazione)
- [6. Design Laws](#6-design-laws)
- [7. Esempi Applicativi](#7-esempi-applicativi)
- [8. Appendice Tecnica](#8-appendice-tecnica)

---

## 1. Introduzione e Scopo

La DSL logica v2.1 per NSLA è un linguaggio formale progettato per definire, validare e interpretare strutture logiche all'interno di sistemi di analisi semantica e modelli computazionali di inferenza.

Obiettivi principali:

- Fornire una sintassi rigorosa e leggibile per l'espressione di vincoli logici e semantici.
- Consentire interoperabilità tra moduli logici e semantici del framework NSLA.
- Offrire un modello formale estensibile, supportando sia inferenza deduttiva che modellazione descrittiva.

---

## 2. Architettura Logica della DSL

### 2.1 Struttura generale

La DSL è organizzata in moduli indipendenti, ciascuno dotato di un proprio *namespace* e insieme di regole. Ogni modulo può importare definizioni da altri moduli mediante la direttiva `import`.

Esempio:

```json
{
  "module": "logic.core",
  "imports": ["math.primitives", "types.boolean"],
  "exports": ["and", "or", "not"]
}
```

### 2.2 Moduli e namespaces

Ogni modulo è identificato da un nome univoco composto da uno o più segmenti separati da punti.

- `core` definisce operatori fondamentali.
- `math` definisce primitive numeriche e relazionali.
- `types` definisce i sorts di base.

Esempio:

```json
{
  "namespace": "logic.math",
  "symbols": ["+", "-", "*", "/", ">", "<"]
}
```

---

## 3. Tipi e Sorts

### 3.1 Definizione dei sorts

I sorts rappresentano le categorie semantiche di base. Ogni simbolo è associato a un sort.

| Sort | Descrizione |
|------|--------------|
| `Bool` | Valore logico (true/false) |
| `Int` | Numero intero |
| `Float` | Numero decimale |
| `String` | Sequenza di caratteri |
| `Entity` | Oggetto o entità logica |

### 3.2 Ereditarietà tra sorts

Un sort può ereditare da un altro per specializzazione. Ad esempio:

```json
{
  "sort": "Number",
  "extends": ["Int", "Float"]
}
```

Regola di compatibilità:

- Se `A` eredita da `B`, allora ogni istanza di `A` è utilizzabile dove è richiesto un `B`.

---

## 4. Sintassi Formale

### 4.1 Espressioni logiche

Le espressioni seguono la sintassi BNF estesa:

```
<expr> ::= <atom> | <unary> | <binary>
<atom> ::= true | false | <identifier>
<unary> ::= (not <expr>)
<binary> ::= (<expr> <op> <expr>)
<op> ::= and | or | implies | equals
```

Esempio:

```json
{
  "expr": "(and (> x 0) (< x 10))"
}
```

### 4.2 Operatori e precedenze

| Operatore | Descrizione | Precedenza |
|------------|--------------|-------------|
| `not` | Negazione | Alta |
| `and` | Coniugazione logica | Media |
| `or` | Disgiunzione logica | Bassa |
| `implies` | Implicazione | Molto bassa |

---

## 5. Semantica e Regole di Valutazione

La valutazione delle espressioni avviene in un contesto di ambiente (environment) che associa identificatori a valori.

Regole:

1. `(not true)` → `false`
2. `(and true X)` → `X`
3. `(or false X)` → `X`
4. `(implies A B)` → `(or (not A) B)`

Esempio di ambiente:

```json
{
  "env": {
    "x": 5,
    "y": 8
  },
  "expr": "(and (> x 0) (< y 10))"
}
```

Risultato della valutazione: `true`.

---

## 6. Design Laws

1. **Law of Determinacy**  
   Ogni espressione deve avere un risultato deterministico dato un ambiente chiuso.

2. **Law of Extensibility**  
   Ogni modulo può estendere sorts o operatori senza rompere compatibilità retroattiva.

3. **Law of Purity**  
   Gli operatori logici non devono produrre effetti collaterali.

4. **Law of Composability**  
   Le espressioni devono poter essere combinate arbitrariamente purché i sorts coincidano.

5. **Law of Referential Transparency**  
   La sostituzione di un'espressione con il suo valore deve preservare la semantica.

---

## 7. Esempi Applicativi

Esempio di vincolo logico per validazione di intervallo numerico:

```json
{
  "rule": "is_valid_range",
  "definition": "(and (>= value min) (<= value max))",
  "types": {
    "value": "Float",
    "min": "Float",
    "max": "Float"
  }
}
```

Esempio di combinazione modulare:

```json
{
  "module": "quality.checks",
  "imports": ["logic.core"],
  "rule": "(implies (is_valid_range) (not is_error))"
}
```

---

## 8. Appendice Tecnica

### Versione

- DSL logica **v2.1**  
- Revisione formale: **NSLA-Core/DeepResearch-2025-04**  
- Autori: *Unità di Ricerca Logica Computazionale (NSLA Project)*

### Struttura JSON Schema di riferimento

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "NSLA Logic DSL",
  "type": "object",
  "properties": {
    "module": { "type": "string" },
    "imports": { "type": "array", "items": { "type": "string" } },
    "exports": { "type": "array", "items": { "type": "string" } },
    "expr": { "type": "string" }
  },
  "required": ["module", "expr"]
}
```

