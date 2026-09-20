"""
Thin wrapper around Google's google-genai SDK.

Uses the new unified SDK (pip install google-genai / `from google import genai`).
Do NOT switch this to the old `google-generativeai` package -- Google
deprecated it on 30 Nov 2025 and it won't get new models.
"""
import json
import logging
import time

from google import genai
from google.genai import types

from . import config

logger = logging.getLogger("career_toolkit.gemini")

_client: genai.Client | None = None

_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY = 1.0
# Don't waste time/quota retrying things a retry can't fix.
_NON_RETRYABLE_HINTS = ("api key", "api_key_invalid", "permission_denied", "401", "invalid_argument")


class GenerationError(RuntimeError):
    """Raised when Gemini fails to return a usable response."""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise GenerationError(
                "GEMINI_API_KEY is not set. Get a key at https://aistudio.google.com/app/apikey "
                "and add it to your .env file."
            )
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _call_with_retry(make_request):
    """Retry a Gemini call up to _MAX_ATTEMPTS times with a short backoff,
    for transient hiccups (timeouts, momentary 5xx). Skips retrying things
    that look like a bad key or bad request, since trying again won't help."""
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return make_request()
        except Exception as exc:  # noqa: BLE001 -- the SDK can raise several internal error types
            last_exc = exc
            if any(hint in str(exc).lower() for hint in _NON_RETRYABLE_HINTS):
                break
            if attempt < _MAX_ATTEMPTS:
                logger.warning(
                    "Gemini call failed (attempt %d/%d), retrying: %s", attempt, _MAX_ATTEMPTS, exc
                )
                time.sleep(_RETRY_BASE_DELAY * attempt)
    logger.exception("Gemini call failed after retries", exc_info=last_exc)
    raise GenerationError(f"Gemini request failed: {last_exc}") from last_exc


def generate_json(system_instruction: str, user_prompt: str, temperature: float = 0.7) -> dict:
    """Call Gemini asking for a JSON response and parse it."""
    client = _get_client()
    response = _call_with_retry(lambda: client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    ))

    text = (response.text or "").strip()
    if not text:
        raise GenerationError("Gemini returned an empty response.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON output: %s", text[:500])
        raise GenerationError("The AI response wasn't valid JSON -- please try again.") from exc


def generate_text(system_instruction: str, user_prompt: str, temperature: float = 0.7) -> str:
    """Call Gemini and return plain text (used for the resume writer)."""
    client = _get_client()
    response = _call_with_retry(lambda: client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        ),
    ))

    text = (response.text or "").strip()
    if not text:
        raise GenerationError("Gemini returned an empty response.")
    return text
