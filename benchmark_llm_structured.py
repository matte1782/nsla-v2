# benchmark_llm_structured.py
import time
import requests

# Configuration
API_URL = "http://127.0.0.1:8000/llm_structured"
TIMEOUT_SECONDS = 30

# Test questions
QUESTIONS = [
    "Cosa si intende per responsabilità contrattuale?",
    "Qual è la differenza tra licenziamento per giusta causa e per giustificato motivo?",
    "Come si calcola il TFR (Trattamento di Fine Rapporto)?",
    "Qual è la differenza tra multa e ammenda?",
    "Cosa si intende per azione revocatoria fallimentare?",
    "Come funziona il reato di riciclaggio di denaro?",
    "Qual è la differenza tra abbonamento e contratto a tempo determinato?",
    "Cosa si intende per mancato rinnovo di un contratto di locazione?",
    "Come funziona l'usucapione per i beni immobili?",
    "Cosa si intende per fallimento colposo?",
]

def run_benchmark():
    total_requests = len(QUESTIONS)
    valid_responses = 0
    total_time = 0.0

    print("Benchmarking /llm_structured endpoint...")
    print("=" * 50)

    for i, question in enumerate(QUESTIONS, 1):
        start_time = time.perf_counter()
        
        try:
            response = requests.post(
                API_URL,
                json={"question": question},
                timeout=TIMEOUT_SECONDS
            )
            elapsed = time.perf_counter() - start_time
            total_time += elapsed

            if response.status_code == 200:
                data = response.json()
                if (
                    data.get("final_answer", "").strip() and
                    isinstance(data.get("premises"), list) and data.get("premises") and
                    data.get("conclusion", "").strip() and
                    data.get("logic_program") and
                    all(key in data["logic_program"] for key in ("sorts", "constants", "axioms", "query"))
                ):
                    valid_responses += 1
                    status = "VALID"
                else:
                    status = "INVALID"
            else:
                elapsed = time.perf_counter() - start_time
                total_time += elapsed
                status = f"HTTP {response.status_code}"
                
        except requests.RequestException as e:
            elapsed = time.perf_counter() - start_time
            total_time += elapsed
            status = f"ERROR: {str(e)}"

        print(f"Request {i}/{total_requests} ({elapsed:.3f}s): {status}")

    # Calculate results
    success_rate = (valid_responses / total_requests) * 100
    avg_time = total_time / total_requests

    # Print summary
    print("\n" + "=" * 50)
    print("RESULTS")
    print(f"Total requests:     {total_requests}")
    print(f"Valid responses:    {valid_responses}")
    print(f"Success rate:       {success_rate:.2f}%")
    print(f"Average time:       {avg_time:.3f}s")

if __name__ == "__main__":
    try:
        run_benchmark()
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user.")
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        exit(1)
