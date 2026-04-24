"""Episodic memory: JSON log file store for past experiences/outcomes."""
from __future__ import annotations

import json
import os
import logging
from datetime import datetime
from typing import Any

from .base import BaseMemory

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class EpisodicMemory(BaseMemory):
    """Stores episodes (task outcomes, lessons learned) in a JSON file.

    Each episode is a dict with: summary, context, outcome, timestamp, tags.
    """

    def __init__(self, filepath: str | None = None):
        self.filepath = filepath or os.path.join(DATA_DIR, "episodes.json")
        self.episodes: list[dict[str, Any]] = self._load()

    # ---- public interface ----

    def save_episode(
        self,
        summary: str,
        context: str = "",
        outcome: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Save a new episode and persist to disk."""
        episode = {
            "id": len(self.episodes) + 1,
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "context": context,
            "outcome": outcome,
            "tags": tags or [],
        }
        self.episodes.append(episode)
        self._save()
        logger.info("Saved episode #%d: %s", episode["id"], summary[:60])
        return episode

    def search_episodes(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        """Keyword-based search over episodes. Returns top-k matches."""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored: list[tuple[float, dict]] = []
        for ep in self.episodes:
            text = f"{ep['summary']} {ep['context']} {ep['outcome']} {' '.join(ep.get('tags', []))}".lower()
            # Score = number of query words found in episode text
            score = sum(1 for w in query_words if w in text)
            if score > 0:
                scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:k]]

    def get_recent(self, k: int = 5) -> list[dict[str, Any]]:
        """Return k most recent episodes."""
        return list(self.episodes[-k:])

    # ---- base overrides ----

    def clear(self) -> None:
        self.episodes.clear()
        self._save()

    def get_stats(self) -> dict[str, Any]:
        return {
            "type": "episodic",
            "episode_count": len(self.episodes),
            "filepath": self.filepath,
        }

    def format_for_prompt(self, episodes: list[dict] | None = None) -> str:
        """Format episodes for prompt injection."""
        eps = episodes if episodes is not None else self.get_recent(3)
        if not eps:
            return "No past experiences recorded."
        lines: list[str] = []
        for ep in eps:
            lines.append(
                f"- [{ep.get('timestamp', '?')[:10]}] {ep['summary']}"
                + (f" | Outcome: {ep['outcome']}" if ep.get("outcome") else "")
            )
        return "\n".join(lines)

    # ---- internals ----

    def _load(self) -> list[dict[str, Any]]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, list) else []
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.episodes, f, ensure_ascii=False, indent=2)
