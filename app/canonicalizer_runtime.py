"""
Runtime wrapper for Phase 2.1 Canonicalizer.

This module encapsulates the interaction with ``LLMClient.call_canonicalizer`` by
adding:

- input validation and logging
- optional in-memory caching (to avoid re-hitting the LLM in iterative flows)
- deterministic fallback when the LLM backend is unavailable

It exposes a single entry point ``CanonicalizerRuntime.run(question)`` returning
``CanonicalizerOutput`` objects, making it easy to swap the backend during tests.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

from .models_v2 import CanonicalizerOutput

logger = logging.getLogger(__name__)


class CanonicalizerRuntime:
    """
    Execute the legal canonicalizer with optional caching/fallback.

    Args:
        llm_client: Instance exposing ``call_canonicalizer`` and optionally the
            dummy helper ``_build_dummy_canonicalizer_output``.
        enable_cache: Whether to cache canonicalizations by normalized question.
        cache_ttl: Optional TTL (seconds) for cached entries. ``None`` disables TTL.
    """

    def __init__(
        self,
        llm_client,
        enable_cache: bool = True,
        cache_ttl: Optional[float] = 600.0,
    ) -> None:
        self.llm_client = llm_client
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, CanonicalizerOutput]] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run(self, question: str) -> CanonicalizerOutput:
        """
        Run the canonicalizer over a legal question.

        Returns:
            CanonicalizerOutput populated with mapped concepts/unmapped terms.

        Raises:
            ValueError: If the question is empty.
        """
        normalized = (question or "").strip()
        if not normalized:
            raise ValueError("CanonicalizerRuntime requires a non-empty question")

        cached = self._get_from_cache(normalized)
        if cached is not None:
            logger.debug("Canonicalizer cache hit (len(question)=%d)", len(normalized))
            return cached

        try:
            output = self.llm_client.call_canonicalizer(normalized)
            logger.info(
                "Canonicalizer completed: %d concepts, %d unmapped terms",
                len(output.concepts),
                len(output.unmapped_terms),
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning(
                "Canonicalizer failed (%s). Falling back to deterministic output.",
                exc,
                exc_info=True,
            )
            output = self._fallback(normalized)

        self._store_in_cache(normalized, output)
        return output

    def clear_cache(self) -> None:
        """Clear the internal cache (useful for tests)."""
        self._cache.clear()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _fallback(self, question: str) -> CanonicalizerOutput:
        """
        Deterministic fallback when the backend is unavailable.

        Prefer the LLM client's dummy helper if available, otherwise synthesize a
        minimal structure containing only the original question.
        """
        builder = getattr(self.llm_client, "_build_dummy_canonicalizer_output", None)
        if callable(builder):
            return builder(question)

        return CanonicalizerOutput(
            question=question,
            language="it",
            domain="civil_law_contractual_liability",
            concepts=[],
            unmapped_terms=[],
        )

    def _get_from_cache(self, key: str) -> Optional[CanonicalizerOutput]:
        if not self.enable_cache:
            return None

        cached = self._cache.get(key)
        if cached is None:
            return None

        timestamp, value = cached
        if self.cache_ttl is not None and (time.time() - timestamp) > self.cache_ttl:
            del self._cache[key]
            return None
        return value

    def _store_in_cache(self, key: str, value: CanonicalizerOutput) -> None:
        if not self.enable_cache:
            return
        self._cache[key] = (time.time(), value)


__all__ = ["CanonicalizerRuntime"]

