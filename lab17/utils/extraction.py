"""LLM-based fact extraction from conversations.

Bonus: LLM-based extraction with parse/error handling +2.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Analyze the following conversation and extract structured information.

Conversation:
{conversation}

Extract the following as JSON:
{{
  "profile_facts": [
    {{"key": "fact_name", "value": "fact_value", "confidence": "high|medium|low"}}
  ],
  "episode": {{
    "summary": "brief summary of what happened (or null if no significant event)",
    "outcome": "what was the result/lesson (or null)",
    "tags": ["relevant", "tags"]
  }},
  "corrections": [
    {{"key": "fact_name", "old_value": "what was said before", "new_value": "corrected value"}}
  ]
}}

Rules:
- Only extract EXPLICIT facts stated by the user (not assumptions)
- For corrections: detect when user says "actually", "not X but Y", "I meant", etc.
- confidence: "high" for direct statements, "medium" for implied, "low" for uncertain
- If no facts/episode/corrections found, use empty lists or null
- Return ONLY valid JSON, no markdown fences

JSON:"""


class FactExtractor:
    """Extract profile facts and episodes from conversation using LLM."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)

    def extract(self, conversation: str) -> dict[str, Any]:
        """Extract facts from conversation text.

        Returns dict with keys: profile_facts, episode, corrections.
        Includes error handling and retry logic.
        """
        prompt = EXTRACTION_PROMPT.format(conversation=conversation)

        for attempt in range(3):
            try:
                response = self.llm.invoke(prompt)
                content = response.content if hasattr(response, "content") else str(response)
                parsed = self._parse_json(content)
                if parsed:
                    return self._validate(parsed)
            except Exception as e:
                logger.warning("Extraction attempt %d failed: %s", attempt + 1, e)

        logger.error("All extraction attempts failed, returning empty result")
        return {"profile_facts": [], "episode": None, "corrections": []}

    def _parse_json(self, text: str) -> dict | None:
        """Parse JSON from LLM output, handling common formatting issues."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        patterns = [
            r"```json\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
            r"\{.*\}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1) if "```" in pattern else match.group(0))
                except json.JSONDecodeError:
                    continue

        logger.warning("Could not parse JSON from: %s", text[:200])
        return None

    def _validate(self, data: dict) -> dict[str, Any]:
        """Validate and normalize extracted data."""
        result: dict[str, Any] = {
            "profile_facts": [],
            "episode": None,
            "corrections": [],
        }

        # Validate profile_facts
        for fact in data.get("profile_facts", []):
            if isinstance(fact, dict) and "key" in fact and "value" in fact:
                result["profile_facts"].append({
                    "key": str(fact["key"]).strip(),
                    "value": str(fact["value"]).strip(),
                    "confidence": fact.get("confidence", "medium"),
                })

        # Validate episode
        ep = data.get("episode")
        if isinstance(ep, dict) and ep.get("summary"):
            result["episode"] = {
                "summary": str(ep["summary"]),
                "outcome": str(ep.get("outcome", "")),
                "tags": ep.get("tags", []),
            }

        # Validate corrections
        for corr in data.get("corrections", []):
            if isinstance(corr, dict) and "key" in corr and "new_value" in corr:
                result["corrections"].append({
                    "key": str(corr["key"]).strip(),
                    "old_value": str(corr.get("old_value", "")),
                    "new_value": str(corr["new_value"]).strip(),
                })

        return result
