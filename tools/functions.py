"""
tools/functions.py — Python callables that back each LLM tool.

These functions are invoked by the agent when the model emits a tool-call.
Each one triggers a Pushover notification so the owner is alerted in real time.

To add a new tool:
  1. Define the function here and add it to ``TOOL_REGISTRY``.
  2. Add its JSON schema to ``schemas.py``.
  3. Add it to ``TOOLS`` in ``__init__.py``.
"""

import json
import os

from notifications import push


def record_user_details(
    email: str,
    name: str = "Not provided",
    notes: str = "Not provided",
) -> dict[str, str]:
    """Record a visitor's contact details and notify the owner."""
    push(f"Recording {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}


def record_unknown_question(question: str) -> dict[str, str]:
    """Record a question the assistant was unable to answer."""
    push(f"Recording unknown question: {question}")
    return {"recorded": "ok"}


def search_projects(query: str) -> dict:
    """Search the owner's projects JSON and return matching entries.

    Performs a case-insensitive keyword search across project name,
    description, tech stack, and highlights. Returns up to 3 most
    relevant matches so the LLM can give a detailed, accurate answer.

    Args:
        query: The search term or topic the visitor asked about
               (e.g. "machine learning", "VRP", "Python", "routing").

    Returns:
        A dict with a ``results`` list of matching project objects,
        or a ``message`` key if nothing was found.
    """
    projects_path = os.path.join(
        os.path.dirname(__file__), "..", "profile", "projects.json"
    )

    try:
        with open(projects_path, "r", encoding="utf-8") as f:
            projects = json.load(f)
    except FileNotFoundError:
        return {"message": "Projects file not found."}
    except json.JSONDecodeError:
        return {"message": "Projects file is malformed."}

    keywords = [kw.strip().lower() for kw in query.split() if kw.strip()]

    def score(project: dict) -> int:
        """Score a project by how many query keywords it matches."""
        searchable = " ".join([
            project.get("name", ""),
            project.get("description", ""),
            " ".join(project.get("tech", [])),
            " ".join(project.get("highlights", [])),
        ]).lower()
        return sum(1 for kw in keywords if kw in searchable)

    scored = [(score(p), p) for p in projects]
    matches = [p for s, p in sorted(scored, key=lambda x: -x[0]) if s > 0]

    if not matches:
        return {
            "message": (
                f"No projects found matching '{query}'. "
                "You can mention that the owner has projects in "
                "logistics optimisation, AI agents, and full-stack development."
            )
        }

    # Return top 3 matches, stripping the GitHub URL for private repos
    results = []
    for p in matches[:3]:
        entry = {
            "name":        p.get("name", ""),
            "description": p.get("description", ""),
            "tech":        p.get("tech", []),
            "highlights":  p.get("highlights", []),
            "demo":        p.get("demo", ""),
        }
        # Only expose the URL for public repos
        if not p.get("private", True):
            entry["url"] = p.get("url", "")
        results.append(entry)

    return {"results": results}


# Dispatch table — maps each tool name to its Python callable.
TOOL_REGISTRY: dict[str, callable] = {
    record_user_details.__name__:  record_user_details,
    record_unknown_question.__name__: record_unknown_question,
    search_projects.__name__:      search_projects,
}