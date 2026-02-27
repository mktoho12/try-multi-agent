from __future__ import annotations

import json
import subprocess

from tools.registry import ToolDef


def run_shell(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return json.dumps(
            {
                "stdout": result.stdout[:4000],
                "stderr": result.stderr[:2000],
                "returncode": result.returncode,
            }
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Command timed out after {timeout}s"})
    except Exception as e:
        return json.dumps({"error": str(e)})


RUN_SHELL = ToolDef(
    name="run_shell",
    description="Execute a shell command and return stdout/stderr/returncode.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 30)",
            },
        },
        "required": ["command"],
    },
    handler=run_shell,
)
