from __future__ import annotations

import csv
from pathlib import Path

ROWS = [
    "id",
    "v2_guardrail_ok",
    "v2_guardrail_issues",
    "v2_fallback_used",
    "v2_feedback_status",
]


def main() -> None:
    path = Path("data/results_subset_phase4_round29.csv")
    if not path.exists():
        raise SystemExit(f"{path} missing")

    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            print(" | ".join(f"{k}={row.get(k)}" for k in ROWS))


if __name__ == "__main__":
    main()








