"""Feedback tools for iterative review cycles."""

from __future__ import annotations

import json
import threading
from typing import Any

from tools.registry import ToolDef

_lock = threading.Lock()
_feedback_store: list[dict[str, Any]] = []
_next_id = 1


def clear_store() -> None:
    """Reset feedback store (for testing or between runs)."""
    global _next_id
    with _lock:
        _feedback_store.clear()
        _next_id = 1


def submit_feedback(
    iteration: int,
    reviewer_role: str,
    category: str,
    severity: str,
    target_file: str = "",
    summary: str = "",
    detail: str = "",
    suggested_fix: str = "",
) -> str:
    global _next_id
    with _lock:
        item = {
            "id": _next_id,
            "iteration": iteration,
            "reviewer_role": reviewer_role,
            "category": category,
            "severity": severity,
            "target_file": target_file,
            "summary": summary,
            "detail": detail,
            "suggested_fix": suggested_fix,
            "status": "open",
        }
        _feedback_store.append(item)
        _next_id += 1
    return json.dumps({"status": "submitted", "feedback": item})


def list_feedback(
    iteration: int = 0,
    severity: str = "",
    status: str = "",
) -> str:
    with _lock:
        result = list(_feedback_store)
    if iteration:
        result = [f for f in result if f["iteration"] == iteration]
    if severity:
        result = [f for f in result if f["severity"] == severity]
    if status:
        result = [f for f in result if f["status"] == status]
    return json.dumps({"feedback": result, "total": len(result)})


def update_feedback_status(
    feedback_id: int,
    status: str,
    note: str = "",
) -> str:
    with _lock:
        for item in _feedback_store:
            if item["id"] == feedback_id:
                item["status"] = status
                if note:
                    item["resolution_note"] = note
                return json.dumps({"status": "updated", "feedback": item})
    return json.dumps({"error": f"Feedback {feedback_id} not found"})


SUBMIT_FEEDBACK = ToolDef(
    name="submit_feedback",
    description=(
        "Submit structured review feedback. Use this to report issues found during review. "
        "severity: critical | major | minor | suggestion. "
        "category: usability | security | performance | correctness | operations."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "iteration": {"type": "integer", "description": "Current iteration number"},
            "reviewer_role": {"type": "string", "description": "Your agent role name"},
            "category": {
                "type": "string",
                "enum": ["usability", "security", "performance", "correctness", "operations"],
                "description": "Feedback category",
            },
            "severity": {
                "type": "string",
                "enum": ["critical", "major", "minor", "suggestion"],
                "description": "Issue severity",
            },
            "target_file": {
                "type": "string",
                "description": "Target file path (empty for general feedback)",
            },
            "summary": {"type": "string", "description": "One-line summary of the issue"},
            "detail": {"type": "string", "description": "Detailed description"},
            "suggested_fix": {"type": "string", "description": "Suggested fix or improvement"},
        },
        "required": ["iteration", "reviewer_role", "category", "severity", "summary", "detail"],
    },
    handler=submit_feedback,
)

LIST_FEEDBACK = ToolDef(
    name="list_feedback",
    description="List feedback items, optionally filtered by iteration, severity, or status.",
    input_schema={
        "type": "object",
        "properties": {
            "iteration": {"type": "integer", "description": "Filter by iteration number"},
            "severity": {
                "type": "string",
                "enum": ["critical", "major", "minor", "suggestion"],
                "description": "Filter by severity",
            },
            "status": {
                "type": "string",
                "enum": ["open", "addressed", "deferred"],
                "description": "Filter by status",
            },
        },
    },
    handler=list_feedback,
)

UPDATE_FEEDBACK_STATUS = ToolDef(
    name="update_feedback_status",
    description="Update feedback status to 'addressed' or 'deferred' after handling it.",
    input_schema={
        "type": "object",
        "properties": {
            "feedback_id": {"type": "integer", "description": "Feedback item ID"},
            "status": {
                "type": "string",
                "enum": ["addressed", "deferred"],
                "description": "New status",
            },
            "note": {"type": "string", "description": "Resolution note"},
        },
        "required": ["feedback_id", "status"],
    },
    handler=update_feedback_status,
)
