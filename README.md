---
title: Talk With Me
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: true
tags:
  - chatbot
  - rag
  - portfolio
  - fastapi
  - llm
  - groq
  - faiss
---

# Talk With Me — Personal AI Assistant

> A personal AI chatbot that answers questions about **Masoud Ahangary's** background, experience, projects, and skills — powered by RAG over his CV, LinkedIn profile, and project portfolio.

**[🚀 Live Demo](https://cyborgmass-talk-with-me.hf.space)** · **[📂 Portfolio](https://cyborgmass-talk-with-me.hf.space/projects.html)** · **[💻 GitHub](https://github.com/cyborg1367/talk-with-me)**

![Talk With Me screenshot](https://i.postimg.cc/HsRyGkrj/screenshot.png)

---

## What it does

Enter your name and start chatting. The assistant answers questions about:
- Work experience and background
- Projects (VRP scheduling, genetic algorithms, AI systems)
- Skills and tech stack
- How to get in touch

The bot only answers from verified profile documents — it won't hallucinate facts or invent durations.

---

## How it works

```
User question
     ↓
Embed question with all-MiniLM-L6-v2
     ↓
Retrieve top-4 relevant chunks from FAISS index
(built over CV PDF + LinkedIn PDF + summary + projects JSON)
     ↓
Inject retrieved context into system prompt
     ↓
Stream response from Llama 3.3 70B via Groq
     ↓
Render markdown with streaming cursor in the browser
```

---

## Tech stack

| Layer       | Technology                                      |
|-------------|-------------------------------------------------|
| Backend     | FastAPI + Python 3.12                           |
| LLM         | Llama 3.3 70B via Groq (streaming SSE)          |
| RAG         | FAISS + sentence-transformers (all-MiniLM-L6-v2)|
| Frontend    | Vanilla HTML / CSS / JS — no framework          |
| Deployment  | HuggingFace Spaces — Docker SDK                 |
| CI/CD       | GitHub Actions → auto-deploy to HF on push      |

---

## Project structure

```
talk_with_me/
├── app.py                  # FastAPI entry point
├── config.py               # Settings (env vars)
├── profile_meta.py         # Sidebar: name, title, skills, links
├── notifications.py        # Pushover push notifications
│
├── agent/
│   ├── cyborg.py           # AI agent — chat() + chat_stream()
│   ├── prompts.py          # System prompt builder
│   └── rag.py              # FAISS index — chunking, embedding, retrieval
│
├── api/
│   ├── models.py           # Pydantic request/response models
│   └── routes.py           # /api/chat/stream  /api/profile  /api/projects
│
├── tools/
│   ├── functions.py        # Tool callables + TOOL_REGISTRY
│   └── schemas.py          # OpenAI-format tool JSON schemas
│
├── profile/
│   ├── linkedin.pdf        # LinkedIn export (RAG source)
│   ├── summary.txt         # Career summary (RAG source)
│   ├── cv.pdf              # CV/resume (RAG source, optional)
│   └── projects.json       # Portfolio projects (RAG + showcase page)
│
└── frontend/
    ├── index.html          # Chat page
    ├── projects.html       # Portfolio showcase page
    ├── css/
    │   ├── styles.css      # Main stylesheet
    │   └── projects.css    # Portfolio page styles
    └── js/
        ├── chat.js         # Chat page logic
        └── projects.js     # Portfolio page logic
```

---

## Running locally

```bash
# Clone the repo
git clone https://github.com/cyborg1367/talk-with-me.git
cd talk-with-me

# Install dependencies (requires uv)
uv sync

# Set environment variables
cp .env.example .env   # then fill in your keys

# Start the dev server
uv run uvicorn app:app --reload --port 8000
```

Open `http://localhost:8000`.

---

## Environment variables

Set these as **Secrets** in HuggingFace Space settings → Variables and Secrets:

| Variable         | Required | Description                          |
|------------------|----------|--------------------------------------|
| `OPENAI_API_KEY` | ✅        | Your Groq API key (free at groq.com) |
| `PUSHOVER_TOKEN` | optional | Pushover app token for notifications |
| `PUSHOVER_USER`  | optional | Pushover user key for notifications  |

---

## Deploying your own version

1. Fork this repo
2. Create a new HuggingFace Space → Docker SDK
3. Replace `profile/` documents with your own CV, LinkedIn PDF, and summary
4. Edit `profile_meta.py` with your name, title, skills, and links
5. Edit `profile/projects.json` with your projects
6. Add `OPENAI_API_KEY` (Groq key) as a Space secret
7. Push — the Space builds and deploys automatically

---

## Features

- ✅ Streaming SSE responses with real-time token rendering
- ✅ RAG over CV, LinkedIn, summary, and projects — no hallucinated facts
- ✅ Portfolio showcase page at `/projects.html`
- ✅ Dark mode (persists across sessions)
- ✅ Email CTA after 3 bot responses
- ✅ Markdown rendering in bot bubbles
- ✅ Responsive — works on mobile
- ✅ GitHub Actions CI/CD pipeline

---

## Built by

**Masoud Ahangary** — ML Engineer & Data Scientist  
[LinkedIn](https://linkedin.com/in/masoud-ahangary) · [GitHub](https://github.com/cyborg1367) · [HuggingFace](https://huggingface.co/cyborgmass)