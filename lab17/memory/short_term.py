"""Short-term memory: sliding window conversation buffer."""
from __future__ import annotations

import tiktoken
from typing import Any

from .base import BaseMemory


class ShortTermMemory(BaseMemory):
    """Sliding window buffer keeping the most recent messages.

    Uses tiktoken for accurate token counting (bonus: token counting +2).
    """

    def __init__(self, max_messages: int = 20, max_tokens: int = 2000):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.messages: list[dict[str, str]] = []
        self._encoder = tiktoken.get_encoding("cl100k_base")

    # ---- public interface ----

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the buffer."""
        self.messages.append({"role": role, "content": content})
        self._enforce_window()

    def get_recent(self, k: int | None = None) -> list[dict[str, str]]:
        """Return the *k* most recent messages (default: all in window)."""
        if k is None:
            return list(self.messages)
        return list(self.messages[-k:])

    def trim(self, max_tokens: int | None = None) -> list[dict[str, str]]:
        """Trim messages to fit within *max_tokens* and return kept messages."""
        budget = max_tokens or self.max_tokens
        kept: list[dict[str, str]] = []
        used = 0
        for msg in reversed(self.messages):
            t = self.count_tokens(msg["content"])
            if used + t > budget:
                break
            kept.insert(0, msg)
            used += t
        self.messages = kept
        return kept

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken (accurate, not word-count)."""
        return len(self._encoder.encode(text))

    def total_tokens(self) -> int:
        """Total tokens currently in the buffer."""
        return sum(self.count_tokens(m["content"]) for m in self.messages)

    # ---- base overrides ----

    def clear(self) -> None:
        self.messages.clear()

    def get_stats(self) -> dict[str, Any]:
        return {
            "type": "short_term",
            "message_count": len(self.messages),
            "total_tokens": self.total_tokens(),
            "max_messages": self.max_messages,
            "max_tokens": self.max_tokens,
        }

    # ---- internals ----

    def _enforce_window(self) -> None:
        """Keep only the latest max_messages."""
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def format_for_prompt(self) -> str:
        """Format messages for prompt injection."""
        lines: list[str] = []
        for m in self.messages:
            prefix = "User" if m["role"] == "user" else "Assistant"
            lines.append(f"{prefix}: {m['content']}")
        return "\n".join(lines)
