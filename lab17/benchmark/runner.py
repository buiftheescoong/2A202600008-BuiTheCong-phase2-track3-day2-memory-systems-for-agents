"""Benchmark runner: compare no-memory vs with-memory agent on 10 conversations."""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from langchain_google_genai import ChatGoogleGenerativeAI

from agent.graph import build_agent_graph
from agent.nodes import generate_no_memory_response
from benchmark.conversations import SCENARIOS
from benchmark.evaluate import evaluate_response, compute_metrics
from utils.token_budget import TokenBudgetManager

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))


def run_scenario_with_memory(scenario: dict, graph, backends) -> list[dict]:
    """Run a single scenario with memory agent."""
    # Setup pre-existing episodes if needed
    if "setup_episodes" in scenario:
        for ep in scenario["setup_episodes"]:
            backends["episodic"].save_episode(**ep)

    turn_results = []
    for user_msg, expected in scenario["turns"]:
        state = {
            "messages": [],
            "user_id": "benchmark_user",
            "current_query": user_msg,
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

        try:
            result = graph.invoke(state)
            response = result.get("response", "")
            token_report = result.get("token_report", {})
        except Exception as e:
            response = f"[ERROR] {e}"
            token_report = {}

        eval_result = evaluate_response(response, expected)

        turn_results.append({
            "user": user_msg,
            "expected": expected,
            "with_memory_response": response,
            "with_memory_pass": eval_result["pass"],
            "tokens_used": token_report.get("total_tokens", 0),
        })

    return turn_results


def run_scenario_no_memory(scenario: dict, llm) -> list[dict]:
    """Run a single scenario without memory."""
    turn_results = []
    for user_msg, expected in scenario["turns"]:
        try:
            response = generate_no_memory_response(user_msg, llm)
        except Exception as e:
            response = f"[ERROR] {e}"

        eval_result = evaluate_response(response, expected)

        turn_results.append({
            "user": user_msg,
            "expected": expected,
            "no_memory_response": response,
            "no_memory_pass": eval_result["pass"],
        })

    return turn_results


def generate_benchmark_md(all_results: list[dict], metrics: dict) -> str:
    """Generate BENCHMARK.md content."""
    lines = [
        "# Benchmark Report: Multi-Memory Agent vs No-Memory Agent",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Model:** Google Gemini 2.5 Flash",
        f"**Scenarios:** {metrics['total_scenarios']}",
        f"**Overall Pass Rate (with memory):** {metrics['pass_rate']}",
        "",
        "---",
        "",
        "## Summary Table",
        "",
        "| # | Scenario | Group | No-memory result | With-memory result | Pass? |",
        "|---|----------|-------|------------------|---------------------|-------|",
    ]

    for r in all_results:
        # Find the assertion turn (last turn with expected keyword)
        assertion_turn_no = None
        assertion_turn_with = None
        for t_no, t_with in zip(r["no_memory_turns"], r["with_memory_turns"]):
            if t_no.get("expected") is not None:
                assertion_turn_no = t_no
                assertion_turn_with = t_with

        if assertion_turn_no and assertion_turn_with:
            no_mem = assertion_turn_no["no_memory_response"][:150].replace("|", "\\|").replace("\n", " ")
            with_mem = assertion_turn_with["with_memory_response"][:150].replace("|", "\\|").replace("\n", " ")
            passed = "Pass" if assertion_turn_with["with_memory_pass"] else "Fail"
            lines.append(
                f"| {r['id']} | {r['name']} | {r['group']} | {no_mem} | {with_mem} | {passed} |"
            )

    lines += [
        "",
        "---",
        "",
        "## Detailed Results",
        "",
    ]

    for r in all_results:
        lines.append(f"### Scenario {r['id']}: {r['name']}")
        lines.append(f"**Group:** {r['group']} | **Turns:** {len(r['with_memory_turns'])}")
        lines.append("")

        for i, (t_no, t_with) in enumerate(zip(r["no_memory_turns"], r["with_memory_turns"])):
            expected = t_no.get("expected", None)
            user_msg = t_no["user"]

            if t_with.get("expected") is not None:
                passed = "PASS" if t_with["with_memory_pass"] else "FAIL"
            else:
                passed = None

            lines.append(f"**Turn {i+1}:** {user_msg}")
            if expected:
                lines.append(f"- **Expected keyword:** `{expected}` {'-> ' + passed if passed else ''}")
            lines.append(f"- **No-memory:** {t_no['no_memory_response']}")
            lines.append(f"- **With-memory:** {t_with['with_memory_response']}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Metrics
    lines += [
        "---",
        "",
        "## Metrics",
        "",
        f"- **Total Assertions:** {metrics['total_assertions']}",
        f"- **Passed:** {metrics['passed_assertions']}",
        f"- **Pass Rate:** {metrics['pass_rate']}",
        f"- **Memory Hit Rate:** {metrics['memory_hit_rate']}",
        f"- **Total Tokens (with memory):** {metrics['total_tokens_with_memory']}",
        f"- **Total Tokens (without memory):** {metrics['total_tokens_without_memory']}",
        "",
        "### Group Breakdown",
        "",
        "| Group | Pass | Fail |",
        "|-------|------|------|",
    ]

    for group, counts in metrics.get("group_results", {}).items():
        lines.append(f"| {group} | {counts['pass']} | {counts['fail']} |")

    # Token Budget Breakdown
    lines += [
        "",
        "---",
        "",
        "## Token Budget Analysis",
        "",
        "The agent uses a 4-level priority eviction system:",
        "1. **Short-term** (highest priority) - never trimmed, keeps conversation coherence",
        "2. **Long-term profile** - trimmed to 40% of remaining budget",
        "3. **Episodic** - trimmed to 50% of remaining budget",
        "4. **Semantic** (lowest priority) - gets whatever is left",
        "",
        "Token counting uses `tiktoken` (cl100k_base encoding) for accurate counting.",
        "",
    ]

    # Reflection
    lines += [
        "---",
        "",
        "## Reflection: Privacy & Limitations",
        "",
        "### Privacy Risks",
        "",
        "1. **Long-term Profile (Redis)** - **HIGHEST RISK**: Stores PII directly (name, allergies, ",
        "   preferences). If Redis is compromised, all user profiles are exposed.",
        "   - **Mitigation:** Encrypt at-rest, require auth, implement TTL for inactive users.",
        "",
        "2. **Episodic Memory (JSON)** - **MEDIUM RISK**: Contains conversation summaries that may ",
        "   include sensitive context (health issues, work details).",
        "   - **Mitigation:** Implement data retention policy (TTL), anonymize before storage.",
        "",
        "3. **Semantic Memory (ChromaDB)** - **LOW RISK**: Stores general knowledge docs, not user PII.",
        "   But if user conversations are indexed, risk increases.",
        "",
        "4. **Short-term Memory** - **LOW RISK**: In-memory only, cleared on restart. But contains ",
        "   raw conversation which may have PII during session.",
        "",
        "### Which memory is most helpful?",
        "",
        "**Long-term profile** provides the biggest improvement: remembering user name, preferences, ",
        "and allergies directly impacts personalization quality. Without it, every conversation starts ",
        "from zero.",
        "",
        "### Which memory is riskiest if retrieved incorrectly?",
        "",
        "**Long-term profile** - retrieving wrong allergy info could lead to harmful recommendations ",
        "(e.g., suggesting food with allergens). **Episodic memory** - retrieving wrong past context ",
        "could confuse the user or provide incorrect advice.",
        "",
        "### Deletion Strategy",
        "",
        "If a user requests memory deletion (GDPR right to be forgotten):",
        "- **Redis:** `DEL user:{id}:profile user:{id}:changelog`",
        "- **Episodic JSON:** Filter and rewrite episodes.json removing user entries",
        "- **ChromaDB:** Delete user-specific documents from collection",
        "- **Short-term:** Already ephemeral, cleared on session end",
        "",
        "### User Consent",
        "",
        "Current implementation **lacks explicit consent mechanism**. Production system needs:",
        "- Opt-in/opt-out for each memory type",
        "- Transparency about what is stored",
        "- Easy access to view/delete stored data",
        "",
        "### Technical Limitations",
        "",
        "1. **Conflict detection depends on LLM** - extraction prompt may miss corrections or ",
        "   misinterpret them, especially in ambiguous language.",
        "2. **Keyword-based episodic search** - simple keyword matching is brittle; would benefit ",
        "   from embedding-based search like semantic memory.",
        "3. **No cross-session short-term** - sliding window resets on restart, losing recent context.",
        "4. **Scale issues:** Single Redis instance, single ChromaDB. Would need sharding/clustering ",
        "   for multi-user production deployment.",
        "5. **Token budget is heuristic** - the 40/50/remaining split is not optimized per query type.",
        "6. **No memory importance scoring** - all facts treated equally; a production system should ",
        "   weight facts by relevance and recency.",
        "",
    ]

    return "\n".join(lines)


def main():
    """Run full benchmark."""
    print("=" * 60)
    print("  Benchmark: No-Memory vs With-Memory Agent")
    print("=" * 60)

    # Build with-memory agent
    print("\n[1/3] Building with-memory agent...")
    graph, backends = build_agent_graph(user_id="benchmark_user")

    # No-memory LLM
    no_memory_llm = backends["llm"]

    all_results = []

    print(f"\n[2/3] Running {len(SCENARIOS)} scenarios...")
    for i, scenario in enumerate(SCENARIOS):
        print(f"\n  Scenario {scenario['id']}: {scenario['name']}...")

        # Clear memory between scenarios (fresh state per scenario)
        backends["short_term"].clear()
        backends["long_term"].clear()
        backends["episodic"].clear()

        # Run with memory
        with_turns = run_scenario_with_memory(scenario, graph, backends)

        # Clear again for no-memory run
        backends["short_term"].clear()
        backends["long_term"].clear()
        backends["episodic"].clear()

        # Run without memory
        no_turns = run_scenario_no_memory(scenario, no_memory_llm)

        total_tokens = sum(t.get("tokens_used", 0) for t in with_turns)

        all_results.append({
            "id": scenario["id"],
            "name": scenario["name"],
            "group": scenario["group"],
            "with_memory_turns": with_turns,
            "no_memory_turns": no_turns,
            "total_tokens_with_memory": total_tokens,
            "total_tokens_without_memory": 0,
            "turn_results": [
                {
                    "expected": t.get("expected"),
                    "with_memory_pass": t.get("with_memory_pass", True),
                    "group": scenario["group"],
                }
                for t in with_turns
            ],
        })

        # Print quick result
        assertion_turns = [t for t in with_turns if t.get("expected")]
        if assertion_turns:
            t = assertion_turns[-1]
            status = "PASS" if t["with_memory_pass"] else "FAIL"
            print(f"    {status} (expected: {t['expected']})")

    # Compute metrics
    metrics = compute_metrics(all_results)

    # Generate BENCHMARK.md
    print("\n[3/3] Generating BENCHMARK.md...")
    md_content = generate_benchmark_md(all_results, metrics)
    benchmark_path = os.path.join(PROJECT_ROOT, "BENCHMARK.md")
    with open(benchmark_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"\n{'=' * 60}")
    print(f"  Results: {metrics['passed_assertions']}/{metrics['total_assertions']} passed ({metrics['pass_rate']})")
    print(f"  Report: {benchmark_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
