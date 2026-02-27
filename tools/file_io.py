from __future__ import annotations

import json

from tools.registry import ToolDef
from workspace.shared import SharedWorkspace

_workspace: SharedWorkspace | None = None


def set_workspace(ws: SharedWorkspace) -> None:
    global _workspace
    _workspace = ws


def _get_ws() -> SharedWorkspace:
    if _workspace is None:
        raise RuntimeError("Workspace not initialised")
    return _workspace


def read_file(path: str) -> str:
    content = _get_ws().read_file(path)
    if content is None:
        return json.dumps({"error": f"File not found: {path}"})
    return json.dumps({"content": content})


def write_file(path: str, content: str, author: str = "unknown") -> str:
    _get_ws().write_file(path, content, author)
    return json.dumps({"status": "ok", "path": path})


def list_files(pattern: str = "**/*") -> str:
    files = _get_ws().list_files(pattern)
    return json.dumps({"files": files})


READ_FILE = ToolDef(
    name="read_file",
    description="Read a file from the shared workspace. Returns file content.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path in the workspace"},
        },
        "required": ["path"],
    },
    handler=read_file,
)

WRITE_FILE = ToolDef(
    name="write_file",
    description="Write or overwrite a file in the shared workspace.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path in the workspace"},
            "content": {"type": "string", "description": "File content to write"},
            "author": {"type": "string", "description": "Author name / agent role"},
        },
        "required": ["path", "content"],
    },
    handler=write_file,
)

LIST_FILES = ToolDef(
    name="list_files",
    description="List files in the workspace matching a glob pattern.",
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern (default **/*)",
            },
        },
    },
    handler=list_files,
)
