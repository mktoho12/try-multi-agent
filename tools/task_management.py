from __future__ import annotations

import json
import threading
import time
from typing import Any

from tools.registry import ToolDef

_lock = threading.Lock()
_tasks: list[dict[str, Any]] = []
_next_id = 1


def create_task(
    title: str,
    description: str,
    priority: str = "medium",
    assignee: str = "",
) -> str:
    global _next_id
    with _lock:
        task = {
            "id": _next_id,
            "title": title,
            "description": description,
            "priority": priority,
            "assignee": assignee,
            "status": "open",
            "created_at": time.time(),
        }
        _tasks.append(task)
        _next_id += 1
    return json.dumps({"status": "created", "task": task})


def update_task(task_id: int, status: str = "", assignee: str = "") -> str:
    with _lock:
        for t in _tasks:
            if t["id"] == task_id:
                if status:
                    t["status"] = status
                if assignee:
                    t["assignee"] = assignee
                return json.dumps({"status": "updated", "task": t})
    return json.dumps({"error": f"Task {task_id} not found"})


def list_tasks(status: str = "", assignee: str = "") -> str:
    with _lock:
        result = list(_tasks)
    if status:
        result = [t for t in result if t["status"] == status]
    if assignee:
        result = [t for t in result if t["assignee"] == assignee]
    return json.dumps({"tasks": result})


CREATE_TASK = ToolDef(
    name="create_task",
    description="Create a new task for tracking work items.",
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Task title"},
            "description": {"type": "string", "description": "Task description"},
            "priority": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low", "lowest"],
                "description": "Task priority",
            },
            "assignee": {"type": "string", "description": "Assigned agent role"},
        },
        "required": ["title", "description"],
    },
    handler=create_task,
)

UPDATE_TASK = ToolDef(
    name="update_task",
    description="Update the status or assignee of a task.",
    input_schema={
        "type": "object",
        "properties": {
            "task_id": {"type": "integer", "description": "Task ID"},
            "status": {"type": "string", "description": "New status (open/in_progress/done)"},
            "assignee": {"type": "string", "description": "New assignee"},
        },
        "required": ["task_id"],
    },
    handler=update_task,
)

LIST_TASKS = ToolDef(
    name="list_tasks",
    description="List tasks, optionally filtered by status or assignee.",
    input_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "Filter by status"},
            "assignee": {"type": "string", "description": "Filter by assignee"},
        },
    },
    handler=list_tasks,
)
