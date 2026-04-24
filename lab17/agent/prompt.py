"""Prompt templates with explicit memory sections."""
from __future__ import annotations


SYSTEM_PROMPT_TEMPLATE = """You are an AI assistant with long-term memory capabilities.
You remember user preferences, past conversations, and can retrieve relevant knowledge.

Always respond in the same language the user uses.

== USER PROFILE ==
{profile_section}

== RELEVANT PAST EXPERIENCES ==
{episodic_section}

== KNOWLEDGE BASE ==
{semantic_section}

== RECENT CONVERSATION ==
{short_term_section}

Instructions:
- Use the memory sections above to provide personalized, context-aware responses.
- If you recall something about the user, mention it naturally.
- If you don't have information, say so honestly.
- When the user corrects a previous fact, acknowledge the correction.
"""


def build_system_prompt(
    profile_section: str = "",
    episodic_section: str = "",
    semantic_section: str = "",
    short_term_section: str = "",
) -> str:
    """Build the full system prompt with memory sections injected."""
    return SYSTEM_PROMPT_TEMPLATE.format(
        profile_section=profile_section or "No profile information available.",
        episodic_section=episodic_section or "No past experiences recorded.",
        semantic_section=semantic_section or "No relevant knowledge found.",
        short_term_section=short_term_section or "No recent conversation.",
    )


NO_MEMORY_SYSTEM_PROMPT = """You are an AI assistant. You have NO memory of previous conversations.
You do not know anything about the user. Respond based only on the current message.
Always respond in the same language the user uses."""
