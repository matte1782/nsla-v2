"""
Utility script to hit the local `/legal_query_v2` endpoint for a handful of
benchmark cases and store the responses under `data/`.

Usage
-----
python scripts/manual_sanity.py case_009 case_020
python scripts/manual_sanity.py            # runs all predefined cases
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict

import requests

API_URL = "http://127.0.0.1:8000/legal_query_v2"
OUTPUT_DIR = Path("data")

CASES: Dict[str, Dict[str, str]] = {
    "case_001": {
        "question": (
            "Quali sono gli elementi costitutivi di un contratto valido "
            "secondo il diritto italiano?"
        ),
        "reference_answer": (
            "Un contratto è valido solo se sussistono cinque requisiti: "
            "accordo tra le parti, causa lecita, oggetto possibile e "
            "determinato, forma prescritta quando richiesta e capacità delle "
            "parti."
        ),
    },
    "case_005": {
        "question": "Cosa si intende per contratto di adesione?",
        "reference_answer": (
            "È un contratto predisposto unilateralmente dal professionista in "
            "cui l'altra parte può solo aderire senza negoziare clausole."
        ),
    },
    "case_009": {
        "question": "In cosa consiste l'usucapione per i beni immobili?",
        "reference_answer": (
            "L'usucapione immobiliare consente di acquistare la proprieta "
            "per effetto di un possesso pubblico, pacifico, ininterrotto "
            "e con animus domini protratto per vent'anni, salvo termini "
            "abbreviati previsti dalla legge."
        ),
    },
    "case_020": {
        "question": "Qual e il regime della responsabilita del vettore per il trasporto di cose?",
        "reference_answer": (
            "Il vettore risponde della perdita o avaria delle cose dal momento "
            "in cui le riceve sino alla consegna, salvo provi che l'evento "
            "deriva da caso fortuito, vizio della cosa o forza maggiore."
        ),
    },
    "case_023": {
        "question": (
            "Quali requisiti servono per l'usucapione abbreviata di beni "
            "mobili registrati?"
        ),
        "reference_answer": (
            "Servono tre anni di possesso continuato e pubblico in buona fede "
            "con titolo idoneo regolarmente trascritto; altrimenti vale il "
            "termine ordinario ventennale."
        ),
    },
}


def run_case(case_id: str) -> None:
    if case_id not in CASES:
        raise SystemExit(f"Unknown case id: {case_id}")

    payload = CASES[case_id]
    response = requests.post(API_URL, json=payload, timeout=180)
    response.raise_for_status()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{case_id}_response.json"
    out_path.write_text(
        json.dumps(response.json(), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(f"[manual_sanity] Saved {case_id} response to {out_path}")


def main() -> None:
    case_ids = sys.argv[1:] or list(CASES.keys())
    for case_id in case_ids:
        run_case(case_id)


if __name__ == "__main__":
    main()

