# app/llm_client.py
"""
Client LLM per NSLA v1/v2.

- Espone una API semplice per:
  - ask_llm_freeform: risposta "chiacchierata"
  - ask_llm_structured / ask_llm_structured_raw: risposta strutturata (LLMOutput)
- Supporta due backend:
  - "dummy" (default, usato nei test e quando non vogliamo chiamare davvero il modello)
  - "ollama" (usa `ollama run <model>` via subprocess)

L'obiettivo principale è:
- NON far fallire i test se l'LLM non è disponibile
- Mantenere compatibilità con il vecchio codice e con main.py
"""

from __future__ import annotations

import copy
import json
import logging
import os
import random
import re
import subprocess
import time
from collections import defaultdict
from typing import Any, Dict, Optional, Tuple

from .config import Settings, get_settings
from .models import LLMOutput, LogicProgram
from .models_v2 import CanonicalizerOutput, JudgeLLMResult
from .logic_feedback import LogicFeedback
from .prompt_loader import get_prompt_loader
from .canonical_rule_utils import ensure_canonical_query_rule

logger = logging.getLogger(__name__)


class LLMCallError(RuntimeError):
    def __init__(self, operation: str, reason: str, original: Exception):
        super().__init__(f"{operation} failed due to {reason}: {original}")
        self.operation = operation
        self.reason = reason
        self.original = original


class LLMClient:
    """
    Wrapper sottile sopra l'LLM (dummy o Ollama).

    Nota importante:
    - Se il backend è "dummy", NON vengono effettuate chiamate esterne.
      Questo è il comportamento di default, pensato per i test.
    - Per usare davvero Ollama:
        esporta NSLA_LLM_BACKEND=ollama
        (e opzionalmente NSLA_OLLAMA_MODEL, NSLA_OLLAMA_BIN)
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        # Carica le impostazioni globali, se disponibili
        self.settings = settings or get_settings()

        # Backend: dummy (default) oppure ollama
        # 1. prova a leggere da settings.llm_backend se esiste
        backend = getattr(self.settings, "llm_backend", None) or "dummy"
        # Override via ENV se disponibile
        backend_env = os.getenv("NSLA_LLM_BACKEND", backend)
        backend_clean = (backend_env or "dummy").strip()
        self.backend = backend_clean or "dummy"

        # Rileva se siamo sotto pytest: in tal caso forziamo il dummy
        if os.getenv("PYTEST_CURRENT_TEST"):
            self.backend = "dummy"

        # Parametri per Ollama (usati solo se backend == "ollama")
        self.ollama_bin = (os.getenv("NSLA_OLLAMA_BIN", "ollama") or "ollama").strip()
        model_env = os.getenv("NSLA_OLLAMA_MODEL", "llama3")
        model_clean = (model_env or "llama3").strip()
        self.model_name = model_clean or "llama3"

        # Tracking
        self._last_structured_stats: Dict[str, Any] = {}
        self._llm_status: Dict[str, str] = {}

        # Prompt loader for Phase 2
        self.prompt_loader = get_prompt_loader()

        # Retry configuration
        self.max_retries = int(os.getenv("NSLA_LLM_MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("NSLA_LLM_RETRY_DELAY", "1.0"))

        logger.info(
            "LLMClient inizializzato. Backend=%s, Model=%s, MaxRetries=%d",
            self.backend,
            self.model_name,
            self.max_retries,
        )

    # ------------------------------------------------------------------
    # JSON Extraction Utilities
    # ------------------------------------------------------------------
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Robust JSON extraction from LLM response.
        
        Strategies:
        1. Try parsing the entire text as JSON
        2. Find first { ... } block and parse it
        3. Find last { ... } block and parse it
        4. Try to fix common JSON issues (trailing commas, etc.)
        
        Returns:
            Parsed JSON dict or None if extraction fails
        """
        text = text.strip()
        
        # Strategy 1: Try parsing entire text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Find first { ... } block
        first_brace = text.find("{")
        if first_brace != -1:
            # Find matching closing brace
            brace_count = 0
            for i in range(first_brace, len(text)):
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        candidate = text[first_brace:i+1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            pass
                        break
        
        # Strategy 3: Find last { ... } block (sometimes LLM adds explanation after)
        last_brace = text.rfind("}")
        if last_brace != -1:
            # Find matching opening brace
            brace_count = 0
            for i in range(last_brace, -1, -1):
                if text[i] == "}":
                    brace_count += 1
                elif text[i] == "{":
                    brace_count -= 1
                    if brace_count == 0:
                        candidate = text[i:last_brace+1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            pass
                        break
        
        # Strategy 4: Remove markdown code blocks and try again
        text_cleaned = re.sub(r'```json\s*', '', text)
        text_cleaned = re.sub(r'```\s*', '', text_cleaned)
        text_cleaned = text_cleaned.strip()
        
        # Try parsing cleaned text
        try:
            return json.loads(text_cleaned)
        except json.JSONDecodeError:
            pass
        
        # Strategy 5: Try to find JSON-like structure with regex (last resort)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None

    def _call_llm_with_retry(
        self,
        prompt: str,
        timeout: int = 300,
        operation_name: str = "LLM call"
    ) -> str:
        """
        Call LLM with retry logic.
        
        Args:
            prompt: The prompt to send
            timeout: Timeout in seconds
            operation_name: Name of operation for logging
            
        Returns:
            LLM response string
            
        Raises:
            RuntimeError: If all retries fail
        """
        last_error: Optional[Exception] = None
        reason: str = "error"

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug("%s attempt %d/%d", operation_name, attempt, self.max_retries)
                
                if self.backend == "dummy":
                    raise RuntimeError("Dummy backend: cannot make real LLM calls")
                
                response = self._call_ollama(prompt, timeout=timeout)
                logger.debug("%s succeeded on attempt %d", operation_name, attempt)
                self._record_llm_status(operation_name, "ok")
                return response
                
            except Exception as e:
                last_error = e
                reason = self._classify_llm_error(e)
                logger.warning(
                    "%s failed on attempt %d/%d: %s",
                    operation_name,
                    attempt,
                    self.max_retries,
                    str(e)
                )
                
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    jitter = random.uniform(0, self.retry_delay)
                    logger.info("Retrying in %.1f seconds...", delay)
                    time.sleep(delay + jitter)
                else:
                    logger.error(
                        "%s failed after %d attempts. Last error: %s",
                        operation_name,
                        self.max_retries,
                        str(last_error)
                    )
                    self._record_llm_status(operation_name, reason)
                    raise LLMCallError(operation_name, reason, last_error) from last_error

    # ------------------------------------------------------------------
    # Backend primitives
    # ------------------------------------------------------------------
    def _call_ollama(self, prompt: str, timeout: int = 300) -> str:
        """
        Chiama `ollama run <model_name>` con il prompt dato e restituisce stdout.
        """
        logger.debug("Calling ollama model=%s", self.model_name)
        try:
            result = subprocess.run(
                [self.ollama_bin, "run", self.model_name],
                input=prompt,
                text=True,
                capture_output=True,
                check=True,
                timeout=timeout,
                encoding="utf-8",
                errors="ignore",
            )
        except subprocess.TimeoutExpired as e:
            logger.error("Ollama timed out: %s", e)
            raise LLMCallError("Ollama", "timeout", e) from e
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            logger.error("Ollama process error: %s", stderr)
            reason = "throttled" if "429" in stderr or "didn't generate first token" in stderr.lower() else "error"
            raise LLMCallError("Ollama", reason, e) from e

        stdout = result.stdout.strip()
        if not stdout:
            raise LLMCallError("Ollama", "empty", RuntimeError("Ollama returned empty response"))
        return stdout

    # ------------------------------------------------------------------
    # Dummy helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_dummy_freeform_answer(extra: str | None = None) -> str:
        base = (
            "Sono il client LLM in modalità dummy. "
            "In un contesto reale qui ci sarebbe la risposta del modello."
        )
        if extra:
            return f"{base} {extra}"
        return base

    @staticmethod
    def _build_dummy_logic_program(question: str) -> LogicProgram:
        """
        Crea un LogicProgram minimale ma coerente con la DSL v2.1.

        L'obiettivo è garantire che anche nei percorsi di fallback/throttling
        il programma contenga:
        - dichiarazioni canoniche di sort/predicati
        - la query finale con la relativa regola legale
        in modo che i missing_links risultino informativi.
        """
        program = LogicProgram(
            dsl_version="2.1",
            sorts={
                "Soggetto": {"type": "Entity"},
                "Debitore": {"type": "Soggetto"},
                "Creditore": {"type": "Soggetto"},
                "Contratto": {"type": "Entity"},
                "Danno": {"type": "Entity"},
                "Evento": {"type": "Entity"},
            },
            constants={
                "deb_dummy": {"sort": "Debitore"},
                "cred_dummy": {"sort": "Creditore"},
                "contratto_dummy": {"sort": "Contratto"},
                "danno_dummy": {"sort": "Danno"},
                "evento_dummy": {"sort": "Evento"},
            },
            predicates={
                "HaObbligo": {"arity": 3, "sorts": ["Debitore", "Creditore", "Contratto"]},
                "Inadempimento": {"arity": 2, "sorts": ["Debitore", "Contratto"]},
                "DannoPatrimoniale": {"arity": 1, "sorts": ["Danno"]},
                "Imputabilita": {"arity": 2, "sorts": ["Debitore", "Contratto"]},
                "ResponsabilitaContrattuale": {
                    "arity": 3,
                    "sorts": ["Debitore", "Creditore", "Contratto"],
                },
                "Consenso": {"arity": 2, "sorts": ["Soggetto", "Contratto"]},
                "CapacitaContrattuale": {"arity": 1, "sorts": ["Soggetto"]},
                "CausaLegittima": {"arity": 1, "sorts": ["Contratto"]},
                "OggettoDeterminato": {"arity": 1, "sorts": ["Contratto"]},
                "FormaPrescritta": {"arity": 1, "sorts": ["Contratto"]},
                "ContrattoValido": {"arity": 2, "sorts": ["Debitore", "Contratto"]},
            },
            facts={},
            axioms=[],
            rules=[],
            query="ResponsabilitaContrattuale(deb_dummy, cred_dummy, contratto_dummy)",
        )
        ensure_canonical_query_rule(program)
        return program

    @staticmethod
    def _build_dummy_llm_output(question: str) -> Dict[str, Any]:
        """
        Crea un JSON compatibile con LLMOutput per i test.
        """
        lp = LLMClient._build_dummy_logic_program(question)
        return {
            "final_answer": (
                "Risposta generica (modalità dummy) alla domanda: "
                f"'{question}'."
            ),
            "premises": [
                "Esiste almeno un contratto valido.",
                "Le parti sono identificate in modo astratto.",
            ],
            "conclusion": "Contratto valido a fini dimostrativi.",
            "logic_program": lp.model_dump(),
        }

    @staticmethod
    def _build_dummy_canonicalizer_output(question: str) -> CanonicalizerOutput:
        """
        Crea un CanonicalizerOutput minimale per i test.
        """
        return CanonicalizerOutput(
            question=question,
            language="it",
            domain="civil_law_contractual_liability",
            concepts=[],
            unmapped_terms=[],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def ask_llm_freeform(self, question: str) -> str:
        """
        Risposta non strutturata (usata da /llm_only).
        """
        logger.debug("ask_llm_freeform called (backend=%s)", self.backend)

        if self.backend == "dummy":
            return self._build_dummy_freeform_answer()

        # Backend ollama: prompt molto semplice
        prompt = (
            "You are a helpful Italian legal assistant. "
            "Answer the following question in clear Italian.\n\n"
            f"Domanda: {question}\n\n"
            "Risposta:"
        )
        try:
            raw = self._call_ollama(prompt)
            return raw.strip()
        except LLMCallError as exc:
            logger.error("Freeform LLM call failed: %s", exc)
            self._record_llm_status("Freeform", exc.reason)
            return self._build_dummy_freeform_answer(
                "(risposta di fallback per indisponibilità del modello)"
            )

    def call_judge_metric(
        self,
        question: str,
        reference_answer: Optional[str],
        answer_a: str,
        answer_b: str,
        label_a: str = "baseline_v1",
        label_b: str = "nsla_v2",
    ) -> JudgeLLMResult:
        """
        Invoke the Judge-LLM metric (Phase 4).

        Returns:
            JudgeLLMResult with vote/confidence/rationale.
        """
        runtime_data = {
            "question": question,
            "reference_answer": reference_answer or "",
            "answer_a": answer_a,
            "answer_b": answer_b,
            "label_a": label_a,
            "label_b": label_b,
        }

        if self.backend == "dummy":
            return JudgeLLMResult(
                question=question,
                reference_answer=reference_answer,
                answer_a=answer_a,
                answer_b=answer_b,
                label_a=label_a,
                label_b=label_b,
                vote="tie",
                confidence=0.0,
                rationale="Dummy backend: judge metric inactive.",
            )

        prompt = self.prompt_loader.load_prompt_with_context(
            "judge/prompt_phase_4_judge_metric.txt",
            include_ontology=False,
            inject_runtime=runtime_data,
        )

        raw = self._call_llm_with_retry(
            prompt,
            timeout=120,
            operation_name="Judge LLM",
        )
        data = self._extract_json_from_text(raw)
        if not data:
            raise RuntimeError("Judge LLM returned an unparsable response")

        vote = str(data.get("vote", "tie")).strip() or "tie"
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        rationale = data.get("rationale")

        return JudgeLLMResult(
            question=question,
            reference_answer=reference_answer,
            answer_a=answer_a,
            answer_b=answer_b,
            label_a=label_a,
            label_b=label_b,
            vote=vote,
            confidence=max(0.0, min(confidence, 1.0)),
            rationale=rationale,
        )

    def ask_llm_plain(self, question: str) -> str:
        """
        Helper di compatibilità usato dall'endpoint /llm_only e dai test.

        Per non duplicare la logica, delega semplicemente a ask_llm_freeform,
        così:
        - in backend 'dummy' restituisce la risposta dummy;
        - in backend 'ollama' usa lo stesso prompt freeform.
        """
        return self.ask_llm_freeform(question)

    def ask_llm_structured_raw(self, question: str) -> str:
        """
        Versione 'raw' che restituisce la stringa JSON così come prodotta
        (o costruita dal dummy) per la struttura LLMOutput.
        """
        logger.debug("ask_llm_structured_raw called (backend=%s)", self.backend)

        if self.backend == "dummy":
            dummy = self._build_dummy_llm_output(question)
            return json.dumps(dummy, ensure_ascii=False)

        # Backend ollama: costruiamo un prompt che richiede esplicitamente il JSON
        schema = """
Devi rispondere SOLO con un singolo oggetto JSON, senza testo extra.
Lo schema è il seguente:

{
  "final_answer": "string, spiegazione in italiano",
  "premises": ["string", "..."],
  "conclusion": "string, riassunto sintetico",
  "logic_program": {
    "sorts": { "NomeSort": { } },
    "constants": { "nome": { "sort": "NomeSort" } },
    "axioms": [
      { "condition": "true", "conclusion": "Predicato(...)" }
    ],
    "query": "Predicato(...)"
  }
}
"""
        prompt = (
            "You are NSLA v1 legal reasoning assistant.\n\n"
            f"{schema}\n\n"
            "Domanda utente (in italiano):\n"
            f"{question}\n\n"
            "Trasforma la domanda nella struttura JSON richiesta.\n"
            "Rispondi SOLO con il JSON."
        )

        raw = self._call_ollama(prompt)

        # Alcuni modelli aggiungono testo prima/dopo: proviamo a estrarre l'oggetto JSON principale
        raw_stripped = raw.strip()
        first_brace = raw_stripped.find("{")
        last_brace = raw_stripped.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = raw_stripped[first_brace : last_brace + 1]
        else:
            # Se non troviamo nulla, fallback su dummy
            logger.warning("Impossibile estrarre JSON valido da risposta LLM, uso dummy.")
            return json.dumps(self._build_dummy_llm_output(question), ensure_ascii=False)

        # Verifica che sia JSON valido; se fallisce, fallback su dummy
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            logger.warning("JSON LLM non valido, uso dummy.")
            return json.dumps(self._build_dummy_llm_output(question), ensure_ascii=False)

    def ask_llm_structured(self, question: str) -> LLMOutput:
        """
        Come ask_llm_structured_raw ma ritorna un oggetto LLMOutput pydantic.
        """
        try:
            raw = self.ask_llm_structured_raw(question)
            data = json.loads(raw)
        except (LLMCallError, json.JSONDecodeError) as e:
            logger.error("Failed to obtain structured output: %s", e)
            data = self._build_dummy_llm_output(question)
            if isinstance(e, LLMCallError):
                self._record_llm_status("Structured Extractor", e.reason)

        logic_program_dict = data.get("logic_program")
        if not isinstance(logic_program_dict, dict):
            if isinstance(logic_program_dict, str):
                logic_program_dict = {"dsl_version": "2.1"}
                self._last_structured_stats = {"logic_program_coerced": 1}
            else:
                logic_program_dict = {}
        normalized_lp, stats = self._normalize_logic_program_dict(logic_program_dict)
        data["logic_program"] = normalized_lp
        self._last_structured_stats = stats

        # Ora validiamo con il modello pydantic
        return LLMOutput.model_validate(data)

    # ------------------------------------------------------------------
    # Public API - Phase 2 methods
    # ------------------------------------------------------------------
    def call_canonicalizer(self, question: str) -> CanonicalizerOutput:
        """
        Phase 2.1: Canonicalize legal question using ontology.
        
        Args:
            question: Italian legal question about contractual liability
            
        Returns:
            CanonicalizerOutput with mapped concepts and unmapped terms
            
        Raises:
            RuntimeError: If LLM call fails after retries
            ValueError: If JSON parsing/validation fails
        """
        logger.info("Phase 2.1: Canonicalizing question (length=%d)", len(question))
        
        if self.backend == "dummy":
            logger.debug("Dummy backend: returning dummy canonicalizer output")
            return self._build_dummy_canonicalizer_output(question)
        
        try:
            # Load prompt template with context
            prompt = self.prompt_loader.load_prompt_with_context(
                "prompt_phase_2_1_canonicalizer.txt",
                variables=None,
                include_ontology=True,
                include_specs=["canonicalizer_agent_vFinal.json"],
                inject_runtime={"question": question}
            )
            
            # Call LLM with retry
            response = self._call_llm_with_retry(
                prompt,
                timeout=300,
                operation_name="Canonicalizer"
            )
            
            # Extract JSON
            json_data = self._extract_json_from_text(response)
            if json_data is None:
                raise ValueError(
                    f"Failed to extract JSON from canonicalizer response. "
                    f"Response preview: {response[:500]}"
                )
            
            # Validate with Pydantic
            canonicalization = CanonicalizerOutput.model_validate(json_data)
            logger.info(
                "Canonicalization successful: %d concepts, %d unmapped terms",
                len(canonicalization.concepts),
                len(canonicalization.unmapped_terms)
            )
            return canonicalization
            
        except Exception as e:
            logger.error("Canonicalizer failed: %s", str(e), exc_info=True)
            raise

    def call_structured_extractor(
        self,
        question: str,
        canonicalization: CanonicalizerOutput
    ) -> LogicProgram:
        """
        Phase 2.2: Extract structured logic program from question and canonicalization.
        
        Args:
            question: Original Italian legal question
            canonicalization: CanonicalizerOutput from Phase 2.1
            
        Returns:
            LogicProgram (DSL v2.1) ready for Z3
            
        Raises:
            RuntimeError: If LLM call fails after retries
            ValueError: If JSON parsing/validation fails
        """
        logger.info("Phase 2.2: Extracting structured logic program")
        
        if self.backend == "dummy":
            logger.debug("Dummy backend: returning dummy logic program")
            return self._build_dummy_logic_program(question)
        
        try:
            # Prepare input data for prompt
            canonicalization_dict = canonicalization.model_dump()
            
            # Load prompt template
            template = self.prompt_loader.load_text_file("prompt_phase_2_2_structured_extractor.txt")
            
            # Build input JSON for injection
            input_data = {
                "question": question,
                "canonicalization": canonicalization_dict,
                "target_task": "determine if ResponsabilitaContrattuale(Debitore, Creditore, Contratto) is entailed or not"
            }
            
            # Inject runtime variables
            prompt = self.prompt_loader.inject_runtime_variables(template, input_data)
            
            # Add context files
            prompt = self.prompt_loader.format_prompt(
                prompt,
                variables=None,
                context_files=[
                    "resources/nsla_v2/dsl_nsla_v_2_1.md",
                    "resources/nsla_v2/nsla_v_2_dsl_logica_guida_tecnica.md",
                    "resources/ontology/legal_it_v1.yaml"
                ],
                use_double_braces=False
            )
            
            # Call LLM with retry
            response = self._call_llm_with_retry(
                prompt,
                timeout=300,
                operation_name="Structured Extractor"
            )
            
            # Extract JSON
            json_data = self._extract_json_from_text(response)
            if json_data is None:
                raise ValueError(
                    f"Failed to extract JSON from structured extractor response. "
                    f"Response preview: {response[:500]}"
                )
            
            # The response should have "logic_program_v1" key or be the logic_program directly
            if "logic_program_v1" in json_data:
                logic_program_dict = json_data["logic_program_v1"]
            elif "logic_program" in json_data:
                logic_program_dict = json_data["logic_program"]
            else:
                # Assume the entire response is the logic program
                logic_program_dict = json_data
            
            logic_program_dict, norm_stats = self._normalize_logic_program_dict(logic_program_dict)

            # Validate with Pydantic
            logic_program = LogicProgram.model_validate(logic_program_dict)
            self._last_structured_stats = norm_stats
            logger.info(
                "Structured extraction successful: DSL v%s, %d predicates, %d rules",
                logic_program.dsl_version,
                len(logic_program.predicates),
                len(logic_program.rules)
            )
            return logic_program
            
        except Exception as e:
            logger.error("Structured extractor failed: %s", str(e), exc_info=True)
            raise

    def pop_structured_stats(self) -> Dict[str, Any]:
        stats = getattr(self, "_last_structured_stats", {}) or {}
        self._last_structured_stats = {}
        return stats

    def call_refinement_llm(
        self,
        question: str,
        logic_program_v1: LogicProgram,
        feedback_v1: LogicFeedback,
        answer_v1: Optional[str] = None,
        history_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Phase 2.3: Refine logic program based on Z3 feedback.
        
        Args:
            question: Original Italian legal question
            logic_program_v1: Initial logic program from Phase 2.2
            feedback_v1: LogicFeedback from Z3 evaluation of v1
            
        Args:
            question: Original Italian legal question.
            logic_program_v1: Program to refine (typically structured extractor output).
            feedback_v1: Logic feedback from solver on ``logic_program_v1``.
            answer_v1: Optional textual answer to expose as "previous answer".
            history_summary: Optional textual summary of previous iterations.

        Returns:
            Dict compatible with LLMOutputV2 (final_answer, logic_program, notes)
            
        Raises:
            RuntimeError: If LLM call fails after retries
            ValueError: If JSON parsing/validation fails
        """
        logger.info(
            "Phase 2.3: Refining logic program (status=%s)",
            feedback_v1.status
        )
        
        if self.backend == "dummy":
            logger.debug("Dummy backend: returning dummy LLMOutputV2")
            lp = self._build_dummy_logic_program(question)
            return {
                "final_answer": answer_v1 or f"Risposta dummy per: {question}",
                "logic_program": lp.model_dump(),
                "notes": "Dummy response",
            }
        
        try:
            # Prepare input data for prompt
            logic_program_dict = logic_program_v1.model_dump()
            
            # Load prompt template
            template = self.prompt_loader.load_text_file("prompt_phase_2_3_refinement_llmoutput_v2.txt")
            
            # Build input data for injection
            input_data = {
                "question_json": json.dumps(question, ensure_ascii=False),
                "question": question,
                "previous_answer": (answer_v1 or "").replace("{", "\\{").replace("}", "\\}"),
                "logic_program_v1_json": json.dumps(
                    logic_program_dict, ensure_ascii=False, indent=2
                ),
                "logic_program_v1": logic_program_dict,
                "status_v1": feedback_v1.status,
                "missing_links_v1": json.dumps(
                    feedback_v1.missing_links, ensure_ascii=False
                ),
                "conflicting_axioms_v1": json.dumps(
                    feedback_v1.conflicting_axioms, ensure_ascii=False
                ),
                "summary_v1": feedback_v1.human_summary,
                "history_summary": history_summary
                or "Nessuna iterazione precedente: primo refinement.",
            }
            
            # Inject runtime variables
            prompt = self.prompt_loader.inject_runtime_variables(template, input_data)
            
            # Add context files
            prompt = self.prompt_loader.format_prompt(
                prompt,
                variables=None,
                context_files=[
                    "resources/nsla_v2/dsl_nsla_v_2_1.md",
                    "resources/nsla_v2/nsla_v_2_dsl_logica_guida_tecnica.md",
                    "resources/nsla_v2/nsla_v_2_iterative_loop_design.md",
                    "resources/ontology/legal_it_v1.yaml"
                ],
                use_double_braces=False
            )
            
            # Call LLM with retry
            response = self._call_llm_with_retry(
                prompt,
                timeout=300,
                operation_name="Refinement LLM"
            )
            
            # Extract JSON
            json_data = self._extract_json_from_text(response)
            if json_data is None:
                raise ValueError(
                    f"Failed to extract JSON from refinement LLM response. "
                    f"Response preview: {response[:500]}"
                )
            
            # Validate structure (should have final_answer and logic_program)
            if "final_answer" not in json_data:
                raise ValueError("Refinement response missing 'final_answer' field")
            if "logic_program" not in json_data:
                raise ValueError("Refinement response missing 'logic_program' field")
            
            logger.info("Refinement successful: logic_program updated")
            return json_data
            
        except Exception as e:
            logger.error("Refinement LLM failed: %s", str(e), exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------

    def _normalize_logic_program_dict(
        self, data: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Normalize LLM output before validating with LogicProgram.
        """
        stats = defaultdict(int)

        if isinstance(data, dict):
            normalized = copy.deepcopy(data)
        else:
            normalized = {}
            stats["logic_program_root_reset"] += 1

        normalized.setdefault("dsl_version", "2.1")
        normalized.setdefault("sorts", {})
        normalized.setdefault("constants", {})
        normalized.setdefault("predicates", {})
        normalized.setdefault("axioms", [])
        normalized.setdefault("rules", [])
        normalized.setdefault("facts", {})

        # Ensure container types (treat scalars/nulls as empty)
        if not isinstance(normalized.get("sorts"), dict):
            normalized["sorts"] = {}
            stats["sorts_reset"] += 1

        constants = normalized.get("constants")
        if isinstance(constants, list):
            const_map: Dict[str, Any] = {}
            for idx, const in enumerate(constants):
                if isinstance(const, dict):
                    name = const.get("name") or f"c{idx}"
                    const_map[name] = {k: v for k, v in const.items() if k != "name"}
                elif isinstance(const, str):
                    const_map[f"c{idx}"] = {"sort": const}
                    stats["constant_strings_normalized"] += 1
            normalized["constants"] = const_map
            stats["constant_list_coerced"] += len(constants)
        elif not isinstance(constants, dict):
            if constants not in (None, {}):
                stats["constant_scalar_reset"] += 1
            normalized["constants"] = {}

        predicates = normalized.get("predicates")
        if isinstance(predicates, list):
            pred_map: Dict[str, Any] = {}
            for pred in predicates:
                if isinstance(pred, dict):
                    name = pred.get("name")
                    if name:
                        pred_map[name] = {k: v for k, v in pred.items() if k != "name"}
            normalized["predicates"] = pred_map
            stats["predicate_list_coerced"] += 1
        elif not isinstance(predicates, dict):
            if predicates not in (None, {}):
                stats["predicate_scalar_reset"] += 1
            normalized["predicates"] = {}

        axioms = normalized.get("axioms")
        if axioms is None:
            normalized["axioms"] = []
        elif isinstance(axioms, (str, dict)):
            normalized["axioms"] = [axioms]
        elif not isinstance(axioms, list):
            normalized["axioms"] = []
            stats["axiom_entries_dropped"] += 1

        if isinstance(normalized["axioms"], list):
            new_axioms = []
            for entry in normalized["axioms"]:
                if isinstance(entry, str):
                    formula = self._sanitize_expression(entry)
                    if formula:
                        new_axioms.append({"formula": formula})
                        stats["axiom_strings_wrapped"] += 1
                    continue
                if not isinstance(entry, dict):
                    stats["axiom_entries_dropped"] += 1
                    continue
                formula = self._sanitize_expression(entry.get("formula"))
                if not formula:
                    condition = self._sanitize_expression(entry.get("condition"))
                    conclusion = self._sanitize_expression(entry.get("conclusion"))
                    if conclusion:
                        formula = (
                            conclusion
                            if not condition or condition.lower() in {"true", "vero", "1"}
                            else f"{condition} -> {conclusion}"
                        )
                if not formula and entry.get("pred"):
                    formula = self._format_atom(entry.get("pred"), entry.get("args"))
                if formula:
                    new_axioms.append({"formula": formula})
                else:
                    stats["axiom_entries_dropped"] += 1
            normalized["axioms"] = new_axioms

        rules = normalized.get("rules")
        if rules is None:
            normalized["rules"] = []
        elif isinstance(rules, (str, dict)):
            normalized["rules"] = [rules]
        elif not isinstance(rules, list):
            normalized["rules"] = []
            stats["rule_entries_dropped"] += 1

        if isinstance(normalized["rules"], list):
            new_rules = []
            for entry in normalized["rules"]:
                if isinstance(entry, str):
                    condition, conclusion = self._rule_parts_from_string(entry)
                    new_rules.append(
                        {
                            "condition": self._sanitize_expression(condition) or "true",
                            "conclusion": self._sanitize_expression(conclusion),
                        }
                    )
                    stats["rule_strings_wrapped"] += 1
                    continue
                if not isinstance(entry, dict):
                    stats["rule_entries_dropped"] += 1
                    continue
                condition = self._sanitize_expression(entry.get("condition")) or "true"
                conclusion = self._sanitize_expression(entry.get("conclusion"))
                if not conclusion and entry.get("pred"):
                    conclusion = self._format_atom(entry.get("pred"), entry.get("args"))
                if conclusion:
                    new_rules.append(
                        {
                            "condition": condition,
                            "conclusion": conclusion,
                            "id": entry.get("id"),
                        }
                    )
                else:
                    stats["rule_entries_dropped"] += 1
            normalized["rules"] = new_rules

        facts = normalized.get("facts")
        if isinstance(facts, list):
            normalized["facts"] = {fact: True for fact in facts if isinstance(fact, str)}
            stats["fact_list_coerced"] += len(facts)
        elif not isinstance(facts, dict):
            if facts not in (None, {}):
                stats["fact_scalar_reset"] += 1
            normalized["facts"] = {}

        query = normalized.get("query")
        if isinstance(query, dict):
            name = str(query.get("pred") or "").strip()
            args = query.get("args") or []
            clean_args = [str(arg).strip() for arg in args if str(arg).strip()]
            if name:
                joined = ",".join(clean_args)
                normalized["query"] = f"{name}({joined})" if joined else name
            else:
                normalized["query"] = None

        return normalized, dict(stats)

    @staticmethod
    def _sanitize_expression(expr: Optional[str]) -> str:
        if expr is None:
            return ""
        text = str(expr).strip()
        if not text:
            return ""
        replacements = {
            "∨": " or ",
            "∧": " and ",
            "¬": " not ",
            "→": " -> ",
            "⇒": " -> ",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        return " ".join(text.split())

    @staticmethod
    def _format_atom(predicate: Any, args: Any) -> str:
        name = str(predicate).strip()
        if not name:
            return ""
        arg_list = []
        if isinstance(args, list):
            arg_list = [str(arg).strip() for arg in args if str(arg).strip()]
        params = ", ".join(arg_list)
        return f"{name}({params})" if params else f"{name}()"

    def _rule_parts_from_string(self, text: str) -> Tuple[str, str]:
        """
        Split a textual rule into condition and conclusion parts.
        """
        seps = ["->", "→", "=>"]
        for sep in seps:
            if sep in text:
                left, right = text.split(sep, 1)
                return left.strip(), right.strip()
        if ":-" in text:
            left, right = text.split(":-", 1)
            return right.strip(), left.strip()
        return "true", text.strip()

    def _record_llm_status(self, operation: str, status: str) -> None:
        self._llm_status[operation] = status

    def pop_llm_statuses(self) -> Dict[str, str]:
        statuses = dict(self._llm_status)
        self._llm_status.clear()
        return statuses

    def _classify_llm_error(self, error: Exception) -> str:
        if isinstance(error, LLMCallError) and getattr(error, "reason", None):
            return error.reason
        text = str(error).lower()
        if isinstance(error, subprocess.TimeoutExpired) or "timeout" in text:
            return "timeout"
        if "429" in text or "rate limit" in text or "didn't generate first token" in text:
            return "throttled"
        if "connection" in text:
            return "connection"
        return "error"
