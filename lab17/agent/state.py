"""LangGraph state definition for the multi-memory agent."""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class MemoryState(TypedDict):
    """Full state flowing through the LangGraph agent.

    Each field maps to a specific memory backend or control signal.
    """

    # Conversation messages (LangGraph managed)
    messages: Annotated[list, add_messages]

    # User identity
    user_id: str

    # Current user query (latest message)
    current_query: str

    # Intent classification result
    intent: str  # "preference_recall" | "experience_recall" | "factual_query" | "general"

    # Memory sections retrieved from backends
    user_profile: dict[str, str]       # from long-term (Redis)
    episodes: list[dict[str, Any]]     # from episodic (JSON)
    semantic_hits: list[dict[str, Any]] # from semantic (ChromaDB)
    short_term_text: str               # formatted short-term buffer

    # Token budget
    memory_budget: int  # max tokens for memory sections

    # Trimmed memory sections (after budget allocation)
    trimmed_memory: dict[str, str]

    # Control flags
    should_save: bool  # whether to extract & save after response

    # Agent response
    response: str

    # Token usage report
    token_report: dict[str, Any]
