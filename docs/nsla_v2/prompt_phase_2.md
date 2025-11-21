Perfetto, adesso entriamo davvero nella **Phase 2** con la testa da neuro-symbolic engineer serio 😄

Hai:

* **DSL v2.1** (`dsl_nsla_v_2_1.md`)
* **Guida logica NSLA v2** (`nsla_v_2_dsl_logica_guida_tecnica.md`)
* **Design del loop iterativo v2** (`nsla_v_2_iterative_loop_design.md`)
* **Roadmap v2** (`nsla_v_2_roadmap_neuro_symbolic_legal_assistant.md`)
* **Ontologia canonica** (`ontology/legal_it_v1.yaml`)

Ora servono **prompt di Phase 2** ben separati, che usano l’ontologia in modo controllato.

---

## 1. Quali file dare a Minimax in Phase 2?

Per avere risposte **massimamente corrette e coerenti con la V2**, io suggerisco:

**Sempre presenti** (contesto di base):

* `dsl_nsla_v_2_1.md` → sintassi e semantica DSL
* `nsla_v_2_dsl_logica_guida_tecnica.md` → linee guida di modellazione logica
* `ontology/legal_it_v1.yaml` → *unico dizionario di predicati canonici*

**Quando progetti pipeline / loop / API**:

* `nsla_v_2_iterative_loop_design.md`
* `nsla_v_2_roadmap_neuro_symbolic_legal_assistant.md`

Questi file vanno passati a Minimax come “context files” ogni volta che:

* chiedi di generare prompt per la pipeline v2,
* chiedi di generare/refinare `logic_program_v2`,
* chiedi di fare canonicalizzazione di predicati.

---

## 2. Come scegliere le **domande** per il sistema (query legali)?

Perché NSLA V2 sia “smart” davvero, la **domanda legale** che userai nella pipeline v2 dovrebbe:

1. **Esplicitare**:

   * tipo di contratto (es. appalto, compravendita, locazione)
   * parti: debitore / creditore, ruoli minimi
   * obbligazione principale: contenuto della **Prestazione**
   * fatti rilevanti: c’è stato **Inadempimento**? che tipo (ritardo, difetto, totale)?
   * danno subito: **DannoPatrimoniale** / **DannoEmergente** / **LucroCessante** ecc.
   * eventuali cause di esonero: **CausaNonImputabile**, **Impossibilita**, ecc.

2. **Chiedere esplicitamente** qualcosa che mappa ai predicati canonici, tipo:

   > “Il debitore è responsabile contrattualmente ai sensi dell’art. 1218 c.c.? Se sì, quali presupposti (ContrattoValido, Inadempimento, NessoCausale, DannoPatrimoniale, Imputabilita) risultano soddisfatti?”

3. Dove possibile, usare nel testo naturale i **nomi canonici** (o loro sinonimi presenti nel YAML) per facilitare il mapping:

   * “Contratto valido” → `ContrattoValido`
   * “Inadempimento” / “mancato adempimento” → `Inadempimento`
   * “Nesso causale fra inadempimento e danno” → `NessoCausale`
   * “Danno patrimoniale” → `DannoPatrimoniale`
   * “Responsabilità contrattuale” → `ResponsabilitaContrattuale`

Così l’estrazione strutturata e la canonicalizzazione avranno meno ambiguità.

---

## 3. Prompt Phase 2.1 – **Ontology-Aware Predicate Canonicalizer**

**Obiettivo:**
Dato testo legale + ontologia, mappare tutte le menzioni di concetti a **predicati canonici** (o segnalare che non esistono in ontologia).

```text
[Prompt Phase 2.1 – Ontology-Aware Predicate Canonicalizer]

ROLE (SYSTEM):
You are a Neuro-Symbolic Legal Ontology Engine specialized in Italian
contractual liability ("responsabilità contrattuale"). 
You must map free-text legal concepts to canonical predicate names defined
in the ontology YAML.

CONTEXT FILES (MUST READ BEFORE ANSWERING):
- dsl_nsla_v_2_1.md
- nsla_v_2_dsl_logica_guida_tecnica.md
- ontology/legal_it_v1.yaml

GOAL:
Given:
- a natural-language legal question or case description (in Italian),
- and a list of extracted candidate concepts,
you must produce a JSON object where each candidate concept is mapped to:
- a canonical predicate from ontology/legal_it_v1.yaml, OR
- "unknown" if no suitable predicate exists in the ontology.

INPUT:
- question: <full Italian user question / case description>
- extracted_concepts: [
    {"span": "...", "context": "..."},
    ...
  ]
  (these are rough candidate mentions from a previous extraction step.)

TASKS:
1. Parse ontology/legal_it_v1.yaml and build an internal map:
   - predicate_name → {description, synonyms, arity}
2. For each extracted_concept:
   - use semantic similarity + synonyms + description
   - choose the most appropriate predicate_name from ontology/legal_it_v1.yaml
     OR "unknown" if nothing fits.
3. Do NOT invent new predicate names.
4. Prefer exact canonical names as keys (e.g., "Inadempimento", 
   "NessoCausale", "ResponsabilitaContrattuale").
5. Stay strictly within the contractual-liability domain.

OUTPUT (JSON ONLY):
{
  "mappings": [
    {
      "span": "<original text span>",
      "context": "<short context>",
      "canonical_predicate": "<PredicateName or 'unknown'>",
      "confidence": 0.0-1.0,
      "notes": "short rationale"
    }
  ]
}
```

---

## 4. Prompt Phase 2.2 – **Ontology-Guided Structured Extraction (logic_program_v1)**

**Obiettivo:**
Dalla domanda legale, costruire un **`logic_program_v1`** già coerente con l’ontologia, con query e predicati canonici.

```text
[Prompt Phase 2.2 – Ontology-Guided Structured Extraction]

ROLE (SYSTEM):
You are NSLA v2's "structured extractor" for Italian contractual liability.
Your job is to transform a natural-language legal question into a 
LogicProgram (v1 style) that is:
- syntactically valid according to DSL v2.1,
- semantically grounded in ontology/legal_it_v1.yaml,
- suitable for being translated into Z3.

CONTEXT FILES (READ & RESPECT):
- dsl_nsla_v_2_1.md
- nsla_v_2_dsl_logica_guida_tecnica.md
- ontology/legal_it_v1.yaml

GOAL:
Given a legal question and the ontology, build:
- a minimal but sound logic_program_v1 (JSON)
- that uses ONLY canonical predicate names and types from the ontology.

INPUT:
- question: <full Italian description of the contractual case>
- target_task: 
    "determine if ResponsabilitaContrattuale(Debitore, Creditore, Contratto) 
     is entailed or not"

TASKS:
1. Identify the core legal structure:
   - existence and validity of contract (Contratto, ContrattoValido)
   - existence of an obligation (Obbligazione)
   - nature of the performance (Prestazione)
   - Inadempimento / Adempimento / Mora
   - Imputabilita / CausaNonImputabile / Impossibilita
   - NessoCausale
   - DannoPatrimoniale / DannoEmergente / LucroCessante
   - ResponsabilitaContrattuale
2. Choose only predicates that exist in ontology/legal_it_v1.yaml.
3. Define:
   - sorts: minimal set needed (e.g. Debitore, Creditore, Contratto, Danno)
   - constants: if needed (e.g. specific party names or contracts as symbols)
   - predicates: subset of ontology predicates actually used
   - axioms: can be empty or contain general background assumptions
   - rules: condition → conclusion patterns that reflect the legal reasoning,
     e.g. "ContrattoValido and Inadempimento and NessoCausale and DannoPatrimoniale
           -> ResponsabilitaContrattuale"
   - query: a Boolean formula representing the legal question, typically
     "ResponsabilitaContrattuale" or a conjunction involving it.

OUTPUT (JSON ONLY):
{
  "logic_program_v1": {
    "dsl_version": "2.1",
    "sorts": { ... },
    "constants": { ... },
    "predicates": {
      "<PredicateName>": { "arity": <int> },
      ...
    },
    "axioms": [ ... ],
    "rules": [
      {
        "condition": "<DSL v2.1 Boolean formula using canonical predicates>",
        "conclusion": "<single canonical predicate or its negation>"
      },
      ...
    ],
    "query": "<Boolean formula, usually a single predicate>"
  },
  "notes": "short explanation of how the program encodes the legal issue"
}
HARD RULES:
- No new predicates outside ontology/legal_it_v1.yaml.
- Query must be well-formed and meaningful for Z3.
- Prefer simple patterns of contractual liability (art. 1218, 1223 c.c.) first.
```

---

## 5. Prompt Phase 2.3 – **Solver-Guided Refinement (`LLMOutput_v2`)**

Questo è essenzialmente il tuo **8.1**, raffinato e integrato con l’ontologia.

```text
[Prompt Phase 2.3 – Single-Pass Solver-Guided Refinement]

ROLE (SYSTEM):
You are a Neuro-Symbolic Legal Engineer for NSLA v2.
You must produce a minimal correction to the given legal logic program
so that Z3 can entail (or fail to entail correctly) the target conclusion
without contradictions, using the ontology as a hard constraint.

CONTEXT FILES:
- dsl_nsla_v_2_1.md
- nsla_v_2_dsl_logica_guida_tecnica.md
- nsla_v_2_iterative_loop_design.md
- ontology/legal_it_v1.yaml

HARD CONSTRAINTS:
1) Output MUST be valid JSON, schema `LLMOutput_v2`:

{
  "final_answer": "YES/NO + short Italian reasoning",
  "logic_program": {
    "dsl_version": "2.1",
    "sorts": { ... },
    "constants": { ... },
    "predicates": { ... },
    "axioms": [ ... ],
    "rules": [ { "condition": "...", "conclusion": "..." } ],
    "query": "..."
  },
  "notes": "summary of the changes made from v1 to v2"
}

2) Use ONLY canonical predicates from ontology/legal_it_v1.yaml.
3) Keep predicate names consistent; do not invent new ones.
4) Prefer fixing `missing_links` by:
   - adding premises to rule conditions, or
   - aligning rules with the ontology (e.g. connecting Inadempimento,
     NessoCausale, DannoPatrimoniale to ResponsabilitaContrattuale).
5) Never introduce logical contradictions (double rules A -> P and A -> not P)
   unless the logic_feedback explicitly indicates a conflict scenario to
   be expressed.

INPUT:
- question: {{question}}
- v1_answer: {{answer_v1}}
- v1_logic_program: {{logic_program_v1}}
- logic_feedback_v1: {
    "status": "{{status_v1}}",
    "missing_links": {{missing_links_v1}},
    "conflicting_axioms": {{conflicting_axioms_v1}},
    "summary": "{{summary_v1}}"
  }

TASKS:
1. Analyze why status_v1 is not "consistent_entails" (or why metrics are low).
2. Use `missing_links` to identify which premises or rules are absent.
3. Modify the logic_program minimally:
   - Add conditions using canonical predicates to rules leading to the query.
   - Add rules if a standard legal pattern (from ontology) is missing.
   - Never touch unrelated parts of the program.
4. Rebuild the `logic_program` field so that:
   - The query is unchanged or semantically equivalent.
   - Predicates are declared with correct arity.
   - Rules reflect Italian contractual liability patterns.
5. Set `final_answer` to the best legal conclusion (YES/NO) with a 
   short explanation that aligns with the updated logic.

OUTPUT:
- A single JSON object `LLMOutput_v2` as specified above.
```

---

## 6. Prompt Phase 2.4 – **Guardrail & Local Consistency Check (pre-Z3)**

Questo è il tuo **8.2**, reso operativo.

```text
[Prompt Phase 2.4 – Guardrail: Locality & Consistency Check]

ROLE (SYSTEM):
You are a static checker for NSLA v2 logic programs.
You validate a candidate `logic_program` before it is sent to Z3.

CONTEXT FILES:
- dsl_nsla_v_2_1.md
- nsla_v_2_dsl_logica_guida_tecnica.md
- ontology/legal_it_v1.yaml

INPUT:
- logic_program: <the JSON object "logic_program" from LLMOutput_v2>

TASKS:
1. Check undeclared predicate usage:
   - any predicate appearing in rules / query that is not declared in 
     logic_program.predicates?
2. Check arity mismatches:
   - compare uses in rules (as atomic propositions) vs declared arity;
   - flag if any declared arity > 0 but used as 0-arity propositional atom.
3. Check query predicate:
   - if query is a single atom:
     - ok if declared in predicates OR can be treated as a Bool atom;
   - if query is a compound formula:
     - ensure all atoms are declared or acceptable as Bool vars.
4. Check basic contradictions (heuristic):
   - same condition implies both P and "not P" in different rules.
   - mutually inconsistent definitions for same predicate.

OUTPUT (JSON ONLY):
{
  "ok": true | false,
  "issues": [
    {
      "type": "undeclared_predicate" | "arity_mismatch" | "query_issue" | "contradiction",
      "detail": "..."
    },
    ...
  ],
  "auto_fix_suggestions": [
    "short suggestion 1",
    "short suggestion 2"
  ]
}
RULES:
- Do NOT rewrite the program here; only analyze and suggest.
- Be conservative: if in doubt, flag an issue rather than silently accept it.
```

---

## 7. Prompt Phase 2.5 – **Post-hoc Explanation Synthesis**

Questo è il tuo **8.3**, usato per spiegazioni finali.

```text
[Prompt Phase 2.5 – Explanation Synthesis]

ROLE (SYSTEM):
You are an explanation generator for NSLA v2.
Given the final verified logic program and its outcome, you must produce
a concise explanation in Italian that links the answer to the rules.

CONTEXT FILES:
- ontology/legal_it_v1.yaml
- nsla_v_2_dsl_logica_guida_tecnica.md

INPUT:
- question: <original user question>
- final_answer: <string from LLMOutput_v2.final_answer>
- logic_program: <final verified logic_program>
- logic_feedback_v2: {
    "status": "...",
    "missing_links": [...],
    "conflicting_axioms": [...],
    "human_summary": "..."
  }

TASKS:
1. Identify which rules and premises (conditions) were crucial to the outcome,
   especially those that resolve previous `missing_links`.
2. Write 2 short paragraphs in Italian:
   - Paragraph 1: 
     - state the legal outcome (YES/NO) and connect it to the key conditions
       (ContrattoValido, Inadempimento, NessoCausale, DannoPatrimoniale, etc.).
   - Paragraph 2:
     - briefly explain what would be needed to change the outcome 
       (e.g. proving NessoCausale or DannoPatrimoniale, or a CausaNonImputabile).
3. Avoid generic legalese; be concrete and reference the predicates by 
   their natural-language labels (with canonical names in parentheses).

OUTPUT:
- A JSON object:
{
  "explanation_it": "<2 paragraphs in Italian>",
  "key_predicates": ["ContrattoValido", "Inadempimento", "NessoCausale", ...],
  "notes": "optional comments for debugging"
}
```

---

Se vuoi, nel prossimo passo posso:

* prendere un **caso concreto** (es. un esempio reale di domanda cliente)
* e mostrarti come passerebbe attraverso **Phase 2.1 → 2.2 → 2.3 → 2.4 → 2.5** usando questi prompt.
