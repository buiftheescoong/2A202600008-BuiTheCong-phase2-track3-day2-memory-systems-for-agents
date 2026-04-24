"""Memory router: classify intent and map to memory backends."""
from __future__ import annotations

import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

INTENT_CLASSIFICATION_PROMPT = """Classify the user's intent into ONE of these categories:

- "preference_recall": User asks about their own preferences, profile, personal info
- "experience_recall": User references a past conversation, lesson learned, previous task
- "factual_query": User asks a factual/knowledge question that could be in a knowledge base
- "general": General conversation, greeting, or doesn't need specific memory

User message: {query}

Reply with ONLY the category name (one of: preference_recall, experience_recall, factual_query, general). Nothing else."""

# Map intents to which memory backends should be queried
INTENT_BACKEND_MAP: dict[str, list[str]] = {
    "preference_recall": ["long_term", "short_term"],
    "experience_recall": ["episodic", "short_term"],
    "factual_query": ["semantic", "short_term"],
    "general": ["long_term", "short_term"],  # lightweight: profile + recent
}

VALID_INTENTS = set(INTENT_BACKEND_MAP.keys())


class MemoryRouter:
    """Routes queries to appropriate memory backends based on intent."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)

    def classify_intent(self, query: str) -> str:
        """Classify user query intent using LLM."""
        try:
            prompt = INTENT_CLASSIFICATION_PROMPT.format(query=query)
            response = self.llm.invoke(prompt)
            content = response.content.strip().lower().strip('"').strip("'")

            if content in VALID_INTENTS:
                logger.info("Intent classified: %s", content)
                return content
            # Fuzzy match
            for intent in VALID_INTENTS:
                if intent in content:
                    return intent
        except Exception as e:
            logger.warning("Intent classification failed: %s", e)

        return "general"

    def get_backends(self, intent: str) -> list[str]:
        """Return list of backend names to query for given intent."""
        return INTENT_BACKEND_MAP.get(intent, INTENT_BACKEND_MAP["general"])
