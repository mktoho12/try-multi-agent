from __future__ import annotations

from dataclasses import dataclass, field

from orchestrator.task import Priority


@dataclass
class Phase:
    name: str
    priority: Priority
    agent_roles: list[str]
    depends_on: list[str] = field(default_factory=list)
