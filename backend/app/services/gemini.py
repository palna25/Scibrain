
"""Shared Gemini service with lazy client initialization.

Importing this module does not require GEMINI_API_KEY.
The API key is checked only when a Gemini request is made.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from google import genai
from google.genai import types


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


class GeminiConfigurationError(RuntimeError):
    """Raised when Gemini is requested without valid configuration."""


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    """Create and reuse the Gemini client when first needed."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not configured. "
            "Set it in the backend environment before making Gemini requests."
        )

    return genai.Client(api_key=api_key)


def _get_model() -> str:
    """Read the model setting when a request is made."""
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or (
        DEFAULT_GEMINI_MODEL
    )


def call_gemini(prompt: str) -> str:
    """Generate a text response from Gemini."""
    response = _get_client().models.generate_content(
        model=_get_model(),
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
        ),
    )

    text = response.text
    if not text:
        raise RuntimeError("Gemini returned an empty response")

    return text


def call_gemini_json(
    prompt: str,
    response_schema: dict[str, Any],
) -> dict[str, Any]:
    """Generate and parse a JSON response conforming to the supplied schema."""
    response = _get_client().models.generate_content(
        model=_get_model(),
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )

    response_text = response.text
    if not response_text:
        raise RuntimeError("Gemini returned an empty response")

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Gemini returned invalid JSON"
        ) from exc

    if not isinstance(result, dict):
        raise RuntimeError(
            "Gemini returned JSON, but the top-level value was not an object"
        )

    return result
