"""
agent/cyborg.py — The Cyborg agent with RAG-powered context retrieval.

At startup, all profile documents are chunked and embedded into a FAISS
index. For each user message, the most relevant chunks are retrieved and
injected into the LLM context window — replacing the old approach of
dumping the full LinkedIn PDF into every prompt.
"""

import json
import logging
import re
from typing import AsyncGenerator

import httpx
from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageParam
from pypdf import PdfReader

from agent.prompts import build_system_prompt
from agent.rag import RAGIndex
from config import settings
from tools import TOOLS
from tools.functions import TOOL_REGISTRY

logger = logging.getLogger(__name__)


class Cyborg:
    """AI assistant that embodies Masoud Ahangary for website visitors."""

    def __init__(self) -> None:
        """Initialise LLM clients, load documents, and build the RAG index."""

        self.client = OpenAI(
            base_url=settings.base_url,
            api_key=settings.openai_api_key,
            timeout=settings.timeout,
        )

        self.async_client = AsyncOpenAI(
            base_url=settings.base_url,
            api_key=settings.openai_api_key,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

        self.name: str = "Masoud Ahangary"

        # Load raw text for RAG indexing
        linkedin_text = self._load_pdf(settings.linkedin_pdf)
        summary_text  = self._load_text(settings.summary_txt)

        # Keep formatted projects for the base system prompt
        self._projects: str = self._load_projects_formatted(settings.projects_json)

        # Build RAG index over all documents
        self._rag = RAGIndex()
        self._rag.build(
            linkedin_text=linkedin_text,
            summary_text=summary_text,
            cv_pdf_path=settings.cv_pdf,
            projects_json_path=settings.projects_json,
        )

    # ── Private loaders ────────────────────────────────────────────────────────

    @staticmethod
    def _load_pdf(path: str) -> str:
        try:
            reader = PdfReader(path)
            return "".join(page.extract_text() or "" for page in reader.pages)
        except FileNotFoundError:
            logger.warning("PDF not found: %s", path)
            return ""

    @staticmethod
    def _load_text(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except FileNotFoundError:
            logger.warning("Text file not found: %s", path)
            return ""

    @staticmethod
    def _load_projects_formatted(path: str) -> str:
        """Load projects.json and format as readable text for the system prompt."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                projects = json.load(fh)
            lines: list[str] = []
            for p in projects:
                lines.append(f"### {p.get('name', '')}")
                if p.get("description"):
                    lines.append(f"Description: {p['description']}")
                if p.get("tech"):
                    lines.append(f"Tech stack: {', '.join(p['tech'])}")
                if p.get("highlights"):
                    lines.append("Key highlights:")
                    lines.extend(f"  - {h}" for h in p["highlights"])
                if p.get("demo"):
                    lines.append(f"Live demo: {p['demo']}")
                if p.get("url") and not p.get("private", True):
                    lines.append(f"GitHub: {p['url']}")
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            logger.warning("Projects load error: %s", exc)
            return ""

    # ── Message building (RAG) ─────────────────────────────────────────────────

    def _build_messages(
        self,
        message: str,
        history: list,
    ) -> list:
        """Build the full message list with RAG-retrieved context.

        Retrieves the top-4 chunks most relevant to *message* from the
        FAISS index and injects them into the system prompt so the LLM
        has accurate, specific information to answer with.

        Args:
            message: The latest user message.
            history: Prior conversation turns.

        Returns:
            Full messages list ready to send to the LLM.
        """
        # Retrieve relevant chunks for this specific query
        chunks    = self._rag.retrieve(message, top_k=4)
        retrieved = "\n\n---\n\n".join(c.text for c in chunks) if chunks else ""

        if chunks:
            sources = ", ".join(set(c.source for c in chunks))
            logger.info("RAG: retrieved %d chunks from [%s]", len(chunks), sources)

        system = build_system_prompt(
            name=self.name,
            retrieved_context=retrieved,
            projects=self._projects,
        )

        return (
            [{"role": "system", "content": system}]
            + list(history)
            + [{"role": "user", "content": message}]
        )

    # ── Tool dispatch ──────────────────────────────────────────────────────────

    @staticmethod
    def _handle_tool_calls(tool_calls: list) -> list[dict]:
        results: list[dict] = []
        for tool_call in tool_calls:
            tool_name: str  = tool_call.function.name
            arguments: dict = json.loads(tool_call.function.arguments)
            logger.info("Tool called: %s", tool_name)
            tool_fn = TOOL_REGISTRY.get(tool_name)
            result  = tool_fn(**arguments) if tool_fn else {}
            results.append({
                "role":        "tool",
                "content":     json.dumps(result),
                "tool_call_id": tool_call.id,
            })
        return results

    # ── Sync chat (fallback) ───────────────────────────────────────────────────

    def chat(
        self,
        message: str,
        history: list[ChatCompletionMessageParam],
    ) -> str:
        """Blocking chat with RAG context. Used as streaming fallback."""
        messages = self._build_messages(message, history)
        while True:
            response = self.client.chat.completions.create(
                model=settings.model,
                messages=messages,
                tools=TOOLS,
            )
            if response.choices[0].finish_reason == "tool_calls":
                assistant_msg: ChatCompletionMessage = response.choices[0].message
                tool_results = self._handle_tool_calls(assistant_msg.tool_calls)
                messages.append(assistant_msg)
                messages.extend(tool_results)
            else:
                break
        return response.choices[0].message.content

    # ── Async streaming chat ───────────────────────────────────────────────────

    async def chat_stream(
        self,
        message: str,
        history: list[ChatCompletionMessageParam],
    ) -> AsyncGenerator[str, None]:
        """Yield text chunks as they arrive, with RAG context and tool handling."""

        messages = self._build_messages(message, history)

        # Text-based tool call artifact filter
        _TEXT_TOOL_RE = re.compile(
            r'<function=(\w+)>(.*?)(?:</function>|(?=<function=)|$)',
            re.DOTALL,
        )
        _TOOL_NAMES = {
            'record_user_details', 'record_unknown_question'
        }

        def _has_artifact(buf: str) -> bool:
            if '<function=' in buf:
                return True
            for name in _TOOL_NAMES:
                if f'{name}>' in buf or f'{name}(' in buf:
                    return True
            return False

        def _artifact_start(buf: str) -> int:
            positions = []
            if '<function=' in buf:
                positions.append(buf.index('<function='))
            for name in _TOOL_NAMES:
                if f'{name}>' in buf:
                    positions.append(buf.index(f'{name}>'))
                if f'{name}(' in buf:
                    positions.append(buf.index(f'{name}('))
            return min(positions) if positions else len(buf)

        while True:
            pending:       dict[int, dict] = {}
            finish_reason: str | None      = None
            text_buffer:   str             = ""

            stream = await self.async_client.chat.completions.create(
                model=settings.model,
                messages=messages,
                tools=TOOLS,
                stream=True,
            )

            try:
                async for chunk in stream:
                    if not chunk.choices:
                        continue

                    choice = chunk.choices[0]
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason

                    delta = choice.delta

                    if delta.content:
                        text_buffer += delta.content

                        if _has_artifact(text_buffer):
                            safe_end  = _artifact_start(text_buffer)
                            safe_text = text_buffer[:safe_end].rstrip()
                            if safe_text:
                                yield safe_text

                            for match in _TEXT_TOOL_RE.finditer(text_buffer[safe_end:]):
                                func_name = match.group(1)
                                try:
                                    args    = json.loads(match.group(2))
                                    tool_fn = TOOL_REGISTRY.get(func_name)
                                    if tool_fn:
                                        tool_fn(**args)
                                        logger.info("Executed text-tool call: %s", func_name)
                                except Exception as exc:
                                    logger.warning("Text-tool call failed: %s", exc)

                            text_buffer = ""
                        else:
                            if len(text_buffer) > 20:
                                yield text_buffer[:-20]
                                text_buffer = text_buffer[-20:]

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in pending:
                                pending[idx] = {
                                    "id": "", "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            buf = pending[idx]
                            if tc.id:
                                buf["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    buf["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    buf["function"]["arguments"] += tc.function.arguments

            except httpx.ReadError as exc:
                logger.warning("Stream dropped by upstream: %s", exc)
                raise RuntimeError("The model dropped the connection mid-stream.") from exc

            # Flush remaining buffer
            if text_buffer and not _has_artifact(text_buffer):
                yield text_buffer.rstrip()

            # Handle tool calls
            if finish_reason == "tool_calls" and pending:
                tool_calls = [pending[i] for i in sorted(pending)]
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls,
                })
                for tc in tool_calls:
                    tool_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    logger.info("Tool called (stream): %s", tool_name)
                    tool_fn = TOOL_REGISTRY.get(tool_name)
                    result  = tool_fn(**args) if tool_fn else {}
                    messages.append({
                        "role":        "tool",
                        "content":     json.dumps(result),
                        "tool_call_id": tc["id"],
                    })
            else:
                break