"""Token budget manager with 4-level priority eviction.

Bonus: Token counting thật (tiktoken) +2.
"""
from __future__ import annotations

import tiktoken
from typing import Any


class TokenBudgetManager:
    """Manages token budget for memory injection into prompts.

    4-level priority eviction hierarchy (lowest priority trimmed first):
      1. Semantic hits   (least critical – can re-search)
      2. Episodic memories (moderately important)
      3. Long-term profile (important for personalization)
      4. Short-term conversation (most critical – never trimmed, keeps coherence)
    """

    def __init__(self, total_budget: int = 4000):
        self.total_budget = total_budget
        self._encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Accurate token count via tiktoken."""
        if not text:
            return 0
        return len(self._encoder.encode(text))

    def allocate_budget(
        self,
        profile_text: str,
        episodic_text: str,
        semantic_text: str,
        short_term_text: str,
    ) -> dict[str, str]:
        """Apply 4-level priority eviction and return trimmed sections.

        Priority (highest kept last): short_term > profile > episodic > semantic.

        Returns dict with keys: profile, episodic, semantic, short_term.
        Each value is the (possibly trimmed) text that fits within budget.
        """
        # Short-term always gets full allocation (priority 4 – highest)
        st_tokens = self.count_tokens(short_term_text)

        remaining = self.total_budget - st_tokens

        # Long-term profile (priority 3)
        profile_tokens = self.count_tokens(profile_text)
        if profile_tokens > remaining * 0.4:
            profile_text = self._trim_text(profile_text, int(remaining * 0.4))
            profile_tokens = self.count_tokens(profile_text)
        remaining -= profile_tokens

        # Episodic (priority 2)
        ep_tokens = self.count_tokens(episodic_text)
        if ep_tokens > remaining * 0.5:
            episodic_text = self._trim_text(episodic_text, int(remaining * 0.5))
            ep_tokens = self.count_tokens(episodic_text)
        remaining -= ep_tokens

        # Semantic (priority 1 – lowest, trimmed most aggressively)
        sem_tokens = self.count_tokens(semantic_text)
        if sem_tokens > remaining:
            semantic_text = self._trim_text(semantic_text, max(remaining, 0))

        return {
            "profile": profile_text,
            "episodic": episodic_text,
            "semantic": semantic_text,
            "short_term": short_term_text,
        }

    def get_usage_report(
        self,
        profile_text: str,
        episodic_text: str,
        semantic_text: str,
        short_term_text: str,
    ) -> dict[str, Any]:
        """Return detailed token usage breakdown."""
        p = self.count_tokens(profile_text)
        e = self.count_tokens(episodic_text)
        s = self.count_tokens(semantic_text)
        st = self.count_tokens(short_term_text)
        total = p + e + s + st
        return {
            "profile_tokens": p,
            "episodic_tokens": e,
            "semantic_tokens": s,
            "short_term_tokens": st,
            "total_tokens": total,
            "budget": self.total_budget,
            "utilization": f"{total / self.total_budget:.1%}" if self.total_budget else "N/A",
            "within_budget": total <= self.total_budget,
        }

    def _trim_text(self, text: str, max_tokens: int) -> str:
        """Trim text to fit within max_tokens (keep from the end for recency)."""
        if max_tokens <= 0:
            return ""
        tokens = self._encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        # Keep the last max_tokens tokens (recency bias)
        trimmed_tokens = tokens[-max_tokens:]
        return "... " + self._encoder.decode(trimmed_tokens)
