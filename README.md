---
title: Talk With Me
emoji: 💼
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Talk With Me

A personal AI assistant that represents Masoud Ahangary on his website.
Ask it anything about his background, experience, skills, or projects.

## Tech stack

| Layer      | Technology                          |
|------------|-------------------------------------|
| Backend    | FastAPI + Python 3.12               |
| LLM        | OpenRouter (configurable model)     |
| Frontend   | Vanilla HTML / CSS / JS             |
| Deployment | HuggingFace Spaces — Docker SDK     |

## Project structure

```
talk_with_me/
├── app.py               # FastAPI entry point
├── config.py            # Settings (env vars)
├── notifications.py     # Pushover notifications
├── profile_meta.py      # Edit this to update sidebar display data
├── Dockerfile
├── agent/
│   ├── cyborg.py        # Cyborg agent + chat loop
│   └── prompts.py       # System prompt builder
├── tools/
│   ├── functions.py     # Tool callables + TOOL_REGISTRY
│   └── schemas.py       # OpenAI JSON schemas
├── api/
│   ├── models.py        # Pydantic request/response models
│   └── routes.py        # /api/chat  /api/profile
└── frontend/
    ├── index.html
    ├── css/styles.css
    └── js/chat.js
```

## Environment variables

Set these as **Secrets** in your HuggingFace Space settings
(Settings → Repository secrets):

| Variable         | Required | Description                        |
|------------------|----------|------------------------------------|
| `OPENAI_API_KEY` | ✅       | Your OpenRouter API key            |
| `PUSHOVER_TOKEN` | optional | Pushover app token for alerts      |
| `PUSHOVER_USER`  | optional | Pushover user key                  |

## Running locally

```bash
# Install dependencies
uv sync

# Start the dev server (auto-reload)
uv run uvicorn app:app --reload --port 8000
```

Then open `http://localhost:8000`.

## Deploying to HuggingFace Spaces

1. Create a new Space → choose **Docker** as the SDK.
2. Push this repository to the Space.
3. Add the environment variable secrets listed above.
4. The Space builds and starts automatically on port 7860.

## Customising the profile

Edit `profile_meta.py` — change name, title, skills, social links,
and availability status. No other file needs to change.

Edit `profile/summary.txt` and replace `profile/linkedin.pdf` to update
the context the LLM uses when answering questions.
