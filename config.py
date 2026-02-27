import os
from pathlib import Path

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
WORKSPACE_DIR = Path(__file__).parent / "workspace_output"
