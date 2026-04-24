"""LangGraph graph definition for the multi-memory agent.

Bonus: Graph flow demo +2.
"""
from __future__ import annotations

import os
import logging

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI

from .state import MemoryState
from .nodes import (
    classify_intent,
    retrieve_memory,
    build_prompt,
    generate_response,
    extract_and_save,
    init_resources,
)
from .router import MemoryRouter
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from utils.token_budget import TokenBudgetManager
from utils.extraction import FactExtractor

logger = logging.getLogger(__name__)

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def should_save(state: MemoryState) -> str:
    """Conditional edge: decide whether to save memory after response."""
    if state.get("should_save", False):
        return "save"
    return "end"


def build_agent_graph(
    user_id: str = "default",
    redis_url: str | None = None,
    memory_budget: int = 4000,
    model_name: str = "gemini-2.5-flash",
) -> tuple:
    """Build and compile the LangGraph agent.

    Returns (compiled_graph, memory_backends_dict) so caller can inspect state.
    """
    # ---- Initialize all backends ----
    short_term = ShortTermMemory(max_messages=20, max_tokens=2000)
    long_term = LongTermMemory(
        redis_url=redis_url or os.getenv("REDIS_URL", "redis://localhost:6379"),
        user_id=user_id,
    )
    episodic = EpisodicMemory()
    semantic = SemanticMemory()

    # Load FAQ docs into semantic memory
    faq_path = os.path.join(DATA_DIR, "faq_docs.txt")
    if os.path.exists(faq_path) and semantic.collection.count() == 0:
        semantic.load_from_file(faq_path)
        logger.info("Loaded FAQ docs into semantic memory")

    # ---- Initialize shared resources ----
    router = MemoryRouter(model_name=model_name)
    extractor = FactExtractor(model_name=model_name)
    budget_manager = TokenBudgetManager(total_budget=memory_budget)
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.3)

    init_resources(
        short_term=short_term,
        long_term=long_term,
        episodic=episodic,
        semantic=semantic,
        router=router,
        extractor=extractor,
        budget_manager=budget_manager,
        llm=llm,
    )

    # ---- Build LangGraph ----
    workflow = StateGraph(MemoryState)

    # Add nodes
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("retrieve_memory", retrieve_memory)
    workflow.add_node("build_prompt", build_prompt)
    workflow.add_node("generate_response", generate_response)
    workflow.add_node("extract_and_save", extract_and_save)

    # Define edges
    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "retrieve_memory")
    workflow.add_edge("retrieve_memory", "build_prompt")
    workflow.add_edge("build_prompt", "generate_response")

    # Conditional: save or end
    workflow.add_conditional_edges(
        "generate_response",
        should_save,
        {"save": "extract_and_save", "end": END},
    )
    workflow.add_edge("extract_and_save", END)

    # Compile
    graph = workflow.compile()

    backends = {
        "short_term": short_term,
        "long_term": long_term,
        "episodic": episodic,
        "semantic": semantic,
        "llm": llm,
    }

    logger.info("Agent graph compiled successfully")
    return graph, backends


def get_graph_mermaid(graph) -> str:
    """Export graph as Mermaid diagram string (bonus: graph flow demo)."""
    try:
        return graph.get_graph().draw_mermaid()
    except Exception:
        # Fallback manual mermaid
        return """graph TD
    __start__ --> classify_intent
    classify_intent --> retrieve_memory
    retrieve_memory --> build_prompt
    build_prompt --> generate_response
    generate_response -->|should_save=True| extract_and_save
    generate_response -->|should_save=False| __end__
    extract_and_save --> __end__"""
