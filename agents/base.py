from __future__ import annotations

import logging
from typing import Any

import anthropic

import config
from tools.registry import ToolRegistry
from workspace.shared import SharedWorkspace

logger = logging.getLogger(__name__)


class Agent:
    role: str = "base"
    system_prompt: str = "You are a helpful assistant."
    tool_names: list[str] = []
    model: str = ""
    max_tokens: int = 0
    max_iterations: int = 15

    def __init__(
        self,
        tool_registry: ToolRegistry,
        workspace: SharedWorkspace,
    ) -> None:
        self._registry = tool_registry
        self._workspace = workspace
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def _effective_model(self) -> str:
        return self.model or config.DEFAULT_MODEL

    def _effective_max_tokens(self) -> int:
        return self.max_tokens or config.MAX_TOKENS

    def _build_system(self) -> str:
        ctx = self._workspace.get_context_summary()
        return f"{self.system_prompt}\n\n{ctx}"

    def _trim_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop earlier tool-call rounds to fit context window, keeping first and last messages."""
        if len(messages) <= 3:
            return messages
        # Keep the first user message and the last 2 messages (most recent exchange)
        return [messages[0]] + messages[-2:]

    def run(self, task_description: str) -> str:
        logger.info("[%s] Starting — %s", self.role, task_description[:80])
        tools = self._registry.get_schemas(self.tool_names or None)
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": task_description},
        ]

        final_text = ""
        for i in range(self.max_iterations):
            logger.debug("[%s] Iteration %d", self.role, i + 1)

            kwargs: dict[str, Any] = {
                "model": self._effective_model(),
                "max_tokens": self._effective_max_tokens(),
                "system": self._build_system(),
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            try:
                response = self._client.messages.create(**kwargs)
            except anthropic.BadRequestError as exc:
                if "prompt is too long" in str(exc):
                    logger.warning("[%s] Context too long, trimming messages", self.role)
                    messages = self._trim_messages(messages)
                    kwargs["messages"] = messages
                    response = self._client.messages.create(**kwargs)
                else:
                    raise

            # Collect any text produced in this turn
            for block in response.content:
                if block.type == "text":
                    final_text = block.text

            if response.stop_reason == "end_turn":
                logger.info("[%s] Finished (end_turn)", self.role)
                break

            if response.stop_reason != "tool_use":
                logger.info("[%s] Finished (stop_reason=%s)", self.role, response.stop_reason)
                break

            # Process tool calls
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tb in tool_use_blocks:
                logger.debug("[%s] Calling tool %s", self.role, tb.name)
                result = self._registry.execute(tb.name, tb.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tb.id,
                        "content": result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})
        else:
            logger.warning("[%s] Hit max_iterations (%d)", self.role, self.max_iterations)

        logger.info("[%s] Done", self.role)
        return final_text
