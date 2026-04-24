"""Main entry point: interactive multi-memory agent chat loop."""
from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from agent.graph import build_agent_graph, get_graph_mermaid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_interactive():
    """Run the agent in interactive chat mode."""
    print("=" * 60)
    print("  Multi-Memory Agent with LangGraph")
    print("  (Type 'quit' to exit, 'stats' for memory stats,")
    print("   'profile' to view profile, 'graph' for mermaid)")
    print("=" * 60)

    user_id = input("\nEnter your user ID (default: 'user1'): ").strip() or "user1"

    graph, backends = build_agent_graph(user_id=user_id)
    print(f"\nAgent ready for user '{user_id}'!")
    print(f"  Redis: {'connected' if backends['long_term']._connected else 'fallback mode'}")
    print(f"  ChromaDB: {backends['semantic'].collection.count()} docs loaded")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            print("Goodbye!")
            break

        if user_input.lower() == "stats":
            print("\n--- Memory Stats ---")
            for name, mem in backends.items():
                if name == "llm":
                    continue
                stats = mem.get_stats()
                print(f"  {name}: {stats}")
            continue

        if user_input.lower() == "profile":
            print("\n--- User Profile ---")
            profile = backends["long_term"].get_profile()
            if profile:
                for k, v in profile.items():
                    print(f"  {k}: {v}")
            else:
                print("  (empty)")
            continue

        if user_input.lower() == "graph":
            print("\n--- LangGraph Mermaid ---")
            print(get_graph_mermaid(graph))
            continue

        # Run agent
        try:
            initial_state = {
                "messages": [],
                "user_id": user_id,
                "current_query": user_input,
                "intent": "general",
                "user_profile": {},
                "episodes": [],
                "semantic_hits": [],
                "short_term_text": "",
                "memory_budget": 4000,
                "trimmed_memory": {},
                "should_save": False,
                "response": "",
                "token_report": {},
            }

            result = graph.invoke(initial_state)
            response = result.get("response", "No response generated.")
            token_report = result.get("token_report", {})

            print(f"\nAssistant: {response}")

            if token_report:
                print(f"\n  [tokens: {token_report.get('total_tokens', '?')}/{token_report.get('budget', '?')}"
                      f" | utilization: {token_report.get('utilization', '?')}]")

        except Exception as e:
            logger.error("Error: %s", e, exc_info=True)
            print(f"\n[Error] {e}")


if __name__ == "__main__":
    run_interactive()
