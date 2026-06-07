"""
agent/cyborg.py — The Cyborg agent.

Provides two public interfaces:
  chat()        Synchronous, used as a fallback via asyncio.to_thread.
  chat_stream() Async generator — yields text chunks as they arrive from
                the model, handling tool calls inline without blocking.
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
from config import settings
from tools import TOOLS
from tools.functions import TOOL_REGISTRY

logger = logging.getLogger(__name__)


class Cyborg:
    """AI assistant that embodies Masoud Ahangary for website visitors."""

    def __init__(self) -> None:
        """Initialise sync + async LLM clients and load profile context."""

        # Sync client — used by the blocking chat() method.
        self.client = OpenAI(
            base_url=settings.base_url,
            api_key=settings.openai_api_key,
            timeout=settings.timeout,
        )

        # Async client — used by the streaming chat_stream() method.
        # Streaming needs a longer read timeout since tokens arrive gradually.
        self.async_client = AsyncOpenAI(
            base_url=settings.base_url,
            api_key=settings.openai_api_key,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

        self.name: str = "Masoud Ahangary"

        self._linkedin: str = self._load_linkedin(settings.linkedin_pdf)
        self._summary: str  = self._load_summary(settings.summary_txt)

    # ── Private loaders ───────────────────────────────────────────────────────

    @staticmethod
    def _load_linkedin(path: str) -> str:
        reader = PdfReader(path)
        return "".join(page.extract_text() or "" for page in reader.pages)

    @staticmethod
    def _load_summary(path: str) -> str:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    # ── Tool dispatch ─────────────────────────────────────────────────────────

    @staticmethod
    def _handle_tool_calls(tool_calls: list) -> list[dict]:
        """Execute each tool and return tool-role messages."""
        results: list[dict] = []
        for tool_call in tool_calls:
            tool_name: str = tool_call.function.name
            arguments: dict = json.loads(tool_call.function.arguments)
            logger.info("Tool called: %s", tool_name)
            tool_fn = TOOL_REGISTRY.get(tool_name)
            result: dict = tool_fn(**arguments) if tool_fn else {}
            results.append({
                "role": "tool",
                "content": json.dumps(result),
                "tool_call_id": tool_call.id,
            })
        return results

    # ── System prompt ─────────────────────────────────────────────────────────

    @property
    def system_prompt(self) -> str:
        return build_system_prompt(
            name=self.name,
            summary=self._summary,
            linkedin=self._linkedin,
        )

    # ── Sync chat (fallback) ──────────────────────────────────────────────────

    def chat(
        self,
        message: str,
        history: list[ChatCompletionMessageParam],
    ) -> str:
        """Blocking chat — kept as a fallback. Prefer chat_stream() for new code."""
        messages: list[ChatCompletionMessageParam] = (
            [{"role": "system", "content": self.system_prompt}]
            + history
            + [{"role": "user", "content": message}]
        )
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

    # ── Async streaming chat ──────────────────────────────────────────────────

    async def chat_stream(
        self,
        message: str,
        history: list[ChatCompletionMessageParam],
    ) -> AsyncGenerator[str, None]:
        """Yield text chunks as they arrive from the model.

        Tool calls are handled inline:
          1. Stream until the model either emits content or requests tool calls.
          2. If tool calls are requested, execute them silently.
          3. Loop back and stream the follow-up response.

        The caller sees a continuous stream of text chunks regardless of
        how many tool-call rounds happen internally.

        Args:
            message: The latest user message.
            history: Prior conversation turns.

        Yields:
            Raw text chunks from the model as they arrive.
        """
        messages: list = (
            [{"role": "system", "content": self.system_prompt}]
            + list(history)
            + [{"role": "user", "content": message}]
        )

        # Regex to detect text-based tool call artifacts some models emit
        # instead of proper API tool_calls, e.g.:
        #   <function=record_user_details>{"name": ...}</function>
        _TEXT_TOOL_RE = re.compile(
            r'<function=(\w+)>(.*?)(?:</function>|(?=<function=)|$)',
            re.DOTALL,
        )

        while True:
            # Accumulate tool-call deltas across chunks in this pass.
            pending: dict[int, dict] = {}
            finish_reason: str | None = None

            # Buffer accumulated text to detect text-based tool call artifacts
            text_buffer: str = ""

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

                        # If a text-based tool call artifact starts appearing,
                        # yield everything before it and then process/discard it.
                        if '<function=' in text_buffer:
                            safe_end = text_buffer.index('<function=')
                            safe_text = text_buffer[:safe_end].rstrip()
                            if safe_text:
                                yield safe_text

                            # Try to execute any complete tool calls found
                            for match in _TEXT_TOOL_RE.finditer(text_buffer[safe_end:]):
                                func_name = match.group(1)
                                try:
                                    args = json.loads(match.group(2))
                                    tool_fn = TOOL_REGISTRY.get(func_name)
                                    if tool_fn:
                                        tool_fn(**args)
                                        logger.info("Executed text-tool call: %s", func_name)
                                except Exception as exc:
                                    logger.warning("Text-tool call failed: %s", exc)

                            text_buffer = ""  # discard artifact, continue
                        else:
                            # Yield all but last 20 chars (guard against
                            # '<function=' spanning two chunks)
                            if len(text_buffer) > 20:
                                yield text_buffer[:-20]
                                text_buffer = text_buffer[-20:]

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in pending:
                                pending[idx] = {
                                    "id": "",
                                    "type": "function",
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
                raise RuntimeError(
                    "The model dropped the connection mid-stream. "
                ) from exc

            # Flush any remaining buffered text (no artifact detected)
            if text_buffer and '<function=' not in text_buffer:
                yield text_buffer.rstrip()

            # ── After stream ends ──────────────────────────────────────────
            if finish_reason == "tool_calls" and pending:
                tool_calls = [pending[i] for i in sorted(pending)]

                # Add assistant message with accumulated tool calls.
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls,
                })

                # Execute each tool and append results.
                for tc in tool_calls:
                    tool_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}

                    logger.info("Tool called (stream): %s", tool_name)
                    tool_fn = TOOL_REGISTRY.get(tool_name)
                    result = tool_fn(**args) if tool_fn else {}

                    messages.append({
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": tc["id"],
                    })

                # Loop back to stream the response after tool execution.
            else:
                # Normal finish or empty — we are done.
                break