"""Long-term profile memory backed by Redis (real).

Bonus: Redis thật +2.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import redis

from .base import BaseMemory

logger = logging.getLogger(__name__)


class LongTermMemory(BaseMemory):
    """User profile store using Redis Hashes.

    Each user gets a Redis hash  ``user:<user_id>:profile``  where every
    field is a profile fact (e.g. ``name``, ``allergy``, ``fav_language``).

    A changelog list  ``user:<user_id>:changelog``  tracks every mutation
    so conflict resolution is auditable.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379", user_id: str = "default"):
        self.user_id = user_id
        self.redis_url = redis_url
        try:
            self.client = redis.from_url(redis_url, decode_responses=True)
            self.client.ping()
            self._connected = True
            logger.info("Redis connected at %s", redis_url)
        except redis.ConnectionError:
            logger.warning("Redis not available – falling back to in-memory dict")
            self._connected = False
            self._fallback: dict[str, dict[str, str]] = {}
            self._fallback_log: dict[str, list[dict]] = {}

    # ---- keys ----

    @property
    def _profile_key(self) -> str:
        return f"user:{self.user_id}:profile"

    @property
    def _changelog_key(self) -> str:
        return f"user:{self.user_id}:changelog"

    # ---- public interface ----

    def get_profile(self) -> dict[str, str]:
        """Return full profile dict."""
        if self._connected:
            return self.client.hgetall(self._profile_key)
        return dict(self._fallback.get(self.user_id, {}))

    def get_fact(self, key: str) -> str | None:
        """Get a single profile fact."""
        if self._connected:
            return self.client.hget(self._profile_key, key)
        return self._fallback.get(self.user_id, {}).get(key)

    def update_fact(self, key: str, value: str) -> dict[str, Any]:
        """Update a profile fact. Returns change record with conflict info."""
        old_value = self.get_fact(key)
        is_conflict = old_value is not None and old_value != value

        change_record = {
            "timestamp": datetime.now().isoformat(),
            "key": key,
            "old_value": old_value,
            "new_value": value,
            "is_conflict": is_conflict,
        }

        # Always overwrite with new value (latest wins)
        if self._connected:
            self.client.hset(self._profile_key, key, value)
            self.client.rpush(self._changelog_key, json.dumps(change_record))
        else:
            self._fallback.setdefault(self.user_id, {})[key] = value
            self._fallback_log.setdefault(self.user_id, []).append(change_record)

        if is_conflict:
            logger.info(
                "Conflict resolved for '%s': '%s' -> '%s' (latest wins)",
                key, old_value, value,
            )
        return change_record

    def delete_fact(self, key: str) -> bool:
        """Delete a profile fact. Returns True if it existed."""
        existed = self.get_fact(key) is not None
        if self._connected:
            self.client.hdel(self._profile_key, key)
        else:
            self._fallback.get(self.user_id, {}).pop(key, None)
        return existed

    def get_changelog(self) -> list[dict]:
        """Return mutation history for auditing."""
        if self._connected:
            raw = self.client.lrange(self._changelog_key, 0, -1)
            return [json.loads(r) for r in raw]
        return list(self._fallback_log.get(self.user_id, []))

    def set_user(self, user_id: str) -> None:
        """Switch active user."""
        self.user_id = user_id

    # ---- base overrides ----

    def clear(self) -> None:
        if self._connected:
            self.client.delete(self._profile_key)
            self.client.delete(self._changelog_key)
        else:
            self._fallback.pop(self.user_id, None)
            self._fallback_log.pop(self.user_id, None)

    def get_stats(self) -> dict[str, Any]:
        profile = self.get_profile()
        return {
            "type": "long_term",
            "backend": "redis" if self._connected else "in-memory",
            "user_id": self.user_id,
            "fact_count": len(profile),
            "changelog_size": len(self.get_changelog()),
        }

    def format_for_prompt(self) -> str:
        """Format profile as key-value pairs for prompt injection."""
        profile = self.get_profile()
        if not profile:
            return "No profile information available."
        lines = [f"- {k}: {v}" for k, v in profile.items()]
        return "\n".join(lines)
