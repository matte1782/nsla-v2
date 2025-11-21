"""
Utilities to summarize iterative NSLA v2 histories for prompts/logging.
"""

from __future__ import annotations

from typing import List

from .models_v2 import IterationState


class HistorySummarizer:
    """
    Build compact textual summaries of iteration histories.

    The summary is intentionally deterministic to guarantee reproducible prompts
    (important for tests and offline benchmarking).
    """

    def summarize(self, history: List[IterationState], max_entries: int = 3) -> str:
        """
        Summarize the last ``max_entries`` iterations (default: 3).
        """
        if not history:
            return "Nessuna iterazione precedente: questa è la prima proposta."

        tail = history[-max_entries:]
        lines = [
            "Contesto iterativo (più recente alla fine):",
        ]

        for state in tail:
            missing = ", ".join(state.feedback.missing_links) or "nessuno"
            conflicts = ", ".join(state.feedback.conflicting_axioms) or "nessuno"
            lines.append(
                f"- iter {state.iteration}: status={state.feedback.status}; "
                f"missing={missing}; conflicts={conflicts}; "
                f"summary={state.feedback.human_summary}"
            )

        return "\n".join(lines)


__all__ = ["HistorySummarizer"]

