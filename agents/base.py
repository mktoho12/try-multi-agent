from __future__ import annotations

import logging
import sys
from typing import Any

import anthropic

import config
from tools.registry import ToolRegistry
from workspace.shared import SharedWorkspace

logger = logging.getLogger(__name__)

# ── ANSI color helpers ──────────────────────────────────────────────
_ROLE_COLORS: dict[str, str] = {
    "orchestrator":       "\033[95m",   # magenta
    "product_manager":    "\033[96m",   # cyan
    "system_architect":   "\033[93m",   # yellow
    "db_architect":       "\033[94m",   # blue
    "backend_engineer":   "\033[92m",   # green
    "frontend_engineer":  "\033[91m",   # red
    "code_reviewer":      "\033[33m",   # dark yellow
    "test_engineer":      "\033[36m",   # dark cyan
    "security_reviewer":  "\033[35m",   # dark magenta
    "infra_engineer":     "\033[34m",   # dark blue
    "it_systems":         "\033[32m",   # dark green
    "operator":           "\033[37m",   # white
    "legal_agent":        "\033[90m",   # gray
    "tax_agent":          "\033[90m",   # gray
    "document_writer":    "\033[97m",   # bright white
    "validation_engineer":"\033[31;1m", # bold red
}
_RESET = "\033[0m"
_BOLD  = "\033[1m"
_DIM   = "\033[2m"


def _color(role: str) -> str:
    return _ROLE_COLORS.get(role, "\033[0m")


def _role_tag(role: str) -> str:
    return f"{_BOLD}{_color(role)}{role}{_RESET}"


def _emit(role: str, icon: str, msg: str) -> None:
    """Print a colored activity line directly to stderr (bypasses log formatting)."""
    tag = _role_tag(role)
    print(f"  {tag} {icon} {msg}", file=sys.stderr, flush=True)


def _format_tool_detail(name: str, inp: dict[str, Any]) -> str:
    """Summarise tool call arguments into a short readable string."""
    if name == "write_file":
        path = inp.get("path", "?")
        size = len(inp.get("content", ""))
        return f"{path}  ({size:,} chars)"
    if name == "read_file":
        return inp.get("path", "?")
    if name == "list_files":
        return inp.get("path", "/") or "/"
    if name == "run_shell":
        cmd = inp.get("command", "?")
        return cmd if len(cmd) <= 60 else cmd[:57] + "..."
    if name == "send_message":
        to = inp.get("to", "?")
        body = inp.get("content", "")[:40]
        return f"-> {to}: {body}"
    if name == "submit_feedback":
        sev = inp.get("severity", "?")
        summary = inp.get("summary", "?")[:50]
        return f"[{sev}] {summary}"
    if name == "create_task":
        return inp.get("title", "?")[:50]
    if name == "read_messages":
        return ""
    if name == "browser_navigate":
        return inp.get("url", "?")
    if name == "browser_screenshot":
        return inp.get("filename", "screenshot.png")
    if name == "browser_console_errors":
        return ""
    # generic fallback
    s = str(inp)
    return s if len(s) <= 60 else s[:57] + "..."


# ── Tool-name icons ────────────────────────────────────────────────
_TOOL_ICONS: dict[str, str] = {
    "write_file":      ">> ",
    "read_file":       "<< ",
    "list_files":      "ls ",
    "run_shell":       " $ ",
    "send_message":    "=>",
    "read_messages":   "<=",
    "submit_feedback": "!! ",
    "create_task":     "++ ",
    "browser_navigate":      ":: ",
    "browser_screenshot":    "[] ",
    "browser_console_errors":"!! ",
}


# ── Agent iteration stats ─────────────────────────────────────────
_agent_stats: list[dict[str, Any]] = []


def clear_agent_stats() -> None:
    _agent_stats.clear()


def get_agent_stats() -> list[dict[str, Any]]:
    return list(_agent_stats)


def print_agent_stats_summary() -> None:
    """Print a table summarising iteration usage per agent."""
    if not _agent_stats:
        return
    print(f"\n{'':>2}{'Agent':<24} {'Used':>5} / {'Max':>5}  Status", file=sys.stderr, flush=True)
    print(f"{'':>2}{'-' * 52}", file=sys.stderr, flush=True)
    for s in _agent_stats:
        role = s["role"]
        used = s["iterations_used"]
        mx = s["max_iterations"]
        hit = s["hit_max"]
        tag = _role_tag(role)
        status = f"{_BOLD}\033[31mHIT LIMIT{_RESET}" if hit else "ok"
        print(f"  {tag:<44} {used:>5} / {mx:>5}  {status}", file=sys.stderr, flush=True)
    print(file=sys.stderr, flush=True)


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

    _MAX_RESULT_CHARS = 200

    def _trim_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Shrink tool results in older messages instead of dropping them entirely."""
        if len(messages) <= 3:
            return messages
        trimmed = []
        # Keep first message and last 4 messages intact
        keep_last = 4
        for idx, msg in enumerate(messages):
            if idx == 0 or idx >= len(messages) - keep_last:
                trimmed.append(msg)
                continue
            # For older user messages containing tool_results, truncate the content
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                new_content = []
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        content = block.get("content", "")
                        if isinstance(content, str) and len(content) > self._MAX_RESULT_CHARS:
                            block = {**block, "content": content[:self._MAX_RESULT_CHARS] + "… [trimmed]"}
                    new_content.append(block)
                trimmed.append({**msg, "content": new_content})
            else:
                trimmed.append(msg)
        return trimmed

    def run(self, task_description: str) -> str:
        _emit(self.role, "~~", f"starting  ({self._effective_model()})")
        tools = self._registry.get_schemas(self.tool_names or None)
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": task_description},
        ]

        final_text = ""
        hit_max = False
        iterations_used = 0
        for i in range(self.max_iterations):

            kwargs: dict[str, Any] = {
                "model": self._effective_model(),
                "max_tokens": self._effective_max_tokens(),
                "system": [
                    {
                        "type": "text",
                        "text": self._build_system(),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": messages,
            }
            if tools:
                cached_tools = [dict(t) for t in tools]
                cached_tools[-1] = {**cached_tools[-1], "cache_control": {"type": "ephemeral"}}
                kwargs["tools"] = cached_tools

            try:
                response = self._client.messages.create(**kwargs)
            except anthropic.BadRequestError as exc:
                if "prompt is too long" in str(exc):
                    _emit(self.role, "!!", "context too long — trimming")
                    messages = self._trim_messages(messages)
                    kwargs["messages"] = messages
                    response = self._client.messages.create(**kwargs)
                else:
                    raise

            usage = response.usage
            cache_create = getattr(usage, "cache_creation_input_tokens", 0)
            cache_read = getattr(usage, "cache_read_input_tokens", 0)
            cache_parts: list[str] = []
            if cache_create:
                cache_parts.append(f"cache_create={cache_create:,}")
            if cache_read:
                cache_parts.append(f"cache_read={cache_read:,}")
            cache_info = f"  ({', '.join(cache_parts)})" if cache_parts else ""

            # Collect any text produced in this turn
            for block in response.content:
                if block.type == "text":
                    final_text = block.text
                    # Show first meaningful line of agent's thinking
                    first_line = block.text.strip().split("\n")[0][:80]
                    if first_line:
                        c = _color(self.role)
                        _emit(self.role, "..", f"{_DIM}{c}{first_line}{_RESET}")

            if response.stop_reason == "end_turn":
                iterations_used = i + 1
                _emit(self.role, "OK", f"done  (iter {i + 1}){cache_info}")
                break

            if response.stop_reason != "tool_use":
                iterations_used = i + 1
                _emit(self.role, "OK", f"done  (iter {i + 1}, {response.stop_reason}){cache_info}")
                break

            # Process tool calls — show cache stats for intermediate iterations
            if cache_info:
                _emit(self.role, "$$", f"iter {i + 1}{cache_info}")
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tb in tool_use_blocks:
                icon = _TOOL_ICONS.get(tb.name, "?  ")
                detail = _format_tool_detail(tb.name, tb.input)
                _emit(self.role, icon, detail)
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
            iterations_used = self.max_iterations
            hit_max = True
            _emit(self.role, "!!", f"hit max iterations ({self.max_iterations})")

        _agent_stats.append({
            "role": self.role,
            "iterations_used": iterations_used,
            "max_iterations": self.max_iterations,
            "hit_max": hit_max,
        })

        return final_text
