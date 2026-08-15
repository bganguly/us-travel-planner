"""Topic guardrail — rejects questions outside the travel planning domain.

Runs as a before_agent_callback. Uses a dedicated lightweight Gemini call
as a classifier so the main agent never sees off-topic requests.
Returns a types.Content to short-circuit the agent, or None to let it proceed.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from google import genai
from google.genai import types

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext

_CLASSIFIER_MODEL = "gemini-2.0-flash-lite"

_ALLOWED_TOPICS = (
    "US travel planning, road trips, motorcycle routes, national parks, "
    "rental bikes, trip budgets, scenic highways, travel guidelines, "
    "Utah, Arizona, Zion, Bryce Canyon, Grand Canyon, or Route 66"
)

_REFUSAL_TEXT = (
    "I can only help with US travel planning — road trips, motorcycle routes, "
    "national parks, bike rentals, and trip budgets. "
    "I don't have information on that topic in this system."
)

_CLASSIFY_PROMPT = (
    "You are a strict topic classifier. Answer only YES or NO, nothing else.\n"
    "Is the following message related to {topics}?\n\n"
    "Message: {message}"
)


async def topic_guard_callback(callback_context: CallbackContext) -> types.Content | None:
    user_content = callback_context.user_content
    if not user_content or not user_content.parts:
        return None

    user_text = " ".join(
        part.text
        for part in user_content.parts
        if getattr(part, "text", None)
    ).strip()

    if not user_text:
        return None

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "bikram-java")
    client = genai.Client(vertexai=True, project=project, location="global")

    response = await client.aio.models.generate_content(
        model=_CLASSIFIER_MODEL,
        contents=_CLASSIFY_PROMPT.format(topics=_ALLOWED_TOPICS, message=user_text),
    )

    verdict = (response.text or "").strip().upper()
    if verdict.startswith("YES"):
        return None

    return types.Content(
        role="model",
        parts=[types.Part(text=_REFUSAL_TEXT)],
    )
