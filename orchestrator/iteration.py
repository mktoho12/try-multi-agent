"""Data structures for iterative orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FeedbackItem:
    """Structured feedback from a reviewer agent."""

    reviewer_role: str  # "operator", "it_systems", "code_reviewer", etc.
    category: str  # "usability" | "security" | "performance" | "correctness" | "operations"
    severity: str  # "critical" | "major" | "minor" | "suggestion"
    target_file: str  # target file path (empty string = general)
    summary: str  # one-line summary
    detail: str  # detailed description
    suggested_fix: str  # suggested fix


@dataclass
class IterationScope:
    """Scope decided by the orchestrator agent for a single iteration."""

    action: str  # "build" | "converged" | "escalate"
    builder_agents: list[str] = field(default_factory=list)
    reviewer_agents: list[str] = field(default_factory=list)
    agent_instructions: dict[str, str] = field(default_factory=dict)  # role → instruction
    focus_areas: list[str] = field(default_factory=list)
    escalation_reason: str = ""


@dataclass
class IterationRecord:
    """Record of a single iteration's results."""

    number: int
    build_results: dict[str, str] = field(default_factory=dict)
    feedback: list[FeedbackItem] = field(default_factory=list)
