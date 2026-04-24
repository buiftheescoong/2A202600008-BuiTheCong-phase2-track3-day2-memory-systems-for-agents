"""Evaluation logic for benchmark results."""
from __future__ import annotations

from typing import Any


def evaluate_response(response: str, expected_keyword: str | None) -> dict[str, Any]:
    """Evaluate if response contains expected keyword."""
    if expected_keyword is None:
        return {"pass": True, "reason": "No assertion (info turn)"}

    response_lower = response.lower()
    keyword_lower = expected_keyword.lower()

    passed = keyword_lower in response_lower

    return {
        "pass": passed,
        "expected": expected_keyword,
        "reason": "Keyword found" if passed else f"Missing '{expected_keyword}'",
    }


def compute_metrics(results: list[dict]) -> dict[str, Any]:
    """Compute aggregate benchmark metrics."""
    total_assertions = 0
    passed_assertions = 0
    total_tokens_with = 0
    total_tokens_without = 0

    group_results: dict[str, dict] = {}

    for r in results:
        group = r.get("group", "unknown")
        if group not in group_results:
            group_results[group] = {"pass": 0, "fail": 0}

        for turn in r.get("turn_results", []):
            if turn.get("expected") is not None:
                total_assertions += 1
                if turn.get("with_memory_pass"):
                    passed_assertions += 1
                    group_results[group]["pass"] += 1
                else:
                    group_results[group]["fail"] += 1

        total_tokens_with += r.get("total_tokens_with_memory", 0)
        total_tokens_without += r.get("total_tokens_without_memory", 0)

    return {
        "total_scenarios": len(results),
        "total_assertions": total_assertions,
        "passed_assertions": passed_assertions,
        "pass_rate": f"{passed_assertions/total_assertions:.0%}" if total_assertions else "N/A",
        "group_results": group_results,
        "total_tokens_with_memory": total_tokens_with,
        "total_tokens_without_memory": total_tokens_without,
        "memory_hit_rate": f"{passed_assertions/total_assertions:.0%}" if total_assertions else "N/A",
    }
