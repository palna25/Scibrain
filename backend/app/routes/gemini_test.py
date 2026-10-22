
from fastapi import APIRouter, HTTPException

from app.services.gemini import (
    GeminiConfigurationError,
    call_gemini_json,
)


router = APIRouter(
    prefix="/api/gemini-test",
    tags=["Gemini Test"],
)


@router.get("")
def gemini_diagnostic():
    schema = {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "definition": {"type": "string"},
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "topic",
            "definition",
            "key_points",
        ],
    }

    prompt = """
    Explain Retrieval-Augmented Generation.

    Return a concise definition and exactly three important
    key points.
    """

    try:
        response = call_gemini_json(prompt, schema)
    except GeminiConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return response
