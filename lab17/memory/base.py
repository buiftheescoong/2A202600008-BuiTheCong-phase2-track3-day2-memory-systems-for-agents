"""Abstract base class for all memory backends."""
from abc import ABC, abstractmethod
from typing import Any


class BaseMemory(ABC):
    """Base interface for memory backends."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all data in this memory."""
        ...

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Return stats about this memory (size, count, etc.)."""
        ...
