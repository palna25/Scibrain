from fastapi import APIRouter

from app.services.gemini import call_gemini_json


router = APIRouter(
    prefix="/api/gemini-test",
    tags=["Gemini Test"],
)


@router.get("")
def test_gemini():
    schema = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
            },
            "definition": {
                "type": "string",
            },
            "key_points": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
        },
        "required": [
            "topic",
            "definition",
            "key_points",
        ],
    }

    response = call_gemini_json(
        """
        Explain Retrieval-Augmented Generation.

        Return a concise definition and exactly three important
        key points.
        """,
        schema,
    )

    return response