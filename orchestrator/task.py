from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Priority(enum.IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM_HIGH = 2
    MEDIUM = 3
    LOW = 4
    LOWEST = 5


@dataclass
class Task:
    title: str
    description: str
    priority: Priority = Priority.MEDIUM
    assignee: str = ""
    status: str = "pending"
