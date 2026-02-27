from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., str]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool_def: ToolDef) -> None:
        self._tools[tool_def.name] = tool_def

    def get_schemas(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        targets = names if names else list(self._tools.keys())
        schemas: list[dict[str, Any]] = []
        for name in targets:
            if name not in self._tools:
                continue
            td = self._tools[name]
            schemas.append(
                {
                    "name": td.name,
                    "description": td.description,
                    "input_schema": td.input_schema,
                }
            )
        return schemas

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        if name not in self._tools:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            return self._tools[name].handler(**arguments)
        except Exception as e:
            return json.dumps({"error": str(e)})
