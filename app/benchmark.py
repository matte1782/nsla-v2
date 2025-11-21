# app/benchmark.py
import json
import csv
import time
import logging
import statistics
import math
from typing import List, Dict, Any, Tuple, Optional
import os
import requests
from datetime import datetime
from requests.exceptions import RequestException, ConnectionError

logger = logging.getLogger(__name__)


def _prepare_timeout(value: Optional[float]) -> Optional[float]:
    """
    Normalize timeout values for requests.

    Args:
        value: Timeout in seconds. Values <= 0 disable the timeout.

    Returns:
        float | None suitable for `requests.post(timeout=...)`.
    """
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def load_cases(path: str) -> List[Dict[str, Any]]:
    """Carica i casi di test dal file JSON specificato."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def call_llm_only(
    base_url: str,
    question: str,
    timeout: Optional[float] = 30.0,
) -> Tuple[str, float]:
    """Chiama l'endpoint /llm_only e misura il tempo di risposta."""
    url = f"{base_url}/llm_only"
    start_time = time.perf_counter()
    
    request_timeout = _prepare_timeout(timeout)
    
    try:
        response = requests.post(url, json={"question": question}, timeout=request_timeout)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code} from /llm_only")
        elapsed = time.perf_counter() - start_time
        data = response.json()
        return data.get("answer", ""), elapsed
    except RequestException as e:
        # Lascia che ConnectionError e altre RequestException siano propagate
        elapsed = time.perf_counter() - start_time
        raise


def call_legal_query(
    base_url: str,
    question: str,
    timeout: Optional[float] = 60.0,
) -> Tuple[Dict[str, Any], float]:
    """Chiama l'endpoint /legal_query e misura il tempo di risposta."""
    url = f"{base_url}/legal_query"
    start_time = time.perf_counter()
    
    request_timeout = _prepare_timeout(timeout)
    
    try:
        response = requests.post(url, json={"question": question}, timeout=request_timeout)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code} from /legal_query")
        elapsed = time.perf_counter() - start_time
        return response.json(), elapsed
    except RequestException as e:
        elapsed = time.perf_counter() - start_time
        raise


def call_legal_query_v2(
    base_url: str,
    question: str,
    reference_answer: Optional[str] = None,
    timeout: Optional[float] = 240.0,
) -> Tuple[Dict[str, Any], float]:
    """Chiama l'endpoint /legal_query_v2 e misura il tempo di risposta."""
    url = f"{base_url}/legal_query_v2"
    start_time = time.perf_counter()

    payload = {"question": question}
    if reference_answer is not None:
        payload["reference_answer"] = reference_answer
    request_timeout = _prepare_timeout(timeout)

    response = requests.post(url, json=payload, timeout=request_timeout)
    if response.status_code != 200:
        elapsed = time.perf_counter() - start_time
        raise RuntimeError(f"HTTP {response.status_code} from /legal_query_v2")
    elapsed = time.perf_counter() - start_time
    return response.json(), elapsed


def call_legal_query_v2_iterative(
    base_url: str,
    question: str,
    max_iters: int = 3,
    timeout: Optional[float] = 300.0,
) -> Tuple[Dict[str, Any], float]:
    """Chiama l'endpoint /legal_query_v2_iterative e misura il tempo di risposta."""
    max_iters = max(1, max_iters)
    url = f"{base_url}/legal_query_v2_iterative?max_iters={max_iters}"
    start_time = time.perf_counter()

    request_timeout = _prepare_timeout(timeout)

    response = requests.post(url, json={"question": question}, timeout=request_timeout)
    if response.status_code != 200:
        elapsed = time.perf_counter() - start_time
        raise RuntimeError(f"HTTP {response.status_code} from /legal_query_v2_iterative")
    elapsed = time.perf_counter() - start_time
    return response.json(), elapsed


def is_correct(predicted: str, gold: str) -> bool:
    """Controlla se la gold_answer è contenuta nella risposta predetta (case-insensitive)."""
    return gold.lower() in predicted.lower()


def _tokenize(text: str) -> set:
    """Tokenizza un testo in modo semplice: split su spazi e lowercasing."""
    return set(word.lower() for word in text.split() if word.strip())


def _f1_score(predicted: str, gold: str) -> float:
    """Calcola l'F1 basato su sovrapposizione token-level."""
    if not predicted.strip() or not gold.strip():
        return 0.0
    pred_tokens = _tokenize(predicted)
    gold_tokens = _tokenize(gold)
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0
    intersection = pred_tokens & gold_tokens
    if not intersection:
        return 0.0
    precision = len(intersection) / len(pred_tokens)
    recall = len(intersection) / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def _bleu_score_simple(predicted: str, gold: str) -> float:
    """Calcola un BLEU semplificato basato su n-gram overlap."""
    if not predicted.strip() or not gold.strip():
        return 0.0
    
    pred_words = predicted.lower().split()
    gold_words = gold.lower().split()
    
    if len(gold_words) == 0:
        return 0.0
    
    # Calcola ungegram precision per n=1,2,3,4
    precisions = []
    for n in range(1, min(5, len(gold_words) + 1)):
        if n > len(pred_words):
            precisions.append(0.0)
            continue
            
        pred_ngrams = [tuple(pred_words[i:i+n]) for i in range(len(pred_words)-n+1)]
        gold_ngrams = [tuple(gold_words[i:i+n]) for i in range(len(gold_words)-n+1)]
        
        if not pred_ngrams:
            precisions.append(0.0)
            continue
            
        common = sum(1 for ngram in pred_ngrams if ngram in gold_ngrams)
        precision = common / len(pred_ngrams)
        precisions.append(precision)
    
    # Calcola BLEU con brevità penalizzata
    if not precisions or all(p == 0 for p in precisions):
        return 0.0
    
    geometric_mean = math.exp(
        sum(math.log(max(p, 1e-10)) for p in precisions) / len(precisions)
    )
    bp = min(1.0, math.exp(1 - len(gold_words) / max(len(pred_words), 1)))
    
    return bp * geometric_mean


def call_judge_llm(
    question: str,
    answer_llm: str,
    answer_nsla: str,
    gold: str,
    base_url: str = "http://127.0.0.1:8000",
    timeout: Optional[float] = 90.0,
) -> Dict[str, Any]:
    """
    Call the dedicated judge endpoint to compare LLM-only vs NSLA answers.
    Returns a dict with vote/confidence/rationale.
    """
    payload = {
        "question": question,
        "answer_a": answer_llm,
        "answer_b": answer_nsla,
        "reference_answer": gold,
        "label_a": "LLM",
        "label_b": "NSLA",
    }

    request_timeout = _prepare_timeout(timeout)

    try:
        response = requests.post(
            f"{base_url}/judge_compare",
            json=payload,
            timeout=request_timeout,
        )
        if response.status_code == 200:
            data = response.json()
            return {
                "vote": data.get("vote", "tie"),
                "confidence": data.get("confidence", 0.0),
                "rationale": data.get("rationale", ""),
            }
    except RequestException:
        pass

    return {"vote": "tie", "confidence": 0.0, "rationale": ""}


def _log_request(case_id: str, question: str, result: Dict[str, Any], duration: float):
    """Logga la richiesta in formato JSON per analisi."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "case_id": case_id,
        "question": question,
        "duration": duration,
        "result_summary": {
            "n_cases": result.get("n_cases", 0),
            "n_success": result.get("n_success", 0),
            "n_fail": result.get("n_fail", 0),
            "llm_only_accuracy": result.get("llm_only_accuracy", 0),
            "nsla_accuracy": result.get("nsla_accuracy", 0),
            "nsla_v2_accuracy": result.get("nsla_v2_accuracy", 0),
            "nsla_iter_accuracy": result.get("nsla_iter_accuracy", 0),
            "v2_guardrail_pass_rate": result.get("v2_guardrail_pass_rate", 0),
            "iter_guardrail_pass_rate": result.get("iter_guardrail_pass_rate", 0),
        },
        "error": result.get("error")
    }
    
    log_file = os.path.join(log_dir, f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def run_benchmark(
    base_url: str = "http://127.0.0.1:8000",
    cases_path: str = "data/cases_dev.json",
    csv_path: str = "data/results.csv",
    use_bleu: bool = True,
    use_judge: bool = False,
    timeout_llm: float = 300.0,
    timeout_nsla: float = 300.0,
    timeout_v2: float = 600.0,
    timeout_iter: float = 900.0,
    timeout_judge: float = 300.0,
    case_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Esegue il benchmark completo con metriche avanzate.

    Args:
        base_url: Endpoint del backend FastAPI.
        cases_path: Percorso al file JSON con i casi di test.
        csv_path: Percorso del file CSV di output.
        use_bleu: Se True calcola anche il BLEU semplificato.
        use_judge: Se True invoca il judge LLM esterno.
        timeout_*: Timeout (in secondi) per le varie chiamate HTTP. Valori <= 0 disabilitano il timeout.
        case_ids: Lista opzionale di ID da eseguire (subset del file casi).
    """
    start_time = time.perf_counter()
    
    try:
        cases = load_cases(cases_path)
    except Exception as exc:
        logger.error("Impossibile caricare i casi: %s", exc)
        return {
            "n_cases": 0,
            "n_success": 0,
            "n_fail": 0,
            "llm_only_accuracy": 0.0,
            "nsla_accuracy": 0.0,
            "avg_llm_only_time": 0.0,
            "avg_nsla_time": 0.0,
            "llm_only_EM": 0.0,
            "nsla_EM": 0.0,
            "llm_only_F1": 0.0,
            "nsla_F1": 0.0,
            "bert_score_llm": 0.0,
            "bert_score_nsla": 0.0,
            "bleu_score_llm": 0.0,
            "bleu_score_nsla": 0.0,
            "nsla_win_rate": 0.0,
            "details": [],
            "error": f"Impossibile caricare i casi: {str(exc)}"
        }

    if case_ids:
        requested_ids = {cid.strip() for cid in case_ids if cid and cid.strip()}
        filtered_cases = [case for case in cases if case.get("id") in requested_ids]
        missing_ids = sorted(requested_ids - {case.get("id") for case in filtered_cases})
        if missing_ids:
            logger.warning(
                "I seguenti case_id non sono presenti in %s: %s",
                cases_path,
                ", ".join(missing_ids),
            )
        if not filtered_cases:
            msg = (
                "Nessun caso corrisponde agli ID richiesti."
                if requested_ids
                else "Nessun case_id valido fornito."
            )
            logger.error(msg)
            return {
                "n_cases": 0,
                "n_success": 0,
                "n_fail": 0,
                "llm_only_accuracy": 0.0,
                "nsla_accuracy": 0.0,
                "avg_llm_only_time": 0.0,
                "avg_nsla_time": 0.0,
                "llm_only_EM": 0.0,
                "nsla_EM": 0.0,
                "llm_only_F1": 0.0,
                "nsla_F1": 0.0,
                "bert_score_llm": 0.0,
                "bert_score_nsla": 0.0,
                "bleu_score_llm": 0.0,
                "bleu_score_nsla": 0.0,
                "nsla_win_rate": 0.0,
                "details": [],
                "error": msg,
            }
        cases = filtered_cases

    if not cases:
        return {
            "n_cases": 0,
            "n_success": 0,
            "n_fail": 0,
            "llm_only_accuracy": 0.0,
            "nsla_accuracy": 0.0,
            "avg_llm_only_time": 0.0,
            "avg_nsla_time": 0.0,
            "llm_only_EM": 0.0,
            "nsla_EM": 0.0,
            "llm_only_F1": 0.0,
            "nsla_F1": 0.0,
            "bert_score_llm": 0.0,
            "bert_score_nsla": 0.0,
            "bleu_score_llm": 0.0,
            "bleu_score_nsla": 0.0,
            "nsla_win_rate": 0.0,
            "details": [],
            "error": "Nessun caso di test trovato"
        }

    n_cases = len(cases)
    rows = []
    n_success = 0
    n_fail = 0
    error_messages = []
    
    total_time_llm = []
    total_time_nsla = []
    total_time_nsla_v2 = []
    total_time_nsla_iter = []
    total_llm_correct = 0
    total_nsla_correct = 0
    total_nsla_v2_correct = 0
    total_nsla_iter_correct = 0
    total_llm_em = 0
    total_nsla_em = 0
    total_nsla_v2_em = 0
    total_nsla_iter_em = 0
    total_llm_f1 = 0.0
    total_nsla_f1 = 0.0
    total_nsla_v2_f1 = 0.0
    total_nsla_iter_f1 = 0.0
    total_bleu_llm = 0.0
    total_bleu_nsla = 0.0
    total_bleu_nsla_v2 = 0.0
    total_bleu_nsla_iter = 0.0
    v2_guardrail_pass = 0
    v2_guardrail_total = 0
    iter_guardrail_pass = 0
    iter_guardrail_total = 0
    tag_metrics: Dict[str, Dict[str, float]] = {}
    nsla_wins = 0
    
    print("Inizio benchmark avanzato...")
    print("=" * 60)
    
    for case in cases:
        case_id = case["id"]
        question = case["question"]
        gold_answer = case["gold_answer"]
        tags = case.get("tags", [])
        iter_cfg = case.get("iter", {})
        iter_max = int(iter_cfg.get("max_iters", 3))
        
        # Valori di default per la riga
        llm_only_answer = ""
        nsla_answer = ""
        nsla_v2_answer = ""
        nsla_iter_answer = ""
        verified = False
        llm_only_correct = False
        nsla_correct = False
        nsla_v2_correct = False
        nsla_iter_correct = False
        t_llm = 0.0
        t_nsla = 0.0
        t_nsla_v2 = 0.0
        t_nsla_iter = 0.0
        case_error = None
        em_llm = 0
        em_nsla = 0
        em_nsla_v2 = 0
        em_nsla_iter = 0
        f1_llm = 0.0
        f1_nsla = 0.0
        f1_nsla_v2 = 0.0
        f1_nsla_iter = 0.0
        bleu_llm = 0.0
        bleu_nsla = 0.0
        bleu_nsla_v2 = 0.0
        bleu_nsla_iter = 0.0
        judge_vote = "tie"
        judge_confidence = 0.0
        judge_rationale = ""
        v2_judge_vote = ""
        v2_judge_confidence = 0.0
        v2_judge_rationale = ""
        v2_feedback_status = ""
        v2_missing_links = []
        v2_guardrail_ok = None
        v2_guardrail_issues = 0
        v2_fallback_used = False
        v2_explanation = ""
        v2_feedback_v1_status = ""
        v2_llm_status = {}
        iter_status = ""
        iter_missing = []
        iter_conflicts = []
        iter_guardrail_ok = None
        iter_guardrail_issues = 0
        iter_iterations = 0
        iter_llm_status = {}
        
        try:
            # Chiama gli endpoint principali
            llm_answer, t_llm = call_llm_only(base_url, question, timeout=timeout_llm)
            nsla_json, t_nsla = call_legal_query(base_url, question, timeout=timeout_nsla)
            v2_json, t_nsla_v2 = call_legal_query_v2(
                base_url,
                question,
                reference_answer=gold_answer,
                timeout=timeout_v2,
            )
            iter_json, t_nsla_iter = call_legal_query_v2_iterative(
                base_url,
                question,
                iter_max,
                timeout=timeout_iter,
            )
            
            # Estrazione informazioni da /legal_query
            llm_only_answer = llm_answer
            nsla_answer = nsla_json.get("final_answer") or nsla_json.get("answer", "")
            verified = bool(nsla_json.get("verified", False))
            
            # Phase 2 artifacts
            nsla_v2_answer = v2_json.get("final_answer", "")
            v2_feedback = v2_json.get("feedback") or {}
            v2_feedback_status = v2_feedback.get("status", "unknown")
            v2_missing_links = v2_feedback.get("missing_links", [])
            v2_guardrail = v2_json.get("guardrail") or {}
            v2_llm_status = v2_json.get("llm_status") or {}
            v2_guardrail_ok = v2_guardrail.get("ok")
            v2_guardrail_issues = len(v2_guardrail.get("issues", []) or [])
            if v2_guardrail_ok is not None:
                v2_guardrail_total += 1
                if v2_guardrail_ok:
                    v2_guardrail_pass += 1
            v2_fallback_used = bool(v2_json.get("fallback_used", False))
            v2_explanation = (v2_json.get("explanation") or {}).get("summary", "")
            v2_feedback_v1_status = (
                ((v2_json.get("phase2") or {}).get("feedback_v1") or {}).get("status") or ""
            )
            v2_judge = v2_json.get("judge") or {}
            if v2_judge:
                v2_judge_vote = v2_judge.get("vote", "tie")
                v2_judge_confidence = float(v2_judge.get("confidence", 0.0) or 0.0)
                v2_judge_rationale = v2_judge.get("rationale", "") or ""

            # Phase 3 artifacts
            best_iter = iter_json.get("best") or {}
            iter_history = iter_json.get("history") or []
            iter_llm_status = iter_json.get("llm_status") or {}
            iter_iterations = len(iter_history)
            nsla_iter_answer = best_iter.get("final_answer", "")
            iter_feedback = best_iter.get("feedback") or {}
            iter_status = iter_feedback.get("status", "unknown")
            iter_missing = iter_feedback.get("missing_links", [])
            iter_conflicts = iter_feedback.get("conflicting_axioms", [])
            iter_guardrail = best_iter.get("guardrail") or {}
            iter_guardrail_ok = iter_guardrail.get("ok")
            iter_guardrail_issues = len(iter_guardrail.get("issues", []) or [])
            if iter_guardrail_ok is not None:
                iter_guardrail_total += 1
                if iter_guardrail_ok:
                    iter_guardrail_pass += 1
            
            # Valutazione correctness
            llm_only_correct = is_correct(llm_only_answer, gold_answer)
            nsla_correct = is_correct(nsla_answer, gold_answer)
            nsla_v2_correct = is_correct(nsla_v2_answer, gold_answer)
            nsla_iter_correct = is_correct(nsla_iter_answer, gold_answer)
            
            # Calcolo EM e F1
            em_llm = 1 if llm_only_answer.strip().lower() == gold_answer.strip().lower() else 0
            em_nsla = 1 if nsla_answer.strip().lower() == gold_answer.strip().lower() else 0
            em_nsla_v2 = 1 if nsla_v2_answer.strip().lower() == gold_answer.strip().lower() else 0
            em_nsla_iter = 1 if nsla_iter_answer.strip().lower() == gold_answer.strip().lower() else 0
            f1_llm = _f1_score(llm_only_answer, gold_answer)
            f1_nsla = _f1_score(nsla_answer, gold_answer)
            f1_nsla_v2 = _f1_score(nsla_v2_answer, gold_answer)
            f1_nsla_iter = _f1_score(nsla_iter_answer, gold_answer)
            
            # Calcolo BLEU (se richiesto)
            if use_bleu:
                bleu_llm = _bleu_score_simple(llm_only_answer, gold_answer)
                bleu_nsla = _bleu_score_simple(nsla_answer, gold_answer)
                bleu_nsla_v2 = _bleu_score_simple(nsla_v2_answer, gold_answer)
                bleu_nsla_iter = _bleu_score_simple(nsla_iter_answer, gold_answer)
            
            # Judge LLM (se richiesto)
            if use_judge:
                judge_result = call_judge_llm(
                    question,
                    llm_only_answer,
                    nsla_v2_answer,
                    gold_answer,
                    base_url,
                    timeout=timeout_judge,
                )
                judge_vote = judge_result.get("vote", "tie")
                judge_confidence = float(judge_result.get("confidence", 0.0) or 0.0)
                judge_rationale = judge_result.get("rationale", "") or ""
                if judge_vote == "NSLA":
                    nsla_wins += 1
            
            # Aggiorna statistiche
            total_time_llm.append(t_llm)
            total_time_nsla.append(t_nsla)
            total_time_nsla_v2.append(t_nsla_v2)
            total_time_nsla_iter.append(t_nsla_iter)
            total_llm_correct += llm_only_correct
            total_nsla_correct += nsla_correct
            total_nsla_v2_correct += nsla_v2_correct
            total_nsla_iter_correct += nsla_iter_correct
            total_llm_em += em_llm
            total_nsla_em += em_nsla
            total_nsla_v2_em += em_nsla_v2
            total_nsla_iter_em += em_nsla_iter
            total_llm_f1 += f1_llm
            total_nsla_f1 += f1_nsla
            total_nsla_v2_f1 += f1_nsla_v2
            total_nsla_iter_f1 += f1_nsla_iter
            total_bleu_llm += bleu_llm
            total_bleu_nsla += bleu_nsla
            total_bleu_nsla_v2 += bleu_nsla_v2
            total_bleu_nsla_iter += bleu_nsla_iter

            for tag in tags:
                tm = tag_metrics.setdefault(
                    tag,
                    {
                        "cases": 0,
                        "llm_correct": 0,
                        "nsla_correct": 0,
                        "nsla_v2_correct": 0,
                        "nsla_iter_correct": 0,
                        "llm_f1": 0.0,
                        "nsla_f1": 0.0,
                        "nsla_v2_f1": 0.0,
                        "nsla_iter_f1": 0.0,
                    },
                )
                tm["cases"] += 1
                tm["llm_correct"] += int(llm_only_correct)
                tm["nsla_correct"] += int(nsla_correct)
                tm["nsla_v2_correct"] += int(nsla_v2_correct)
                tm["nsla_iter_correct"] += int(nsla_iter_correct)
                tm["llm_f1"] += f1_llm
                tm["nsla_f1"] += f1_nsla
                tm["nsla_v2_f1"] += f1_nsla_v2
                tm["nsla_iter_f1"] += f1_nsla_iter
            
            # Caso di successo
            n_success += 1
            
        except (ConnectionError, RuntimeError, RequestException) as e:
            # Gestione errori di connessione e HTTP
            n_fail += 1
            case_error = str(e)
            logger.error("Errore nel processare il caso %s: %s", case_id, e)
            error_messages.append(f"Caso {case_id} fallito: {e}")
            
            # Aggiungi tempi di default per il caso fallito
            total_time_llm.append(t_llm)
            total_time_nsla.append(t_nsla)
            total_time_nsla_v2.append(t_nsla_v2)
            total_time_nsla_iter.append(t_nsla_iter)
        except Exception as e:
            # Gestione di altri errori imprevisti
            n_fail += 1
            case_error = f"Errore imprevisto: {str(e)}"
            logger.error("Errore imprevisto nel caso %s: %s", case_id, e)
            error_messages.append(f"Caso {case_id} fallito: {case_error}")
            
            # Aggiungi tempi di default
            total_time_llm.append(t_llm)
            total_time_nsla.append(t_nsla)
            total_time_nsla_v2.append(t_nsla_v2)
            total_time_nsla_iter.append(t_nsla_iter)
        
        # Crea la riga per questo caso
        row = {
            "id": case_id,
            "tags": ",".join(tags) if tags else "",
            "question": question,
            "gold_answer": gold_answer,
            "llm_only_answer": llm_only_answer,
            "nsla_answer": nsla_answer,
            "nsla_v2_answer": nsla_v2_answer,
            "nsla_iter_answer": nsla_iter_answer,
            "llm_only_correct": llm_only_correct,
            "nsla_correct": nsla_correct,
            "nsla_v2_correct": nsla_v2_correct,
            "nsla_iter_correct": nsla_iter_correct,
            "llm_only_EM": em_llm,
            "nsla_EM": em_nsla,
            "nsla_v2_EM": em_nsla_v2,
            "nsla_iter_EM": em_nsla_iter,
            "llm_only_F1": round(f1_llm * 100, 2),
            "nsla_F1": round(f1_nsla * 100, 2),
            "nsla_v2_F1": round(f1_nsla_v2 * 100, 2),
            "nsla_iter_F1": round(f1_nsla_iter * 100, 2),
            "bleu_score_llm": round(bleu_llm * 100, 2),
            "bleu_score_nsla": round(bleu_nsla * 100, 2),
            "bleu_score_nsla_v2": round(bleu_nsla_v2 * 100, 2),
            "bleu_score_nsla_iter": round(bleu_nsla_iter * 100, 2),
            "judge_vote": judge_vote,
            "judge_confidence": judge_confidence,
            "judge_rationale": judge_rationale,
            "v2_judge_vote": v2_judge_vote,
            "v2_judge_confidence": v2_judge_confidence,
            "v2_judge_rationale": v2_judge_rationale,
            "llm_only_time": t_llm,
            "nsla_time": t_nsla,
            "nsla_v2_time": t_nsla_v2,
            "nsla_iter_time": t_nsla_iter,
            "verified": verified,
            "v2_feedback_status": v2_feedback_status,
            "v2_missing_links": "|".join(v2_missing_links),
            "v2_guardrail_ok": v2_guardrail_ok,
            "v2_guardrail_issues": v2_guardrail_issues,
            "v2_fallback_used": v2_fallback_used,
            "v2_explanation": v2_explanation,
            "v2_feedback_v1_status": v2_feedback_v1_status,
            "v2_llm_status": json.dumps(v2_llm_status, ensure_ascii=False),
            "iter_status": iter_status,
            "iter_missing_links": "|".join(iter_missing),
            "iter_conflicts": "|".join(iter_conflicts),
            "iter_guardrail_ok": iter_guardrail_ok,
            "iter_guardrail_issues": iter_guardrail_issues,
            "iter_iterations": iter_iterations,
            "iter_llm_status": json.dumps(iter_llm_status, ensure_ascii=False),
            "delta_f1_v2_vs_v1": round((f1_nsla_v2 - f1_nsla) * 100, 2),
            "delta_f1_iter_vs_v2": round((f1_nsla_iter - f1_nsla_v2) * 100, 2),
            "error": case_error
        }
        rows.append(row)
        
        print(
            f"Caso {case_id}: LLM={llm_only_correct} | NSLA={nsla_correct} | "
            f"EM LLM={em_llm} | EM NSLA={em_nsla} | F1 LLM={f1_llm:.3f} | "
            f"F1 NSLA={f1_nsla:.3f} | v2Judge={v2_judge_vote or 'n/a'} | BenchJudge={judge_vote}"
        )
    
    # Calcolo metriche aggregate
    if rows:
        llm_only_accuracy = total_llm_correct / n_cases
        nsla_accuracy = total_nsla_correct / n_cases
        nsla_v2_accuracy = total_nsla_v2_correct / n_cases
        nsla_iter_accuracy = total_nsla_iter_correct / n_cases
        llm_only_em = (total_llm_em / n_cases) * 100
        nsla_em = (total_nsla_em / n_cases) * 100
        nsla_v2_em = (total_nsla_v2_em / n_cases) * 100
        nsla_iter_em = (total_nsla_iter_em / n_cases) * 100
        llm_only_f1 = (total_llm_f1 / n_cases) * 100
        nsla_f1 = (total_nsla_f1 / n_cases) * 100
        nsla_v2_f1 = (total_nsla_v2_f1 / n_cases) * 100
        nsla_iter_f1 = (total_nsla_iter_f1 / n_cases) * 100
        avg_llm_only_time = sum(total_time_llm) / len(total_time_llm)
        avg_nsla_time = sum(total_time_nsla) / len(total_time_nsla)
        avg_nsla_v2_time = (
            sum(total_time_nsla_v2) / len(total_time_nsla_v2) if total_time_nsla_v2 else 0.0
        )
        avg_nsla_iter_time = (
            sum(total_time_nsla_iter) / len(total_time_nsla_iter) if total_time_nsla_iter else 0.0
        )
        llm_only_std_time = statistics.stdev(total_time_llm) if len(total_time_llm) > 1 else 0.0
        nsla_std_time = statistics.stdev(total_time_nsla) if len(total_time_nsla) > 1 else 0.0
        nsla_v2_std_time = (
            statistics.stdev(total_time_nsla_v2) if len(total_time_nsla_v2) > 1 else 0.0
        )
        nsla_iter_std_time = (
            statistics.stdev(total_time_nsla_iter) if len(total_time_nsla_iter) > 1 else 0.0
        )
        bleu_llm_avg = (total_bleu_llm / n_cases) * 100 if use_bleu else 0.0
        bleu_nsla_avg = (total_bleu_nsla / n_cases) * 100 if use_bleu else 0.0
        bleu_nsla_v2_avg = (total_bleu_nsla_v2 / n_cases) * 100 if use_bleu else 0.0
        bleu_nsla_iter_avg = (total_bleu_nsla_iter / n_cases) * 100 if use_bleu else 0.0
        nsla_win_rate = (nsla_wins / n_cases) * 100 if use_judge else 0.0
    else:
        llm_only_accuracy = 0.0
        nsla_accuracy = 0.0
        nsla_v2_accuracy = 0.0
        nsla_iter_accuracy = 0.0
        llm_only_em = 0.0
        nsla_em = 0.0
        nsla_v2_em = 0.0
        nsla_iter_em = 0.0
        llm_only_f1 = 0.0
        nsla_f1 = 0.0
        nsla_v2_f1 = 0.0
        nsla_iter_f1 = 0.0
        avg_llm_only_time = 0.0
        avg_nsla_time = 0.0
        avg_nsla_v2_time = 0.0
        avg_nsla_iter_time = 0.0
        llm_only_std_time = 0.0
        nsla_std_time = 0.0
        nsla_v2_std_time = 0.0
        nsla_iter_std_time = 0.0
        bleu_llm_avg = 0.0
        bleu_nsla_avg = 0.0
        bleu_nsla_v2_avg = 0.0
        bleu_nsla_iter_avg = 0.0
        nsla_win_rate = 0.0
    
    # Salvataggio risultati su CSV
    if rows:
        fieldnames = list(rows[0].keys())
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    
    total_duration = time.perf_counter() - start_time
    
    # Costruzione del risultato finale
    result = {
        "n_cases": n_cases,
        "n_success": n_success,
        "n_fail": n_fail,
        "llm_only_accuracy": llm_only_accuracy,
        "nsla_accuracy": nsla_accuracy,
        "nsla_v2_accuracy": nsla_v2_accuracy,
        "nsla_iter_accuracy": nsla_iter_accuracy,
        "avg_llm_only_time": avg_llm_only_time,
        "avg_nsla_time": avg_nsla_time,
        "avg_nsla_v2_time": avg_nsla_v2_time,
        "avg_nsla_iter_time": avg_nsla_iter_time,
        "llm_only_EM": round(llm_only_em, 2),
        "nsla_EM": round(nsla_em, 2),
        "nsla_v2_EM": round(nsla_v2_em, 2),
        "nsla_iter_EM": round(nsla_iter_em, 2),
        "llm_only_F1": round(llm_only_f1, 2),
        "nsla_F1": round(nsla_f1, 2),
        "nsla_v2_F1": round(nsla_v2_f1, 2),
        "nsla_iter_F1": round(nsla_iter_f1, 2),
        "bert_score_llm": 0.0,
        "bert_score_nsla": 0.0,
        "bleu_score_llm": round(bleu_llm_avg, 2),
        "bleu_score_nsla": round(bleu_nsla_avg, 2),
        "bleu_score_nsla_v2": round(bleu_nsla_v2_avg, 2),
        "bleu_score_nsla_iter": round(bleu_nsla_iter_avg, 2),
        "nsla_win_rate": round(nsla_win_rate, 2),
        "llm_only_std_time": round(llm_only_std_time, 3),
        "nsla_std_time": round(nsla_std_time, 3),
        "nsla_v2_std_time": round(nsla_v2_std_time, 3),
        "nsla_iter_std_time": round(nsla_iter_std_time, 3),
        "total_duration": round(total_duration, 3),
        "details": rows,
        "error": None if not error_messages else "; ".join(error_messages)
    }

    v2_guardrail_rate = (
        v2_guardrail_pass / v2_guardrail_total if v2_guardrail_total else 0.0
    )
    iter_guardrail_rate = (
        iter_guardrail_pass / iter_guardrail_total if iter_guardrail_total else 0.0
    )

    tag_stats = []
    for tag, stats in sorted(tag_metrics.items()):
        cases = stats["cases"]
        tag_stats.append(
            {
                "tag": tag,
                "cases": cases,
                "llm_accuracy": stats["llm_correct"] / cases if cases else 0.0,
                "nsla_accuracy": stats["nsla_correct"] / cases if cases else 0.0,
                "nsla_v2_accuracy": stats["nsla_v2_correct"] / cases if cases else 0.0,
                "nsla_iter_accuracy": stats["nsla_iter_correct"] / cases if cases else 0.0,
                "llm_F1": (stats["llm_f1"] / cases) * 100 if cases else 0.0,
                "nsla_F1": (stats["nsla_f1"] / cases) * 100 if cases else 0.0,
                "nsla_v2_F1": (stats["nsla_v2_f1"] / cases) * 100 if cases else 0.0,
                "nsla_iter_F1": (stats["nsla_iter_f1"] / cases) * 100 if cases else 0.0,
            }
        )

    result["v2_guardrail_pass_rate"] = round(v2_guardrail_rate, 3)
    result["iter_guardrail_pass_rate"] = round(iter_guardrail_rate, 3)
    result["tag_stats"] = tag_stats
    
    # Log della richiesta
    _log_request("full_benchmark", f"{n_cases} casi", result, total_duration)
    
    # Stampa del report finale
    print("\n" + "=" * 60)
    print("RISULTATI BENCHMARK AVANZATO")
    print(f"Casi testati: {n_cases}")
    print(f"Casi riusciti: {n_success}")
    print(f"Casi falliti: {n_fail}")
    print(f"Durata totale: {total_duration:.1f}s")
    print(f"Accuracy LLM-only: {llm_only_accuracy*100:.2f}%")
    print(f"Accuracy NSLA: {nsla_accuracy*100:.2f}%")
    print(f"Accuracy NSLA v2: {nsla_v2_accuracy*100:.2f}%")
    print(f"Accuracy NSLA iter: {nsla_iter_accuracy*100:.2f}%")
    print(f"EM LLM-only: {llm_only_em:.2f}%")
    print(f"EM NSLA: {nsla_em:.2f}%")
    print(f"EM NSLA v2: {nsla_v2_em:.2f}%")
    print(f"EM NSLA iter: {nsla_iter_em:.2f}%")
    print(f"F1 LLM-only: {llm_only_f1:.2f}%")
    print(f"F1 NSLA: {nsla_f1:.2f}%")
    print(f"F1 NSLA v2: {nsla_v2_f1:.2f}%")
    print(f"F1 NSLA iter: {nsla_iter_f1:.2f}%")
    if use_bleu:
        print(f"BLEU LLM-only: {bleu_llm_avg:.2f}%")
        print(f"BLEU NSLA: {bleu_nsla_avg:.2f}%")
        print(f"BLEU NSLA v2: {bleu_nsla_v2_avg:.2f}%")
        print(f"BLEU NSLA iter: {bleu_nsla_iter_avg:.2f}%")
    if use_judge:
        print(f"NSLA Win Rate: {nsla_win_rate:.2f}%")
    print(f"Tempo medio LLM-only: {avg_llm_only_time:.3f}s ± {llm_only_std_time:.3f}s")
    print(f"Tempo medio NSLA: {avg_nsla_time:.3f}s ± {nsla_std_time:.3f}s")
    print(f"Tempo medio NSLA v2: {avg_nsla_v2_time:.3f}s ± {nsla_v2_std_time:.3f}s")
    print(f"Tempo medio NSLA iter: {avg_nsla_iter_time:.3f}s ± {nsla_iter_std_time:.3f}s")
    print(f"Guardrail v2 OK: {v2_guardrail_rate*100:.1f}% | Iter guardrail OK: {iter_guardrail_rate*100:.1f}%")
    if error_messages:
        print(f"Errori: {len(error_messages)}")
    print("=" * 60)
    
    return result


def main():
    """Funzione principale per l'esecuzione del benchmark."""
    import argparse
    
    parser = argparse.ArgumentParser(description="NSLA Benchmark avanzato")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="URL del server")
    parser.add_argument("--cases", default="data/cases_dev.json", help="File dei casi di test")
    parser.add_argument("--output", default="data/results.csv", help="File di output CSV")
    parser.add_argument("--no-bleu", action="store_true", help="Disabilita calcolo BLEU")
    parser.add_argument("--judge", action="store_true", help="Abilita judge LLM")
    parser.add_argument(
        "--case-id",
        dest="case_ids",
        action="append",
        help="ID specifico del caso da eseguire (ripetibile)",
    )
    parser.add_argument(
        "--timeout-llm",
        type=float,
        default=300.0,
        help="Timeout (s) per /llm_only. Usa <=0 per disabilitare.",
    )
    parser.add_argument(
        "--timeout-nsla",
        type=float,
        default=300.0,
        help="Timeout (s) per /legal_query.",
    )
    parser.add_argument(
        "--timeout-v2",
        type=float,
        default=600.0,
        help="Timeout (s) per /legal_query_v2.",
    )
    parser.add_argument(
        "--timeout-iter",
        type=float,
        default=900.0,
        help="Timeout (s) per /legal_query_v2_iterative.",
    )
    parser.add_argument(
        "--timeout-judge",
        type=float,
        default=300.0,
        help="Timeout (s) per /judge_compare.",
    )
    
    args = parser.parse_args()
    
    try:
        result = run_benchmark(
            base_url=args.url,
            cases_path=args.cases,
            csv_path=args.output,
            use_bleu=not args.no_bleu,
            use_judge=args.judge,
            timeout_llm=args.timeout_llm,
            timeout_nsla=args.timeout_nsla,
            timeout_v2=args.timeout_v2,
            timeout_iter=args.timeout_iter,
            timeout_judge=args.timeout_judge,
            case_ids=args.case_ids,
        )
        print(f"\nBenchmark completato! Risultati salvati in {args.output}")
    except Exception as e:
        print(f"Errore durante l'esecuzione del benchmark: {e}")


if __name__ == "__main__":
    main()
