"""
tools/schemas.py — OpenAI function-calling JSON schemas.

Each schema mirrors the signature of its corresponding function in
``tools.functions`` and is sent to the model so it knows when and how
to invoke the tool.
"""

from tools.functions import record_unknown_question, record_user_details

record_user_details_schema: dict = {
    "name": record_user_details.__name__,
    "description": (
        "Use this tool to record that a user is interested in being in touch "
        "and has provided an email address."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user",
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it",
            },
            "notes": {
                "type": "string",
                "description": (
                    "Any additional information from the conversation "
                    "worth preserving for context"
                ),
            },
        },
        "required": ["email"],
        "additionalProperties": False,
    },
}

record_unknown_question_schema: dict = {
    "name": record_unknown_question.__name__,
    "description": (
        "Always use this tool to record any question that couldn't be answered, "
        "even for trivial or off-topic questions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that could not be answered",
            },
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}