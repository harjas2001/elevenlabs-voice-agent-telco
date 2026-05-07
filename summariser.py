"""
summariser.py
Post-call AI summary module for elevenlabs-voice-agent-starter.

On session end, sends the conversation transcript to Claude and returns
a structured summary card rendered in the analytics dashboard.

Requires: ANTHROPIC_API_KEY in environment.
"""

import json
import logging
import os

from anthropic import Anthropic

logger = logging.getLogger(__name__)

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "[summariser] ANTHROPIC_API_KEY not set. "
                "Add it to your .env file to enable post-call summaries."
            )
        _client = Anthropic(api_key=api_key)
    return _client


_SYSTEM_PROMPT = """You are a post-call quality analyst for a voice AI customer service agent.
You receive a conversation transcript and return a structured JSON summary.

Return ONLY valid JSON with these exact keys — no preamble, no markdown, no explanation:
{
  "issue": "One sentence — what the customer contacted about",
  "outcome": "One sentence — how it resolved (e.g. Resolved, Escalated, Abandoned)",
  "sentiment": "positive | neutral | negative",
  "escalated": true | false,
  "recommended_followup": "One sentence action item, or null if none required"
}"""


def summarise_session(transcript: str, escalated: bool = False) -> dict:
    """
    Generate a structured post-call summary card via Claude.

    Args:
        transcript: Full conversation transcript as a plain string.
        escalated:  Whether the session was flagged via deterministic
                    phrase detection in main.py. Passed to Claude as
                    additional context and used to normalise the output.

    Returns:
        Dict with keys: issue, outcome, sentiment, escalated,
        recommended_followup. Returns a safe fallback dict on any error
        so the dashboard never breaks.
    """
    if not transcript or not transcript.strip():
        return _fallback(escalated, reason="empty transcript")

    user_message = (
        f"Live escalation flag: {escalated}\n\n"
        f"Transcript:\n{transcript.strip()}"
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        # logger.warning(f"[summariser] Raw response from Claude: {raw}")
        summary = json.loads(raw)

        # Normalise: if live detection flagged escalation, respect it
        # regardless of what Claude inferred from the transcript.
        summary["escalated"] = escalated or bool(summary.get("escalated", False))
        return summary

    except json.JSONDecodeError:
        logger.warning("[summariser] Claude returned non-JSON response — using fallback.")
        return _fallback(escalated, reason="json_parse_error")
    except Exception as exc:
        logger.error(f"[summariser] API call failed: {exc}")
        return _fallback(escalated, reason=str(exc))


def _fallback(escalated: bool, reason: str = "") -> dict:
    """Safe fallback returned on any summariser failure."""
    return {
        "issue": "Summary unavailable",
        "outcome": "Escalated" if escalated else "Completed",
        "sentiment": "neutral",
        "escalated": escalated,
        "recommended_followup": None,
        "_error": reason,
    }