"""LangGraph node functions for the multi-memory agent."""
from __future__ import annotations

import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from .state import MemoryState
from .prompt import build_system_prompt, NO_MEMORY_SYSTEM_PROMPT
from .router import MemoryRouter
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from utils.token_budget import TokenBudgetManager
from utils.extraction import FactExtractor

logger = logging.getLogger(__name__)

# ---------- Shared resources (injected at graph build time) ----------

_short_term: ShortTermMemory | None = None
_long_term: LongTermMemory | None = None
_episodic: EpisodicMemory | None = None
_semantic: SemanticMemory | None = None
_router: MemoryRouter | None = None
_extractor: FactExtractor | None = None
_budget_manager: TokenBudgetManager | None = None
_llm: ChatGoogleGenerativeAI | None = None


def init_resources(
    short_term: ShortTermMemory,
    long_term: LongTermMemory,
    episodic: EpisodicMemory,
    semantic: SemanticMemory,
    router: MemoryRouter,
    extractor: FactExtractor,
    budget_manager: TokenBudgetManager,
    llm: ChatGoogleGenerativeAI,
) -> None:
    """Initialize shared resources for all nodes."""
    global _short_term, _long_term, _episodic, _semantic
    global _router, _extractor, _budget_manager, _llm
    _short_term = short_term
    _long_term = long_term
    _episodic = episodic
    _semantic = semantic
    _router = router
    _extractor = extractor
    _budget_manager = budget_manager
    _llm = llm


# ======================== NODE FUNCTIONS ========================


def classify_intent(state: MemoryState) -> dict[str, Any]:
    """Node 1: Classify user query intent."""
    query = state.get("current_query", "")
    intent = _router.classify_intent(query)
    logger.info("[classify_intent] query=%s → intent=%s", query[:50], intent)
    return {"intent": intent}


def retrieve_memory(state: MemoryState) -> dict[str, Any]:
    """Node 2: Retrieve relevant memories from backends based on intent."""
    intent = state.get("intent", "general")
    query = state.get("current_query", "")
    backends = _router.get_backends(intent)

    user_profile = {}
    episodes = []
    semantic_hits = []
    short_term_text = ""

    if "long_term" in backends:
        user_profile = _long_term.get_profile()

    if "episodic" in backends:
        episodes = _episodic.search_episodes(query, k=3)
        if not episodes:
            episodes = _episodic.get_recent(3)

    if "semantic" in backends:
        semantic_hits = _semantic.search(query, k=3)

    if "short_term" in backends:
        short_term_text = _short_term.format_for_prompt()

    logger.info(
        "[retrieve_memory] profile=%d facts, episodes=%d, semantic=%d hits",
        len(user_profile), len(episodes), len(semantic_hits),
    )

    return {
        "user_profile": user_profile,
        "episodes": episodes,
        "semantic_hits": semantic_hits,
        "short_term_text": short_term_text,
    }


def build_prompt(state: MemoryState) -> dict[str, Any]:
    """Node 3: Build prompt with memory sections, applying token budget."""
    # Format raw memory sections
    profile_text = _long_term.format_for_prompt()
    episodic_text = _episodic.format_for_prompt(state.get("episodes"))
    semantic_text = _semantic.format_for_prompt(state.get("semantic_hits"))
    short_term_text = state.get("short_term_text", "")

    # Apply token budget (4-level eviction)
    budget = state.get("memory_budget", 4000)
    _budget_manager.total_budget = budget
    trimmed = _budget_manager.allocate_budget(
        profile_text, episodic_text, semantic_text, short_term_text,
    )

    # Token usage report
    token_report = _budget_manager.get_usage_report(
        trimmed["profile"], trimmed["episodic"],
        trimmed["semantic"], trimmed["short_term"],
    )

    return {
        "trimmed_memory": trimmed,
        "token_report": token_report,
    }


def generate_response(state: MemoryState) -> dict[str, Any]:
    """Node 4: Generate LLM response with memory-injected prompt."""
    trimmed = state.get("trimmed_memory", {})

    system_prompt = build_system_prompt(
        profile_section=trimmed.get("profile", ""),
        episodic_section=trimmed.get("episodic", ""),
        semantic_section=trimmed.get("semantic", ""),
        short_term_section=trimmed.get("short_term", ""),
    )

    query = state.get("current_query", "")

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ]

    response = _llm.invoke(messages)
    response_text = response.content if hasattr(response, "content") else str(response)

    # Add to short-term memory
    _short_term.add_message("user", query)
    _short_term.add_message("assistant", response_text)

    logger.info("[generate_response] response length=%d chars", len(response_text))

    return {
        "response": response_text,
        "should_save": True,
    }


def extract_and_save(state: MemoryState) -> dict[str, Any]:
    """Node 5: Extract facts from conversation and save to memory backends."""
    query = state.get("current_query", "")
    response = state.get("response", "")

    conversation = f"User: {query}\nAssistant: {response}"
    extracted = _extractor.extract(conversation)

    # Save corrections first (conflict handling)
    for corr in extracted.get("corrections", []):
        change = _long_term.update_fact(corr["key"], corr["new_value"])
        if change.get("is_conflict"):
            # Log conflict to episodic
            _episodic.save_episode(
                summary=f"Profile correction: {corr['key']} changed from '{corr.get('old_value', '?')}' to '{corr['new_value']}'",
                context=conversation[:200],
                outcome="Profile updated (latest wins)",
                tags=["conflict_resolution", "profile_update"],
            )
        logger.info("[save] Correction: %s = %s", corr["key"], corr["new_value"])

    # Save new profile facts (high confidence only)
    for fact in extracted.get("profile_facts", []):
        if fact.get("confidence") in ("high", "medium"):
            _long_term.update_fact(fact["key"], fact["value"])
            logger.info("[save] Profile fact: %s = %s", fact["key"], fact["value"])

    # Save episode if significant
    episode_data = extracted.get("episode")
    if episode_data and episode_data.get("summary"):
        _episodic.save_episode(
            summary=episode_data["summary"],
            context=conversation[:300],
            outcome=episode_data.get("outcome", ""),
            tags=episode_data.get("tags", []),
        )
        logger.info("[save] Episode: %s", episode_data["summary"][:60])

    return {}


# ======================== NO-MEMORY AGENT ========================


def generate_no_memory_response(query: str, llm: ChatGoogleGenerativeAI) -> str:
    """Generate response WITHOUT any memory (for benchmark comparison)."""
    messages = [
        SystemMessage(content=NO_MEMORY_SYSTEM_PROMPT),
        HumanMessage(content=query),
    ]
    response = llm.invoke(messages)
    return response.content if hasattr(response, "content") else str(response)
